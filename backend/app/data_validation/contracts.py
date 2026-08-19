"""Pure contracts and deterministic issue collection for P1 data validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Literal, cast

from app.domain.contracts import (
    ErrorDetailDocumentV3,
    ErrorDocumentV3,
    ImportQualityReportDocument,
    JsonValue,
)
from app.domain.errors import ProductErrorCodeV2, category_for_error_code_v2


DATA_QUALITY_RULE_VERSION = "data-quality-rules.v1"
ERROR_DOCUMENT_VERSION = "error.v3"
ERROR_REGISTRY_VERSION = "error-code-registry.v2"
IMPORT_QUALITY_REPORT_VERSION = "import-quality-report.v1"
REPORT_CANONICALIZATION_VERSION = "canonical-json.v1"
SCHEMA_SET_VERSION = "2.2.0"

type ErrorCategoryValue = Literal[
    "DATA_ERROR",
    "UNSUPPORTED_CAPABILITY",
    "MODEL_INVALID",
    "INFEASIBLE",
    "NO_SOLUTION_WITHIN_LIMIT",
    "VALIDATION_FAILED",
    "SYSTEM_ERROR",
]


def json_compatible(value: object) -> JsonValue:
    """Return a deterministic JSON-compatible diagnostic projection."""

    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return f"<non-finite:{value!s}>"
        return value
    if isinstance(value, Mapping):
        return {
            str(key): json_compatible(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [json_compatible(child) for child in value]
    if isinstance(value, (bytes, bytearray)):
        return f"<binary:{len(value)}-bytes>"
    return f"<unsupported:{type(value).__name__}>"


def canonical_json_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize one validator-owned document using canonical-json.v1."""

    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_json_text(value: object) -> str:
    """Return a stable comparison key for arbitrary observed input values."""

    return json.dumps(
        json_compatible(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stable_fingerprint(value: object) -> str:
    """Return a short, non-positional identity for a malformed record."""

    return sha256(stable_json_text(value).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class QualityIssue:
    """One normalized issue before conversion to the versioned Error envelope."""

    code: ProductErrorCodeV2
    entity_type: str
    entity_id: str
    field: str
    observed_value: JsonValue
    expected_contract: str
    source_location: str
    action: str
    message: str

    def sort_key(self) -> tuple[str, ...]:
        return (
            self.code.value,
            self.entity_type,
            self.entity_id,
            self.field,
            self.source_location,
            stable_json_text(self.observed_value),
            self.expected_contract,
            self.action,
            self.message,
        )

    def to_error_document(self) -> ErrorDocumentV3:
        detail: ErrorDetailDocumentV3 = {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field": self.field,
            "observed_value": self.observed_value,
            "expected_contract": self.expected_contract,
            "source_location": self.source_location,
            "action": self.action,
        }
        return {
            "error_version": "error.v3",
            "category": cast(
                ErrorCategoryValue, category_for_error_code_v2(self.code).value
            ),
            "code": self.code.value,
            "message": self.message,
            "details": [detail],
        }


@dataclass
class IssueCollector:
    """Collect, de-duplicate, and order independent validation findings."""

    _issues: list[QualityIssue] = field(default_factory=list)

    def add(
        self,
        code: ProductErrorCodeV2,
        *,
        entity_type: str,
        entity_id: str,
        field: str,
        observed_value: object,
        expected_contract: str,
        source_location: str,
        action: str,
        message: str,
    ) -> None:
        self._issues.append(
            QualityIssue(
                code=code,
                entity_type=entity_type,
                entity_id=entity_id,
                field=field,
                observed_value=json_compatible(observed_value),
                expected_contract=expected_contract,
                source_location=source_location,
                action=action,
                message=message,
            )
        )

    def ordered_issues(self) -> tuple[QualityIssue, ...]:
        unique: dict[tuple[str, ...], QualityIssue] = {}
        for issue in self._issues:
            unique[issue.sort_key()] = issue
        return tuple(sorted(unique.values(), key=QualityIssue.sort_key))

    def error_documents(self) -> tuple[ErrorDocumentV3, ...]:
        return tuple(issue.to_error_document() for issue in self.ordered_issues())


@dataclass(frozen=True)
class DataValidationResult:
    """Versioned quality report plus its exact canonical bytes."""

    document: ImportQualityReportDocument
    canonical_bytes: bytes

    @property
    def passed(self) -> bool:
        return self.document["status"] == "PASS"


__all__ = [
    "DATA_QUALITY_RULE_VERSION",
    "DataValidationResult",
    "ERROR_DOCUMENT_VERSION",
    "ERROR_REGISTRY_VERSION",
    "IMPORT_QUALITY_REPORT_VERSION",
    "IssueCollector",
    "QualityIssue",
    "REPORT_CANONICALIZATION_VERSION",
    "SCHEMA_SET_VERSION",
    "canonical_json_bytes",
    "json_compatible",
    "stable_fingerprint",
    "stable_json_text",
]
