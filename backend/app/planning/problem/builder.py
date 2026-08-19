"""Build solver-neutral PlanningProblem v1 values from immutable Snapshot v2."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import NoReturn, cast

from app.domain.capabilities import CapabilityName, require_v1_capability_contract
from app.domain.canonical_records import PlanningSnapshotDocumentV2
from app.domain.types import (
    ContractValueError,
    duration_to_ticks,
    format_utc_instant,
    parse_utc_instant,
    require_tick_seconds,
)
from app.snapshots import ImmutablePlanningSnapshot, SnapshotError, verify_snapshot

from .contracts import (
    ImmutablePlanningProblem,
    PlanningProblemDocument,
    PlanningProblemError,
    PlanningProblemErrorCode,
)
from .hashing import (
    PLANNING_PROBLEM_VERSION,
    PROBLEM_BUILDER_VERSION,
    canonical_problem_bytes,
    canonical_problem_document,
    problem_hash_for,
    validate_built_problem,
    verify_problem,
)


def _reject(
    code: PlanningProblemErrorCode,
    *,
    field: str,
    entity_id: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise PlanningProblemError(
        code,
        field=field,
        entity_id=entity_id,
        expected_contract=expected_contract,
        message=message,
    )


def _second_precision_utc(value: str, field: str, snapshot_id: str) -> datetime:
    try:
        parsed = parse_utc_instant(value)
        if format_utc_instant(parsed) != value:
            raise ContractValueError("timestamp must use second precision")
    except (ContractValueError, TypeError) as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.INVALID_BUILD_CONFIG,
            field=field,
            entity_id=snapshot_id,
            expected_contract="second-precision RFC 3339 UTC instant ending in Z",
            message="Planning horizon instant is invalid",
        ) from error
    return parsed


def _validate_config(
    snapshot_document: PlanningSnapshotDocumentV2,
    *,
    problem_builder_version: str,
    tick_seconds: int,
    horizon_start_utc: str,
    horizon_end_utc: str,
) -> tuple[int, datetime, datetime]:
    snapshot_id = snapshot_document["snapshot_id"]
    if problem_builder_version != PROBLEM_BUILDER_VERSION:
        _reject(
            PlanningProblemErrorCode.INVALID_BUILDER_VERSION,
            field="problem_builder_version",
            entity_id=snapshot_id,
            expected_contract=PROBLEM_BUILDER_VERSION,
            message="Builder semantics cannot be relabelled with another version",
        )
    try:
        tick = int(require_tick_seconds(tick_seconds))
    except (ContractValueError, TypeError) as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.INVALID_BUILD_CONFIG,
            field="tick_seconds",
            entity_id=snapshot_id,
            expected_contract="positive integer solver tick",
            message="Planning tick is invalid",
        ) from error
    horizon_start = _second_precision_utc(
        horizon_start_utc, "horizon_start_utc", snapshot_id
    )
    horizon_end = _second_precision_utc(
        horizon_end_utc, "horizon_end_utc", snapshot_id
    )
    if horizon_start_utc != snapshot_document["cutoff_at_utc"]:
        _reject(
            PlanningProblemErrorCode.INVALID_BUILD_CONFIG,
            field="horizon_start_utc",
            entity_id=snapshot_id,
            expected_contract="horizon start exactly equal to Snapshot cutoff",
            message="Problem cannot skip or replay time outside its Snapshot boundary",
        )
    if horizon_start >= horizon_end:
        _reject(
            PlanningProblemErrorCode.INVALID_BUILD_CONFIG,
            field="horizon_end_utc",
            entity_id=snapshot_id,
            expected_contract="horizon end strictly after horizon start",
            message="Planning horizon is empty or reversed",
        )
    return tick, horizon_start, horizon_end


def _project_options(instance: Mapping[str, object]) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for option in cast(list[Mapping[str, object]], instance["resource_options"]):
        options.append(
            {
                "resource_id": option["resource_id"],
                "setup_seconds": option["setup_seconds"],
                "cycle_seconds_per_unit": option["cycle_seconds_per_unit"],
                "final_duration_seconds": option["final_duration_seconds"],
                "duration_source": option["duration_source"],
                "source_version": option["source_version"],
            }
        )
    return options


def _reject_overlapping_locks(
    instance: Mapping[str, object],
    locks_by_id: Mapping[str, Mapping[str, object]],
    *,
    horizon_start: datetime,
    horizon_end: datetime,
) -> None:
    operation_id = str(instance["operation_instance_id"])
    for lock_id in cast(list[str], instance["lock_ids"]):
        lock = locks_by_id.get(lock_id)
        if lock is None:
            _reject(
                PlanningProblemErrorCode.MISSING_PROBLEM_FACT,
                field="operation_instances.lock_ids",
                entity_id=operation_id,
                expected_contract="lock ID present in immutable Snapshot records",
                message="Operation lock reference is missing",
            )
        lock_start = parse_utc_instant(str(lock["start_at_utc"]))
        lock_end = parse_utc_instant(str(lock["end_at_utc"]))
        if lock_start < horizon_end and lock_end > horizon_start:
            _reject(
                PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT,
                field="operation_instances.lock_ids",
                entity_id=operation_id,
                expected_contract=(
                    "planning-problem.v1 has no active HARD_LOCK/SOFT_LOCK fields"
                ),
                message="A lock intersecting the planning horizon cannot be discarded",
            )


def _project_operations(
    snapshot_document: PlanningSnapshotDocumentV2,
    *,
    tick_seconds: int,
    horizon_start: datetime,
    horizon_end: datetime,
) -> tuple[list[dict[str, object]], set[str], set[str]]:
    records = snapshot_document["records"]
    facts_by_id = {
        str(fact["execution_fact_id"]): cast(Mapping[str, object], fact)
        for fact in records["execution_facts"]
    }
    locks_by_id = {
        str(lock["lock_id"]): cast(Mapping[str, object], lock)
        for lock in records["operation_locks"]
    }
    operations: list[dict[str, object]] = []
    active_ids: set[str] = set()
    completed_ids: set[str] = set()
    horizon_seconds = int((horizon_end - horizon_start).total_seconds())

    for raw_instance in snapshot_document["operation_instances"]:
        instance = cast(Mapping[str, object], raw_instance)
        operation_id = str(instance["operation_instance_id"])
        status = str(instance["status"])
        if status == "COMPLETED":
            completed_ids.add(operation_id)
            continue
        active_ids.add(operation_id)
        _reject_overlapping_locks(
            instance,
            locks_by_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
        options = _project_options(instance)
        projected: dict[str, object] = {
            "operation_id": operation_id,
            "status": status,
            "release_at_utc": instance["release_at_utc"],
            "material_ready_at_utc": instance["material_ready_at_utc"],
            "resource_options": options,
        }
        if status == "RUNNING":
            fact_id = instance.get("execution_fact_id")
            fact = facts_by_id.get(str(fact_id)) if fact_id is not None else None
            if fact is None:
                _reject(
                    PlanningProblemErrorCode.MISSING_PROBLEM_FACT,
                    field="operation_instances.execution_fact_id",
                    entity_id=operation_id,
                    expected_contract="one matching RUNNING execution fact",
                    message="RUNNING operation has no resolvable execution fact",
                )
            required = ("actual_start_at_utc", "resource_id", "remaining_seconds")
            if any(field not in fact for field in required):
                _reject(
                    PlanningProblemErrorCode.MISSING_PROBLEM_FACT,
                    field="records.execution_facts",
                    entity_id=operation_id,
                    expected_contract="actual start, assigned resource, and remaining seconds",
                    message="RUNNING fact is incomplete for Problem projection",
                )
            remaining_seconds = cast(int, fact["remaining_seconds"])
            future_seconds = duration_to_ticks(remaining_seconds, tick_seconds) * tick_seconds
            if future_seconds > horizon_seconds:
                _reject(
                    PlanningProblemErrorCode.INVALID_BUILD_CONFIG,
                    field="horizon_end_utc",
                    entity_id=operation_id,
                    expected_contract="horizon contains the full ceiled RUNNING remainder",
                    message="Planning horizon would truncate RUNNING occupancy",
                )
            projected.update(
                {
                    "actual_start_at_utc": fact["actual_start_at_utc"],
                    "assigned_resource_id": fact["resource_id"],
                    "remaining_seconds": remaining_seconds,
                }
            )
        else:
            earliest_start = max(
                horizon_start,
                parse_utc_instant(str(instance["release_at_utc"])),
                parse_utc_instant(str(instance["material_ready_at_utc"])),
            )
            available_seconds = int((horizon_end - earliest_start).total_seconds())
            option_ticks = [
                duration_to_ticks(
                    cast(int, option["final_duration_seconds"]), tick_seconds
                )
                for option in options
            ]
            if (
                available_seconds <= 0
                or not option_ticks
                or min(option_ticks) * tick_seconds > available_seconds
            ):
                _reject(
                    PlanningProblemErrorCode.INVALID_BUILD_CONFIG,
                    field="horizon_end_utc",
                    entity_id=operation_id,
                    expected_contract=(
                        "horizon contains at least one full ceiled candidate duration "
                        "after release/material gates"
                    ),
                    message="Planning horizon would truncate every candidate",
                )
        operations.append(projected)
    return operations, active_ids, completed_ids


def _project_edges(
    snapshot_document: PlanningSnapshotDocumentV2,
    *,
    active_ids: set[str],
    completed_ids: set[str],
) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    for raw_edge in snapshot_document["operation_precedence_edges"]:
        edge = cast(Mapping[str, object], raw_edge)
        predecessor = str(edge["predecessor_operation_instance_id"])
        successor = str(edge["successor_operation_instance_id"])
        if predecessor in completed_ids and successor in completed_ids:
            continue
        if predecessor not in active_ids or successor not in active_ids:
            _reject(
                PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT,
                field="operation_precedence_edges",
                entity_id=str(edge["operation_precedence_edge_id"]),
                expected_contract=(
                    "planning-problem.v1 cannot preserve a precedence boundary "
                    "between COMPLETED and active operations"
                ),
                message="Filtering one edge endpoint would silently discard lag semantics",
            )
        projected: dict[str, object] = {
            "predecessor_operation_id": predecessor,
            "successor_operation_id": successor,
            "min_lag_seconds": edge["min_lag_seconds"],
            "transport_lag_seconds": edge["transport_lag_seconds"],
        }
        if "max_lag_seconds" in edge:
            projected["max_lag_seconds"] = edge["max_lag_seconds"]
        edges.append(projected)
    return edges


def _project_unavailable_intervals(
    snapshot_document: PlanningSnapshotDocumentV2,
    *,
    horizon_start: datetime,
    horizon_end: datetime,
) -> list[dict[str, object]]:
    records = snapshot_document["records"]
    calendars = {
        str(calendar["calendar_id"]): cast(Mapping[str, object], calendar)
        for calendar in records["calendars"]
    }
    intervals: list[dict[str, object]] = []
    for resource in records["resources"]:
        resource_id = resource["resource_id"]
        calendar_id = resource["calendar_id"]
        calendar = calendars.get(calendar_id)
        if calendar is None:
            _reject(
                PlanningProblemErrorCode.MISSING_PROBLEM_FACT,
                field="records.resources.calendar_id",
                entity_id=resource_id,
                expected_contract="referenced Calendar in immutable Snapshot",
                message="Resource calendar is missing",
            )
        for interval in cast(
            list[Mapping[str, object]], calendar["unavailable_intervals"]
        ):
            start = parse_utc_instant(str(interval["start_at_utc"]))
            end = parse_utc_instant(str(interval["end_at_utc"]))
            if start >= horizon_end or end <= horizon_start:
                continue
            intervals.append(
                {
                    "resource_id": resource_id,
                    "start_utc": interval["start_at_utc"],
                    "end_utc": interval["end_at_utc"],
                }
            )
    return intervals


def _required_capabilities(
    snapshot_document: PlanningSnapshotDocumentV2,
    operations: list[dict[str, object]],
    intervals: list[dict[str, object]],
) -> list[str]:
    required: set[CapabilityName] = set()
    if operations:
        required.update(
            {CapabilityName.DAG_ROUTING, CapabilityName.RELEASE_AND_MATERIAL_GATE}
        )
        if len(snapshot_document["records"]["workshops"]) > 1:
            required.add(CapabilityName.SINGLE_FACTORY_MULTI_WORKSHOP)
        if any(
            len(cast(list[object], operation["resource_options"])) > 1
            for operation in operations
        ):
            required.add(CapabilityName.ALTERNATIVE_RESOURCE)
        if any(operation["status"] == "RUNNING" for operation in operations):
            required.add(CapabilityName.RUNNING_OPERATION)
    if intervals:
        required.add(CapabilityName.MACHINE_CALENDAR)
    names = sorted(capability.value for capability in required)
    require_v1_capability_contract(names)
    return names


def build_planning_problem(
    snapshot: ImmutablePlanningSnapshot,
    *,
    problem_builder_version: str,
    tick_seconds: int,
    horizon_start_utc: str,
    horizon_end_utc: str,
) -> ImmutablePlanningProblem:
    """Build one deterministic Problem without Solver or persistence objects."""

    try:
        verify_snapshot(snapshot)
    except SnapshotError as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.INVALID_SNAPSHOT,
            field=error.field,
            entity_id=snapshot.snapshot_id,
            expected_contract="verified immutable planning-snapshot.v2",
            message="Snapshot integrity or provenance validation failed",
        ) from error
    snapshot_document = snapshot.document
    tick, horizon_start, horizon_end = _validate_config(
        snapshot_document,
        problem_builder_version=problem_builder_version,
        tick_seconds=tick_seconds,
        horizon_start_utc=horizon_start_utc,
        horizon_end_utc=horizon_end_utc,
    )
    if len(snapshot_document["records"]["factories"]) > 1:
        _reject(
            PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT,
            field="records.factories",
            entity_id=snapshot.snapshot_id,
            expected_contract="single-factory PlanningProblem v1",
            message="MULTI_FACTORY is not a V1 capability",
        )

    operations, active_ids, completed_ids = _project_operations(
        snapshot_document,
        tick_seconds=tick,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    edges = _project_edges(
        snapshot_document,
        active_ids=active_ids,
        completed_ids=completed_ids,
    )
    intervals = _project_unavailable_intervals(
        snapshot_document,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    required_capabilities = _required_capabilities(
        snapshot_document, operations, intervals
    )

    base = cast(
        PlanningProblemDocument,
        {
            "problem_version": PLANNING_PROBLEM_VERSION,
            "snapshot_id": snapshot.snapshot_id,
            "problem_builder_version": problem_builder_version,
            "problem_hash": "",
            "tick_seconds": tick,
            "horizon_start_utc": horizon_start_utc,
            "horizon_end_utc": horizon_end_utc,
            "resource_ids": [
                resource["resource_id"]
                for resource in snapshot_document["records"]["resources"]
            ],
            "operation_instances": operations,
            "precedence_edges": edges,
            "resource_unavailable_intervals": intervals,
            "required_capabilities": required_capabilities,
        },
    )
    canonical = canonical_problem_document(cast(Mapping[str, object], base))
    canonical["problem_hash"] = problem_hash_for(cast(Mapping[str, object], canonical))
    validate_built_problem(cast(Mapping[str, object], canonical))
    problem = ImmutablePlanningProblem(
        canonical_bytes=canonical_problem_bytes(cast(Mapping[str, object], canonical)),
        problem_hash=canonical["problem_hash"],
        snapshot_id=canonical["snapshot_id"],
        problem_builder_version=canonical["problem_builder_version"],
    )
    verify_problem(problem)
    return problem


__all__ = ["build_planning_problem"]
