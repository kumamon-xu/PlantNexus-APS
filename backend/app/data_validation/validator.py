"""Deterministic, multi-error canonical Import v2 quality evaluator."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import cast

from app.domain.contracts import ImportQualityReportDocument

from .capabilities import validate_capabilities_and_resources
from .contracts import (
    DATA_QUALITY_RULE_VERSION,
    DataValidationResult,
    ERROR_REGISTRY_VERSION,
    IMPORT_QUALITY_REPORT_VERSION,
    IssueCollector,
    REPORT_CANONICALIZATION_VERSION,
    SCHEMA_SET_VERSION,
    canonical_json_bytes,
)
from .references import validate_structure_and_references
from .routing import validate_routing_and_values


class QualityReportContractError(ValueError):
    """A report violates its deterministic count, status, or identity contract."""


def report_id_for(document: Mapping[str, object]) -> str:
    """Derive the report ID from all report fields except the self identifier."""

    basis = {key: value for key, value in document.items() if key != "report_id"}
    return f"import-quality-{sha256(canonical_json_bytes(basis)).hexdigest()}"


def validate_import_package(
    document: Mapping[str, object],
) -> DataValidationResult:
    """Validate one Import v2 document and always return a versioned report."""

    issues = IssueCollector()
    view = validate_structure_and_references(document, issues)
    validate_routing_and_values(view, issues)
    validate_capabilities_and_resources(view, issues)
    errors = list(issues.error_documents())
    status = "PASS" if not errors else "FAIL"
    report_without_id: dict[str, object] = {
        "report_version": IMPORT_QUALITY_REPORT_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "import_package_version": "import-package.v2",
        "package_id": view.package_id,
        "data_quality_rule_version": DATA_QUALITY_RULE_VERSION,
        "error_registry_version": ERROR_REGISTRY_VERSION,
        "report_canonicalization_version": REPORT_CANONICALIZATION_VERSION,
        "status": status,
        "error_count": len(errors),
        "errors": errors,
    }
    report = cast(
        ImportQualityReportDocument,
        {"report_id": report_id_for(report_without_id), **report_without_id},
    )
    canonical_bytes = canonical_json_bytes(cast(Mapping[str, object], report))
    validate_quality_report_contract(report)
    return DataValidationResult(document=report, canonical_bytes=canonical_bytes)


def validate_quality_report_contract(
    document: Mapping[str, object],
) -> None:
    """Check invariants that JSON Schema cannot express as array-count equality."""

    errors = document.get("errors")
    count = document.get("error_count")
    status = document.get("status")
    if not isinstance(errors, list):
        raise QualityReportContractError("errors must be an array")
    if isinstance(count, bool) or not isinstance(count, int) or count != len(errors):
        raise QualityReportContractError("error_count must equal len(errors)")
    expected_status = "PASS" if count == 0 else "FAIL"
    if status != expected_status:
        raise QualityReportContractError(
            "status must be PASS only for zero errors and FAIL otherwise"
        )
    observed_id = document.get("report_id")
    expected_id = report_id_for(document)
    if observed_id != expected_id:
        raise QualityReportContractError("report_id does not match report content")


__all__ = [
    "QualityReportContractError",
    "report_id_for",
    "validate_import_package",
    "validate_quality_report_contract",
]
