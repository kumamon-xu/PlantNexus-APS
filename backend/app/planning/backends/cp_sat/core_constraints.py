"""Fail-closed input boundary for the bounded P2-05/P2-06 model slice."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import NoReturn, TypedDict, cast

from app.domain.types import duration_to_ticks, format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.temporal_constraints import (
    ceil_seconds_to_ticks,
    floor_seconds_to_ticks,
)
from app.planning.contracts import DiagnosticDocument, SolverStatus
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import validate_built_problem_v2


CORE_CONSTRAINT_IDS = ("C-001", "C-003", "C-004", "C-010", "C-011")
_CP_SAT_INT_MAX = (1 << 63) - 1


class CoreModelReason(StrEnum):
    """Stable reasons for rejecting facts outside the bounded core model."""

    ZERO_RESOURCE_OPTIONS = "ZERO_RESOURCE_OPTIONS"
    DURATION_EXCEEDS_HORIZON = "DURATION_EXCEEDS_HORIZON"
    INVALID_HORIZON_TICKS = "INVALID_HORIZON_TICKS"
    UNSUPPORTED_PRECEDENCE_FACT = "UNSUPPORTED_PRECEDENCE_FACT"
    UNSUPPORTED_CALENDAR_FACT = "UNSUPPORTED_CALENDAR_FACT"
    UNSUPPORTED_RELEASE_MATERIAL_FACT = "UNSUPPORTED_RELEASE_MATERIAL_FACT"
    UNSUPPORTED_RUNNING_FACT = "UNSUPPORTED_RUNNING_FACT"
    UNSUPPORTED_LOCK_FACT = "UNSUPPORTED_LOCK_FACT"
    TEMPORAL_INSTANT_NOT_SECOND_PRECISION = "TEMPORAL_INSTANT_NOT_SECOND_PRECISION"
    TICK_VALUE_OUT_OF_RANGE = "TICK_VALUE_OUT_OF_RANGE"


class CoreModelInputError(ValueError):
    """Sanitized MODEL_INVALID rejection before a CP-SAT model is created."""

    code = "CP_SAT_CORE_MODEL_INPUT_ERROR"
    solver_status = SolverStatus.MODEL_INVALID

    def __init__(
        self,
        reason: CoreModelReason,
        *,
        field: str,
        entity_id: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        self.message = message
        super().__init__(f"{self.code}/{reason.value} at {field} ({entity_id}): {message}")

    def diagnostic(self) -> DiagnosticDocument:
        """Return a stable JSON-compatible diagnostic."""

        return {
            "code": f"{self.code}_{self.reason.value}",
            "message": self.message,
        }


class CorePrecheckDocument(TypedDict):
    horizon_ticks: int
    operation_count: int
    option_count: int
    resource_count: int


def _reject(
    reason: CoreModelReason,
    *,
    field: str,
    entity_id: str,
    message: str,
) -> NoReturn:
    raise CoreModelInputError(
        reason,
        field=field,
        entity_id=entity_id,
        message=message,
    )


def _reject_zero_options_before_contract(problem: Mapping[str, object]) -> None:
    """Keep the requested zero-candidate reason stable before general validation."""

    operations = problem.get("operation_instances")
    if not isinstance(operations, list):
        return
    for index, operation_value in enumerate(operations):
        if not isinstance(operation_value, Mapping):
            continue
        operation = cast(Mapping[str, object], operation_value)
        options = operation.get("resource_options")
        if isinstance(options, list) and not options:
            operation_id = str(operation.get("operation_id", f"index:{index}"))
            _reject(
                CoreModelReason.ZERO_RESOURCE_OPTIONS,
                field=f"operation_instances[{index}].resource_options",
                entity_id=operation_id,
                message="Core assignment requires at least one explicit resource option",
            )


def _require_second_precision(
    value: str,
    *,
    field: str,
    entity_id: str,
) -> None:
    parsed = parse_utc_instant(value)
    if format_utc_instant(parsed) != value:
        _reject(
            CoreModelReason.TEMPORAL_INSTANT_NOT_SECOND_PRECISION,
            field=field,
            entity_id=entity_id,
            message=(
                "CP-SAT temporal projection requires canonical whole-second UTC "
                "instants; sub-second values cannot be rounded silently"
            ),
        )


def _require_cp_sat_tick(
    value: int,
    *,
    field: str,
    entity_id: str,
) -> None:
    if value < -_CP_SAT_INT_MAX or value > _CP_SAT_INT_MAX:
        _reject(
            CoreModelReason.TICK_VALUE_OUT_OF_RANGE,
            field=field,
            entity_id=entity_id,
            message="A temporal bound exceeds the pinned CP-SAT integer domain",
        )


def precheck_core_problem(
    problem: Mapping[str, object],
) -> CorePrecheckDocument:
    """Validate represented facts and reject still-deferred P2-07 facts."""

    _reject_zero_options_before_contract(problem)
    validate_built_problem_v2(problem)
    typed_problem = cast(PlanningProblemDocumentV2, problem)
    snapshot_id = typed_problem["snapshot_id"]
    _require_second_precision(
        typed_problem["horizon_start_utc"],
        field="horizon_start_utc",
        entity_id=snapshot_id,
    )
    _require_second_precision(
        typed_problem["horizon_end_utc"],
        field="horizon_end_utc",
        entity_id=snapshot_id,
    )
    horizon_start = parse_utc_instant(typed_problem["horizon_start_utc"])
    horizon_end = parse_utc_instant(typed_problem["horizon_end_utc"])
    tick_seconds = typed_problem["tick_seconds"]
    horizon_seconds = int((horizon_end - horizon_start).total_seconds())
    horizon_ticks = horizon_seconds // tick_seconds
    if horizon_ticks < 1:
        _reject(
            CoreModelReason.INVALID_HORIZON_TICKS,
            field="horizon_end_utc",
            entity_id=snapshot_id,
            message="Planning horizon contains no complete positive solver tick",
        )

    if typed_problem["operation_locks"]:
        _reject(
            CoreModelReason.UNSUPPORTED_LOCK_FACT,
            field="operation_locks",
            entity_id=snapshot_id,
            message="HARD and SOFT lock constraints are reserved for TASK-P2-07",
        )

    option_count = 0
    for operation_index, operation in enumerate(typed_problem["operation_instances"]):
        operation_id = operation["operation_id"]
        if operation["status"] == "RUNNING":
            _reject(
                CoreModelReason.UNSUPPORTED_RUNNING_FACT,
                field=f"operation_instances[{operation_index}].status",
                entity_id=operation_id,
                message="RUNNING execution facts are reserved for TASK-P2-07",
            )
        _require_second_precision(
            operation["release_at_utc"],
            field=f"operation_instances[{operation_index}].release_at_utc",
            entity_id=operation_id,
        )
        _require_second_precision(
            operation["material_ready_at_utc"],
            field=f"operation_instances[{operation_index}].material_ready_at_utc",
            entity_id=operation_id,
        )
        options = operation["resource_options"]
        option_count += len(options)
        for option_index, option in enumerate(options):
            duration_ticks = duration_to_ticks(
                option["final_duration_seconds"], tick_seconds
            )
            if duration_ticks > horizon_ticks:
                _reject(
                    CoreModelReason.DURATION_EXCEEDS_HORIZON,
                    field=(
                        f"operation_instances[{operation_index}]."
                        f"resource_options[{option_index}].final_duration_seconds"
                    ),
                    entity_id=operation_id,
                    message=(
                        "A resource option cannot fit wholly inside the planning "
                        "horizon; silent truncation or option removal is forbidden"
                    ),
                )

    for anchor_index, anchor in enumerate(
        typed_problem["historical_completion_anchors"]
    ):
        for field_name in ("actual_start_at_utc", "actual_end_at_utc"):
            _require_second_precision(
                anchor[field_name],
                field=f"historical_completion_anchors[{anchor_index}].{field_name}",
                entity_id=anchor["operation_id"],
            )

    for edge_index, edge in enumerate(typed_problem["precedence_edges"]):
        edge_id = edge["precedence_edge_id"]
        _require_cp_sat_tick(
            ceil_seconds_to_ticks(edge["min_lag_seconds"], tick_seconds),
            field=f"precedence_edges[{edge_index}].min_lag_seconds",
            entity_id=edge_id,
        )
        _require_cp_sat_tick(
            ceil_seconds_to_ticks(edge["transport_lag_seconds"], tick_seconds),
            field=f"precedence_edges[{edge_index}].transport_lag_seconds",
            entity_id=edge_id,
        )
        maximum = edge.get("max_lag_seconds")
        if maximum is not None:
            _require_cp_sat_tick(
                floor_seconds_to_ticks(maximum, tick_seconds),
                field=f"precedence_edges[{edge_index}].max_lag_seconds",
                entity_id=edge_id,
            )

    for interval_index, interval in enumerate(
        typed_problem["resource_unavailable_intervals"]
    ):
        for field_name in ("start_utc", "end_utc"):
            _require_second_precision(
                interval[field_name],
                field=f"resource_unavailable_intervals[{interval_index}].{field_name}",
                entity_id=interval["resource_id"],
            )

    return {
        "horizon_ticks": horizon_ticks,
        "operation_count": len(typed_problem["operation_instances"]),
        "option_count": option_count,
        "resource_count": len(typed_problem["resources"]),
    }


__all__ = [
    "CORE_CONSTRAINT_IDS",
    "CoreModelInputError",
    "CoreModelReason",
    "CorePrecheckDocument",
    "precheck_core_problem",
]
