"""Independent P0 evaluator for the SIM-MINIMAL-001 fixture vocabulary.

The evaluator recomputes C-001 through C-011 from fixture input facts and a
candidate schedule.  It deliberately does not import a planning backend,
read expected outcomes, or claim the P2 production/performance validator
boundary.  ``sim-minimal-records.v1`` and ``golden-schedule.v1`` are
fixture-local contracts used only to make P0 correctness executable.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any, Literal, cast

from app.domain.contracts import (
    ErrorDetailDocument,
    ErrorDocumentV2,
    JsonValue,
    ValidationReportDocumentV2,
    ValidationViolationDocumentV2,
)
from app.domain.types import (
    ContractValueError,
    duration_to_ticks,
    format_utc_instant,
    parse_utc_instant,
    require_duration_seconds,
    require_tick_seconds,
)


type JsonObject = dict[str, Any]
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

FIXTURE_RECORD_CONTRACT = "sim-minimal-records.v1"
CANDIDATE_SCHEDULE_CONTRACT = "golden-schedule.v1"
VALIDATION_REPORT_CONTRACT = "validation-report.v2"

RULE_METADATA: dict[ConstraintId, tuple[str, str]] = {
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


class ValidationInputError(ValueError):
    """The fixture-local problem or candidate cannot be evaluated safely."""


@dataclass(frozen=True)
class ResourceOption:
    resource_id: str
    duration_seconds: int


@dataclass(frozen=True)
class Operation:
    operation_id: str
    status: str
    release_at: datetime
    material_ready_at: datetime
    resource_options: tuple[ResourceOption, ...]


@dataclass(frozen=True)
class PrecedenceEdge:
    edge_id: str
    predecessor_operation_id: str
    successor_operation_id: str
    min_lag_seconds: int
    max_lag_seconds: int | None
    transport_lag_seconds: int
    cross_workshop: bool


@dataclass(frozen=True)
class UnavailableInterval:
    resource_id: str
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class ExecutionFact:
    operation_id: str
    status: Literal["COMPLETED", "RUNNING"]
    resource_id: str | None
    remaining_seconds: int | None


@dataclass(frozen=True)
class Lock:
    operation_id: str
    lock_type: Literal["HARD_LOCK", "SOFT_LOCK"]
    resource_id: str
    start_tick: int
    end_tick: int


@dataclass(frozen=True)
class Assignment:
    operation_id: str
    resource_id: str
    start_tick: int
    end_tick: int
    source_index: int

    def observed_tuple(self) -> dict[str, JsonValue]:
        return {
            "operation_id": self.operation_id,
            "resource_id": self.resource_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
        }


@dataclass(frozen=True)
class FixtureProblem:
    problem_hash: str
    scenario_id: str
    scenario_version: str
    tick_seconds: int
    horizon_start: datetime
    horizon_end: datetime
    horizon_ticks: int
    resources: Mapping[str, int]
    operations: Mapping[str, Operation]
    edges: tuple[PrecedenceEdge, ...]
    unavailable_intervals: tuple[UnavailableInterval, ...]
    execution_facts: tuple[ExecutionFact, ...]
    locks: tuple[Lock, ...]


def _object(value: object, location: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValidationInputError(f"{location} must be a string-keyed object")
    return cast(JsonObject, value)


def _array(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationInputError(f"{location} must be an array")
    return cast(list[Any], value)


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationInputError(f"{location} must be a non-empty string")
    return value


def _integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationInputError(f"{location} must be an integer")
    return value


def _boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationInputError(f"{location} must be a boolean")
    return value


def _utc(value: object, location: str) -> datetime:
    try:
        return parse_utc_instant(_text(value, location))
    except ContractValueError as error:
        raise ValidationInputError(f"{location}: {error}") from error


def _duration(value: object, location: str, *, positive: bool = False) -> int:
    raw = _integer(value, location)
    try:
        return int(require_duration_seconds(raw, allow_zero=not positive))
    except ContractValueError as error:
        raise ValidationInputError(f"{location}: {error}") from error


def _records(package: JsonObject, collection: str) -> list[Any]:
    records = _object(package.get("records"), "import_package.records")
    if collection not in records:
        raise ValidationInputError(f"import_package.records.{collection} is required")
    return _array(records[collection], f"import_package.records.{collection}")


def _unique_by_id(
    documents: Sequence[object], id_field: str, location: str
) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for index, raw in enumerate(documents):
        document = _object(raw, f"{location}[{index}]")
        entity_id = _text(document.get(id_field), f"{location}[{index}].{id_field}")
        if entity_id in result:
            raise ValidationInputError(f"{location}.{id_field} duplicates {entity_id}")
        result[entity_id] = document
    return result


def fixture_problem_hash(import_package: Mapping[str, object]) -> str:
    """Hash only fixture problem facts, never the candidate or expected output."""

    try:
        canonical = json.dumps(
            import_package,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValidationInputError("import_package must contain only JSON values") from error
    return f"fixture-problem:sha256:{hashlib.sha256(canonical).hexdigest()}"


def _parse_problem(import_package: Mapping[str, object]) -> FixtureProblem:
    package = _object(dict(import_package), "import_package")
    if package.get("import_package_version") != "import-package.v1":
        raise ValidationInputError("import_package_version must be import-package.v1")
    if package.get("synthetic") is not True:
        raise ValidationInputError("P0 fixture evaluator accepts synthetic input only")
    scenario_id = _text(package.get("scenario_id"), "import_package.scenario_id")

    metadata_values = _records(package, "fixture_metadata")
    if len(metadata_values) != 1:
        raise ValidationInputError("fixture_metadata must contain exactly one record")
    metadata = _object(metadata_values[0], "fixture_metadata[0]")
    if metadata.get("fixture_record_contract") != FIXTURE_RECORD_CONTRACT:
        raise ValidationInputError(
            f"fixture_record_contract must be {FIXTURE_RECORD_CONTRACT}"
        )
    scenario_version = _text(
        metadata.get("scenario_version"), "fixture_metadata[0].scenario_version"
    )
    try:
        tick_seconds = int(
            require_tick_seconds(
                _integer(metadata.get("tick_seconds"), "fixture_metadata[0].tick_seconds")
            )
        )
    except ContractValueError as error:
        raise ValidationInputError(f"fixture_metadata[0].tick_seconds: {error}") from error
    horizon_start = _utc(
        metadata.get("horizon_start_utc"), "fixture_metadata[0].horizon_start_utc"
    )
    horizon_end = _utc(
        metadata.get("horizon_end_utc"), "fixture_metadata[0].horizon_end_utc"
    )
    horizon_seconds = int((horizon_end - horizon_start).total_seconds())
    if horizon_seconds <= 0 or horizon_seconds % tick_seconds != 0:
        raise ValidationInputError(
            "fixture horizon must be positive and exactly divisible by tick_seconds"
        )

    resource_documents = _unique_by_id(
        _records(package, "resources"), "resource_id", "resources"
    )
    resources: dict[str, int] = {}
    for resource_id, document in resource_documents.items():
        capacity = _integer(document.get("capacity"), f"resources.{resource_id}.capacity")
        if capacity <= 0:
            raise ValidationInputError(f"resources.{resource_id}.capacity must be positive")
        resources[resource_id] = capacity

    operation_documents = _unique_by_id(
        _records(package, "operation_instances"),
        "operation_id",
        "operation_instances",
    )
    operations: dict[str, Operation] = {}
    for operation_id, document in operation_documents.items():
        status = _text(document.get("status"), f"operations.{operation_id}.status")
        if status not in {"NOT_STARTED", "RUNNING", "COMPLETED"}:
            raise ValidationInputError(f"operations.{operation_id}.status is unsupported")
        option_values = _array(
            document.get("resource_options"),
            f"operations.{operation_id}.resource_options",
        )
        if not option_values:
            raise ValidationInputError(
                f"operations.{operation_id}.resource_options must be non-empty"
            )
        options: list[ResourceOption] = []
        seen_options: set[str] = set()
        for option_index, raw_option in enumerate(option_values):
            option = _object(
                raw_option,
                f"operations.{operation_id}.resource_options[{option_index}]",
            )
            resource_id = _text(
                option.get("resource_id"),
                f"operations.{operation_id}.resource_options[{option_index}].resource_id",
            )
            if resource_id in seen_options:
                raise ValidationInputError(
                    f"operations.{operation_id}.resource_options duplicates {resource_id}"
                )
            if resource_id not in resources:
                raise ValidationInputError(
                    f"operations.{operation_id} references unknown resource {resource_id}"
                )
            seen_options.add(resource_id)
            options.append(
                ResourceOption(
                    resource_id=resource_id,
                    duration_seconds=_duration(
                        option.get("final_duration_seconds"),
                        (
                            f"operations.{operation_id}.resource_options"
                            f"[{option_index}].final_duration_seconds"
                        ),
                        positive=True,
                    ),
                )
            )
        operations[operation_id] = Operation(
            operation_id=operation_id,
            status=status,
            release_at=_utc(
                document.get("release_at_utc"),
                f"operations.{operation_id}.release_at_utc",
            ),
            material_ready_at=_utc(
                document.get("material_ready_at_utc"),
                f"operations.{operation_id}.material_ready_at_utc",
            ),
            resource_options=tuple(options),
        )

    edge_documents = _unique_by_id(
        _records(package, "precedence_edges"), "edge_id", "precedence_edges"
    )
    edges: list[PrecedenceEdge] = []
    for edge_id, document in edge_documents.items():
        predecessor = _text(
            document.get("predecessor_operation_id"),
            f"precedence_edges.{edge_id}.predecessor_operation_id",
        )
        successor = _text(
            document.get("successor_operation_id"),
            f"precedence_edges.{edge_id}.successor_operation_id",
        )
        if predecessor not in operations or successor not in operations:
            raise ValidationInputError(f"precedence_edges.{edge_id} has unknown endpoint")
        raw_maximum = document.get("max_lag_seconds")
        maximum = (
            None
            if raw_maximum is None
            else _duration(raw_maximum, f"precedence_edges.{edge_id}.max_lag_seconds")
        )
        minimum = _duration(
            document.get("min_lag_seconds"),
            f"precedence_edges.{edge_id}.min_lag_seconds",
        )
        if maximum is not None and maximum < minimum:
            raise ValidationInputError(
                f"precedence_edges.{edge_id}.max_lag_seconds precedes minimum"
            )
        edges.append(
            PrecedenceEdge(
                edge_id=edge_id,
                predecessor_operation_id=predecessor,
                successor_operation_id=successor,
                min_lag_seconds=minimum,
                max_lag_seconds=maximum,
                transport_lag_seconds=_duration(
                    document.get("transport_lag_seconds"),
                    f"precedence_edges.{edge_id}.transport_lag_seconds",
                ),
                cross_workshop=_boolean(
                    document.get("cross_workshop"),
                    f"precedence_edges.{edge_id}.cross_workshop",
                ),
            )
        )

    unavailable: list[UnavailableInterval] = []
    for index, raw_interval in enumerate(
        _records(package, "resource_unavailable_intervals")
    ):
        interval = _object(raw_interval, f"resource_unavailable_intervals[{index}]")
        resource_id = _text(
            interval.get("resource_id"),
            f"resource_unavailable_intervals[{index}].resource_id",
        )
        if resource_id not in resources:
            raise ValidationInputError(
                f"resource_unavailable_intervals[{index}] has unknown resource"
            )
        start_at = _utc(
            interval.get("start_utc"),
            f"resource_unavailable_intervals[{index}].start_utc",
        )
        end_at = _utc(
            interval.get("end_utc"),
            f"resource_unavailable_intervals[{index}].end_utc",
        )
        if start_at >= end_at:
            raise ValidationInputError(
                f"resource_unavailable_intervals[{index}] must have positive length"
            )
        unavailable.append(UnavailableInterval(resource_id, start_at, end_at))

    facts: list[ExecutionFact] = []
    seen_facts: set[str] = set()
    for index, raw_fact in enumerate(_records(package, "execution_facts")):
        fact = _object(raw_fact, f"execution_facts[{index}]")
        operation_id = _text(
            fact.get("operation_id"), f"execution_facts[{index}].operation_id"
        )
        if operation_id not in operations or operation_id in seen_facts:
            raise ValidationInputError(
                f"execution_facts[{index}] has unknown or duplicate operation"
            )
        seen_facts.add(operation_id)
        status = _text(fact.get("status"), f"execution_facts[{index}].status")
        if status == "COMPLETED":
            facts.append(ExecutionFact(operation_id, "COMPLETED", None, None))
        elif status == "RUNNING":
            resource_id = _text(
                fact.get("resource_id"), f"execution_facts[{index}].resource_id"
            )
            if resource_id not in resources:
                raise ValidationInputError(
                    f"execution_facts[{index}] references unknown resource"
                )
            _utc(
                fact.get("actual_start_at_utc"),
                f"execution_facts[{index}].actual_start_at_utc",
            )
            facts.append(
                ExecutionFact(
                    operation_id,
                    "RUNNING",
                    resource_id,
                    _duration(
                        fact.get("remaining_seconds"),
                        f"execution_facts[{index}].remaining_seconds",
                        positive=True,
                    ),
                )
            )
        else:
            raise ValidationInputError(
                f"execution_facts[{index}].status must be COMPLETED or RUNNING"
            )

    locks: list[Lock] = []
    for index, raw_lock in enumerate(_records(package, "locks")):
        lock = _object(raw_lock, f"locks[{index}]")
        operation_id = _text(lock.get("operation_id"), f"locks[{index}].operation_id")
        resource_id = _text(lock.get("resource_id"), f"locks[{index}].resource_id")
        if operation_id not in operations or resource_id not in resources:
            raise ValidationInputError(f"locks[{index}] has an unknown reference")
        lock_type = _text(lock.get("lock_type"), f"locks[{index}].lock_type")
        if lock_type not in {"HARD_LOCK", "SOFT_LOCK"}:
            raise ValidationInputError(f"locks[{index}].lock_type is unsupported")
        locks.append(
            Lock(
                operation_id=operation_id,
                lock_type=cast(Literal["HARD_LOCK", "SOFT_LOCK"], lock_type),
                resource_id=resource_id,
                start_tick=_integer(lock.get("start_tick"), f"locks[{index}].start_tick"),
                end_tick=_integer(lock.get("end_tick"), f"locks[{index}].end_tick"),
            )
        )

    return FixtureProblem(
        problem_hash=fixture_problem_hash(import_package),
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        tick_seconds=tick_seconds,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        horizon_ticks=horizon_seconds // tick_seconds,
        resources=resources,
        operations=operations,
        edges=tuple(edges),
        unavailable_intervals=tuple(unavailable),
        execution_facts=tuple(facts),
        locks=tuple(locks),
    )


def _parse_assignments(
    candidate_schedule: Mapping[str, object], problem: FixtureProblem
) -> tuple[Assignment, ...]:
    schedule = _object(dict(candidate_schedule), "candidate_schedule")
    if schedule.get("golden_schedule_version") != CANDIDATE_SCHEDULE_CONTRACT:
        raise ValidationInputError(
            f"golden_schedule_version must be {CANDIDATE_SCHEDULE_CONTRACT}"
        )
    scenario = _object(schedule.get("scenario"), "candidate_schedule.scenario")
    if (
        scenario.get("scenario_id") != problem.scenario_id
        or scenario.get("scenario_version") != problem.scenario_version
    ):
        raise ValidationInputError("candidate scenario identity differs from fixture problem")
    if _integer(schedule.get("tick_seconds"), "candidate_schedule.tick_seconds") != problem.tick_seconds:
        raise ValidationInputError("candidate tick_seconds differs from fixture problem")
    if (
        _utc(schedule.get("horizon_start_utc"), "candidate_schedule.horizon_start_utc")
        != problem.horizon_start
        or _utc(schedule.get("horizon_end_utc"), "candidate_schedule.horizon_end_utc")
        != problem.horizon_end
    ):
        raise ValidationInputError("candidate horizon differs from fixture problem")

    assignments: list[Assignment] = []
    for index, raw_assignment in enumerate(
        _array(schedule.get("assignments"), "candidate_schedule.assignments")
    ):
        assignment = _object(raw_assignment, f"candidate_schedule.assignments[{index}]")
        assignments.append(
            Assignment(
                operation_id=_text(
                    assignment.get("operation_id"),
                    f"candidate_schedule.assignments[{index}].operation_id",
                ),
                resource_id=_text(
                    assignment.get("resource_id"),
                    f"candidate_schedule.assignments[{index}].resource_id",
                ),
                start_tick=_integer(
                    assignment.get("start_tick"),
                    f"candidate_schedule.assignments[{index}].start_tick",
                ),
                end_tick=_integer(
                    assignment.get("end_tick"),
                    f"candidate_schedule.assignments[{index}].end_tick",
                ),
                source_index=index,
            )
        )
    return tuple(assignments)


def _json_value(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _violation(
    constraint_id: ConstraintId,
    entity_ids: Sequence[str],
    observed_value: object,
) -> ValidationViolationDocumentV2:
    unique_ids = list(dict.fromkeys(entity_ids))
    if not unique_ids:
        raise AssertionError("a validation violation must identify an entity")
    expected_rule, message = RULE_METADATA[constraint_id]
    return {
        "constraint_id": constraint_id,
        "severity": "HARD",
        "entity_ids": unique_ids,
        "observed_value": _json_value(observed_value),
        "expected_rule": expected_rule,
        "message": message,
    }


def _assignment_groups(
    assignments: Sequence[Assignment],
) -> defaultdict[str, list[Assignment]]:
    groups: defaultdict[str, list[Assignment]] = defaultdict(list)
    for assignment in assignments:
        groups[assignment.operation_id].append(assignment)
    return groups


def _single_assignments(
    groups: Mapping[str, Sequence[Assignment]],
) -> dict[str, Assignment]:
    return {
        operation_id: values[0]
        for operation_id, values in groups.items()
        if len(values) == 1
    }


def _evaluate_c001(
    problem: FixtureProblem,
    assignments: Sequence[Assignment],
    groups: Mapping[str, Sequence[Assignment]],
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    unfinished = {
        operation_id
        for operation_id, operation in problem.operations.items()
        if operation.status in {"NOT_STARTED", "RUNNING"}
    }
    for operation_id in sorted(unfinished):
        selected = groups.get(operation_id, ())
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
    unknown_counts = Counter(
        assignment.operation_id
        for assignment in assignments
        if assignment.operation_id not in problem.operations
    )
    for operation_id in sorted(unknown_counts):
        violations.append(
            _violation(
                "C-001",
                [operation_id],
                {
                    "operation_id": operation_id,
                    "assignment_count": unknown_counts[operation_id],
                    "reason": "operation is absent from fixture problem",
                },
            )
        )
    return violations


def _evaluate_c002(
    problem: FixtureProblem, singles: Mapping[str, Assignment]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for edge in problem.edges:
        predecessor = singles.get(edge.predecessor_operation_id)
        successor = singles.get(edge.successor_operation_id)
        if predecessor is None or successor is None:
            continue
        lag_seconds = (
            successor.start_tick - predecessor.end_tick
        ) * problem.tick_seconds
        if lag_seconds < edge.min_lag_seconds or (
            edge.max_lag_seconds is not None and lag_seconds > edge.max_lag_seconds
        ):
            violations.append(
                _violation(
                    "C-002",
                    [
                        edge.edge_id,
                        edge.predecessor_operation_id,
                        edge.successor_operation_id,
                    ],
                    {
                        "predecessor_end_tick": predecessor.end_tick,
                        "successor_start_tick": successor.start_tick,
                        "lag_seconds": lag_seconds,
                        "min_lag_seconds": edge.min_lag_seconds,
                        "max_lag_seconds": edge.max_lag_seconds,
                    },
                )
            )
    return violations


def _evaluate_c003(
    problem: FixtureProblem, groups: Mapping[str, Sequence[Assignment]]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for operation_id, operation in problem.operations.items():
        selected = groups.get(operation_id, ())
        if not selected:
            continue
        allowed = {option.resource_id for option in operation.resource_options}
        selected_resources = [value.resource_id for value in selected]
        if len(selected) != 1 or selected_resources[0] not in allowed:
            violations.append(
                _violation(
                    "C-003",
                    [operation_id, *selected_resources],
                    {
                        "operation_id": operation_id,
                        "selected_resource_count": len(selected),
                        "selected_resource_ids": selected_resources,
                        "allowed_resource_ids": sorted(allowed),
                    },
                )
            )
    return violations


def _evaluate_c004(
    problem: FixtureProblem, assignments: Sequence[Assignment]
) -> list[ValidationViolationDocumentV2]:
    by_resource: defaultdict[str, list[Assignment]] = defaultdict(list)
    for assignment in assignments:
        if problem.resources.get(assignment.resource_id) == 1:
            by_resource[assignment.resource_id].append(assignment)
    violations: list[ValidationViolationDocumentV2] = []
    for resource_id in sorted(by_resource):
        values = by_resource[resource_id]
        for first, second in combinations(values, 2):
            if first.start_tick < second.end_tick and second.start_tick < first.end_tick:
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
    problem: FixtureProblem, assignments: Sequence[Assignment]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for assignment in assignments:
        start_at = problem.horizon_start + timedelta(
            seconds=assignment.start_tick * problem.tick_seconds
        )
        end_at = problem.horizon_start + timedelta(
            seconds=assignment.end_tick * problem.tick_seconds
        )
        for unavailable in problem.unavailable_intervals:
            if (
                assignment.resource_id == unavailable.resource_id
                and start_at < unavailable.end_at
                and unavailable.start_at < end_at
            ):
                violations.append(
                    _violation(
                        "C-005",
                        [assignment.operation_id, assignment.resource_id],
                        {
                            "assignment_start_utc": format_utc_instant(start_at),
                            "assignment_end_utc": format_utc_instant(end_at),
                            "unavailable_start_utc": format_utc_instant(
                                unavailable.start_at
                            ),
                            "unavailable_end_utc": format_utc_instant(unavailable.end_at),
                        },
                    )
                )
    return violations


def _evaluate_c006(
    problem: FixtureProblem, singles: Mapping[str, Assignment]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for operation_id, operation in problem.operations.items():
        assignment = singles.get(operation_id)
        if assignment is None:
            continue
        start_at = problem.horizon_start + timedelta(
            seconds=assignment.start_tick * problem.tick_seconds
        )
        if start_at < operation.release_at or start_at < operation.material_ready_at:
            violations.append(
                _violation(
                    "C-006",
                    [operation_id],
                    {
                        "assignment_start_utc": format_utc_instant(start_at),
                        "release_at_utc": format_utc_instant(operation.release_at),
                        "material_ready_at_utc": format_utc_instant(
                            operation.material_ready_at
                        ),
                    },
                )
            )
    return violations


def _evaluate_c007(
    problem: FixtureProblem, groups: Mapping[str, Sequence[Assignment]]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for fact in problem.execution_facts:
        selected = groups.get(fact.operation_id, ())
        if fact.status == "COMPLETED" and selected:
            violations.append(
                _violation(
                    "C-007",
                    [fact.operation_id],
                    {
                        "execution_status": fact.status,
                        "assignments": [value.observed_tuple() for value in selected],
                    },
                )
            )
        elif fact.status == "RUNNING":
            if fact.resource_id is None or fact.remaining_seconds is None:
                raise AssertionError("parsed RUNNING fact is incomplete")
            expected_end_tick = duration_to_ticks(
                fact.remaining_seconds, problem.tick_seconds
            )
            matches = (
                len(selected) == 1
                and selected[0].resource_id == fact.resource_id
                and selected[0].start_tick == 0
                and selected[0].end_tick == expected_end_tick
            )
            if not matches:
                violations.append(
                    _violation(
                        "C-007",
                        [fact.operation_id, fact.resource_id],
                        {
                            "execution_status": fact.status,
                            "expected_resource_id": fact.resource_id,
                            "remaining_seconds": fact.remaining_seconds,
                            "expected_start_tick": 0,
                            "expected_end_tick": expected_end_tick,
                            "assignments": [value.observed_tuple() for value in selected],
                        },
                    )
                )
    return violations


def _evaluate_c008(
    problem: FixtureProblem, groups: Mapping[str, Sequence[Assignment]]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for lock in problem.locks:
        if lock.lock_type != "HARD_LOCK":
            continue
        selected = groups.get(lock.operation_id, ())
        matches = (
            len(selected) == 1
            and selected[0].resource_id == lock.resource_id
            and selected[0].start_tick == lock.start_tick
            and selected[0].end_tick == lock.end_tick
        )
        if not matches:
            violations.append(
                _violation(
                    "C-008",
                    [lock.operation_id, lock.resource_id],
                    {
                        "hard_lock": {
                            "resource_id": lock.resource_id,
                            "start_tick": lock.start_tick,
                            "end_tick": lock.end_tick,
                        },
                        "assignments": [value.observed_tuple() for value in selected],
                    },
                )
            )
    return violations


def _evaluate_c009(
    problem: FixtureProblem, singles: Mapping[str, Assignment]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for edge in problem.edges:
        if not edge.cross_workshop:
            continue
        predecessor = singles.get(edge.predecessor_operation_id)
        successor = singles.get(edge.successor_operation_id)
        if predecessor is None or successor is None:
            continue
        observed = (
            successor.start_tick - predecessor.end_tick
        ) * problem.tick_seconds
        if observed < edge.transport_lag_seconds:
            violations.append(
                _violation(
                    "C-009",
                    [
                        edge.edge_id,
                        edge.predecessor_operation_id,
                        edge.successor_operation_id,
                    ],
                    {
                        "predecessor_end_tick": predecessor.end_tick,
                        "successor_start_tick": successor.start_tick,
                        "transport_seconds_observed": observed,
                        "transport_lag_seconds": edge.transport_lag_seconds,
                    },
                )
            )
    return violations


def _evaluate_c010(
    problem: FixtureProblem, singles: Mapping[str, Assignment]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for operation_id, operation in problem.operations.items():
        assignment = singles.get(operation_id)
        if assignment is None:
            continue
        duration_by_resource = {
            option.resource_id: option.duration_seconds
            for option in operation.resource_options
        }
        duration_seconds = duration_by_resource.get(assignment.resource_id)
        if duration_seconds is None:
            continue
        expected_ticks = duration_to_ticks(duration_seconds, problem.tick_seconds)
        observed_ticks = assignment.end_tick - assignment.start_tick
        if observed_ticks != expected_ticks:
            violations.append(
                _violation(
                    "C-010",
                    [operation_id, assignment.resource_id],
                    {
                        "resource_id": assignment.resource_id,
                        "interval_ticks": observed_ticks,
                        "duration_seconds": duration_seconds,
                        "expected_duration_ticks": expected_ticks,
                    },
                )
            )
    return violations


def _evaluate_c011(
    problem: FixtureProblem, assignments: Sequence[Assignment]
) -> list[ValidationViolationDocumentV2]:
    violations: list[ValidationViolationDocumentV2] = []
    for assignment in assignments:
        operation = problem.operations.get(assignment.operation_id)
        if operation is None or operation.status != "NOT_STARTED":
            continue
        if not (
            0 <= assignment.start_tick
            < assignment.end_tick
            <= problem.horizon_ticks
        ):
            violations.append(
                _violation(
                    "C-011",
                    [assignment.operation_id],
                    {
                        "start_tick": assignment.start_tick,
                        "end_tick": assignment.end_tick,
                        "horizon_start_tick": 0,
                        "horizon_end_tick": problem.horizon_ticks,
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


def validate_fixture_schedule(
    import_package: Mapping[str, object], candidate_schedule: Mapping[str, object]
) -> ValidationReportDocumentV2:
    """Return a deterministic ValidationReport v2 for fixture-local input."""

    problem = _parse_problem(import_package)
    assignments = _parse_assignments(candidate_schedule, problem)
    groups = _assignment_groups(assignments)
    singles = _single_assignments(groups)

    violations = [
        *_evaluate_c001(problem, assignments, groups),
        *_evaluate_c002(problem, singles),
        *_evaluate_c003(problem, groups),
        *_evaluate_c004(problem, assignments),
        *_evaluate_c005(problem, assignments),
        *_evaluate_c006(problem, singles),
        *_evaluate_c007(problem, groups),
        *_evaluate_c008(problem, groups),
        *_evaluate_c009(problem, singles),
        *_evaluate_c010(problem, singles),
        *_evaluate_c011(problem, assignments),
    ]
    violations.sort(key=_violation_sort_key)
    violation_count = len(violations)
    return {
        "validation_report_version": VALIDATION_REPORT_CONTRACT,
        "problem_hash": problem.problem_hash,
        "status": "PASS" if violation_count == 0 else "FAIL",
        "hard_violation_count": violation_count,
        "violations": violations,
    }


def validation_error_from_report(
    report: ValidationReportDocumentV2,
) -> ErrorDocumentV2 | None:
    """Map a failed report to the registered Validation Error v2 envelope."""

    if report["status"] == "PASS":
        return None
    details: list[ErrorDetailDocument] = []
    for violation in report["violations"]:
        details.append(
            {
                "entity_id": violation["entity_ids"][0],
                "field": "candidate_schedule",
                "observed_value": _json_value(
                    {
                        "constraint_id": violation["constraint_id"],
                        "entity_ids": violation["entity_ids"],
                        "value": violation["observed_value"],
                    }
                ),
                "expected_contract": violation["expected_rule"],
                "source_location": "candidate.assignments",
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
    "CANDIDATE_SCHEDULE_CONTRACT",
    "FIXTURE_RECORD_CONTRACT",
    "RULE_METADATA",
    "VALIDATION_REPORT_CONTRACT",
    "ValidationInputError",
    "fixture_problem_hash",
    "validate_fixture_schedule",
    "validation_error_from_report",
]
