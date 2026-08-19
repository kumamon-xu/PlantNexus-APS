"""Serializable, solver-neutral PlanningProblem JSON contract types."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class OperationResourceOptionDocument(TypedDict):
    resource_id: str
    setup_seconds: int
    cycle_seconds_per_unit: int
    final_duration_seconds: int
    duration_source: str
    source_version: str


class OperationInstanceDocument(TypedDict):
    operation_id: str
    status: Literal["NOT_STARTED", "RUNNING"]
    release_at_utc: str
    material_ready_at_utc: str
    resource_options: list[OperationResourceOptionDocument]
    actual_start_at_utc: NotRequired[str]
    assigned_resource_id: NotRequired[str]
    remaining_seconds: NotRequired[int]


class PrecedenceEdgeDocument(TypedDict):
    predecessor_operation_id: str
    successor_operation_id: str
    min_lag_seconds: int
    transport_lag_seconds: int
    max_lag_seconds: NotRequired[int]


class ResourceUnavailableIntervalDocument(TypedDict):
    resource_id: str
    start_utc: str
    end_utc: str


class PlanningProblemDocument(TypedDict):
    problem_version: Literal["planning-problem.v1"]
    snapshot_id: str
    problem_builder_version: str
    problem_hash: str
    tick_seconds: int
    horizon_start_utc: str
    horizon_end_utc: str
    resource_ids: list[str]
    operation_instances: list[OperationInstanceDocument]
    precedence_edges: list[PrecedenceEdgeDocument]
    resource_unavailable_intervals: list[ResourceUnavailableIntervalDocument]
    required_capabilities: list[str]


__all__ = [
    "OperationInstanceDocument",
    "OperationResourceOptionDocument",
    "PlanningProblemDocument",
    "PrecedenceEdgeDocument",
    "ResourceUnavailableIntervalDocument",
]
