"""Canonical JSON, hash projection, and integrity checks for Snapshot v2."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Final, cast

from app.domain.canonical_records import (
    COLLECTION_ID_FIELDS,
    ImportPackageDocumentV2,
    PlanningSnapshotDocumentV2,
    validate_planning_snapshot_v2,
)

from .contracts import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
)

SNAPSHOT_VERSION: Final = "planning-snapshot.v2"
SNAPSHOT_SCHEMA_SET_VERSION: Final = "2.0.0"
SNAPSHOT_CANONICALIZATION_VERSION: Final = "canonical-json.v1"
SNAPSHOT_HASH_PROJECTION_VERSION: Final = "snapshot-hash-projection.v1"

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_SEMANTIC_FIELDS: Final = (
    "snapshot_version",
    "schema_set_version",
    "cutoff_at_utc",
    "source_versions",
    "rule_version",
    "normalization_rule_version",
    "expansion_version",
    "canonicalization_version",
    "import_package",
    "import_quality_report",
    "entity_counts",
    "synthetic",
    "records",
    "operation_instances",
    "operation_precedence_edges",
)


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


def canonical_json_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize JSON-compatible values using canonical-json.v1."""

    try:
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="snapshot",
            expected_contract="canonical-json.v1 JSON-compatible finite values",
            message="Canonical serialization failed",
        ) from error


def _json_copy(document: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(canonical_json_bytes(document)))


def canonical_import_document(
    document: Mapping[str, object],
) -> ImportPackageDocumentV2:
    """Copy and order every unordered collection in a canonical Import v2."""

    copied = _json_copy(document)
    records = cast(dict[str, object], copied["records"])
    for collection, id_field in COLLECTION_ID_FIELDS.items():
        values = cast(list[dict[str, object]], records[collection])
        values.sort(key=lambda item: str(item[id_field]))

    for resource in cast(list[dict[str, object]], records["resources"]):
        resource["capabilities"] = sorted(cast(list[str], resource["capabilities"]))
    for calendar in cast(list[dict[str, object]], records["calendars"]):
        intervals = cast(
            list[dict[str, object]], calendar["unavailable_intervals"]
        )
        intervals.sort(key=lambda item: str(item["interval_id"]))
    for operation in cast(
        list[dict[str, object]], records["routing_operations"]
    ):
        operation["required_capabilities"] = sorted(
            cast(list[str], operation["required_capabilities"])
        )
    copied["source_versions"] = dict(
        sorted(cast(dict[str, str], copied["source_versions"]).items())
    )
    return cast(ImportPackageDocumentV2, copied)


def import_package_id_for(document: Mapping[str, object]) -> str:
    """Reproduce the P1 normalization content-derived package identity."""

    canonical = cast(dict[str, object], canonical_import_document(document))
    canonical.pop("package_id", None)
    return f"import-{sha256(canonical_json_bytes(canonical)).hexdigest()}"


def import_dataset_hash_for(document: Mapping[str, object]) -> str:
    """Hash the complete, canonically ordered Import v2 document."""

    canonical = cast(Mapping[str, object], canonical_import_document(document))
    return f"sha256:{sha256(canonical_json_bytes(canonical)).hexdigest()}"


def canonical_snapshot_document(
    document: Mapping[str, object],
) -> PlanningSnapshotDocumentV2:
    """Copy and deterministically order all Snapshot business facts."""

    copied = _json_copy(document)
    import_shim: dict[str, object] = {
        "import_package_version": "import-package.v2",
        "schema_set_version": "2.0.0",
        "package_id": "snapshot-canonicalization-only",
        "source_versions": copied["source_versions"],
        "normalization_rule_version": copied["normalization_rule_version"],
        "canonicalization_version": copied["canonicalization_version"],
        "synthetic": copied["synthetic"],
        "records": copied["records"],
    }
    if "synthetic_provenance" in copied:
        import_shim["synthetic_provenance"] = copied["synthetic_provenance"]
    copied["records"] = canonical_import_document(import_shim)["records"]
    copied["source_versions"] = dict(
        sorted(cast(dict[str, str], copied["source_versions"]).items())
    )

    instances = cast(list[dict[str, object]], copied["operation_instances"])
    for instance in instances:
        instance["required_capabilities"] = sorted(
            cast(list[str], instance["required_capabilities"])
        )
        instance["lock_ids"] = sorted(cast(list[str], instance["lock_ids"]))
        options = cast(list[dict[str, object]], instance["resource_options"])
        options.sort(key=lambda item: str(item["routing_resource_option_id"]))
    instances.sort(key=lambda item: str(item["operation_instance_id"]))

    edges = cast(list[dict[str, object]], copied["operation_precedence_edges"])
    edges.sort(key=lambda item: str(item["operation_precedence_edge_id"]))
    return cast(PlanningSnapshotDocumentV2, copied)


def snapshot_hash_projection(document: Mapping[str, object]) -> dict[str, object]:
    """Select the exact semantic projection used by Snapshot v2 hashing.

    Self identity/hash and unknown transport metadata such as received/generated
    timestamps are outside this allow-list. Business timestamps in canonical
    records and ``cutoff_at_utc`` remain included.
    """

    projection = {field: deepcopy(document[field]) for field in _SEMANTIC_FIELDS}
    if "synthetic_provenance" in document:
        projection["synthetic_provenance"] = deepcopy(
            document["synthetic_provenance"]
        )
    canonical = canonical_snapshot_document(projection)
    return cast(dict[str, object], canonical)


def snapshot_hash_for(document: Mapping[str, object]) -> str:
    projection = snapshot_hash_projection(document)
    return f"sha256:{sha256(canonical_json_bytes(projection)).hexdigest()}"


def snapshot_id_for_hash(snapshot_hash: str) -> str:
    """Derive the stable ID in the explicit PlanningSnapshot v2 namespace."""

    if _SHA256.fullmatch(snapshot_hash) is None:
        _reject(
            SnapshotErrorCode.HASH_MISMATCH,
            field="snapshot_hash",
            expected_contract="sha256:<64 lowercase hex>",
            message="Snapshot hash is malformed",
        )
    return f"planning-snapshot-v2-{snapshot_hash.removeprefix('sha256:')}"


def canonical_snapshot_bytes(document: Mapping[str, object]) -> bytes:
    canonical = canonical_snapshot_document(document)
    return canonical_json_bytes(cast(Mapping[str, object], canonical))


def verify_snapshot(snapshot: ImmutablePlanningSnapshot) -> None:
    """Verify canonical bytes, v2 contract, content hash, ID, and data plane."""

    try:
        decoded = json.loads(snapshot.canonical_bytes)
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="canonical_bytes",
            expected_contract="canonical-json.v1 PlanningSnapshot v2",
            message="Snapshot bytes are not valid UTF-8 JSON",
        ) from error
    if not isinstance(decoded, dict):
        _reject(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="canonical_bytes",
            expected_contract="PlanningSnapshot v2 object",
            message="Snapshot root is not an object",
        )
    expected_fields = set(_SEMANTIC_FIELDS) | {"snapshot_id", "snapshot_hash"}
    if decoded.get("synthetic") is True:
        expected_fields.add("synthetic_provenance")
    if set(decoded) != expected_fields:
        _reject(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="canonical_bytes",
            expected_contract="exact planning-snapshot.v2 field set",
            message="Persisted Snapshot contains missing or unknown root fields",
        )
    try:
        canonical = canonical_snapshot_bytes(decoded)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field="canonical_bytes",
            expected_contract="complete planning-snapshot.v2 canonical object",
            message="Snapshot canonical payload is incomplete",
        ) from error
    if canonical != snapshot.canonical_bytes:
        _reject(
            SnapshotErrorCode.HASH_MISMATCH,
            field="canonical_bytes",
            expected_contract="byte-exact canonical-json.v1",
            message="Stored bytes are not canonical",
        )
    try:
        validate_planning_snapshot_v2(cast(PlanningSnapshotDocumentV2, decoded))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field=getattr(error, "field", "snapshot"),
            expected_contract="valid planning-snapshot.v2",
            message="Snapshot semantic validation failed",
        ) from error

    expected_hash = snapshot_hash_for(decoded)
    expected_id = snapshot_id_for_hash(expected_hash)
    if (
        decoded.get("snapshot_hash") != expected_hash
        or snapshot.snapshot_hash != expected_hash
    ):
        _reject(
            SnapshotErrorCode.HASH_MISMATCH,
            field="snapshot_hash",
            expected_contract="SHA-256 of snapshot-hash-projection.v1",
            message="Snapshot hash does not match semantic content",
        )
    if decoded.get("snapshot_id") != expected_id or snapshot.snapshot_id != expected_id:
        _reject(
            SnapshotErrorCode.HASH_MISMATCH,
            field="snapshot_id",
            expected_contract="PlanningSnapshot v2 content-derived ID",
            message="Snapshot ID does not match its content hash",
        )
    expected_plane = (
        SnapshotDataPlane.SIMULATION
        if decoded.get("synthetic") is True
        else SnapshotDataPlane.PRODUCTION
    )
    if snapshot.data_plane is not expected_plane:
        _reject(
            SnapshotErrorCode.DATA_PLANE_MISMATCH,
            field="data_plane",
            expected_contract=expected_plane.value,
            message="Snapshot data plane differs from its synthetic marker",
        )


__all__ = [
    "SNAPSHOT_CANONICALIZATION_VERSION",
    "SNAPSHOT_HASH_PROJECTION_VERSION",
    "SNAPSHOT_SCHEMA_SET_VERSION",
    "SNAPSHOT_VERSION",
    "canonical_import_document",
    "canonical_json_bytes",
    "canonical_snapshot_bytes",
    "canonical_snapshot_document",
    "import_dataset_hash_for",
    "import_package_id_for",
    "snapshot_hash_for",
    "snapshot_hash_projection",
    "snapshot_id_for_hash",
    "verify_snapshot",
]
