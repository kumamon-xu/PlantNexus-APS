"""Serializable, solver-neutral PlanningProblem JSON contract types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Literal, NotRequired, TypedDict, cast

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


class PlanningProblemErrorCode(StrEnum):
    """Stable, module-local rejection codes for the Problem boundary."""

    INVALID_SNAPSHOT = "INVALID_SNAPSHOT"
    INVALID_BUILDER_VERSION = "INVALID_BUILDER_VERSION"
    INVALID_BUILD_CONFIG = "INVALID_BUILD_CONFIG"
    MISSING_PROBLEM_FACT = "MISSING_PROBLEM_FACT"
    UNSUPPORTED_PROBLEM_FACT = "UNSUPPORTED_PROBLEM_FACT"
    MODEL_INVALID = "MODEL_INVALID"
    HASH_MISMATCH = "HASH_MISMATCH"


_ERROR_CATEGORY_BY_CODE = {
    PlanningProblemErrorCode.INVALID_SNAPSHOT: ProductErrorCategory.DATA_ERROR,
    PlanningProblemErrorCode.INVALID_BUILDER_VERSION: ProductErrorCategory.DATA_ERROR,
    PlanningProblemErrorCode.INVALID_BUILD_CONFIG: ProductErrorCategory.DATA_ERROR,
    PlanningProblemErrorCode.MISSING_PROBLEM_FACT: ProductErrorCategory.DATA_ERROR,
    PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT: (
        ProductErrorCategory.UNSUPPORTED_CAPABILITY
    ),
    PlanningProblemErrorCode.MODEL_INVALID: ProductErrorCategory.MODEL_INVALID,
    PlanningProblemErrorCode.HASH_MISMATCH: ProductErrorCategory.MODEL_INVALID,
}


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
        self.category = _ERROR_CATEGORY_BY_CODE[code]
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


__all__ = [
    "ImmutablePlanningProblem",
    "OperationInstanceDocument",
    "OperationResourceOptionDocument",
    "PlanningProblemDocument",
    "PlanningProblemError",
    "PlanningProblemErrorCode",
    "PrecedenceEdgeDocument",
    "ResourceUnavailableIntervalDocument",
]
