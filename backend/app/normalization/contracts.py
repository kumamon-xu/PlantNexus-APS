"""Pure, versioned contracts for the P1 normalization boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.importers import StagedImportBatch


class NormalizationErrorCode(StrEnum):
    """Stable DATA_ERROR codes emitted before cross-entity validation."""

    INVALID_RAW_ROW = "INVALID_RAW_ROW"
    INVALID_MAPPING_PROFILE = "INVALID_MAPPING_PROFILE"
    PROFILE_SOURCE_MISMATCH = "PROFILE_SOURCE_MISMATCH"
    NORMALIZATION_VERSION_MISMATCH = "NORMALIZATION_VERSION_MISMATCH"
    MISSING_FIELD = "MISSING_FIELD"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_TIMEZONE = "INVALID_TIMEZONE"
    UNIT_CONVERSION_ERROR = "UNIT_CONVERSION_ERROR"
    MISSING_DURATION = "MISSING_DURATION"
    DUPLICATE_CANONICAL_ID = "DUPLICATE_CANONICAL_ID"
    CONFLICTING_AUTHORITY = "CONFLICTING_AUTHORITY"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"


class NormalizationError(ValueError):
    """A deterministic, sanitized normalization rejection."""

    category = "DATA_ERROR"

    def __init__(
        self,
        code: NormalizationErrorCode,
        *,
        source_location: str,
        field: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.code = code
        self.source_location = source_location
        self.field = field
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(
            f"{self.category}/{code.value} at {source_location} ({field}): {message}"
        )


class FieldTransform(StrEnum):
    """Explicit transformations accepted by mapping-profile.v1."""

    TEXT = "TEXT"
    CANONICAL_ID = "CANONICAL_ID"
    UTC_INSTANT = "UTC_INSTANT"
    NONNEGATIVE_DURATION_SECONDS = "NONNEGATIVE_DURATION_SECONDS"
    POSITIVE_DURATION_SECONDS = "POSITIVE_DURATION_SECONDS"
    POSITIVE_NUMBER = "POSITIVE_NUMBER"
    SORTED_TEXT_LIST = "SORTED_TEXT_LIST"
    UNAVAILABLE_INTERVALS = "UNAVAILABLE_INTERVALS"


@dataclass(frozen=True)
class FieldMapping:
    """One source-field to canonical-field mapping with no implicit fallback."""

    source_field: str
    target_field: str
    transform: FieldTransform
    required: bool = True
    id_namespace: str | None = None
    id_source_system: str | None = None
    unit_field: str | None = None


@dataclass(frozen=True)
class RecordMapping:
    """Map one exact source record type into one canonical collection."""

    record_type: str
    collection: str
    fields: tuple[FieldMapping, ...]


@dataclass(frozen=True)
class MappingProfile:
    """An exact source-system/version mapping profile; never resolved as latest."""

    profile_id: str
    profile_version: str
    source_system: str
    source_version: str
    unit_registry_version: str
    records: tuple[RecordMapping, ...]
    mapping_contract_version: str = "mapping-profile.v1"


@dataclass(frozen=True)
class NormalizationInput:
    """A staged batch paired with its explicitly selected mapping profile."""

    batch: StagedImportBatch
    profile: MappingProfile


@dataclass(frozen=True)
class NormalizationResult:
    """Canonical Import v2 bytes plus replay evidence outside the hash payload."""

    document: dict[str, object]
    canonical_bytes: bytes
    dataset_hash: str
    source_batch_ids: tuple[str, ...]
    mapping_profile_versions: tuple[str, ...]
    unit_registry_version: str


COLLECTION_ID_FIELDS: dict[str, str] = {
    "factories": "factory_id",
    "workshops": "workshop_id",
    "production_lines": "production_line_id",
    "resource_groups": "resource_group_id",
    "resources": "resource_id",
    "calendars": "calendar_id",
    "products": "product_id",
    "routing_versions": "routing_version_id",
    "routing_operations": "routing_operation_id",
    "routing_precedence_edges": "routing_precedence_edge_id",
    "routing_resource_options": "routing_resource_option_id",
    "demand_orders": "demand_order_id",
    "production_orders": "production_order_id",
    "production_lots": "production_lot_id",
    "execution_facts": "execution_fact_id",
    "operation_locks": "lock_id",
}


COLLECTION_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "factories": frozenset({"factory_id", "factory_code", "factory_timezone"}),
    "workshops": frozenset({"workshop_id", "workshop_code", "factory_id"}),
    "production_lines": frozenset(
        {"production_line_id", "production_line_code", "workshop_id"}
    ),
    "resource_groups": frozenset(
        {"resource_group_id", "resource_group_code", "production_line_id"}
    ),
    "resources": frozenset(
        {
            "resource_id",
            "resource_code",
            "resource_type",
            "status",
            "resource_group_id",
            "calendar_id",
            "capabilities",
        }
    ),
    "calendars": frozenset({"calendar_id", "timezone", "unavailable_intervals"}),
    "products": frozenset({"product_id", "product_code", "quantity_unit"}),
    "routing_versions": frozenset(
        {"routing_version_id", "routing_code", "version", "product_id"}
    ),
    "routing_operations": frozenset(
        {
            "routing_operation_id",
            "routing_version_id",
            "operation_code",
            "required_capabilities",
        }
    ),
    "routing_precedence_edges": frozenset(
        {
            "routing_precedence_edge_id",
            "routing_version_id",
            "predecessor_routing_operation_id",
            "successor_routing_operation_id",
            "min_lag_seconds",
            "transport_lag_seconds",
        }
    ),
    "routing_resource_options": frozenset(
        {
            "routing_resource_option_id",
            "routing_operation_id",
            "resource_id",
            "quantity_unit",
            "setup_seconds",
            "cycle_seconds_per_unit",
            "final_duration_seconds",
            "duration_source",
            "duration_source_version",
        }
    ),
    "demand_orders": frozenset(
        {"demand_order_id", "product_id", "quantity", "quantity_unit", "due_at_utc"}
    ),
    "production_orders": frozenset(
        {
            "production_order_id",
            "demand_order_id",
            "routing_version_id",
            "quantity",
            "quantity_unit",
            "release_at_utc",
            "material_ready_at_utc",
        }
    ),
    "production_lots": frozenset(
        {"production_lot_id", "production_order_id", "quantity", "quantity_unit"}
    ),
    "execution_facts": frozenset(
        {
            "execution_fact_id",
            "production_lot_id",
            "routing_operation_id",
            "status",
            "observed_at_utc",
            "quantity_unit",
        }
    ),
    "operation_locks": frozenset(
        {
            "lock_id",
            "production_lot_id",
            "routing_operation_id",
            "lock_type",
            "resource_id",
            "start_at_utc",
            "end_at_utc",
        }
    ),
}


COLLECTION_OPTIONAL_FIELDS: dict[str, frozenset[str]] = {
    collection: frozenset() for collection in COLLECTION_REQUIRED_FIELDS
}
COLLECTION_OPTIONAL_FIELDS["routing_precedence_edges"] = frozenset({"max_lag_seconds"})
COLLECTION_OPTIONAL_FIELDS["execution_facts"] = frozenset(
    {
        "resource_id",
        "actual_start_at_utc",
        "actual_end_at_utc",
        "completed_quantity",
        "remaining_quantity",
        "remaining_seconds",
    }
)


__all__ = [
    "COLLECTION_ID_FIELDS",
    "COLLECTION_OPTIONAL_FIELDS",
    "COLLECTION_REQUIRED_FIELDS",
    "FieldMapping",
    "FieldTransform",
    "MappingProfile",
    "NormalizationError",
    "NormalizationErrorCode",
    "NormalizationInput",
    "NormalizationResult",
    "RecordMapping",
]
