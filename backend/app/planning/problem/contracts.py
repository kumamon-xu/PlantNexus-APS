"""Serializable, solver-neutral PlanningProblem JSON contract types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict, cast

if TYPE_CHECKING:
    from app.domain.errors import ProductErrorCategory


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


class DemandPriorityInput(TypedDict):
    """Explicit, versioned priority fact supplied to the v2 builder."""

    priority_weight: int
    source_system: str
    source_version: str
    source_record_id: str


class DeliveryDemandDocument(TypedDict):
    demand_order_id: str
    due_at_utc: str
    due_source_system: str
    due_source_version: str
    due_source_record_id: str
    priority_weight: int
    priority_source_system: str
    priority_source_version: str
    priority_source_record_id: str


class ResourceDocumentV2(TypedDict):
    resource_id: str
    resource_code: str
    resource_type: str
    status: str
    factory_id: str
    workshop_id: str
    production_line_id: str
    resource_group_id: str
    calendar_id: str
    capabilities: list[str]
    capacity: Literal[1]


class OperationInstanceDocumentV2(TypedDict):
    operation_id: str
    demand_order_id: str
    status: Literal["NOT_STARTED", "RUNNING"]
    release_at_utc: str
    material_ready_at_utc: str
    required_capabilities: list[str]
    resource_options: list[OperationResourceOptionDocument]
    actual_start_at_utc: NotRequired[str]
    assigned_resource_id: NotRequired[str]
    remaining_seconds: NotRequired[int]


class HistoricalCompletionAnchorDocument(TypedDict):
    operation_id: str
    execution_fact_id: str
    resource_id: str
    actual_start_at_utc: str
    actual_end_at_utc: str
    source_system: str
    source_version: str
    source_record_id: str


class PrecedenceEdgeDocumentV2(TypedDict):
    precedence_edge_id: str
    predecessor_operation_id: str
    successor_operation_id: str
    min_lag_seconds: int
    transport_lag_seconds: int
    max_lag_seconds: NotRequired[int]


class OperationLockDocumentV2(TypedDict):
    lock_id: str
    operation_id: str
    lock_type: Literal["HARD_LOCK", "SOFT_LOCK"]
    resource_id: str
    start_at_utc: str
    end_at_utc: str
    source_system: str
    source_version: str
    source_record_id: str


class ResourceUnavailableIntervalDocumentV2(TypedDict):
    calendar_id: str
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


class PlanningProblemDocumentV2(TypedDict):
    problem_version: Literal["planning-problem.v2"]
    schema_set_version: Literal["2.3.0"]
    snapshot_id: str
    problem_builder_version: Literal["planning-problem-builder.v2"]
    problem_hash: str
    canonicalization_version: Literal["canonical-json.v1"]
    problem_hash_projection_version: Literal["planning-problem-hash-projection.v2"]
    tick_seconds: int
    horizon_start_utc: str
    horizon_end_utc: str
    delivery_demands: list[DeliveryDemandDocument]
    resources: list[ResourceDocumentV2]
    operation_instances: list[OperationInstanceDocumentV2]
    historical_completion_anchors: list[HistoricalCompletionAnchorDocument]
    precedence_edges: list[PrecedenceEdgeDocumentV2]
    operation_locks: list[OperationLockDocumentV2]
    resource_unavailable_intervals: list[ResourceUnavailableIntervalDocumentV2]
    required_capabilities: list[str]


class PlanningProblemErrorCode(StrEnum):
    """Stable, module-local rejection codes for the Problem boundary."""

    INVALID_SNAPSHOT = "INVALID_SNAPSHOT"
    INVALID_BUILDER_VERSION = "INVALID_BUILDER_VERSION"
    INVALID_BUILD_CONFIG = "INVALID_BUILD_CONFIG"
    MISSING_PROBLEM_FACT = "MISSING_PROBLEM_FACT"
    INVALID_PRIORITY_FACT = "INVALID_PRIORITY_FACT"
    INVALID_LOCK_FACT = "INVALID_LOCK_FACT"
    INVALID_HISTORICAL_FACT = "INVALID_HISTORICAL_FACT"
    UNSUPPORTED_PROBLEM_FACT = "UNSUPPORTED_PROBLEM_FACT"
    MODEL_INVALID = "MODEL_INVALID"
    HASH_MISMATCH = "HASH_MISMATCH"


def _error_category_for(code: PlanningProblemErrorCode) -> ProductErrorCategory:
    """Resolve the domain enum lazily so direct Problem CLI imports stay acyclic."""

    from app.domain.errors import ProductErrorCategory

    if code is PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT:
        return ProductErrorCategory.UNSUPPORTED_CAPABILITY
    if code in {
        PlanningProblemErrorCode.MODEL_INVALID,
        PlanningProblemErrorCode.HASH_MISMATCH,
    }:
        return ProductErrorCategory.MODEL_INVALID
    return ProductErrorCategory.DATA_ERROR


class PlanningProblemError(ValueError):
    """A deterministic, sanitized rejection from Problem construction."""

    def __init__(
        self,
        code: PlanningProblemErrorCode,
        *,
        field: str,
        entity_id: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.code = code
        self.category = _error_category_for(code)
        self.field = field
        self.entity_id = entity_id
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(
            f"{self.category.value}/{code.value} at {field} ({entity_id}): {message}"
        )


@dataclass(frozen=True)
class ImmutablePlanningProblem:
    """A PlanningProblem value backed only by canonical JSON bytes."""

    canonical_bytes: bytes
    problem_hash: str
    snapshot_id: str
    problem_builder_version: str

    @property
    def document(self) -> PlanningProblemDocument:
        decoded = json.loads(self.canonical_bytes)
        return cast(PlanningProblemDocument, decoded)


@dataclass(frozen=True)
class ImmutablePlanningProblemV2:
    """A v2 PlanningProblem value backed only by canonical JSON bytes."""

    canonical_bytes: bytes
    problem_hash: str
    snapshot_id: str
    problem_builder_version: str

    @property
    def document(self) -> PlanningProblemDocumentV2:
        decoded = json.loads(self.canonical_bytes)
        return cast(PlanningProblemDocumentV2, decoded)


__all__ = [
    "DeliveryDemandDocument",
    "DemandPriorityInput",
    "HistoricalCompletionAnchorDocument",
    "ImmutablePlanningProblem",
    "ImmutablePlanningProblemV2",
    "OperationInstanceDocumentV2",
    "OperationLockDocumentV2",
    "OperationInstanceDocument",
    "OperationResourceOptionDocument",
    "PlanningProblemDocument",
    "PlanningProblemDocumentV2",
    "PlanningProblemError",
    "PlanningProblemErrorCode",
    "PrecedenceEdgeDocument",
    "PrecedenceEdgeDocumentV2",
    "ResourceDocumentV2",
    "ResourceUnavailableIntervalDocument",
    "ResourceUnavailableIntervalDocumentV2",
]
