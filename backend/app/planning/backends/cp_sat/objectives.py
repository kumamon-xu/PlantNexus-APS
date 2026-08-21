"""OBJ-001 weighted-tardiness construction for the complete P2 CP-SAT model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn, TypedDict

from ortools.sat.python import cp_model

from app.domain.types import parse_utc_instant
from app.planning.backends.cp_sat.model import CoreCpSatModel
from app.planning.problem.contracts import PlanningProblemDocumentV2


OBJECTIVE_ID = "OBJ-001"
OBJECTIVE_METRIC = "WEIGHTED_TARDINESS"
OBJECTIVE_UNIT = "priority_weighted_tardiness_seconds"
_CP_SAT_INT_MAX = (1 << 63) - 1


class DeliveryObjectiveReason(StrEnum):
    """Stable model-input failures specific to OBJ-001 construction."""

    DEMAND_OPERATION_MISMATCH = "DEMAND_OPERATION_MISMATCH"
    INVALID_PRIORITY_WEIGHT = "INVALID_PRIORITY_WEIGHT"
    OBJECTIVE_INTEGER_OVERFLOW = "OBJECTIVE_INTEGER_OVERFLOW"


class DeliveryObjectiveError(ValueError):
    """OBJ-001 cannot be represented without changing its exact semantics."""

    def __init__(
        self,
        reason: DeliveryObjectiveReason,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value} at {field}: {message}")


class DeliveryObjectiveMetricsDocument(TypedDict):
    demand_count: int
    completion_variables: int
    tardiness_variables: int
    objective_variables: int
    added_constraints: int
    objective_upper_bound: int
    objective_unit: str


@dataclass(frozen=True)
class DemandObjectiveVariables:
    demand_order_id: str
    priority_weight: int
    due_offset_seconds: int
    completion_tick: cp_model.IntVar
    tardiness_seconds: cp_model.IntVar


@dataclass(frozen=True)
class DeliveryObjectiveModel:
    total_weighted_tardiness_seconds: cp_model.IntVar
    demands: tuple[DemandObjectiveVariables, ...]
    metrics: DeliveryObjectiveMetricsDocument


def _reject(
    reason: DeliveryObjectiveReason,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise DeliveryObjectiveError(reason, field=field, message=message)


def _exact_seconds_between(later: str, earlier: str) -> int:
    delta = parse_utc_instant(later) - parse_utc_instant(earlier)
    if delta.microseconds:
        raise ValueError("OBJ-001 timestamps must have exact second precision")
    return delta.days * 86400 + delta.seconds


def add_delivery_objective(
    problem: PlanningProblemDocumentV2,
    core_model: CoreCpSatModel,
) -> DeliveryObjectiveModel:
    """Minimize exact priority-weighted tardiness seconds inside the hard domain."""

    model = core_model.model
    if model.has_objective():
        raise ValueError("CP-SAT model already has an objective")

    demand_ids = [demand["demand_order_id"] for demand in problem["delivery_demands"]]
    operation_demand_ids = {
        operation["demand_order_id"] for operation in problem["operation_instances"]
    }
    if len(demand_ids) != len(set(demand_ids)) or set(demand_ids) != operation_demand_ids:
        _reject(
            DeliveryObjectiveReason.DEMAND_OPERATION_MISMATCH,
            field="delivery_demands/operation_instances",
            message=(
                "delivery demands must identify exactly the active operation demand set"
            ),
        )

    operations_by_demand: dict[str, list[cp_model.IntVar]] = {
        demand_id: [] for demand_id in demand_ids
    }
    operation_demand_by_id = {
        operation["operation_id"]: operation["demand_order_id"]
        for operation in problem["operation_instances"]
    }
    for operation in core_model.operations:
        demand_id = operation_demand_by_id[operation.operation_id]
        operations_by_demand[demand_id].append(operation.end)

    horizon_seconds = core_model.horizon_ticks * problem["tick_seconds"]
    constraints_before = len(model.proto.constraints)
    demand_variables: list[DemandObjectiveVariables] = []
    objective_terms: list[cp_model.LinearExpr] = []
    objective_upper_bound = 0
    for index, demand in enumerate(problem["delivery_demands"]):
        weight = demand["priority_weight"]
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 1:
            _reject(
                DeliveryObjectiveReason.INVALID_PRIORITY_WEIGHT,
                field=f"delivery_demands[{index}].priority_weight",
                message="priority weight must be a positive non-boolean integer",
            )
        due_offset_seconds = _exact_seconds_between(
            demand["due_at_utc"], problem["horizon_start_utc"]
        )
        tardiness_upper = max(0, horizon_seconds - due_offset_seconds)
        weighted_upper = weight * tardiness_upper
        if weight > _CP_SAT_INT_MAX or weighted_upper > _CP_SAT_INT_MAX:
            _reject(
                DeliveryObjectiveReason.OBJECTIVE_INTEGER_OVERFLOW,
                field=f"delivery_demands[{index}]",
                message="one weighted tardiness term exceeds the CP-SAT int64 domain",
            )
        objective_upper_bound += weighted_upper
        if objective_upper_bound > _CP_SAT_INT_MAX:
            _reject(
                DeliveryObjectiveReason.OBJECTIVE_INTEGER_OVERFLOW,
                field="delivery_demands",
                message="weighted tardiness sum exceeds the CP-SAT int64 domain",
            )

        completion_tick = model.new_int_var(
            0,
            core_model.horizon_ticks,
            f"obj001_demand_{index:06d}_completion_tick",
        )
        model.add_max_equality(
            completion_tick,
            operations_by_demand[demand["demand_order_id"]],
        )
        tardiness_seconds = model.new_int_var(
            0,
            tardiness_upper,
            f"obj001_demand_{index:06d}_tardiness_seconds",
        )
        model.add_max_equality(
            tardiness_seconds,
            [
                completion_tick * problem["tick_seconds"] - due_offset_seconds,
                0,
            ],
        )
        objective_terms.append(weight * tardiness_seconds)
        demand_variables.append(
            DemandObjectiveVariables(
                demand_order_id=demand["demand_order_id"],
                priority_weight=weight,
                due_offset_seconds=due_offset_seconds,
                completion_tick=completion_tick,
                tardiness_seconds=tardiness_seconds,
            )
        )

    objective = model.new_int_var(
        0,
        objective_upper_bound,
        "obj001_total_weighted_tardiness_seconds",
    )
    model.add(objective == sum(objective_terms, 0))
    model.minimize(objective)
    return DeliveryObjectiveModel(
        total_weighted_tardiness_seconds=objective,
        demands=tuple(demand_variables),
        metrics={
            "demand_count": len(demand_variables),
            "completion_variables": len(demand_variables),
            "tardiness_variables": len(demand_variables),
            "objective_variables": 1,
            "added_constraints": len(model.proto.constraints) - constraints_before,
            "objective_upper_bound": objective_upper_bound,
            "objective_unit": OBJECTIVE_UNIT,
        },
    )


__all__ = [
    "DeliveryObjectiveError",
    "DeliveryObjectiveMetricsDocument",
    "DeliveryObjectiveModel",
    "DeliveryObjectiveReason",
    "DemandObjectiveVariables",
    "OBJECTIVE_ID",
    "OBJECTIVE_METRIC",
    "OBJECTIVE_UNIT",
    "add_delivery_objective",
]
