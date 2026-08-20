"""Independent PlanningProblem v2 and PlanningSolution schedule validation.

The evaluator consumes only solver-neutral JSON facts.  It deliberately keeps
its rule arithmetic in this module and does not depend on a solver backend, the
fixture-local P0 evaluator, or committed expected outcomes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from typing import Literal, cast

from app.domain.contracts import (
    ErrorDetailDocument,
    ErrorDocumentV2,
    JsonValue,
    ValidationReportDocumentV2,
    ValidationViolationDocumentV2,
)
from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.problem.contracts import PlanningProblemError
from app.planning.problem.hashing import (
    problem_v2_hash_for,
    validate_built_problem_v2,
)


type ConstraintId = Literal[
    "C-001",
    "C-002",
    "C-003",
    "C-004",
    "C-005",
    "C-006",
    "C-007",
    "C-008",
    "C-009",
    "C-010",
    "C-011",
]

VALIDATION_REPORT_CONTRACT = "validation-report.v2"
FORMAL_RULE_METADATA: dict[ConstraintId, tuple[str, str]] = {
    "C-001": (
        "exactly one assignment per unfinished operation",
        "operation assignment completeness violated",
    ),
    "C-002": (
        "successor start remains inside the declared lag window",
        "precedence lag violated",
    ),
    "C-003": (
        "exactly one listed candidate resource",
        "candidate resource selection violated",
    ),
    "C-004": (
        "capacity-1 resource intervals do not overlap",
        "resource overlap detected",
    ),
    "C-005": (
        "non-preemptive assignment avoids all unavailable intervals",
        "resource calendar violated",
    ),
    "C-006": (
        "start >= release_at and start >= material_ready_at",
        "release or material gate violated",
    ),
    "C-007": (
        "completed/running execution facts remain authoritative",
        "execution fact preservation violated",
    ),
    "C-008": (
        "HARD_LOCK resource/start/end remain fixed",
        "hard lock moved",
    ),
    "C-009": (
        "cross-workshop transport lag is respected",
        "cross-workshop transport lag violated",
    ),
    "C-010": (
        "interval length equals selected resource duration ticks",
        "operation duration inconsistent with selected resource",
    ),
    "C-011": (
        "NOT_STARTED assignment remains wholly inside horizon",
        "planning horizon violated",
    ),
}


class ProblemScheduleValidationInputError(ValueError):
    """Stable rejection for an invalid authoritative Problem input."""

    def __init__(self, *, field: str, expected_contract: str, message: str) -> None:
        self.field = field
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True)
class _Assignment:
    index: int
    operation_id: str
    resource_id: str | None
    start_tick: int | None
    end_tick: int | None
    duration_ticks: int | None
    start_at_utc: datetime | None
    end_at_utc: datetime | None
    duration_seconds: int | None
    lock_ids: tuple[str, ...]
    execution_fact_ids: tuple[str, ...]

    def interval_is_usable(self) -> bool:
        return (
            self.start_tick is not None
            and self.end_tick is not None
            and self.end_tick > self.start_tick
        )

    def observed_tuple(self) -> dict[str, object]:
        return {
            "operation_id": self.operation_id,
            "resource_id": self.resource_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "duration_ticks": self.duration_ticks,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class _Endpoint:
    operation_id: str
    resource_id: str
    start_at: datetime
    end_at: datetime


def _json_value(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _violation(
    constraint_id: ConstraintId,
    entity_ids: Sequence[str],
    observed_value: object,
) -> ValidationViolationDocumentV2:
    identifiers = list(dict.fromkeys(value for value in entity_ids if value))
    if not identifiers:
        identifiers = ["candidate"]
    expected_rule, message = FORMAL_RULE_METADATA[constraint_id]
    return {
        "constraint_id": constraint_id,
        "severity": "HARD",
        "entity_ids": identifiers,
        "observed_value": _json_value(observed_value),
        "expected_rule": expected_rule,
        "message": message,
    }


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _identifier(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        return None
    return value


def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return parse_utc_instant(value)
    except ValueError:
        return None


def _identifier_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    identifiers = tuple(
        identifier for item in value if (identifier := _identifier(item)) is not None
    )
    if len(identifiers) != len(value):
        return ()
    return identifiers


def _validated_problem(problem: Mapping[str, object]) -> None:
    try:
        validate_built_problem_v2(problem)
        declared_hash = problem["problem_hash"]
        expected_hash = problem_v2_hash_for(problem)
    except (KeyError, TypeError, ValueError, PlanningProblemError) as error:
        raise ProblemScheduleValidationInputError(
            field=getattr(error, "field", "planning_problem"),
            expected_contract="valid solver-neutral planning-problem.v2",
            message="authoritative Problem failed its contract precheck",
        ) from error
    if declared_hash != expected_hash:
        raise ProblemScheduleValidationInputError(
            field="problem_hash",
            expected_contract="content-derived planning-problem-hash-projection.v2",
            message="authoritative Problem hash does not match its facts",
        )


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


def _materialize_assignments(
    problem: Mapping[str, object], candidate: Mapping[str, object]
) -> tuple[list[_Assignment], list[ValidationViolationDocumentV2]]:
    violations: list[ValidationViolationDocumentV2] = []
    snapshot_id = str(problem["snapshot_id"])
    expected_reference = _problem_reference(problem)
    observed_reference = candidate.get("problem")
    if (
        not isinstance(observed_reference, Mapping)
        or dict(observed_reference) != expected_reference
    ):
        violations.append(
            _violation(
                "C-001",
                [snapshot_id],
                {
                    "reason": "candidate references a different PlanningProblem",
                    "observed_problem_reference": (
                        dict(observed_reference)
                        if isinstance(observed_reference, Mapping)
                        else observed_reference
                    ),
                    "expected_problem_reference": expected_reference,
                },
            )
        )

    raw_assignments = candidate.get("assignments")
    if not isinstance(raw_assignments, list):
        violations.append(
            _violation(
                "C-001",
                [snapshot_id],
                {
                    "reason": "candidate.assignments is not an array",
                    "observed_type": type(raw_assignments).__name__,
                },
            )
        )
        return [], violations

    assignments: list[_Assignment] = []
    for index, raw_assignment in enumerate(raw_assignments):
        location = f"candidate.assignments[{index}]"
        if not isinstance(raw_assignment, Mapping):
            violations.append(
                _violation(
                    "C-001",
                    [location],
                    {
                        "reason": "assignment is not an object",
                        "observed_type": type(raw_assignment).__name__,
                    },
                )
            )
            continue
        operation_id = _identifier(raw_assignment.get("operation_id"))
        if operation_id is None:
            violations.append(
                _violation(
                    "C-001",
                    [location],
                    {
                        "reason": "assignment has no canonical operation_id",
                        "observed_operation_id": raw_assignment.get("operation_id"),
                    },
                )
            )
            continue
        resource_id = _identifier(raw_assignment.get("resource_id"))
        if resource_id is None:
            violations.append(
                _violation(
                    "C-003",
                    [operation_id],
                    {
                        "reason": "assignment has no canonical resource_id",
                        "observed_resource_id": raw_assignment.get("resource_id"),
                    },
                )
            )
        assignment = _Assignment(
            index=index,
            operation_id=operation_id,
            resource_id=resource_id,
            start_tick=_integer(raw_assignment.get("start_tick")),
            end_tick=_integer(raw_assignment.get("end_tick")),
            duration_ticks=_integer(raw_assignment.get("duration_ticks")),
            start_at_utc=_instant(raw_assignment.get("start_at_utc")),
            end_at_utc=_instant(raw_assignment.get("end_at_utc")),
            duration_seconds=_integer(raw_assignment.get("duration_seconds")),
            lock_ids=_identifier_tuple(raw_assignment.get("lock_ids")),
            execution_fact_ids=_identifier_tuple(
                raw_assignment.get("execution_fact_ids")
            ),
        )
        assignments.append(assignment)
        if not assignment.interval_is_usable():
            violations.append(
                _violation(
                    "C-001",
                    [operation_id],
                    {
                        "reason": "assignment has no positive scheduled interval",
                        "start_tick": assignment.start_tick,
                        "end_tick": assignment.end_tick,
                    },
                )
            )
    return assignments, violations


def _groups(
    assignments: Sequence[_Assignment],
) -> defaultdict[str, list[_Assignment]]:
    values: defaultdict[str, list[_Assignment]] = defaultdict(list)
    for assignment in assignments:
        values[assignment.operation_id].append(assignment)
    for grouped in values.values():
        grouped.sort(
            key=lambda value: (
                value.resource_id or "",
                value.start_tick if value.start_tick is not None else -1,
                value.end_tick if value.end_tick is not None else -1,
                value.duration_ticks if value.duration_ticks is not None else -1,
                value.duration_seconds if value.duration_seconds is not None else -1,
                value.lock_ids,
                value.execution_fact_ids,
            )
        )
    return values


def _singles(
    values: Mapping[str, Sequence[_Assignment]],
) -> dict[str, _Assignment]:
    return {
        operation_id: assignments[0]
        for operation_id, assignments in values.items()
        if len(assignments) == 1
    }


def _evaluate_c001(
    problem: Mapping[str, object],
    assignments: Sequence[_Assignment],
    grouped: Mapping[str, Sequence[_Assignment]],
) -> list[ValidationViolationDocumentV2]:
    operations = cast(list[Mapping[str, object]], problem["operation_instances"])
    active_ids = {str(operation["operation_id"]) for operation in operations}
    anchor_ids = {
        str(anchor["operation_id"])
        for anchor in cast(
            list[Mapping[str, object]], problem["historical_completion_anchors"]
        )
    }
    violations: list[ValidationViolationDocumentV2] = []
    for operation_id in sorted(active_ids):
        selected = grouped.get(operation_id, ())
        if len(selected) != 1:
            violations.append(
                _violation(
                    "C-001",
                    [operation_id],
                    {
                        "operation_id": operation_id,
                        "assignment_count": len(selected),
                        "assignments": [value.observed_tuple() for value in selected],
                    },
                )
            )
    unknown_counts: dict[str, int] = defaultdict(int)
    for assignment in assignments:
        if assignment.operation_id not in active_ids | anchor_ids:
            unknown_counts[assignment.operation_id] += 1
    for operation_id in sorted(unknown_counts):
        violations.append(
            _violation(
                "C-001",
                [operation_id],
                {
                    "operation_id": operation_id,
                    "assignment_count": unknown_counts[operation_id],
                    "reason": "operation is absent from the authoritative Problem",
                },
            )
        )
    return violations


def _endpoint_maps(
    problem: Mapping[str, object], singles: Mapping[str, _Assignment]
) -> tuple[dict[str, _Endpoint], dict[str, str]]:
    horizon_start = parse_utc_instant(str(problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    endpoints: dict[str, _Endpoint] = {}
    resources: dict[str, str] = {}
    for operation_id, assignment in singles.items():
        if assignment.resource_id is None or not assignment.interval_is_usable():
            continue
        assert assignment.start_tick is not None
        assert assignment.end_tick is not None
        endpoints[operation_id] = _Endpoint(
            operation_id=operation_id,
            resource_id=assignment.resource_id,
            start_at=horizon_start
            + timedelta(seconds=assignment.start_tick * tick_seconds),
            end_at=horizon_start
            + timedelta(seconds=assignment.end_tick * tick_seconds),
        )
        resources[operation_id] = assignment.resource_id
    for anchor in cast(
        list[Mapping[str, object]], problem["historical_completion_anchors"]
    ):
        operation_id = str(anchor["operation_id"])
        resource_id = str(anchor["resource_id"])
        endpoints[operation_id] = _Endpoint(
            operation_id=operation_id,
            resource_id=resource_id,
            start_at=parse_utc_instant(str(anchor["actual_start_at_utc"])),
            end_at=parse_utc_instant(str(anchor["actual_end_at_utc"])),
        )
        resources[operation_id] = resource_id
    return endpoints, resources


def _evaluate_c002(
    problem: Mapping[str, object], endpoints: Mapping[str, _Endpoint]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for edge in cast(list[Mapping[str, object]], problem["precedence_edges"]):
        predecessor_id = str(edge["predecessor_operation_id"])
        successor_id = str(edge["successor_operation_id"])
        predecessor = endpoints.get(predecessor_id)
        successor = endpoints.get(successor_id)
        if predecessor is None or successor is None:
            continue
        lag_seconds = int((successor.start_at - predecessor.end_at).total_seconds())
        minimum = cast(int, edge["min_lag_seconds"])
        maximum = cast(int | None, edge.get("max_lag_seconds"))
        if lag_seconds < minimum or (maximum is not None and lag_seconds > maximum):
            violations.append(
                _violation(
                    "C-002",
                    [str(edge["precedence_edge_id"]), predecessor_id, successor_id],
                    {
                        "predecessor_end_utc": format_utc_instant(predecessor.end_at),
                        "successor_start_utc": format_utc_instant(successor.start_at),
                        "lag_seconds": lag_seconds,
                        "min_lag_seconds": minimum,
                        "max_lag_seconds": maximum,
                    },
                )
            )
    return violations


def _evaluate_c003(
    problem: Mapping[str, object], grouped: Mapping[str, Sequence[_Assignment]]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for operation in cast(list[Mapping[str, object]], problem["operation_instances"]):
        operation_id = str(operation["operation_id"])
        selected = grouped.get(operation_id, ())
        if not selected:
            continue
        allowed = {
            str(option["resource_id"])
            for option in cast(
                list[Mapping[str, object]], operation["resource_options"]
            )
        }
        observed = [assignment.resource_id for assignment in selected]
        if len(selected) != 1 or observed[0] not in allowed:
            violations.append(
                _violation(
                    "C-003",
                    [operation_id, *[value for value in observed if value]],
                    {
                        "operation_id": operation_id,
                        "selected_resource_count": len(selected),
                        "selected_resource_ids": observed,
                        "allowed_resource_ids": sorted(allowed),
                    },
                )
            )
    return violations


def _evaluate_c004(
    problem: Mapping[str, object], assignments: Sequence[_Assignment]
) -> list[ValidationViolationDocumentV2]:
    capacities = {
        str(resource["resource_id"]): cast(int, resource["capacity"])
        for resource in cast(list[Mapping[str, object]], problem["resources"])
    }
    by_resource: defaultdict[str, list[_Assignment]] = defaultdict(list)
    for assignment in assignments:
        if (
            assignment.resource_id is not None
            and capacities.get(assignment.resource_id) == 1
            and assignment.interval_is_usable()
        ):
            by_resource[assignment.resource_id].append(assignment)
    violations: list[ValidationViolationDocumentV2] = []
    for resource_id in sorted(by_resource):
        ordered = sorted(
            by_resource[resource_id],
            key=lambda value: (
                cast(int, value.start_tick),
                cast(int, value.end_tick),
                value.operation_id,
                value.index,
            ),
        )
        for first_index, first in enumerate(ordered):
            assert first.start_tick is not None and first.end_tick is not None
            for second in ordered[first_index + 1 :]:
                assert second.start_tick is not None and second.end_tick is not None
                if second.start_tick >= first.end_tick:
                    break
                if first.start_tick < second.end_tick:
                    violations.append(
                        _violation(
                            "C-004",
                            [resource_id, first.operation_id, second.operation_id],
                            {
                                "resource_id": resource_id,
                                "first": first.observed_tuple(),
                                "second": second.observed_tuple(),
                            },
                        )
                    )
    return violations


def _evaluate_c005(
    problem: Mapping[str, object], assignments: Sequence[_Assignment]
) -> list[ValidationViolationDocumentV2]:
    horizon_start = parse_utc_instant(str(problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    violations: list[ValidationViolationDocumentV2] = []
    intervals = cast(
        list[Mapping[str, object]], problem["resource_unavailable_intervals"]
    )
    for assignment in assignments:
        if assignment.resource_id is None or not assignment.interval_is_usable():
            continue
        assert assignment.start_tick is not None and assignment.end_tick is not None
        start_at = horizon_start + timedelta(
            seconds=assignment.start_tick * tick_seconds
        )
        end_at = horizon_start + timedelta(seconds=assignment.end_tick * tick_seconds)
        for unavailable in intervals:
            if assignment.resource_id != unavailable["resource_id"]:
                continue
            unavailable_start = parse_utc_instant(str(unavailable["start_utc"]))
            unavailable_end = parse_utc_instant(str(unavailable["end_utc"]))
            if start_at < unavailable_end and unavailable_start < end_at:
                violations.append(
                    _violation(
                        "C-005",
                        [assignment.operation_id, assignment.resource_id],
                        {
                            "assignment_start_utc": format_utc_instant(start_at),
                            "assignment_end_utc": format_utc_instant(end_at),
                            "unavailable_start_utc": format_utc_instant(
                                unavailable_start
                            ),
                            "unavailable_end_utc": format_utc_instant(unavailable_end),
                        },
                    )
                )
    return violations


def _evaluate_c006(
    problem: Mapping[str, object], singles: Mapping[str, _Assignment]
) -> list[ValidationViolationDocumentV2]:
    horizon_start = parse_utc_instant(str(problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    violations: list[ValidationViolationDocumentV2] = []
    for operation in cast(list[Mapping[str, object]], problem["operation_instances"]):
        operation_id = str(operation["operation_id"])
        assignment = singles.get(operation_id)
        if assignment is None or assignment.start_tick is None:
            continue
        start_at = horizon_start + timedelta(
            seconds=assignment.start_tick * tick_seconds
        )
        release_at = parse_utc_instant(str(operation["release_at_utc"]))
        material_at = parse_utc_instant(str(operation["material_ready_at_utc"]))
        if start_at < release_at or start_at < material_at:
            violations.append(
                _violation(
                    "C-006",
                    [operation_id],
                    {
                        "assignment_start_utc": format_utc_instant(start_at),
                        "release_at_utc": format_utc_instant(release_at),
                        "material_ready_at_utc": format_utc_instant(material_at),
                    },
                )
            )
    return violations


def _ceil_ticks(seconds: int, tick_seconds: int) -> int:
    return (seconds + tick_seconds - 1) // tick_seconds


def _evaluate_c007(
    problem: Mapping[str, object], grouped: Mapping[str, Sequence[_Assignment]]
) -> list[ValidationViolationDocumentV2]:
    tick_seconds = cast(int, problem["tick_seconds"])
    violations: list[ValidationViolationDocumentV2] = []
    for anchor in cast(
        list[Mapping[str, object]], problem["historical_completion_anchors"]
    ):
        operation_id = str(anchor["operation_id"])
        selected = grouped.get(operation_id, ())
        if selected:
            violations.append(
                _violation(
                    "C-007",
                    [operation_id, str(anchor["execution_fact_id"])],
                    {
                        "execution_status": "COMPLETED",
                        "assignments": [value.observed_tuple() for value in selected],
                    },
                )
            )
    for operation in cast(list[Mapping[str, object]], problem["operation_instances"]):
        if operation["status"] != "RUNNING":
            continue
        operation_id = str(operation["operation_id"])
        expected_resource = str(operation["assigned_resource_id"])
        remaining_seconds = cast(int, operation["remaining_seconds"])
        expected_end_tick = _ceil_ticks(remaining_seconds, tick_seconds)
        selected = grouped.get(operation_id, ())
        expected_start = parse_utc_instant(str(problem["horizon_start_utc"]))
        candidate_start = (
            expected_start + timedelta(seconds=selected[0].start_tick * tick_seconds)
            if len(selected) == 1 and selected[0].start_tick is not None
            else None
        )
        candidate_end = (
            expected_start + timedelta(seconds=selected[0].end_tick * tick_seconds)
            if len(selected) == 1 and selected[0].end_tick is not None
            else None
        )
        matches = (
            len(selected) == 1
            and selected[0].resource_id == expected_resource
            and selected[0].start_tick == 0
            and selected[0].end_tick == expected_end_tick
            and selected[0].start_at_utc == candidate_start
            and selected[0].end_at_utc == candidate_end
        )
        if not matches:
            violations.append(
                _violation(
                    "C-007",
                    [operation_id, expected_resource],
                    {
                        "execution_status": "RUNNING",
                        "actual_start_at_utc": operation["actual_start_at_utc"],
                        "expected_resource_id": expected_resource,
                        "remaining_seconds": remaining_seconds,
                        "expected_start_tick": 0,
                        "expected_end_tick": expected_end_tick,
                        "assignments": [value.observed_tuple() for value in selected],
                    },
                )
            )
    return violations


def _evaluate_c008(
    problem: Mapping[str, object], grouped: Mapping[str, Sequence[_Assignment]]
) -> list[ValidationViolationDocumentV2]:
    horizon_start = parse_utc_instant(str(problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    violations: list[ValidationViolationDocumentV2] = []
    for lock in cast(list[Mapping[str, object]], problem["operation_locks"]):
        if lock["lock_type"] != "HARD_LOCK":
            continue
        operation_id = str(lock["operation_id"])
        resource_id = str(lock["resource_id"])
        lock_start = parse_utc_instant(str(lock["start_at_utc"]))
        lock_end = parse_utc_instant(str(lock["end_at_utc"]))
        selected = grouped.get(operation_id, ())
        candidate_start: datetime | None = None
        candidate_end: datetime | None = None
        if len(selected) == 1 and selected[0].interval_is_usable():
            assert selected[0].start_tick is not None
            assert selected[0].end_tick is not None
            candidate_start = horizon_start + timedelta(
                seconds=selected[0].start_tick * tick_seconds
            )
            candidate_end = horizon_start + timedelta(
                seconds=selected[0].end_tick * tick_seconds
            )
        matches = (
            len(selected) == 1
            and selected[0].resource_id == resource_id
            and candidate_start == lock_start
            and candidate_end == lock_end
        )
        if not matches:
            violations.append(
                _violation(
                    "C-008",
                    [operation_id, resource_id, str(lock["lock_id"])],
                    {
                        "hard_lock": {
                            "resource_id": resource_id,
                            "start_at_utc": format_utc_instant(lock_start),
                            "end_at_utc": format_utc_instant(lock_end),
                        },
                        "assignments": [value.observed_tuple() for value in selected],
                    },
                )
            )
    return violations


def _evaluate_c009(
    problem: Mapping[str, object], endpoints: Mapping[str, _Endpoint]
) -> list[ValidationViolationDocumentV2]:
    workshop_by_resource = {
        str(resource["resource_id"]): str(resource["workshop_id"])
        for resource in cast(list[Mapping[str, object]], problem["resources"])
    }
    violations: list[ValidationViolationDocumentV2] = []
    for edge in cast(list[Mapping[str, object]], problem["precedence_edges"]):
        predecessor_id = str(edge["predecessor_operation_id"])
        successor_id = str(edge["successor_operation_id"])
        predecessor = endpoints.get(predecessor_id)
        successor = endpoints.get(successor_id)
        if predecessor is None or successor is None:
            continue
        predecessor_workshop = workshop_by_resource.get(predecessor.resource_id)
        successor_workshop = workshop_by_resource.get(successor.resource_id)
        if predecessor_workshop is None or successor_workshop is None:
            continue
        if predecessor_workshop == successor_workshop:
            continue
        observed = int((successor.start_at - predecessor.end_at).total_seconds())
        required = cast(int, edge["transport_lag_seconds"])
        if observed < required:
            violations.append(
                _violation(
                    "C-009",
                    [str(edge["precedence_edge_id"]), predecessor_id, successor_id],
                    {
                        "predecessor_workshop_id": predecessor_workshop,
                        "successor_workshop_id": successor_workshop,
                        "predecessor_end_utc": format_utc_instant(predecessor.end_at),
                        "successor_start_utc": format_utc_instant(successor.start_at),
                        "transport_seconds_observed": observed,
                        "transport_lag_seconds": required,
                    },
                )
            )
    return violations


def _evaluate_c010(
    problem: Mapping[str, object], singles: Mapping[str, _Assignment]
) -> list[ValidationViolationDocumentV2]:
    tick_seconds = cast(int, problem["tick_seconds"])
    violations: list[ValidationViolationDocumentV2] = []
    for operation in cast(list[Mapping[str, object]], problem["operation_instances"]):
        operation_id = str(operation["operation_id"])
        assignment = singles.get(operation_id)
        if (
            assignment is None
            or assignment.resource_id is None
            or assignment.start_tick is None
            or assignment.end_tick is None
        ):
            continue
        option = next(
            (
                value
                for value in cast(
                    list[Mapping[str, object]], operation["resource_options"]
                )
                if value["resource_id"] == assignment.resource_id
            ),
            None,
        )
        if option is None:
            continue
        expected_seconds = (
            cast(int, operation["remaining_seconds"])
            if operation["status"] == "RUNNING"
            else cast(int, option["final_duration_seconds"])
        )
        expected_ticks = _ceil_ticks(expected_seconds, tick_seconds)
        observed_ticks = assignment.end_tick - assignment.start_tick
        matches = (
            observed_ticks == expected_ticks
            and assignment.duration_ticks == observed_ticks
            and assignment.duration_seconds == expected_seconds
        )
        if not matches:
            violations.append(
                _violation(
                    "C-010",
                    [operation_id, assignment.resource_id],
                    {
                        "resource_id": assignment.resource_id,
                        "operation_status": operation["status"],
                        "interval_ticks": observed_ticks,
                        "declared_duration_ticks": assignment.duration_ticks,
                        "declared_duration_seconds": assignment.duration_seconds,
                        "authoritative_duration_seconds": expected_seconds,
                        "expected_duration_ticks": expected_ticks,
                    },
                )
            )
    return violations


def _evaluate_c011(
    problem: Mapping[str, object], assignments: Sequence[_Assignment]
) -> list[ValidationViolationDocumentV2]:
    horizon_start = parse_utc_instant(str(problem["horizon_start_utc"]))
    horizon_end = parse_utc_instant(str(problem["horizon_end_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    status_by_operation = {
        str(operation["operation_id"]): str(operation["status"])
        for operation in cast(
            list[Mapping[str, object]], problem["operation_instances"]
        )
    }
    violations: list[ValidationViolationDocumentV2] = []
    for assignment in assignments:
        if status_by_operation.get(assignment.operation_id) != "NOT_STARTED":
            continue
        restored_start = (
            horizon_start + timedelta(seconds=assignment.start_tick * tick_seconds)
            if assignment.start_tick is not None
            else None
        )
        restored_end = (
            horizon_start + timedelta(seconds=assignment.end_tick * tick_seconds)
            if assignment.end_tick is not None
            else None
        )
        projection_matches = (
            restored_start is not None
            and restored_end is not None
            and assignment.start_at_utc == restored_start
            and assignment.end_at_utc == restored_end
        )
        inside_horizon = (
            restored_start is not None
            and restored_end is not None
            and restored_start >= horizon_start
            and restored_end > restored_start
            and restored_end <= horizon_end
        )
        if not projection_matches or not inside_horizon:
            violations.append(
                _violation(
                    "C-011",
                    [assignment.operation_id],
                    {
                        "start_tick": assignment.start_tick,
                        "end_tick": assignment.end_tick,
                        "declared_start_utc": (
                            format_utc_instant(assignment.start_at_utc)
                            if assignment.start_at_utc is not None
                            else None
                        ),
                        "declared_end_utc": (
                            format_utc_instant(assignment.end_at_utc)
                            if assignment.end_at_utc is not None
                            else None
                        ),
                        "restored_start_utc": (
                            format_utc_instant(restored_start)
                            if restored_start is not None
                            else None
                        ),
                        "restored_end_utc": (
                            format_utc_instant(restored_end)
                            if restored_end is not None
                            else None
                        ),
                        "horizon_start_utc": format_utc_instant(horizon_start),
                        "horizon_end_utc": format_utc_instant(horizon_end),
                    },
                )
            )
    return violations


def _violation_sort_key(
    violation: ValidationViolationDocumentV2,
) -> tuple[str, tuple[str, ...], str]:
    return (
        violation["constraint_id"],
        tuple(violation["entity_ids"]),
        json.dumps(
            violation["observed_value"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


class ProblemScheduleValidator:
    """Stateless formal validator for one Problem and candidate solution pair."""

    def validate(
        self,
        problem: Mapping[str, object],
        candidate: Mapping[str, object],
    ) -> ValidationReportDocumentV2:
        _validated_problem(problem)
        assignments, materialization_violations = _materialize_assignments(
            problem, candidate
        )
        grouped = _groups(assignments)
        singles = _singles(grouped)
        endpoints, _ = _endpoint_maps(problem, singles)
        violations = [
            *materialization_violations,
            *_evaluate_c001(problem, assignments, grouped),
            *_evaluate_c002(problem, endpoints),
            *_evaluate_c003(problem, grouped),
            *_evaluate_c004(problem, assignments),
            *_evaluate_c005(problem, assignments),
            *_evaluate_c006(problem, singles),
            *_evaluate_c007(problem, grouped),
            *_evaluate_c008(problem, grouped),
            *_evaluate_c009(problem, endpoints),
            *_evaluate_c010(problem, singles),
            *_evaluate_c011(problem, assignments),
        ]
        violations.sort(key=_violation_sort_key)
        count = len(violations)
        return {
            "validation_report_version": VALIDATION_REPORT_CONTRACT,
            "problem_hash": str(problem["problem_hash"]),
            "status": "PASS" if count == 0 else "FAIL",
            "hard_violation_count": count,
            "violations": violations,
        }


def validate_problem_schedule(
    problem: Mapping[str, object], candidate: Mapping[str, object]
) -> ValidationReportDocumentV2:
    """Validate one formal candidate without using its declared solve outcome."""

    return ProblemScheduleValidator().validate(problem, candidate)


def validation_error_from_problem_report(
    report: ValidationReportDocumentV2,
) -> ErrorDocumentV2 | None:
    """Map a failed formal report to the registered Error v2 envelope."""

    if report["status"] == "PASS":
        return None
    details: list[ErrorDetailDocument] = []
    for violation in report["violations"]:
        details.append(
            {
                "entity_id": violation["entity_ids"][0],
                "field": "candidate.assignments",
                "observed_value": _json_value(
                    {
                        "constraint_id": violation["constraint_id"],
                        "entity_ids": violation["entity_ids"],
                        "value": violation["observed_value"],
                    }
                ),
                "expected_contract": violation["expected_rule"],
                "source_location": "planning_solution.assignments",
            }
        )
    count = report["hard_violation_count"]
    return {
        "error_version": "error.v2",
        "category": "VALIDATION_FAILED",
        "code": "SCHEDULE_VALIDATION_FAILED",
        "message": f"candidate schedule has {count} hard constraint violation(s)",
        "details": details,
    }


__all__ = [
    "FORMAL_RULE_METADATA",
    "ProblemScheduleValidationInputError",
    "ProblemScheduleValidator",
    "VALIDATION_REPORT_CONTRACT",
    "validate_problem_schedule",
    "validation_error_from_problem_report",
]
