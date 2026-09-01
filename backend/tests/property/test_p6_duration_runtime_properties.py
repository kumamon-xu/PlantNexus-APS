from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings, strategies as st
import pytest

from app.duration_prediction.runtime import (
    REGISTERED_FALLBACK_REASONS,
    DurationCandidate,
    DurationPredictionProvider,
    DurationProviderSignal,
)
from backend.tests.p6_duration_runtime_support import (
    build_test_provider,
    canonical_json_bytes,
    recompute_feature_identity,
    runtime_requests,
)


@pytest.fixture(scope="module")
def provider() -> DurationPredictionProvider:
    return build_test_provider()


@settings(max_examples=40, deadline=None)
@given(
    reason=st.sampled_from(REGISTERED_FALLBACK_REASONS),
    standard_seconds=st.integers(min_value=1, max_value=10_000_000),
)
def test_any_registered_failure_preserves_exact_positive_standard_duration(
    provider: DurationPredictionProvider,
    reason: str,
    standard_seconds: int,
) -> None:
    request = runtime_requests()[0]
    standard = {**request.standard_duration, "seconds": standard_seconds}
    feature = dict(request.feature_record)
    features = [dict(item) for item in feature["features"]]
    for item in features:
        if item["feature_name"] == "standard_duration_seconds":
            item["value"] = standard_seconds
    feature["features"] = features
    recompute_feature_identity(feature)
    request = replace(request, standard_duration=standard, feature_record=feature)

    def signal(*_args: object) -> None:
        raise DurationProviderSignal(reason)

    prediction = replace(provider, candidate_predictor=signal).predict(request)

    assert prediction["fallback_reason"] == reason
    assert prediction["selected_duration_seconds"] == standard_seconds
    assert prediction["standard_duration"] == standard


@settings(max_examples=40, deadline=None)
@given(
    p50=st.integers(min_value=10, max_value=100_000),
    margin=st.integers(min_value=0, max_value=20_000),
)
def test_exact_confidence_boundary_is_deterministic(
    provider: DurationPredictionProvider, p50: int, margin: int
) -> None:
    candidate_provider = replace(
        provider,
        candidate_predictor=lambda *_args: DurationCandidate(p50, p50 + margin),
    )

    prediction = candidate_provider.predict(runtime_requests()[0])

    if margin * 10 <= p50:
        assert prediction["fallback_reason"] == "NONE"
        assert prediction["selected_duration_seconds"] == p50
    else:
        assert prediction["fallback_reason"] == "LOW_CONFIDENCE"
        assert (
            prediction["selected_duration_seconds"]
            == prediction["standard_duration"]["seconds"]
        )


@settings(max_examples=24, deadline=None)
@given(row_index=st.integers(min_value=0, max_value=7))
def test_same_input_replay_has_exact_bytes(
    provider: DurationPredictionProvider, row_index: int
) -> None:
    request = runtime_requests()[row_index]

    first = provider.predict(request)
    second = provider.predict(request)

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["prediction_id"] == second["prediction_id"]
    assert first["prediction_fingerprint"] == second["prediction_fingerprint"]


@settings(max_examples=24, deadline=None)
@given(row_index=st.integers(min_value=0, max_value=7))
def test_return_value_mutation_cannot_poison_later_predictions(
    provider: DurationPredictionProvider, row_index: int
) -> None:
    request = runtime_requests()[row_index]
    expected = provider.predict(request)
    poisoned = provider.predict(request)
    poisoned["selected_duration_seconds"] = 1
    poisoned["standard_duration"]["seconds"] = 1
    poisoned["model_reference"]["model_version"] = "999.0.0"

    replay = provider.predict(request)

    assert replay == expected
