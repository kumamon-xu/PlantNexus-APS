"""Minimal semantic prechecks for the P0 schema contract skeleton.

This module checks only reference, UTC interval, and duration invariants needed
to make the skeleton unambiguous. Constraint C-001..C-011 rule-sheet behavior
and schedule validation remain owned by TASK-P0-04/TASK-P0-07.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.types import (
    ContractValueError,
    duration_to_ticks,
    parse_utc_instant,
    require_duration_seconds,
    require_tick_seconds,
)
from app.planning.problem.contracts import PlanningProblemDocument
from app.snapshots.contracts import PlanningSnapshotDocument


class ContractViolation(ValueError):
    """One deterministic semantic rejection from the P0 contract skeleton."""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code} at {field}: {message}")


def _utc(value: str, field: str) -> datetime:
    try:
        return parse_utc_instant(value)
    except ContractValueError as error:
        raise ContractViolation("INVALID_TIME", field, str(error)) from error


def _unique(values: list[str], field: str) -> set[str]:
    unique = set(values)
    if len(unique) != len(values):
        raise ContractViolation("DUPLICATE_ID", field, "IDs must be unique")
    return unique


def validate_snapshot_contract(document: PlanningSnapshotDocument) -> None:
    """Validate UTC and Production/Simulation separation for one Snapshot."""

    _utc(document["cutoff_at"], "cutoff_at")
    scenario_id = document.get("scenario_id")
    if document["synthetic"] and not scenario_id:
        raise ContractViolation(
            "MISSING_SCENARIO_ID",
            "scenario_id",
            "synthetic Snapshot must identify its scenario",
        )
    if not document["synthetic"] and scenario_id is not None:
        raise ContractViolation(
            "SYNTHETIC_REFERENCE_IN_PRODUCTION",
            "scenario_id",
            "Production Snapshot must not reference a synthetic scenario",
        )
    if any(value < 0 for value in document["entity_counts"].values()):
        raise ContractViolation(
            "INVALID_ENTITY_COUNT", "entity_counts", "counts must be non-negative"
        )


def validate_planning_problem_contract(document: PlanningProblemDocument) -> None:
    """Validate P0 reference, UTC interval, lag, and duration invariants."""

    try:
        tick_seconds = int(require_tick_seconds(document["tick_seconds"]))
    except ContractValueError as error:
        raise ContractViolation("INVALID_DURATION", "tick_seconds", str(error)) from error

    horizon_start = _utc(document["horizon_start_utc"], "horizon_start_utc")
    horizon_end = _utc(document["horizon_end_utc"], "horizon_end_utc")
    if horizon_start >= horizon_end:
        raise ContractViolation(
            "INVALID_TIME_RANGE",
            "horizon_end_utc",
            "horizon end must be after horizon start",
        )

    resource_ids = _unique(document["resource_ids"], "resource_ids")
    operation_ids = _unique(
        [operation["operation_id"] for operation in document["operation_instances"]],
        "operation_instances.operation_id",
    )

    for operation_index, operation in enumerate(document["operation_instances"]):
        _utc(operation["release_at_utc"], f"operation_instances[{operation_index}].release_at_utc")
        _utc(
            operation["material_ready_at_utc"],
            f"operation_instances[{operation_index}].material_ready_at_utc",
        )
        if operation["status"] == "RUNNING":
            actual_start = operation.get("actual_start_at_utc")
            assigned_resource = operation.get("assigned_resource_id")
            remaining_seconds = operation.get("remaining_seconds")
            if actual_start is None or assigned_resource is None or remaining_seconds is None:
                raise ContractViolation(
                    "MISSING_RUNNING_FACT",
                    f"operation_instances[{operation_index}]",
                    "RUNNING operation requires actual start, assigned resource, and remaining seconds",
                )
            _utc(
                actual_start,
                f"operation_instances[{operation_index}].actual_start_at_utc",
            )
            if assigned_resource not in resource_ids:
                raise ContractViolation(
                    "INVALID_REFERENCE",
                    f"operation_instances[{operation_index}].assigned_resource_id",
                    "RUNNING assigned resource is absent from resource_ids",
                )
            try:
                require_duration_seconds(remaining_seconds, allow_zero=False)
            except ContractValueError as error:
                raise ContractViolation(
                    "INVALID_DURATION",
                    f"operation_instances[{operation_index}].remaining_seconds",
                    str(error),
                ) from error
        option_resource_ids: set[str] = set()
        for option_index, option in enumerate(operation["resource_options"]):
            option_field = f"operation_instances[{operation_index}].resource_options[{option_index}]"
            option_resource_ids.add(option["resource_id"])
            if option["resource_id"] not in resource_ids:
                raise ContractViolation(
                    "INVALID_REFERENCE",
                    f"{option_field}.resource_id",
                    "candidate resource is absent from resource_ids",
                )
            try:
                require_duration_seconds(option["setup_seconds"])
                require_duration_seconds(option["cycle_seconds_per_unit"])
                require_duration_seconds(option["final_duration_seconds"], allow_zero=False)
                duration_to_ticks(option["final_duration_seconds"], tick_seconds)
            except ContractValueError as error:
                raise ContractViolation(
                    "INVALID_DURATION", option_field, str(error)
                ) from error
        if operation["status"] == "RUNNING":
            assigned_resource = operation.get("assigned_resource_id")
            if assigned_resource not in option_resource_ids:
                raise ContractViolation(
                    "INVALID_REFERENCE",
                    f"operation_instances[{operation_index}].assigned_resource_id",
                    "RUNNING assigned resource must be one of the operation resource options",
                )

    for edge_index, edge in enumerate(document["precedence_edges"]):
        edge_field = f"precedence_edges[{edge_index}]"
        for endpoint in ("predecessor_operation_id", "successor_operation_id"):
            if edge[endpoint] not in operation_ids:
                raise ContractViolation(
                    "INVALID_REFERENCE",
                    f"{edge_field}.{endpoint}",
                    "edge endpoint is absent from operation_instances",
                )
        if edge["predecessor_operation_id"] == edge["successor_operation_id"]:
            raise ContractViolation(
                "INVALID_REFERENCE", edge_field, "self-referencing precedence edge is invalid"
            )
        maximum = edge.get("max_lag_seconds")
        try:
            require_duration_seconds(edge["min_lag_seconds"])
            require_duration_seconds(edge["transport_lag_seconds"])
            if maximum is not None:
                require_duration_seconds(maximum)
        except ContractValueError as error:
            raise ContractViolation("INVALID_DURATION", edge_field, str(error)) from error
        if maximum is not None and maximum < edge["min_lag_seconds"]:
            raise ContractViolation(
                "INVALID_LAG_RANGE",
                f"{edge_field}.max_lag_seconds",
                "max lag must be greater than or equal to min lag",
            )

    for interval_index, interval in enumerate(document["resource_unavailable_intervals"]):
        interval_field = f"resource_unavailable_intervals[{interval_index}]"
        if interval["resource_id"] not in resource_ids:
            raise ContractViolation(
                "INVALID_REFERENCE",
                f"{interval_field}.resource_id",
                "unavailable interval resource is absent from resource_ids",
            )
        interval_start = _utc(interval["start_utc"], f"{interval_field}.start_utc")
        interval_end = _utc(interval["end_utc"], f"{interval_field}.end_utc")
        if interval_start >= interval_end:
            raise ContractViolation(
                "INVALID_TIME_RANGE",
                f"{interval_field}.end_utc",
                "interval end must be after interval start",
            )


__all__ = [
    "ContractViolation",
    "validate_planning_problem_contract",
    "validate_snapshot_contract",
]
