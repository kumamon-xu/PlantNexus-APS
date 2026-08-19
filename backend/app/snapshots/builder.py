"""Build immutable PlanningSnapshot v2 values from the validated P1 chain."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import cast

from app.data_validation.validator import validate_quality_report_contract
from app.domain.canonical_records import (
    COLLECTION_ID_FIELDS,
    ImportPackageDocumentV2,
    PlanningSnapshotDocumentV2,
    SyntheticProvenance,
    validate_import_package_v2,
    validate_planning_snapshot_v2,
)
from app.domain.production import (
    ORDER_EXPANSION_VERSION,
    OrderExpansionResult,
    canonical_expansion_bytes,
)
from app.domain.types import ContractValueError, parse_utc_instant

from .canonical import (
    SNAPSHOT_CANONICALIZATION_VERSION,
    SNAPSHOT_SCHEMA_SET_VERSION,
    SNAPSHOT_VERSION,
    canonical_import_document,
    canonical_snapshot_bytes,
    import_dataset_hash_for,
    import_package_id_for,
    snapshot_hash_for,
    snapshot_id_for_hash,
    verify_snapshot,
)
from .contracts import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
)

_IMPORT_FIELDS = {
    "import_package_version",
    "schema_set_version",
    "package_id",
    "source_versions",
    "normalization_rule_version",
    "canonicalization_version",
    "synthetic",
    "records",
}
_QUALITY_FIELDS = {
    "report_version",
    "schema_set_version",
    "report_id",
    "import_package_version",
    "package_id",
    "data_quality_rule_version",
    "error_registry_version",
    "report_canonicalization_version",
    "status",
    "error_count",
    "errors",
}


def _reject(
    code: SnapshotErrorCode,
    *,
    field: str,
    expected_contract: str,
    message: str,
) -> None:
    raise SnapshotError(
        code,
        field=field,
        expected_contract=expected_contract,
        message=message,
    )


def _validated_import(document: Mapping[str, object]) -> ImportPackageDocumentV2:
    expected_fields = _IMPORT_FIELDS | (
        {"synthetic_provenance"} if document.get("synthetic") is True else set()
    )
    if set(document) != expected_fields:
        _reject(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="import_package",
            expected_contract="exact import-package.v2 field set",
            message="Import fields do not match the versioned contract",
        )
    try:
        validate_import_package_v2(cast(ImportPackageDocumentV2, document))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field=getattr(error, "field", "import_package"),
            expected_contract="valid canonical Import v2",
            message="Canonical Import validation failed",
        ) from error
    canonical = canonical_import_document(document)
    if canonical["canonicalization_version"] != SNAPSHOT_CANONICALIZATION_VERSION:
        _reject(
            SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH,
            field="import_package.canonicalization_version",
            expected_contract=SNAPSHOT_CANONICALIZATION_VERSION,
            message="Snapshot cannot reinterpret another canonicalization version",
        )
    if canonical["package_id"] != import_package_id_for(canonical):
        _reject(
            SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH,
            field="import_package.package_id",
            expected_contract="P1 content-derived Import package ID",
            message="Import package ID does not bind the supplied facts",
        )
    return canonical


def _validated_quality_report(
    report: Mapping[str, object],
    import_document: ImportPackageDocumentV2,
) -> Mapping[str, object]:
    if set(report) != _QUALITY_FIELDS:
        _reject(
            SnapshotErrorCode.QUALITY_REPORT_REQUIRED,
            field="import_quality_report",
            expected_contract="exact import-quality-report.v1 field set",
            message="A complete quality report is required",
        )
    try:
        validate_quality_report_contract(report)
    except (KeyError, TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.QUALITY_REPORT_REQUIRED,
            field="import_quality_report",
            expected_contract="content-derived import-quality-report.v1",
            message="Quality report integrity validation failed",
        ) from error
    expected = {
        "report_version": "import-quality-report.v1",
        "schema_set_version": "2.2.0",
        "import_package_version": "import-package.v2",
        "package_id": import_document["package_id"],
        "data_quality_rule_version": "data-quality-rules.v1",
        "error_registry_version": "error-code-registry.v2",
        "report_canonicalization_version": "canonical-json.v1",
        "status": "PASS",
        "error_count": 0,
        "errors": [],
    }
    for field, value in expected.items():
        if report.get(field) != value:
            _reject(
                SnapshotErrorCode.QUALITY_REPORT_REQUIRED,
                field=f"import_quality_report.{field}",
                expected_contract=repr(value),
                message="A matching zero-error PASS report is required",
            )
    return report


def _validate_expansion(
    expansion: OrderExpansionResult,
    import_document: ImportPackageDocumentV2,
    quality_report: Mapping[str, object],
) -> None:
    document = expansion.document
    recomputed_bytes = canonical_expansion_bytes(cast(Mapping[str, object], document))
    recomputed_hash = f"sha256:{sha256(recomputed_bytes).hexdigest()}"
    if (
        expansion.canonical_bytes != recomputed_bytes
        or expansion.expansion_hash != recomputed_hash
    ):
        _reject(
            SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH,
            field="order_expansion",
            expected_contract="self-consistent order-expansion.v1 artifact",
            message="Expansion bytes or hash do not match its document",
        )
    if (
        document["expansion_version"] != ORDER_EXPANSION_VERSION
        or document["canonicalization_version"]
        != SNAPSHOT_CANONICALIZATION_VERSION
    ):
        _reject(
            SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH,
            field="order_expansion.expansion_version",
            expected_contract="order-expansion.v1 + canonical-json.v1",
            message="Expansion version is unsupported",
        )
    import_reference = document["import_package"]
    expected_import_reference: dict[str, object] = {
        "import_package_version": "import-package.v2",
        "schema_set_version": "2.0.0",
        "package_id": import_document["package_id"],
        "source_versions": dict(sorted(import_document["source_versions"].items())),
        "normalization_rule_version": import_document["normalization_rule_version"],
        "canonicalization_version": import_document["canonicalization_version"],
        "synthetic": import_document["synthetic"],
    }
    provenance = import_document.get("synthetic_provenance")
    if provenance is not None:
        expected_import_reference["synthetic_provenance"] = provenance
    if import_reference != expected_import_reference:
        _reject(
            SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH,
            field="order_expansion.import_package",
            expected_contract="the exact target Import provenance",
            message="Expansion belongs to another Import or data plane",
        )
    quality_reference = document["import_quality_report"]
    for field in (
        "report_version",
        "schema_set_version",
        "report_id",
        "data_quality_rule_version",
        "error_registry_version",
        "report_canonicalization_version",
        "status",
    ):
        if quality_reference.get(field) != quality_report.get(field):
            _reject(
                SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH,
                field=f"order_expansion.import_quality_report.{field}",
                expected_contract="the exact target quality report",
                message="Expansion quality provenance is mismatched",
            )


def _entity_counts(
    import_document: ImportPackageDocumentV2,
    expansion: OrderExpansionResult,
) -> dict[str, int]:
    counts = {
        collection: len(import_document["records"][collection])
        for collection in COLLECTION_ID_FIELDS
    }
    counts["operation_instances"] = len(expansion.document["operation_instances"])
    counts["operation_precedence_edges"] = len(
        expansion.document["operation_precedence_edges"]
    )
    return counts


def build_planning_snapshot(
    import_document: Mapping[str, object],
    quality_report: Mapping[str, object],
    expansion: OrderExpansionResult,
    *,
    cutoff_at_utc: str,
) -> ImmutablePlanningSnapshot:
    """Build one immutable Snapshot after all upstream identities are verified."""

    try:
        parse_utc_instant(cutoff_at_utc)
    except (ContractValueError, TypeError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="cutoff_at_utc",
            expected_contract="second-precision UTC instant ending in Z",
            message="Snapshot cutoff is invalid",
        ) from error
    canonical_import = _validated_import(import_document)
    validated_report = _validated_quality_report(quality_report, canonical_import)
    _validate_expansion(expansion, canonical_import, validated_report)

    base: dict[str, object] = {
        "snapshot_version": SNAPSHOT_VERSION,
        "schema_set_version": SNAPSHOT_SCHEMA_SET_VERSION,
        "cutoff_at_utc": cutoff_at_utc,
        "source_versions": dict(sorted(canonical_import["source_versions"].items())),
        "rule_version": validated_report["data_quality_rule_version"],
        "normalization_rule_version": canonical_import["normalization_rule_version"],
        "expansion_version": expansion.document["expansion_version"],
        "canonicalization_version": SNAPSHOT_CANONICALIZATION_VERSION,
        "import_package": {
            "import_package_version": "import-package.v2",
            "package_id": canonical_import["package_id"],
            "dataset_hash": import_dataset_hash_for(canonical_import),
        },
        "import_quality_report": {
            "report_version": "import-quality-report.v1",
            "report_id": validated_report["report_id"],
            "status": "PASS",
        },
        "entity_counts": _entity_counts(canonical_import, expansion),
        "synthetic": canonical_import["synthetic"],
        "records": canonical_import["records"],
        "operation_instances": expansion.document["operation_instances"],
        "operation_precedence_edges": expansion.document[
            "operation_precedence_edges"
        ],
    }
    provenance = canonical_import.get("synthetic_provenance")
    if provenance is not None:
        base["synthetic_provenance"] = cast(SyntheticProvenance, provenance)
    snapshot_hash = snapshot_hash_for(base)
    snapshot_id = snapshot_id_for_hash(snapshot_hash)
    document = cast(
        PlanningSnapshotDocumentV2,
        {"snapshot_id": snapshot_id, "snapshot_hash": snapshot_hash, **base},
    )
    try:
        validate_planning_snapshot_v2(document)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field=getattr(error, "field", "snapshot"),
            expected_contract="valid planning-snapshot.v2",
            message="Built Snapshot failed semantic validation",
        ) from error
    canonical_bytes = canonical_snapshot_bytes(cast(Mapping[str, object], document))
    data_plane = (
        SnapshotDataPlane.SIMULATION
        if document["synthetic"]
        else SnapshotDataPlane.PRODUCTION
    )
    snapshot = ImmutablePlanningSnapshot(
        canonical_bytes=canonical_bytes,
        snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash,
        data_plane=data_plane,
    )
    verify_snapshot(snapshot)
    return snapshot


__all__ = ["build_planning_snapshot"]
