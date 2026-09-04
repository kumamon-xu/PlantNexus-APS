"""Deterministic TASK-P6-02 duration machine-contract evidence checker."""

from __future__ import annotations

import argparse
import json
import math
import re
import tomllib
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

JsonObject = dict[str, Any]

REPORT_VERSION = "p6-duration-contract-report.v1"
TASK_ID = "TASK-P6-02"
DIFF_BASE = "e74099ca24ed59140f6490c84025b7299b5f201d"
SCHEMA_SET_VERSION = "2.9.0"
CURRENT_SCHEMA_SET_VERSION = "2.10.0"
HISTORICAL_ARTIFACT_COUNT = 70
HISTORICAL_MANIFEST_SHA256 = (
    "sha256:ada3e2a0498bb5b42ef81aba01693a949cd41deac229ebad8ea6f9334e901c64"
)
UV_LOCK_SHA256 = (
    "sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82"
)
DEPENDENCY_PROJECTION_SHA256 = (
    "sha256:2b9c344936b57d46b279067300c22c6cf74fc87281a624944a3ce492a6251d2e"
)
MIGRATION_MANIFEST_SHA256 = (
    "sha256:37a43d34e7db40456c314e428e985f86a62a051d1a36c0d2d5570aaa46bb3425"
)
FROZEN_MIGRATION_FILES = (
    "0001_engineering_job_metadata.py",
    "0002_raw_import_staging.py",
    "0003_planning_snapshots.py",
    "0004_schedule_versions_audit_export_jobs.py",
    "0005_replan_event_persistence.py",
)
OPEN_AUTHORITY_GAPS = {"OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015"}

SCHEMAS: Mapping[str, str] = {
    "feature": "duration-feature-record.schema.json",
    "model": "duration-model-manifest.schema.json",
    "evaluation": "duration-evaluation-report.schema.json",
    "prediction": "duration-prediction.schema.json",
}
SCHEMA_IDS: Mapping[str, str] = {
    "feature": "urn:plantnexus:aps:schema:duration-feature-record:v1",
    "model": "urn:plantnexus:aps:schema:duration-model-manifest:v1",
    "evaluation": "urn:plantnexus:aps:schema:duration-evaluation-report:v1",
    "prediction": "urn:plantnexus:aps:schema:duration-prediction:v1",
}
POSITIVE_SAMPLES: tuple[str, ...] = (
    "duration-feature-record.v1.synthetic.json",
    "duration-model-manifest.v1.synthetic.json",
    "duration-evaluation-report.v1.synthetic.json",
    "duration-prediction.v1.candidate.synthetic.json",
    "duration-prediction.v1.fallback.synthetic.json",
)
NEGATIVE_SAMPLES: tuple[str, ...] = (
    "duration-feature-record.v1.future-leakage.invalid.json",
    "duration-model-manifest.v1.incomplete-lineage.invalid.json",
    "duration-prediction.v1.invalid-quantiles.invalid.json",
    "duration-prediction.v1.mixed-version.invalid.json",
    "duration-prediction.v1.unknown-fallback.invalid.json",
)
NEW_ARTIFACT_PATHS = {
    *(f"schemas/json/{name}" for name in SCHEMAS.values()),
    *(f"schemas/samples/{name}" for name in POSITIVE_SAMPLES),
    *(f"schemas/samples/{name}" for name in NEGATIVE_SAMPLES),
}
POST_P6_ADDITIVE_ARTIFACT_PATHS = {
    "schemas/json/canonical-ingress-request.schema.json",
    "schemas/json/canonical-ingress-result.schema.json",
    "schemas/json/planning-run.schema.json",
    "schemas/samples/canonical-ingress-request.v1.synthetic.json",
    "schemas/samples/canonical-ingress-result.v1.accepted.synthetic.json",
    "schemas/samples/canonical-ingress-result.v1.rejected.synthetic.json",
    "schemas/samples/planning-run.v1.created.synthetic.json",
    "schemas/samples/planning-run.v1.completed.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-unknown-field.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-version.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-type.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-plane.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-scope.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-authority.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-reference.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-idempotency.synthetic.json",
    "schemas/samples/canonical-ingress.v1.invalid-fingerprint.synthetic.json",
    "schemas/samples/planning-run.v1.invalid-transition.synthetic.json",
}
FALLBACK_REASONS: tuple[str, ...] = (
    "NONE",
    "PREDICTION_MISSING",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_TIMEOUT",
    "INVALID_QUANTILES",
    "CONFIDENCE_MISSING",
    "CONFIDENCE_INVALID",
    "LOW_CONFIDENCE",
    "MODEL_NOT_APPROVED",
    "MODEL_OUT_OF_SCOPE",
    "MODEL_VERSION_INCOMPATIBLE",
    "FEATURE_VERSION_INCOMPATIBLE",
    "DATASET_VERSION_INCOMPATIBLE",
    "CONTRACT_VERSION_INCOMPATIBLE",
    "ARTIFACT_DIGEST_MISMATCH",
    "PROVENANCE_INCOMPLETE",
    "EVALUATION_GATE_NOT_PASSED",
    "DRIFT_GATE_DISABLED",
    "AUTHORITY_NOT_ESTABLISHED",
    "PRIVACY_GOVERNANCE_FAILED",
)
_IDENTITY_FIELDS: Mapping[str, tuple[str, str, str]] = {
    "feature": (
        "feature_record_id",
        "feature_record_fingerprint",
        "duration-feature-record-",
    ),
    "model": (
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    ),
    "evaluation": (
        "evaluation_report_id",
        "evaluation_report_fingerprint",
        "duration-evaluation-report-",
    ),
    "prediction": (
        "prediction_id",
        "prediction_fingerprint",
        "duration-prediction-",
    ),
}
_VERSION_FIELDS: Mapping[str, tuple[str, str]] = {
    "feature": ("duration_feature_record_version", "duration-feature-record.v1"),
    "model": ("duration_model_manifest_version", "duration-model-manifest.v1"),
    "evaluation": (
        "duration_evaluation_report_version",
        "duration-evaluation-report.v1",
    ),
    "prediction": ("duration_prediction_version", "duration-prediction.v1"),
}


class P6ContractError(ValueError):
    """Stable fail-closed P6 duration-contract error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _load_json(path: Path) -> JsonObject:
    loaded = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    if not isinstance(loaded, dict):
        raise P6ContractError("INVALID_JSON_ROOT", f"{path} must contain an object")
    return cast(JsonObject, loaded)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _kind(document: Mapping[str, Any]) -> str:
    for kind, (field, version) in _VERSION_FIELDS.items():
        if document.get(field) == version:
            return kind
    raise P6ContractError("UNKNOWN_DOCUMENT_VERSION", "P6 v1 version field is absent")


def contract_fingerprint(document: Mapping[str, Any]) -> str:
    """Return the canonical content fingerprint excluding self identity fields."""

    kind = _kind(document)
    identifier, fingerprint, _ = _IDENTITY_FIELDS[kind]
    projection = {k: deepcopy(v) for k, v in document.items() if k not in {identifier, fingerprint}}
    return f"sha256:{sha256(_canonical_bytes(projection)).hexdigest()}"


def recompute_identity(document: Mapping[str, Any]) -> JsonObject:
    """Return a copy with canonical fingerprint and content-derived ID refreshed."""

    result = deepcopy(dict(document))
    kind = _kind(result)
    identifier, fingerprint, prefix = _IDENTITY_FIELDS[kind]
    digest = contract_fingerprint(result)
    result[fingerprint] = digest
    result[identifier] = prefix + digest.removeprefix("sha256:")
    return result


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise P6ContractError("INVALID_UTC_INSTANT", field)
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    if parsed.utcoffset() is None:
        raise P6ContractError("INVALID_UTC_INSTANT", field)
    return parsed


def _walk_finite(value: object, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise P6ContractError("NON_FINITE_NUMBER", path)
    if isinstance(value, dict):
        for key, nested in value.items():
            _walk_finite(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_finite(nested, f"{path}[{index}]")


def _walk_strict_schema(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        if "default" in value:
            raise P6ContractError("SCHEMA_DEFAULT_FORBIDDEN", path)
        if value.get("type") == "object" and value.get("additionalProperties") is not False:
            raise P6ContractError("SCHEMA_NOT_STRICT", path)
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#/"):
            raise P6ContractError("NON_OFFLINE_REFERENCE", f"{path}: {reference}")
        for key, nested in value.items():
            _walk_strict_schema(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_strict_schema(nested, f"{path}[{index}]")


def _schema_for_document(root: Path, document: Mapping[str, Any]) -> JsonObject:
    return _load_json(root / "schemas" / "json" / SCHEMAS[_kind(document)])


def _schema_error_code(error: ValidationError) -> str:
    path = tuple(error.absolute_path)
    if error.validator == "required" and "dataset_manifest" in error.message:
        return "MISSING_DATASET_LINEAGE"
    if "schema_set_version" in path:
        return "INCOMPATIBLE_SCHEMA_SET"
    if "fallback_reason" in path:
        return "UNKNOWN_FALLBACK_REASON"
    return "SCHEMA_VALIDATION_FAILED"


def _validate_schema(document: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        raise P6ContractError(_schema_error_code(error), error.message)


def _common_semantics(document: Mapping[str, Any]) -> None:
    if document.get("schema_set_version") != SCHEMA_SET_VERSION:
        raise P6ContractError("INCOMPATIBLE_SCHEMA_SET", "exact 2.9.0 is required")
    if document.get("data_plane") != "SIMULATION":
        raise P6ContractError("PRODUCTION_BOUNDARY_VIOLATION", "data_plane")
    if document.get("synthetic") is not True or document.get("production_binding") is not False:
        raise P6ContractError("PRODUCTION_BOUNDARY_VIOLATION", "synthetic binding")
    governance = cast(Mapping[str, Any], document["governance_boundary"])
    if governance.get("production_authorized") is not False:
        raise P6ContractError("PRODUCTION_BOUNDARY_VIOLATION", "governance")
    if set(cast(Iterable[str], governance.get("open_authority_gaps", []))) != OPEN_AUTHORITY_GAPS:
        raise P6ContractError("AUTHORITY_GAPS_INCOMPLETE", "OPEN-010/011/014/015")


def _feature_semantics(document: Mapping[str, Any]) -> None:
    cutoff = _utc(document["as_of_cutoff_utc"], "as_of_cutoff_utc")
    source_records = cast(Sequence[Mapping[str, Any]], document["source_records"])
    source_ids = [cast(str, record["source_record_id"]) for record in source_records]
    if len(source_ids) != len(set(source_ids)):
        raise P6ContractError("DUPLICATE_SOURCE_RECORD", "source_record_id")
    for record in source_records:
        observed = _utc(record["observed_at_utc"], "source.observed_at_utc")
        available = _utc(record["available_at_utc"], "source.available_at_utc")
        if observed > available or available > cutoff:
            raise P6ContractError("AS_OF_LEAKAGE", cast(str, record["source_record_id"]))

    forbidden_tokens = (
        "actual_duration",
        "completed_at",
        "target_duration",
        "label",
        "future",
        "employee",
        "operator_name",
        "email",
        "phone",
    )
    feature_names: list[str] = []
    for feature in cast(Sequence[Mapping[str, Any]], document["features"]):
        name = cast(str, feature["feature_name"])
        feature_names.append(name)
        if any(token in name for token in forbidden_tokens):
            raise P6ContractError("FORBIDDEN_FEATURE", name)
        if _utc(feature["available_at_utc"], f"feature.{name}.available_at_utc") > cutoff:
            raise P6ContractError("AS_OF_LEAKAGE", name)
        refs = set(cast(Iterable[str], feature["source_record_ids"]))
        if not refs.issubset(set(source_ids)):
            raise P6ContractError("SOURCE_LINEAGE_MISMATCH", name)
        value = feature["value"]
        value_type = feature["value_type"]
        matches_type = {
            "INTEGER": type(value) is int,
            "NUMBER": type(value) is float,
            "BOOLEAN": type(value) is bool,
            "CATEGORY": type(value) is str,
        }[cast(str, value_type)]
        if not matches_type:
            raise P6ContractError("FEATURE_VALUE_TYPE_MISMATCH", name)
    if len(feature_names) != len(set(feature_names)):
        raise P6ContractError("DUPLICATE_FEATURE", "feature_name")


def _model_semantics(document: Mapping[str, Any]) -> None:
    if _utc(document["training_data_cutoff_utc"], "training_data_cutoff_utc") > _utc(
        document["created_at_utc"], "created_at_utc"
    ):
        raise P6ContractError("MODEL_TIME_LINEAGE_INVALID", "cutoff after creation")
    training = cast(Mapping[str, Any], document["training_provenance"])
    if training.get("dependency_lock_digest") != UV_LOCK_SHA256:
        raise P6ContractError("DEPENDENCY_LINEAGE_MISMATCH", "model manifest")
    forbidden_keys = {"state", "promotion_status", "deployment_status", "runtime_endpoint"}

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            overlap = forbidden_keys.intersection(value)
            if overlap:
                raise P6ContractError("MODEL_STATE_FORBIDDEN", sorted(overlap)[0])
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)

    inspect(document)


def _metric_semantics(metric: Mapping[str, Any]) -> None:
    name = cast(str, metric["metric_name"])
    expected = {
        "MAE_SECONDS": ("SECONDS", "LOWER_IS_BETTER"),
        "P50_ABSOLUTE_ERROR_SECONDS": ("SECONDS", "LOWER_IS_BETTER"),
        "P90_COVERAGE_RATIO": ("RATIO", "HIGHER_IS_BETTER"),
        "STANDARD_DURATION_MAE_SECONDS": ("SECONDS", "LOWER_IS_BETTER"),
    }[name]
    if (metric["unit"], metric["direction"]) != expected:
        raise P6ContractError("METRIC_SEMANTICS_INVALID", name)
    if metric["unit"] == "RATIO" and cast(float, metric["value"]) > 1:
        raise P6ContractError("METRIC_SEMANTICS_INVALID", f"{name} > 1")


def _evaluation_semantics(document: Mapping[str, Any]) -> None:
    if _utc(document["evaluation_data_cutoff_utc"], "evaluation_data_cutoff_utc") > _utc(
        document["evaluated_at_utc"], "evaluated_at_utc"
    ):
        raise P6ContractError("EVALUATION_TIME_LINEAGE_INVALID", "cutoff after evaluation")
    metrics = cast(Sequence[Mapping[str, Any]], document["metrics"])
    names = [cast(str, metric["metric_name"]) for metric in metrics]
    if len(names) != len(set(names)):
        raise P6ContractError("DUPLICATE_METRIC", "top-level metrics")
    for metric in metrics:
        _metric_semantics(metric)
    slice_keys: list[tuple[str, str]] = []
    for slice_record in cast(Sequence[Mapping[str, Any]], document["slices"]):
        key = (cast(str, slice_record["slice_key"]), cast(str, slice_record["slice_value"]))
        slice_keys.append(key)
        for metric in cast(Sequence[Mapping[str, Any]], slice_record["metrics"]):
            _metric_semantics(metric)
    if len(slice_keys) != len(set(slice_keys)):
        raise P6ContractError("DUPLICATE_EVALUATION_SLICE", "slice key/value")


def _prediction_semantics(document: Mapping[str, Any]) -> None:
    if _utc(document["as_of_cutoff_utc"], "as_of_cutoff_utc") > _utc(
        document["predicted_at_utc"], "predicted_at_utc"
    ):
        raise P6ContractError("PREDICTION_TIME_LINEAGE_INVALID", "cutoff after prediction")
    p50 = document["p50_seconds"]
    p90 = document["p90_seconds"]
    confidence = document["confidence"]
    present = (p50 is not None, p90 is not None, confidence is not None)
    if any(present) and not all(present):
        raise P6ContractError("INCOMPLETE_CANDIDATE", "quantile/confidence tuple")
    if p50 is not None and cast(int, p90) < cast(int, p50):
        raise P6ContractError("INVALID_QUANTILE_ORDER", "p90_seconds < p50_seconds")
    reason = document["fallback_reason"]
    if reason == "NONE":
        if not all(present):
            raise P6ContractError("PREDICTION_MISSING", "candidate selected")
        if document["selected_duration_source"] != "MODEL_CANDIDATE":
            raise P6ContractError("SELECTION_MISMATCH", "candidate source")
        if document["selected_duration_seconds"] != p50:
            raise P6ContractError("SELECTION_MISMATCH", "candidate must select p50")
    else:
        standard = cast(Mapping[str, Any], document["standard_duration"])
        if document["selected_duration_source"] != "STANDARD_DURATION":
            raise P6ContractError("FALLBACK_SELECTION_MISMATCH", cast(str, reason))
        if document["selected_duration_seconds"] != standard["seconds"]:
            raise P6ContractError("FALLBACK_SELECTION_MISMATCH", "standard seconds")
    if document["model_version"] != cast(Mapping[str, Any], document["model_reference"])[
        "model_version"
    ]:
        raise P6ContractError("LINEAGE_MISMATCH", "model_version")
    if document["feature_schema_version"] != cast(
        Mapping[str, Any], document["feature_record_reference"]
    )["feature_schema_version"]:
        raise P6ContractError("LINEAGE_MISMATCH", "feature_schema_version")


def validate_document(root: Path, document: Mapping[str, Any]) -> None:
    """Validate one P6 document through schema, semantics and canonical identity."""

    _walk_finite(document)
    _validate_schema(document, _schema_for_document(root, document))
    _common_semantics(document)
    kind = _kind(document)
    if kind == "feature":
        _feature_semantics(document)
    elif kind == "model":
        _model_semantics(document)
    elif kind == "evaluation":
        _evaluation_semantics(document)
    else:
        _prediction_semantics(document)
    identifier, fingerprint, prefix = _IDENTITY_FIELDS[kind]
    expected = contract_fingerprint(document)
    if document.get(fingerprint) != expected:
        raise P6ContractError("FINGERPRINT_MISMATCH", fingerprint)
    if document.get(identifier) != prefix + expected.removeprefix("sha256:"):
        raise P6ContractError("IDENTITY_MISMATCH", identifier)


def load_positive_samples(root: Path) -> dict[str, JsonObject]:
    return {
        name: _load_json(root / "schemas" / "samples" / name)
        for name in POSITIVE_SAMPLES
    }


def _reference_identity(document: Mapping[str, Any], kind: str) -> tuple[object, object]:
    identifier, fingerprint, _ = _IDENTITY_FIELDS[kind]
    return document[identifier], document[fingerprint]


def validate_p6_bundle(root: Path, documents: Mapping[str, Mapping[str, Any]]) -> None:
    """Validate all positive documents and their exact cross-document lineage."""

    for document in documents.values():
        validate_document(root, document)
    feature = documents[POSITIVE_SAMPLES[0]]
    model = documents[POSITIVE_SAMPLES[1]]
    evaluation = documents[POSITIVE_SAMPLES[2]]
    predictions = (documents[POSITIVE_SAMPLES[3]], documents[POSITIVE_SAMPLES[4]])

    model_id, model_fingerprint = _reference_identity(model, "model")
    evaluation_model = cast(Mapping[str, Any], evaluation["model_reference"])
    if (
        evaluation_model["model_manifest_id"],
        evaluation_model["model_manifest_fingerprint"],
        evaluation_model["model_version"],
        evaluation_model["model_artifact_digest"],
    ) != (
        model_id,
        model_fingerprint,
        model["model_version"],
        cast(Mapping[str, Any], model["model_artifact"])["artifact_digest"],
    ):
        raise P6ContractError("LINEAGE_MISMATCH", "evaluation -> model")
    if evaluation["dataset_manifest"] != model["dataset_manifest"]:
        raise P6ContractError("LINEAGE_MISMATCH", "evaluation -> dataset")
    if evaluation["feature_schema_version"] != model["feature_schema_version"]:
        raise P6ContractError("LINEAGE_MISMATCH", "evaluation -> feature schema")

    feature_id, feature_fingerprint = _reference_identity(feature, "feature")
    evaluation_id, evaluation_fingerprint = _reference_identity(evaluation, "evaluation")
    source_by_id = {
        record["source_record_id"]: record
        for record in cast(Sequence[Mapping[str, Any]], feature["source_records"])
    }
    standard_source = source_by_id.get("source-standard-duration-001")
    if standard_source is None:
        raise P6ContractError("LINEAGE_MISMATCH", "authoritative standard source absent")
    scope = cast(Mapping[str, Sequence[str]], model["scope"])
    if feature["factory_id"] not in scope["factory_ids"] or feature["resource_id"] not in scope[
        "resource_ids"
    ]:
        raise P6ContractError("LINEAGE_MISMATCH", "feature outside model scope")

    for prediction in predictions:
        feature_ref = cast(Mapping[str, Any], prediction["feature_record_reference"])
        model_ref = cast(Mapping[str, Any], prediction["model_reference"])
        evaluation_ref = cast(Mapping[str, Any], prediction["evaluation_reference"])
        standard = cast(Mapping[str, Any], prediction["standard_duration"])
        if (
            feature_ref["feature_record_id"],
            feature_ref["feature_record_fingerprint"],
        ) != (feature_id, feature_fingerprint):
            raise P6ContractError("LINEAGE_MISMATCH", "prediction -> feature")
        if (
            model_ref["model_manifest_id"],
            model_ref["model_manifest_fingerprint"],
            model_ref["model_version"],
            model_ref["model_artifact_digest"],
        ) != (
            model_id,
            model_fingerprint,
            model["model_version"],
            cast(Mapping[str, Any], model["model_artifact"])["artifact_digest"],
        ):
            raise P6ContractError("LINEAGE_MISMATCH", "prediction -> model")
        if (
            evaluation_ref["evaluation_report_id"],
            evaluation_ref["evaluation_report_fingerprint"],
        ) != (evaluation_id, evaluation_fingerprint):
            raise P6ContractError("LINEAGE_MISMATCH", "prediction -> evaluation")
        if standard["source_record_fingerprint"] != standard_source["record_fingerprint"]:
            raise P6ContractError("LINEAGE_MISMATCH", "prediction -> standard duration")
        for field in ("factory_id", "operation_id", "resource_option_id", "resource_id"):
            if prediction[field] != feature[field]:
                raise P6ContractError("LINEAGE_MISMATCH", f"prediction -> feature {field}")


def _historical_evidence(root: Path) -> JsonObject:
    paths = sorted(
        [
            *root.joinpath("schemas", "json").glob("*.json"),
            *root.joinpath("schemas", "samples").glob("*.json"),
        ],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    historical = [
        path
        for path in paths
        if path.relative_to(root).as_posix()
        not in NEW_ARTIFACT_PATHS | POST_P6_ADDITIVE_ARTIFACT_PATHS
    ]
    rows = "".join(
        f"{path.relative_to(root).as_posix()}={sha256(path.read_bytes()).hexdigest()}\n"
        for path in historical
    )
    digest = f"sha256:{sha256(rows.encode('utf-8')).hexdigest()}"
    if len(historical) != HISTORICAL_ARTIFACT_COUNT or digest != HISTORICAL_MANIFEST_SHA256:
        raise P6ContractError("HISTORICAL_BYTES_CHANGED", f"{len(historical)} / {digest}")
    return {"artifact_count": len(historical), "manifest_sha256": digest}


def _schema_evidence(root: Path) -> JsonObject:
    observed: dict[str, str] = {}
    for kind, filename in SCHEMAS.items():
        schema = _load_json(root / "schemas" / "json" / filename)
        Draft202012Validator.check_schema(schema)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise P6ContractError("SCHEMA_DRAFT_MISMATCH", filename)
        if schema.get("$id") != SCHEMA_IDS[kind]:
            raise P6ContractError("SCHEMA_ID_MISMATCH", filename)
        if cast(Mapping[str, Any], schema["properties"])["schema_set_version"] != {
            "const": SCHEMA_SET_VERSION
        }:
            raise P6ContractError("INCOMPATIBLE_SCHEMA_SET", filename)
        _walk_strict_schema(schema)
        observed[filename] = _sha256(root / "schemas" / "json" / filename)
    return {"schema_count": len(observed), "schema_sha256": observed}


def _positive_evidence(root: Path, documents: Mapping[str, Mapping[str, Any]]) -> JsonObject:
    for name, document in documents.items():
        validate_document(root, document)
        round_trip = json.loads(_canonical_bytes(document))
        if round_trip != document:
            raise P6ContractError("ROUND_TRIP_MISMATCH", name)
    return {"sample_count": len(documents), "round_trip": "EXACT"}


def _identity_evidence(documents: Mapping[str, Mapping[str, Any]]) -> JsonObject:
    fingerprints: dict[str, str] = {}
    for name, document in documents.items():
        expected = contract_fingerprint(document)
        _, field, _ = _IDENTITY_FIELDS[_kind(document)]
        if document[field] != expected:
            raise P6ContractError("FINGERPRINT_MISMATCH", name)
        fingerprints[name] = expected
    return {"canonicalization_version": "canonical-json.v1", "fingerprints": fingerprints}


def _pointer_parent(document: JsonObject, pointer: str) -> tuple[Any, str]:
    if not pointer.startswith("/"):
        raise P6ContractError("INVALID_NEGATIVE_VECTOR", pointer)
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]
    current: Any = document
    for token in tokens[:-1]:
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current, tokens[-1]


def apply_negative_vector(base: Mapping[str, Any], vector: Mapping[str, Any]) -> JsonObject:
    required_keys = {
        "negative_sample_version",
        "base_sample",
        "mutations",
        "recompute_identity",
        "expected_rejection",
        "synthetic",
        "assumption_profile",
    }
    if set(vector) != required_keys:
        raise P6ContractError("INVALID_NEGATIVE_VECTOR", "descriptor keys")
    if vector["negative_sample_version"] != "duration-contract-negative.v1":
        raise P6ContractError("INVALID_NEGATIVE_VECTOR", "descriptor version")
    if vector["synthetic"] is not True or vector["assumption_profile"] != (
        "SIM-P6-DURATION-CONTRACT-001@1.0.0"
    ):
        raise P6ContractError("INVALID_NEGATIVE_VECTOR", "provenance")
    result = deepcopy(dict(base))
    for mutation in cast(Sequence[Mapping[str, Any]], vector["mutations"]):
        op = mutation.get("op")
        expected_keys = {"op", "path"} if op == "remove" else {"op", "path", "value"}
        if set(mutation) != expected_keys or op not in {"remove", "replace"}:
            raise P6ContractError("INVALID_NEGATIVE_VECTOR", "mutation keys")
        parent, token = _pointer_parent(result, cast(str, mutation["path"]))
        if op == "remove":
            if isinstance(parent, list):
                parent.pop(int(token))
            else:
                del parent[token]
        elif isinstance(parent, list):
            parent[int(token)] = deepcopy(mutation["value"])
        else:
            parent[token] = deepcopy(mutation["value"])
    return recompute_identity(result) if vector["recompute_identity"] else result


def _negative_evidence(root: Path, documents: Mapping[str, Mapping[str, Any]]) -> JsonObject:
    observed: dict[str, str] = {}
    schema_rejections = 0
    semantic_rejections = 0
    for name in NEGATIVE_SAMPLES:
        vector = _load_json(root / "schemas" / "samples" / name)
        base_name = cast(str, vector["base_sample"])
        if base_name not in documents:
            raise P6ContractError("INVALID_NEGATIVE_VECTOR", f"unknown base {base_name}")
        mutated = apply_negative_vector(documents[base_name], vector)
        try:
            validate_document(root, mutated)
        except P6ContractError as error:
            expected = cast(str, vector["expected_rejection"])
            if error.code != expected:
                raise P6ContractError(
                    "NEGATIVE_REJECTION_MISMATCH", f"{name}: {error.code} != {expected}"
                ) from error
            observed[name] = error.code
            if error.code in {
                "MISSING_DATASET_LINEAGE",
                "INCOMPATIBLE_SCHEMA_SET",
                "UNKNOWN_FALLBACK_REASON",
            }:
                schema_rejections += 1
            else:
                semantic_rejections += 1
        else:
            raise P6ContractError("NEGATIVE_SAMPLE_ACCEPTED", name)
    return {
        "negative_sample_count": len(observed),
        "schema_rejections": schema_rejections,
        "semantic_rejections": semantic_rejections,
        "observed": observed,
    }


def _schema_mutation_evidence(
    root: Path, documents: Mapping[str, Mapping[str, Any]]
) -> JsonObject:
    rejected = 0
    for document in documents.values():
        schema = _schema_for_document(root, document)
        for field, value in (
            ("unexpected_field", True),
            ("data_plane", "PRODUCTION"),
            ("schema_set_version", "2.8.0"),
        ):
            mutation = deepcopy(dict(document))
            mutation[field] = value
            try:
                _validate_schema(mutation, schema)
            except P6ContractError:
                rejected += 1
            else:
                raise P6ContractError("SCHEMA_MUTATION_ACCEPTED", f"{_kind(document)}:{field}")
    prediction = documents[POSITIVE_SAMPLES[3]]
    prediction_schema = _schema_for_document(root, prediction)
    for field, value in (("unit", "MINUTES"), ("confidence", 1.1)):
        mutation = deepcopy(dict(prediction))
        mutation[field] = value
        try:
            _validate_schema(mutation, prediction_schema)
        except P6ContractError:
            rejected += 1
        else:
            raise P6ContractError("SCHEMA_MUTATION_ACCEPTED", field)
    return {"schema_rejections": rejected}


def _tamper_evidence(root: Path, documents: Mapping[str, Mapping[str, Any]]) -> JsonObject:
    rejected = 0
    for name, document in documents.items():
        mutation = deepcopy(dict(document))
        mutation["environment"] = "BENCHMARK"
        try:
            validate_document(root, mutation)
        except P6ContractError as error:
            if error.code != "FINGERPRINT_MISMATCH":
                raise P6ContractError("TAMPER_REJECTION_MISMATCH", f"{name}: {error.code}") from error
            rejected += 1
        else:
            raise P6ContractError("TAMPER_ACCEPTED", name)
    return {"tamper_rejections": rejected}


def _lineage_mutation_evidence(
    root: Path, documents: Mapping[str, Mapping[str, Any]]
) -> JsonObject:
    mutations: list[dict[str, JsonObject]] = []
    for label, mutator in (
        (
            "feature_fingerprint",
            lambda doc: cast(MutableMapping[str, Any], doc["feature_record_reference"]).__setitem__(
                "feature_record_fingerprint", "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
            ),
        ),
        (
            "model_version",
            lambda doc: (
                doc.__setitem__("model_version", "1.0.1"),
                cast(MutableMapping[str, Any], doc["model_reference"]).__setitem__(
                    "model_version", "1.0.1"
                ),
            ),
        ),
        (
            "evaluation_reference",
            lambda doc: cast(MutableMapping[str, Any], doc["evaluation_reference"]).__setitem__(
                "evaluation_report_id", "duration-evaluation-report-" + "d" * 64
            ),
        ),
        (
            "standard_duration_source",
            lambda doc: cast(MutableMapping[str, Any], doc["standard_duration"]).__setitem__(
                "source_record_fingerprint", "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
            ),
        ),
    ):
        bundle = deepcopy({name: dict(document) for name, document in documents.items()})
        candidate = bundle[POSITIVE_SAMPLES[3]]
        mutator(candidate)
        bundle[POSITIVE_SAMPLES[3]] = recompute_identity(candidate)
        mutations.append(bundle)

    dataset_bundle = deepcopy({name: dict(document) for name, document in documents.items()})
    evaluation = dataset_bundle[POSITIVE_SAMPLES[2]]
    cast(MutableMapping[str, Any], evaluation["dataset_manifest"])["fingerprint"] = (
        "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    )
    dataset_bundle[POSITIVE_SAMPLES[2]] = recompute_identity(evaluation)
    mutations.append(dataset_bundle)

    rejected = 0
    for bundle in mutations:
        try:
            validate_p6_bundle(root, bundle)
        except P6ContractError as error:
            if error.code != "LINEAGE_MISMATCH":
                raise P6ContractError("LINEAGE_REJECTION_MISMATCH", error.code) from error
            rejected += 1
        else:
            raise P6ContractError("LINEAGE_MUTATION_ACCEPTED", str(rejected))
    return {"lineage_rejections": rejected}


def _repository_boundary_evidence(root: Path) -> JsonObject:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    projection = {
        "runtime": project["project"]["dependencies"],
        "groups": project.get("dependency-groups", {}),
    }
    dependency_digest = f"sha256:{sha256(_canonical_bytes(projection)).hexdigest()}"
    if dependency_digest != DEPENDENCY_PROJECTION_SHA256:
        raise P6ContractError("DEPENDENCY_SET_CHANGED", dependency_digest)
    if (
        project["tool"]["plantnexus-aps"]["versions"]["schema"]
        != CURRENT_SCHEMA_SET_VERSION
    ):
        raise P6ContractError("INCOMPATIBLE_SCHEMA_SET", "pyproject.toml")
    if _sha256(root / "uv.lock") != UV_LOCK_SHA256:
        raise P6ContractError("DEPENDENCY_LOCK_CHANGED", "uv.lock")
    app_init = (root / "backend" / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^SCHEMA_VERSION = "([^"]+)"$', app_init, re.MULTILINE)
    if match is None or match.group(1) != CURRENT_SCHEMA_SET_VERSION:
        raise P6ContractError("INCOMPATIBLE_SCHEMA_SET", "app.SCHEMA_VERSION")
    dictionary = cast(
        Mapping[str, Any],
        yaml.safe_load((root / "schemas" / "data_dictionary.yaml").read_text(encoding="utf-8")),
    )
    if dictionary.get("schema_set_version") != CURRENT_SCHEMA_SET_VERSION:
        raise P6ContractError("INCOMPATIBLE_SCHEMA_SET", "data dictionary")
    expected_documents = {version for _, version in _VERSION_FIELDS.values()}
    if not expected_documents.issubset(set(cast(Mapping[str, Any], dictionary["schemas"]))):
        raise P6ContractError("DATA_DICTIONARY_INCOMPLETE", "P6 v1 documents")

    migration_root = root / "backend" / "migrations" / "versions"
    all_migrations = sorted(migration_root.glob("*.py"))
    frozen_names = set(FROZEN_MIGRATION_FILES)
    unexpected_predecessors = [
        path.name
        for path in all_migrations
        if path.name <= FROZEN_MIGRATION_FILES[-1] and path.name not in frozen_names
    ]
    migrations = [migration_root / name for name in FROZEN_MIGRATION_FILES]
    if unexpected_predecessors or any(not path.is_file() for path in migrations):
        raise P6ContractError(
            "MIGRATION_HISTORY_CHANGED",
            ",".join(unexpected_predecessors) or "frozen migration missing",
        )
    rows = "".join(
        f"{path.relative_to(root).as_posix()}={sha256(path.read_bytes()).hexdigest()}\n"
        for path in migrations
    )
    migration_digest = f"sha256:{sha256(rows.encode('utf-8')).hexdigest()}"
    if migration_digest != MIGRATION_MANIFEST_SHA256:
        raise P6ContractError("MIGRATION_HISTORY_CHANGED", migration_digest)
    if migrations[-1].stem != "0005_replan_event_persistence":
        raise P6ContractError("MIGRATION_HEAD_CHANGED", migrations[-1].stem)
    return {
        "schema_metadata": SCHEMA_SET_VERSION,
        "dependency_projection_sha256": dependency_digest,
        "uv_lock_sha256": UV_LOCK_SHA256,
        "migration_count": len(migrations),
        "migration_manifest_sha256": migration_digest,
        "migration_head": migrations[-1].stem,
        "runtime_dependency_change": "NONE",
        "development_dependency_change": "NONE",
        "migration_change": "NONE",
        "state_machine_change": "NONE",
    }


def run_contract_checks(root: Path) -> JsonObject:
    root = root.resolve()
    checks: list[JsonObject] = []

    def passed(name: str, evidence: object) -> None:
        checks.append({"name": name, "status": "PASS", "evidence": evidence})

    historical = _historical_evidence(root)
    passed("historical_schema_and_sample_bytes", historical)
    schema_evidence = _schema_evidence(root)
    passed("strict_offline_schema_definitions", schema_evidence)
    documents = load_positive_samples(root)
    positive = _positive_evidence(root, documents)
    passed("positive_schema_and_round_trip", positive)
    identity = _identity_evidence(documents)
    passed("canonical_identity_and_fingerprints", identity)
    validate_p6_bundle(root, documents)
    passed(
        "bundle_semantics_and_exact_lineage",
        {
            "documents": len(documents),
            "candidate_selection": "P50_ADVISORY_ONLY",
            "fallback_selection": "AUTHORITATIVE_STANDARD_DURATION",
        },
    )
    negative = _negative_evidence(root, documents)
    passed("published_negative_vectors", negative)
    schema_mutations = _schema_mutation_evidence(root, documents)
    passed("unknown_version_unit_confidence_mutations", schema_mutations)
    tamper = _tamper_evidence(root, documents)
    passed("canonical_tamper_rejection", tamper)
    lineage = _lineage_mutation_evidence(root, documents)
    passed("mixed_lineage_rejection", lineage)
    repository = _repository_boundary_evidence(root)
    passed("repository_dependency_migration_and_state_boundary", repository)

    schema_rejections = cast(int, negative["schema_rejections"]) + cast(
        int, schema_mutations["schema_rejections"]
    )
    semantic_rejections = cast(int, negative["semantic_rejections"]) + cast(
        int, lineage["lineage_rejections"]
    )
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "schema_set_version": SCHEMA_SET_VERSION,
        "status": "PASS",
        "result": "PASS",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "new_schemas": len(SCHEMAS),
            "positive_samples": len(POSITIVE_SAMPLES),
            "negative_samples": len(NEGATIVE_SAMPLES),
            "frozen_historical_artifacts": cast(int, historical["artifact_count"]),
            "schema_rejections": schema_rejections,
            "semantic_rejections": semantic_rejections,
            "tamper_rejections": cast(int, tamper["tamper_rejections"]),
        },
        "fallback_reasons": list(FALLBACK_REASONS),
        "artifacts": {
            "schemas": list(SCHEMAS.values()),
            "positive_samples": list(POSITIVE_SAMPLES),
            "negative_samples": list(NEGATIVE_SAMPLES),
            "fingerprints": identity["fingerprints"],
        },
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "production_binding": False,
            "planning_authority": "ADVISORY_DURATION_ONLY",
            "standard_duration_authority": "UNCHANGED",
            "routing_resource_hard_constraints_state_weights": "UNCHANGED",
            "dataset_training_runtime_planning_integration": "NOT_IMPLEMENTED",
            "production_authority_external_integration_capacity_sla": "NOT_FORMED",
            "open_authority_gaps": sorted(OPEN_AUTHORITY_GAPS),
            "repository": repository,
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-duration-contracts.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = run_contract_checks(args.root)
    except Exception as error:  # deterministic CI failure envelope
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "diff_base": DIFF_BASE,
            "schema_set_version": SCHEMA_SET_VERSION,
            "status": "FAIL",
            "result": "FAIL",
            "check_count": 0,
            "checks": [],
            "issues": [{"type": type(error).__name__, "message": str(error)}],
        }
        _write_report(args.report, report)
        return 1
    _write_report(args.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
