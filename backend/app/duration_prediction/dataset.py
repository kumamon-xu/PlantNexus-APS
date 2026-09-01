"""Build a deterministic, provenance-complete P6 duration dataset.

The builder accepts one explicitly allow-listed Simulation source.  It has no
database, planning, model-training, network, or Production authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Never, cast


type JsonObject = dict[str, Any]

SOURCE_DOCUMENT_VERSION = "duration-dataset-source.v1"
DATASET_BUNDLE_VERSION = "duration-dataset-bundle.v1"
DATASET_MANIFEST_VERSION = "duration-dataset-manifest.v1"
DATASET_ROW_VERSION = "duration-dataset-row.v1"
SCHEMA_SET_VERSION = "2.9.0"
CANONICALIZATION_VERSION = "canonical-json.v1"
FEATURE_RECORD_VERSION = "duration-feature-record.v1"
FEATURE_SCHEMA_VERSION = "duration-features.v1"
SOURCE_VERSION = "SIM-P6-DURATION-HISTORY@1.0.0"
DATASET_VERSION = "SIM-P6-FEATURE-DATASET-001@1.0.0"
FACTORY_ID = "factory-sim-p6-001"
DATA_PLANE = "SIMULATION"
ENVIRONMENT = "TEST"
BUILDER_CONTRACT_VERSION = "duration-dataset-builder.v1"
LABEL_POLICY_VERSION = "explicit-normal-completion-label.v1"
SPLIT_POLICY_VERSION = "group-safe-time-split.v1"
PRIVACY_POLICY_VERSION = "duration-dataset-no-pii-no-target-feature.v1"
RETENTION_POLICY_VERSION = "sim-p6-contract-fixture-retention.v1"
DELETION_POLICY_VERSION = "delete-with-versioned-fixture-retirement.v1"
OPEN_AUTHORITY_GAPS = ("OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015")
PARTITIONS: tuple[tuple[str, str, str], ...] = (
    ("train", "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z"),
    ("validation", "2026-08-01T00:00:00Z", "2026-08-16T00:00:00Z"),
    ("test", "2026-08-16T00:00:00Z", "2026-09-01T00:00:00Z"),
)
EXPECTED_SOURCE_RECORDS = 10
EXPECTED_PARTITION_COUNTS: Mapping[str, int] = {
    "train": 4,
    "validation": 2,
    "test": 2,
}
EXPECTED_EXCLUSION_COUNTS: Mapping[str, int] = {
    "INTERRUPTED_NOT_LABEL_ELIGIBLE": 1,
    "RUNNING_NOT_LABEL_ELIGIBLE": 1,
}
FEATURE_DEFINITIONS: tuple[JsonObject, ...] = (
    {
        "feature_name": "planned_quantity",
        "source_field": "planned_quantity",
        "value_type": "INTEGER",
        "unit": "COUNT",
        "transform_version": "identity-count.v1",
    },
    {
        "feature_name": "setup_seconds",
        "source_field": "setup_seconds",
        "value_type": "INTEGER",
        "unit": "SECONDS",
        "transform_version": "identity-seconds.v1",
    },
    {
        "feature_name": "standard_duration_seconds",
        "source_field": "standard_duration_seconds",
        "value_type": "INTEGER",
        "unit": "SECONDS",
        "transform_version": "identity-seconds.v1",
    },
    {
        "feature_name": "operation_family",
        "source_field": "operation_family",
        "value_type": "CATEGORY",
        "unit": "CATEGORY",
        "transform_version": "identity-category.v1",
    },
)

_ROOT_KEYS = {
    "source_dataset_version",
    "source_dataset_id",
    "source_dataset_fingerprint",
    "schema_set_version",
    "canonicalization_version",
    "source_name",
    "source_version",
    "data_plane",
    "environment",
    "synthetic",
    "production_binding",
    "factory_id",
    "authority",
    "feature_policy",
    "label_policy",
    "split_policy",
    "privacy_policy",
    "synthetic_provenance",
    "governance_boundary",
    "records",
}
_RECORD_KEYS = {
    "source_record_id",
    "source_record_fingerprint",
    "lineage_group_id",
    "revision",
    "operation_id",
    "operation_type_id",
    "resource_option_id",
    "resource_id",
    "decision_cutoff_utc",
    "status",
    "disposition",
    "label_observed_at_utc",
    "label_available_at_utc",
    "actual_processing_seconds",
    "feature_observed_at_utc",
    "feature_available_at_utc",
    "planned_quantity",
    "setup_seconds",
    "standard_duration_seconds",
    "operation_family",
    "pii_fields_present",
    "target_fields_present",
}
_FORBIDDEN_SENSITIVE_KEYS = {
    "customer_id",
    "employee_id",
    "operator_id",
    "person_name",
    "email",
    "phone",
    "address",
    "ssn",
    "model_prediction_seconds",
    "predicted_duration_seconds",
}


class P6DatasetError(ValueError):
    """Stable fail-closed error raised for an invalid P6 dataset input."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> Never:
    raise P6DatasetError(code, detail)


def _reject_constant(value: str) -> Never:
    _fail("NON_FINITE_NUMBER", value)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical UTF-8 JSON bytes without a trailing newline."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        _fail("NON_CANONICAL_JSON", str(error))


def load_duration_source(path: Path) -> JsonObject:
    """Load a strict JSON source with duplicate/non-finite rejection."""

    try:
        loaded = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6DatasetError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail("SOURCE_READ_FAILED", type(error).__name__)
    if not isinstance(loaded, dict):
        _fail("INVALID_SOURCE_ROOT", "source must be a JSON object")
    return cast(JsonObject, loaded)


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _expect_object(value: object, path: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail("INVALID_OBJECT", path)
    return cast(JsonObject, value)


def _expect_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        _fail("MISSING_FIELD", f"{path}: {','.join(missing)}")
    if unknown:
        _fail("UNKNOWN_FIELD", f"{path}: {','.join(unknown)}")


def _expect_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        _fail("INVALID_IDENTIFIER", path)
    return value


def _expect_positive_int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("INVALID_POSITIVE_INTEGER", path)
    return value


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _fail("INVALID_UTC_INSTANT", path)
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        _fail("INVALID_UTC_INSTANT", path)
    if parsed.utcoffset() is None:
        _fail("INVALID_UTC_INSTANT", path)
    return parsed


def _walk_finite_and_sensitive(value: object, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        _fail("NON_FINITE_NUMBER", path)
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in _FORBIDDEN_SENSITIVE_KEYS:
                _fail("PII_OR_TARGET_FIELD_FORBIDDEN", f"{path}.{key}")
            _walk_finite_and_sensitive(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_finite_and_sensitive(nested, f"{path}[{index}]")


def source_record_fingerprint(record: Mapping[str, Any]) -> str:
    """Fingerprint a source record without its self fingerprint."""

    projection = {
        key: deepcopy(value)
        for key, value in record.items()
        if key != "source_record_fingerprint"
    }
    return _fingerprint(projection)


def source_dataset_fingerprint(source: Mapping[str, Any]) -> str:
    """Fingerprint a source while treating input record order as non-semantic."""

    projection = {
        key: deepcopy(value)
        for key, value in source.items()
        if key not in {"source_dataset_id", "source_dataset_fingerprint"}
    }
    records = projection.get("records")
    if isinstance(records, list):
        projection["records"] = sorted(
            records,
            key=lambda item: str(item.get("source_record_id", ""))
            if isinstance(item, dict)
            else "",
        )
    return _fingerprint(projection)


def recompute_source_identity(source: Mapping[str, Any]) -> JsonObject:
    """Return a copy with record and source content identities refreshed."""

    result = deepcopy(dict(source))
    records = result.get("records")
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                record["source_record_fingerprint"] = source_record_fingerprint(record)
    digest = source_dataset_fingerprint(result)
    result["source_dataset_fingerprint"] = digest
    result["source_dataset_id"] = "duration-dataset-source-" + digest.removeprefix(
        "sha256:"
    )
    return result


def _expected_policies() -> Mapping[str, object]:
    return {
        "authority": {
            "source_authority": "SIMULATION_SCENARIO_OWNER",
            "label_authority": "SIMULATION_EXECUTION_FACT",
            "purpose": "CONTRACT_CORRECTNESS_ONLY",
            "access_scope": "LOCAL_TEST_ONLY",
            "retention_policy_version": RETENTION_POLICY_VERSION,
            "deletion_policy_version": DELETION_POLICY_VERSION,
        },
        "feature_policy": {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "definitions": list(deepcopy(FEATURE_DEFINITIONS)),
            "as_of_required": True,
        },
        "label_policy": {
            "policy_version": LABEL_POLICY_VERSION,
            "label_name": "actual_processing_seconds",
            "source_field": "actual_processing_seconds",
            "unit": "SECONDS",
            "eligible_status": "COMPLETED",
            "eligible_disposition": "NORMAL",
            "derive_from_start_end": False,
            "standard_duration_is_label": False,
            "model_output_is_label": False,
        },
        "split_policy": {
            "policy_version": SPLIT_POLICY_VERSION,
            "event_time_field": "label_available_at_utc",
            "group_field": "lineage_group_id",
            "interval_semantics": "HALF_OPEN",
            "partitions": [
                {"name": name, "start_at_utc": start, "end_at_utc": end}
                for name, start, end in PARTITIONS
            ],
        },
        "privacy_policy": {
            "policy_version": PRIVACY_POLICY_VERSION,
            "pii_allowed": False,
            "target_as_feature_allowed": False,
            "raw_source_in_provider_artifact": False,
        },
        "synthetic_provenance": {
            "assumption_profile": DATASET_VERSION,
            "assumption_refs": ["SIM-ASSUMPTION-022"],
            "randomness": "NONE",
        },
        "governance_boundary": {
            "production_authorized": False,
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        },
    }


def _validate_root(source: JsonObject) -> None:
    _expect_keys(source, _ROOT_KEYS, "$")
    _walk_finite_and_sensitive(source)
    exact_values: Mapping[str, object] = {
        "source_dataset_version": SOURCE_DOCUMENT_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "source_name": "p6-duration-history-contract-fixture",
        "source_version": SOURCE_VERSION,
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "synthetic": True,
        "production_binding": False,
        "factory_id": FACTORY_ID,
    }
    for field, expected in exact_values.items():
        if source.get(field) != expected:
            _fail("UNAUTHORIZED_SOURCE", field)
    for field, expected in _expected_policies().items():
        if source.get(field) != expected:
            _fail("POLICY_MISMATCH", field)
    records = source.get("records")
    if not isinstance(records, list) or not records:
        _fail("INVALID_RECORDS", "records must be a non-empty array")
    if len(records) != EXPECTED_SOURCE_RECORDS:
        _fail("PROFILE_SHAPE_MISMATCH", "source record count")
    expected_source_fingerprint = source_dataset_fingerprint(source)
    if source.get("source_dataset_fingerprint") != expected_source_fingerprint:
        _fail("SOURCE_FINGERPRINT_MISMATCH", expected_source_fingerprint)
    expected_id = "duration-dataset-source-" + expected_source_fingerprint.removeprefix(
        "sha256:"
    )
    if source.get("source_dataset_id") != expected_id:
        _fail("SOURCE_ID_MISMATCH", expected_id)


def _partition_for(label_available_at: str) -> str:
    instant = _utc(label_available_at, "label_available_at_utc")
    for name, start, end in PARTITIONS:
        if _utc(start, f"{name}.start") <= instant < _utc(end, f"{name}.end"):
            return name
    _fail("LABEL_OUTSIDE_SPLIT_WINDOW", label_available_at)


def _validate_record(record: JsonObject, index: int) -> tuple[bool, str | None]:
    path = f"$.records[{index}]"
    _expect_keys(record, _RECORD_KEYS, path)
    for field in (
        "source_record_id",
        "lineage_group_id",
        "operation_id",
        "operation_type_id",
        "resource_option_id",
        "resource_id",
        "operation_family",
    ):
        _expect_string(record.get(field), f"{path}.{field}")
    _expect_positive_int(record.get("revision"), f"{path}.revision")
    _expect_positive_int(record.get("planned_quantity"), f"{path}.planned_quantity")
    _expect_positive_int(record.get("setup_seconds"), f"{path}.setup_seconds")
    _expect_positive_int(
        record.get("standard_duration_seconds"),
        f"{path}.standard_duration_seconds",
    )
    if record.get("pii_fields_present") is not False:
        _fail("PII_POLICY_VIOLATION", path)
    if record.get("target_fields_present") is not False:
        _fail("TARGET_LEAKAGE", path)
    expected_record_fingerprint = source_record_fingerprint(record)
    if record.get("source_record_fingerprint") != expected_record_fingerprint:
        _fail("RECORD_FINGERPRINT_MISMATCH", str(record.get("source_record_id")))

    cutoff = _utc(record.get("decision_cutoff_utc"), f"{path}.decision_cutoff_utc")
    feature_observed = _utc(
        record.get("feature_observed_at_utc"), f"{path}.feature_observed_at_utc"
    )
    feature_available = _utc(
        record.get("feature_available_at_utc"), f"{path}.feature_available_at_utc"
    )
    if feature_observed > feature_available or feature_available > cutoff:
        _fail("FUTURE_FEATURE_LEAKAGE", str(record.get("source_record_id")))

    status = record.get("status")
    disposition = record.get("disposition")
    actual = record.get("actual_processing_seconds")
    label_observed_value = record.get("label_observed_at_utc")
    label_available_value = record.get("label_available_at_utc")

    if status == "RUNNING":
        if disposition != "IN_PROGRESS" or actual is not None:
            _fail("INVALID_CENSORED_RECORD", str(record.get("source_record_id")))
        if label_observed_value is not None or label_available_value is not None:
            _fail("INVALID_CENSORED_RECORD", str(record.get("source_record_id")))
        return False, "RUNNING_NOT_LABEL_ELIGIBLE"

    if status != "COMPLETED" or disposition not in {"NORMAL", "INTERRUPTED"}:
        _fail("UNKNOWN_COMPLETION_SEMANTICS", str(record.get("source_record_id")))
    _expect_positive_int(actual, f"{path}.actual_processing_seconds")
    label_observed = _utc(label_observed_value, f"{path}.label_observed_at_utc")
    label_available = _utc(label_available_value, f"{path}.label_available_at_utc")
    if not cutoff < label_observed <= label_available:
        _fail("INVALID_LABEL_TIMELINE", str(record.get("source_record_id")))
    if disposition == "INTERRUPTED":
        return False, "INTERRUPTED_NOT_LABEL_ELIGIBLE"
    return True, None


def _builder_code_revision() -> str:
    source_bytes = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return f"sha256:{sha256(source_bytes).hexdigest()}"


def _feature_record(record: Mapping[str, Any]) -> JsonObject:
    source_record_id = cast(str, record["source_record_id"])
    feature_source_record: JsonObject = {
        "source_system": "simulated-operation-context",
        "source_version": SOURCE_VERSION,
        "source_record_id": source_record_id + "-feature-context",
        "observed_at_utc": record["feature_observed_at_utc"],
        "available_at_utc": record["feature_available_at_utc"],
    }
    feature_source_record["record_fingerprint"] = _fingerprint(feature_source_record)
    feature_source_record_id = cast(str, feature_source_record["source_record_id"])
    features: list[JsonObject] = []
    for definition in FEATURE_DEFINITIONS:
        source_field = cast(str, definition["source_field"])
        features.append(
            {
                "feature_name": definition["feature_name"],
                "value_type": definition["value_type"],
                "value": record[source_field],
                "unit": definition["unit"],
                "source_record_ids": [feature_source_record_id],
                "available_at_utc": record["feature_available_at_utc"],
                "transform_version": definition["transform_version"],
            }
        )
    projection: JsonObject = {
        "duration_feature_record_version": FEATURE_RECORD_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "factory_id": FACTORY_ID,
        "operation_id": record["operation_id"],
        "resource_option_id": record["resource_option_id"],
        "resource_id": record["resource_id"],
        "as_of_cutoff_utc": record["decision_cutoff_utc"],
        "source_records": [feature_source_record],
        "features": features,
        "pii_fields_present": False,
        "target_fields_present": False,
        "synthetic": True,
        "synthetic_provenance": {
            "assumption_profile": "SIM-P6-DURATION-CONTRACT-001@1.0.0",
            "assumption_refs": ["SIM-ASSUMPTION-021", "SIM-ASSUMPTION-022"],
        },
        "production_binding": False,
        "governance_boundary": {
            "production_authorized": False,
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        },
    }
    digest = _fingerprint(projection)
    projection["feature_record_id"] = "duration-feature-record-" + digest.removeprefix(
        "sha256:"
    )
    projection["feature_record_fingerprint"] = digest
    return projection


def _dataset_row(record: Mapping[str, Any], partition: str) -> JsonObject:
    projection: JsonObject = {
        "dataset_row_version": DATASET_ROW_VERSION,
        "partition": partition,
        "lineage_group_id": record["lineage_group_id"],
        "operation_type_id": record["operation_type_id"],
        "label": {
            "label_name": "actual_processing_seconds",
            "value": record["actual_processing_seconds"],
            "unit": "SECONDS",
            "source_record_id": record["source_record_id"],
            "source_record_fingerprint": record["source_record_fingerprint"],
            "observed_at_utc": record["label_observed_at_utc"],
            "available_at_utc": record["label_available_at_utc"],
            "policy_version": LABEL_POLICY_VERSION,
        },
        "feature_record": _feature_record(record),
    }
    digest = _fingerprint(projection)
    projection["dataset_row_id"] = "duration-dataset-row-" + digest.removeprefix(
        "sha256:"
    )
    projection["dataset_row_fingerprint"] = digest
    return projection


def _manifest(
    source: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
) -> JsonObject:
    partitions: list[JsonObject] = []
    for name, start, end in PARTITIONS:
        partition_rows = [row for row in rows if row["partition"] == name]
        partitions.append(
            {
                "name": name,
                "start_at_utc": start,
                "end_at_utc": end,
                "row_count": len(partition_rows),
                "lineage_group_count": len(
                    {cast(str, row["lineage_group_id"]) for row in partition_rows}
                ),
            }
        )
    cutoff = max(
        cast(str, cast(Mapping[str, Any], row["label"])["available_at_utc"])
        for row in rows
    )
    projection: JsonObject = {
        "document_version": DATASET_MANIFEST_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "dataset_version": DATASET_VERSION,
        "source": {
            "document_version": SOURCE_DOCUMENT_VERSION,
            "artifact_id": source["source_dataset_id"],
            "source_version": SOURCE_VERSION,
            "fingerprint": source["source_dataset_fingerprint"],
        },
        "builder": {
            "contract_version": BUILDER_CONTRACT_VERSION,
            "code_revision": _builder_code_revision(),
        },
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "factory_ids": [FACTORY_ID],
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_definitions": list(deepcopy(FEATURE_DEFINITIONS)),
        "label_policy": deepcopy(source["label_policy"]),
        "split_policy": deepcopy(source["split_policy"]),
        "privacy_policy": deepcopy(source["privacy_policy"]),
        "authority": deepcopy(source["authority"]),
        "training_data_cutoff_utc": cutoff,
        "counts": {
            "source_records": len(cast(Sequence[object], source["records"])),
            "eligible_rows": len(rows),
            "excluded_records": len(exclusions),
        },
        "partitions": partitions,
        "exclusion_reason_counts": {
            reason: sum(1 for item in exclusions if item["reason"] == reason)
            for reason in (
                "INTERRUPTED_NOT_LABEL_ELIGIBLE",
                "RUNNING_NOT_LABEL_ELIGIBLE",
            )
        },
        "synthetic": True,
        "synthetic_provenance": deepcopy(source["synthetic_provenance"]),
        "production_binding": False,
        "governance_boundary": deepcopy(source["governance_boundary"]),
    }
    digest = _fingerprint(projection)
    projection["artifact_id"] = "duration-dataset-manifest-" + digest.removeprefix(
        "sha256:"
    )
    projection["fingerprint"] = digest
    return projection


def build_duration_dataset(source: Mapping[str, Any]) -> JsonObject:
    """Validate and deterministically build the P6 Simulation dataset bundle."""

    source_copy = deepcopy(dict(source))
    _validate_root(source_copy)
    raw_records = cast(list[object], source_copy["records"])
    seen_ids: set[str] = set()
    seen_operation_revisions: set[tuple[str, int]] = set()
    exclusions: list[JsonObject] = []
    eligible: list[tuple[JsonObject, str]] = []

    for index, raw_record in enumerate(raw_records):
        record = _expect_object(raw_record, f"$.records[{index}]")
        is_eligible, reason = _validate_record(record, index)
        source_record_id = cast(str, record["source_record_id"])
        if source_record_id in seen_ids:
            _fail("DUPLICATE_SOURCE_RECORD", source_record_id)
        seen_ids.add(source_record_id)
        operation_revision = (
            cast(str, record["operation_id"]),
            cast(int, record["revision"]),
        )
        if operation_revision in seen_operation_revisions:
            _fail("DUPLICATE_OPERATION_REVISION", str(operation_revision))
        seen_operation_revisions.add(operation_revision)
        if is_eligible:
            partition = _partition_for(cast(str, record["label_available_at_utc"]))
            eligible.append((record, partition))
        else:
            assert reason is not None
            exclusions.append(
                {
                    "source_record_id": source_record_id,
                    "source_record_fingerprint": record["source_record_fingerprint"],
                    "lineage_group_id": record["lineage_group_id"],
                    "reason": reason,
                }
            )

    group_partitions: dict[str, set[str]] = {}
    for record, partition in eligible:
        group = cast(str, record["lineage_group_id"])
        group_partitions.setdefault(group, set()).add(partition)
    crossing_groups = sorted(
        group for group, names in group_partitions.items() if len(names) != 1
    )
    if crossing_groups:
        _fail("LINEAGE_GROUP_SPLIT_CROSSING", ",".join(crossing_groups))
    if not eligible:
        _fail("EMPTY_ELIGIBLE_DATASET", "no completed normal labels")

    partition_counts = {
        name: sum(1 for _, partition in eligible if partition == name)
        for name, _, _ in PARTITIONS
    }
    exclusion_counts = {
        reason: sum(1 for item in exclusions if item["reason"] == reason)
        for reason in EXPECTED_EXCLUSION_COUNTS
    }
    if partition_counts != EXPECTED_PARTITION_COUNTS:
        _fail("PROFILE_SHAPE_MISMATCH", "partition counts")
    if exclusion_counts != EXPECTED_EXCLUSION_COUNTS:
        _fail("PROFILE_SHAPE_MISMATCH", "exclusion counts")

    partition_order = {name: index for index, (name, _, _) in enumerate(PARTITIONS)}
    eligible.sort(
        key=lambda item: (
            partition_order[item[1]],
            cast(str, item[0]["label_available_at_utc"]),
            cast(str, item[0]["lineage_group_id"]),
            cast(str, item[0]["source_record_id"]),
        )
    )
    rows = [_dataset_row(record, partition) for record, partition in eligible]
    exclusions.sort(key=lambda item: cast(str, item["source_record_id"]))
    manifest = _manifest(source_copy, rows, exclusions)
    bundle: JsonObject = {
        "duration_dataset_bundle_version": DATASET_BUNDLE_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "dataset_manifest": manifest,
        "rows": rows,
        "exclusions": exclusions,
    }
    bundle["bundle_fingerprint"] = _fingerprint(bundle)
    return bundle


def write_duration_dataset(source: Mapping[str, Any], target: Path) -> JsonObject:
    """Build first, then atomically replace ``target`` with canonical JSON."""

    bundle = build_duration_dataset(source)
    payload = canonical_json_bytes(bundle) + b"\n"
    target = target.absolute()
    if target.is_symlink():
        _fail("ATOMIC_TARGET_SYMLINK_FORBIDDEN", target.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = -1
    temporary_path: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary_path = Path(raw_path)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    except OSError as error:
        _fail("ATOMIC_WRITE_FAILED", type(error).__name__)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return bundle
