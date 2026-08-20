"""CP-SAT model construction for C-001/C-003/C-004/C-010/C-011."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import TypedDict, cast

from ortools.sat.python import cp_model

from app.domain.types import duration_to_ticks
from app.planning.backends.cp_sat.core_constraints import precheck_core_problem
from app.planning.problem.contracts import PlanningProblemDocumentV2


class CoreModelMetricsDocument(TypedDict):
    variables: int
    constraints: int
    optional_intervals: int


@dataclass(frozen=True)
class CoreOptionVariables:
    resource_id: str
    duration_seconds: int
    duration_ticks: int
    presence: cp_model.IntVar
    interval: cp_model.IntervalVar


@dataclass(frozen=True)
class CoreOperationVariables:
    operation_id: str
    start: cp_model.IntVar
    end: cp_model.IntVar
    options: tuple[CoreOptionVariables, ...]


@dataclass(frozen=True)
class CoreCpSatModel:
    model: cp_model.CpModel
    operations: tuple[CoreOperationVariables, ...]
    horizon_ticks: int
    model_build_seconds: float

    @property
    def metrics(self) -> CoreModelMetricsDocument:
        return {
            "variables": len(self.model.proto.variables),
            "constraints": len(self.model.proto.constraints),
            "optional_intervals": sum(
                len(operation.options) for operation in self.operations
            ),
        }


def build_core_model(problem: PlanningProblemDocumentV2) -> CoreCpSatModel:
    """Build the complete bounded core model without adding an objective."""

    started = perf_counter()
    precheck = precheck_core_problem(cast(dict[str, object], problem))
    horizon_ticks = precheck["horizon_ticks"]
    tick_seconds = problem["tick_seconds"]
    model = cp_model.CpModel()
    operations: list[CoreOperationVariables] = []
    intervals_by_resource: dict[str, list[cp_model.IntervalVar]] = {
        resource["resource_id"]: [] for resource in problem["resources"]
    }

    for operation_index, operation in enumerate(problem["operation_instances"]):
        start = model.new_int_var(
            0, horizon_ticks, f"op_{operation_index:06d}_start"
        )
        end = model.new_int_var(0, horizon_ticks, f"op_{operation_index:06d}_end")
        options: list[CoreOptionVariables] = []
        for option_index, option in enumerate(operation["resource_options"]):
            duration_seconds = option["final_duration_seconds"]
            duration_ticks = duration_to_ticks(duration_seconds, tick_seconds)
            presence = model.new_bool_var(
                f"op_{operation_index:06d}_option_{option_index:04d}_present"
            )
            interval = model.new_optional_interval_var(
                start,
                duration_ticks,
                end,
                presence,
                f"op_{operation_index:06d}_option_{option_index:04d}_interval",
            )
            option_variables = CoreOptionVariables(
                resource_id=option["resource_id"],
                duration_seconds=duration_seconds,
                duration_ticks=duration_ticks,
                presence=presence,
                interval=interval,
            )
            options.append(option_variables)
            intervals_by_resource[option["resource_id"]].append(interval)
        model.add_exactly_one(option.presence for option in options)
        operations.append(
            CoreOperationVariables(
                operation_id=operation["operation_id"],
                start=start,
                end=end,
                options=tuple(options),
            )
        )

    for resource_id in sorted(intervals_by_resource):
        intervals = intervals_by_resource[resource_id]
        if intervals:
            model.add_no_overlap(intervals)

    validation_error = model.validate()
    if validation_error:
        raise ValueError("Pinned CP-SAT rejected the constructed core model")
    return CoreCpSatModel(
        model=model,
        operations=tuple(operations),
        horizon_ticks=horizon_ticks,
        model_build_seconds=max(0.0, perf_counter() - started),
    )


__all__ = [
    "CoreCpSatModel",
    "CoreModelMetricsDocument",
    "CoreOperationVariables",
    "CoreOptionVariables",
    "build_core_model",
]
