"""Pure TASK-P4-08 result-application contracts and ScheduleVersion builder."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import NoReturn, cast

from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    require_p4_document,
    schedule_content_fingerprint,
)
from app.domain.types import parse_utc_instant


REPLAN_APPLICATION_VERSION = "replan-application.v1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^(?:uncommitted|[0-9a-f]{40})$")
_ACTOR = re.compile(r"^actor:[A-Za-z0-9._:-]+$")
_CANONICAL_ID = re.compile(r"^[^\s\x00-\x1f\x7f]{1,256}$")


class ReplanApplicationFailure(StrEnum):
    """Stable, sanitized reasons owned by the P4 application boundary."""

    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    INVALID_INPUT = "INVALID_INPUT"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    STATE_CONFLICT = "STATE_CONFLICT"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    SOLVER_NO_CANDIDATE = "SOLVER_NO_CANDIDATE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CHANGE_REPORT_FAILED = "CHANGE_REPORT_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ReplanApplicationError(RuntimeError):
    """A no-secret failure exposed by the application service."""

    def __init__(
        self,
        reason: ReplanApplicationFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        super().__init__(f"{reason.value}: {field}: {message}")


def reject_replan_application(
    reason: ReplanApplicationFailure,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise ReplanApplicationError(reason, field=field, message=message)


@dataclass(frozen=True, slots=True)
class ReplanApplicationContext:
    """Server-bound context; request carriers cannot grant this authority."""

    data_plane: str
    environment: str
    production_binding: bool
    actor_ref: str
    idempotency_key_reference: str
    correlation_id: str
    occurred_at_utc: str
    planning_run_id: str
    attempt_number: int
    code_commit: str


@dataclass(frozen=True, slots=True)
class DynamicScheduleDraft:
    """One immutable DRAFT plus its exact references."""

    document: dict[str, object]
    schedule_reference: dict[str, object]
    candidate_reference: dict[str, object]
    validation_reference: dict[str, object]
    kpi_reference: dict[str, object]
    solver_reference: dict[str, object]
    change_report_reference: dict[str, object]


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message="must be an array",
        )
    return cast(Sequence[object], value)


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _CANONICAL_ID.fullmatch(value) is None:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message="must be a canonical identifier",
        )
    return value


def _fingerprint(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message="must be a lowercase SHA-256 fingerprint",
        )
    return value


def _clone(value: object, field: str) -> object:
    try:
        return json.loads(canonical_contract_bytes(value))
    except (TypeError, ValueError) as error:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message=f"must be canonical JSON ({type(error).__name__})",
        )


def _artifact_reference(
    *, document_version: str, artifact_id: str, fingerprint: str
) -> dict[str, object]:
    return {
        "document_version": _identifier(document_version, "document_version"),
        "artifact_id": _identifier(artifact_id, "artifact_id"),
        "fingerprint": _fingerprint(fingerprint, "fingerprint"),
    }


def require_replan_application_authorization(
    context: ReplanApplicationContext,
) -> None:
    """Default-deny Production before any repository or result lookup."""

    if (
        context.data_plane != "SIMULATION"
        or context.environment not in {"DEVELOPMENT", "TEST", "BENCHMARK"}
        or context.production_binding
    ):
        reject_replan_application(
            ReplanApplicationFailure.AUTHORIZATION_DENIED,
            field="data_plane/environment/production_binding",
            message="P4 result application has no Production authority",
        )
    if _ACTOR.fullmatch(context.actor_ref) is None:
        reject_replan_application(
            ReplanApplicationFailure.AUTHORIZATION_DENIED,
            field="actor_ref",
            message="server-bound actor reference is invalid",
        )
    _fingerprint(context.idempotency_key_reference, "idempotency_key_reference")
    _identifier(context.correlation_id, "correlation_id")
    _identifier(context.planning_run_id, "planning_run_id")
    if (
        isinstance(context.attempt_number, bool)
        or not isinstance(context.attempt_number, int)
        or context.attempt_number < 1
    ):
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field="attempt_number",
            message="must be an integer >= 1",
        )
    try:
        parse_utc_instant(context.occurred_at_utc)
    except (TypeError, ValueError) as error:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field="occurred_at_utc",
            message=f"must be a valid UTC instant ({type(error).__name__})",
        )
    if _COMMIT.fullmatch(context.code_commit) is None:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field="code_commit",
            message="must be a full lowercase commit SHA or uncommitted",
        )


def require_replan_request_context(
    request: Mapping[str, object], context: ReplanApplicationContext
) -> None:
    """Validate the frozen carrier and its server-bound execution context."""

    try:
        version = require_p4_document(request)
    except (KeyError, TypeError, ValueError) as error:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=getattr(error, "field", "replan_request"),
            message="ReplanRequest failed the frozen P4 contract",
        )
    if version != "replan-request.v1":
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field="replan_request_version",
            message="only replan-request.v1 is supported",
        )
    expected = {
        "data_plane": context.data_plane,
        "environment": context.environment,
        "production_binding": False,
        "synthetic": True,
        "correlation_id": context.correlation_id,
    }
    for field, value in expected.items():
        if request.get(field) != value:
            reject_replan_application(
                ReplanApplicationFailure.LINEAGE_MISMATCH,
                field=f"replan_request.{field}",
                message="request and server execution context differ",
            )


def schedule_identity(
    *, request_fingerprint: str, context: ReplanApplicationContext
) -> str:
    """Derive a stable version identity without depending on report wall time."""

    basis = {
        "application_version": REPLAN_APPLICATION_VERSION,
        "data_plane": context.data_plane,
        "request_fingerprint": _fingerprint(
            request_fingerprint, "request_fingerprint"
        ),
        "planning_run_id": context.planning_run_id,
        "attempt_number": context.attempt_number,
        "idempotency_key_reference": context.idempotency_key_reference,
    }
    return "schedule-version-replan-" + sha256(
        canonical_contract_bytes(basis)
    ).hexdigest()


def schedule_content(
    *, candidate: Mapping[str, object], effective_locks: Mapping[str, object]
) -> dict[str, object]:
    """Project solver assignments into the ScheduleVersion carrier shape."""

    assignments: list[dict[str, object]] = []
    for index, value in enumerate(
        _sequence(candidate.get("assignments"), "candidate.assignments")
    ):
        document = cast(
            dict[str, object], _clone(value, f"candidate.assignments[{index}]")
        )
        try:
            start = parse_utc_instant(
                _identifier(document.get("start_at_utc"), "start_at_utc")
            )
            end = parse_utc_instant(
                _identifier(document.get("end_at_utc"), "end_at_utc")
            )
        except (TypeError, ValueError) as error:
            reject_replan_application(
                ReplanApplicationFailure.INVALID_INPUT,
                field=f"candidate.assignments[{index}]",
                message=f"assignment time carrier is invalid ({type(error).__name__})",
            )
        elapsed = int((end - start).total_seconds())
        if elapsed <= 0:
            reject_replan_application(
                ReplanApplicationFailure.INVALID_INPUT,
                field=f"candidate.assignments[{index}].duration_seconds",
                message="planned ScheduleVersion duration must be positive",
            )
        # Solver duration is the processing requirement; the ScheduleVersion and
        # ChangeReport carriers describe the tick-rounded occupied UTC interval.
        document["duration_seconds"] = elapsed
        assignments.append(document)
    assignments.sort(
        key=lambda value: _identifier(value.get("operation_id"), "operation_id")
    )
    locks: dict[str, dict[str, object]] = {}
    sections = (
        ("explicit_hard_locks", "HARD"),
        ("freeze_derived_hard_locks", "HARD"),
        ("soft_locks", "SOFT"),
    )
    for section, lock_type in sections:
        for index, raw in enumerate(
            _sequence(effective_locks.get(section), f"effective_locks.{section}")
        ):
            protection = _mapping(raw, f"effective_locks.{section}[{index}]")
            lock_id = _identifier(
                protection.get("reference_id", protection.get("lock_id")),
                f"effective_locks.{section}[{index}].reference_id",
            )
            document = {
                "lock_id": lock_id,
                "operation_id": _identifier(
                    protection.get("operation_id"),
                    f"effective_locks.{section}[{index}].operation_id",
                ),
                "lock_type": lock_type,
                "resource_id": protection.get("resource_id"),
                "start_at_utc": protection.get("start_at_utc"),
                "end_at_utc": protection.get("end_at_utc"),
            }
            existing = locks.get(lock_id)
            if existing is not None and existing != document:
                reject_replan_application(
                    ReplanApplicationFailure.LINEAGE_MISMATCH,
                    field=f"effective_locks.{section}",
                    message="one lock identity is bound to different content",
                )
            locks[lock_id] = document
    return {"assignments": assignments, "locks": [locks[key] for key in sorted(locks)]}


def schedule_reference(
    *, schedule_version_id: str, content_fingerprint: str
) -> dict[str, object]:
    return {
        "schedule_version_version": "schedule-version.v2",
        "schedule_version_id": _identifier(
            schedule_version_id, "schedule_version_id"
        ),
        "state": "DRAFT",
        "content_fingerprint": _fingerprint(
            content_fingerprint, "content_fingerprint"
        ),
    }


def change_report_reference(change_report: Mapping[str, object]) -> dict[str, object]:
    return {
        "change_report_version": "change-report.v1",
        "report_id": _identifier(change_report.get("report_id"), "report_id"),
        "report_fingerprint": _fingerprint(
            change_report.get("report_fingerprint"), "report_fingerprint"
        ),
    }


def build_dynamic_schedule_draft(
    *,
    context: ReplanApplicationContext,
    base_schedule: Mapping[str, object],
    request: Mapping[str, object],
    candidate: Mapping[str, object],
    formal_validation: Mapping[str, object],
    kpi: Mapping[str, object],
    solver_report: Mapping[str, object],
    change_report: Mapping[str, object],
    effective_locks: Mapping[str, object],
) -> DynamicScheduleDraft:
    """Build the sole allowed P4 result: a fresh immutable DRAFT v2."""

    require_replan_application_authorization(context)
    require_replan_request_context(request, context)
    if base_schedule.get("state") != "PUBLISHED":
        reject_replan_application(
            ReplanApplicationFailure.STATE_CONFLICT,
            field="base_schedule.state",
            message="dynamic replan requires the current PUBLISHED base",
        )
    if formal_validation.get("status") != "PASS" or formal_validation.get(
        "hard_violation_count"
    ) != 0:
        reject_replan_application(
            ReplanApplicationFailure.VALIDATION_FAILED,
            field="formal_validation",
            message="fresh validation must PASS with zero hard violations",
        )
    content = schedule_content(candidate=candidate, effective_locks=effective_locks)
    content_document = {"content": content}
    content_fingerprint = schedule_content_fingerprint(content_document)
    request_fingerprint = _fingerprint(
        request.get("request_fingerprint"), "request.request_fingerprint"
    )
    schedule_version_id = schedule_identity(
        request_fingerprint=request_fingerprint, context=context
    )
    expected_reference = schedule_reference(
        schedule_version_id=schedule_version_id,
        content_fingerprint=content_fingerprint,
    )
    report_schedule = _mapping(
        change_report.get("new_schedule_version"),
        "change_report.new_schedule_version",
    )
    if dict(report_schedule) != expected_reference:
        reject_replan_application(
            ReplanApplicationFailure.CHANGE_REPORT_FAILED,
            field="change_report.new_schedule_version",
            message="ChangeReport does not bind the exact DRAFT identity/content",
        )

    candidate_fingerprint = _fingerprint(
        candidate.get("candidate_fingerprint"), "candidate_fingerprint"
    )
    candidate_reference = _artifact_reference(
        document_version="replan-candidate.v1",
        artifact_id="replan-candidate-"
        + candidate_fingerprint.removeprefix("sha256:"),
        fingerprint=candidate_fingerprint,
    )
    validation_fingerprint = contract_fingerprint(formal_validation)
    validation_reference = _artifact_reference(
        document_version="validation-report.v2",
        artifact_id="validation-report-"
        + validation_fingerprint.removeprefix("sha256:"),
        fingerprint=validation_fingerprint,
    )
    kpi_reference = _artifact_reference(
        document_version="kpi.v2",
        artifact_id=_identifier(kpi.get("kpi_id"), "kpi.kpi_id"),
        fingerprint=contract_fingerprint(kpi),
    )
    solver_reference = _artifact_reference(
        document_version="solver-report.v2",
        artifact_id=_identifier(
            solver_report.get("report_id"), "solver_report.report_id"
        ),
        fingerprint=_fingerprint(
            solver_report.get("report_fingerprint"),
            "solver_report.report_fingerprint",
        ),
    )
    report_reference = change_report_reference(change_report)
    base_reference = cast(
        dict[str, object],
        _clone(request.get("base_schedule_version"), "base_schedule_version"),
    )
    stream = _mapping(request.get("event_stream"), "request.event_stream")
    lineage = {
        "replan_request": {
            "replan_request_version": "replan-request.v1",
            "request_id": request["request_id"],
            "request_fingerprint": request_fingerprint,
        },
        "base_schedule_version": base_reference,
        "base_snapshot": _clone(request.get("base_snapshot"), "base_snapshot"),
        "base_problem": _clone(request.get("base_problem"), "base_problem"),
        "new_snapshot": _clone(request.get("new_snapshot"), "new_snapshot"),
        "new_problem": _clone(request.get("new_problem"), "new_problem"),
        "event_stream_fingerprint": stream.get("stream_fingerprint"),
        "fact_checkpoint": _clone(
            stream.get("fact_checkpoint"), "event_stream.fact_checkpoint"
        ),
        "planning_run_id": context.planning_run_id,
        "candidate": candidate_reference,
        "validation_report": validation_reference,
        "kpi": kpi_reference,
        "solver_report": solver_reference,
        "change_report": report_reference,
        "code_commit": context.code_commit,
    }
    revision = base_schedule.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field="base_schedule.revision",
            message="must be an integer >= 1",
        )
    document: dict[str, object] = {
        "schedule_version_version": "schedule-version.v2",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "schedule_version_id": schedule_version_id,
        "revision": revision + 1,
        "state": "DRAFT",
        "data_plane": "SIMULATION",
        "environment": context.environment,
        "synthetic": True,
        "synthetic_provenance": _clone(
            request.get("synthetic_provenance"), "synthetic_provenance"
        ),
        "parent_schedule_version": base_reference,
        "source_kind": "DYNAMIC_REPLAN",
        "lineage": lineage,
        "content": content,
        "content_fingerprint": content_fingerprint,
        "validation": {
            "validation_report": validation_reference,
            "status": "PASS",
            "hard_violation_count": 0,
            "validated_at_utc": context.occurred_at_utc,
        },
        "decision": None,
        "publication": None,
        "superseded_by": None,
        "allowed_actions": ["view", "edit", "lock", "audit"],
        "created_at_utc": context.occurred_at_utc,
        "created_by_actor_ref": context.actor_ref,
    }
    try:
        require_p4_document(document)
    except (KeyError, TypeError, ValueError) as error:
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=getattr(error, "field", "schedule_version"),
            message="constructed DRAFT failed the frozen P4 contract",
        )
    return DynamicScheduleDraft(
        document=document,
        schedule_reference=expected_reference,
        candidate_reference=candidate_reference,
        validation_reference=validation_reference,
        kpi_reference=kpi_reference,
        solver_reference=solver_reference,
        change_report_reference=report_reference,
    )


__all__ = [
    "DynamicScheduleDraft",
    "REPLAN_APPLICATION_VERSION",
    "ReplanApplicationContext",
    "ReplanApplicationError",
    "ReplanApplicationFailure",
    "build_dynamic_schedule_draft",
    "change_report_reference",
    "reject_replan_application",
    "require_replan_application_authorization",
    "require_replan_request_context",
    "schedule_content",
    "schedule_identity",
    "schedule_reference",
]
