"""Pure capability registry and explicit unsupported-capability precheck."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType

from app.domain.errors import (
    ProductErrorCategory,
    ProductErrorCode,
    category_for_error_code,
)


class CapabilityStatus(StrEnum):
    V1_SUPPORTED = "V1_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    DEFERRED = "DEFERRED"


class CapabilityName(StrEnum):
    SINGLE_FACTORY_MULTI_WORKSHOP = "SINGLE_FACTORY_MULTI_WORKSHOP"
    DAG_ROUTING = "DAG_ROUTING"
    ALTERNATIVE_RESOURCE = "ALTERNATIVE_RESOURCE"
    MACHINE_CALENDAR = "MACHINE_CALENDAR"
    RELEASE_AND_MATERIAL_GATE = "RELEASE_AND_MATERIAL_GATE"
    RUNNING_OPERATION = "RUNNING_OPERATION"
    HARD_SOFT_LOCK = "HARD_SOFT_LOCK"
    APPROVAL_AND_PUBLICATION = "APPROVAL_AND_PUBLICATION"
    DYNAMIC_REPLANNING = "DYNAMIC_REPLANNING"
    SECONDARY_CAPACITY = "SECONDARY_CAPACITY"
    SEQUENCE_DEPENDENT_SETUP = "SEQUENCE_DEPENDENT_SETUP"
    BATCH_PROCESSING = "BATCH_PROCESSING"
    SPLIT_MERGE = "SPLIT_MERGE"
    MATERIAL_COMPETITION = "MATERIAL_COMPETITION"
    PREEMPTIVE_OPERATION = "PREEMPTIVE_OPERATION"
    BUFFER_CAPACITY = "BUFFER_CAPACITY"
    ALTERNATIVE_MATERIAL = "ALTERNATIVE_MATERIAL"
    MULTI_FACTORY = "MULTI_FACTORY"
    AI_DURATION_PREDICTION = "AI_DURATION_PREDICTION"
    REALITY_CALIBRATION = "REALITY_CALIBRATION"


_V1_SUPPORTED = (
    CapabilityName.SINGLE_FACTORY_MULTI_WORKSHOP,
    CapabilityName.DAG_ROUTING,
    CapabilityName.ALTERNATIVE_RESOURCE,
    CapabilityName.MACHINE_CALENDAR,
    CapabilityName.RELEASE_AND_MATERIAL_GATE,
    CapabilityName.RUNNING_OPERATION,
    CapabilityName.HARD_SOFT_LOCK,
    CapabilityName.APPROVAL_AND_PUBLICATION,
    CapabilityName.DYNAMIC_REPLANNING,
)
_UNSUPPORTED = (
    CapabilityName.SECONDARY_CAPACITY,
    CapabilityName.SEQUENCE_DEPENDENT_SETUP,
    CapabilityName.BATCH_PROCESSING,
    CapabilityName.SPLIT_MERGE,
    CapabilityName.MATERIAL_COMPETITION,
    CapabilityName.PREEMPTIVE_OPERATION,
    CapabilityName.BUFFER_CAPACITY,
    CapabilityName.ALTERNATIVE_MATERIAL,
    CapabilityName.MULTI_FACTORY,
)
_DEFERRED = (
    CapabilityName.AI_DURATION_PREDICTION,
    CapabilityName.REALITY_CALIBRATION,
)

CAPABILITY_STATUS_BY_NAME: Mapping[CapabilityName, CapabilityStatus] = MappingProxyType(
    {
        **{name: CapabilityStatus.V1_SUPPORTED for name in _V1_SUPPORTED},
        **{name: CapabilityStatus.UNSUPPORTED for name in _UNSUPPORTED},
        **{name: CapabilityStatus.DEFERRED for name in _DEFERRED},
    }
)


class CapabilityContractError(ValueError):
    """A capability declaration is invalid or explicitly unavailable in V1."""

    def __init__(self, code: ProductErrorCode, capability_names: Iterable[str]) -> None:
        self.code = code
        self.category: ProductErrorCategory = category_for_error_code(code)
        self.capability_names = tuple(sorted(capability_names))
        joined = ", ".join(self.capability_names) or "<empty>"
        super().__init__(f"{code.value}: {joined}")


def require_v1_capability_contract(
    required: Iterable[CapabilityName | str],
) -> tuple[CapabilityName, ...]:
    """Accept only registered V1 contract capabilities.

    This is a declaration precheck, not evidence that the phase-specific
    implementation (for example a Solver) already exists.
    """

    raw_names = tuple(str(value) for value in required)
    duplicates = sorted({name for name in raw_names if raw_names.count(name) > 1})
    if duplicates:
        raise CapabilityContractError(ProductErrorCode.DUPLICATE_CAPABILITY, duplicates)

    parsed: list[CapabilityName] = []
    unknown: list[str] = []
    for raw_name in raw_names:
        try:
            parsed.append(CapabilityName(raw_name))
        except ValueError:
            unknown.append(raw_name)
    if unknown:
        raise CapabilityContractError(
            ProductErrorCode.INVALID_CAPABILITY_DECLARATION, unknown
        )

    blocked = [
        name.value
        for name in parsed
        if CAPABILITY_STATUS_BY_NAME[name] is not CapabilityStatus.V1_SUPPORTED
    ]
    if blocked:
        raise CapabilityContractError(ProductErrorCode.UNSUPPORTED_CAPABILITY, blocked)
    return tuple(parsed)


__all__ = [
    "CAPABILITY_STATUS_BY_NAME",
    "CapabilityContractError",
    "CapabilityName",
    "CapabilityStatus",
    "require_v1_capability_contract",
]
