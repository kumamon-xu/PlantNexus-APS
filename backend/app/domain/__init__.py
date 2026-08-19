"""Pure domain contract types for the P0 executable specification."""

from .capabilities import (
    CAPABILITY_STATUS_BY_NAME,
    CapabilityContractError,
    CapabilityName,
    CapabilityStatus,
    require_v1_capability_contract,
)
from .errors import (
    ERROR_CATEGORY_BY_CODE,
    ProductErrorCategory,
    ProductErrorCode,
    category_for_error_code,
)
from .types import (
    CanonicalId,
    ContractValueError,
    DurationSeconds,
    TickSeconds,
    canonical_id,
    duration_to_ticks,
    format_utc_instant,
    parse_utc_instant,
    require_duration_seconds,
    require_tick_seconds,
    require_utc,
)
from .validation import (
    ContractViolation,
    validate_planning_problem_contract,
    validate_snapshot_contract,
)

__all__ = [
    "CAPABILITY_STATUS_BY_NAME",
    "CanonicalId",
    "ContractValueError",
    "ContractViolation",
    "CapabilityContractError",
    "CapabilityName",
    "CapabilityStatus",
    "DurationSeconds",
    "ERROR_CATEGORY_BY_CODE",
    "ProductErrorCategory",
    "ProductErrorCode",
    "TickSeconds",
    "canonical_id",
    "category_for_error_code",
    "duration_to_ticks",
    "format_utc_instant",
    "parse_utc_instant",
    "require_duration_seconds",
    "require_tick_seconds",
    "require_utc",
    "require_v1_capability_contract",
    "validate_planning_problem_contract",
    "validate_snapshot_contract",
]
