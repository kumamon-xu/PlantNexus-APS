"""Shared builders for focused P6 runtime tests and machine evidence."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from app.duration_prediction.evaluation import (
    evaluate_duration_paths,
    load_evaluation_profile,
)
from app.duration_prediction.runtime import (
    CandidatePredictor,
    DurationPredictionProvider,
    DurationPredictionRequest,
    LoadedMonitoringPolicy,
    MonotonicClock,
    build_duration_prediction_provider,
    load_duration_monitoring_policy,
    load_duration_runtime_policy,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-DATASET"
    / "expected-dataset-bundle.v1.json"
)
MODEL_BUNDLE_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MODEL"
    / "expected-model-bundle.v1.json"
)
MODEL_ARTIFACT_PATH = (
    ROOT / "fixtures" / "synthetic" / "P6-DURATION-MODEL" / "baseline-model.v1.pnmodel"
)
EVALUATION_PROFILE_PATH = (
    ROOT / "benchmarks" / "p6" / "duration-evaluation-profile.v1.json"
)
RUNTIME_POLICY_PATH = (
    ROOT / "fixtures" / "synthetic" / "P6-DURATION-RUNTIME" / "runtime-policy.v1.json"
)
MONITORING_POLICY_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MONITORING"
    / "monitor-policy.v1.json"
)
PREDICTION_SCHEMA_PATH = ROOT / "schemas" / "json" / "duration-prediction.schema.json"


def load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def recompute_feature_identity(feature_record: dict[str, Any]) -> dict[str, Any]:
    projection = {
        key: value
        for key, value in feature_record.items()
        if key not in {"feature_record_id", "feature_record_fingerprint"}
    }
    digest = sha256(canonical_json_bytes(projection)).hexdigest()
    feature_record["feature_record_id"] = f"duration-feature-record-{digest}"
    feature_record["feature_record_fingerprint"] = f"sha256:{digest}"
    return feature_record


def recompute_monitoring_window_identity(window: dict[str, Any]) -> dict[str, Any]:
    projection = {
        key: value
        for key, value in window.items()
        if key not in {"window_id", "window_fingerprint"}
    }
    digest = sha256(canonical_json_bytes(projection)).hexdigest()
    window["window_id"] = f"duration-monitoring-window-{digest}"
    window["window_fingerprint"] = f"sha256:{digest}"
    return window


def standard_duration_for_feature(feature_record: dict[str, Any]) -> dict[str, Any]:
    standard_feature = next(
        item
        for item in feature_record["features"]
        if item["feature_name"] == "standard_duration_seconds"
    )
    source_id = standard_feature["source_record_ids"][0]
    source = next(
        item
        for item in feature_record["source_records"]
        if item["source_record_id"] == source_id
    )
    return {
        "seconds": standard_feature["value"],
        "duration_source": source["source_system"],
        "source_version": source["source_version"],
        "source_record_id": source["source_record_id"],
        "source_record_fingerprint": source["record_fingerprint"],
    }


def runtime_inputs() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    dataset = load_json(DATASET_PATH)
    model_bundle = load_json(MODEL_BUNDLE_PATH)
    evaluation = evaluate_duration_paths(
        dataset_path=DATASET_PATH,
        model_bundle_path=MODEL_BUNDLE_PATH,
        model_artifact_path=MODEL_ARTIFACT_PATH,
        profile_path=EVALUATION_PROFILE_PATH,
    )
    return (
        dataset,
        model_bundle,
        evaluation.measurement_report,
        evaluation.gate_report,
    )


def build_test_provider(
    *,
    candidate_predictor: CandidatePredictor | None = None,
    monotonic_clock: MonotonicClock | None = None,
    gate_report: dict[str, Any] | None = None,
    model_bundle: dict[str, Any] | None = None,
    model_artifact_path: Path = MODEL_ARTIFACT_PATH,
) -> DurationPredictionProvider:
    _, default_model_bundle, _, default_gate = runtime_inputs()
    kwargs: dict[str, Any] = {}
    if candidate_predictor is not None:
        kwargs["candidate_predictor"] = candidate_predictor
    if monotonic_clock is not None:
        kwargs["monotonic_clock"] = monotonic_clock
    return build_duration_prediction_provider(
        runtime_policy=load_duration_runtime_policy(RUNTIME_POLICY_PATH),
        evaluation_profile=load_evaluation_profile(EVALUATION_PROFILE_PATH),
        gate_report=deepcopy(gate_report if gate_report is not None else default_gate),
        model_bundle=deepcopy(
            model_bundle if model_bundle is not None else default_model_bundle
        ),
        model_artifact_path=model_artifact_path,
        **kwargs,
    )


def runtime_requests() -> list[DurationPredictionRequest]:
    dataset = load_json(DATASET_PATH)
    requests: list[DurationPredictionRequest] = []
    for row in dataset["rows"]:
        feature = deepcopy(row["feature_record"])
        requests.append(
            DurationPredictionRequest(
                factory_id=feature["factory_id"],
                operation_id=feature["operation_id"],
                resource_option_id=feature["resource_option_id"],
                resource_id=feature["resource_id"],
                predicted_at_utc="2026-09-01T10:30:00Z",
                as_of_cutoff_utc=feature["as_of_cutoff_utc"],
                standard_duration=standard_duration_for_feature(feature),
                feature_record=feature,
            )
        )
    return requests


def load_monitoring_policy() -> LoadedMonitoringPolicy:
    return load_duration_monitoring_policy(MONITORING_POLICY_PATH)


def monitoring_window(
    *,
    observation_count: int = 8,
    candidate_count: int = 7,
    fallback_count: int = 1,
    fallback_reason_counts: dict[str, int] | None = None,
    late_observation_count: int = 0,
    model_version_counts: dict[str, int] | None = None,
    feature_schema_version_counts: dict[str, int] | None = None,
    feature_bucket_counts: dict[str, int] | None = None,
    quality_evaluated_count: int = 8,
    quality_pass_count: int = 7,
) -> dict[str, Any]:
    policy = load_monitoring_policy()
    document: dict[str, Any] = {
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "duration_monitoring_window_version": "duration-monitoring-window.v1",
        "environment": "TEST",
        "feature_distribution": {
            "bucket_counts": feature_bucket_counts
            if feature_bucket_counts is not None
            else {"HIGH": 2, "LOW": 2, "MID_HIGH": 2, "MID_LOW": 2},
            "profile_version": "duration-feature-aggregate-profile.v1",
        },
        "outcomes": {
            "candidate_count": candidate_count,
            "fallback_count": fallback_count,
            "fallback_reason_counts": fallback_reason_counts
            if fallback_reason_counts is not None
            else ({"LOW_CONFIDENCE": fallback_count} if fallback_count else {}),
        },
        "policy_reference": {
            "artifact_id": policy.document["policy_id"],
            "document_version": "duration-monitoring-policy.v1",
            "fingerprint": policy.fingerprint,
            "threshold_policy_version": "duration-drift-thresholds.v1",
        },
        "privacy": {
            "aggregation": "WINDOW_ONLY",
            "direct_identifiers_present": False,
            "raw_feature_fields_present": False,
            "raw_label_fields_present": False,
            "source_record_references_present": False,
        },
        "production_binding": False,
        "quality": {
            "evaluated_count": quality_evaluated_count,
            "pass_count": quality_pass_count,
            "policy_version": "duration-quality-aggregate.v1",
        },
        "runtime_reference": deepcopy(policy.document["runtime_reference"]),
        "synthetic": True,
        "versions": {
            "feature_schema_version_counts": feature_schema_version_counts
            if feature_schema_version_counts is not None
            else {"duration-features.v1": observation_count},
            "model_version_counts": model_version_counts
            if model_version_counts is not None
            else {"1.0.0": observation_count},
        },
        "window": {
            "ended_at_utc": "2026-09-01T12:00:00Z",
            "late_observation_count": late_observation_count,
            "observation_count": observation_count,
            "sequence": 1,
            "started_at_utc": "2026-09-01T11:00:00Z",
        },
    }
    return recompute_monitoring_window_identity(document)


def sequence_clock(values: list[int]) -> MonotonicClock:
    iterator: Iterator[int] = iter(values)
    return lambda: next(iterator)
