"""Deterministic non-production reference schedulers and TASK-P2-10 evidence."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from app.domain.contracts import ValidationReportDocumentV2
from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.contracts import (
    OperationAssignmentDocument,
    ProblemReferenceDocument,
)
from app.planning.problem.contracts import (
    DeliveryDemandDocument,
    OperationInstanceDocumentV2,
    OperationLockDocumentV2,
    OperationResourceOptionDocument,
    PlanningProblemDocumentV2,
    PlanningProblemError,
    PrecedenceEdgeDocumentV2,
    ResourceDocumentV2,
    ResourceUnavailableIntervalDocumentV2,
)
from app.planning.problem.hashing import (
    problem_v2_hash_for,
    validate_built_problem_v2,
)
from app.planning.validation.problem_schedule_validator import (
    ProblemScheduleValidationInputError,
    ProblemScheduleValidator,
)
from app.simulation.baselines.contracts import (
    ALGORITHM_IDENTITIES,
    REFERENCE_SCHEDULER_CONTRACT_VERSION,
    REFERENCE_SCHEDULER_POLICY_VERSION,
    REFERENCE_SCHEDULER_REPORT_VERSION,
    REFERENCE_SCHEDULER_RESULT_VERSION,
    ReferenceAlgorithm,
    ReferenceCandidateDocument,
    ReferenceSchedulerFailureDocument,
    ReferenceSchedulerMetricsDocument,
    ReferenceSchedulerResultDocument,
    ReferenceSchedulerStatus,
    algorithm_identity,
)


TASK_ID = "TASK-P2-10"
type JsonObject = dict[str, Any]

_FIXED_FINGERPRINTS = {
    "planning_problem_v2_schema": (
        "schemas/json/planning-problem.v2.schema.json",
        "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    ),
    "planning_solution_schema": (
        "schemas/json/planning-solution.schema.json",
        "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    ),
    "kpi_schema": (
        "schemas/json/kpi.schema.json",
        "be3dfbcd06e9fb7887df699c2ba0fc8bb229d603b0d55a75268a72bc2cdc9426",
    ),
    "validation_report_v2_schema": (
        "schemas/json/validation-report.v2.schema.json",
        "1da63e931e7ddd90134eb652c857f13eb862787de855165cd230c2d8071fd353",
    ),
    "constraint_rule_sheet": (
        "schemas/rules/constraint-rule-sheet.v1.yaml",
        "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2",
    ),
    "problem_contracts": (
        "backend/app/planning/problem/contracts.py",
        "ff9eaf8828e5b019a8ddde886e8bbad05c98981392d7974557e1e23abc914b3a",
    ),
    "planning_contracts": (
        "backend/app/planning/contracts.py",
        "d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630",
    ),
    "formal_validator": (
        "backend/app/planning/validation/problem_schedule_validator.py",
        "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f",
    ),
    "p2_correctness_orchestrator": (
        "backend/app/simulation/scenarios/p2_correctness.py",
        "316aee9cdc3325570916417fe1f85e48e4b0d46ba08fb06e8672ca1cf6b5f3e2",
    ),
    "dependency_lock": (
        "uv.lock",
        "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
    ),
}
_P2_CORRECTNESS_ASSET_DIGEST = (
    "2f1ebe2362d53f193c0edb649f14e4b6673d7f3bd2e61b5f88b282a534d8cadd"
)


@dataclass(frozen=True, slots=True)
class _Endpoint:
    operation_id: str
    resource_id: str
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True, slots=True)
class _Placement:
    operation_id: str
    resource_id: str
    start_tick: int
    end_tick: int
    duration_ticks: int
    duration_seconds: int
    lock_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ScheduleFailure:
    code: str
    message: str
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class _Context:
    problem: PlanningProblemDocumentV2
    horizon_start: datetime
    horizon_end: datetime
    horizon_ticks: int
    tick_seconds: int
    operations: Mapping[str, OperationInstanceDocumentV2]
    demands: Mapping[str, DeliveryDemandDocument]
    resources: Mapping[str, ResourceDocumentV2]
    incoming: Mapping[str, tuple[PrecedenceEdgeDocumentV2, ...]]
    outgoing: Mapping[str, tuple[PrecedenceEdgeDocumentV2, ...]]
    anchors: Mapping[str, _Endpoint]
    locks: Mapping[str, tuple[OperationLockDocumentV2, ...]]
    unavailable: Mapping[str, tuple[ResourceUnavailableIntervalDocumentV2, ...]]


def _exact_seconds(later: datetime, earlier: datetime) -> int:
    delta = later - earlier
    if delta.microseconds:
        raise ValueError("reference scheduler timestamps require exact seconds")
    return delta.days * 86400 + delta.seconds


def _ceil_div(value: int, divisor: int) -> int:
    return -(-value // divisor)


def _context(problem: PlanningProblemDocumentV2) -> _Context:
    horizon_start = parse_utc_instant(problem["horizon_start_utc"])
    horizon_end = parse_utc_instant(problem["horizon_end_utc"])
    horizon_seconds = _exact_seconds(horizon_end, horizon_start)
    tick_seconds = problem["tick_seconds"]
    horizon_ticks = horizon_seconds // tick_seconds
    operations = {
        operation["operation_id"]: operation
        for operation in problem["operation_instances"]
    }
    demands = {
        demand["demand_order_id"]: demand
        for demand in problem["delivery_demands"]
    }
    resources = {
        resource["resource_id"]: resource for resource in problem["resources"]
    }
    incoming_values: defaultdict[str, list[PrecedenceEdgeDocumentV2]] = defaultdict(
        list
    )
    outgoing_values: defaultdict[str, list[PrecedenceEdgeDocumentV2]] = defaultdict(
        list
    )
    for edge in problem["precedence_edges"]:
        incoming_values[edge["successor_operation_id"]].append(edge)
        outgoing_values[edge["predecessor_operation_id"]].append(edge)
    incoming = {
        operation_id: tuple(
            sorted(values, key=lambda item: item["precedence_edge_id"])
        )
        for operation_id, values in incoming_values.items()
    }
    outgoing = {
        operation_id: tuple(
            sorted(values, key=lambda item: item["precedence_edge_id"])
        )
        for operation_id, values in outgoing_values.items()
    }
    anchors = {
        anchor["operation_id"]: _Endpoint(
            operation_id=anchor["operation_id"],
            resource_id=anchor["resource_id"],
            start_at=parse_utc_instant(anchor["actual_start_at_utc"]),
            end_at=parse_utc_instant(anchor["actual_end_at_utc"]),
        )
        for anchor in problem["historical_completion_anchors"]
    }
    lock_values: defaultdict[str, list[OperationLockDocumentV2]] = defaultdict(list)
    for lock in problem["operation_locks"]:
        lock_values[lock["operation_id"]].append(lock)
    locks = {
        operation_id: tuple(sorted(values, key=lambda item: item["lock_id"]))
        for operation_id, values in lock_values.items()
    }
    unavailable_values: defaultdict[
        str, list[ResourceUnavailableIntervalDocumentV2]
    ] = defaultdict(list)
    for interval in problem["resource_unavailable_intervals"]:
        unavailable_values[interval["resource_id"]].append(interval)
    unavailable = {
        resource_id: tuple(
            sorted(values, key=lambda item: (item["start_utc"], item["end_utc"]))
        )
        for resource_id, values in unavailable_values.items()
    }
    return _Context(
        problem=problem,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        horizon_ticks=horizon_ticks,
        tick_seconds=tick_seconds,
        operations=operations,
        demands=demands,
        resources=resources,
        incoming=incoming,
        outgoing=outgoing,
        anchors=anchors,
        locks=locks,
        unavailable=unavailable,
    )


def _option_for(
    operation: OperationInstanceDocumentV2, resource_id: str
) -> OperationResourceOptionDocument | None:
    return next(
        (
            option
            for option in operation["resource_options"]
            if option["resource_id"] == resource_id
        ),
        None,
    )


def _endpoint(context: _Context, placement: _Placement) -> _Endpoint:
    return _Endpoint(
        operation_id=placement.operation_id,
        resource_id=placement.resource_id,
        start_at=context.horizon_start
        + timedelta(seconds=placement.start_tick * context.tick_seconds),
        end_at=context.horizon_start
        + timedelta(seconds=placement.end_tick * context.tick_seconds),
    )


def _known_endpoints(
    context: _Context, placements: Mapping[str, _Placement]
) -> dict[str, _Endpoint]:
    values = dict(context.anchors)
    values.update(
        {
            operation_id: _endpoint(context, placement)
            for operation_id, placement in placements.items()
        }
    )
    return values


def _edge_is_satisfied(
    context: _Context,
    edge: PrecedenceEdgeDocumentV2,
    predecessor: _Endpoint,
    successor: _Endpoint,
) -> bool:
    lag_seconds = _exact_seconds(successor.start_at, predecessor.end_at)
    if lag_seconds < edge["min_lag_seconds"]:
        return False
    maximum = edge.get("max_lag_seconds")
    if maximum is not None and lag_seconds > maximum:
        return False
    predecessor_workshop = context.resources[predecessor.resource_id]["workshop_id"]
    successor_workshop = context.resources[successor.resource_id]["workshop_id"]
    return not (
        predecessor_workshop != successor_workshop
        and lag_seconds < edge["transport_lag_seconds"]
    )


def _resource_is_free(
    context: _Context,
    placement: _Placement,
    placements: Mapping[str, _Placement],
) -> bool:
    start_at = context.horizon_start + timedelta(
        seconds=placement.start_tick * context.tick_seconds
    )
    end_at = context.horizon_start + timedelta(
        seconds=placement.end_tick * context.tick_seconds
    )
    for existing in placements.values():
        if existing.resource_id != placement.resource_id:
            continue
        if placement.start_tick < existing.end_tick and existing.start_tick < placement.end_tick:
            return False
    for interval in context.unavailable.get(placement.resource_id, ()):
        unavailable_start = parse_utc_instant(interval["start_utc"])
        unavailable_end = parse_utc_instant(interval["end_utc"])
        if start_at < unavailable_end and unavailable_start < end_at:
            return False
    return True


def _placement_is_feasible(
    context: _Context,
    operation: OperationInstanceDocumentV2,
    placement: _Placement,
    placements: Mapping[str, _Placement],
) -> bool:
    if (
        placement.start_tick < 0
        or placement.end_tick <= placement.start_tick
        or placement.end_tick > context.horizon_ticks
    ):
        return False
    option = _option_for(operation, placement.resource_id)
    if option is None:
        return False
    expected_seconds = (
        cast(int, operation.get("remaining_seconds"))
        if operation["status"] == "RUNNING"
        else option["final_duration_seconds"]
    )
    if (
        placement.duration_seconds != expected_seconds
        or placement.duration_ticks != _ceil_div(expected_seconds, context.tick_seconds)
        or placement.end_tick - placement.start_tick != placement.duration_ticks
    ):
        return False
    candidate = _endpoint(context, placement)
    if candidate.start_at < parse_utc_instant(operation["release_at_utc"]):
        return False
    if candidate.start_at < parse_utc_instant(operation["material_ready_at_utc"]):
        return False
    if not _resource_is_free(context, placement, placements):
        return False
    endpoints = _known_endpoints(context, placements)
    for edge in context.incoming.get(operation["operation_id"], ()):
        predecessor = endpoints.get(edge["predecessor_operation_id"])
        if predecessor is not None and not _edge_is_satisfied(
            context, edge, predecessor, candidate
        ):
            return False
    for edge in context.outgoing.get(operation["operation_id"], ()):
        successor = endpoints.get(edge["successor_operation_id"])
        if successor is not None and not _edge_is_satisfied(
            context, edge, candidate, successor
        ):
            return False
    return True


def _fixed_placements(
    context: _Context,
) -> tuple[dict[str, _Placement], _ScheduleFailure | None]:
    placements: dict[str, _Placement] = {}
    for operation_id in sorted(context.operations):
        operation = context.operations[operation_id]
        operation_locks = context.locks.get(operation_id, ())
        hard_locks = tuple(
            lock for lock in operation_locks if lock["lock_type"] == "HARD_LOCK"
        )
        placement: _Placement | None = None
        if operation["status"] == "RUNNING":
            duration_seconds = cast(int, operation.get("remaining_seconds"))
            duration_ticks = _ceil_div(duration_seconds, context.tick_seconds)
            placement = _Placement(
                operation_id=operation_id,
                resource_id=cast(str, operation.get("assigned_resource_id")),
                start_tick=0,
                end_tick=duration_ticks,
                duration_ticks=duration_ticks,
                duration_seconds=duration_seconds,
                lock_ids=tuple(lock["lock_id"] for lock in operation_locks),
            )
        if hard_locks:
            signatures = {
                (lock["resource_id"], lock["start_at_utc"], lock["end_at_utc"])
                for lock in hard_locks
            }
            if len(signatures) != 1:
                return {}, _ScheduleFailure(
                    code="FIXED_ASSIGNMENT_CONFLICT",
                    message="operation has incompatible HARD_LOCK facts",
                    operation_id=operation_id,
                )
            resource_id, start_text, end_text = next(iter(signatures))
            start_seconds = _exact_seconds(
                parse_utc_instant(start_text), context.horizon_start
            )
            end_seconds = _exact_seconds(
                parse_utc_instant(end_text), context.horizon_start
            )
            if (
                start_seconds % context.tick_seconds
                or end_seconds % context.tick_seconds
            ):
                return {}, _ScheduleFailure(
                    code="FIXED_ASSIGNMENT_OFF_GRID",
                    message="HARD_LOCK does not align to the authoritative tick grid",
                    operation_id=operation_id,
                )
            option = _option_for(operation, resource_id)
            if option is None:
                return {}, _ScheduleFailure(
                    code="FIXED_RESOURCE_NOT_ALLOWED",
                    message="HARD_LOCK resource is not an operation candidate",
                    operation_id=operation_id,
                )
            duration_seconds = (
                cast(int, operation.get("remaining_seconds"))
                if operation["status"] == "RUNNING"
                else option["final_duration_seconds"]
            )
            locked = _Placement(
                operation_id=operation_id,
                resource_id=resource_id,
                start_tick=start_seconds // context.tick_seconds,
                end_tick=end_seconds // context.tick_seconds,
                duration_ticks=_ceil_div(duration_seconds, context.tick_seconds),
                duration_seconds=duration_seconds,
                lock_ids=tuple(lock["lock_id"] for lock in operation_locks),
            )
            if placement is not None and placement != locked:
                return {}, _ScheduleFailure(
                    code="FIXED_ASSIGNMENT_CONFLICT",
                    message="RUNNING remainder and HARD_LOCK facts are incompatible",
                    operation_id=operation_id,
                )
            placement = locked
        if placement is not None:
            if not _placement_is_feasible(context, operation, placement, placements):
                return {}, _ScheduleFailure(
                    code="FIXED_ASSIGNMENT_VIOLATION",
                    message="authoritative fixed assignment violates the hard domain",
                    operation_id=operation_id,
                )
            placements[operation_id] = placement

    endpoints = _known_endpoints(context, placements)
    for edge in context.problem["precedence_edges"]:
        predecessor = endpoints.get(edge["predecessor_operation_id"])
        successor = endpoints.get(edge["successor_operation_id"])
        if (
            predecessor is not None
            and successor is not None
            and not _edge_is_satisfied(context, edge, predecessor, successor)
        ):
            return {}, _ScheduleFailure(
                code="FIXED_PRECEDENCE_VIOLATION",
                message="fixed endpoints violate precedence or transport lag",
                operation_id=edge["successor_operation_id"],
            )
    return placements, None


def _placement_key(placement: _Placement) -> tuple[int, int, int, str]:
    return (
        placement.end_tick,
        placement.start_tick,
        placement.duration_ticks,
        placement.resource_id,
    )


def _earliest_placement(
    context: _Context,
    operation: OperationInstanceDocumentV2,
    placements: Mapping[str, _Placement],
) -> _Placement | None:
    operation_id = operation["operation_id"]
    operation_locks = context.locks.get(operation_id, ())
    lock_ids = tuple(lock["lock_id"] for lock in operation_locks)
    endpoints = _known_endpoints(context, placements)
    values: list[_Placement] = []
    for option in operation["resource_options"]:
        duration_seconds = option["final_duration_seconds"]
        duration_ticks = _ceil_div(duration_seconds, context.tick_seconds)
        lower = max(
            0,
            _ceil_div(
                _exact_seconds(
                    parse_utc_instant(operation["release_at_utc"]),
                    context.horizon_start,
                ),
                context.tick_seconds,
            ),
            _ceil_div(
                _exact_seconds(
                    parse_utc_instant(operation["material_ready_at_utc"]),
                    context.horizon_start,
                ),
                context.tick_seconds,
            ),
        )
        for edge in context.incoming.get(operation_id, ()):
            predecessor = endpoints.get(edge["predecessor_operation_id"])
            if predecessor is None:
                continue
            transport = 0
            if (
                context.resources[predecessor.resource_id]["workshop_id"]
                != context.resources[option["resource_id"]]["workshop_id"]
            ):
                transport = edge["transport_lag_seconds"]
            required = max(edge["min_lag_seconds"], transport)
            lower = max(
                lower,
                _ceil_div(
                    _exact_seconds(predecessor.end_at, context.horizon_start)
                    + required,
                    context.tick_seconds,
                ),
            )
        upper = context.horizon_ticks - duration_ticks
        for start_tick in range(lower, upper + 1):
            candidate = _Placement(
                operation_id=operation_id,
                resource_id=option["resource_id"],
                start_tick=start_tick,
                end_tick=start_tick + duration_ticks,
                duration_ticks=duration_ticks,
                duration_seconds=duration_seconds,
                lock_ids=lock_ids,
            )
            if _placement_is_feasible(context, operation, candidate, placements):
                values.append(candidate)
                break
    return min(values, key=_placement_key) if values else None


def _operation_key(
    context: _Context,
    operation: OperationInstanceDocumentV2,
    algorithm: ReferenceAlgorithm,
) -> tuple[object, ...]:
    demand = context.demands[operation["demand_order_id"]]
    release = parse_utc_instant(operation["release_at_utc"])
    due = parse_utc_instant(demand["due_at_utc"])
    operation_id = operation["operation_id"]
    if algorithm is ReferenceAlgorithm.FCFS:
        return (release, operation["demand_order_id"], operation_id)
    if algorithm is ReferenceAlgorithm.EDD:
        return (due, release, operation["demand_order_id"], operation_id)
    if algorithm is ReferenceAlgorithm.SPT:
        minimum_duration = min(
            option["final_duration_seconds"]
            for option in operation["resource_options"]
        )
        return (minimum_duration, due, operation_id)
    if algorithm is ReferenceAlgorithm.PRIORITY_EDD:
        return (
            -demand["priority_weight"],
            due,
            release,
            operation["demand_order_id"],
            operation_id,
        )
    raise ValueError("operation priority key is not used by this algorithm")


def _ready_operations(
    context: _Context,
    unscheduled: set[str],
    placements: Mapping[str, _Placement],
) -> list[OperationInstanceDocumentV2]:
    endpoints = set(context.anchors) | set(placements)
    values = []
    for operation_id in sorted(unscheduled):
        incoming = context.incoming.get(operation_id, ())
        if all(edge["predecessor_operation_id"] in endpoints for edge in incoming):
            values.append(context.operations[operation_id])
    return values


def _build_schedule(
    context: _Context, algorithm: ReferenceAlgorithm
) -> tuple[ReferenceCandidateDocument | None, _ScheduleFailure | None]:
    placements, failure = _fixed_placements(context)
    if failure is not None:
        return None, failure
    unscheduled = set(context.operations) - set(placements)
    while unscheduled:
        ready = _ready_operations(context, unscheduled, placements)
        if not ready:
            return None, _ScheduleFailure(
                code="NO_READY_OPERATION",
                message="no deterministic ready operation remains",
            )
        if algorithm is ReferenceAlgorithm.GREEDY_EARLIEST_AVAILABLE_MACHINE:
            choices: list[tuple[tuple[int, int, int, str, str], _Placement]] = []
            for operation in ready:
                placement = _earliest_placement(context, operation, placements)
                if placement is None:
                    return None, _ScheduleFailure(
                        code="NO_HARD_FEASIBLE_PLACEMENT",
                        message="ready operation has no hard-feasible placement",
                        operation_id=operation["operation_id"],
                    )
                choices.append(
                    (
                        (*_placement_key(placement), operation["operation_id"]),
                        placement,
                    )
                )
            selected = min(choices, key=lambda item: item[0])[1]
        else:
            operation = min(
                ready,
                key=lambda item: _operation_key(context, item, algorithm),
            )
            placement = _earliest_placement(context, operation, placements)
            if placement is None:
                return None, _ScheduleFailure(
                    code="NO_HARD_FEASIBLE_PLACEMENT",
                    message="selected ready operation has no hard-feasible placement",
                    operation_id=operation["operation_id"],
                )
            selected = placement
        placements[selected.operation_id] = selected
        unscheduled.remove(selected.operation_id)

    assignments = [
        _assignment_document(context, placements[operation_id])
        for operation_id in sorted(placements)
    ]
    return {
        "problem": _problem_reference(context.problem),
        "assignments": assignments,
    }, None


def _problem_reference(problem: PlanningProblemDocumentV2) -> ProblemReferenceDocument:
    return {
        "problem_version": problem["problem_version"],
        "problem_builder_version": problem["problem_builder_version"],
        "problem_hash_projection_version": problem[
            "problem_hash_projection_version"
        ],
        "problem_hash": problem["problem_hash"],
        "snapshot_id": problem["snapshot_id"],
        "tick_seconds": problem["tick_seconds"],
        "horizon_start_utc": problem["horizon_start_utc"],
        "horizon_end_utc": problem["horizon_end_utc"],
    }


def _assignment_document(
    context: _Context, placement: _Placement
) -> OperationAssignmentDocument:
    start_at = context.horizon_start + timedelta(
        seconds=placement.start_tick * context.tick_seconds
    )
    end_at = context.horizon_start + timedelta(
        seconds=placement.end_tick * context.tick_seconds
    )
    return {
        "operation_id": placement.operation_id,
        "resource_id": placement.resource_id,
        "start_tick": placement.start_tick,
        "end_tick": placement.end_tick,
        "duration_ticks": placement.duration_ticks,
        "start_at_utc": format_utc_instant(start_at),
        "end_at_utc": format_utc_instant(end_at),
        "duration_seconds": placement.duration_seconds,
        "lock_ids": list(placement.lock_ids),
        "execution_fact_ids": [],
    }


def _quality_metrics(
    context: _Context, candidate: ReferenceCandidateDocument
) -> tuple[int, int]:
    completion_by_demand: defaultdict[str, list[int]] = defaultdict(list)
    for assignment in candidate["assignments"]:
        operation = context.operations[assignment["operation_id"]]
        completion_by_demand[operation["demand_order_id"]].append(
            assignment["end_tick"]
        )
    weighted_tardiness = 0
    for demand_id in sorted(context.demands):
        demand = context.demands[demand_id]
        due_offset_seconds = _exact_seconds(
            parse_utc_instant(demand["due_at_utc"]), context.horizon_start
        )
        completion_tick = max(completion_by_demand[demand_id])
        tardiness_seconds = max(
            0,
            completion_tick * context.tick_seconds - due_offset_seconds,
        )
        weighted_tardiness += demand["priority_weight"] * tardiness_seconds
    makespan_seconds = (
        max(assignment["end_tick"] for assignment in candidate["assignments"])
        * context.tick_seconds
        if candidate["assignments"]
        else 0
    )
    return weighted_tardiness, makespan_seconds


def _runtime(started: float) -> float:
    return max(round(perf_counter() - started, 9), 0.000000001)


def _failure_document(failure: _ScheduleFailure) -> ReferenceSchedulerFailureDocument:
    document: ReferenceSchedulerFailureDocument = {
        "code": failure.code,
        "message": failure.message,
    }
    if failure.operation_id is not None:
        document["operation_id"] = failure.operation_id
    return document


def _result(
    *,
    algorithm: ReferenceAlgorithm,
    problem_hash: str,
    status: ReferenceSchedulerStatus,
    runtime_seconds: float,
    operation_count: int,
    candidate: ReferenceCandidateDocument | None = None,
    validation_report: ValidationReportDocumentV2 | None = None,
    weighted_tardiness_seconds: int | None = None,
    makespan_seconds: int | None = None,
    failure: ReferenceSchedulerFailureDocument | None = None,
) -> ReferenceSchedulerResultDocument:
    metrics: ReferenceSchedulerMetricsDocument = {
        "weighted_tardiness_seconds": weighted_tardiness_seconds,
        "makespan_seconds": makespan_seconds,
        "runtime_seconds": runtime_seconds,
        "scheduled_operation_count": operation_count if candidate is not None else 0,
        "unscheduled_operation_count": 0 if candidate is not None else operation_count,
    }
    return {
        "reference_scheduler_result_version": REFERENCE_SCHEDULER_RESULT_VERSION,
        "reference_scheduler_contract_version": REFERENCE_SCHEDULER_CONTRACT_VERSION,
        "reference_scheduler_policy_version": REFERENCE_SCHEDULER_POLICY_VERSION,
        "algorithm": algorithm,
        "algorithm_id": algorithm_identity(algorithm).algorithm_id,
        "status": status,
        "problem_hash": problem_hash,
        "non_production": True,
        "optimality_claim": "NONE",
        "candidate": candidate,
        "validation_report": validation_report,
        "metrics": metrics,
        "failure": failure,
    }


def schedule_reference(
    problem: PlanningProblemDocumentV2,
    algorithm: ReferenceAlgorithm | str,
) -> ReferenceSchedulerResultDocument:
    """Build one complete deterministic candidate or return an explicit failure."""

    selected = ReferenceAlgorithm(algorithm)
    started = perf_counter()
    problem_hash = str(problem.get("problem_hash", ""))
    operation_count = len(problem.get("operation_instances", []))
    try:
        validate_built_problem_v2(cast(Mapping[str, object], problem))
        expected_hash = problem_v2_hash_for(cast(Mapping[str, object], problem))
        if problem_hash != expected_hash:
            raise ValueError("PlanningProblem content hash does not match its facts")
        context = _context(problem)
    except (KeyError, TypeError, ValueError, PlanningProblemError) as error:
        return _result(
            algorithm=selected,
            problem_hash=problem_hash,
            status=ReferenceSchedulerStatus.INVALID_PROBLEM,
            runtime_seconds=_runtime(started),
            operation_count=operation_count,
            failure={
                "code": "INVALID_PROBLEM",
                "message": str(error),
            },
        )

    candidate, schedule_failure = _build_schedule(context, selected)
    if schedule_failure is not None:
        return _result(
            algorithm=selected,
            problem_hash=problem_hash,
            status=ReferenceSchedulerStatus.HEURISTIC_FAILURE,
            runtime_seconds=_runtime(started),
            operation_count=operation_count,
            failure=_failure_document(schedule_failure),
        )
    assert candidate is not None
    try:
        validation_report = ProblemScheduleValidator().validate(
            cast(Mapping[str, object], problem),
            cast(Mapping[str, object], candidate),
        )
    except ProblemScheduleValidationInputError as error:
        return _result(
            algorithm=selected,
            problem_hash=problem_hash,
            status=ReferenceSchedulerStatus.INVALID_PROBLEM,
            runtime_seconds=_runtime(started),
            operation_count=operation_count,
            failure={
                "code": "INVALID_PROBLEM",
                "message": str(error),
            },
        )
    if validation_report["status"] != "PASS":
        return _result(
            algorithm=selected,
            problem_hash=problem_hash,
            status=ReferenceSchedulerStatus.VALIDATION_FAILED,
            runtime_seconds=_runtime(started),
            operation_count=operation_count,
            validation_report=validation_report,
            failure={
                "code": "FORMAL_VALIDATION_FAILED",
                "message": "candidate was discarded after formal Validator failure",
            },
        )
    weighted_tardiness, makespan = _quality_metrics(context, candidate)
    return _result(
        algorithm=selected,
        problem_hash=problem_hash,
        status=ReferenceSchedulerStatus.FEASIBLE,
        runtime_seconds=_runtime(started),
        operation_count=operation_count,
        candidate=candidate,
        validation_report=validation_report,
        weighted_tardiness_seconds=weighted_tardiness,
        makespan_seconds=makespan,
    )


def schedule_all_references(
    problem: PlanningProblemDocumentV2,
) -> tuple[ReferenceSchedulerResultDocument, ...]:
    """Run the five registered algorithms in stable identity order."""

    return tuple(schedule_reference(problem, algorithm) for algorithm in ReferenceAlgorithm)


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _fingerprints(root: Path) -> JsonObject:
    values: JsonObject = {}
    for name, (relative, expected) in _FIXED_FINGERPRINTS.items():
        observed = sha256((root / relative).read_bytes()).hexdigest()
        if observed != expected:
            raise ValueError(f"frozen artifact changed: {relative}")
        values[name] = {"path": relative, "sha256": observed}
    return values


def _asset_fingerprint(root: Path, paths: Sequence[Path]) -> tuple[str, list[JsonObject]]:
    rows = [
        {
            "path": path.resolve().relative_to(root).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted({path.resolve() for path in paths})
    ]
    payload = "\n".join(f"{row['path']} {row['sha256']}" for row in rows).encode()
    observed = sha256(payload).hexdigest()
    if observed != _P2_CORRECTNESS_ASSET_DIGEST:
        raise ValueError("frozen P2 correctness asset set changed")
    return observed, rows


def _stable_result_projection(result: ReferenceSchedulerResultDocument) -> JsonObject:
    return {
        "algorithm": result["algorithm"],
        "algorithm_id": result["algorithm_id"],
        "status": result["status"],
        "problem_hash": result["problem_hash"],
        "candidate": result["candidate"],
        "validation_report": result["validation_report"],
        "metrics": {
            key: value
            for key, value in result["metrics"].items()
            if key != "runtime_seconds"
        },
        "failure": result["failure"],
    }


def _candidate_fingerprint(candidate: ReferenceCandidateDocument) -> str:
    payload = json.dumps(
        candidate,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _blocked_calendar_problem(
    problem: PlanningProblemDocumentV2,
) -> PlanningProblemDocumentV2:
    blocked = deepcopy(problem)
    resource = blocked["resources"][0]
    blocked["resource_unavailable_intervals"] = [
        {
            "calendar_id": resource["calendar_id"],
            "resource_id": resource["resource_id"],
            "start_utc": blocked["horizon_start_utc"],
            "end_utc": blocked["horizon_end_utc"],
        }
    ]
    blocked["problem_hash"] = problem_v2_hash_for(
        cast(Mapping[str, object], blocked)
    )
    return blocked


def run_reference_checks(root: Path) -> JsonObject:
    """Run fixed identity, feasibility, determinism, failure, and boundary checks."""

    root = root.resolve()
    fingerprints = _fingerprints(root)

    # The P2-09 orchestrator is used only as the frozen authoritative Problem
    # provider for evidence.  Reference scheduling never reads its solve result.
    from app.simulation.scenarios.p2_correctness import (
        execute_correctness_case,
        load_correctness_cases,
    )

    cases = load_correctness_cases(root)
    asset_paths = tuple(path for case in cases for path in case.asset_paths)
    asset_digest, asset_rows = _asset_fingerprint(root, asset_paths)
    scenario_results: list[JsonObject] = []
    problem_hashes: list[JsonObject] = []
    validator_passes = 0
    deterministic_replays = 0
    candidate_count = 0
    calendar_problem: PlanningProblemDocumentV2 | None = None
    for case in cases:
        replay = execute_correctness_case(case, root=root)
        problem = cast(PlanningProblemDocumentV2, replay.problem)
        if case.scenario_id == "P2-CALENDAR":
            calendar_problem = problem
        problem_hashes.append(
            {"scenario_id": case.scenario_id, "problem_hash": problem["problem_hash"]}
        )
        for algorithm in ReferenceAlgorithm:
            first = schedule_reference(problem, algorithm)
            second = schedule_reference(problem, algorithm)
            if first["status"] is not ReferenceSchedulerStatus.FEASIBLE:
                raise ValueError(
                    f"{case.scenario_id}/{algorithm.value} was not reference-feasible"
                )
            if _stable_result_projection(first) != _stable_result_projection(second):
                raise ValueError(
                    f"{case.scenario_id}/{algorithm.value} is not deterministic"
                )
            deterministic_replays += 1
            candidate = first["candidate"]
            if candidate is None or len(candidate["assignments"]) != len(
                problem["operation_instances"]
            ):
                raise ValueError("reference scheduler exposed a partial candidate")
            fresh_report = ProblemScheduleValidator().validate(
                cast(Mapping[str, object], problem),
                cast(Mapping[str, object], candidate),
            )
            if fresh_report["status"] != "PASS":
                raise ValueError("fresh formal Validator rejected a reference candidate")
            validator_passes += 1
            candidate_count += 1
            scenario_results.append(
                {
                    "scenario_id": case.scenario_id,
                    "problem_hash": problem["problem_hash"],
                    "algorithm": algorithm,
                    "algorithm_id": first["algorithm_id"],
                    "status": first["status"],
                    "candidate_fingerprint": _candidate_fingerprint(candidate),
                    "assignment_count": len(candidate["assignments"]),
                    "validation_status": fresh_report["status"],
                    "hard_violation_count": fresh_report["hard_violation_count"],
                    "metrics": first["metrics"],
                }
            )
    if calendar_problem is None:
        raise ValueError("P2-CALENDAR authoritative Problem is missing")
    blocked = _blocked_calendar_problem(calendar_problem)
    failure_results = schedule_all_references(blocked)
    for result in failure_results:
        if (
            result["status"] is not ReferenceSchedulerStatus.HEURISTIC_FAILURE
            or result["candidate"] is not None
            or result["metrics"]["scheduled_operation_count"] != 0
        ):
            raise ValueError("explicit heuristic failure leaked a partial candidate")

    identities = [
        {
            "algorithm": identity.algorithm,
            "algorithm_id": identity.algorithm_id,
            "operation_selection": list(identity.operation_selection),
            "resource_selection": list(identity.resource_selection),
        }
        for identity in ALGORITHM_IDENTITIES.values()
    ]
    checks = [
        _pass(
            "frozen-problem-solution-kpi-validator-rule-correctness-and-lock",
            {
                "fingerprints": fingerprints,
                "asset_count": len(asset_rows),
                "asset_digest": asset_digest,
            },
        ),
        _pass(
            "five-versioned-algorithm-identities-and-exact-tie-breaks",
            identities,
        ),
        _pass(
            "seven-authoritative-p2-correctness-problems",
            problem_hashes,
        ),
        _pass(
            "complete-candidates-across-all-reference-algorithms",
            {
                "candidate_count": candidate_count,
                "partial_candidate_count": 0,
            },
        ),
        _pass(
            "fresh-formal-validator-and-shared-kpi-measurement",
            {
                "validator_passes": validator_passes,
                "metric_names": [
                    "weighted_tardiness_seconds",
                    "makespan_seconds",
                    "runtime_seconds",
                ],
            },
        ),
        _pass(
            "deterministic-replay-and-explicit-heuristic-failure",
            {
                "deterministic_replays": deterministic_replays,
                "heuristic_failures": len(failure_results),
                "failure_candidate_count": 0,
                "infeasibility_certificate_claims": 0,
            },
        ),
        _pass(
            "non-production-and-comparison-boundary",
            {
                "production_fallback": "PROHIBITED",
                "optimality_claim": "NONE",
                "global_comparison": "DEFERRED_TO_TASK_P2_12",
                "xs_s_m_profiles": "NOT_STARTED",
                "benchmark_thresholds": "NOT_STARTED",
            },
        ),
    ]
    return {
        "report_version": REFERENCE_SCHEDULER_REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "contract_version": REFERENCE_SCHEDULER_CONTRACT_VERSION,
        "policy_version": REFERENCE_SCHEDULER_POLICY_VERSION,
        "check_count": len(checks),
        "counts": {
            "algorithms": len(ReferenceAlgorithm),
            "scenario_cases": len(cases),
            "complete_candidates": candidate_count,
            "independent_validator_passes": validator_passes,
            "deterministic_replays": deterministic_replays,
            "heuristic_failure_cases": len(failure_results),
        },
        "algorithms": identities,
        "scenario_results": scenario_results,
        "checks": checks,
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "problem_contract": "PLANNING_PROBLEM_V2_UNCHANGED",
            "hard_constraints": "C_001_THROUGH_C_011_FORMAL_VALIDATOR",
            "candidate_policy": "COMPLETE_OR_DISCARDED",
            "random_or_partial_schedule": "PROHIBITED",
            "heuristic_failure_is_infeasibility_certificate": False,
            "production_fallback": "PROHIBITED",
            "global_comparison": "DEFERRED_TO_TASK_P2_12",
            "benchmark_profiles_thresholds": "NOT_STARTED",
            "p2_11_plus_or_p3": "NOT_STARTED",
        },
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_reference_checks(args.root)
    _write_report(args.report, report)
    print(
        f"PASS {TASK_ID}: algorithms={report['counts']['algorithms']} "
        f"scenarios={report['counts']['scenario_cases']} "
        f"candidates={report['counts']['complete_candidates']} "
        f"checks={report['check_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TASK_ID",
    "main",
    "run_reference_checks",
    "schedule_all_references",
    "schedule_reference",
]
