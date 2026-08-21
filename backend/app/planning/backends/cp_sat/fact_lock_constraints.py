"""Exact TASK-P2-07 execution-fact and operation-lock constraints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict

from ortools.sat.python import cp_model

from app.domain.types import parse_utc_instant, require_tick_seconds
from app.planning.backends.cp_sat.temporal_constraints import ceil_seconds_to_ticks
from app.planning.problem.contracts import PlanningProblemDocumentV2


FACT_LOCK_CONSTRAINT_IDS = ("C-007", "C-008")


class FactLockConstraintMetricsDocument(TypedDict):
    """Deterministic model deltas attributable to TASK-P2-07."""

    running_operations: int
    hard_locks: int
    soft_locks: int
    lock_references: int
    fixed_operation_intervals: int
    resource_fix_constraints: int
    start_fix_constraints: int
    end_fix_constraints: int


@dataclass(frozen=True)
class FactLockOptionBinding:
    """Resource selection variable consumed by fact/lock constraints."""

    resource_id: str
    presence: cp_model.IntVar


@dataclass(frozen=True)
class FactLockOperationBinding:
    """Master interval variables consumed by the independent fact/lock builder."""

    operation_id: str
    start: cp_model.IntVar
    end: cp_model.IntVar
    options: tuple[FactLockOptionBinding, ...]


def exact_tick_offset(value: str, origin: str, tick_seconds: int) -> int:
    """Project one UTC instant only when it lies exactly on the solver grid."""

    tick = int(require_tick_seconds(tick_seconds))
    delta = parse_utc_instant(value) - parse_utc_instant(origin)
    total_microseconds = (
        (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    )
    tick_microseconds = tick * 1_000_000
    if total_microseconds % tick_microseconds:
        raise ValueError("UTC instant is not aligned to the exact solver tick grid")
    return total_microseconds // tick_microseconds


def _fix_resource(
    model: cp_model.CpModel,
    operation: FactLockOperationBinding,
    resource_id: str,
) -> None:
    option_by_resource: Mapping[str, FactLockOptionBinding] = {
        option.resource_id: option for option in operation.options
    }
    model.add(option_by_resource[resource_id].presence == 1)


def add_fact_lock_constraints(
    model: cp_model.CpModel,
    problem: PlanningProblemDocumentV2,
    operations: Sequence[FactLockOperationBinding],
) -> FactLockConstraintMetricsDocument:
    """Add exact C-007/C-008 constraints without hints or an objective."""

    operation_by_id = {operation.operation_id: operation for operation in operations}
    tick_seconds = problem["tick_seconds"]
    running_count = 0
    hard_count = 0
    soft_count = 0
    resource_constraints = 0
    start_constraints = 0
    end_constraints = 0
    fixed_operation_ids: set[str] = set()

    for operation_fact in problem["operation_instances"]:
        if operation_fact["status"] != "RUNNING":
            continue
        operation = operation_by_id[operation_fact["operation_id"]]
        remaining_seconds = operation_fact.get("remaining_seconds")
        assigned_resource = operation_fact.get("assigned_resource_id")
        assert isinstance(remaining_seconds, int) and not isinstance(
            remaining_seconds, bool
        )
        assert isinstance(assigned_resource, str)
        remaining_ticks = ceil_seconds_to_ticks(
            remaining_seconds, tick_seconds
        )
        model.add(operation.start == 0)
        model.add(operation.end == remaining_ticks)
        _fix_resource(model, operation, assigned_resource)
        running_count += 1
        resource_constraints += 1
        start_constraints += 1
        end_constraints += 1
        fixed_operation_ids.add(operation.operation_id)

    horizon_start = problem["horizon_start_utc"]
    for lock in problem["operation_locks"]:
        if lock["lock_type"] == "SOFT_LOCK":
            soft_count += 1
            continue
        operation = operation_by_id[lock["operation_id"]]
        start_tick = exact_tick_offset(
            lock["start_at_utc"], horizon_start, tick_seconds
        )
        end_tick = exact_tick_offset(lock["end_at_utc"], horizon_start, tick_seconds)
        model.add(operation.start == start_tick)
        model.add(operation.end == end_tick)
        _fix_resource(model, operation, lock["resource_id"])
        hard_count += 1
        resource_constraints += 1
        start_constraints += 1
        end_constraints += 1
        fixed_operation_ids.add(operation.operation_id)

    return {
        "running_operations": running_count,
        "hard_locks": hard_count,
        "soft_locks": soft_count,
        "lock_references": len(problem["operation_locks"]),
        "fixed_operation_intervals": len(fixed_operation_ids),
        "resource_fix_constraints": resource_constraints,
        "start_fix_constraints": start_constraints,
        "end_fix_constraints": end_constraints,
    }


__all__ = [
    "FACT_LOCK_CONSTRAINT_IDS",
    "FactLockConstraintMetricsDocument",
    "FactLockOperationBinding",
    "FactLockOptionBinding",
    "add_fact_lock_constraints",
    "exact_tick_offset",
]
