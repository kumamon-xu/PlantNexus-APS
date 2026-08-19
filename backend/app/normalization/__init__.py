"""P1 deterministic normalization and canonical Import producer."""

from .contracts import (
    COLLECTION_ID_FIELDS,
    FieldMapping,
    FieldTransform,
    MappingProfile,
    NormalizationError,
    NormalizationErrorCode,
    NormalizationInput,
    NormalizationResult,
    RecordMapping,
)
from .ids import stable_canonical_id
from .normalizer import (
    CANONICALIZATION_VERSION,
    CURRENT_SCHEMA_SET_VERSION,
    IMPORT_DOCUMENT_SCHEMA_SET_VERSION,
    NORMALIZATION_CONTRACT_VERSION,
    canonical_json_bytes,
    normalize_import,
)
from .order_expansion import expand_orders
from .time import normalize_utc_instant
from .units import MAX_DURATION_SECONDS, UnitConversionRegistry, UnitConversionRule

__all__ = [
    "CANONICALIZATION_VERSION",
    "COLLECTION_ID_FIELDS",
    "CURRENT_SCHEMA_SET_VERSION",
    "FieldMapping",
    "FieldTransform",
    "IMPORT_DOCUMENT_SCHEMA_SET_VERSION",
    "MAX_DURATION_SECONDS",
    "MappingProfile",
    "NORMALIZATION_CONTRACT_VERSION",
    "NormalizationError",
    "NormalizationErrorCode",
    "NormalizationInput",
    "NormalizationResult",
    "RecordMapping",
    "UnitConversionRegistry",
    "UnitConversionRule",
    "canonical_json_bytes",
    "expand_orders",
    "normalize_import",
    "normalize_utc_instant",
    "stable_canonical_id",
]
