"""Independent P4 replan-candidate and ChangeReport arithmetic validator.

The evaluator deliberately imports neither CP-SAT nor any planning backend or
reporting calculator.  It reuses the formal C-001..C-011 evaluator only as a
fresh public boundary and independently recomputes the P4 facts/locks,
operation universe, objective values, and ChangeReport classification basis.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from typing import NoReturn, TypedDict, cast

from app.domain.execution_contracts import contract_fingerprint
from app.domain.types import parse_utc_instant
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


REPLAN_CANDIDATE_VALIDATION_VERSION = "replan-candidate-validation.v1"

_ASSIGNMENT_FIELDS = frozenset(
    {
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
)
_STABILITY_FIELDS = frozenset(
    {
        "soft_lock_violations",
        "changed_existing_operations",
        "resource_changes",
        "absolute_start_shift_seconds",
    }
)


class ReplanCandidateValidationReason(StrEnum):
    """Stable input-boundary failures before independent rule evaluation."""

    INVALID_CANDIDATE = "INVALID_CANDIDATE"
    INVALID_BASE_ASSIGNMENT = "INVALID_BASE_ASSIGNMENT"
    INVALID_EFFECTIVE_LOCK_PROJECTION = "INVALID_EFFECTIVE_LOCK_PROJECTION"
    INVALID_OBJECTIVE_EVIDENCE = "INVALID_OBJECTIVE_EVIDENCE"


class ReplanCandidateValidationInputError(ValueError):
    """An authoritative validation input is not representable."""

    def __init__(
        self,
        reason: ReplanCandidateValidationReason,
        *,
        field: str,
        entity_id: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        self.message = message
        super().__init__(f"{reason.value} at {field} ({entity_id}): {message}")


class ReplanValidationViolation(TypedDict):
    code: str
    field: str
    entity_id: str
    expected: object
    observed: object


class ReplanCandidateValidationReport(TypedDict):
    validation_report_version: str
    report_id: str
    report_fingerprint: str
    status: str
    hard_violation_count: int
    violations: list[ReplanValidationViolation]
    formal_validation: dict[str, object]
    objective_values: dict[str, object]
    fact_lock_evidence: dict[str, object]
    change_report_projection: dict[str, object]
    independence: dict[str, object]


def _reject(
    reason: ReplanCandidateValidationReason,
    *,
    field: str,
    entity_id: str,
    message: str,
) -> NoReturn:
    raise ReplanCandidateValidationInputError(
        reason,
        field=field,
        entity_id=entity_id,
        message=message,
    )


def _mapping(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(
            reason,
            field=field,
            entity_id="<input>",
            message="value must be an object",
        )
    return cast(Mapping[str, object], value)


def _sequence(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
) -> Sequence[object]:
    if not isinstance(value, list):
        _reject(
            reason,
            field=field,
            entity_id="<input>",
            message="value must be an array",
        )
    return value


def _identifier(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
    entity_id: str = "<input>",
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        _reject(
            reason,
            field=field,
            entity_id=entity_id,
            message="value must be a canonical identifier",
        )
    return value


def _integer(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
    entity_id: str,
    minimum: int = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _reject(
            reason,
            field=field,
            entity_id=entity_id,
            message=f"value must be an integer >= {minimum}",
        )
    return value


def _utc(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
    entity_id: str,
) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _reject(
            reason,
            field=field,
            entity_id=entity_id,
            message="instant must be RFC3339 UTC Z",
        )
    try:
        instant = parse_utc_instant(value)
    except ValueError as error:
        raise ReplanCandidateValidationInputError(
            reason,
            field=field,
            entity_id=entity_id,
            message="instant is invalid",
        ) from error
    if instant.microsecond:
        _reject(
            reason,
            field=field,
            entity_id=entity_id,
            message="instant must have whole-second precision",
        )
    return instant


def _identifier_list(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
    entity_id: str,
) -> list[str]:
    values = _sequence(value, field, reason=reason)
    identifiers = [
        _identifier(
            item,
            f"{field}[]",
            reason=reason,
            entity_id=entity_id,
        )
        for item in values
    ]
    if identifiers != sorted(set(identifiers)):
        _reject(
            reason,
            field=field,
            entity_id=entity_id,
            message="identifiers must be sorted and unique",
        )
    return identifiers


def _assignment(
    value: object,
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
) -> dict[str, object]:
    document = _mapping(value, field, reason=reason)
    operation_id = _identifier(
        document.get("operation_id"),
        f"{field}.operation_id",
        reason=reason,
    )
    if set(document) != _ASSIGNMENT_FIELDS:
        _reject(
            reason,
            field=field,
            entity_id=operation_id,
            message="fields differ from planning-solution.v1 operationAssignment",
        )
    start_tick = _integer(
        document.get("start_tick"),
        f"{field}.start_tick",
        reason=reason,
        entity_id=operation_id,
    )
    end_tick = _integer(
        document.get("end_tick"),
        f"{field}.end_tick",
        reason=reason,
        entity_id=operation_id,
        minimum=1,
    )
    duration_ticks = _integer(
        document.get("duration_ticks"),
        f"{field}.duration_ticks",
        reason=reason,
        entity_id=operation_id,
        minimum=1,
    )
    duration_seconds = _integer(
        document.get("duration_seconds"),
        f"{field}.duration_seconds",
        reason=reason,
        entity_id=operation_id,
        minimum=1,
    )
    start = _utc(
        document.get("start_at_utc"),
        f"{field}.start_at_utc",
        reason=reason,
        entity_id=operation_id,
    )
    end = _utc(
        document.get("end_at_utc"),
        f"{field}.end_at_utc",
        reason=reason,
        entity_id=operation_id,
    )
    if end <= start or end_tick - start_tick != duration_ticks:
        _reject(
            reason,
            field=field,
            entity_id=operation_id,
            message="assignment interval/tick fields are inconsistent",
        )
    return {
        "operation_id": operation_id,
        "resource_id": _identifier(
            document.get("resource_id"),
            f"{field}.resource_id",
            reason=reason,
            entity_id=operation_id,
        ),
        "start_tick": start_tick,
        "end_tick": end_tick,
        "duration_ticks": duration_ticks,
        "start_at_utc": cast(str, document["start_at_utc"]),
        "end_at_utc": cast(str, document["end_at_utc"]),
        "duration_seconds": duration_seconds,
        "lock_ids": _identifier_list(
            document.get("lock_ids"),
            f"{field}.lock_ids",
            reason=reason,
            entity_id=operation_id,
        ),
        "execution_fact_ids": _identifier_list(
            document.get("execution_fact_ids"),
            f"{field}.execution_fact_ids",
            reason=reason,
            entity_id=operation_id,
        ),
    }


def _assignment_index(
    values: Sequence[object],
    field: str,
    *,
    reason: ReplanCandidateValidationReason,
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for index, value in enumerate(values):
        assignment = _assignment(value, f"{field}[{index}]", reason=reason)
        operation_id = cast(str, assignment["operation_id"])
        if operation_id in indexed:
            _reject(
                reason,
                field=field,
                entity_id=operation_id,
                message="operation assignment appears more than once",
            )
        indexed[operation_id] = assignment
    return dict(sorted(indexed.items()))


def _problem_reference(problem: Mapping[str, object]) -> dict[str, object]:
    return {
        "problem_version": problem["problem_version"],
        "problem_builder_version": problem["problem_builder_version"],
        "problem_hash_projection_version": problem["problem_hash_projection_version"],
        "problem_hash": problem["problem_hash"],
        "snapshot_id": problem["snapshot_id"],
        "tick_seconds": problem["tick_seconds"],
        "horizon_start_utc": problem["horizon_start_utc"],
        "horizon_end_utc": problem["horizon_end_utc"],
    }


def _candidate(
    value: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    required = {
        "candidate_version",
        "assignment_count",
        "assignments",
        "candidate_fingerprint",
    }
    if set(value) != required or value.get("candidate_version") != "replan-candidate.v1":
        _reject(
            ReplanCandidateValidationReason.INVALID_CANDIDATE,
            field="candidate",
            entity_id="<candidate>",
            message="candidate fields/version differ from replan-candidate.v1",
        )
    raw_assignments = _sequence(
        value.get("assignments"),
        "candidate.assignments",
        reason=ReplanCandidateValidationReason.INVALID_CANDIDATE,
    )
    assignments = _assignment_index(
        raw_assignments,
        "candidate.assignments",
        reason=ReplanCandidateValidationReason.INVALID_CANDIDATE,
    )
    count = _integer(
        value.get("assignment_count"),
        "candidate.assignment_count",
        reason=ReplanCandidateValidationReason.INVALID_CANDIDATE,
        entity_id="<candidate>",
    )
    if count != len(assignments):
        _reject(
            ReplanCandidateValidationReason.INVALID_CANDIDATE,
            field="candidate.assignment_count",
            entity_id="<candidate>",
            message="assignment_count differs from the complete assignment array",
        )
    basis = {
        "candidate_version": "replan-candidate.v1",
        "assignment_count": count,
        "assignments": list(assignments.values()),
    }
    expected_fingerprint = contract_fingerprint(basis)
    if value.get("candidate_fingerprint") != expected_fingerprint:
        _reject(
            ReplanCandidateValidationReason.INVALID_CANDIDATE,
            field="candidate.candidate_fingerprint",
            entity_id="<candidate>",
            message="candidate fingerprint differs from canonical content",
        )
    return assignments, basis


def _projection(value: Mapping[str, object]) -> Mapping[str, object]:
    if (
        value.get("effective_lock_projection_version")
        != "effective-lock-projection.v1"
        or value.get("canonicalization_version") != "canonical-json.v1"
        or value.get("data_plane") != "SIMULATION"
    ):
        _reject(
            ReplanCandidateValidationReason.INVALID_EFFECTIVE_LOCK_PROJECTION,
            field="effective_locks",
            entity_id="<projection>",
            message="projection version/plane is outside the P4 Simulation contract",
        )
    basis = dict(value)
    observed = basis.pop("projection_fingerprint", None)
    if observed != contract_fingerprint(basis):
        _reject(
            ReplanCandidateValidationReason.INVALID_EFFECTIVE_LOCK_PROJECTION,
            field="effective_locks.projection_fingerprint",
            entity_id="<projection>",
            message="projection fingerprint differs from canonical content",
        )
    return value


def _ids(
    value: object,
    field: str,
) -> list[str]:
    return _identifier_list(
        value,
        field,
        reason=ReplanCandidateValidationReason.INVALID_EFFECTIVE_LOCK_PROJECTION,
        entity_id="<projection>",
    )


def _protection_values(
    projection: Mapping[str, object], field: str
) -> list[Mapping[str, object]]:
    values = _sequence(
        projection.get(field),
        f"effective_locks.{field}",
        reason=ReplanCandidateValidationReason.INVALID_EFFECTIVE_LOCK_PROJECTION,
    )
    return [
        _mapping(
            value,
            f"effective_locks.{field}[{index}]",
            reason=ReplanCandidateValidationReason.INVALID_EFFECTIVE_LOCK_PROJECTION,
        )
        for index, value in enumerate(values)
    ]


def _violation(
    violations: list[ReplanValidationViolation],
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
            "expected": expected,
            "observed": observed,
        }
    )


def _tuple(assignment: Mapping[str, object]) -> tuple[object, object, object]:
    return (
        assignment.get("resource_id"),
        assignment.get("start_at_utc"),
        assignment.get("end_at_utc"),
    )


def _protection_tuple(protection: Mapping[str, object]) -> tuple[object, object, object]:
    return (
        protection.get("resource_id"),
        protection.get("start_at_utc"),
        protection.get("end_at_utc"),
    )


def _protection_id(value: Mapping[str, object]) -> str:
    identifier = value.get("reference_id", value.get("lock_id"))
    return _identifier(
        identifier,
        "effective_locks.protection_id",
        reason=ReplanCandidateValidationReason.INVALID_EFFECTIVE_LOCK_PROJECTION,
    )


def _measure_delivery(
    problem: Mapping[str, object], assignments: Mapping[str, Mapping[str, object]]
) -> int:
    completion_by_demand: dict[str, int] = {}
    demand_by_operation = {
        cast(str, operation["operation_id"]): cast(str, operation["demand_order_id"])
        for operation in cast(
            Sequence[Mapping[str, object]], problem["operation_instances"]
        )
    }
    for operation_id, assignment in assignments.items():
        demand_id = demand_by_operation[operation_id]
        completion_by_demand[demand_id] = max(
            completion_by_demand.get(demand_id, 0),
            cast(int, assignment["end_tick"]),
        )
    horizon_start = parse_utc_instant(cast(str, problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    total = 0
    for demand in cast(Sequence[Mapping[str, object]], problem["delivery_demands"]):
        demand_id = cast(str, demand["demand_order_id"])
        due = parse_utc_instant(cast(str, demand["due_at_utc"]))
        due_offset = int((due - horizon_start).total_seconds())
        completion_seconds = completion_by_demand[demand_id] * tick_seconds
        total += cast(int, demand["priority_weight"]) * max(
            0, completion_seconds - due_offset
        )
    return total


def _measure_stability(
    *,
    base: Mapping[str, Mapping[str, object]],
    candidate: Mapping[str, Mapping[str, object]],
    soft_locks: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    soft_violations = 0
    for lock in soft_locks:
        operation_id = cast(str, lock.get("operation_id"))
        assignment = candidate.get(operation_id)
        soft_violations += int(
            assignment is None or _tuple(assignment) != _protection_tuple(lock)
        )
    changed = resource_changes = absolute_shift = 0
    for operation_id in sorted(set(base).intersection(candidate)):
        before = base[operation_id]
        after = candidate[operation_id]
        if _tuple(before) != _tuple(after):
            changed += 1
            resource_changes += int(before["resource_id"] != after["resource_id"])
            before_start = parse_utc_instant(cast(str, before["start_at_utc"]))
            after_start = parse_utc_instant(cast(str, after["start_at_utc"]))
            absolute_shift += abs(int((after_start - before_start).total_seconds()))
    return {
        "soft_lock_violations": soft_violations,
        "changed_existing_operations": changed,
        "resource_changes": resource_changes,
        "absolute_start_shift_seconds": absolute_shift,
    }


def _objective_evidence(value: Mapping[str, object]) -> dict[str, object]:
    if set(value) != {"delivery", "stability", "makespan"}:
        _reject(
            ReplanCandidateValidationReason.INVALID_OBJECTIVE_EVIDENCE,
            field="objective_evidence",
            entity_id="<objective>",
            message="objective evidence must contain Delivery/Stability/Makespan",
        )
    delivery = _integer(
        value.get("delivery"),
        "objective_evidence.delivery",
        reason=ReplanCandidateValidationReason.INVALID_OBJECTIVE_EVIDENCE,
        entity_id="OBJ-001",
    )
    stability = _mapping(
        value.get("stability"),
        "objective_evidence.stability",
        reason=ReplanCandidateValidationReason.INVALID_OBJECTIVE_EVIDENCE,
    )
    if set(stability) != _STABILITY_FIELDS:
        _reject(
            ReplanCandidateValidationReason.INVALID_OBJECTIVE_EVIDENCE,
            field="objective_evidence.stability",
            entity_id="OBJ-002",
            message="stability evidence has an unknown component set",
        )
    normalized_stability = {
        field: _integer(
            stability[field],
            f"objective_evidence.stability.{field}",
            reason=ReplanCandidateValidationReason.INVALID_OBJECTIVE_EVIDENCE,
            entity_id="OBJ-002",
        )
        for field in sorted(_STABILITY_FIELDS)
    }
    makespan = _integer(
        value.get("makespan"),
        "objective_evidence.makespan",
        reason=ReplanCandidateValidationReason.INVALID_OBJECTIVE_EVIDENCE,
        entity_id="OBJ-003",
    )
    return {
        "delivery": delivery,
        "stability": normalized_stability,
        "makespan": makespan,
    }


def validate_replan_candidate(
    *,
    problem: PlanningProblemDocumentV2,
    base_assignments: Sequence[object],
    effective_locks: Mapping[str, object],
    candidate: Mapping[str, object],
    objective_evidence: Mapping[str, object],
) -> ReplanCandidateValidationReport:
    """Freshly validate one solver candidate and its report arithmetic."""

    projection = _projection(effective_locks)
    candidate_assignments, candidate_basis = _candidate(candidate)
    base = _assignment_index(
        base_assignments,
        "base_assignments",
        reason=ReplanCandidateValidationReason.INVALID_BASE_ASSIGNMENT,
    )
    declared_objectives = _objective_evidence(objective_evidence)
    active_ids = sorted(
        cast(str, operation["operation_id"])
        for operation in problem["operation_instances"]
    )
    formal = validate_problem_schedule(
        cast(Mapping[str, object], problem),
        {
            "problem": _problem_reference(cast(Mapping[str, object], problem)),
            "assignments": candidate_basis["assignments"],
        },
    )
    violations: list[ReplanValidationViolation] = []
    if formal["status"] != "PASS":
        _violation(
            violations,
            code="FORMAL_VALIDATOR_FAILED",
            field="candidate.assignments",
            entity_id=cast(str, problem["problem_hash"]),
            expected="C-001..C-011 PASS",
            observed=formal["hard_violation_count"],
        )
    if list(candidate_assignments) != active_ids:
        _violation(
            violations,
            code="ACTIVE_UNIVERSE_MISMATCH",
            field="candidate.assignments",
            entity_id=cast(str, problem["problem_hash"]),
            expected=active_ids,
            observed=list(candidate_assignments),
        )

    projected_active = _ids(
        projection.get("new_active_operation_ids"),
        "effective_locks.new_active_operation_ids",
    )
    projected_base = _ids(
        projection.get("base_assignment_operation_ids"),
        "effective_locks.base_assignment_operation_ids",
    )
    projected_completed = _ids(
        projection.get("completed_operation_ids"),
        "effective_locks.completed_operation_ids",
    )
    projected_added = _ids(
        projection.get("added_operation_ids"),
        "effective_locks.added_operation_ids",
    )
    expected_sets = {
        "new_active_operation_ids": active_ids,
        "base_assignment_operation_ids": list(base),
        "completed_operation_ids": sorted(set(base) - set(active_ids)),
        "added_operation_ids": sorted(set(active_ids) - set(base)),
    }
    observed_sets = {
        "new_active_operation_ids": projected_active,
        "base_assignment_operation_ids": projected_base,
        "completed_operation_ids": projected_completed,
        "added_operation_ids": projected_added,
    }
    for field, expected in expected_sets.items():
        if observed_sets[field] != expected:
            _violation(
                violations,
                code="CHANGE_REPORT_UNIVERSE_MISMATCH",
                field=f"effective_locks.{field}",
                entity_id="<operation-universe>",
                expected=expected,
                observed=observed_sets[field],
            )

    running = _protection_values(projection, "running_protections")
    explicit_hard = _protection_values(projection, "explicit_hard_locks")
    derived_hard = _protection_values(projection, "freeze_derived_hard_locks")
    soft_locks = _protection_values(projection, "soft_locks")
    completed = _protection_values(projection, "completed_protections")
    hard_sections = (
        ("running_protections", running),
        ("explicit_hard_locks", explicit_hard),
        ("freeze_derived_hard_locks", derived_hard),
    )
    for section, protections in hard_sections:
        for protection in protections:
            operation_id = cast(str, protection.get("operation_id"))
            assignment = candidate_assignments.get(operation_id)
            expected_tuple = _protection_tuple(protection)
            observed_tuple = None if assignment is None else _tuple(assignment)
            if observed_tuple != expected_tuple:
                _violation(
                    violations,
                    code="EFFECTIVE_HARD_LOCK_VIOLATION",
                    field=f"effective_locks.{section}",
                    entity_id=operation_id,
                    expected=expected_tuple,
                    observed=observed_tuple,
                )
                continue
            assert assignment is not None
            reference_id = _protection_id(protection)
            metadata_field = (
                "execution_fact_ids"
                if section == "running_protections"
                else "lock_ids"
            )
            if reference_id not in cast(list[str], assignment[metadata_field]):
                _violation(
                    violations,
                    code="PROTECTION_METADATA_MISSING",
                    field=f"candidate.assignments.{metadata_field}",
                    entity_id=operation_id,
                    expected=reference_id,
                    observed=assignment[metadata_field],
                )
    completed_ids = sorted(cast(str, value.get("operation_id")) for value in completed)
    if completed_ids != projected_completed:
        _violation(
            violations,
            code="COMPLETION_FACT_EVIDENCE_MISMATCH",
            field="effective_locks.completed_protections",
            entity_id="<operation-universe>",
            expected=projected_completed,
            observed=completed_ids,
        )

    measured_stability = _measure_stability(
        base=base,
        candidate=candidate_assignments,
        soft_locks=soft_locks,
    )
    measured_objectives: dict[str, object] = {
        "delivery": _measure_delivery(problem, candidate_assignments),
        "stability": measured_stability,
        "makespan": max(
            (cast(int, item["end_tick"]) for item in candidate_assignments.values()),
            default=0,
        )
        * problem["tick_seconds"],
    }
    for field in ("delivery", "stability", "makespan"):
        if declared_objectives[field] != measured_objectives[field]:
            _violation(
                violations,
                code="OBJECTIVE_EVIDENCE_MISMATCH",
                field=f"objective_evidence.{field}",
                entity_id={
                    "delivery": "OBJ-001",
                    "stability": "OBJ-002",
                    "makespan": "OBJ-003",
                }[field],
                expected=measured_objectives[field],
                observed=declared_objectives[field],
            )

    classifications: dict[str, str] = {}
    for operation_id in sorted(set(base).union(candidate_assignments)):
        before = base.get(operation_id)
        after = candidate_assignments.get(operation_id)
        if before is None:
            classifications[operation_id] = "ADDED"
        elif after is None:
            classifications[operation_id] = "REMOVED_BY_FACT"
        elif _tuple(before) == _tuple(after):
            classifications[operation_id] = "UNCHANGED"
        else:
            classifications[operation_id] = "CHANGED"
    counts = {
        classification: sum(value == classification for value in classifications.values())
        for classification in ("UNCHANGED", "CHANGED", "ADDED", "REMOVED_BY_FACT")
    }
    violations.sort(
        key=lambda item: (item["code"], item["field"], item["entity_id"])
    )
    basis: dict[str, object] = {
        "validation_report_version": REPLAN_CANDIDATE_VALIDATION_VERSION,
        "status": "PASS" if not violations else "FAIL",
        "hard_violation_count": len(violations),
        "violations": violations,
        "formal_validation": dict(formal),
        "objective_values": measured_objectives,
        "fact_lock_evidence": {
            "running_fact_count": len(running),
            "explicit_hard_lock_count": len(explicit_hard),
            "freeze_derived_hard_lock_count": len(derived_hard),
            "soft_lock_count": len(soft_locks),
            "completed_fact_count": len(completed),
        },
        "change_report_projection": {
            "operation_universe_count": len(classifications),
            "classifications": classifications,
            "classification_counts": counts,
            "complete": not any(
                item["code"].startswith("CHANGE_REPORT_")
                or item["code"] == "COMPLETION_FACT_EVIDENCE_MISMATCH"
                for item in violations
            ),
        },
        "independence": {
            "cp_sat_imported": False,
            "backend_imported": False,
            "reporting_calculator_imported": False,
            "solver_status_trusted": False,
            "formal_validator_fresh": True,
            "side_effects": "NONE",
        },
    }
    fingerprint = contract_fingerprint(basis)
    return cast(
        ReplanCandidateValidationReport,
        {
            "report_id": "replan-candidate-validation-"
            + fingerprint.removeprefix("sha256:"),
            "report_fingerprint": fingerprint,
            **basis,
        },
    )


__all__ = [
    "REPLAN_CANDIDATE_VALIDATION_VERSION",
    "ReplanCandidateValidationInputError",
    "ReplanCandidateValidationReason",
    "ReplanCandidateValidationReport",
    "validate_replan_candidate",
]
