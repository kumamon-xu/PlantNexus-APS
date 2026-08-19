"""Pure contracts for deterministic production-order expansion.

This module owns only solver-neutral derived identities, provenance envelopes,
and explicit rejection semantics.  It does not split lots, predict durations,
build Snapshots, or create planning-model objects.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Final, Literal, NotRequired, TypedDict, cast

from app.domain.canonical_records import (
    OperationInstanceDocument,
    OperationPrecedenceEdgeDocument,
    SyntheticProvenance,
)

ORDER_EXPANSION_VERSION: Final = "order-expansion.v1"
EXPANSION_CANONICALIZATION_VERSION: Final = "canonical-json.v1"
EXPLICIT_LOTS_MODE: Final = "EXPLICIT_LOTS"
SPLIT_MERGE_CAPABILITY: Final = "SPLIT_MERGE"


class OrderExpansionErrorCode(StrEnum):
    """Module-local codes for failures at the expansion boundary."""

    EXPANSION_VERSION_MISMATCH = "EXPANSION_VERSION_MISMATCH"
    INVALID_CANONICAL_INPUT = "INVALID_CANONICAL_INPUT"
    QUALITY_REPORT_REQUIRED = "QUALITY_REPORT_REQUIRED"
    QUALITY_REPORT_MISMATCH = "QUALITY_REPORT_MISMATCH"
    MISSING_PRODUCTION_LOT = "MISSING_PRODUCTION_LOT"
    ROUTING_VERSION_MISMATCH = "ROUTING_VERSION_MISMATCH"
    MISSING_RESOURCE_OPTION = "MISSING_RESOURCE_OPTION"
    MISSING_DURATION = "MISSING_DURATION"
    DUPLICATE_DERIVED_ID = "DUPLICATE_DERIVED_ID"
    INVALID_EXECUTION_FACT = "INVALID_EXECUTION_FACT"
    INVALID_OPERATION_LOCK = "INVALID_OPERATION_LOCK"
    UNSUPPORTED_SPLIT_MERGE = "UNSUPPORTED_SPLIT_MERGE"


class OrderExpansionError(ValueError):
    """A deterministic, sanitized rejection from pure order expansion."""

    def __init__(
        self,
        code: OrderExpansionErrorCode,
        *,
        field: str,
        entity_id: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.code = code
        self.category: Literal["DATA_ERROR", "UNSUPPORTED_CAPABILITY"] = (
            "UNSUPPORTED_CAPABILITY"
            if code is OrderExpansionErrorCode.UNSUPPORTED_SPLIT_MERGE
            else "DATA_ERROR"
        )
        self.field = field
        self.entity_id = entity_id
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(
            f"{self.category}/{code.value} at {field} ({entity_id}): {message}"
        )


class OrderExpansionImportReference(TypedDict):
    import_package_version: Literal["import-package.v2"]
    schema_set_version: Literal["2.0.0"]
    package_id: str
    source_versions: dict[str, str]
    normalization_rule_version: str
    canonicalization_version: str
    synthetic: bool
    synthetic_provenance: NotRequired[SyntheticProvenance]


class OrderExpansionQualityReference(TypedDict):
    report_version: Literal["import-quality-report.v1"]
    schema_set_version: Literal["2.2.0"]
    report_id: str
    data_quality_rule_version: Literal["data-quality-rules.v1"]
    error_registry_version: Literal["error-code-registry.v2"]
    report_canonicalization_version: Literal["canonical-json.v1"]
    status: Literal["PASS"]


class OrderExpansionDocument(TypedDict):
    expansion_version: Literal["order-expansion.v1"]
    canonicalization_version: Literal["canonical-json.v1"]
    import_package: OrderExpansionImportReference
    import_quality_report: OrderExpansionQualityReference
    operation_instances: list[OperationInstanceDocument]
    operation_precedence_edges: list[OperationPrecedenceEdgeDocument]


@dataclass(frozen=True)
class OrderExpansionResult:
    """Canonical expansion artifact and its deterministic content digest."""

    document: OrderExpansionDocument
    canonical_bytes: bytes
    expansion_hash: str


def canonical_expansion_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize an expansion-owned document using canonical-json.v1."""

    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_expansion_id(
    kind: Literal["operation-instance", "operation-precedence-edge"],
    expansion_version: str,
    *lineage_ids: str,
) -> str:
    """Derive one replay-stable ID from versioned, explicit source lineage."""

    if expansion_version != ORDER_EXPANSION_VERSION:
        raise OrderExpansionError(
            OrderExpansionErrorCode.EXPANSION_VERSION_MISMATCH,
            field="expansion_version",
            entity_id=expansion_version or "<missing>",
            expected_contract=ORDER_EXPANSION_VERSION,
            message="Expansion versions must be selected explicitly",
        )
    if not lineage_ids or any(not value for value in lineage_ids):
        raise OrderExpansionError(
            OrderExpansionErrorCode.INVALID_CANONICAL_INPUT,
            field="lineage_ids",
            entity_id=kind,
            expected_contract="one or more non-empty canonical lineage IDs",
            message="Derived IDs require complete source lineage",
        )
    basis = cast(
        Mapping[str, object],
        {
            "expansion_version": expansion_version,
            "kind": kind,
            "lineage_ids": list(lineage_ids),
        },
    )
    digest = sha256(canonical_expansion_bytes(basis)).hexdigest()
    return f"{kind}-{digest}"


__all__ = [
    "EXPLICIT_LOTS_MODE",
    "EXPANSION_CANONICALIZATION_VERSION",
    "ORDER_EXPANSION_VERSION",
    "SPLIT_MERGE_CAPABILITY",
    "OrderExpansionDocument",
    "OrderExpansionError",
    "OrderExpansionErrorCode",
    "OrderExpansionImportReference",
    "OrderExpansionQualityReference",
    "OrderExpansionResult",
    "canonical_expansion_bytes",
    "stable_expansion_id",
]
