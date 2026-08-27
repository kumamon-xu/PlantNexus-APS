"""Independent completeness precheck for P4 OBJ-002 and ChangeReport.

The evaluator deliberately duplicates the small accepted integer projection. It
does not import the ChangeReport builder, stability calculator, Solver backend,
formal ScheduleValidator, persistence, API, or Simulator code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import cast

from app.domain.execution_contracts import (
    canonical_contract_bytes,
    change_report_fingerprint,
    contract_fingerprint,
    require_p4_document,
)


PRECHECK_VERSION = "change-report-precheck.v1"
_ASSIGNMENT_FIELDS = {
    "operation_id",
    "resource_id",
    "start_tick",
    "end_tick",
    "duration_ticks",
    "start_at_utc",
    "end_at_utc",
    "duration_seconds",
    "lock_ids",
    "execution_fact_ids",
}
_REASON_FIELDS = {"reason_code", "evidence_refs"}
_REFERENCE_FIELDS = {"document_version", "artifact_id", "fingerprint"}
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_KPI_ID = re.compile(r"^kpi-[0-9a-f]{64}$")
_CLASSIFICATION_REASONS = {
    "UNCHANGED": {"NO_CHANGE", "FREEZE_OR_HARD_LOCK_PRESERVED"},
    "CHANGED": {
        "TRIGGER_EVENT",
        "EXECUTION_FACT",
        "FREEZE_OR_HARD_LOCK_PRESERVED",
        "SOFT_LOCK_STABILITY_TRADE_OFF",
        "DELIVERY_OBJECTIVE_TRADE_OFF",
        "UNATTRIBUTED_SOLVER_CHANGE",
    },
    "ADDED": {"TRIGGER_EVENT", "URGENT_DEMAND"},
    "REMOVED_BY_FACT": {"REMOVED_BY_COMPLETION_FACT"},
}


class ChangeReportPrecheckInputError(ValueError):
    """Authoritative precheck inputs are malformed or internally inconsistent."""

    def __init__(self, reason: str, *, field: str, entity_id: str) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        super().__init__(f"{reason} at {field} ({entity_id})")


def _input_error(
    reason: str, field: str, entity_id: str
) -> ChangeReportPrecheckInputError:
    return ChangeReportPrecheckInputError(
        reason,
        field=field,
        entity_id=entity_id,
    )


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _input_error("INVALID_SHAPE", field, "<input>")
    return cast(Mapping[str, object], value)


def _list(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise _input_error("INVALID_SHAPE", field, "<input>")
    return value


def _identifier(value: object, field: str, entity_id: str = "<input>") -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        raise _input_error("INVALID_IDENTIFIER", field, entity_id)
    return value


def _integer(
    value: object,
    field: str,
    entity_id: str,
    *,
    minimum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _input_error("INVALID_INTEGER", field, entity_id)
    return value


def _utc(value: object, field: str, entity_id: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise _input_error("INVALID_UTC", field, entity_id)
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _input_error("INVALID_UTC", field, entity_id) from error
    if instant.microsecond:
        raise _input_error("INVALID_UTC_PRECISION", field, entity_id)
    return instant


def _json_copy(value: object, field: str) -> object:
    try:
        return json.loads(canonical_contract_bytes(value))
    except (TypeError, ValueError) as error:
        raise _input_error("NON_CANONICAL_JSON", field, "<input>") from error


def _identifier_list(value: object, field: str, entity_id: str) -> list[str]:
    values = [
        _identifier(item, f"{field}[]", entity_id) for item in _list(value, field)
    ]
    if len(values) != len(set(values)):
        raise _input_error("DUPLICATE_IDENTIFIER", field, entity_id)
    return sorted(values)


def _assignment(value: object, field: str) -> dict[str, object]:
    assignment = _mapping(value, field)
    operation_id = _identifier(
        assignment.get("operation_id"), f"{field}.operation_id"
    )
    if set(assignment) != _ASSIGNMENT_FIELDS:
        raise _input_error("INVALID_ASSIGNMENT_FIELDS", field, operation_id)
    start = _utc(
        assignment.get("start_at_utc"), f"{field}.start_at_utc", operation_id
    )
    end = _utc(
        assignment.get("end_at_utc"), f"{field}.end_at_utc", operation_id
    )
    start_tick = _integer(
        assignment.get("start_tick"), f"{field}.start_tick", operation_id, minimum=0
    )
    end_tick = _integer(
        assignment.get("end_tick"), f"{field}.end_tick", operation_id, minimum=1
    )
    duration_ticks = _integer(
        assignment.get("duration_ticks"),
        f"{field}.duration_ticks",
        operation_id,
        minimum=1,
    )
    duration_seconds = _integer(
        assignment.get("duration_seconds"),
        f"{field}.duration_seconds",
        operation_id,
        minimum=1,
    )
    if (
        end <= start
        or int((end - start).total_seconds()) != duration_seconds
        or end_tick - start_tick != duration_ticks
    ):
        raise _input_error("INCONSISTENT_ASSIGNMENT", field, operation_id)
    return {
        "operation_id": operation_id,
        "resource_id": _identifier(
            assignment.get("resource_id"), f"{field}.resource_id", operation_id
        ),
        "start_tick": start_tick,
        "end_tick": end_tick,
        "duration_ticks": duration_ticks,
        "start_at_utc": cast(str, assignment["start_at_utc"]),
        "end_at_utc": cast(str, assignment["end_at_utc"]),
        "duration_seconds": duration_seconds,
        "lock_ids": _identifier_list(
            assignment.get("lock_ids"), f"{field}.lock_ids", operation_id
        ),
        "execution_fact_ids": _identifier_list(
            assignment.get("execution_fact_ids"),
            f"{field}.execution_fact_ids",
            operation_id,
        ),
    }


def _assignments(values: Sequence[object], field: str) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for index, value in enumerate(values):
        assignment = _assignment(value, f"{field}[{index}]")
        operation_id = cast(str, assignment["operation_id"])
        if operation_id in indexed:
            raise _input_error("DUPLICATE_OPERATION", field, operation_id)
        indexed[operation_id] = assignment
    return dict(sorted(indexed.items()))


def _delta(
    base: Mapping[str, object], new: Mapping[str, object]
) -> dict[str, object]:
    operation_id = cast(str, base["operation_id"])
    base_start = _utc(base["start_at_utc"], "base.start_at_utc", operation_id)
    new_start = _utc(new["start_at_utc"], "new.start_at_utc", operation_id)
    base_end = _utc(base["end_at_utc"], "base.end_at_utc", operation_id)
    new_end = _utc(new["end_at_utc"], "new.end_at_utc", operation_id)
    start_shift = int((new_start - base_start).total_seconds())
    return {
        "resource_changed": base["resource_id"] != new["resource_id"],
        "start_shift_seconds": start_shift,
        "absolute_start_shift_seconds": abs(start_shift),
        "end_shift_seconds": int((new_end - base_end).total_seconds()),
        "duration_delta_seconds": cast(int, new["duration_seconds"])
        - cast(int, base["duration_seconds"]),
    }


def _changed(delta: Mapping[str, object]) -> bool:
    return bool(
        delta["resource_changed"]
        or delta["start_shift_seconds"] != 0
        or delta["end_shift_seconds"] != 0
    )


def _reference(value: object, field: str) -> dict[str, str]:
    reference = _mapping(value, field)
    if set(reference) != _REFERENCE_FIELDS:
        raise _input_error("INVALID_REFERENCE", field, "<reference>")
    fingerprint = reference.get("fingerprint")
    if not isinstance(fingerprint, str) or _SHA256.fullmatch(fingerprint) is None:
        raise _input_error("INVALID_FINGERPRINT", f"{field}.fingerprint", "<reference>")
    return {
        "document_version": _identifier(
            reference.get("document_version"), f"{field}.document_version"
        ),
        "artifact_id": _identifier(reference.get("artifact_id"), f"{field}.artifact_id"),
        "fingerprint": fingerprint,
    }


def _kpi_reference(
    value: Mapping[str, object], field: str
) -> tuple[dict[str, str], int, int]:
    kpi_id = _identifier(value.get("kpi_id"), f"{field}.kpi_id")
    basis = {key: item for key, item in value.items() if key != "kpi_id"}
    expected_kpi_id = "kpi-" + sha256(canonical_contract_bytes(basis)).hexdigest()
    if (
        _KPI_ID.fullmatch(kpi_id) is None
        or kpi_id != expected_kpi_id
        or value.get("kpi_version") != "kpi.v2"
        or value.get("schema_set_version") != "2.5.0"
        or value.get("canonicalization_version") != "canonical-json.v1"
        or value.get("synthetic") is not True
    ):
        raise _input_error("INVALID_KPI", field, kpi_id)
    delivery = _mapping(value.get("delivery"), f"{field}.delivery")
    planning = _mapping(value.get("planning"), f"{field}.planning")
    tardiness = _integer(
        delivery.get("priority_weighted_tardiness_seconds"),
        f"{field}.delivery.priority_weighted_tardiness_seconds",
        kpi_id,
        minimum=0,
    )
    makespan = _integer(
        planning.get("makespan_seconds"),
        f"{field}.planning.makespan_seconds",
        kpi_id,
        minimum=0,
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


def _soft_lock_violations(
    values: Sequence[object], new: Mapping[str, Mapping[str, object]]
) -> tuple[int, set[str]]:
    seen: set[str] = set()
    violations = 0
    for index, value in enumerate(values):
        lock = _mapping(value, f"active_soft_locks[{index}]")
        lock_id = _identifier(
            lock.get("reference_id"), f"active_soft_locks[{index}].reference_id"
        )
        if lock_id in seen:
            raise _input_error("DUPLICATE_SOFT_LOCK", "active_soft_locks", lock_id)
        seen.add(lock_id)
        operation_id = _identifier(
            lock.get("operation_id"),
            f"active_soft_locks[{index}].operation_id",
            lock_id,
        )
        if lock.get("protection_kind") != "SOFT_LOCK" or lock.get(
            "protection_priority"
        ) != 4:
            raise _input_error("INVALID_SOFT_LOCK", "active_soft_locks", lock_id)
        assignment = new.get(operation_id)
        if assignment is None:
            raise _input_error(
                "SOFT_LOCK_OUTSIDE_ACTIVE_UNIVERSE", "active_soft_locks", operation_id
            )
        start_at_utc = lock.get("start_at_utc")
        end_at_utc = lock.get("end_at_utc")
        start = _utc(start_at_utc, "active_soft_locks.start_at_utc", lock_id)
        end = _utc(end_at_utc, "active_soft_locks.end_at_utc", lock_id)
        if end <= start:
            raise _input_error("INVALID_SOFT_LOCK_INTERVAL", "active_soft_locks", lock_id)
        expected_tuple = (
            _identifier(lock.get("resource_id"), "active_soft_locks.resource_id", lock_id),
            start_at_utc,
            end_at_utc,
        )
        observed_tuple = (
            assignment["resource_id"],
            assignment["start_at_utc"],
            assignment["end_at_utc"],
        )
        violations += int(expected_tuple != observed_tuple)
    return violations, seen


def _normalize_reason(value: object, field: str) -> dict[str, object]:
    reason = _mapping(value, field)
    if set(reason) != _REASON_FIELDS:
        raise _input_error("INVALID_REASON_FIELDS", field, "<reason>")
    code = _identifier(reason.get("reason_code"), f"{field}.reason_code")
    references = [
        _reference(item, f"{field}.evidence_refs[{index}]")
        for index, item in enumerate(_list(reason.get("evidence_refs"), field))
    ]
    if not references:
        raise _input_error("MISSING_REASON_EVIDENCE", field, code)
    identities = [canonical_contract_bytes(item) for item in references]
    if len(identities) != len(set(identities)):
        raise _input_error("DUPLICATE_REASON_EVIDENCE", field, code)
    references.sort(
        key=lambda item: (
            item["document_version"], item["artifact_id"], item["fingerprint"]
        )
    )
    return {"reason_code": code, "evidence_refs": references}


def _expected_reasons(
    *,
    operation_id: str,
    classification: str,
    provided: object,
    solver_reference: Mapping[str, object],
    removed_reference: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if provided is None and classification == "CHANGED":
        raw: Sequence[object] = [
            {
                "reason_code": "UNATTRIBUTED_SOLVER_CHANGE",
                "evidence_refs": [dict(solver_reference)],
            }
        ]
    else:
        raw = _list(provided, f"reasons_by_operation.{operation_id}")
    reasons = [
        _normalize_reason(value, f"reasons_by_operation.{operation_id}[{index}]")
        for index, value in enumerate(raw)
    ]
    if not reasons:
        raise _input_error("MISSING_REASON", "reasons_by_operation", operation_id)
    codes = {cast(str, reason["reason_code"]) for reason in reasons}
    if not codes.issubset(_CLASSIFICATION_REASONS[classification]):
        raise _input_error("INCOMPATIBLE_REASON", "reasons_by_operation", operation_id)
    if classification == "REMOVED_BY_FACT":
        if removed_reference is None or codes != {"REMOVED_BY_COMPLETION_FACT"}:
            raise _input_error(
                "MISSING_COMPLETION_FACT", "reasons_by_operation", operation_id
            )
        if not any(
            dict(removed_reference)
            in cast(list[dict[str, object]], reason["evidence_refs"])
            for reason in reasons
        ):
            raise _input_error(
                "MISMATCHED_COMPLETION_FACT", "reasons_by_operation", operation_id
            )
    identities = [canonical_contract_bytes(reason) for reason in reasons]
    if len(identities) != len(set(identities)):
        raise _input_error("DUPLICATE_REASON", "reasons_by_operation", operation_id)
    reasons.sort(key=canonical_contract_bytes)
    return reasons


def _violation(
    violations: list[dict[str, object]],
    *,
    code: str,
    field: str,
    entity_id: str,
    expected: object,
    observed: object,
) -> None:
    violations.append(
        {
            "code": code,
            "field": field,
            "entity_id": entity_id,
            "expected": _json_copy(expected, f"{field}.expected"),
            "observed": _json_copy(observed, f"{field}.observed"),
        }
    )


def _compare(
    violations: list[dict[str, object]],
    *,
    field: str,
    entity_id: str,
    expected: object,
    observed: object,
) -> None:
    if observed != expected:
        _violation(
            violations,
            code="PROJECTION_MISMATCH",
            field=field,
            entity_id=entity_id,
            expected=expected,
            observed=observed,
        )


def _report_operations(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def validate_change_report(
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
    report: Mapping[str, object],
) -> dict[str, object]:
    """Independently recompute the full universe and return PASS/FAIL evidence."""

    base = _assignments(base_assignments, "base_assignments")
    new = _assignments(new_assignments, "new_assignments")
    active = sorted(
        _identifier(value, "active_operation_ids[]") for value in active_operation_ids
    )
    if len(active) != len(set(active)):
        raise _input_error(
            "DUPLICATE_ACTIVE_OPERATION", "active_operation_ids", "<active>"
        )
    if active != list(new):
        raise _input_error(
            "ACTIVE_UNIVERSE_MISMATCH", "active_operation_ids", "<active>"
        )

    removed_ids = sorted(set(base) - set(new))
    removed = {
        _identifier(operation_id, "removed_by_fact.operation_id"): _reference(
            reference, f"removed_by_fact.{operation_id}"
        )
        for operation_id, reference in removed_by_fact.items()
    }
    if set(removed) != set(removed_ids):
        raise _input_error("REMOVED_FACT_SET_MISMATCH", "removed_by_fact", "<universe>")
    universe = sorted(set(base).union(new))
    if set(reasons_by_operation) - set(universe):
        raise _input_error(
            "REASON_OUTSIDE_UNIVERSE", "reasons_by_operation", "<universe>"
        )

    lineage = _mapping(context.get("lineage"), "context.lineage")
    solver_reference = _reference(
        lineage.get("solver_report"), "context.lineage.solver_report"
    )
    zero_delta: dict[str, object] = {
        "resource_changed": False,
        "start_shift_seconds": 0,
        "absolute_start_shift_seconds": 0,
        "end_shift_seconds": 0,
        "duration_delta_seconds": 0,
    }
    expected_operations: list[dict[str, object]] = []
    changed = resource_changes = absolute_shift = 0
    comparable = unchanged = 0
    for operation_id in universe:
        base_assignment = base.get(operation_id)
        new_assignment = new.get(operation_id)
        if base_assignment is None:
            classification = "ADDED"
            delta = zero_delta
        elif new_assignment is None:
            classification = "REMOVED_BY_FACT"
            delta = zero_delta
        else:
            comparable += 1
            delta = _delta(base_assignment, new_assignment)
            if _changed(delta):
                classification = "CHANGED"
                changed += 1
                resource_changes += int(cast(bool, delta["resource_changed"]))
                absolute_shift += cast(int, delta["absolute_start_shift_seconds"])
            else:
                classification = "UNCHANGED"
                unchanged += 1
        expected_operations.append(
            {
                "operation_id": operation_id,
                "classification": classification,
                "base_assignment": base_assignment,
                "new_assignment": new_assignment,
                "deltas": dict(delta),
                "reasons": _expected_reasons(
                    operation_id=operation_id,
                    classification=classification,
                    provided=reasons_by_operation.get(operation_id),
                    solver_reference=solver_reference,
                    removed_reference=removed.get(operation_id),
                ),
            }
        )

    soft_lock_violations, soft_lock_ids = _soft_lock_violations(active_soft_locks, new)
    ratio: dict[str, object]
    if comparable == 0:
        ratio = {
            "status": "NOT_APPLICABLE_NO_COMPARABLE_OPERATION",
            "numerator": 0,
            "denominator": 0,
        }
    else:
        ratio = {
            "status": "APPLICABLE",
            "numerator": unchanged,
            "denominator": comparable,
        }
    stability = {
        "soft_lock_violations": soft_lock_violations,
        "changed_existing_operations": changed,
        "resource_changes": resource_changes,
        "absolute_start_shift_seconds": absolute_shift,
        "unchanged_existing": unchanged,
        "comparable_existing": comparable,
        "unchanged_ratio": ratio,
    }
    before_reference, before_tardiness, before_makespan = _kpi_reference(
        before_kpi, "before_kpi"
    )
    after_reference, after_tardiness, after_makespan = _kpi_reference(
        after_kpi, "after_kpi"
    )

    violations: list[dict[str, object]] = []
    try:
        require_p4_document(report)
    except ValueError as error:
        _violation(
            violations,
            code="FROZEN_CONTRACT_REJECTED",
            field=getattr(error, "field", "report"),
            entity_id=str(report.get("report_id", "<report>")),
            expected="change-report.v1 semantic precheck PASS",
            observed=getattr(getattr(error, "reason", None), "value", type(error).__name__),
        )

    expected_freeze = cast(
        dict[str, object],
        _json_copy(context.get("freeze_evidence"), "context.freeze_evidence"),
    )
    expected_lock_ids = _identifier_list(
        expected_freeze.get("effective_lock_ids"),
        "context.freeze_evidence.effective_lock_ids",
        str(expected_freeze.get("freeze_policy_id", "<freeze>")),
    )
    if not soft_lock_ids.issubset(expected_lock_ids):
        raise _input_error(
            "SOFT_LOCK_MISSING_FROM_FREEZE_EVIDENCE",
            "active_soft_locks",
            sorted(soft_lock_ids - set(expected_lock_ids))[0],
        )
    expected_freeze["effective_lock_ids"] = expected_lock_ids
    expected_header = {
        "change_report_version": "change-report.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "environment": context.get("environment"),
        "synthetic": True,
        "synthetic_provenance": _json_copy(
            context.get("synthetic_provenance"), "context.synthetic_provenance"
        ),
        "production_binding": False,
        "base_schedule_version": _json_copy(
            context.get("base_schedule_version"), "context.base_schedule_version"
        ),
        "new_schedule_version": _json_copy(
            context.get("new_schedule_version"), "context.new_schedule_version"
        ),
        "lineage": _json_copy(lineage, "context.lineage"),
        "freeze_evidence": expected_freeze,
        "generated_at_utc": context.get("generated_at_utc"),
        "correlation_id": context.get("correlation_id"),
    }
    for field, expected in expected_header.items():
        _compare(
            violations,
            field=field,
            entity_id=str(report.get("report_id", "<report>")),
            expected=expected,
            observed=report.get(field),
        )
    _compare(
        violations,
        field="operation_universe_count",
        entity_id="<universe>",
        expected=len(universe),
        observed=report.get("operation_universe_count"),
    )
    observed_operations = _report_operations(report.get("operations"))
    _compare(
        violations,
        field="operations",
        entity_id="<universe>",
        expected=expected_operations,
        observed=observed_operations,
    )
    _compare(
        violations,
        field="stability",
        entity_id="OBJ-002",
        expected=stability,
        observed=report.get("stability"),
    )
    _compare(
        violations,
        field="before_kpi",
        entity_id="OBJ-001",
        expected=before_reference,
        observed=report.get("before_kpi"),
    )
    _compare(
        violations,
        field="after_kpi",
        entity_id="OBJ-001",
        expected=after_reference,
        observed=report.get("after_kpi"),
    )
    expected_fingerprint = change_report_fingerprint(report)
    _compare(
        violations,
        field="report_fingerprint",
        entity_id=str(report.get("report_id", "<report>")),
        expected=expected_fingerprint,
        observed=report.get("report_fingerprint"),
    )
    _compare(
        violations,
        field="report_id",
        entity_id=str(report.get("report_id", "<report>")),
        expected="change-report-" + expected_fingerprint.removeprefix("sha256:"),
        observed=report.get("report_id"),
    )
    violations.sort(
        key=lambda item: (
            cast(str, item["code"]),
            cast(str, item["field"]),
            cast(str, item["entity_id"]),
            canonical_contract_bytes(item),
        )
    )
    basis: dict[str, object] = {
        "precheck_version": PRECHECK_VERSION,
        "status": "PASS" if not violations else "FAIL",
        "change_report_id": report.get("report_id"),
        "change_report_fingerprint": report.get("report_fingerprint"),
        "hard_violation_count": len(violations),
        "violations": violations,
        "objective_vector": [
            soft_lock_violations,
            changed,
            resource_changes,
            absolute_shift,
        ],
        "kpi_comparison": {
            "before_priority_weighted_tardiness_seconds": before_tardiness,
            "after_priority_weighted_tardiness_seconds": after_tardiness,
            "priority_weighted_tardiness_delta_seconds": (
                after_tardiness - before_tardiness
            ),
            "before_makespan_seconds": before_makespan,
            "after_makespan_seconds": after_makespan,
            "makespan_delta_seconds": after_makespan - before_makespan,
        },
        "operation_universe_count": len(universe),
        "independence": {
            "builder_imported": False,
            "stability_calculator_imported": False,
            "solver_imported": False,
            "formal_validator_imported": False,
            "side_effects": "NONE",
        },
    }
    fingerprint = contract_fingerprint(basis)
    return {
        "report_id": "change-report-precheck-"
        + fingerprint.removeprefix("sha256:"),
        "report_fingerprint": fingerprint,
        **basis,
    }


__all__ = [
    "ChangeReportPrecheckInputError",
    "PRECHECK_VERSION",
    "validate_change_report",
]
