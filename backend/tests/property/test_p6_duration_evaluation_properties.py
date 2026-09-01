from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st

from app.duration_prediction.evaluation import (
    build_duration_evaluation,
    canonical_json_bytes,
    interval_tightness_confidence,
    load_evaluation_profile,
    select_duration_with_fallback,
)
from app.duration_prediction.model import load_duration_model

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "benchmarks" / "p6" / "duration-evaluation-profile.v1.json"
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
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MODEL"
    / "baseline-model.v1.pnmodel"
)


def _load(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@settings(max_examples=24, deadline=None)
@given(order=st.permutations(tuple(range(8))))
def test_dataset_source_order_cannot_change_aggregate_gate_report(
    order: tuple[int, ...],
) -> None:
    dataset = _load(DATASET_PATH)
    model_bundle = _load(MODEL_BUNDLE_PATH)
    profile = load_evaluation_profile(PROFILE_PATH)
    loaded_model = load_duration_model(
        MODEL_ARTIFACT_PATH,
        model_bundle["model_manifest"],
        model_bundle["training_configuration"],
    )
    baseline = build_duration_evaluation(
        dataset, model_bundle, loaded_model, profile
    )
    reordered = deepcopy(dataset)
    rows = dataset["rows"]
    reordered["rows"] = [deepcopy(rows[index]) for index in order]

    replay = build_duration_evaluation(
        reordered, model_bundle, loaded_model, profile
    )

    assert replay.gate_report == baseline.gate_report
    assert canonical_json_bytes(replay.gate_report) == canonical_json_bytes(
        baseline.gate_report
    )


@settings(max_examples=100, deadline=None)
@given(
    p50=st.integers(min_value=1, max_value=100_000),
    margin=st.integers(min_value=0, max_value=200_000),
)
def test_interval_confidence_is_exact_bounded_and_float_free(
    p50: int, margin: int
) -> None:
    observed = interval_tightness_confidence(p50, p50 + margin)
    expected = max(Fraction(0), Fraction(p50 - margin, p50))

    assert observed == expected
    assert isinstance(observed, Fraction)
    assert Fraction(0) <= observed <= Fraction(1)


@settings(max_examples=100, deadline=None)
@given(
    standard=st.integers(min_value=1, max_value=100_000),
    p50=st.integers(min_value=1, max_value=100_000),
    score_numerator=st.integers(min_value=0, max_value=100),
)
def test_fallback_threshold_boundary_never_changes_standard_authority(
    standard: int, p50: int, score_numerator: int
) -> None:
    confidence = Fraction(score_numerator, 100)
    decision = select_duration_with_fallback(
        standard_duration_seconds=standard,
        p50_seconds=p50,
        p90_seconds=p50,
        confidence=confidence,
    )

    if confidence < Fraction(9, 10):
        assert decision["fallback_used"] is True
        assert decision["selected_source"] == "STANDARD_DURATION"
        assert decision["selected_duration_seconds"] == standard
        assert decision["fallback_reason"] == "FALLBACK_CONFIDENCE_BELOW_THRESHOLD"
    else:
        assert decision["fallback_used"] is False
        assert decision["selected_source"] == "MODEL_P50"
        assert decision["selected_duration_seconds"] == p50
        assert decision["fallback_reason"] is None
