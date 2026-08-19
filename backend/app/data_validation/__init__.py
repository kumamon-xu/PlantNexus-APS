"""P1 canonical-data quality gate; independent from planning and Solver code."""

from .contracts import (
    DATA_QUALITY_RULE_VERSION,
    DataValidationResult,
    ERROR_DOCUMENT_VERSION,
    ERROR_REGISTRY_VERSION,
    IMPORT_QUALITY_REPORT_VERSION,
    REPORT_CANONICALIZATION_VERSION,
    SCHEMA_SET_VERSION,
)
from .validator import (
    QualityReportContractError,
    report_id_for,
    validate_import_package,
    validate_quality_report_contract,
)

__all__ = [
    "DATA_QUALITY_RULE_VERSION",
    "DataValidationResult",
    "ERROR_DOCUMENT_VERSION",
    "ERROR_REGISTRY_VERSION",
    "IMPORT_QUALITY_REPORT_VERSION",
    "QualityReportContractError",
    "REPORT_CANONICALIZATION_VERSION",
    "SCHEMA_SET_VERSION",
    "report_id_for",
    "validate_import_package",
    "validate_quality_report_contract",
]
