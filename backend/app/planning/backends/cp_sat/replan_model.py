"""P4 global CP-SAT replan model and exact lexicographic objective variables."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from app.domain.types import parse_utc_instant
from app.planning.backends.cp_sat.model import (
    CoreCpSatModel,
    CoreOperationVariables,
    build_core_model,
)
from app.planning.backends.cp_sat.objectives import (
    DeliveryObjectiveModel,
    add_delivery_objective,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2


REPLAN_MODEL_VERSION = "cp-sat-replan-model.v1"
_CP_SAT_INT_MAX = (1 << 63) - 1


@dataclass(frozen=True)
class StabilityObjectiveModel:
    """Four integer components in the accepted OBJ-002 comparison order."""

    soft_lock_violations: cp_model.IntVar
    changed_existing_operations: cp_model.IntVar
    resource_changes: cp_model.IntVar
    absolute_start_shift_seconds: cp_model.IntVar

    @property
    def ordered(self) -> tuple[tuple[str, cp_model.IntVar], ...]:
        return (
            ("soft_lock_violations", self.soft_lock_violations),
            ("changed_existing_operations", self.changed_existing_operations),
            ("resource_changes", self.resource_changes),
            ("absolute_start_shift_seconds", self.absolute_start_shift_seconds),
        )


@dataclass(frozen=True)
class ReplanCpSatModel:
    """One complete global hard domain shared by every lexicographic round."""

    core: CoreCpSatModel
    delivery: DeliveryObjectiveModel
    stability: StabilityObjectiveModel
    makespan_seconds: cp_model.IntVar
    base_hint_count: int
    effective_hard_lock_count: int


def _operation_index(
    core: CoreCpSatModel,
) -> dict[str, CoreOperationVariables]:
    return {operation.operation_id: operation for operation in core.operations}


def _sequence(value: object, field: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{field} must be an array of objects")
    return cast(Sequence[Mapping[str, object]], value)


def _tick_offset(value: object, problem: PlanningProblemDocumentV2, field: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC3339 UTC instant")
    delta = parse_utc_instant(value) - parse_utc_instant(problem["horizon_start_utc"])
    seconds = delta.days * 86400 + delta.seconds
    if delta.microseconds or seconds % problem["tick_seconds"]:
        raise ValueError(f"{field} is not exactly representable on the Problem grid")
    return seconds // problem["tick_seconds"]


def _selected_resource_literal(
    operation: CoreOperationVariables,
    resource_id: object,
    *,
    field: str,
) -> cp_model.IntVar:
    if not isinstance(resource_id, str):
        raise ValueError(f"{field} must be a resource identifier")
    for option in operation.options:
        if option.resource_id == resource_id:
            return option.presence
    raise ValueError(f"{field} does not identify a candidate resource")


def _equality_literal(
    model: cp_model.CpModel,
    variable: cp_model.IntVar,
    value: int,
    *,
    name: str,
) -> cp_model.IntVar:
    literal = model.new_bool_var(name)
    model.add(variable == value).only_enforce_if(literal)
    model.add(variable != value).only_enforce_if(literal.Not())
    return literal


def _conjunction_literal(
    model: cp_model.CpModel,
    literals: Sequence[cp_model.IntVar],
    *,
    name: str,
) -> cp_model.IntVar:
    result = model.new_bool_var(name)
    model.add_bool_and(literals).only_enforce_if(result)
    model.add_bool_or([literal.Not() for literal in literals]).only_enforce_if(
        result.Not()
    )
    return result


def _complement_literal(
    model: cp_model.CpModel,
    literal: cp_model.IntVar,
    *,
    name: str,
) -> cp_model.IntVar:
    complement = model.new_bool_var(name)
    model.add(complement + literal == 1)
    return complement


def _sum_variable(
    model: cp_model.CpModel,
    values: Sequence[cp_model.IntVar],
    *,
    upper_bound: int,
    name: str,
) -> cp_model.IntVar:
    if upper_bound > _CP_SAT_INT_MAX:
        raise ValueError(f"{name} exceeds the CP-SAT int64 domain")
    result = model.new_int_var(0, upper_bound, name)
    model.add(result == sum(values, 0))
    return result


def _protection_identifier(protection: Mapping[str, object]) -> str:
    value = protection.get("reference_id", protection.get("lock_id"))
    if not isinstance(value, str) or not value:
        raise ValueError("effective protection has no canonical identifier")
    return value


def _add_effective_hard_locks(
    problem: PlanningProblemDocumentV2,
    core: CoreCpSatModel,
    projection: Mapping[str, object],
) -> int:
    model = core.model
    operations = _operation_index(core)
    count = 0
    for section in (
        "running_protections",
        "explicit_hard_locks",
        "freeze_derived_hard_locks",
    ):
        for protection in _sequence(projection.get(section), section):
            operation_id = protection.get("operation_id")
            if not isinstance(operation_id, str) or operation_id not in operations:
                raise ValueError(f"{section} references an unknown active operation")
            operation = operations[operation_id]
            resource = _selected_resource_literal(
                operation,
                protection.get("resource_id"),
                field=f"{section}.resource_id",
            )
            start_tick = _tick_offset(
                protection.get("start_at_utc"),
                problem,
                f"{section}.start_at_utc",
            )
            end_tick = _tick_offset(
                protection.get("end_at_utc"),
                problem,
                f"{section}.end_at_utc",
            )
            model.add(resource == 1)
            model.add(operation.start == start_tick)
            model.add(operation.end == end_tick)
            _ = _protection_identifier(protection)
            count += 1
    return count


def _base_assignment_index(
    base_assignments: Sequence[object],
) -> dict[str, Mapping[str, object]]:
    indexed: dict[str, Mapping[str, object]] = {}
    for index, value in enumerate(base_assignments):
        if not isinstance(value, Mapping):
            raise ValueError(f"base_assignments[{index}] must be an object")
        operation_id = value.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError(f"base_assignments[{index}] has no operation_id")
        if operation_id in indexed:
            raise ValueError("base assignments contain a duplicate operation")
        indexed[operation_id] = value
    return indexed


def _add_base_hints(
    problem: PlanningProblemDocumentV2,
    core: CoreCpSatModel,
    base: Mapping[str, Mapping[str, object]],
) -> int:
    operations = _operation_index(core)
    hints = 0
    for operation_id, assignment in sorted(base.items()):
        operation = operations.get(operation_id)
        if operation is None:
            continue
        try:
            start_tick = _tick_offset(
                assignment.get("start_at_utc"), problem, "base.start_at_utc"
            )
            end_tick = _tick_offset(
                assignment.get("end_at_utc"), problem, "base.end_at_utc"
            )
        except ValueError:
            continue
        if not (0 <= start_tick <= end_tick <= core.horizon_ticks):
            continue
        resource_id = assignment.get("resource_id")
        selected = None
        for option in operation.options:
            value = int(option.resource_id == resource_id)
            core.model.add_hint(option.presence, value)
            hints += 1
            if value:
                selected = option
        if selected is None:
            continue
        core.model.add_hint(operation.start, start_tick)
        core.model.add_hint(operation.end, end_tick)
        hints += 2
    return hints


def _add_stability_objective(
    problem: PlanningProblemDocumentV2,
    core: CoreCpSatModel,
    projection: Mapping[str, object],
    base: Mapping[str, Mapping[str, object]],
) -> StabilityObjectiveModel:
    model = core.model
    operations = _operation_index(core)
    soft_violations: list[cp_model.IntVar] = []
    for index, protection in enumerate(_sequence(projection.get("soft_locks"), "soft_locks")):
        operation_id = protection.get("operation_id")
        if not isinstance(operation_id, str) or operation_id not in operations:
            raise ValueError("SOFT lock references an unknown active operation")
        operation = operations[operation_id]
        resource_match = _selected_resource_literal(
            operation,
            protection.get("resource_id"),
            field="soft_locks.resource_id",
        )
        start_match = _equality_literal(
            model,
            operation.start,
            _tick_offset(
                protection.get("start_at_utc"), problem, "soft_locks.start_at_utc"
            ),
            name=f"obj002_soft_{index:06d}_start_match",
        )
        end_match = _equality_literal(
            model,
            operation.end,
            _tick_offset(
                protection.get("end_at_utc"), problem, "soft_locks.end_at_utc"
            ),
            name=f"obj002_soft_{index:06d}_end_match",
        )
        exact_match = _conjunction_literal(
            model,
            [resource_match, start_match, end_match],
            name=f"obj002_soft_{index:06d}_exact_match",
        )
        soft_violations.append(
            _complement_literal(
                model,
                exact_match,
                name=f"obj002_soft_{index:06d}_violation",
            )
        )

    changed_values: list[cp_model.IntVar] = []
    resource_changes: list[cp_model.IntVar] = []
    start_shifts: list[cp_model.IntVar] = []
    horizon_seconds = core.horizon_ticks * problem["tick_seconds"]
    shift_upper_bound = 0
    comparable_index = 0
    for operation_id, assignment in sorted(base.items()):
        operation = operations.get(operation_id)
        if operation is None:
            continue
        resource_match = _selected_resource_literal(
            operation,
            assignment.get("resource_id"),
            field="base_assignments.resource_id",
        )
        base_start_tick = _tick_offset(
            assignment.get("start_at_utc"), problem, "base_assignments.start_at_utc"
        )
        base_end_tick = _tick_offset(
            assignment.get("end_at_utc"), problem, "base_assignments.end_at_utc"
        )
        start_match = _equality_literal(
            model,
            operation.start,
            base_start_tick,
            name=f"obj002_existing_{comparable_index:06d}_start_match",
        )
        end_match = _equality_literal(
            model,
            operation.end,
            base_end_tick,
            name=f"obj002_existing_{comparable_index:06d}_end_match",
        )
        exact_match = _conjunction_literal(
            model,
            [resource_match, start_match, end_match],
            name=f"obj002_existing_{comparable_index:06d}_exact_match",
        )
        changed_values.append(
            _complement_literal(
                model,
                exact_match,
                name=f"obj002_existing_{comparable_index:06d}_changed",
            )
        )
        resource_changes.append(
            _complement_literal(
                model,
                resource_match,
                name=f"obj002_existing_{comparable_index:06d}_resource_changed",
            )
        )
        base_start_seconds = base_start_tick * problem["tick_seconds"]
        upper = max(abs(base_start_seconds), abs(horizon_seconds - base_start_seconds))
        shift = model.new_int_var(
            0,
            upper,
            f"obj002_existing_{comparable_index:06d}_absolute_start_shift_seconds",
        )
        model.add_abs_equality(
            shift,
            operation.start * problem["tick_seconds"] - base_start_seconds,
        )
        start_shifts.append(shift)
        shift_upper_bound += upper
        if shift_upper_bound > _CP_SAT_INT_MAX:
            raise ValueError("OBJ-002 absolute start shift exceeds CP-SAT int64")
        comparable_index += 1

    return StabilityObjectiveModel(
        soft_lock_violations=_sum_variable(
            model,
            soft_violations,
            upper_bound=len(soft_violations),
            name="obj002_soft_lock_violations",
        ),
        changed_existing_operations=_sum_variable(
            model,
            changed_values,
            upper_bound=len(changed_values),
            name="obj002_changed_existing_operations",
        ),
        resource_changes=_sum_variable(
            model,
            resource_changes,
            upper_bound=len(resource_changes),
            name="obj002_resource_changes",
        ),
        absolute_start_shift_seconds=_sum_variable(
            model,
            start_shifts,
            upper_bound=shift_upper_bound,
            name="obj002_absolute_start_shift_seconds",
        ),
    )


def _add_makespan(problem: PlanningProblemDocumentV2, core: CoreCpSatModel) -> cp_model.IntVar:
    makespan_tick = core.model.new_int_var(
        0, core.horizon_ticks, "obj003_makespan_tick"
    )
    core.model.add_max_equality(
        makespan_tick,
        [operation.end for operation in core.operations],
    )
    makespan_seconds = core.model.new_int_var(
        0,
        core.horizon_ticks * problem["tick_seconds"],
        "obj003_makespan_seconds",
    )
    core.model.add(
        makespan_seconds == makespan_tick * problem["tick_seconds"]
    )
    return makespan_seconds


def build_replan_model(
    problem: PlanningProblemDocumentV2,
    *,
    base_assignments: Sequence[object],
    effective_locks: Mapping[str, object],
) -> ReplanCpSatModel:
    """Build one complete model; only the active objective changes between rounds."""

    core = build_core_model(problem)
    base = _base_assignment_index(base_assignments)
    hard_count = _add_effective_hard_locks(problem, core, effective_locks)
    hint_count = _add_base_hints(problem, core, base)
    stability = _add_stability_objective(
        problem,
        core,
        effective_locks,
        base,
    )
    makespan = _add_makespan(problem, core)
    delivery = add_delivery_objective(problem, core)
    validation_error = core.model.validate()
    if validation_error:
        raise ValueError("Pinned CP-SAT rejected the P4 replan model")
    return ReplanCpSatModel(
        core=core,
        delivery=delivery,
        stability=stability,
        makespan_seconds=makespan,
        base_hint_count=hint_count,
        effective_hard_lock_count=hard_count,
    )


__all__ = [
    "REPLAN_MODEL_VERSION",
    "ReplanCpSatModel",
    "StabilityObjectiveModel",
    "build_replan_model",
]
