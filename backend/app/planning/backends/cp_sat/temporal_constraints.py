"""Exact TASK-P2-06 temporal, calendar, material, and transport constraints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict, cast

from ortools.sat.python import cp_model

from app.domain.types import parse_utc_instant, require_tick_seconds
from app.planning.problem.contracts import PlanningProblemDocumentV2


TEMPORAL_CONSTRAINT_IDS = ("C-002", "C-005", "C-006", "C-009")


class TemporalConstraintMetricsDocument(TypedDict):
    """Deterministic model deltas attributable to TASK-P2-06."""

    precedence_edges: int
    precedence_min_constraints: int
    precedence_max_constraints: int
    calendar_input_intervals: int
    calendar_fixed_intervals: int
    release_gate_constraints: int
    material_gate_constraints: int
    transport_conditional_constraints: int


@dataclass(frozen=True)
class TemporalOptionBinding:
    """The resource-selection facts needed by conditional transport constraints."""

    resource_id: str
    presence: cp_model.IntVar


@dataclass(frozen=True)
class TemporalOperationBinding:
    """Solver variables consumed by the independent temporal builder."""

    operation_id: str
    start: cp_model.IntVar
    end: cp_model.IntVar
    options: tuple[TemporalOptionBinding, ...]


def ceil_seconds_to_ticks(seconds: int, tick_seconds: int) -> int:
    """Return mathematical ``ceil(seconds / tick_seconds)`` for signed seconds."""

    tick = int(require_tick_seconds(tick_seconds))
    return -((-seconds) // tick)


def floor_seconds_to_ticks(seconds: int, tick_seconds: int) -> int:
    """Return mathematical ``floor(seconds / tick_seconds)`` for signed seconds."""

    tick = int(require_tick_seconds(tick_seconds))
    return seconds // tick


def _relative_seconds(value: str, origin: str) -> int:
    delta = parse_utc_instant(value) - parse_utc_instant(origin)
    if delta.microseconds:
        raise ValueError("Temporal instants must use exact whole-second precision")
    return delta.days * 86_400 + delta.seconds


def _merge_tick_intervals(
    intervals: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if start >= end:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return tuple(merged)


def calendar_tick_blocks(
    problem: PlanningProblemDocumentV2,
    *,
    horizon_ticks: int,
) -> dict[str, tuple[tuple[int, int], ...]]:
    """Project raw half-open UTC unavailability exactly onto grid-aligned intervals."""

    tick_seconds = problem["tick_seconds"]
    horizon_start = problem["horizon_start_utc"]
    projected: dict[str, list[tuple[int, int]]] = {
        resource["resource_id"]: [] for resource in problem["resources"]
    }
    for interval in problem["resource_unavailable_intervals"]:
        start = floor_seconds_to_ticks(
            _relative_seconds(interval["start_utc"], horizon_start), tick_seconds
        )
        end = ceil_seconds_to_ticks(
            _relative_seconds(interval["end_utc"], horizon_start), tick_seconds
        )
        clipped_start = max(0, start)
        clipped_end = min(horizon_ticks, end)
        if clipped_start < clipped_end:
            projected[interval["resource_id"]].append(
                (clipped_start, clipped_end)
            )
    return {
        resource_id: _merge_tick_intervals(intervals)
        for resource_id, intervals in sorted(projected.items())
    }


def _add_precedence_and_transport(
    model: cp_model.CpModel,
    problem: PlanningProblemDocumentV2,
    operation_by_id: Mapping[str, TemporalOperationBinding],
) -> tuple[int, int, int]:
    tick_seconds = problem["tick_seconds"]
    horizon_start = problem["horizon_start_utc"]
    anchor_by_id = {
        anchor["operation_id"]: anchor
        for anchor in problem["historical_completion_anchors"]
    }
    workshop_by_resource = {
        resource["resource_id"]: resource["workshop_id"]
        for resource in problem["resources"]
    }
    minimum_count = 0
    maximum_count = 0
    transport_count = 0

    for edge_index, edge in enumerate(problem["precedence_edges"]):
        predecessor_id = edge["predecessor_operation_id"]
        successor_id = edge["successor_operation_id"]
        successor = operation_by_id[successor_id]
        predecessor = operation_by_id.get(predecessor_id)
        minimum_ticks = ceil_seconds_to_ticks(
            edge["min_lag_seconds"], tick_seconds
        )
        maximum_seconds = cast(int | None, edge.get("max_lag_seconds"))

        if predecessor is not None:
            model.add(successor.start - predecessor.end >= minimum_ticks)
            minimum_count += 1
            if maximum_seconds is not None:
                maximum_ticks = floor_seconds_to_ticks(
                    maximum_seconds, tick_seconds
                )
                model.add(successor.start - predecessor.end <= maximum_ticks)
                maximum_count += 1
        else:
            anchor = anchor_by_id[predecessor_id]
            anchor_end_offset = _relative_seconds(
                anchor["actual_end_at_utc"], horizon_start
            )
            model.add(
                successor.start
                >= ceil_seconds_to_ticks(
                    anchor_end_offset + edge["min_lag_seconds"], tick_seconds
                )
            )
            minimum_count += 1
            if maximum_seconds is not None:
                model.add(
                    successor.start
                    <= floor_seconds_to_ticks(
                        anchor_end_offset + maximum_seconds, tick_seconds
                    )
                )
                maximum_count += 1

        transport_ticks = ceil_seconds_to_ticks(
            edge["transport_lag_seconds"], tick_seconds
        )
        if predecessor is not None:
            for predecessor_option in predecessor.options:
                predecessor_workshop = workshop_by_resource[
                    predecessor_option.resource_id
                ]
                for successor_option in successor.options:
                    if (
                        predecessor_workshop
                        == workshop_by_resource[successor_option.resource_id]
                    ):
                        continue
                    model.add(
                        successor.start - predecessor.end >= transport_ticks
                    ).only_enforce_if(
                        [predecessor_option.presence, successor_option.presence]
                    )
                    transport_count += 1
        else:
            anchor = anchor_by_id[predecessor_id]
            predecessor_workshop = workshop_by_resource[anchor["resource_id"]]
            anchor_end_offset = _relative_seconds(
                anchor["actual_end_at_utc"], horizon_start
            )
            anchor_transport_tick = ceil_seconds_to_ticks(
                anchor_end_offset + edge["transport_lag_seconds"], tick_seconds
            )
            for successor_option in successor.options:
                if (
                    predecessor_workshop
                    == workshop_by_resource[successor_option.resource_id]
                ):
                    continue
                model.add(successor.start >= anchor_transport_tick).only_enforce_if(
                    successor_option.presence
                )
                transport_count += 1

    return minimum_count, maximum_count, transport_count


def _add_release_and_material_gates(
    model: cp_model.CpModel,
    problem: PlanningProblemDocumentV2,
    operation_by_id: Mapping[str, TemporalOperationBinding],
) -> tuple[int, int]:
    tick_seconds = problem["tick_seconds"]
    horizon_start = problem["horizon_start_utc"]
    release_count = 0
    material_count = 0
    for operation in problem["operation_instances"]:
        variables = operation_by_id[operation["operation_id"]]
        release_tick = ceil_seconds_to_ticks(
            _relative_seconds(operation["release_at_utc"], horizon_start),
            tick_seconds,
        )
        material_tick = ceil_seconds_to_ticks(
            _relative_seconds(operation["material_ready_at_utc"], horizon_start),
            tick_seconds,
        )
        if release_tick > 0:
            model.add(variables.start >= release_tick)
            release_count += 1
        if material_tick > 0:
            model.add(variables.start >= material_tick)
            material_count += 1
    return release_count, material_count


def add_temporal_constraints(
    model: cp_model.CpModel,
    problem: PlanningProblemDocumentV2,
    operations: Sequence[TemporalOperationBinding],
    intervals_by_resource: dict[str, list[cp_model.IntervalVar]],
    *,
    horizon_ticks: int,
) -> TemporalConstraintMetricsDocument:
    """Add C-002/C-005/C-006/C-009 without adding an objective."""

    operation_by_id = {operation.operation_id: operation for operation in operations}
    minimum_count, maximum_count, transport_count = _add_precedence_and_transport(
        model, problem, operation_by_id
    )
    release_count, material_count = _add_release_and_material_gates(
        model, problem, operation_by_id
    )
    calendar_blocks = calendar_tick_blocks(problem, horizon_ticks=horizon_ticks)
    calendar_count = 0
    for resource_index, resource_id in enumerate(sorted(calendar_blocks)):
        for block_index, (start, end) in enumerate(calendar_blocks[resource_id]):
            interval = model.new_fixed_size_interval_var(
                start,
                end - start,
                f"calendar_{resource_index:06d}_{block_index:04d}_unavailable",
            )
            intervals_by_resource[resource_id].append(interval)
            calendar_count += 1

    return {
        "precedence_edges": len(problem["precedence_edges"]),
        "precedence_min_constraints": minimum_count,
        "precedence_max_constraints": maximum_count,
        "calendar_input_intervals": len(problem["resource_unavailable_intervals"]),
        "calendar_fixed_intervals": calendar_count,
        "release_gate_constraints": release_count,
        "material_gate_constraints": material_count,
        "transport_conditional_constraints": transport_count,
    }


__all__ = [
    "TEMPORAL_CONSTRAINT_IDS",
    "TemporalConstraintMetricsDocument",
    "TemporalOperationBinding",
    "TemporalOptionBinding",
    "add_temporal_constraints",
    "calendar_tick_blocks",
    "ceil_seconds_to_ticks",
    "floor_seconds_to_ticks",
]
