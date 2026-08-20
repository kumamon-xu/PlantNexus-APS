"""Minimal semantic prechecks for the P0 schema contract skeleton.

This module checks only reference, UTC interval, and duration invariants needed
to make the skeleton unambiguous. Constraint C-001..C-011 rule-sheet behavior
and schedule validation remain owned by TASK-P0-04/TASK-P0-07.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.errors import ProductErrorCategory, ProductErrorCode, category_for_error_code
from app.domain.types import (
    ContractValueError,
    duration_to_ticks,
    parse_utc_instant,
    require_duration_seconds,
    require_tick_seconds,
)
from app.planning.problem.contracts import (
    PlanningProblemDocument,
    PlanningProblemDocumentV2,
)
from app.snapshots.contracts import PlanningSnapshotDocument


class ContractViolation(ValueError):
    """One deterministic semantic rejection from the P0 contract skeleton."""

    def __init__(self, code: ProductErrorCode, field: str, message: str) -> None:
        self.code = code.value
        self.category: ProductErrorCategory = category_for_error_code(code)
        self.field = field
        self.message = message
        super().__init__(f"{code} at {field}: {message}")


def _utc(value: str, field: str) -> datetime:
    try:
        return parse_utc_instant(value)
    except ContractValueError as error:
        raise ContractViolation(ProductErrorCode.INVALID_TIME, field, str(error)) from error


def _unique(values: list[str], field: str) -> set[str]:
    unique = set(values)
    if len(unique) != len(values):
        raise ContractViolation(ProductErrorCode.DUPLICATE_ID, field, "IDs must be unique")
    return unique


def validate_snapshot_contract(document: PlanningSnapshotDocument) -> None:
    """Validate UTC and Production/Simulation separation for one Snapshot."""

    _utc(document["cutoff_at"], "cutoff_at")
    scenario_id = document.get("scenario_id")
    if document["synthetic"] and not scenario_id:
        raise ContractViolation(
            ProductErrorCode.MISSING_SCENARIO_ID,
            "scenario_id",
            "synthetic Snapshot must identify its scenario",
        )
    if not document["synthetic"] and scenario_id is not None:
        raise ContractViolation(
            ProductErrorCode.SYNTHETIC_REFERENCE_IN_PRODUCTION,
            "scenario_id",
            "Production Snapshot must not reference a synthetic scenario",
        )
    if any(value < 0 for value in document["entity_counts"].values()):
        raise ContractViolation(
            ProductErrorCode.INVALID_ENTITY_COUNT,
            "entity_counts",
            "counts must be non-negative",
        )


def validate_planning_problem_contract(document: PlanningProblemDocument) -> None:
    """Validate P0 reference, UTC interval, lag, and duration invariants."""

    try:
        tick_seconds = int(require_tick_seconds(document["tick_seconds"]))
    except ContractValueError as error:
        raise ContractViolation(
            ProductErrorCode.INVALID_DURATION, "tick_seconds", str(error)
        ) from error

    horizon_start = _utc(document["horizon_start_utc"], "horizon_start_utc")
    horizon_end = _utc(document["horizon_end_utc"], "horizon_end_utc")
    if horizon_start >= horizon_end:
        raise ContractViolation(
            ProductErrorCode.INVALID_TIME_RANGE,
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
                    ProductErrorCode.MISSING_RUNNING_FACT,
                    f"operation_instances[{operation_index}]",
                    "RUNNING operation requires actual start, assigned resource, and remaining seconds",
                )
            _utc(
                actual_start,
                f"operation_instances[{operation_index}].actual_start_at_utc",
            )
            if assigned_resource not in resource_ids:
                raise ContractViolation(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"operation_instances[{operation_index}].assigned_resource_id",
                    "RUNNING assigned resource is absent from resource_ids",
                )
            try:
                require_duration_seconds(remaining_seconds, allow_zero=False)
            except ContractValueError as error:
                raise ContractViolation(
                    ProductErrorCode.INVALID_DURATION,
                    f"operation_instances[{operation_index}].remaining_seconds",
                    str(error),
                ) from error
        option_resource_ids: set[str] = set()
        for option_index, option in enumerate(operation["resource_options"]):
            option_field = f"operation_instances[{operation_index}].resource_options[{option_index}]"
            option_resource_ids.add(option["resource_id"])
            if option["resource_id"] not in resource_ids:
                raise ContractViolation(
                    ProductErrorCode.INVALID_REFERENCE,
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
                    ProductErrorCode.INVALID_DURATION, option_field, str(error)
                ) from error
        if operation["status"] == "RUNNING":
            assigned_resource = operation.get("assigned_resource_id")
            if assigned_resource not in option_resource_ids:
                raise ContractViolation(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"operation_instances[{operation_index}].assigned_resource_id",
                    "RUNNING assigned resource must be one of the operation resource options",
                )

    for edge_index, edge in enumerate(document["precedence_edges"]):
        edge_field = f"precedence_edges[{edge_index}]"
        for endpoint in ("predecessor_operation_id", "successor_operation_id"):
            if edge[endpoint] not in operation_ids:
                raise ContractViolation(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{edge_field}.{endpoint}",
                    "edge endpoint is absent from operation_instances",
                )
        if edge["predecessor_operation_id"] == edge["successor_operation_id"]:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                edge_field,
                "self-referencing precedence edge is invalid",
            )
        maximum = edge.get("max_lag_seconds")
        try:
            require_duration_seconds(edge["min_lag_seconds"])
            require_duration_seconds(edge["transport_lag_seconds"])
            if maximum is not None:
                require_duration_seconds(maximum)
        except ContractValueError as error:
            raise ContractViolation(
                ProductErrorCode.INVALID_DURATION, edge_field, str(error)
            ) from error
        if maximum is not None and maximum < edge["min_lag_seconds"]:
            raise ContractViolation(
                ProductErrorCode.INVALID_LAG_RANGE,
                f"{edge_field}.max_lag_seconds",
                "max lag must be greater than or equal to min lag",
            )

    for interval_index, interval in enumerate(document["resource_unavailable_intervals"]):
        interval_field = f"resource_unavailable_intervals[{interval_index}]"
        if interval["resource_id"] not in resource_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{interval_field}.resource_id",
                "unavailable interval resource is absent from resource_ids",
            )
        interval_start = _utc(interval["start_utc"], f"{interval_field}.start_utc")
        interval_end = _utc(interval["end_utc"], f"{interval_field}.end_utc")
        if interval_start >= interval_end:
            raise ContractViolation(
                ProductErrorCode.INVALID_TIME_RANGE,
                f"{interval_field}.end_utc",
                "interval end must be after interval start",
            )


def _non_empty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(
            ProductErrorCode.INVALID_REFERENCE,
            field,
            "value must be an explicit non-empty string",
        )


def validate_planning_problem_v2_contract(document: PlanningProblemDocumentV2) -> None:
    """Validate v2 references, sourced facts, intervals, lags, and durations."""

    try:
        tick_seconds = int(require_tick_seconds(document["tick_seconds"]))
    except ContractValueError as error:
        raise ContractViolation(
            ProductErrorCode.INVALID_DURATION, "tick_seconds", str(error)
        ) from error

    horizon_start = _utc(document["horizon_start_utc"], "horizon_start_utc")
    horizon_end = _utc(document["horizon_end_utc"], "horizon_end_utc")
    if horizon_start >= horizon_end:
        raise ContractViolation(
            ProductErrorCode.INVALID_TIME_RANGE,
            "horizon_end_utc",
            "horizon end must be after horizon start",
        )

    demand_ids = _unique(
        [demand["demand_order_id"] for demand in document["delivery_demands"]],
        "delivery_demands.demand_order_id",
    )
    for demand_index, demand in enumerate(document["delivery_demands"]):
        field = f"delivery_demands[{demand_index}]"
        _utc(demand["due_at_utc"], f"{field}.due_at_utc")
        if (
            isinstance(demand["priority_weight"], bool)
            or not isinstance(demand["priority_weight"], int)
            or demand["priority_weight"] < 1
        ):
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.priority_weight",
                "priority weight must be an explicit positive integer",
            )
        for source_field in (
            "due_source_system",
            "due_source_version",
            "due_source_record_id",
            "priority_source_system",
            "priority_source_version",
            "priority_source_record_id",
        ):
            _non_empty(demand[source_field], f"{field}.{source_field}")

    resource_ids = _unique(
        [resource["resource_id"] for resource in document["resources"]],
        "resources.resource_id",
    )
    resource_calendars: dict[str, str] = {}
    for resource_index, resource in enumerate(document["resources"]):
        field = f"resources[{resource_index}]"
        if type(resource["capacity"]) is not int or resource["capacity"] != 1:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.capacity",
                "v2 primary-resource capacity must be exactly integer 1",
            )
        for identity_field in (
            "resource_code",
            "resource_type",
            "status",
            "factory_id",
            "workshop_id",
            "production_line_id",
            "resource_group_id",
            "calendar_id",
        ):
            _non_empty(resource[identity_field], f"{field}.{identity_field}")
        _unique(resource["capabilities"], f"{field}.capabilities")
        for capability_index, capability in enumerate(resource["capabilities"]):
            _non_empty(capability, f"{field}.capabilities[{capability_index}]")
        resource_calendars[resource["resource_id"]] = resource["calendar_id"]

    operation_ids = _unique(
        [operation["operation_id"] for operation in document["operation_instances"]],
        "operation_instances.operation_id",
    )
    option_resources_by_operation: dict[str, set[str]] = {}
    for operation_index, operation in enumerate(document["operation_instances"]):
        field = f"operation_instances[{operation_index}]"
        if operation["demand_order_id"] not in demand_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.demand_order_id",
                "operation demand is absent from delivery_demands",
            )
        _utc(operation["release_at_utc"], f"{field}.release_at_utc")
        _utc(
            operation["material_ready_at_utc"],
            f"{field}.material_ready_at_utc",
        )
        _unique(operation["required_capabilities"], f"{field}.required_capabilities")
        option_resource_ids: list[str] = []
        for option_index, option in enumerate(operation["resource_options"]):
            option_field = f"{field}.resource_options[{option_index}]"
            resource_id = option["resource_id"]
            option_resource_ids.append(resource_id)
            if resource_id not in resource_ids:
                raise ContractViolation(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{option_field}.resource_id",
                    "candidate resource is absent from resources",
                )
            try:
                require_duration_seconds(option["setup_seconds"])
                require_duration_seconds(option["cycle_seconds_per_unit"])
                require_duration_seconds(
                    option["final_duration_seconds"], allow_zero=False
                )
                duration_to_ticks(option["final_duration_seconds"], tick_seconds)
            except ContractValueError as error:
                raise ContractViolation(
                    ProductErrorCode.INVALID_DURATION, option_field, str(error)
                ) from error
            _non_empty(option["duration_source"], f"{option_field}.duration_source")
            _non_empty(option["source_version"], f"{option_field}.source_version")
        if not option_resource_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.resource_options",
                "at least one candidate resource is required",
            )
        option_resources_by_operation[operation["operation_id"]] = _unique(
            option_resource_ids, f"{field}.resource_options.resource_id"
        )
        if operation["status"] == "RUNNING":
            actual_start = operation.get("actual_start_at_utc")
            assigned_resource = operation.get("assigned_resource_id")
            remaining_seconds = operation.get("remaining_seconds")
            if actual_start is None or assigned_resource is None or remaining_seconds is None:
                raise ContractViolation(
                    ProductErrorCode.MISSING_RUNNING_FACT,
                    field,
                    "RUNNING operation requires actual start, resource, and remainder",
                )
            _utc(actual_start, f"{field}.actual_start_at_utc")
            if assigned_resource not in option_resources_by_operation[operation["operation_id"]]:
                raise ContractViolation(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{field}.assigned_resource_id",
                    "RUNNING resource must be an operation candidate",
                )
            try:
                require_duration_seconds(remaining_seconds, allow_zero=False)
            except ContractValueError as error:
                raise ContractViolation(
                    ProductErrorCode.INVALID_DURATION,
                    f"{field}.remaining_seconds",
                    str(error),
                ) from error

    anchor_operation_ids = _unique(
        [anchor["operation_id"] for anchor in document["historical_completion_anchors"]],
        "historical_completion_anchors.operation_id",
    )
    _unique(
        [
            anchor["execution_fact_id"]
            for anchor in document["historical_completion_anchors"]
        ],
        "historical_completion_anchors.execution_fact_id",
    )
    if operation_ids & anchor_operation_ids:
        raise ContractViolation(
            ProductErrorCode.INVALID_REFERENCE,
            "historical_completion_anchors.operation_id",
            "historical and active operation sets must be disjoint",
        )
    for anchor_index, anchor in enumerate(document["historical_completion_anchors"]):
        field = f"historical_completion_anchors[{anchor_index}]"
        if anchor["resource_id"] not in resource_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.resource_id",
                "historical resource is absent from resources",
            )
        start = _utc(anchor["actual_start_at_utc"], f"{field}.actual_start_at_utc")
        end = _utc(anchor["actual_end_at_utc"], f"{field}.actual_end_at_utc")
        if start >= end or end > horizon_start:
            raise ContractViolation(
                ProductErrorCode.INVALID_TIME_RANGE,
                f"{field}.actual_end_at_utc",
                "historical completion must end no later than the Snapshot cutoff",
            )
        for source_field in ("source_system", "source_version", "source_record_id"):
            _non_empty(anchor[source_field], f"{field}.{source_field}")

    edge_ids = _unique(
        [edge["precedence_edge_id"] for edge in document["precedence_edges"]],
        "precedence_edges.precedence_edge_id",
    )
    del edge_ids
    logical_edges: list[str] = []
    valid_predecessors = operation_ids | anchor_operation_ids
    for edge_index, edge in enumerate(document["precedence_edges"]):
        field = f"precedence_edges[{edge_index}]"
        predecessor = edge["predecessor_operation_id"]
        successor = edge["successor_operation_id"]
        if predecessor not in valid_predecessors or successor not in operation_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                field,
                "edge must point from an active operation or historical anchor to an active operation",
            )
        if predecessor == successor:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE, field, "self edge is invalid"
            )
        logical_edges.append(f"{predecessor}\u0000{successor}")
        maximum = edge.get("max_lag_seconds")
        try:
            require_duration_seconds(edge["min_lag_seconds"])
            require_duration_seconds(edge["transport_lag_seconds"])
            if maximum is not None:
                require_duration_seconds(maximum)
        except ContractValueError as error:
            raise ContractViolation(
                ProductErrorCode.INVALID_DURATION, field, str(error)
            ) from error
        if maximum is not None and maximum < edge["min_lag_seconds"]:
            raise ContractViolation(
                ProductErrorCode.INVALID_LAG_RANGE,
                f"{field}.max_lag_seconds",
                "max lag must be greater than or equal to min lag",
            )
    _unique(logical_edges, "precedence_edges.logical_pair")

    _unique(
        [lock["lock_id"] for lock in document["operation_locks"]],
        "operation_locks.lock_id",
    )
    for lock_index, lock in enumerate(document["operation_locks"]):
        field = f"operation_locks[{lock_index}]"
        operation_id = lock["operation_id"]
        if operation_id not in operation_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.operation_id",
                "lock operation is absent from active operation_instances",
            )
        if lock["resource_id"] not in option_resources_by_operation[operation_id]:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.resource_id",
                "lock resource must be an operation candidate",
            )
        start = _utc(lock["start_at_utc"], f"{field}.start_at_utc")
        end = _utc(lock["end_at_utc"], f"{field}.end_at_utc")
        if start >= end or end <= horizon_start:
            raise ContractViolation(
                ProductErrorCode.INVALID_TIME_RANGE,
                f"{field}.end_at_utc",
                "v2 Problem contains only locks active after the Snapshot cutoff",
            )
        for source_field in ("source_system", "source_version", "source_record_id"):
            _non_empty(lock[source_field], f"{field}.{source_field}")

    interval_keys: list[str] = []
    for interval_index, interval in enumerate(document["resource_unavailable_intervals"]):
        field = f"resource_unavailable_intervals[{interval_index}]"
        resource_id = interval["resource_id"]
        if resource_id not in resource_ids:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.resource_id",
                "interval resource is absent from resources",
            )
        if interval["calendar_id"] != resource_calendars[resource_id]:
            raise ContractViolation(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.calendar_id",
                "interval calendar differs from the resource calendar",
            )
        start = _utc(interval["start_utc"], f"{field}.start_utc")
        end = _utc(interval["end_utc"], f"{field}.end_utc")
        if start >= end or start >= horizon_end or end <= horizon_start:
            raise ContractViolation(
                ProductErrorCode.INVALID_TIME_RANGE,
                field,
                "unavailable interval must intersect the planning horizon",
            )
        interval_keys.append(
            f"{resource_id}\u0000{interval['calendar_id']}\u0000{interval['start_utc']}\u0000{interval['end_utc']}"
        )
    _unique(interval_keys, "resource_unavailable_intervals")


__all__ = [
    "ContractViolation",
    "validate_planning_problem_contract",
    "validate_planning_problem_v2_contract",
    "validate_snapshot_contract",
]
