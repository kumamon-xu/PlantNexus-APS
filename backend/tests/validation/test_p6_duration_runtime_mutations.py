from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from typing import Any, Callable

import pytest

from app.duration_prediction.runtime import (
    DurationPredictionProvider,
    DurationProviderSignal,
    P6RuntimeError,
    monitor_duration_runtime,
    validate_duration_prediction,
)
from backend.tests.p6_duration_runtime_support import (
    build_test_provider,
    canonical_json_bytes,
    load_monitoring_policy,
    monitoring_window,
    recompute_monitoring_window_identity,
    runtime_requests,
)


Mutation = Callable[[dict[str, Any]], None]


@pytest.fixture(scope="module")
def provider() -> DurationPredictionProvider:
    return build_test_provider()


def _recompute_prediction_identity(prediction: dict[str, Any]) -> None:
    projection = {
        key: value
        for key, value in prediction.items()
        if key not in {"prediction_id", "prediction_fingerprint"}
    }
    digest = sha256(canonical_json_bytes(projection)).hexdigest()
    prediction["prediction_id"] = f"duration-prediction-{digest}"
    prediction["prediction_fingerprint"] = f"sha256:{digest}"


def _set_unknown(prediction: dict[str, Any]) -> None:
    prediction["unknown"] = True


def _tamper_fingerprint(prediction: dict[str, Any]) -> None:
    prediction["prediction_fingerprint"] = "sha256:" + "0" * 64


def _set_unknown_reason(prediction: dict[str, Any]) -> None:
    prediction["fallback_reason"] = "UNKNOWN"


def _set_candidate_source_to_standard(prediction: dict[str, Any]) -> None:
    prediction["selected_duration_source"] = "STANDARD_DURATION"


def _tamper_policy_reference(prediction: dict[str, Any]) -> None:
    prediction["prediction_policy_reference"]["fingerprint"] = "sha256:" + "0" * 64


def _authorize_production(prediction: dict[str, Any]) -> None:
    prediction["governance_boundary"]["production_authorized"] = True


@pytest.mark.parametrize(
    ("mutation", "recompute", "code"),
    [
        (_set_unknown, False, "OBJECT_SHAPE_MISMATCH"),
        (_tamper_fingerprint, False, "PREDICTION_IDENTITY_MISMATCH"),
        (_set_unknown_reason, True, "PREDICTION_FALLBACK_MISMATCH"),
        (_set_candidate_source_to_standard, True, "PREDICTION_CANDIDATE_MISMATCH"),
        (_tamper_policy_reference, True, "PREDICTION_POLICY_MISMATCH"),
        (_authorize_production, True, "PREDICTION_AUTHORITY_MISMATCH"),
    ],
)
def test_fresh_validator_rejects_isolated_candidate_mutations(
    provider: DurationPredictionProvider,
    mutation: Mutation,
    recompute: bool,
    code: str,
) -> None:
    prediction = provider.predict(runtime_requests()[0])
    mutation(prediction)
    if recompute:
        _recompute_prediction_identity(prediction)

    with pytest.raises(P6RuntimeError) as captured:
        validate_duration_prediction(prediction, provider.policy)

    assert captured.value.code == code


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("p50_seconds", 1),
        ("p90_seconds", 1),
        ("confidence", 0.5),
        ("selected_duration_source", "MODEL_CANDIDATE"),
        ("selected_duration_seconds", 1),
    ],
)
def test_fresh_validator_rejects_partial_fallback_mutations(
    provider: DurationPredictionProvider, field: str, value: object
) -> None:
    def timeout(*_args: object) -> None:
        raise DurationProviderSignal("PROVIDER_TIMEOUT")

    prediction = replace(provider, candidate_predictor=timeout).predict(
        runtime_requests()[0]
    )
    prediction[field] = value
    _recompute_prediction_identity(prediction)

    with pytest.raises(P6RuntimeError) as captured:
        validate_duration_prediction(prediction, provider.policy)

    assert captured.value.code == "PREDICTION_FALLBACK_MISMATCH"


def test_failed_validation_does_not_mutate_original_prediction(
    provider: DurationPredictionProvider,
) -> None:
    original = provider.predict(runtime_requests()[0])
    mutated = deepcopy(original)
    mutated["prediction_fingerprint"] = "sha256:" + "f" * 64

    with pytest.raises(P6RuntimeError):
        validate_duration_prediction(mutated, provider.policy)

    assert provider.predict(runtime_requests()[0]) == original


def test_monitoring_window_identity_tamper_defaults_disabled() -> None:
    window = monitoring_window()
    window["outcomes"]["candidate_count"] = 6

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == ["TELEMETRY_TAMPERED"]
    assert report["window_reference"] is None


def test_invalid_half_open_window_defaults_disabled_with_fresh_identity() -> None:
    window = monitoring_window()
    window["window"]["ended_at_utc"] = window["window"]["started_at_utc"]
    recompute_monitoring_window_identity(window)

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == ["TELEMETRY_WINDOW_INVALID"]


def test_incomplete_quality_aggregate_requires_default_disable() -> None:
    window = monitoring_window(quality_evaluated_count=7, quality_pass_count=7)

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == [
        "QUALITY_EVIDENCE_INCOMPLETE"
    ]
    assert report["monitoring_decision"]["runtime_fallback_reason"] == (
        "DRIFT_GATE_DISABLED"
    )


def test_multiple_breaches_have_stable_reason_order_and_no_auto_action() -> None:
    window = monitoring_window(
        candidate_count=4,
        fallback_count=4,
        fallback_reason_counts={"PROVIDER_TIMEOUT": 4},
        late_observation_count=1,
        model_version_counts={"2.0.0": 8},
        feature_schema_version_counts={"duration-features.v2": 8},
        feature_bucket_counts={"HIGH": 8, "LOW": 0, "MID_HIGH": 0, "MID_LOW": 0},
        quality_pass_count=4,
    )

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == [
        "LATE_TELEMETRY",
        "MODEL_VERSION_DRIFT",
        "FEATURE_VERSION_DRIFT",
        "FALLBACK_RATE_BREACH",
        "FEATURE_DISTRIBUTION_DRIFT",
        "QUALITY_DRIFT",
    ]
    assert report["monitoring_decision"]["automatic_actions"] == []
    assert report["monitoring_decision"]["external_side_effects"] == []
