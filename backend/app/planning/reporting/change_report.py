"""Deterministic builder for complete immutable P4 ChangeReport evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import cast

from app.domain.change_report import (
    ChangeReportFailure,
    ImmutableChangeReport,
    reject_change_report,
)
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    change_report_fingerprint,
    contract_fingerprint,
    require_p4_document,
)
from app.planning.reporting.stability import (
    OperationDelta,
    calculate_operation_delta,
    calculate_stability,
    index_assignments,
)


CHANGE_REPORT_BUILDER_VERSION = "change-report-builder.v1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_SEMANTIC_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_KPI_ID = re.compile(r"^kpi-[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^replan-request-[0-9a-f]{64}$")
_CONTEXT_FIELDS = frozenset(
    {
        "environment",
        "synthetic_provenance",
        "base_schedule_version",
        "new_schedule_version",
        "lineage",
        "freeze_evidence",
        "generated_at_utc",
        "correlation_id",
    }
)
_LINEAGE_FIELDS = frozenset(
    {
        "base_snapshot",
        "base_problem",
        "new_snapshot",
        "new_problem",
        "event_stream_fingerprint",
        "fact_checkpoint",
        "replan_request",
        "planning_run_id",
        "policy",
        "limits",
        "solver_report",
        "validation_report",
    }
)
_SYNTHETIC_PROVENANCE_FIELDS = frozenset(
    {
        "scenario_id",
        "scenario_version",
        "factory_profile_id",
        "profile_version",
        "generator_id",
        "generator_version",
        "simulator_id",
        "simulator_version",
        "seed",
    }
)
_FREEZE_FIELDS = frozenset(
    {
        "freeze_policy_version",
        "freeze_policy_id",
        "freeze_policy_revision",
        "freeze_policy_fingerprint",
        "source",
        "window_seconds",
        "effective_from_utc",
        "effective_until_utc",
        "interval_semantics",
        "effective_lock_ids",
    }
)
_REASON_CODES = frozenset(
    {
        "NO_CHANGE",
        "TRIGGER_EVENT",
        "EXECUTION_FACT",
        "URGENT_DEMAND",
        "FREEZE_OR_HARD_LOCK_PRESERVED",
        "SOFT_LOCK_STABILITY_TRADE_OFF",
        "DELIVERY_OBJECTIVE_TRADE_OFF",
        "REMOVED_BY_COMPLETION_FACT",
        "UNATTRIBUTED_SOLVER_CHANGE",
    }
)
_CLASSIFICATION_REASONS = {
    "UNCHANGED": frozenset({"NO_CHANGE", "FREEZE_OR_HARD_LOCK_PRESERVED"}),
    "CHANGED": frozenset(
        {
            "TRIGGER_EVENT",
            "EXECUTION_FACT",
            "FREEZE_OR_HARD_LOCK_PRESERVED",
            "SOFT_LOCK_STABILITY_TRADE_OFF",
            "DELIVERY_OBJECTIVE_TRADE_OFF",
            "UNATTRIBUTED_SOLVER_CHANGE",
        }
    ),
    "ADDED": frozenset({"TRIGGER_EVENT", "URGENT_DEMAND"}),
    "REMOVED_BY_FACT": frozenset({"REMOVED_BY_COMPLETION_FACT"}),
}


def _mapping(
    value: object,
    field: str,
    *,
    reason: ChangeReportFailure = ChangeReportFailure.INVALID_INPUT,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_change_report(
            reason,
            field=field,
            entity_id="<input>",
            message="value must be an object",
        )
    return cast(Mapping[str, object], value)


def _identifier(value: object, field: str, entity_id: str = "<input>") -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        reject_change_report(
            ChangeReportFailure.INVALID_INPUT,
            field=field,
            entity_id=entity_id,
            message="value must be a canonical identifier",
        )
    return value


def _fingerprint(value: object, field: str, entity_id: str = "<input>") -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=entity_id,
            message="value must be a lowercase sha256 fingerprint",
        )
    return value


def _utc_second(value: object, field: str, entity_id: str = "<input>") -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        reject_change_report(
            ChangeReportFailure.INVALID_INPUT,
            field=field,
            entity_id=entity_id,
            message="instant must be RFC3339 UTC Z",
        )
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        reject_change_report(
            ChangeReportFailure.INVALID_INPUT,
            field=field,
            entity_id=entity_id,
            message=f"instant is invalid: {type(error).__name__}",
        )
    if instant.microsecond:
        reject_change_report(
            ChangeReportFailure.INVALID_INPUT,
            field=field,
            entity_id=entity_id,
            message="instant must have whole-second precision",
        )
    return instant


def _non_negative_integer(
    value: object,
    field: str,
    entity_id: str,
    *,
    reason: ChangeReportFailure = ChangeReportFailure.KPI_EVIDENCE_MISMATCH,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        reject_change_report(
            reason,
            field=field,
            entity_id=entity_id,
            message="value must be a non-negative integer",
        )
    return value


def _positive_integer(value: object, field: str, entity_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=entity_id,
            message="value must be a positive integer",
        )
    return value


def _non_empty_text(value: object, field: str, entity_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=entity_id,
            message="value must contain non-whitespace text",
        )
    return value


def _json_copy(value: object, field: str) -> object:
    try:
        return json.loads(canonical_contract_bytes(value))
    except ValueError as error:
        reject_change_report(
            ChangeReportFailure.INVALID_INPUT,
            field=field,
            entity_id="<input>",
            message=f"value is not canonical JSON: {type(error).__name__}",
        )


def _artifact_reference(value: object, field: str) -> dict[str, str]:
    reference = _mapping(
        value, field, reason=ChangeReportFailure.LINEAGE_MISMATCH
    )
    if set(reference) != {"document_version", "artifact_id", "fingerprint"}:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=str(reference.get("artifact_id", "<artifact>")),
            message="artifact reference fields are incomplete",
        )
    return {
        "document_version": _identifier(
            reference.get("document_version"), f"{field}.document_version"
        ),
        "artifact_id": _identifier(
            reference.get("artifact_id"), f"{field}.artifact_id"
        ),
        "fingerprint": _fingerprint(
            reference.get("fingerprint"), f"{field}.fingerprint"
        ),
    }


def _synthetic_provenance(value: object) -> dict[str, object]:
    provenance = _mapping(
        value,
        "context.synthetic_provenance",
        reason=ChangeReportFailure.LINEAGE_MISMATCH,
    )
    if set(provenance) != _SYNTHETIC_PROVENANCE_FIELDS:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="context.synthetic_provenance",
            entity_id="<provenance>",
            message="synthetic provenance fields are incomplete",
        )
    result: dict[str, object] = {}
    for field in (
        "scenario_id",
        "factory_profile_id",
        "generator_id",
        "simulator_id",
    ):
        result[field] = _identifier(
            provenance.get(field), f"context.synthetic_provenance.{field}"
        )
    for field in (
        "scenario_version",
        "profile_version",
        "generator_version",
        "simulator_version",
    ):
        version = provenance.get(field)
        if not isinstance(version, str) or _SEMANTIC_VERSION.fullmatch(version) is None:
            reject_change_report(
                ChangeReportFailure.LINEAGE_MISMATCH,
                field=f"context.synthetic_provenance.{field}",
                entity_id="<provenance>",
                message="version must be semantic major.minor.patch",
            )
        result[field] = version
    result["seed"] = _non_negative_integer(
        provenance.get("seed"),
        "context.synthetic_provenance.seed",
        "<provenance>",
        reason=ChangeReportFailure.LINEAGE_MISMATCH,
    )
    return result


def _request_reference(value: object, field: str) -> dict[str, str]:
    reference = _mapping(value, field, reason=ChangeReportFailure.LINEAGE_MISMATCH)
    required = {"replan_request_version", "request_id", "request_fingerprint"}
    if set(reference) != required:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id="<request>",
            message="ReplanRequest reference fields are incomplete",
        )
    fingerprint = _fingerprint(
        reference.get("request_fingerprint"), f"{field}.request_fingerprint"
    )
    request_id = reference.get("request_id")
    expected_id = "replan-request-" + fingerprint.removeprefix("sha256:")
    if (
        reference.get("replan_request_version") != "replan-request.v1"
        or not isinstance(request_id, str)
        or _REQUEST_ID.fullmatch(request_id) is None
        or request_id != expected_id
    ):
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=str(request_id),
            message="ReplanRequest version or content identity is inconsistent",
        )
    return {
        "replan_request_version": "replan-request.v1",
        "request_id": request_id,
        "request_fingerprint": fingerprint,
    }


def _policy_reference(value: object, field: str) -> dict[str, str]:
    reference = _mapping(value, field, reason=ChangeReportFailure.LINEAGE_MISMATCH)
    required = {
        "planning_policy_version",
        "policy_id",
        "policy_revision",
        "policy_fingerprint",
    }
    if set(reference) != required or reference.get(
        "planning_policy_version"
    ) != "planning-policy.v2":
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=str(reference.get("policy_id", "<policy>")),
            message="PlanningPolicy reference fields/version are inconsistent",
        )
    return {
        "planning_policy_version": "planning-policy.v2",
        "policy_id": _identifier(reference.get("policy_id"), f"{field}.policy_id"),
        "policy_revision": _non_empty_text(
            reference.get("policy_revision"),
            f"{field}.policy_revision",
            str(reference.get("policy_id", "<policy>")),
        ),
        "policy_fingerprint": _fingerprint(
            reference.get("policy_fingerprint"), f"{field}.policy_fingerprint"
        ),
    }


def _limits_reference(value: object, field: str) -> dict[str, object]:
    reference = _mapping(value, field, reason=ChangeReportFailure.LINEAGE_MISMATCH)
    required = {
        "solve_limits_version",
        "limits_id",
        "limits_revision",
        "limits_fingerprint",
        "max_wall_time_seconds",
        "max_workers",
        "random_seed",
    }
    limits_id = str(reference.get("limits_id", "<limits>"))
    wall_time = reference.get("max_wall_time_seconds")
    if (
        set(reference) != required
        or reference.get("solve_limits_version") != "solve-limits.v1"
        or isinstance(wall_time, bool)
        or not isinstance(wall_time, (int, float))
        or wall_time <= 0
    ):
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=limits_id,
            message="SolveLimits reference fields/version/limits are inconsistent",
        )
    return {
        "solve_limits_version": "solve-limits.v1",
        "limits_id": _identifier(reference.get("limits_id"), f"{field}.limits_id"),
        "limits_revision": _non_empty_text(
            reference.get("limits_revision"), f"{field}.limits_revision", limits_id
        ),
        "limits_fingerprint": _fingerprint(
            reference.get("limits_fingerprint"), f"{field}.limits_fingerprint"
        ),
        "max_wall_time_seconds": wall_time,
        "max_workers": _positive_integer(
            reference.get("max_workers"), f"{field}.max_workers", limits_id
        ),
        "random_seed": _non_negative_integer(
            reference.get("random_seed"),
            f"{field}.random_seed",
            limits_id,
            reason=ChangeReportFailure.LINEAGE_MISMATCH,
        ),
    }


def _schedule_reference(
    value: object,
    field: str,
    *,
    expected_state: str,
) -> dict[str, object]:
    reference = _mapping(
        value, field, reason=ChangeReportFailure.LINEAGE_MISMATCH
    )
    required = {
        "schedule_version_version",
        "schedule_version_id",
        "state",
        "content_fingerprint",
    }
    if set(reference) != required:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=str(reference.get("schedule_version_id", "<schedule>")),
            message="ScheduleVersion reference fields are incomplete",
        )
    version = reference.get("schedule_version_version")
    allowed_versions = (
        {"schedule-version.v1", "schedule-version.v2"}
        if expected_state == "PUBLISHED"
        else {"schedule-version.v2"}
    )
    if version not in allowed_versions or reference.get("state") != expected_state:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field=field,
            entity_id=str(reference.get("schedule_version_id", "<schedule>")),
            message="ScheduleVersion version/state is outside the P4 carrier",
        )
    return {
        "schedule_version_version": cast(str, version),
        "schedule_version_id": _identifier(
            reference.get("schedule_version_id"), f"{field}.schedule_version_id"
        ),
        "state": expected_state,
        "content_fingerprint": _fingerprint(
            reference.get("content_fingerprint"), f"{field}.content_fingerprint"
        ),
    }


def _lineage(value: object) -> dict[str, object]:
    lineage = _mapping(
        value, "context.lineage", reason=ChangeReportFailure.LINEAGE_MISMATCH
    )
    if set(lineage) != _LINEAGE_FIELDS:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="context.lineage",
            entity_id="<lineage>",
            message="lineage must contain the complete ChangeReport carrier set",
        )
    result: dict[str, object] = {}
    for field in (
        "base_snapshot",
        "base_problem",
        "new_snapshot",
        "new_problem",
        "fact_checkpoint",
        "solver_report",
        "validation_report",
    ):
        result[field] = _artifact_reference(lineage[field], f"context.lineage.{field}")
    result["event_stream_fingerprint"] = _fingerprint(
        lineage.get("event_stream_fingerprint"),
        "context.lineage.event_stream_fingerprint",
    )
    result["planning_run_id"] = _identifier(
        lineage.get("planning_run_id"), "context.lineage.planning_run_id"
    )
    result["replan_request"] = _request_reference(
        lineage["replan_request"], "context.lineage.replan_request"
    )
    result["policy"] = _policy_reference(
        lineage["policy"], "context.lineage.policy"
    )
    result["limits"] = _limits_reference(
        lineage["limits"], "context.lineage.limits"
    )
    return result


def _freeze_evidence(value: object) -> dict[str, object]:
    evidence = _mapping(
        value,
        "context.freeze_evidence",
        reason=ChangeReportFailure.LINEAGE_MISMATCH,
    )
    copied = cast(dict[str, object], _json_copy(evidence, "context.freeze_evidence"))
    if set(copied) != _FREEZE_FIELDS:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="context.freeze_evidence",
            entity_id=str(copied.get("freeze_policy_id", "<freeze>")),
            message="freeze evidence fields are incomplete",
        )
    start = _utc_second(
        copied.get("effective_from_utc"), "freeze_evidence.effective_from_utc"
    )
    end = _utc_second(
        copied.get("effective_until_utc"), "freeze_evidence.effective_until_utc"
    )
    window = copied.get("window_seconds")
    if (
        copied.get("freeze_policy_version") != "freeze-policy.v1"
        or copied.get("interval_semantics")
        != "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE"
        or isinstance(window, bool)
        or not isinstance(window, int)
        or window < 1
        or int((end - start).total_seconds()) != window
    ):
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="context.freeze_evidence",
            entity_id=str(copied.get("freeze_policy_id", "<freeze>")),
            message="freeze resolution is inconsistent",
        )
    _fingerprint(
        copied.get("freeze_policy_fingerprint"),
        "freeze_evidence.freeze_policy_fingerprint",
    )
    _identifier(copied.get("freeze_policy_id"), "freeze_evidence.freeze_policy_id")
    _non_empty_text(
        copied.get("freeze_policy_revision"),
        "freeze_evidence.freeze_policy_revision",
        str(copied.get("freeze_policy_id", "<freeze>")),
    )
    source = _mapping(
        copied.get("source"),
        "freeze_evidence.source",
        reason=ChangeReportFailure.LINEAGE_MISMATCH,
    )
    if set(source) != {"source_system", "source_version", "source_record_id"}:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="freeze_evidence.source",
            entity_id=str(copied.get("freeze_policy_id", "<freeze>")),
            message="freeze source fields are incomplete",
        )
    for field in ("source_system", "source_version", "source_record_id"):
        _non_empty_text(
            source.get(field),
            f"freeze_evidence.source.{field}",
            str(copied.get("freeze_policy_id", "<freeze>")),
        )
    lock_ids = copied.get("effective_lock_ids")
    if not isinstance(lock_ids, list):
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="freeze_evidence.effective_lock_ids",
            entity_id=str(copied.get("freeze_policy_id", "<freeze>")),
            message="effective lock IDs must be a unique array",
        )
    normalized_lock_ids = sorted(
        _identifier(item, "freeze_evidence.effective_lock_ids[]")
        for item in cast(list[object], lock_ids)
    )
    if len(normalized_lock_ids) != len(set(normalized_lock_ids)):
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="freeze_evidence.effective_lock_ids",
            entity_id=str(copied.get("freeze_policy_id", "<freeze>")),
            message="effective lock IDs must be a unique array",
        )
    copied["effective_lock_ids"] = normalized_lock_ids
    return copied


def _normalize_context(value: Mapping[str, object]) -> dict[str, object]:
    if set(value) != _CONTEXT_FIELDS:
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="context",
            entity_id="<context>",
            message="context fields differ from the frozen builder contract",
        )
    environment = value.get("environment")
    if environment not in {"DEVELOPMENT", "TEST", "BENCHMARK"}:
        reject_change_report(
            ChangeReportFailure.PLANE_MISMATCH,
            field="context.environment",
            entity_id=str(environment),
            message="P4-06 accepts isolated non-Production environments only",
        )
    generated = value.get("generated_at_utc")
    _utc_second(generated, "context.generated_at_utc")
    return {
        "environment": cast(str, environment),
        "synthetic_provenance": _synthetic_provenance(
            value.get("synthetic_provenance")
        ),
        "base_schedule_version": _schedule_reference(
            value.get("base_schedule_version"),
            "context.base_schedule_version",
            expected_state="PUBLISHED",
        ),
        "new_schedule_version": _schedule_reference(
            value.get("new_schedule_version"),
            "context.new_schedule_version",
            expected_state="DRAFT",
        ),
        "lineage": _lineage(value.get("lineage")),
        "freeze_evidence": _freeze_evidence(value.get("freeze_evidence")),
        "generated_at_utc": cast(str, generated),
        "correlation_id": _identifier(
            value.get("correlation_id"), "context.correlation_id"
        ),
    }


def kpi_evidence_reference(
    value: Mapping[str, object],
    *,
    field: str,
) -> tuple[dict[str, str], int, int]:
    """Validate one immutable KPI document and return its exact report reference."""

    kpi_id = _identifier(value.get("kpi_id"), f"{field}.kpi_id")
    kpi_basis = {key: item for key, item in value.items() if key != "kpi_id"}
    expected_kpi_id = "kpi-" + sha256(canonical_contract_bytes(kpi_basis)).hexdigest()
    if (
        _KPI_ID.fullmatch(kpi_id) is None
        or kpi_id != expected_kpi_id
        or value.get("kpi_version") != "kpi.v2"
        or value.get("schema_set_version") != "2.5.0"
        or value.get("canonicalization_version") != "canonical-json.v1"
        or value.get("synthetic") is not True
    ):
        reject_change_report(
            ChangeReportFailure.KPI_EVIDENCE_MISMATCH,
            field=field,
            entity_id=kpi_id,
            message="only immutable synthetic kpi.v2 evidence is supported",
        )
    delivery = _mapping(
        value.get("delivery"),
        f"{field}.delivery",
        reason=ChangeReportFailure.KPI_EVIDENCE_MISMATCH,
    )
    planning = _mapping(
        value.get("planning"),
        f"{field}.planning",
        reason=ChangeReportFailure.KPI_EVIDENCE_MISMATCH,
    )
    tardiness = _non_negative_integer(
        delivery.get("priority_weighted_tardiness_seconds"),
        f"{field}.delivery.priority_weighted_tardiness_seconds",
        kpi_id,
    )
    makespan = _non_negative_integer(
        planning.get("makespan_seconds"),
        f"{field}.planning.makespan_seconds",
        kpi_id,
    )
    return (
        {
            "document_version": "kpi.v2",
            "artifact_id": kpi_id,
            "fingerprint": contract_fingerprint(value),
        },
        tardiness,
        makespan,
    )


def _reason_evidence(value: object, field: str) -> dict[str, object]:
    reason = _mapping(
        value, field, reason=ChangeReportFailure.INVALID_REASON_EVIDENCE
    )
    if set(reason) != {"reason_code", "evidence_refs"}:
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field=field,
            entity_id="<reason>",
            message="reason fields are incomplete",
        )
    code = reason.get("reason_code")
    if code not in _REASON_CODES:
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field=f"{field}.reason_code",
            entity_id=str(code),
            message="reason code is not in change-report.v1",
        )
    refs = reason.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field=f"{field}.evidence_refs",
            entity_id=cast(str, code),
            message="at least one immutable evidence reference is required",
        )
    normalized = [
        _artifact_reference(item, f"{field}.evidence_refs[{index}]")
        for index, item in enumerate(cast(list[object], refs))
    ]
    keys = [
        (item["document_version"], item["artifact_id"], item["fingerprint"])
        for item in normalized
    ]
    if len(keys) != len(set(keys)):
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field=f"{field}.evidence_refs",
            entity_id=cast(str, code),
            message="evidence references must be unique",
        )
    normalized.sort(
        key=lambda item: (
            item["document_version"],
            item["artifact_id"],
            item["fingerprint"],
        )
    )
    return {"reason_code": cast(str, code), "evidence_refs": normalized}


def _operation_reasons(
    *,
    operation_id: str,
    classification: str,
    provided: object,
    solver_report: Mapping[str, object],
    removed_fact: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if provided is None and classification == "CHANGED":
        values: list[object] = [
            {
                "reason_code": "UNATTRIBUTED_SOLVER_CHANGE",
                "evidence_refs": [dict(solver_report)],
            }
        ]
    elif isinstance(provided, Sequence) and not isinstance(
        provided, (str, bytes, bytearray)
    ):
        values = list(cast(Sequence[object], provided))
    else:
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field="reasons_by_operation",
            entity_id=operation_id,
            message="each operation requires a reason array",
        )
    if not values:
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field="reasons_by_operation",
            entity_id=operation_id,
            message="each operation requires evidence-backed reasons",
        )
    reasons = [
        _reason_evidence(value, f"reasons_by_operation.{operation_id}[{index}]")
        for index, value in enumerate(values)
    ]
    codes = {cast(str, item["reason_code"]) for item in reasons}
    if not codes.issubset(_CLASSIFICATION_REASONS[classification]):
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field="reasons_by_operation",
            entity_id=operation_id,
            message=f"reason is incompatible with {classification}",
        )
    if classification == "REMOVED_BY_FACT":
        if removed_fact is None or codes != {"REMOVED_BY_COMPLETION_FACT"}:
            reject_change_report(
                ChangeReportFailure.MISSING_FACT_EVIDENCE,
                field="reasons_by_operation",
                entity_id=operation_id,
                message="REMOVED_BY_FACT requires completion-fact evidence",
            )
        expected = dict(removed_fact)
        if not any(
            expected in cast(list[dict[str, object]], item["evidence_refs"])
            for item in reasons
        ):
            reject_change_report(
                ChangeReportFailure.MISSING_FACT_EVIDENCE,
                field="reasons_by_operation",
                entity_id=operation_id,
                message="removed operation does not reference its authoritative fact",
            )
    identities = [canonical_contract_bytes(item) for item in reasons]
    if len(identities) != len(set(identities)):
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field="reasons_by_operation",
            entity_id=operation_id,
            message="duplicate reasons are not allowed",
        )
    reasons.sort(key=lambda item: canonical_contract_bytes(item))
    return reasons


def _zero_delta() -> OperationDelta:
    return OperationDelta(
        resource_changed=False,
        start_shift_seconds=0,
        absolute_start_shift_seconds=0,
        end_shift_seconds=0,
        duration_delta_seconds=0,
    )


def build_change_report(
    *,
    context: Mapping[str, object],
    base_assignments: Sequence[object],
    new_assignments: Sequence[object],
    active_operation_ids: Sequence[str],
    active_soft_locks: Sequence[object],
    removed_by_fact: Mapping[str, object],
    reasons_by_operation: Mapping[str, object],
    before_kpi: Mapping[str, object],
    after_kpi: Mapping[str, object],
) -> ImmutableChangeReport:
    """Build a complete content-addressed ChangeReport without side effects."""

    normalized_context = _normalize_context(context)
    base = index_assignments(base_assignments, field="base_assignments")
    new = index_assignments(new_assignments, field="new_assignments")
    stability = calculate_stability(
        base_assignments=list(base.values()),
        new_assignments=list(new.values()),
        active_operation_ids=active_operation_ids,
        active_soft_locks=active_soft_locks,
    )
    freeze = cast(Mapping[str, object], normalized_context["freeze_evidence"])
    effective_lock_ids = set(cast(list[str], freeze["effective_lock_ids"]))
    soft_lock_ids = {
        _identifier(
            _mapping(value, f"active_soft_locks[{index}]").get("reference_id"),
            f"active_soft_locks[{index}].reference_id",
        )
        for index, value in enumerate(active_soft_locks)
    }
    if not soft_lock_ids.issubset(effective_lock_ids):
        reject_change_report(
            ChangeReportFailure.LINEAGE_MISMATCH,
            field="active_soft_locks",
            entity_id=sorted(soft_lock_ids - effective_lock_ids)[0],
            message="active SOFT lock is absent from freeze evidence",
        )
    removed_ids = sorted(set(base) - set(new))
    added_ids = sorted(set(new) - set(base))
    normalized_removed: dict[str, dict[str, str]] = {}
    for operation_id, evidence in removed_by_fact.items():
        canonical_id = _identifier(operation_id, "removed_by_fact.operation_id")
        normalized_removed[canonical_id] = _artifact_reference(
            evidence, f"removed_by_fact.{canonical_id}"
        )
    if set(normalized_removed) != set(removed_ids):
        reject_change_report(
            ChangeReportFailure.MISSING_FACT_EVIDENCE,
            field="removed_by_fact",
            entity_id="<operation-universe>",
            message="base-only operations must have exactly one authoritative fact",
        )
    universe = sorted(set(base).union(new))
    extra_reason_ids = set(reasons_by_operation) - set(universe)
    if extra_reason_ids:
        reject_change_report(
            ChangeReportFailure.INVALID_REASON_EVIDENCE,
            field="reasons_by_operation",
            entity_id=sorted(extra_reason_ids)[0],
            message="reason references an operation outside the universe",
        )
    lineage = cast(dict[str, object], normalized_context["lineage"])
    solver_reference = cast(Mapping[str, object], lineage["solver_report"])
    operations: list[dict[str, object]] = []
    for operation_id in universe:
        base_assignment = base.get(operation_id)
        new_assignment = new.get(operation_id)
        if operation_id in added_ids:
            classification = "ADDED"
            delta = _zero_delta()
        elif operation_id in removed_ids:
            classification = "REMOVED_BY_FACT"
            delta = _zero_delta()
        else:
            if base_assignment is None or new_assignment is None:
                reject_change_report(
                    ChangeReportFailure.ACTIVE_UNIVERSE_MISMATCH,
                    field="operations",
                    entity_id=operation_id,
                    message="comparable operation lacks an assignment",
                )
            delta = calculate_operation_delta(base_assignment, new_assignment)
            classification = "CHANGED" if delta.changed else "UNCHANGED"
        operations.append(
            {
                "operation_id": operation_id,
                "classification": classification,
                "base_assignment": base_assignment,
                "new_assignment": new_assignment,
                "deltas": delta.document,
                "reasons": _operation_reasons(
                    operation_id=operation_id,
                    classification=classification,
                    provided=reasons_by_operation.get(operation_id),
                    solver_report=solver_reference,
                    removed_fact=normalized_removed.get(operation_id),
                ),
            }
        )
    before_reference, _, _ = kpi_evidence_reference(before_kpi, field="before_kpi")
    after_reference, _, _ = kpi_evidence_reference(after_kpi, field="after_kpi")
    document: dict[str, object] = {
        "change_report_version": "change-report.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "report_id": "pending",
        "report_fingerprint": "pending",
        "data_plane": "SIMULATION",
        "environment": normalized_context["environment"],
        "synthetic": True,
        "synthetic_provenance": normalized_context["synthetic_provenance"],
        "production_binding": False,
        "base_schedule_version": normalized_context["base_schedule_version"],
        "new_schedule_version": normalized_context["new_schedule_version"],
        "lineage": lineage,
        "freeze_evidence": normalized_context["freeze_evidence"],
        "before_kpi": before_reference,
        "after_kpi": after_reference,
        "operation_universe_count": len(operations),
        "operations": operations,
        "stability": stability.document,
        "generated_at_utc": normalized_context["generated_at_utc"],
        "correlation_id": normalized_context["correlation_id"],
    }
    fingerprint = change_report_fingerprint(document)
    report_id = f"change-report-{fingerprint.removeprefix('sha256:')}"
    document["report_fingerprint"] = fingerprint
    document["report_id"] = report_id
    try:
        require_p4_document(document)
    except ValueError as error:
        reject_change_report(
            ChangeReportFailure.CONTRACT_REJECTED,
            field=getattr(error, "field", "change_report"),
            entity_id=report_id,
            message="built report failed the frozen P4 carrier precheck",
        )
    return ImmutableChangeReport(
        canonical_bytes=canonical_contract_bytes(document),
        report_id=report_id,
        report_fingerprint=fingerprint,
    )


__all__ = [
    "CHANGE_REPORT_BUILDER_VERSION",
    "build_change_report",
    "kpi_evidence_reference",
]
