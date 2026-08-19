"""Stable P0 product error categories and code-to-category mapping."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ProductErrorCategory(StrEnum):
    """The seven product error categories fixed by the implementation spec."""

    DATA_ERROR = "DATA_ERROR"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    MODEL_INVALID = "MODEL_INVALID"
    INFEASIBLE = "INFEASIBLE"
    NO_SOLUTION_WITHIN_LIMIT = "NO_SOLUTION_WITHIN_LIMIT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class ProductErrorCode(StrEnum):
    """Stable codes currently allocated by P0 contracts."""

    INVALID_TIME = "INVALID_TIME"
    DUPLICATE_ID = "DUPLICATE_ID"
    MISSING_SCENARIO_ID = "MISSING_SCENARIO_ID"
    SYNTHETIC_REFERENCE_IN_PRODUCTION = "SYNTHETIC_REFERENCE_IN_PRODUCTION"
    INVALID_ENTITY_COUNT = "INVALID_ENTITY_COUNT"
    INVALID_DURATION = "INVALID_DURATION"
    INVALID_TIME_RANGE = "INVALID_TIME_RANGE"
    MISSING_RUNNING_FACT = "MISSING_RUNNING_FACT"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    INVALID_LAG_RANGE = "INVALID_LAG_RANGE"
    INVALID_CAPABILITY_DECLARATION = "INVALID_CAPABILITY_DECLARATION"
    DUPLICATE_CAPABILITY = "DUPLICATE_CAPABILITY"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    MODEL_INVALID = "MODEL_INVALID"
    INFEASIBLE = "INFEASIBLE"
    NO_SOLUTION_WITHIN_LIMIT = "NO_SOLUTION_WITHIN_LIMIT"
    SCHEDULE_VALIDATION_FAILED = "SCHEDULE_VALIDATION_FAILED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


_DATA_CODES = (
    ProductErrorCode.INVALID_TIME,
    ProductErrorCode.DUPLICATE_ID,
    ProductErrorCode.MISSING_SCENARIO_ID,
    ProductErrorCode.SYNTHETIC_REFERENCE_IN_PRODUCTION,
    ProductErrorCode.INVALID_ENTITY_COUNT,
    ProductErrorCode.INVALID_DURATION,
    ProductErrorCode.INVALID_TIME_RANGE,
    ProductErrorCode.MISSING_RUNNING_FACT,
    ProductErrorCode.INVALID_REFERENCE,
    ProductErrorCode.INVALID_LAG_RANGE,
    ProductErrorCode.INVALID_CAPABILITY_DECLARATION,
    ProductErrorCode.DUPLICATE_CAPABILITY,
    ProductErrorCode.INVALID_STATE_TRANSITION,
)

ERROR_CATEGORY_BY_CODE: Mapping[ProductErrorCode, ProductErrorCategory] = MappingProxyType(
    {
        **{code: ProductErrorCategory.DATA_ERROR for code in _DATA_CODES},
        ProductErrorCode.UNSUPPORTED_CAPABILITY: ProductErrorCategory.UNSUPPORTED_CAPABILITY,
        ProductErrorCode.MODEL_INVALID: ProductErrorCategory.MODEL_INVALID,
        ProductErrorCode.INFEASIBLE: ProductErrorCategory.INFEASIBLE,
        ProductErrorCode.NO_SOLUTION_WITHIN_LIMIT: ProductErrorCategory.NO_SOLUTION_WITHIN_LIMIT,
        ProductErrorCode.SCHEDULE_VALIDATION_FAILED: ProductErrorCategory.VALIDATION_FAILED,
        ProductErrorCode.SYSTEM_ERROR: ProductErrorCategory.SYSTEM_ERROR,
    }
)


def category_for_error_code(code: ProductErrorCode | str) -> ProductErrorCategory:
    """Return the sole category allocated to a registered product error code."""

    return ERROR_CATEGORY_BY_CODE[ProductErrorCode(code)]


__all__ = [
    "ERROR_CATEGORY_BY_CODE",
    "ProductErrorCategory",
    "ProductErrorCode",
    "category_for_error_code",
]
