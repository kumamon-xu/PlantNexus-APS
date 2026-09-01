"""Deterministic P6 offline evaluation and standard-duration fallback gate.

The module consumes the immutable P6-03 dataset and P6-04 safe model.  It
semantically reads labels only from the validation and test partitions, emits
aggregate-only evidence, preserves the P6-02 measurement carrier, and keeps
runtime, planning, promotion, and Production authority out of scope.
"""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Never, Sequence, cast

from app.duration_prediction.model import (
    LoadedDurationModel,
    load_duration_model,
    predict_duration,
)

JsonObject = dict[str, Any]

EVALUATION_PROFILE_VERSION = "duration-evaluation-profile.v1"
OFFLINE_GATE_REPORT_VERSION = "p6-duration-offline-gate-report.v1"
MEASUREMENT_REPORT_VERSION = "duration-evaluation-report.v1"
PROFILE_ID = "SIM-P6-OFFLINE-EVALUATION-001@1.0.0"
TASK_ID = "TASK-P6-05"
SCHEMA_SET_VERSION = "2.9.0"
CANONICALIZATION_VERSION = "canonical-json.v1"
FEATURE_SCHEMA_VERSION = "duration-features.v1"
DATA_PLANE = "SIMULATION"
ENVIRONMENT = "TEST"
EVALUATED_AT_UTC = "2026-09-01T10:00:00Z"
MAX_JSON_BYTES = 1_048_576
OPEN_AUTHORITY_GAPS = ("OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015")
INCLUDED_PARTITIONS = ("validation", "test")
REQUIRED_FAMILIES = ("milling", "turning")
EXPECTED_PARTITION_COUNTS = {"train": 4, "validation": 2, "test": 2}
EXPECTED_ASSUMPTION_REFS = (
    "SIM-ASSUMPTION-021",
    "SIM-ASSUMPTION-022",
    "SIM-ASSUMPTION-023",
    "SIM-ASSUMPTION-024",
)
EXPECTED_FALLBACK_REASONS = (
    "FALLBACK_CONFIDENCE_MISSING",
    "FALLBACK_CONFIDENCE_INVALID",
    "FALLBACK_CONFIDENCE_BELOW_THRESHOLD",
    "FALLBACK_QUANTILES_INVALID",
    "FALLBACK_LINEAGE_INCOMPATIBLE",
    "FALLBACK_MODEL_INVALID",
    "FALLBACK_TIMEOUT",
    "FALLBACK_AUTHORITY_UNAVAILABLE",
    "FALLBACK_PRIVACY_BOUNDARY",
)
FORBIDDEN_EVIDENCE_KEYS = {
    "actual_processing_seconds",
    "dataset_row_id",
    "feature_record",
    "label",
    "records",
    "rows",
    "source_record_id",
}


class P6EvaluationError(ValueError):
    """Stable fail-closed evaluation or fallback error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> Never:
    raise P6EvaluationError(code, detail)


def _reject_constant(value: str) -> Never:
    _fail("NON_FINITE_JSON", value)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        _fail("INVALID_JSON_VALUE", type(error).__name__)


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _file_sha256(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _load_strict_json_bytes(raw: bytes, context: str) -> JsonObject:
    if len(raw) > MAX_JSON_BYTES:
        _fail("JSON_TOO_LARGE", context)
    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6EvaluationError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        _fail("JSON_PARSE_FAILED", f"{context}:{type(error).__name__}")
    return _expect_object(loaded, context)


def _read_strict_json(path: Path, context: str) -> tuple[JsonObject, str]:
    if path.is_symlink():
        _fail("UNSAFE_INPUT_PATH", f"{context}:symlink")
    try:
        if not path.is_file():
            _fail("INPUT_READ_FAILED", f"{context}:not-regular-file")
        raw = path.read_bytes()
    except P6EvaluationError:
        raise
    except OSError as error:
        _fail("INPUT_READ_FAILED", f"{context}:{type(error).__name__}")
    return _load_strict_json_bytes(raw, context), _file_sha256(raw)


def _expect_object(value: object, path: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail("INVALID_OBJECT", path)
    return cast(JsonObject, value)


def _expect_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        _fail("OBJECT_SHAPE_MISMATCH", f"{path}:missing={missing}:extra={extra}")


def _expect_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("INVALID_LIST", path)
    return value


def _expect_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("INVALID_STRING", path)
    return value


def _expect_int(value: object, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("INVALID_INTEGER", path)
    if minimum is not None and value < minimum:
        _fail("INVALID_INTEGER", path)
    return value


def _expect_bool(value: object, expected: bool, path: str) -> None:
    if value is not expected:
        _fail("BOOLEAN_BOUNDARY_MISMATCH", path)


def _expect_exact(value: object, expected: object, path: str) -> None:
    if value != expected:
        _fail("PROFILE_POLICY_MISMATCH", path)


def _fraction(value: Mapping[str, Any], path: str) -> Fraction:
    _expect_keys(value, {"numerator", "denominator"}, path)
    numerator = _expect_int(value["numerator"], f"{path}.numerator", minimum=0)
    denominator = _expect_int(value["denominator"], f"{path}.denominator", minimum=1)
    result = Fraction(numerator, denominator)
    if result.numerator != numerator or result.denominator != denominator:
        _fail("NON_CANONICAL_FRACTION", path)
    return result


def _fraction_object(value: Fraction) -> JsonObject:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_number(value: Fraction) -> int | float:
    if value.denominator == 1:
        return value.numerator
    return value.numerator / value.denominator


@dataclass(frozen=True)
class LoadedEvaluationProfile:
    document: JsonObject
    fingerprint: str
    confidence_threshold: Fraction


@dataclass(frozen=True)
class _Observation:
    partition: str
    operation_family: str
    operation_type_id: str
    standard_seconds: int
    actual_seconds: int
    feature_record: JsonObject
    label_available_at_utc: str


@dataclass(frozen=True)
class _Result:
    partition: str
    operation_family: str
    operation_type_id: str
    model_absolute_error: int
    standard_absolute_error: int
    covered_by_p90: bool
    confidence: Fraction
    model_selected: bool


@dataclass(frozen=True)
class DurationEvaluationBuild:
    measurement_report: JsonObject
    gate_report: JsonObject


def _validate_profile(document: Mapping[str, Any]) -> LoadedEvaluationProfile:
    profile = deepcopy(dict(document))
    _expect_keys(
        profile,
        {
            "assumption_refs",
            "confidence_policy",
            "created_at_utc",
            "data_plane",
            "duration_evaluation_profile_version",
            "environment",
            "evaluation_selection",
            "fallback_policy",
            "gate_policy",
            "governance_boundary",
            "input_contract",
            "metric_policy",
            "profile_id",
            "synthetic",
            "task_id",
        },
        "profile",
    )
    _expect_exact(profile["duration_evaluation_profile_version"], EVALUATION_PROFILE_VERSION, "profile.version")
    _expect_exact(profile["profile_id"], PROFILE_ID, "profile.id")
    _expect_exact(profile["task_id"], TASK_ID, "profile.task")
    _expect_exact(profile["created_at_utc"], EVALUATED_AT_UTC, "profile.timestamp")
    _expect_exact(profile["data_plane"], DATA_PLANE, "profile.plane")
    _expect_exact(profile["environment"], ENVIRONMENT, "profile.environment")
    _expect_bool(profile["synthetic"], True, "profile.synthetic")
    _expect_exact(tuple(_expect_list(profile["assumption_refs"], "profile.assumptions")), EXPECTED_ASSUMPTION_REFS, "profile.assumptions")

    selection = _expect_object(profile["evaluation_selection"], "profile.selection")
    _expect_exact(
        selection,
        {
            "excluded_label_partitions": ["train"],
            "included_partitions": ["validation", "test"],
            "minimum_heldout_rows": 4,
            "minimum_operation_family_rows": 2,
            "minimum_partition_rows": {"test": 2, "validation": 2},
            "required_operation_families": ["milling", "turning"],
            "train_label_read_limit": 0,
        },
        "profile.selection",
    )
    _expect_exact(
        profile["metric_policy"],
        {
            "absolute_error_unit": "SECONDS",
            "arithmetic": "EXACT_RATIONAL",
            "mae": "sum-absolute-error/count.v1",
            "median_absolute_error": "nearest-rank.v1@1/2",
            "p90_coverage": "actual-processing-seconds-less-than-or-equal-p90.v1",
        },
        "profile.metrics",
    )
    confidence = _expect_object(profile["confidence_policy"], "profile.confidence")
    _expect_keys(confidence, {"formula", "policy_version", "threshold"}, "profile.confidence")
    _expect_exact(confidence["formula"], "max(0,1-(p90_seconds-p50_seconds)/p50_seconds)", "profile.confidence.formula")
    _expect_exact(confidence["policy_version"], "interval-tightness-confidence.v1", "profile.confidence.version")
    threshold = _fraction(_expect_object(confidence["threshold"], "profile.confidence.threshold"), "profile.confidence.threshold")
    if threshold != Fraction(9, 10):
        _fail("PROFILE_POLICY_MISMATCH", "profile.confidence.threshold")

    _expect_exact(
        profile["gate_policy"],
        {
            "failure_decision": "NOT_READY",
            "gate_contract": "p6-duration-offline-confidence-fallback-gate.v1",
            "heldout_model_mae_vs_standard": "STRICTLY_LESS_THAN",
            "minimum_p90_coverage": {
                "operation_family": {"denominator": 2, "numerator": 1},
                "overall": {"denominator": 4, "numerator": 3},
                "partition": {"denominator": 2, "numerator": 1},
            },
            "slice_model_mae_vs_standard": "LESS_THAN_OR_EQUAL",
            "success_decision": "READY_FOR_SIMULATION_RUNTIME",
        },
        "profile.gate",
    )
    fallback = _expect_object(profile["fallback_policy"], "profile.fallback")
    _expect_keys(
        fallback,
        {
            "authority",
            "invalid_standard_duration_decision",
            "policy_version",
            "reason_codes",
            "selected_duration_source",
        },
        "profile.fallback",
    )
    _expect_exact(fallback["authority"], "STANDARD_DURATION_RESOURCE_OPTION", "profile.fallback.authority")
    _expect_exact(fallback["invalid_standard_duration_decision"], "FAIL_CLOSED", "profile.fallback.invalid_standard")
    _expect_exact(fallback["policy_version"], "standard-duration-offline-fallback-gate.v1", "profile.fallback.version")
    _expect_exact(fallback["selected_duration_source"], "feature.standard_duration_seconds", "profile.fallback.source")
    _expect_exact(tuple(_expect_list(fallback["reason_codes"], "profile.fallback.reasons")), EXPECTED_FALLBACK_REASONS, "profile.fallback.reasons")

    _expect_exact(
        profile["governance_boundary"],
        {
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
            "planning_authority": "NONE",
            "production_authorized": False,
            "promotion_authorized": False,
            "runtime_authorized": False,
        },
        "profile.governance",
    )
    contract = _expect_object(profile["input_contract"], "profile.inputs")
    _expect_keys(contract, {"canonicalization_version", "dataset", "feature_schema_version", "model", "schema_set_version"}, "profile.inputs")
    _expect_exact(contract["canonicalization_version"], CANONICALIZATION_VERSION, "profile.inputs.canonicalization")
    _expect_exact(contract["feature_schema_version"], FEATURE_SCHEMA_VERSION, "profile.inputs.features")
    _expect_exact(contract["schema_set_version"], SCHEMA_SET_VERSION, "profile.inputs.schemas")
    dataset = _expect_object(contract["dataset"], "profile.inputs.dataset")
    _expect_exact(
        dataset,
        {
            "bundle_fingerprint": "sha256:137ed52753f8decfcc2b0903c37e697f18c0e5a20369458aabddba6e7df81d98",
            "bundle_file_sha256": "sha256:9cc8d0a3e13258fac0a93cbf849edd50fe1ed270f331608274c8c6277639d144",
            "bundle_version": "duration-dataset-bundle.v1",
            "manifest_fingerprint": "sha256:d02f7818d4744e8a86205cfafe25efe1b39e2f1db6edc485a38e10aea8470bda",
            "manifest_id": "duration-dataset-manifest-d02f7818d4744e8a86205cfafe25efe1b39e2f1db6edc485a38e10aea8470bda",
        },
        "profile.inputs.dataset",
    )
    model = _expect_object(contract["model"], "profile.inputs.model")
    _expect_exact(
        model,
        {
            "artifact_digest": "sha256:472cc92ada06b488fceb8477ac5a3dfe06d6391dd5ada8b441d55b96e9640ddd",
            "artifact_file_sha256": "sha256:70006f2df41a350cc83baea216d3ccc3fbb16034b949b65cd61c808960d67728",
            "bundle_file_sha256": "sha256:f7d07ff8b3373d1beb2efe983ada88d6ca8a026a94099198fec4e528a4b60c47",
            "bundle_fingerprint": "sha256:4536d9700acdbe923a69c20692a19d6f4d8a6a53463e828ea582925676820c8e",
            "configuration_fingerprint": "sha256:8e7a6ec503298eec720b45520ebdce45fd114e55e8e96fdce4668895f4d2da45",
            "configuration_id": "duration-training-config-8e7a6ec503298eec720b45520ebdce45fd114e55e8e96fdce4668895f4d2da45",
            "manifest_fingerprint": "sha256:35f84b792028a1bf135fcc44d415423d47593f2843058d119fe288efd7195bf0",
            "manifest_id": "duration-model-manifest-35f84b792028a1bf135fcc44d415423d47593f2843058d119fe288efd7195bf0",
            "model_version": "1.0.0",
        },
        "profile.inputs.model",
    )
    return LoadedEvaluationProfile(profile, _fingerprint(profile), threshold)


def load_evaluation_profile(path: Path) -> LoadedEvaluationProfile:
    """Load the frozen strict P6-05 profile without environment defaults."""

    document, _ = _read_strict_json(path, "evaluation-profile")
    return _validate_profile(document)


def _feature_value(feature_record: Mapping[str, Any], name: str) -> object:
    features = _expect_list(feature_record.get("features"), "feature_record.features")
    matches: list[object] = []
    for raw in features:
        item = _expect_object(raw, "feature_record.feature")
        if item.get("feature_name") == name:
            matches.append(item.get("value"))
    if len(matches) != 1:
        _fail("FEATURE_CONTRACT_MISMATCH", name)
    return matches[0]


def _verify_dataset(
    bundle: Mapping[str, Any], profile: LoadedEvaluationProfile
) -> tuple[list[_Observation], JsonObject]:
    candidate = _expect_object(bundle, "dataset")
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
        "dataset",
    )
    contract = cast(JsonObject, profile.document["input_contract"])
    dataset_contract = cast(JsonObject, contract["dataset"])
    if (
        candidate["duration_dataset_bundle_version"] != dataset_contract["bundle_version"]
        or candidate["schema_set_version"] != SCHEMA_SET_VERSION
        or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
        or candidate["bundle_fingerprint"] != dataset_contract["bundle_fingerprint"]
    ):
        _fail("DATASET_LINEAGE_MISMATCH", "bundle")
    manifest = _expect_object(candidate["dataset_manifest"], "dataset.manifest")
    if (
        manifest.get("artifact_id") != dataset_contract["manifest_id"]
        or manifest.get("fingerprint") != dataset_contract["manifest_fingerprint"]
        or manifest.get("document_version") != "duration-dataset-manifest.v1"
        or manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
        or manifest.get("data_plane") != DATA_PLANE
        or manifest.get("environment") != ENVIRONMENT
    ):
        _fail("DATASET_LINEAGE_MISMATCH", "manifest")
    _expect_bool(manifest.get("synthetic"), True, "dataset.manifest.synthetic")
    _expect_bool(manifest.get("production_binding"), False, "dataset.manifest.production")
    governance = _expect_object(manifest.get("governance_boundary"), "dataset.manifest.governance")
    _expect_bool(governance.get("production_authorized"), False, "dataset.manifest.authority")
    if tuple(governance.get("open_authority_gaps", [])) != OPEN_AUTHORITY_GAPS:
        _fail("DATASET_AUTHORITY_MISMATCH", "open gaps")

    rows = _expect_list(candidate["rows"], "dataset.rows")
    partition_counts = {name: 0 for name in EXPECTED_PARTITION_COUNTS}
    family_counts = {name: 0 for name in REQUIRED_FAMILIES}
    group_partitions: dict[str, set[str]] = {}
    seen_row_ids: set[str] = set()
    observations: list[_Observation] = []
    train_label_reads = 0
    for index, raw in enumerate(rows):
        row = _expect_object(raw, f"dataset.rows[{index}]")
        partition = _expect_string(row.get("partition"), f"dataset.rows[{index}].partition")
        if partition not in partition_counts:
            _fail("DATASET_PARTITION_MISMATCH", partition)
        partition_counts[partition] += 1
        group = _expect_string(row.get("lineage_group_id"), f"dataset.rows[{index}].group")
        group_partitions.setdefault(group, set()).add(partition)
        row_id = _expect_string(row.get("dataset_row_id"), f"dataset.rows[{index}].id")
        if row_id in seen_row_ids:
            _fail("DUPLICATE_DATASET_ROW", row_id)
        seen_row_ids.add(row_id)
        if partition == "train":
            continue
        if partition not in INCLUDED_PARTITIONS:
            _fail("DATASET_PARTITION_MISMATCH", partition)
        _expect_keys(
            row,
            {
                "dataset_row_version",
                "partition",
                "lineage_group_id",
                "operation_type_id",
                "label",
                "feature_record",
                "dataset_row_id",
                "dataset_row_fingerprint",
            },
            f"dataset.rows[{index}]",
        )
        identity_projection = {
            key: deepcopy(value)
            for key, value in row.items()
            if key not in {"dataset_row_id", "dataset_row_fingerprint"}
        }
        row_fingerprint = _fingerprint(identity_projection)
        if (
            row.get("dataset_row_fingerprint") != row_fingerprint
            or row_id != "duration-dataset-row-" + row_fingerprint.removeprefix("sha256:")
        ):
            _fail("DATASET_ROW_TAMPERED", row_id)
        label = _expect_object(row["label"], f"dataset.rows[{index}].label")
        _expect_keys(
            label,
            {
                "label_name",
                "value",
                "unit",
                "source_record_id",
                "source_record_fingerprint",
                "observed_at_utc",
                "available_at_utc",
                "policy_version",
            },
            f"dataset.rows[{index}].label",
        )
        if (
            label["label_name"] != "actual_processing_seconds"
            or label["unit"] != "SECONDS"
            or label["policy_version"] != "explicit-normal-completion-label.v1"
        ):
            _fail("LABEL_CONTRACT_MISMATCH", row_id)
        actual = _expect_int(label["value"], f"dataset.rows[{index}].label.value", minimum=1)
        feature = _expect_object(row["feature_record"], f"dataset.rows[{index}].feature")
        _expect_bool(feature.get("pii_fields_present"), False, "feature.pii")
        _expect_bool(feature.get("target_fields_present"), False, "feature.target")
        _expect_bool(feature.get("production_binding"), False, "feature.production")
        standard = _expect_int(_feature_value(feature, "standard_duration_seconds"), "feature.standard_duration_seconds", minimum=1)
        family = _expect_string(_feature_value(feature, "operation_family"), "feature.operation_family")
        if family not in family_counts:
            _fail("EVALUATION_SLICE_MISMATCH", family)
        family_counts[family] += 1
        observations.append(
            _Observation(
                partition=partition,
                operation_family=family,
                operation_type_id=_expect_string(row["operation_type_id"], "row.operation_type_id"),
                standard_seconds=standard,
                actual_seconds=actual,
                feature_record=deepcopy(feature),
                label_available_at_utc=_expect_string(label["available_at_utc"], "label.available_at_utc"),
            )
        )
    if partition_counts != EXPECTED_PARTITION_COUNTS:
        _fail("DATASET_PARTITION_MISMATCH", str(partition_counts))
    if any(len(names) != 1 for names in group_partitions.values()):
        _fail("LINEAGE_GROUP_SPLIT_CROSSING", "dataset")
    if len(observations) != 4 or family_counts != {"milling": 2, "turning": 2}:
        _fail("EVALUATION_SAMPLE_TOO_SPARSE", str(family_counts))
    observations.sort(
        key=lambda item: (
            INCLUDED_PARTITIONS.index(item.partition),
            item.operation_family,
            item.operation_type_id,
            _fingerprint(item.feature_record),
        )
    )
    selection: JsonObject = {
        "included_partitions": list(INCLUDED_PARTITIONS),
        "partition_counts": {name: partition_counts[name] for name in INCLUDED_PARTITIONS},
        "heldout_row_count": len(observations),
        "operation_family_counts": family_counts,
        "train_label_reads": train_label_reads,
        "train_label_read_limit": 0,
    }
    return observations, selection


def _verify_model_bundle(
    bundle: Mapping[str, Any],
    loaded: LoadedDurationModel,
    profile: LoadedEvaluationProfile,
) -> JsonObject:
    candidate = _expect_object(bundle, "model-bundle")
    _expect_keys(
        candidate,
        {
            "duration_model_bundle_version",
            "schema_set_version",
            "canonicalization_version",
            "training_configuration",
            "use_authorization_decision",
            "rollback_authority",
            "model_manifest",
            "replay",
            "bundle_fingerprint",
        },
        "model-bundle",
    )
    model_contract = cast(JsonObject, cast(JsonObject, profile.document["input_contract"])["model"])
    if (
        candidate["duration_model_bundle_version"] != "duration-model-bundle.v1"
        or candidate["schema_set_version"] != SCHEMA_SET_VERSION
        or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
        or candidate["bundle_fingerprint"] != model_contract["bundle_fingerprint"]
    ):
        _fail("MODEL_LINEAGE_MISMATCH", "bundle")
    configuration = _expect_object(candidate["training_configuration"], "model.configuration")
    if (
        configuration.get("configuration_id") != model_contract["configuration_id"]
        or configuration.get("configuration_fingerprint")
        != model_contract["configuration_fingerprint"]
    ):
        _fail("MODEL_LINEAGE_MISMATCH", "configuration")
    manifest = _expect_object(candidate["model_manifest"], "model.manifest")
    artifact = _expect_object(manifest.get("model_artifact"), "model.manifest.artifact")
    if (
        manifest.get("model_manifest_id") != model_contract["manifest_id"]
        or manifest.get("model_manifest_fingerprint") != model_contract["manifest_fingerprint"]
        or manifest.get("model_version") != model_contract["model_version"]
        or artifact.get("artifact_digest") != model_contract["artifact_digest"]
        or loaded.model_version != model_contract["model_version"]
        or loaded.artifact_digest != model_contract["artifact_digest"]
    ):
        _fail("MODEL_LINEAGE_MISMATCH", "manifest")
    authorization = _expect_object(candidate["use_authorization_decision"], "model.authorization")
    if authorization.get("decision") != "SIMULATION_EVALUATION_ONLY":
        _fail("MODEL_AUTHORITY_MISMATCH", "decision")
    _expect_bool(authorization.get("production_authorized"), False, "model.authorization.production")
    return manifest


def interval_tightness_confidence(p50_seconds: int, p90_seconds: int) -> Fraction:
    """Return the frozen exact confidence score without floating point."""

    p50 = _expect_int(p50_seconds, "p50_seconds", minimum=1)
    p90 = _expect_int(p90_seconds, "p90_seconds", minimum=1)
    if p90 < p50:
        _fail("INVALID_QUANTILES", "p90<p50")
    return max(Fraction(0), Fraction(p50 - (p90 - p50), p50))


def select_duration_with_fallback(
    *,
    standard_duration_seconds: object,
    p50_seconds: object | None,
    p90_seconds: object | None,
    confidence: object | None,
    confidence_threshold: Fraction = Fraction(9, 10),
    lineage_compatible: bool = True,
    model_valid: bool = True,
    timed_out: bool = False,
    model_authorized: bool = True,
    privacy_safe: bool = True,
) -> JsonObject:
    """Apply the frozen fail-closed fallback precedence with no side effect."""

    standard = _expect_int(standard_duration_seconds, "standard_duration_seconds", minimum=1)
    if confidence_threshold != Fraction(9, 10):
        _fail("CONFIDENCE_THRESHOLD_MISMATCH", str(confidence_threshold))

    reason: str | None = None
    if not privacy_safe:
        reason = "FALLBACK_PRIVACY_BOUNDARY"
    elif not model_authorized:
        reason = "FALLBACK_AUTHORITY_UNAVAILABLE"
    elif timed_out:
        reason = "FALLBACK_TIMEOUT"
    elif not lineage_compatible:
        reason = "FALLBACK_LINEAGE_INCOMPATIBLE"
    elif not model_valid:
        reason = "FALLBACK_MODEL_INVALID"
    elif (
        isinstance(p50_seconds, bool)
        or not isinstance(p50_seconds, int)
        or isinstance(p90_seconds, bool)
        or not isinstance(p90_seconds, int)
        or p50_seconds <= 0
        or p90_seconds < p50_seconds
    ):
        reason = "FALLBACK_QUANTILES_INVALID"
    elif confidence is None:
        reason = "FALLBACK_CONFIDENCE_MISSING"
    elif isinstance(confidence, bool) or not isinstance(confidence, (int, Fraction)):
        reason = "FALLBACK_CONFIDENCE_INVALID"
    else:
        exact_confidence = Fraction(confidence)
        if exact_confidence < 0 or exact_confidence > 1:
            reason = "FALLBACK_CONFIDENCE_INVALID"
        elif exact_confidence < confidence_threshold:
            reason = "FALLBACK_CONFIDENCE_BELOW_THRESHOLD"

    if reason is not None:
        return {
            "fallback_used": True,
            "fallback_reason": reason,
            "selected_duration_seconds": standard,
            "selected_source": "STANDARD_DURATION",
        }
    assert isinstance(p50_seconds, int)
    return {
        "fallback_used": False,
        "fallback_reason": None,
        "selected_duration_seconds": p50_seconds,
        "selected_source": "MODEL_P50",
    }


def _aggregate(results: Sequence[_Result]) -> JsonObject:
    if not results:
        _fail("EMPTY_EVALUATION_SLICE", "aggregate")
    count = len(results)
    model_errors = sorted(item.model_absolute_error for item in results)
    standard_errors = [item.standard_absolute_error for item in results]
    model_mae = Fraction(sum(model_errors), count)
    standard_mae = Fraction(sum(standard_errors), count)
    median = model_errors[(count - 1) // 2]
    covered = sum(item.covered_by_p90 for item in results)
    confidences = [item.confidence for item in results]
    return {
        "sample_count": count,
        "model_mae_seconds": _fraction_object(model_mae),
        "model_median_absolute_error_seconds": {"denominator": 1, "numerator": median},
        "standard_duration_mae_seconds": _fraction_object(standard_mae),
        "p90_coverage": {
            "covered_count": covered,
            "ratio": _fraction_object(Fraction(covered, count)),
            "total_count": count,
        },
        "confidence": {
            "at_or_above_threshold_count": sum(
                item.confidence >= Fraction(9, 10) for item in results
            ),
            "minimum": _fraction_object(min(confidences)),
            "policy_version": "interval-tightness-confidence.v1",
            "threshold": {"denominator": 10, "numerator": 9},
        },
        "selection": {
            "model_p50_count": sum(item.model_selected for item in results),
            "standard_duration_fallback_count": sum(
                not item.model_selected for item in results
            ),
        },
    }


def _metric_array(aggregate: Mapping[str, Any]) -> list[JsonObject]:
    count = cast(int, aggregate["sample_count"])
    model_mae = _fraction(_expect_object(aggregate["model_mae_seconds"], "aggregate.model_mae"), "aggregate.model_mae")
    median = _fraction(_expect_object(aggregate["model_median_absolute_error_seconds"], "aggregate.median"), "aggregate.median")
    standard_mae = _fraction(_expect_object(aggregate["standard_duration_mae_seconds"], "aggregate.standard_mae"), "aggregate.standard_mae")
    coverage = _fraction(_expect_object(cast(JsonObject, aggregate["p90_coverage"])["ratio"], "aggregate.coverage"), "aggregate.coverage")
    return [
        {"metric_name": "MAE_SECONDS", "value": _fraction_number(model_mae), "unit": "SECONDS", "direction": "LOWER_IS_BETTER", "sample_count": count},
        {"metric_name": "P50_ABSOLUTE_ERROR_SECONDS", "value": _fraction_number(median), "unit": "SECONDS", "direction": "LOWER_IS_BETTER", "sample_count": count},
        {"metric_name": "P90_COVERAGE_RATIO", "value": _fraction_number(coverage), "unit": "RATIO", "direction": "HIGHER_IS_BETTER", "sample_count": count},
        {"metric_name": "STANDARD_DURATION_MAE_SECONDS", "value": _fraction_number(standard_mae), "unit": "SECONDS", "direction": "LOWER_IS_BETTER", "sample_count": count},
    ]


def _artifact_reference(document_version: str, prefix: str, projection: object) -> JsonObject:
    fingerprint = _fingerprint(projection)
    return {
        "document_version": document_version,
        "artifact_id": prefix + fingerprint.removeprefix("sha256:"),
        "fingerprint": fingerprint,
    }


def _source_code_identity() -> tuple[str, str]:
    source = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    digest = sha256(source).hexdigest()
    return digest[:40], f"sha256:{digest}"


def _with_identity(
    projection: Mapping[str, Any],
    *,
    id_field: str,
    fingerprint_field: str,
    prefix: str,
) -> JsonObject:
    result = deepcopy(dict(projection))
    fingerprint = _fingerprint(result)
    result[id_field] = prefix + fingerprint.removeprefix("sha256:")
    result[fingerprint_field] = fingerprint
    return result


def _build_measurement_report(
    *,
    profile: LoadedEvaluationProfile,
    model_manifest: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
    overall: Mapping[str, Any],
    operation_type_slices: Sequence[tuple[str, Mapping[str, Any]]],
    evaluation_data_cutoff_utc: str,
) -> JsonObject:
    split_projection = {
        "dataset_manifest_id": dataset_manifest["artifact_id"],
        "included_partitions": list(INCLUDED_PARTITIONS),
        "split_policy": deepcopy(dataset_manifest["split_policy"]),
    }
    standard_projection = {
        "authority": "STANDARD_DURATION_RESOURCE_OPTION",
        "dataset_manifest_id": dataset_manifest["artifact_id"],
        "feature_name": "standard_duration_seconds",
        "unit": "SECONDS",
    }
    privacy_projection = {
        "dataset_manifest_id": dataset_manifest["artifact_id"],
        "pii_fields_present": False,
        "production_binding": False,
        "profile_fingerprint": profile.fingerprint,
        "target_fields_present": False,
    }
    configuration = _artifact_reference(
        "duration-evaluation-config.v1",
        "duration-evaluation-config-",
        {"profile_id": PROFILE_ID, "profile_fingerprint": profile.fingerprint},
    )
    code_revision, _ = _source_code_identity()
    model_artifact = _expect_object(model_manifest["model_artifact"], "model.manifest.artifact")
    projection: JsonObject = {
        "duration_evaluation_report_version": MEASUREMENT_REPORT_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "model_reference": {
            "duration_model_manifest_version": model_manifest["duration_model_manifest_version"],
            "model_manifest_id": model_manifest["model_manifest_id"],
            "model_manifest_fingerprint": model_manifest["model_manifest_fingerprint"],
            "model_version": model_manifest["model_version"],
            "model_artifact_digest": model_artifact["artifact_digest"],
        },
        "dataset_manifest": {
            "document_version": dataset_manifest["document_version"],
            "artifact_id": dataset_manifest["artifact_id"],
            "fingerprint": dataset_manifest["fingerprint"],
        },
        "split_manifest": _artifact_reference(
            "duration-split-manifest.v1", "duration-split-manifest-", split_projection
        ),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "standard_duration_baseline": _artifact_reference(
            "standard-duration-authority.v1",
            "standard-duration-authority-",
            standard_projection,
        ),
        "evaluation_code": {
            "code_revision": code_revision,
            "dependency_lock_digest": "sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
            "configuration": configuration,
        },
        "evaluated_at_utc": EVALUATED_AT_UTC,
        "evaluation_data_cutoff_utc": evaluation_data_cutoff_utc,
        "metrics": _metric_array(overall),
        "slices": [
            {
                "slice_key": "OPERATION_TYPE_ID",
                "slice_value": name,
                "sample_count": aggregate["sample_count"],
                "metrics": _metric_array(aggregate),
            }
            for name, aggregate in operation_type_slices
        ],
        "gate_assessment": {
            "gate_contract": "duration-evaluation-gate.planned-p6-05",
            "decision": "NOT_EVALUATED_BY_P6_02",
            "thresholds_embedded": False,
        },
        "privacy_review_reference": _artifact_reference(
            "duration-privacy-review.v1",
            "duration-privacy-review-",
            privacy_projection,
        ),
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "synthetic": True,
        "synthetic_provenance": {
            "assumption_profile": "SIM-P6-DURATION-CONTRACT-001@1.0.0",
            "assumption_refs": list(EXPECTED_ASSUMPTION_REFS),
        },
        "production_binding": False,
        "governance_boundary": {
            "production_authorized": False,
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        },
    }
    return _with_identity(
        projection,
        id_field="evaluation_report_id",
        fingerprint_field="evaluation_report_fingerprint",
        prefix="duration-evaluation-report-",
    )


def _fallback_matrix(threshold: Fraction) -> JsonObject:
    healthy_confidence = Fraction(19, 20)
    scenarios: list[JsonObject] = []

    def observe(name: str, **overrides: object) -> None:
        arguments: dict[str, Any] = {
            "standard_duration_seconds": 600,
            "p50_seconds": 540,
            "p90_seconds": 570,
            "confidence": healthy_confidence,
            "confidence_threshold": threshold,
            "lineage_compatible": True,
            "model_valid": True,
            "timed_out": False,
            "model_authorized": True,
            "privacy_safe": True,
        }
        arguments.update(overrides)
        scenarios.append({"scenario": name, "decision": select_duration_with_fallback(**arguments)})

    observe("HEALTHY_MODEL")
    observe("CONFIDENCE_MISSING", confidence=None)
    observe("CONFIDENCE_INVALID", confidence=Fraction(11, 10))
    observe("CONFIDENCE_BELOW_THRESHOLD", confidence=Fraction(89, 100))
    observe("QUANTILES_INVALID", p50_seconds=580, p90_seconds=570)
    observe("LINEAGE_INCOMPATIBLE", lineage_compatible=False)
    observe("MODEL_INVALID", model_valid=False)
    observe("TIMEOUT", timed_out=True)
    observe("AUTHORITY_UNAVAILABLE", model_authorized=False)
    observe("PRIVACY_BOUNDARY", privacy_safe=False)
    invalid_standard_error: str | None = None
    try:
        select_duration_with_fallback(
            standard_duration_seconds=0,
            p50_seconds=540,
            p90_seconds=570,
            confidence=healthy_confidence,
            confidence_threshold=threshold,
        )
    except P6EvaluationError as error:
        invalid_standard_error = error.code
    if invalid_standard_error != "INVALID_INTEGER":
        _fail("FALLBACK_MATRIX_MISMATCH", "invalid standard duration")
    return {
        "policy_version": "standard-duration-offline-fallback-gate.v1",
        "scenario_count": len(scenarios) + 1,
        "scenarios": scenarios,
        "invalid_standard_duration": {
            "decision": "FAIL_CLOSED",
            "error_code": "INVALID_INTEGER",
        },
    }


def _gate_check(
    check_id: str, passed: bool, criterion: object, observed: object
) -> JsonObject:
    return {
        "check_id": check_id,
        "criterion": criterion,
        "observed": observed,
        "result": "PASS" if passed else "FAIL",
    }


def build_duration_evaluation(
    dataset_bundle: Mapping[str, Any],
    model_bundle: Mapping[str, Any],
    loaded_model: LoadedDurationModel,
    profile: LoadedEvaluationProfile,
) -> DurationEvaluationBuild:
    """Evaluate held-out labels and return deterministic aggregate-only reports."""

    observations, selection = _verify_dataset(dataset_bundle, profile)
    model_manifest = _verify_model_bundle(model_bundle, loaded_model, profile)
    results: list[_Result] = []
    for observation in observations:
        estimate = predict_duration(loaded_model, observation.feature_record)
        p50 = _expect_int(estimate.get("p50_seconds"), "estimate.p50", minimum=1)
        p90 = _expect_int(estimate.get("p90_seconds"), "estimate.p90", minimum=1)
        confidence = interval_tightness_confidence(p50, p90)
        decision = select_duration_with_fallback(
            standard_duration_seconds=observation.standard_seconds,
            p50_seconds=p50,
            p90_seconds=p90,
            confidence=confidence,
            confidence_threshold=profile.confidence_threshold,
        )
        results.append(
            _Result(
                partition=observation.partition,
                operation_family=observation.operation_family,
                operation_type_id=observation.operation_type_id,
                model_absolute_error=abs(observation.actual_seconds - p50),
                standard_absolute_error=abs(
                    observation.actual_seconds - observation.standard_seconds
                ),
                covered_by_p90=observation.actual_seconds <= p90,
                confidence=confidence,
                model_selected=decision["selected_source"] == "MODEL_P50",
            )
        )
    overall = _aggregate(results)
    partitions = [
        (name, _aggregate([item for item in results if item.partition == name]))
        for name in INCLUDED_PARTITIONS
    ]
    families = [
        (name, _aggregate([item for item in results if item.operation_family == name]))
        for name in REQUIRED_FAMILIES
    ]
    operation_types = sorted({item.operation_type_id for item in results})
    operation_type_slices = [
        (
            name,
            _aggregate([item for item in results if item.operation_type_id == name]),
        )
        for name in operation_types
    ]
    dataset_manifest = _expect_object(
        _expect_object(dataset_bundle, "dataset")["dataset_manifest"],
        "dataset.manifest",
    )
    measurement = _build_measurement_report(
        profile=profile,
        model_manifest=model_manifest,
        dataset_manifest=dataset_manifest,
        overall=overall,
        operation_type_slices=operation_type_slices,
        evaluation_data_cutoff_utc=max(
            observation.label_available_at_utc for observation in observations
        ),
    )

    def mae(aggregate: Mapping[str, Any], key: str) -> Fraction:
        return _fraction(_expect_object(aggregate[key], key), key)

    def coverage(aggregate: Mapping[str, Any]) -> Fraction:
        coverage_object = _expect_object(aggregate["p90_coverage"], "coverage")
        return _fraction(_expect_object(coverage_object["ratio"], "coverage.ratio"), "coverage.ratio")

    checks: list[JsonObject] = [
        _gate_check("heldout-row-count", selection["heldout_row_count"] >= 4, {"minimum": 4}, {"count": selection["heldout_row_count"]}),
        _gate_check("train-label-read-zero", selection["train_label_reads"] == 0, {"maximum": 0}, {"count": selection["train_label_reads"]}),
        _gate_check("heldout-model-mae-strictly-better", mae(overall, "model_mae_seconds") < mae(overall, "standard_duration_mae_seconds"), "MODEL_MAE<STANDARD_MAE", {"model": overall["model_mae_seconds"], "standard": overall["standard_duration_mae_seconds"]}),
        _gate_check("overall-p90-coverage", coverage(overall) >= Fraction(3, 4), {"minimum": {"denominator": 4, "numerator": 3}}, overall["p90_coverage"]),
        _gate_check("heldout-confidence-threshold", cast(JsonObject, overall["confidence"])["at_or_above_threshold_count"] == overall["sample_count"], {"minimum_each": {"denominator": 10, "numerator": 9}}, overall["confidence"]),
    ]
    for name, aggregate in partitions:
        checks.extend(
            [
                _gate_check(f"partition-{name}-sample-count", aggregate["sample_count"] >= 2, {"minimum": 2}, {"count": aggregate["sample_count"]}),
                _gate_check(f"partition-{name}-mae-no-regression", mae(aggregate, "model_mae_seconds") <= mae(aggregate, "standard_duration_mae_seconds"), "MODEL_MAE<=STANDARD_MAE", {"model": aggregate["model_mae_seconds"], "standard": aggregate["standard_duration_mae_seconds"]}),
                _gate_check(f"partition-{name}-p90-coverage", coverage(aggregate) >= Fraction(1, 2), {"minimum": {"denominator": 2, "numerator": 1}}, aggregate["p90_coverage"]),
            ]
        )
    for name, aggregate in families:
        checks.extend(
            [
                _gate_check(f"family-{name}-sample-count", aggregate["sample_count"] >= 2, {"minimum": 2}, {"count": aggregate["sample_count"]}),
                _gate_check(f"family-{name}-mae-no-regression", mae(aggregate, "model_mae_seconds") <= mae(aggregate, "standard_duration_mae_seconds"), "MODEL_MAE<=STANDARD_MAE", {"model": aggregate["model_mae_seconds"], "standard": aggregate["standard_duration_mae_seconds"]}),
                _gate_check(f"family-{name}-p90-coverage", coverage(aggregate) >= Fraction(1, 2), {"minimum": {"denominator": 2, "numerator": 1}}, aggregate["p90_coverage"]),
            ]
        )
    fallback_matrix = _fallback_matrix(profile.confidence_threshold)
    fallback_reasons = [
        cast(JsonObject, cast(JsonObject, item)["decision"])["fallback_reason"]
        for item in cast(list[Any], fallback_matrix["scenarios"])
        if cast(JsonObject, cast(JsonObject, item)["decision"])["fallback_used"]
    ]
    checks.append(
        _gate_check(
            "fallback-matrix",
            tuple(fallback_reasons) == EXPECTED_FALLBACK_REASONS,
            {"reason_codes": list(EXPECTED_FALLBACK_REASONS)},
            {"reason_codes": fallback_reasons},
        )
    )
    blocking_gaps = [
        cast(str, check["check_id"])
        for check in checks
        if check["result"] != "PASS"
    ]
    decision = "READY_FOR_SIMULATION_RUNTIME" if not blocking_gaps else "NOT_READY"
    _, code_digest = _source_code_identity()
    model_contract = cast(JsonObject, cast(JsonObject, profile.document["input_contract"])["model"])
    dataset_contract = cast(JsonObject, cast(JsonObject, profile.document["input_contract"])["dataset"])
    gate_projection: JsonObject = {
        "p6_duration_offline_gate_report_version": OFFLINE_GATE_REPORT_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "task_id": TASK_ID,
        "evaluated_at_utc": EVALUATED_AT_UTC,
        "profile_reference": {
            "profile_id": PROFILE_ID,
            "profile_fingerprint": profile.fingerprint,
        },
        "input_lineage": {
            "dataset_bundle_fingerprint": dataset_contract["bundle_fingerprint"],
            "dataset_manifest_id": dataset_contract["manifest_id"],
            "dataset_manifest_fingerprint": dataset_contract["manifest_fingerprint"],
            "model_bundle_fingerprint": model_contract["bundle_fingerprint"],
            "model_manifest_id": model_contract["manifest_id"],
            "model_manifest_fingerprint": model_contract["manifest_fingerprint"],
            "model_artifact_digest": model_contract["artifact_digest"],
            "model_version": model_contract["model_version"],
            "evaluation_code_digest": code_digest,
        },
        "selection": selection,
        "measurement_report": measurement,
        "metrics": {
            "overall": overall,
            "partitions": [
                {"partition": name, "aggregate": aggregate}
                for name, aggregate in partitions
            ],
            "operation_families": [
                {"operation_family": name, "aggregate": aggregate}
                for name, aggregate in families
            ],
        },
        "fallback_evidence": fallback_matrix,
        "checks": checks,
        "gate_decision": {
            "blocking_gaps": blocking_gaps,
            "decision": decision,
            "gate_contract": "p6-duration-offline-confidence-fallback-gate.v1",
        },
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "synthetic": True,
        "production_binding": False,
        "governance_boundary": {
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
            "planning_authority": "NONE",
            "production_authorized": False,
            "promotion_authorized": False,
            "runtime_authorized": False,
        },
    }
    gate_report = _with_identity(
        gate_projection,
        id_field="gate_report_id",
        fingerprint_field="gate_report_fingerprint",
        prefix="p6-duration-offline-gate-report-",
    )
    validate_offline_gate_report(gate_report, profile)
    return DurationEvaluationBuild(measurement, gate_report)


def _verify_identity(
    value: Mapping[str, Any],
    *,
    id_field: str,
    fingerprint_field: str,
    prefix: str,
    path: str,
) -> None:
    projection = deepcopy(dict(value))
    identifier = projection.pop(id_field, None)
    fingerprint = projection.pop(fingerprint_field, None)
    expected = _fingerprint(projection)
    if fingerprint != expected or identifier != prefix + expected.removeprefix("sha256:"):
        _fail("REPORT_IDENTITY_MISMATCH", path)


def _walk_forbidden_evidence(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_EVIDENCE_KEYS:
                _fail("UNSAFE_EVIDENCE_PAYLOAD", f"{path}.{key}")
            _walk_forbidden_evidence(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_evidence(child, f"{path}[{index}]")


def validate_offline_gate_report(
    report: Mapping[str, Any], profile: LoadedEvaluationProfile
) -> None:
    """Freshly validate identity, decision consistency, and safe aggregation."""

    candidate = _expect_object(report, "gate-report")
    _expect_keys(
        candidate,
        {
            "p6_duration_offline_gate_report_version",
            "canonicalization_version",
            "task_id",
            "evaluated_at_utc",
            "profile_reference",
            "input_lineage",
            "selection",
            "measurement_report",
            "metrics",
            "fallback_evidence",
            "checks",
            "gate_decision",
            "data_plane",
            "environment",
            "synthetic",
            "production_binding",
            "governance_boundary",
            "gate_report_id",
            "gate_report_fingerprint",
        },
        "gate-report",
    )
    if (
        candidate["p6_duration_offline_gate_report_version"] != OFFLINE_GATE_REPORT_VERSION
        or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
        or candidate["task_id"] != TASK_ID
        or candidate["evaluated_at_utc"] != EVALUATED_AT_UTC
        or candidate["data_plane"] != DATA_PLANE
        or candidate["environment"] != ENVIRONMENT
    ):
        _fail("REPORT_CONTRACT_MISMATCH", "header")
    _expect_bool(candidate["synthetic"], True, "gate-report.synthetic")
    _expect_bool(candidate["production_binding"], False, "gate-report.production")
    if candidate["profile_reference"] != {
        "profile_id": PROFILE_ID,
        "profile_fingerprint": profile.fingerprint,
    }:
        _fail("REPORT_PROFILE_MISMATCH", "profile")
    selection = _expect_object(candidate["selection"], "gate-report.selection")
    if selection.get("train_label_reads") != 0:
        _fail("TRAIN_LABEL_READ", str(selection.get("train_label_reads")))
    checks = _expect_list(candidate["checks"], "gate-report.checks")
    check_ids = [
        _expect_string(_expect_object(item, "gate-report.check").get("check_id"), "gate-report.check.id")
        for item in checks
    ]
    if len(check_ids) != len(set(check_ids)) or not checks:
        _fail("REPORT_CHECK_MISMATCH", "duplicate-or-empty")
    failures = [
        check_id
        for check_id, raw in zip(check_ids, checks, strict=True)
        if _expect_object(raw, "gate-report.check").get("result") != "PASS"
    ]
    decision = _expect_object(candidate["gate_decision"], "gate-report.decision")
    if decision.get("blocking_gaps") != failures:
        _fail("REPORT_DECISION_MISMATCH", "blocking gaps")
    expected_decision = "READY_FOR_SIMULATION_RUNTIME" if not failures else "NOT_READY"
    if (
        decision.get("decision") != expected_decision
        or decision.get("gate_contract")
        != "p6-duration-offline-confidence-fallback-gate.v1"
    ):
        _fail("REPORT_DECISION_MISMATCH", "decision")
    measurement = _expect_object(candidate["measurement_report"], "measurement")
    if measurement.get("gate_assessment") != {
        "gate_contract": "duration-evaluation-gate.planned-p6-05",
        "decision": "NOT_EVALUATED_BY_P6_02",
        "thresholds_embedded": False,
    }:
        _fail("MEASUREMENT_CONTRACT_MISMATCH", "gate assessment")
    _verify_identity(
        measurement,
        id_field="evaluation_report_id",
        fingerprint_field="evaluation_report_fingerprint",
        prefix="duration-evaluation-report-",
        path="measurement",
    )
    _walk_forbidden_evidence(candidate)
    _verify_identity(
        candidate,
        id_field="gate_report_id",
        fingerprint_field="gate_report_fingerprint",
        prefix="p6-duration-offline-gate-report-",
        path="gate-report",
    )


def evaluate_duration_paths(
    *,
    dataset_path: Path,
    model_bundle_path: Path,
    model_artifact_path: Path,
    profile_path: Path,
) -> DurationEvaluationBuild:
    """Validate exact immutable files, safely load the model, and evaluate."""

    profile = load_evaluation_profile(profile_path)
    dataset_bundle, dataset_file_digest = _read_strict_json(dataset_path, "dataset-bundle")
    model_bundle, model_bundle_file_digest = _read_strict_json(
        model_bundle_path, "model-bundle"
    )
    input_contract = cast(JsonObject, profile.document["input_contract"])
    dataset_contract = cast(JsonObject, input_contract["dataset"])
    model_contract = cast(JsonObject, input_contract["model"])
    if dataset_file_digest != dataset_contract["bundle_file_sha256"]:
        _fail("DATASET_FILE_DIGEST_MISMATCH", dataset_file_digest)
    if model_bundle_file_digest != model_contract["bundle_file_sha256"]:
        _fail("MODEL_BUNDLE_FILE_DIGEST_MISMATCH", model_bundle_file_digest)
    if model_artifact_path.is_symlink():
        _fail("UNSAFE_INPUT_PATH", "model-artifact:symlink")
    try:
        artifact_file_digest = _file_sha256(model_artifact_path.read_bytes())
    except OSError as error:
        _fail("INPUT_READ_FAILED", f"model-artifact:{type(error).__name__}")
    if artifact_file_digest != model_contract["artifact_file_sha256"]:
        _fail("MODEL_ARTIFACT_FILE_DIGEST_MISMATCH", artifact_file_digest)
    manifest = _expect_object(model_bundle["model_manifest"], "model.manifest")
    configuration = _expect_object(
        model_bundle["training_configuration"], "model.configuration"
    )
    loaded = load_duration_model(model_artifact_path, manifest, configuration)
    return build_duration_evaluation(dataset_bundle, model_bundle, loaded, profile)


def write_duration_evaluation_report(
    report: Mapping[str, Any], target: Path, profile: LoadedEvaluationProfile
) -> None:
    """Validate then atomically publish one aggregate-only Gate report."""

    validate_offline_gate_report(report, profile)
    if target.is_symlink():
        _fail("UNSAFE_REPORT_PATH", "symlink")
    if target.exists() and not target.is_file():
        _fail("UNSAFE_REPORT_PATH", "not-regular-file")
    temporary_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(canonical_json_bytes(report) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        _fail("ATOMIC_REPORT_WRITE_FAILED", type(error).__name__)
