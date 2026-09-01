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
    validate_duration_prediction,
)
from backend.tests.p6_duration_runtime_support import (
    build_test_provider,
    canonical_json_bytes,
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
