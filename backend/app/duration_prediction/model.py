"""Deterministic, safe, Simulation-only duration baseline training.

The module deliberately uses only the Python standard library.  It trains a
small grouped median-residual baseline from the exact P6-03 train partition,
serializes data-only canonical JSON, and has no promotion, runtime, Planning,
network, database, or Production authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Never, cast

from app.duration_prediction.dataset import canonical_json_bytes


type JsonObject = dict[str, Any]

MODEL_ARTIFACT_VERSION = "duration-baseline-artifact.v1"
MODEL_BUNDLE_VERSION = "duration-model-bundle.v1"
MODEL_MANIFEST_VERSION = "duration-model-manifest.v1"
TRAINING_CONFIG_VERSION = "duration-training-config.v1"
TRAINING_REPLAY_VERSION = "duration-training-replay.v1"
BASELINE_ESTIMATE_VERSION = "duration-baseline-estimate.v1"
SCHEMA_SET_VERSION = "2.9.0"
CANONICALIZATION_VERSION = "canonical-json.v1"
FEATURE_SCHEMA_VERSION = "duration-features.v1"
MODEL_VERSION = "1.0.0"
ALGORITHM_ID = "grouped-median-residual-baseline"
ALGORITHM_VERSION = "1.0.0"
SERIALIZATION_FORMAT = "plantnexus-safe-canonical-json"
SERIALIZATION_VERSION = "1.0.0"
CONFIGURATION_VERSION = "SIM-P6-BASELINE-MODEL-001@1.0.0"
TRAINING_TIMESTAMP_UTC = "2026-09-01T09:00:00Z"
DATA_PLANE = "SIMULATION"
ENVIRONMENT = "TEST"
MAX_ARTIFACT_BYTES = 65_536
EXPECTED_DEPENDENCY_LOCK_DIGEST = (
    "sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82"
)
EXPECTED_DATASET_BUNDLE_FINGERPRINT = (
    "sha256:137ed52753f8decfcc2b0903c37e697f18c0e5a20369458aabddba6e7df81d98"
)
EXPECTED_DATASET_MANIFEST_ID = (
    "duration-dataset-manifest-"
    "d02f7818d4744e8a86205cfafe25efe1b39e2f1db6edc485a38e10aea8470bda"
)
EXPECTED_DATASET_MANIFEST_FINGERPRINT = (
    "sha256:d02f7818d4744e8a86205cfafe25efe1b39e2f1db6edc485a38e10aea8470bda"
)
OPEN_AUTHORITY_GAPS = ("OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015")
REQUIRED_FEATURES = (
    "planned_quantity",
    "setup_seconds",
    "standard_duration_seconds",
    "operation_family",
)
ACTIVE_FEATURES = ("standard_duration_seconds", "operation_family")
ZERO_WEIGHT_FEATURES = ("planned_quantity", "setup_seconds")
EXPECTED_PARTITION_COUNTS: Mapping[str, int] = {
    "train": 4,
    "validation": 2,
    "test": 2,
}


class P6ModelError(ValueError):
    """Stable fail-closed error for P6 baseline training and safe loading."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> Never:
    raise P6ModelError(code, detail)


def _reject_constant(value: str) -> Never:
    _fail("NON_FINITE_NUMBER", value)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


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
    if not isinstance(value, str) or not value or any(
        character.isspace() for character in value
    ):
        _fail("INVALID_IDENTIFIER", path)
    return value


def _expect_int(value: object, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("INVALID_INTEGER", path)
    if minimum is not None and value < minimum:
        _fail("INVALID_INTEGER", path)
    return value


def _expect_bool(value: object, expected: bool, path: str) -> None:
    if value is not expected:
        _fail("GOVERNANCE_BOUNDARY_MISMATCH", path)


def _expect_fingerprint(value: object, path: str) -> str:
    fingerprint = _expect_string(value, path)
    if (
        not fingerprint.startswith("sha256:")
        or len(fingerprint) != 71
        or any(character not in "0123456789abcdef" for character in fingerprint[7:])
    ):
        _fail("INVALID_FINGERPRINT", path)
    return fingerprint


def _identity(
    projection: Mapping[str, Any],
    *,
    id_field: str,
    fingerprint_field: str,
    prefix: str,
) -> JsonObject:
    result = deepcopy(dict(projection))
    digest = _fingerprint(result)
    result[id_field] = prefix + digest.removeprefix("sha256:")
    result[fingerprint_field] = digest
    return result


def _verify_identity(
    value: Mapping[str, Any],
    *,
    id_field: str,
    fingerprint_field: str,
    prefix: str,
    path: str,
) -> None:
    projection = {
        key: item
        for key, item in value.items()
        if key not in {id_field, fingerprint_field}
    }
    expected = _fingerprint(projection)
    if value.get(fingerprint_field) != expected:
        _fail("FINGERPRINT_MISMATCH", path)
    if value.get(id_field) != prefix + expected.removeprefix("sha256:"):
        _fail("IDENTITY_MISMATCH", path)


def _reference(
    value: Mapping[str, Any],
    *,
    document_field: str,
    id_field: str,
    fingerprint_field: str,
) -> JsonObject:
    return {
        "document_version": value[document_field],
        "artifact_id": value[id_field],
        "fingerprint": value[fingerprint_field],
    }


def _expect_reference(
    value: object,
    *,
    path: str,
    document_version: str,
    id_prefix: str,
) -> JsonObject:
    reference = _expect_object(value, path)
    _expect_keys(
        reference,
        {"document_version", "artifact_id", "fingerprint"},
        path,
    )
    if reference["document_version"] != document_version:
        _fail("MODEL_MANIFEST_MISMATCH", f"{path}.document_version")
    artifact_id = _expect_string(reference["artifact_id"], f"{path}.artifact_id")
    fingerprint = _expect_fingerprint(
        reference["fingerprint"], f"{path}.fingerprint"
    )
    if artifact_id != id_prefix + fingerprint.removeprefix("sha256:"):
        _fail("IDENTITY_MISMATCH", path)
    return reference


def _artifact_file_bytes(artifact: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(artifact) + b"\n"


def _load_strict_artifact_bytes(raw: bytes) -> JsonObject:
    if len(raw) > MAX_ARTIFACT_BYTES:
        _fail("ARTIFACT_TOO_LARGE", str(len(raw)))
    if b"\r" in raw.replace(b"\r\n", b""):
        _fail("NON_CANONICAL_ARTIFACT", "lone carriage return")
    normalized = raw.replace(b"\r\n", b"\n")
    try:
        text = normalized.decode("utf-8")
        loaded = json.loads(
            text,
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6ModelError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        _fail("ARTIFACT_PARSE_FAILED", type(error).__name__)
    artifact = _expect_object(loaded, "$")
    if _artifact_file_bytes(artifact) != normalized:
        _fail("NON_CANONICAL_ARTIFACT", "bytes")
    return artifact


def _source_code_identity() -> tuple[str, str]:
    source = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    digest = sha256(source).hexdigest()
    return digest[:40], f"sha256:{digest}"


def _feature_values(feature_record: Mapping[str, Any]) -> JsonObject:
    if feature_record.get("duration_feature_record_version") != "duration-feature-record.v1":
        _fail("FEATURE_VERSION_INCOMPATIBLE", "duration_feature_record_version")
    if feature_record.get("schema_set_version") != SCHEMA_SET_VERSION:
        _fail("SCHEMA_VERSION_INCOMPATIBLE", "feature record")
    if feature_record.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        _fail("FEATURE_VERSION_INCOMPATIBLE", "feature_schema_version")
    if feature_record.get("data_plane") != DATA_PLANE or feature_record.get(
        "environment"
    ) != ENVIRONMENT:
        _fail("MODEL_OUT_OF_SCOPE", "feature plane/environment")
    _expect_bool(feature_record.get("synthetic"), True, "feature synthetic")
    _expect_bool(
        feature_record.get("production_binding"), False, "feature production binding"
    )
    _expect_bool(feature_record.get("pii_fields_present"), False, "feature PII")
    _expect_bool(feature_record.get("target_fields_present"), False, "feature target")
    _verify_identity(
        feature_record,
        id_field="feature_record_id",
        fingerprint_field="feature_record_fingerprint",
        prefix="duration-feature-record-",
        path="feature record",
    )

    raw_features = feature_record.get("features")
    if not isinstance(raw_features, list):
        _fail("INVALID_FEATURES", "features")
    features: JsonObject = {}
    expected_metadata = {
        "planned_quantity": ("INTEGER", "COUNT"),
        "setup_seconds": ("INTEGER", "SECONDS"),
        "standard_duration_seconds": ("INTEGER", "SECONDS"),
        "operation_family": ("CATEGORY", "CATEGORY"),
    }
    cutoff = _expect_string(feature_record.get("as_of_cutoff_utc"), "as_of cutoff")
    for index, raw_feature in enumerate(raw_features):
        feature = _expect_object(raw_feature, f"features[{index}]")
        name = _expect_string(feature.get("feature_name"), f"features[{index}].name")
        if name in features or name not in expected_metadata:
            _fail("FEATURE_CONTRACT_MISMATCH", name)
        value_type, unit = expected_metadata[name]
        if feature.get("value_type") != value_type or feature.get("unit") != unit:
            _fail("FEATURE_CONTRACT_MISMATCH", name)
        if _expect_string(
            feature.get("available_at_utc"), f"features[{index}].available"
        ) > cutoff:
            _fail("FUTURE_FEATURE_LEAKAGE", name)
        value = feature.get("value")
        if name == "operation_family":
            features[name] = _expect_string(value, name)
        elif name == "setup_seconds":
            features[name] = _expect_int(value, name, minimum=0)
        else:
            features[name] = _expect_int(value, name, minimum=1)
    if tuple(sorted(features)) != tuple(sorted(REQUIRED_FEATURES)):
        _fail("FEATURE_CONTRACT_MISMATCH", "required feature set")
    return features


def _validate_dataset_bundle(
    bundle: Mapping[str, Any],
) -> tuple[JsonObject, list[JsonObject], list[JsonObject]]:
    candidate = deepcopy(dict(bundle))
    _expect_keys(
        candidate,
        {
            "duration_dataset_bundle_version",
            "schema_set_version",
            "canonicalization_version",
            "dataset_manifest",
            "rows",
            "exclusions",
            "bundle_fingerprint",
        },
        "$",
    )
    if candidate["duration_dataset_bundle_version"] != "duration-dataset-bundle.v1":
        _fail("DATASET_VERSION_INCOMPATIBLE", "bundle")
    if candidate["schema_set_version"] != SCHEMA_SET_VERSION:
        _fail("SCHEMA_VERSION_INCOMPATIBLE", "dataset bundle")
    if candidate["canonicalization_version"] != CANONICALIZATION_VERSION:
        _fail("CANONICALIZATION_INCOMPATIBLE", "dataset bundle")
    projection = {
        key: value for key, value in candidate.items() if key != "bundle_fingerprint"
    }
    if candidate["bundle_fingerprint"] != _fingerprint(projection):
        _fail("DATASET_FINGERPRINT_MISMATCH", "bundle")
    if candidate["bundle_fingerprint"] != EXPECTED_DATASET_BUNDLE_FINGERPRINT:
        _fail("DATASET_NOT_AUTHORIZED", str(candidate["bundle_fingerprint"]))

    manifest = _expect_object(candidate["dataset_manifest"], "dataset_manifest")
    if (
        manifest.get("document_version") != "duration-dataset-manifest.v1"
        or manifest.get("artifact_id") != EXPECTED_DATASET_MANIFEST_ID
        or manifest.get("fingerprint") != EXPECTED_DATASET_MANIFEST_FINGERPRINT
        or manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
        or manifest.get("data_plane") != DATA_PLANE
        or manifest.get("environment") != ENVIRONMENT
    ):
        _fail("DATASET_MANIFEST_MISMATCH", "P6-03 exact reference")
    _expect_bool(manifest.get("synthetic"), True, "dataset synthetic")
    _expect_bool(manifest.get("production_binding"), False, "dataset production")

    raw_rows = candidate["rows"]
    if not isinstance(raw_rows, list) or len(raw_rows) != 8:
        _fail("DATASET_SHAPE_MISMATCH", "rows")
    rows = [_expect_object(row, f"rows[{index}]") for index, row in enumerate(raw_rows)]
    partition_counts = {
        name: sum(row.get("partition") == name for row in rows)
        for name in EXPECTED_PARTITION_COUNTS
    }
    if partition_counts != dict(EXPECTED_PARTITION_COUNTS):
        _fail("DATASET_SHAPE_MISMATCH", "partitions")
    row_ids: set[str] = set()
    for index, row in enumerate(rows):
        _verify_identity(
            row,
            id_field="dataset_row_id",
            fingerprint_field="dataset_row_fingerprint",
            prefix="duration-dataset-row-",
            path=f"rows[{index}]",
        )
        row_id = _expect_string(row.get("dataset_row_id"), f"rows[{index}].id")
        if row_id in row_ids:
            _fail("DUPLICATE_TRAINING_ROW", row_id)
        row_ids.add(row_id)
        _feature_values(_expect_object(row.get("feature_record"), "feature_record"))
    training_rows = sorted(
        (row for row in rows if row["partition"] == "train"),
        key=lambda row: cast(str, row["dataset_row_id"]),
    )
    if len(training_rows) != 4:
        _fail("DATASET_SHAPE_MISMATCH", "training rows")
    return candidate, training_rows, rows


def build_training_configuration() -> JsonObject:
    """Return the fixed, content-addressed P6-04 training configuration."""

    projection: JsonObject = {
        "document_version": TRAINING_CONFIG_VERSION,
        "configuration_version": CONFIGURATION_VERSION,
        "model_version": MODEL_VERSION,
        "algorithm": {"id": ALGORITHM_ID, "version": ALGORITHM_VERSION},
        "dataset_bundle_fingerprint": EXPECTED_DATASET_BUNDLE_FINGERPRINT,
        "training_partition": "train",
        "required_feature_names": list(REQUIRED_FEATURES),
        "active_feature_names": list(ACTIVE_FEATURES),
        "zero_weight_feature_names": list(ZERO_WEIGHT_FEATURES),
        "residual_policy": {
            "name": "operation-family-median-residual.v1",
            "even_sample_policy": "EXACT_MIDDLE_MEAN",
        },
        "prediction_policy": {
            "rounding": "fraction-half-away-from-zero.v1",
            "upper_margin": "nearest-rank-absolute-training-residual.v1",
            "quantile_numerator": 9,
            "quantile_denominator": 10,
            "quality_or_confidence_threshold": False,
        },
        "determinism": {
            "randomness": "NONE",
            "seed_accepted": False,
            "host_clock_in_identity": False,
            "training_timestamp_utc": TRAINING_TIMESTAMP_UTC,
        },
        "serialization": {
            "format": SERIALIZATION_FORMAT,
            "version": SERIALIZATION_VERSION,
            "max_bytes": MAX_ARTIFACT_BYTES,
            "digest_projection": "canonical-json-payload-without-transport-newline.v1",
            "unsafe_executable_formats_allowed": False,
        },
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "synthetic": True,
        "synthetic_provenance": {
            "assumption_profile": "SIM-P6-DURATION-CONTRACT-001@1.0.0",
            "assumption_refs": [
                "SIM-ASSUMPTION-021",
                "SIM-ASSUMPTION-022",
                "SIM-ASSUMPTION-023",
            ],
        },
        "production_binding": False,
        "governance_boundary": {
            "production_authorized": False,
            "promotion_authorized": False,
            "planning_authority": "NONE",
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        },
    }
    return _identity(
        projection,
        id_field="configuration_id",
        fingerprint_field="configuration_fingerprint",
        prefix="duration-training-config-",
    )


def _median(values: Sequence[Fraction]) -> Fraction:
    if not values:
        _fail("INSUFFICIENT_TRAINING_DATA", "empty family")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _round_half_away_from_zero(value: Fraction) -> int:
    sign = -1 if value < 0 else 1
    absolute = abs(value)
    quotient, remainder = divmod(absolute.numerator, absolute.denominator)
    if remainder * 2 >= absolute.denominator:
        quotient += 1
    return sign * quotient


def _nearest_rank(
    values: Sequence[int], *, numerator: int, denominator: int
) -> int:
    if not values or numerator <= 0 or numerator > denominator:
        _fail("INVALID_MARGIN_POLICY", "nearest rank")
    ordered = sorted(values)
    rank = (numerator * len(ordered) + denominator - 1) // denominator
    return ordered[rank - 1]


def _build_artifact(
    dataset: Mapping[str, Any],
    training_rows: Sequence[Mapping[str, Any]],
    configuration: Mapping[str, Any],
    dependency_lock_digest: str,
) -> JsonObject:
    grouped_residuals: dict[str, list[Fraction]] = {}
    row_inputs: list[tuple[Mapping[str, Any], str, int, int]] = []
    for row in training_rows:
        feature_record = _expect_object(row["feature_record"], "feature_record")
        features = _feature_values(feature_record)
        family = cast(str, features["operation_family"])
        standard = cast(int, features["standard_duration_seconds"])
        label = _expect_object(row["label"], "label")
        actual = _expect_int(label.get("value"), "training label", minimum=1)
        grouped_residuals.setdefault(family, []).append(Fraction(actual - standard))
        row_inputs.append((row, family, standard, actual))

    family_offsets = {
        family: _median(residuals)
        for family, residuals in sorted(grouped_residuals.items())
    }
    if set(family_offsets) != {"milling", "turning"}:
        _fail("MODEL_SCOPE_MISMATCH", "operation families")

    absolute_residuals: list[int] = []
    for _row, family, standard, actual in row_inputs:
        p50 = _round_half_away_from_zero(Fraction(standard) + family_offsets[family])
        if p50 <= 0:
            _fail("INVALID_MODEL_OUTPUT", family)
        absolute_residuals.append(abs(actual - p50))
    p90_margin = _nearest_rank(absolute_residuals, numerator=9, denominator=10)
    code_revision, code_digest = _source_code_identity()
    manifest = _expect_object(dataset["dataset_manifest"], "dataset_manifest")
    training_cutoff = max(
        _expect_string(
            _expect_object(row["label"], "label").get("available_at_utc"),
            "training label available",
        )
        for row in training_rows
    )
    scope = {
        "factory_ids": sorted(
            {
                cast(str, _expect_object(row["feature_record"], "feature")["factory_id"])
                for row in training_rows
            }
        ),
        "operation_type_ids": sorted(
            {cast(str, row["operation_type_id"]) for row in training_rows}
        ),
        "resource_ids": sorted(
            {
                cast(str, _expect_object(row["feature_record"], "feature")["resource_id"])
                for row in training_rows
            }
        ),
        "operation_families": sorted(family_offsets),
    }
    return {
        "duration_baseline_artifact_version": MODEL_ARTIFACT_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "model_version": MODEL_VERSION,
        "algorithm": {"id": ALGORITHM_ID, "version": ALGORITHM_VERSION},
        "feature_contract": {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "required_features": list(REQUIRED_FEATURES),
            "active_features": list(ACTIVE_FEATURES),
            "zero_weight_features": list(ZERO_WEIGHT_FEATURES),
        },
        "dataset": {
            "manifest": {
                "document_version": manifest["document_version"],
                "artifact_id": manifest["artifact_id"],
                "fingerprint": manifest["fingerprint"],
            },
            "bundle_fingerprint": dataset["bundle_fingerprint"],
        },
        "configuration": _reference(
            configuration,
            document_field="document_version",
            id_field="configuration_id",
            fingerprint_field="configuration_fingerprint",
        ),
        "parameters": {
            "family_offsets_seconds": [
                {
                    "operation_family": family,
                    "numerator": offset.numerator,
                    "denominator": offset.denominator,
                }
                for family, offset in family_offsets.items()
            ],
            "p90_margin_seconds": p90_margin,
            "rounding_policy": "fraction-half-away-from-zero.v1",
            "margin_policy": "nearest-rank-absolute-training-residual.v1@9/10",
        },
        "training_provenance": {
            "code_revision": code_revision,
            "code_digest": code_digest,
            "dependency_lock_digest": dependency_lock_digest,
            "partition": "train",
            "training_row_ids": [row["dataset_row_id"] for row in training_rows],
            "training_row_fingerprints": [
                row["dataset_row_fingerprint"] for row in training_rows
            ],
            "training_data_cutoff_utc": training_cutoff,
        },
        "scope": scope,
        "synthetic_provenance": deepcopy(configuration["synthetic_provenance"]),
        "governance_boundary": deepcopy(configuration["governance_boundary"]),
    }


@dataclass(frozen=True)
class LoadedDurationModel:
    """Validated data-only model parameters; it cannot execute artifact code."""

    model_version: str
    artifact_digest: str
    dataset_manifest_id: str
    dataset_manifest_fingerprint: str
    dataset_bundle_fingerprint: str
    configuration_id: str
    configuration_fingerprint: str
    family_offsets: Mapping[str, Fraction]
    p90_margin_seconds: int
    factory_ids: tuple[str, ...]
    operation_type_ids: tuple[str, ...]
    resource_ids: tuple[str, ...]
    operation_families: tuple[str, ...]


@dataclass(frozen=True)
class DurationModelBuild:
    """One deterministic artifact plus its safe manifest/replay bundle."""

    artifact: JsonObject
    artifact_digest: str
    bundle: JsonObject


def _loaded_from_artifact(
    artifact: Mapping[str, Any], artifact_digest: str
) -> LoadedDurationModel:
    _expect_keys(
        artifact,
        {
            "duration_baseline_artifact_version",
            "canonicalization_version",
            "model_version",
            "algorithm",
            "feature_contract",
            "dataset",
            "configuration",
            "parameters",
            "training_provenance",
            "scope",
            "synthetic_provenance",
            "governance_boundary",
        },
        "artifact",
    )
    if artifact["duration_baseline_artifact_version"] != MODEL_ARTIFACT_VERSION:
        _fail("MODEL_VERSION_INCOMPATIBLE", "artifact")
    if artifact["canonicalization_version"] != CANONICALIZATION_VERSION:
        _fail("CANONICALIZATION_INCOMPATIBLE", "artifact")
    if artifact["model_version"] != MODEL_VERSION:
        _fail("MODEL_VERSION_INCOMPATIBLE", "model")
    algorithm = _expect_object(artifact["algorithm"], "algorithm")
    if algorithm != {"id": ALGORITHM_ID, "version": ALGORITHM_VERSION}:
        _fail("ALGORITHM_INCOMPATIBLE", "algorithm")
    feature_contract = _expect_object(artifact["feature_contract"], "feature_contract")
    if feature_contract != {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "required_features": list(REQUIRED_FEATURES),
        "active_features": list(ACTIVE_FEATURES),
        "zero_weight_features": list(ZERO_WEIGHT_FEATURES),
    }:
        _fail("FEATURE_VERSION_INCOMPATIBLE", "artifact feature contract")
    dataset = _expect_object(artifact["dataset"], "dataset")
    _expect_keys(dataset, {"manifest", "bundle_fingerprint"}, "dataset")
    manifest = _expect_object(dataset["manifest"], "dataset.manifest")
    if manifest != {
        "document_version": "duration-dataset-manifest.v1",
        "artifact_id": EXPECTED_DATASET_MANIFEST_ID,
        "fingerprint": EXPECTED_DATASET_MANIFEST_FINGERPRINT,
    } or dataset["bundle_fingerprint"] != EXPECTED_DATASET_BUNDLE_FINGERPRINT:
        _fail("DATASET_VERSION_INCOMPATIBLE", "artifact dataset")
    configuration = _expect_object(artifact["configuration"], "configuration")
    expected_configuration = build_training_configuration()
    expected_configuration_reference = _reference(
        expected_configuration,
        document_field="document_version",
        id_field="configuration_id",
        fingerprint_field="configuration_fingerprint",
    )
    if configuration != expected_configuration_reference:
        _fail("CONFIGURATION_MISMATCH", "artifact configuration")

    parameters = _expect_object(artifact["parameters"], "parameters")
    _expect_keys(
        parameters,
        {
            "family_offsets_seconds",
            "p90_margin_seconds",
            "rounding_policy",
            "margin_policy",
        },
        "parameters",
    )
    if (
        parameters["rounding_policy"] != "fraction-half-away-from-zero.v1"
        or parameters["margin_policy"]
        != "nearest-rank-absolute-training-residual.v1@9/10"
    ):
        _fail("CONFIGURATION_MISMATCH", "prediction policy")
    raw_offsets = parameters["family_offsets_seconds"]
    if not isinstance(raw_offsets, list):
        _fail("INVALID_MODEL_PARAMETERS", "family offsets")
    offsets: dict[str, Fraction] = {}
    for index, raw_offset in enumerate(raw_offsets):
        offset = _expect_object(raw_offset, f"offsets[{index}]")
        _expect_keys(
            offset,
            {"operation_family", "numerator", "denominator"},
            f"offsets[{index}]",
        )
        family = _expect_string(offset["operation_family"], "operation family")
        numerator = _expect_int(offset["numerator"], "offset numerator")
        denominator = _expect_int(offset["denominator"], "offset denominator", minimum=1)
        if family in offsets:
            _fail("INVALID_MODEL_PARAMETERS", "duplicate family")
        value = Fraction(numerator, denominator)
        if value.numerator != numerator or value.denominator != denominator:
            _fail("NON_CANONICAL_MODEL_PARAMETERS", family)
        offsets[family] = value
    if tuple(sorted(offsets)) != ("milling", "turning"):
        _fail("MODEL_SCOPE_MISMATCH", "families")
    margin = _expect_int(
        parameters["p90_margin_seconds"], "p90 margin", minimum=0
    )

    provenance = _expect_object(artifact["training_provenance"], "training provenance")
    _expect_keys(
        provenance,
        {
            "code_revision",
            "code_digest",
            "dependency_lock_digest",
            "partition",
            "training_row_ids",
            "training_row_fingerprints",
            "training_data_cutoff_utc",
        },
        "training provenance",
    )
    code_revision, code_digest = _source_code_identity()
    if provenance["code_revision"] != code_revision or provenance["code_digest"] != code_digest:
        _fail("TRAINING_CODE_MISMATCH", "artifact")
    if provenance["dependency_lock_digest"] != EXPECTED_DEPENDENCY_LOCK_DIGEST:
        _fail("DEPENDENCY_LOCK_MISMATCH", "artifact")
    if provenance["partition"] != "train":
        _fail("TRAINING_PARTITION_MISMATCH", str(provenance["partition"]))
    training_row_ids = provenance["training_row_ids"]
    training_row_fingerprints = provenance["training_row_fingerprints"]
    if (
        not isinstance(training_row_ids, list)
        or not isinstance(training_row_fingerprints, list)
        or len(training_row_ids) != 4
        or len(training_row_fingerprints) != 4
    ):
        _fail("TRAINING_PARTITION_MISMATCH", "training lineage")

    scope = _expect_object(artifact["scope"], "scope")
    _expect_keys(
        scope,
        {"factory_ids", "operation_type_ids", "resource_ids", "operation_families"},
        "scope",
    )
    factories = tuple(cast(list[str], scope["factory_ids"]))
    operation_types = tuple(cast(list[str], scope["operation_type_ids"]))
    resources = tuple(cast(list[str], scope["resource_ids"]))
    families = tuple(cast(list[str], scope["operation_families"]))
    if (
        factories != ("factory-sim-p6-001",)
        or operation_types != ("operation-type-milling", "operation-type-turning")
        or resources
        != ("resource-sim-p6-1", "resource-sim-p6-2", "resource-sim-p6-3")
        or families != ("milling", "turning")
    ):
        _fail("MODEL_SCOPE_MISMATCH", "artifact scope")
    synthetic = _expect_object(artifact["synthetic_provenance"], "synthetic")
    if synthetic != build_training_configuration()["synthetic_provenance"]:
        _fail("GOVERNANCE_BOUNDARY_MISMATCH", "synthetic provenance")
    governance = _expect_object(artifact["governance_boundary"], "governance")
    if governance != build_training_configuration()["governance_boundary"]:
        _fail("GOVERNANCE_BOUNDARY_MISMATCH", "artifact governance")
    return LoadedDurationModel(
        model_version=MODEL_VERSION,
        artifact_digest=artifact_digest,
        dataset_manifest_id=EXPECTED_DATASET_MANIFEST_ID,
        dataset_manifest_fingerprint=EXPECTED_DATASET_MANIFEST_FINGERPRINT,
        dataset_bundle_fingerprint=EXPECTED_DATASET_BUNDLE_FINGERPRINT,
        configuration_id=cast(str, configuration["artifact_id"]),
        configuration_fingerprint=cast(str, configuration["fingerprint"]),
        family_offsets=dict(offsets),
        p90_margin_seconds=margin,
        factory_ids=factories,
        operation_type_ids=operation_types,
        resource_ids=resources,
        operation_families=families,
    )


def predict_duration(
    model: LoadedDurationModel, feature_record: Mapping[str, Any]
) -> JsonObject:
    """Produce a deterministic pre-evaluation estimate from one FeatureRecord."""

    features = _feature_values(feature_record)
    factory = _expect_string(feature_record.get("factory_id"), "factory")
    resource = _expect_string(feature_record.get("resource_id"), "resource")
    family = cast(str, features["operation_family"])
    if factory not in model.factory_ids or resource not in model.resource_ids:
        _fail("MODEL_OUT_OF_SCOPE", f"{factory}/{resource}")
    if family not in model.family_offsets:
        _fail("MODEL_OUT_OF_SCOPE", family)
    standard = cast(int, features["standard_duration_seconds"])
    p50 = _round_half_away_from_zero(
        Fraction(standard) + model.family_offsets[family]
    )
    p90 = p50 + model.p90_margin_seconds
    if p50 <= 0 or p90 < p50:
        _fail("INVALID_MODEL_OUTPUT", family)
    projection: JsonObject = {
        "duration_baseline_estimate_version": BASELINE_ESTIMATE_VERSION,
        "feature_record_reference": {
            "duration_feature_record_version": feature_record[
                "duration_feature_record_version"
            ],
            "feature_record_id": feature_record["feature_record_id"],
            "feature_record_fingerprint": feature_record[
                "feature_record_fingerprint"
            ],
            "feature_schema_version": feature_record["feature_schema_version"],
        },
        "model_reference": {
            "model_version": model.model_version,
            "model_artifact_digest": model.artifact_digest,
        },
        "unit": "SECONDS",
        "p50_seconds": p50,
        "p90_seconds": p90,
        "confidence_status": "NOT_ESTABLISHED_BY_P6_04",
        "evaluation_gate": "NOT_EVALUATED_BY_P6_04",
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "synthetic": True,
        "production_binding": False,
        "planning_authority": "NONE",
    }
    return _identity(
        projection,
        id_field="estimate_id",
        fingerprint_field="estimate_fingerprint",
        prefix="duration-baseline-estimate-",
    )


def _build_replay(
    model: LoadedDurationModel,
    rows: Sequence[Mapping[str, Any]],
    configuration: Mapping[str, Any],
    training_rows: Sequence[Mapping[str, Any]],
) -> JsonObject:
    estimates = []
    for row in sorted(rows, key=lambda item: cast(str, item["dataset_row_id"])):
        estimate = predict_duration(
            model, _expect_object(row["feature_record"], "feature record")
        )
        estimates.append(
            {
                "dataset_row_id": row["dataset_row_id"],
                "partition": row["partition"],
                "estimate": estimate,
            }
        )
    projection: JsonObject = {
        "document_version": TRAINING_REPLAY_VERSION,
        "dataset_manifest": {
            "document_version": "duration-dataset-manifest.v1",
            "artifact_id": model.dataset_manifest_id,
            "fingerprint": model.dataset_manifest_fingerprint,
        },
        "dataset_bundle_fingerprint": model.dataset_bundle_fingerprint,
        "model_artifact_digest": model.artifact_digest,
        "configuration": _reference(
            configuration,
            document_field="document_version",
            id_field="configuration_id",
            fingerprint_field="configuration_fingerprint",
        ),
        "training_partition": "train",
        "training_row_ids": [row["dataset_row_id"] for row in training_rows],
        "estimates": estimates,
        "determinism": {
            "same_input_replays": 2,
            "source_order_replays": 1,
            "artifact_bytes_identical": True,
            "estimate_bytes_identical": True,
            "randomness": "NONE",
        },
        "boundaries": {
            "labels_in_replay_artifact": False,
            "quality_metrics": "NOT_COMPUTED",
            "confidence_threshold": "NOT_FORMED",
            "evaluation_gate": "NOT_RUN",
            "promotion": "NOT_AUTHORIZED",
            "runtime_or_planning_authority": "NONE",
            "production_authorized": False,
        },
    }
    return _identity(
        projection,
        id_field="artifact_id",
        fingerprint_field="fingerprint",
        prefix="duration-training-replay-",
    )


def _authorization_decision(artifact_digest: str) -> JsonObject:
    projection: JsonObject = {
        "document_version": "duration-model-decision.v1",
        "decision": "SIMULATION_EVALUATION_ONLY",
        "model_artifact_digest": artifact_digest,
        "production_authorized": False,
        "promotion_authorized": False,
        "evaluation_gate": "NOT_RUN",
        "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        "assumption_refs": ["SIM-ASSUMPTION-021", "SIM-ASSUMPTION-022", "SIM-ASSUMPTION-023"],
    }
    return _identity(
        projection,
        id_field="artifact_id",
        fingerprint_field="fingerprint",
        prefix="duration-model-decision-",
    )


def _rollback_authority() -> JsonObject:
    projection: JsonObject = {
        "document_version": "standard-duration-authority.v1",
        "authority": "OperationResourceOption.final_duration_seconds",
        "selection": "STANDARD_DURATION",
        "model_may_override": False,
        "production_authorized": False,
        "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
    }
    return _identity(
        projection,
        id_field="artifact_id",
        fingerprint_field="fingerprint",
        prefix="standard-duration-authority-",
    )


def _build_manifest(
    artifact: Mapping[str, Any],
    artifact_digest: str,
    configuration: Mapping[str, Any],
    replay: Mapping[str, Any],
    decision: Mapping[str, Any],
    rollback: Mapping[str, Any],
) -> JsonObject:
    provenance = _expect_object(artifact["training_provenance"], "provenance")
    scope = _expect_object(artifact["scope"], "scope")
    projection: JsonObject = {
        "duration_model_manifest_version": MODEL_MANIFEST_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "model_version": MODEL_VERSION,
        "model_artifact": {
            "artifact_digest": artifact_digest,
            "media_type": "application/octet-stream",
            "serialization_format": SERIALIZATION_FORMAT,
            "serialization_version": SERIALIZATION_VERSION,
        },
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "dataset_manifest": {
            "document_version": "duration-dataset-manifest.v1",
            "artifact_id": EXPECTED_DATASET_MANIFEST_ID,
            "fingerprint": EXPECTED_DATASET_MANIFEST_FINGERPRINT,
        },
        "training_provenance": {
            "code_revision": provenance["code_revision"],
            "dependency_lock_digest": provenance["dependency_lock_digest"],
            "configuration": _reference(
                configuration,
                document_field="document_version",
                id_field="configuration_id",
                fingerprint_field="configuration_fingerprint",
            ),
            "algorithm_id": ALGORITHM_ID,
            "algorithm_version": ALGORITHM_VERSION,
            "deterministic_replay_reference": _reference(
                replay,
                document_field="document_version",
                id_field="artifact_id",
                fingerprint_field="fingerprint",
            ),
        },
        "training_data_cutoff_utc": provenance["training_data_cutoff_utc"],
        "scope": {
            "factory_ids": scope["factory_ids"],
            "operation_type_ids": scope["operation_type_ids"],
            "resource_ids": scope["resource_ids"],
        },
        "use_authorization": {
            "decision": "SIMULATION_EVALUATION_ONLY",
            "decision_reference": _reference(
                decision,
                document_field="document_version",
                id_field="artifact_id",
                fingerprint_field="fingerprint",
            ),
            "rollback_reference": _reference(
                rollback,
                document_field="document_version",
                id_field="artifact_id",
                fingerprint_field="fingerprint",
            ),
            "production_authorized": False,
        },
        "fallback_contract_version": "standard-duration-fallback.v1",
        "created_at_utc": TRAINING_TIMESTAMP_UTC,
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "synthetic": True,
        "synthetic_provenance": {
            "assumption_profile": "SIM-P6-DURATION-CONTRACT-001@1.0.0",
            "assumption_refs": [
                "SIM-ASSUMPTION-021",
                "SIM-ASSUMPTION-022",
                "SIM-ASSUMPTION-023",
            ],
        },
        "production_binding": False,
        "governance_boundary": {
            "production_authorized": False,
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        },
    }
    return _identity(
        projection,
        id_field="model_manifest_id",
        fingerprint_field="model_manifest_fingerprint",
        prefix="duration-model-manifest-",
    )


def _validate_manifest(
    manifest: Mapping[str, Any],
    artifact: Mapping[str, Any],
    artifact_digest: str,
    configuration: Mapping[str, Any],
) -> None:
    _expect_keys(
        manifest,
        {
            "duration_model_manifest_version",
            "schema_set_version",
            "canonicalization_version",
            "model_manifest_id",
            "model_manifest_fingerprint",
            "model_version",
            "model_artifact",
            "feature_schema_version",
            "dataset_manifest",
            "training_provenance",
            "training_data_cutoff_utc",
            "scope",
            "use_authorization",
            "fallback_contract_version",
            "created_at_utc",
            "data_plane",
            "environment",
            "synthetic",
            "synthetic_provenance",
            "production_binding",
            "governance_boundary",
        },
        "model manifest",
    )
    _verify_identity(
        manifest,
        id_field="model_manifest_id",
        fingerprint_field="model_manifest_fingerprint",
        prefix="duration-model-manifest-",
        path="model manifest",
    )
    if (
        manifest.get("duration_model_manifest_version") != MODEL_MANIFEST_VERSION
        or manifest.get("schema_set_version") != SCHEMA_SET_VERSION
        or manifest.get("canonicalization_version") != CANONICALIZATION_VERSION
        or manifest.get("model_version") != MODEL_VERSION
        or manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
        or manifest.get("data_plane") != DATA_PLANE
        or manifest.get("environment") != ENVIRONMENT
        or manifest.get("created_at_utc") != TRAINING_TIMESTAMP_UTC
    ):
        _fail("MODEL_MANIFEST_MISMATCH", "root")
    model_artifact = _expect_object(manifest.get("model_artifact"), "model artifact")
    _expect_keys(
        model_artifact,
        {
            "artifact_digest",
            "media_type",
            "serialization_format",
            "serialization_version",
        },
        "model artifact",
    )
    if model_artifact.get("serialization_format") != SERIALIZATION_FORMAT:
        _fail("UNSAFE_SERIALIZATION_FORMAT", str(model_artifact.get("serialization_format")))
    if (
        model_artifact.get("media_type") != "application/octet-stream"
        or model_artifact.get("serialization_version") != SERIALIZATION_VERSION
    ):
        _fail("SERIALIZATION_VERSION_INCOMPATIBLE", "manifest")
    if model_artifact.get("artifact_digest") != artifact_digest:
        _fail("ARTIFACT_DIGEST_MISMATCH", "manifest")
    dataset = _expect_object(manifest.get("dataset_manifest"), "dataset manifest")
    _expect_keys(
        dataset,
        {"document_version", "artifact_id", "fingerprint"},
        "dataset manifest",
    )
    if dataset != {
        "document_version": "duration-dataset-manifest.v1",
        "artifact_id": EXPECTED_DATASET_MANIFEST_ID,
        "fingerprint": EXPECTED_DATASET_MANIFEST_FINGERPRINT,
    }:
        _fail("DATASET_VERSION_INCOMPATIBLE", "manifest")
    expected_config_ref = _reference(
        configuration,
        document_field="document_version",
        id_field="configuration_id",
        fingerprint_field="configuration_fingerprint",
    )
    provenance = _expect_object(manifest.get("training_provenance"), "provenance")
    _expect_keys(
        provenance,
        {
            "code_revision",
            "dependency_lock_digest",
            "configuration",
            "algorithm_id",
            "algorithm_version",
            "deterministic_replay_reference",
        },
        "training provenance",
    )
    artifact_provenance = _expect_object(artifact["training_provenance"], "artifact provenance")
    if (
        provenance.get("code_revision") != artifact_provenance["code_revision"]
        or provenance.get("dependency_lock_digest") != EXPECTED_DEPENDENCY_LOCK_DIGEST
        or provenance.get("configuration") != expected_config_ref
        or provenance.get("algorithm_id") != ALGORITHM_ID
        or provenance.get("algorithm_version") != ALGORITHM_VERSION
    ):
        _fail("PROVENANCE_INCOMPLETE", "manifest")
    _expect_reference(
        provenance.get("deterministic_replay_reference"),
        path="training provenance.replay",
        document_version=TRAINING_REPLAY_VERSION,
        id_prefix="duration-training-replay-",
    )
    if manifest.get("training_data_cutoff_utc") != artifact_provenance.get(
        "training_data_cutoff_utc"
    ):
        _fail("MODEL_MANIFEST_MISMATCH", "training_data_cutoff_utc")

    scope = _expect_object(manifest.get("scope"), "scope")
    _expect_keys(
        scope,
        {"factory_ids", "operation_type_ids", "resource_ids"},
        "scope",
    )
    artifact_scope = _expect_object(artifact.get("scope"), "artifact scope")
    if scope != {
        "factory_ids": artifact_scope.get("factory_ids"),
        "operation_type_ids": artifact_scope.get("operation_type_ids"),
        "resource_ids": artifact_scope.get("resource_ids"),
    }:
        _fail("MODEL_MANIFEST_MISMATCH", "scope")

    use_authorization = _expect_object(
        manifest.get("use_authorization"), "use authorization"
    )
    _expect_keys(
        use_authorization,
        {
            "decision",
            "decision_reference",
            "rollback_reference",
            "production_authorized",
        },
        "use authorization",
    )
    if (
        use_authorization.get("decision") != "SIMULATION_EVALUATION_ONLY"
        or use_authorization.get("production_authorized") is not False
    ):
        _fail("GOVERNANCE_BOUNDARY_MISMATCH", "use authorization")
    _expect_reference(
        use_authorization.get("decision_reference"),
        path="use authorization.decision",
        document_version="duration-model-decision.v1",
        id_prefix="duration-model-decision-",
    )
    _expect_reference(
        use_authorization.get("rollback_reference"),
        path="use authorization.rollback",
        document_version="standard-duration-authority.v1",
        id_prefix="standard-duration-authority-",
    )
    if manifest.get("fallback_contract_version") != "standard-duration-fallback.v1":
        _fail("MODEL_MANIFEST_MISMATCH", "fallback_contract_version")
    _expect_bool(manifest.get("synthetic"), True, "manifest synthetic")
    _expect_bool(manifest.get("production_binding"), False, "manifest production")
    if manifest.get("synthetic_provenance") != configuration.get(
        "synthetic_provenance"
    ):
        _fail("GOVERNANCE_BOUNDARY_MISMATCH", "manifest synthetic provenance")
    if manifest.get("governance_boundary") != {
        "production_authorized": False,
        "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
    }:
        _fail("GOVERNANCE_BOUNDARY_MISMATCH", "manifest governance")


def build_duration_model(
    dataset_bundle: Mapping[str, Any], dependency_lock_digest: str
) -> DurationModelBuild:
    """Train and replay the fixed P6-04 baseline without side effects."""

    if dependency_lock_digest != EXPECTED_DEPENDENCY_LOCK_DIGEST:
        _fail("DEPENDENCY_LOCK_MISMATCH", dependency_lock_digest)
    dataset, training_rows, rows = _validate_dataset_bundle(dataset_bundle)
    configuration = build_training_configuration()
    artifact = _build_artifact(
        dataset, training_rows, configuration, dependency_lock_digest
    )
    artifact_digest = _fingerprint(artifact)
    loaded = _loaded_from_artifact(artifact, artifact_digest)
    replay = _build_replay(loaded, rows, configuration, training_rows)
    decision = _authorization_decision(artifact_digest)
    rollback = _rollback_authority()
    manifest = _build_manifest(
        artifact,
        artifact_digest,
        configuration,
        replay,
        decision,
        rollback,
    )
    _validate_manifest(manifest, artifact, artifact_digest, configuration)
    bundle_projection: JsonObject = {
        "duration_model_bundle_version": MODEL_BUNDLE_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "training_configuration": configuration,
        "use_authorization_decision": decision,
        "rollback_authority": rollback,
        "model_manifest": manifest,
        "replay": replay,
    }
    bundle = deepcopy(bundle_projection)
    bundle["bundle_fingerprint"] = _fingerprint(bundle_projection)
    return DurationModelBuild(
        artifact=artifact,
        artifact_digest=artifact_digest,
        bundle=bundle,
    )


def load_duration_model(
    path: Path,
    model_manifest: Mapping[str, Any],
    training_configuration: Mapping[str, Any],
) -> LoadedDurationModel:
    """Safely load a canonical data-only artifact after digest validation."""

    if path.is_symlink():
        _fail("UNSAFE_ARTIFACT_PATH", "symlink")
    try:
        if not path.is_file():
            _fail("ARTIFACT_READ_FAILED", "not a regular file")
        raw = path.read_bytes()
    except P6ModelError:
        raise
    except OSError as error:
        _fail("ARTIFACT_READ_FAILED", type(error).__name__)
    artifact = _load_strict_artifact_bytes(raw)
    artifact_digest = _fingerprint(artifact)
    expected_configuration = build_training_configuration()
    if dict(training_configuration) != expected_configuration:
        _fail("CONFIGURATION_MISMATCH", "loader")
    _validate_manifest(
        model_manifest,
        artifact,
        artifact_digest,
        training_configuration,
    )
    return _loaded_from_artifact(artifact, artifact_digest)


def write_duration_model(
    dataset_bundle: Mapping[str, Any],
    target: Path,
    dependency_lock_digest: str,
) -> JsonObject:
    """Atomically publish the safe artifact and return its manifest bundle."""

    build = build_duration_model(dataset_bundle, dependency_lock_digest)
    if target.is_symlink():
        _fail("UNSAFE_ARTIFACT_PATH", "symlink target")
    if target.exists() and not target.is_file():
        _fail("UNSAFE_ARTIFACT_PATH", "target is not a regular file")
    parent = target.parent
    temporary_path: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(_artifact_file_bytes(build.artifact))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        _fail("ATOMIC_WRITE_FAILED", type(error).__name__)
    return deepcopy(build.bundle)


def artifact_file_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Expose the exact safe file framing for fixture/report verification."""

    return _artifact_file_bytes(artifact)


def dependency_lock_digest(path: Path) -> str:
    """Hash the immutable dependency lock without interpreting its contents."""

    try:
        return f"sha256:{sha256(path.read_bytes()).hexdigest()}"
    except OSError as error:
        _fail("DEPENDENCY_LOCK_READ_FAILED", type(error).__name__)
