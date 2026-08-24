"""Pure validated-output to reviewable ScheduleVersion construction.

The module owns identity, lineage, and DRAFT/READY document construction only.
It performs no persistence, authorization, solver execution, approval,
publication, export, or PlanningRun mutation.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import re
from typing import Never, cast

from app.domain.state_machines.contracts import PlanningRunState
from app.domain.types import parse_utc_instant
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    require_workspace_document,
    schedule_content_fingerprint,
    workspace_fingerprint,
)


SCHEDULE_VERSION_LIFECYCLE_VERSION = "schedule-version-lifecycle.v1"
SCHEDULE_VERSION_SCHEMA_SET_VERSION = "2.6.0"
SCHEDULE_VERSION_CANONICALIZATION_VERSION = "canonical-json.v1"

_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_ACTOR_REFERENCE = re.compile(r"actor:[A-Za-z0-9._:-]+")
_GIT_COMMIT = re.compile(r"(?:[0-9a-f]{40}|uncommitted)")


class ScheduleVersionLifecycleFailure(StrEnum):
    """Stable module-local failure reasons for the P3-04 lifecycle."""

    INVALID_INPUT = "INVALID_INPUT"
    PLANNING_RUN_NOT_COMPLETED = "PLANNING_RUN_NOT_COMPLETED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MIXED_LINEAGE = "MIXED_LINEAGE"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ScheduleVersionLifecycleError(ValueError):
    """A sanitized lifecycle rejection with no SQL or credential details."""

    def __init__(
        self,
        reason: ScheduleVersionLifecycleFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value}: {field}: {message}")


@dataclass(frozen=True, slots=True)
class ValidatedPlanningOutput:
    """The complete immutable P2 output bundle consumed by P3-04."""

    snapshot: Mapping[str, object]
    problem: Mapping[str, object]
    solution: Mapping[str, object]
    solver_report: Mapping[str, object]
    validation_report: Mapping[str, object]
    import_quality_report: Mapping[str, object]
    kpi: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ScheduleVersionCreationContext:
    """Caller-supplied execution facts; no raw credential or idempotency key."""

    planning_run_state: str
    environment: str
    actor_ref: str
    auth_policy_version: str
    occurred_at_utc: str
    correlation_id: str
    idempotency_key_reference: str
    reason: str


@dataclass(frozen=True, slots=True)
class ReviewableScheduleDocuments:
    """Canonical documents required by one atomic lifecycle transaction."""

    draft: dict[str, object]
    ready_for_review: dict[str, object]
    audit_event: dict[str, object]
    request_fingerprint: str
    schedule_version_id: str
    audit_event_id: str
    validation_fingerprint: str
    kpi_fingerprint: str


def reject_lifecycle(
    reason: ScheduleVersionLifecycleFailure,
    *,
    field: str,
    message: str,
) -> Never:
    raise ScheduleVersionLifecycleError(reason, field=field, message=message)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field=field,
            message="must be bounded non-empty text",
        )
    return value


def _fingerprint(value: object, field: str) -> str:
    text = _text(value, field)
    if _FINGERPRINT.fullmatch(text) is None:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field=field,
            message="must be sha256:<64 lowercase hex>",
        )
    return text


def _canonical_clone(value: Mapping[str, object]) -> dict[str, object]:
    import json

    return cast(dict[str, object], json.loads(canonical_workspace_bytes(value)))


def _artifact_reference(
    *, document_version: str, artifact_id: str, fingerprint: str
) -> dict[str, object]:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": fingerprint,
    }


def _require_exact(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.MIXED_LINEAGE,
            field=field,
            message="does not bind the supplied validated lineage",
        )


def _validate_context(context: ScheduleVersionCreationContext, data_plane: str) -> None:
    if context.planning_run_state != PlanningRunState.COMPLETED.value:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.PLANNING_RUN_NOT_COMPLETED,
            field="planning_run_state",
            message="validated output may be consumed only after COMPLETED",
        )
    if not isinstance(data_plane, str) or data_plane not in {
        "SIMULATION",
        "PRODUCTION",
    }:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH,
            field="data_plane",
            message="must be SIMULATION or PRODUCTION",
        )
    allowed_environments = {
        "SIMULATION": {"DEVELOPMENT", "TEST", "BENCHMARK"},
        "PRODUCTION": {"PRODUCTION"},
    }
    if (
        not isinstance(context.environment, str)
        or context.environment not in allowed_environments[data_plane]
    ):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH,
            field="environment",
            message="environment is incompatible with the repository plane",
        )
    actor_ref = _text(context.actor_ref, "actor_ref")
    if _ACTOR_REFERENCE.fullmatch(actor_ref) is None:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="actor_ref",
            message="must be a sanitized actor reference",
        )
    _text(context.auth_policy_version, "auth_policy_version")
    _text(context.correlation_id, "correlation_id")
    _fingerprint(context.idempotency_key_reference, "idempotency_key_reference")
    reason = _text(context.reason, "reason")
    if any(ord(character) < 32 or ord(character) == 127 for character in reason):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="reason",
            message="must not contain control characters",
        )
    occurred_at_utc = _text(context.occurred_at_utc, "occurred_at_utc")
    if not occurred_at_utc.endswith("Z"):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="occurred_at_utc",
            message="must be an explicit UTC instant",
        )
    try:
        parse_utc_instant(occurred_at_utc)
    except (TypeError, ValueError) as error:
        raise ScheduleVersionLifecycleError(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="occurred_at_utc",
            message="must be a valid UTC instant",
        ) from error


def _lineage(
    output: ValidatedPlanningOutput,
) -> tuple[dict[str, object], bool, dict[str, object] | None, str, str]:
    snapshot = output.snapshot
    problem = output.problem
    solution = output.solution
    solver_report = output.solver_report
    validation_report = output.validation_report
    kpi = output.kpi

    _require_exact(snapshot.get("snapshot_version"), "planning-snapshot.v2", "snapshot")
    _require_exact(problem.get("problem_version"), "planning-problem.v2", "problem")
    _require_exact(
        solution.get("planning_solution_version"),
        "planning-solution.v1",
        "solution",
    )
    _require_exact(
        validation_report.get("validation_report_version"),
        "validation-report.v2",
        "validation_report",
    )
    _require_exact(
        solver_report.get("solver_report_version"),
        "solver-report.v1",
        "solver_report",
    )
    _require_exact(kpi.get("kpi_version"), "kpi.v2", "kpi")

    snapshot_id = _text(snapshot.get("snapshot_id"), "snapshot.snapshot_id")
    snapshot_hash = _fingerprint(
        snapshot.get("snapshot_hash"), "snapshot.snapshot_hash"
    )
    problem_hash = _fingerprint(problem.get("problem_hash"), "problem.problem_hash")
    solution_id = _text(solution.get("solution_id"), "solution.solution_id")
    report_id = _text(solver_report.get("report_id"), "solver_report.report_id")
    kpi_id = _text(kpi.get("kpi_id"), "kpi.kpi_id")
    planning_run_id = _text(
        solver_report.get("planning_run_id"), "solver_report.planning_run_id"
    )

    solution_fingerprint = workspace_fingerprint(solution)
    validation_fingerprint = workspace_fingerprint(validation_report)
    solver_fingerprint = workspace_fingerprint(solver_report)
    kpi_fingerprint = workspace_fingerprint(kpi)

    _require_exact(problem.get("snapshot_id"), snapshot_id, "problem.snapshot_id")
    solution_problem = _mapping(solution.get("problem"), "solution.problem")
    _require_exact(
        solution_problem.get("problem_hash"), problem_hash, "solution.problem_hash"
    )
    _require_exact(
        solution_problem.get("snapshot_id"), snapshot_id, "solution.problem.snapshot_id"
    )
    _require_exact(
        validation_report.get("problem_hash"),
        problem_hash,
        "validation_report.problem_hash",
    )
    if (
        validation_report.get("status") != "PASS"
        or validation_report.get("hard_violation_count") != 0
        or validation_report.get("violations") != []
    ):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.VALIDATION_FAILED,
            field="validation_report",
            message="an exact PASS with zero hard violations is required",
        )

    solver_solution = _mapping(solver_report.get("solution"), "solver_report.solution")
    _require_exact(
        solver_solution.get("solution_id"), solution_id, "solver_report.solution_id"
    )
    _require_exact(
        solver_solution.get("solution_fingerprint"),
        solution_fingerprint,
        "solver_report.solution_fingerprint",
    )
    provenance = _mapping(solver_report.get("provenance"), "solver_report.provenance")
    code_commit = _text(provenance.get("code_commit"), "provenance.code_commit")
    if _GIT_COMMIT.fullmatch(code_commit) is None:
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="provenance.code_commit",
            message="must be a full lowercase commit SHA or uncommitted",
        )

    _require_exact(kpi.get("planning_run_id"), planning_run_id, "kpi.planning_run_id")
    kpi_inputs = _mapping(kpi.get("inputs"), "kpi.inputs")
    expected_input_values: tuple[tuple[str, str, object], ...] = (
        ("snapshot", "snapshot_hash", snapshot_hash),
        ("problem", "problem_hash", problem_hash),
        ("solution", "solution_fingerprint", solution_fingerprint),
        (
            "validation_report",
            "validation_report_fingerprint",
            validation_fingerprint,
        ),
        ("solver_report", "solver_report_fingerprint", solver_fingerprint),
    )
    for container, field, expected in expected_input_values:
        reference = _mapping(kpi_inputs.get(container), f"kpi.inputs.{container}")
        _require_exact(
            reference.get(field), expected, f"kpi.inputs.{container}.{field}"
        )

    synthetic = snapshot.get("synthetic")
    if not isinstance(synthetic, bool):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="snapshot.synthetic",
            message="must be boolean",
        )
    synthetic_provenance: dict[str, object] | None = None
    if synthetic:
        synthetic_provenance = _canonical_clone(
            _mapping(
                snapshot.get("synthetic_provenance"),
                "snapshot.synthetic_provenance",
            )
        )

    lineage = {
        "planning_run_id": planning_run_id,
        "snapshot": _artifact_reference(
            document_version="planning-snapshot.v2",
            artifact_id=snapshot_id,
            fingerprint=snapshot_hash,
        ),
        "problem": _artifact_reference(
            document_version="planning-problem.v2",
            artifact_id=f"planning-problem-{problem_hash.removeprefix('sha256:')}",
            fingerprint=problem_hash,
        ),
        "planning_solution": _artifact_reference(
            document_version="planning-solution.v1",
            artifact_id=solution_id,
            fingerprint=solution_fingerprint,
        ),
        "validation_report": _artifact_reference(
            document_version="validation-report.v2",
            artifact_id=(
                f"validation-report-{validation_fingerprint.removeprefix('sha256:')}"
            ),
            fingerprint=validation_fingerprint,
        ),
        "kpi": _artifact_reference(
            document_version="kpi.v2",
            artifact_id=kpi_id,
            fingerprint=kpi_fingerprint,
        ),
        "solver_report": _artifact_reference(
            document_version="solver-report.v1",
            artifact_id=report_id,
            fingerprint=solver_fingerprint,
        ),
        "code_commit": code_commit,
    }
    return lineage, synthetic, synthetic_provenance, planning_run_id, code_commit


def _schedule_content(output: ValidatedPlanningOutput) -> dict[str, object]:
    raw_assignments = output.solution.get("assignments")
    if not isinstance(raw_assignments, list):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="solution.assignments",
            message="must be an array",
        )
    assignments = [
        _canonical_clone(_mapping(value, f"solution.assignments[{index}]"))
        for index, value in enumerate(raw_assignments)
    ]
    assignments.sort(key=lambda value: _text(value.get("operation_id"), "operation_id"))

    raw_locks = output.problem.get("operation_locks")
    if not isinstance(raw_locks, list):
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="problem.operation_locks",
            message="must be an array",
        )
    lock_type_mapping = {"HARD_LOCK": "HARD", "SOFT_LOCK": "SOFT"}
    locks: list[dict[str, object]] = []
    for index, raw_lock in enumerate(raw_locks):
        lock = _mapping(raw_lock, f"problem.operation_locks[{index}]")
        source_lock_type = _text(
            lock.get("lock_type"), f"problem.operation_locks[{index}].lock_type"
        )
        lock_type = lock_type_mapping.get(source_lock_type)
        if lock_type is None:
            reject_lifecycle(
                ScheduleVersionLifecycleFailure.INVALID_INPUT,
                field=f"problem.operation_locks[{index}].lock_type",
                message="must be HARD_LOCK or SOFT_LOCK",
            )
        locks.append(
            {
                "lock_id": _text(lock.get("lock_id"), "lock.lock_id"),
                "operation_id": _text(lock.get("operation_id"), "lock.operation_id"),
                "lock_type": lock_type,
                "resource_id": _text(lock.get("resource_id"), "lock.resource_id"),
                "start_at_utc": _text(lock.get("start_at_utc"), "lock.start_at_utc"),
                "end_at_utc": _text(lock.get("end_at_utc"), "lock.end_at_utc"),
            }
        )
    locks.sort(key=lambda value: cast(str, value["lock_id"]))
    return {"assignments": assignments, "locks": locks}


def build_reviewable_schedule_documents(
    output: ValidatedPlanningOutput,
    context: ScheduleVersionCreationContext,
    *,
    data_plane: str,
) -> ReviewableScheduleDocuments:
    """Build one DRAFT, its READY transition candidate, and atomic audit event."""

    _validate_context(context, data_plane)
    lineage, synthetic, synthetic_provenance, planning_run_id, code_commit = _lineage(
        output
    )
    if synthetic and data_plane != "SIMULATION":
        reject_lifecycle(
            ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH,
            field="snapshot.synthetic/data_plane",
            message="synthetic P2 output is restricted to the SIMULATION plane",
        )

    identity_basis = {
        "lifecycle_version": SCHEDULE_VERSION_LIFECYCLE_VERSION,
        "data_plane": data_plane,
        "idempotency_key_reference": context.idempotency_key_reference,
    }
    identity_suffix = sha256(canonical_workspace_bytes(identity_basis)).hexdigest()
    schedule_version_id = f"schedule-version-validated-{identity_suffix}"
    audit_event_id = f"audit-event-submit-for-review-{identity_suffix}"
    idempotency_scope = (
        f"{data_plane}/SUBMIT_FOR_REVIEW/{schedule_version_id}/WORKSPACE_INTERNAL"
    )

    content = _schedule_content(output)
    request_basis: dict[str, object] = {
        "lifecycle_version": SCHEDULE_VERSION_LIFECYCLE_VERSION,
        "action": "SUBMIT_FOR_REVIEW",
        "planning_run_state": context.planning_run_state,
        "data_plane": data_plane,
        "environment": context.environment,
        "actor_ref": context.actor_ref,
        "auth_policy_version": context.auth_policy_version,
        "occurred_at_utc": context.occurred_at_utc,
        "correlation_id": context.correlation_id,
        "idempotency_key_reference": context.idempotency_key_reference,
        "reason": context.reason,
        "lineage": lineage,
        "content_fingerprint": workspace_fingerprint(content),
    }
    if synthetic_provenance is not None:
        request_basis["synthetic_provenance"] = synthetic_provenance
    request_fingerprint = workspace_fingerprint(request_basis)

    draft: dict[str, object] = {
        "schedule_version_version": "schedule-version.v1",
        "schema_set_version": SCHEDULE_VERSION_SCHEMA_SET_VERSION,
        "canonicalization_version": SCHEDULE_VERSION_CANONICALIZATION_VERSION,
        "schedule_version_id": schedule_version_id,
        "revision": 1,
        "state": "DRAFT",
        "data_plane": data_plane,
        "environment": context.environment,
        "synthetic": synthetic,
        "parent_schedule_version": None,
        "source_kind": "VALIDATED_SOLUTION",
        "lineage": lineage,
        "content": content,
        "content_fingerprint": workspace_fingerprint(content),
        "validation": {
            "validation_report": lineage["validation_report"],
            "status": "PASS",
            "hard_violation_count": 0,
            "validated_at_utc": context.occurred_at_utc,
        },
        "decision": None,
        "publication": None,
        "superseded_by": None,
        "allowed_actions": ["view", "edit", "lock"],
        "created_at_utc": context.occurred_at_utc,
        "created_by_actor_ref": context.actor_ref,
    }
    if synthetic_provenance is not None:
        draft["synthetic_provenance"] = synthetic_provenance
    draft["content_fingerprint"] = schedule_content_fingerprint(draft)

    ready = deepcopy(draft)
    ready.update(
        {
            "state": "READY_FOR_REVIEW",
            "allowed_actions": ["view", "approve", "reject"],
        }
    )
    version_reference = {
        "schedule_version_id": schedule_version_id,
        "content_fingerprint": draft["content_fingerprint"],
    }
    audit_event: dict[str, object] = {
        "audit_event_version": "audit-event.v1",
        "schema_set_version": SCHEDULE_VERSION_SCHEMA_SET_VERSION,
        "canonicalization_version": SCHEDULE_VERSION_CANONICALIZATION_VERSION,
        "audit_event_id": audit_event_id,
        "occurred_at_utc": context.occurred_at_utc,
        "actor_ref": context.actor_ref,
        "resolved_capability": "edit",
        "auth_policy_version": context.auth_policy_version,
        "environment": context.environment,
        "data_plane": data_plane,
        "synthetic": synthetic,
        "action": "SUBMIT_FOR_REVIEW",
        "aggregate_type": "SCHEDULE_VERSION",
        "aggregate_id": schedule_version_id,
        "target": "WORKSPACE_INTERNAL",
        "intent_type": "COMMAND",
        "reason": context.reason,
        "request_fingerprint": request_fingerprint,
        "idempotency_reference": {
            "scope": idempotency_scope,
            "key_reference": context.idempotency_key_reference,
            "request_fingerprint": request_fingerprint,
        },
        "lineage": lineage,
        "before_state": "DRAFT",
        "after_state": "READY_FOR_REVIEW",
        "source_version": {**version_reference, "state": "DRAFT"},
        "new_version": {**version_reference, "state": "READY_FOR_REVIEW"},
        "export_job_id": None,
        "result": {
            "outcome": "SUCCEEDED",
            "replayed": False,
            "retryable": False,
            "error": None,
        },
        "correlation_id": context.correlation_id,
        "parent_audit_event_id": None,
        "code_commit": code_commit,
    }
    if synthetic_provenance is not None:
        audit_event["synthetic_provenance"] = synthetic_provenance

    try:
        require_workspace_document(draft)
        require_workspace_document(ready)
        require_workspace_document(audit_event)
    except (TypeError, ValueError) as error:
        raise ScheduleVersionLifecycleError(
            ScheduleVersionLifecycleFailure.INVALID_INPUT,
            field="schedule_version/audit_event",
            message="constructed workspace carrier failed its pure contract",
        ) from error

    return ReviewableScheduleDocuments(
        draft=draft,
        ready_for_review=ready,
        audit_event=audit_event,
        request_fingerprint=request_fingerprint,
        schedule_version_id=schedule_version_id,
        audit_event_id=audit_event_id,
        validation_fingerprint=cast(
            str,
            cast(Mapping[str, object], lineage["validation_report"])["fingerprint"],
        ),
        kpi_fingerprint=cast(
            str, cast(Mapping[str, object], lineage["kpi"])["fingerprint"]
        ),
    )


__all__ = [
    "ReviewableScheduleDocuments",
    "SCHEDULE_VERSION_LIFECYCLE_VERSION",
    "ScheduleVersionCreationContext",
    "ScheduleVersionLifecycleError",
    "ScheduleVersionLifecycleFailure",
    "ValidatedPlanningOutput",
    "build_reviewable_schedule_documents",
    "reject_lifecycle",
]
