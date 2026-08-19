"""Pure FactoryProfile v1 shape and semantic precheck.

Factory profiles are synthetic configuration assets. They never provide
production defaults or authoritative factory facts.
"""

from __future__ import annotations

import re
from typing import Literal, TypedDict

from app.domain.capabilities import (
    CAPABILITY_STATUS_BY_NAME,
    CapabilityName,
    CapabilityStatus,
)
from app.domain.types import ContractValueError, canonical_id


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class IntegerRangeDocument(TypedDict):
    minimum: int
    maximum: int


class RatioRangeDocument(TypedDict):
    minimum: float
    maximum: float


class TopologyProfileDocument(TypedDict):
    workshop_count: IntegerRangeDocument
    production_line_count: IntegerRangeDocument


class ResourceProfileDocument(TypedDict):
    target_count: IntegerRangeDocument
    capacity_per_resource: Literal[1]
    capability_pool: list[str]


class RoutingProfileDocument(TypedDict):
    operation_count: IntegerRangeDocument
    candidate_resource_count: IntegerRangeDocument
    routing_depth: IntegerRangeDocument
    cross_workshop_ratio: RatioRangeDocument


class CalendarProfileDocument(TypedDict):
    pattern_ids: list[str]
    fragmentation_count: IntegerRangeDocument


class OrderProfileDocument(TypedDict):
    order_count: IntegerRangeDocument
    due_date_pressure_levels: list[Literal["low", "medium", "high"]]


class FactoryProfileDocument(TypedDict):
    profile_contract_version: Literal["factory-profile.v1"]
    profile_id: str
    profile_version: str
    synthetic_only: Literal[True]
    topology: TopologyProfileDocument
    resources: ResourceProfileDocument
    routing: RoutingProfileDocument
    calendar: CalendarProfileDocument
    orders: OrderProfileDocument
    supported_capabilities: list[str]
    expected_rejections: list[str]


class FactoryProfileContractError(ValueError):
    """A FactoryProfile cannot satisfy the synthetic v1 contract."""


def _require_semver(value: str, location: str) -> None:
    if not isinstance(value, str) or _SEMVER_RE.fullmatch(value) is None:
        raise FactoryProfileContractError(f"{location} must be semantic version text")


def _require_integer_range(
    value: IntegerRangeDocument, location: str, *, minimum: int
) -> None:
    lower = value["minimum"]
    upper = value["maximum"]
    if (
        isinstance(lower, bool)
        or isinstance(upper, bool)
        or not isinstance(lower, int)
        or not isinstance(upper, int)
        or lower < minimum
        or upper < lower
    ):
        raise FactoryProfileContractError(
            f"{location} must have integer {minimum} <= minimum <= maximum"
        )


def _require_ratio_range(value: RatioRangeDocument, location: str) -> None:
    lower = value["minimum"]
    upper = value["maximum"]
    if (
        isinstance(lower, bool)
        or isinstance(upper, bool)
        or not isinstance(lower, (int, float))
        or not isinstance(upper, (int, float))
        or not 0 <= lower <= upper <= 1
    ):
        raise FactoryProfileContractError(
            f"{location} must satisfy 0 <= minimum <= maximum <= 1"
        )


def _capabilities(values: list[str], location: str) -> tuple[CapabilityName, ...]:
    if len(values) != len(set(values)):
        raise FactoryProfileContractError(f"{location} contains duplicates")
    try:
        return tuple(CapabilityName(value) for value in values)
    except ValueError as error:
        raise FactoryProfileContractError(
            f"{location} contains an unregistered capability"
        ) from error


def validate_factory_profile_contract(profile: FactoryProfileDocument) -> None:
    """Validate cross-field semantics that JSON Schema cannot compare."""

    if profile["profile_contract_version"] != "factory-profile.v1":
        raise FactoryProfileContractError("unexpected FactoryProfile contract version")
    if profile["synthetic_only"] is not True:
        raise FactoryProfileContractError("FactoryProfile must be synthetic_only=true")
    try:
        canonical_id(profile["profile_id"])
        for pattern_id in profile["calendar"]["pattern_ids"]:
            canonical_id(pattern_id)
    except ContractValueError as error:
        raise FactoryProfileContractError(str(error)) from error
    _require_semver(profile["profile_version"], "profile_version")

    _require_integer_range(profile["topology"]["workshop_count"], "workshop_count", minimum=1)
    _require_integer_range(
        profile["topology"]["production_line_count"],
        "production_line_count",
        minimum=1,
    )
    _require_integer_range(profile["resources"]["target_count"], "target_count", minimum=1)
    _require_integer_range(profile["routing"]["operation_count"], "operation_count", minimum=1)
    _require_integer_range(
        profile["routing"]["candidate_resource_count"],
        "candidate_resource_count",
        minimum=1,
    )
    _require_integer_range(profile["routing"]["routing_depth"], "routing_depth", minimum=1)
    _require_integer_range(
        profile["calendar"]["fragmentation_count"],
        "fragmentation_count",
        minimum=0,
    )
    _require_integer_range(profile["orders"]["order_count"], "order_count", minimum=1)
    _require_ratio_range(profile["routing"]["cross_workshop_ratio"], "cross_workshop_ratio")
    if profile["resources"]["capacity_per_resource"] != 1:
        raise FactoryProfileContractError("P0 profile capacity_per_resource must equal 1")
    if not profile["calendar"]["pattern_ids"]:
        raise FactoryProfileContractError("calendar.pattern_ids must not be empty")
    if not profile["orders"]["due_date_pressure_levels"]:
        raise FactoryProfileContractError("due_date_pressure_levels must not be empty")

    pool = _capabilities(profile["resources"]["capability_pool"], "capability_pool")
    supported = _capabilities(profile["supported_capabilities"], "supported_capabilities")
    rejected = _capabilities(profile["expected_rejections"], "expected_rejections")
    if any(
        CAPABILITY_STATUS_BY_NAME[name] is not CapabilityStatus.V1_SUPPORTED
        for name in (*pool, *supported)
    ):
        raise FactoryProfileContractError(
            "capability_pool and supported_capabilities must be V1_SUPPORTED"
        )
    if any(
        CAPABILITY_STATUS_BY_NAME[name] is CapabilityStatus.V1_SUPPORTED
        for name in rejected
    ):
        raise FactoryProfileContractError(
            "expected_rejections must contain only unavailable capabilities"
        )
    if set(supported) & set(rejected):
        raise FactoryProfileContractError(
            "supported_capabilities and expected_rejections must be disjoint"
        )


__all__ = [
    "FactoryProfileContractError",
    "FactoryProfileDocument",
    "IntegerRangeDocument",
    "RatioRangeDocument",
    "validate_factory_profile_contract",
]
