from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.duration_prediction.evaluation import (
    P6EvaluationError,
    canonical_json_bytes,
    evaluate_duration_paths,
    interval_tightness_confidence,
    load_evaluation_profile,
    select_duration_with_fallback,
    validate_offline_gate_report,
    write_duration_evaluation_report,
)
from scripts.p6_duration_evaluation_check import (
    build_baseline_projection,
    main as evaluation_check_main,
    run_evaluation_checks,
)

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "benchmarks" / "p6" / "duration-evaluation-profile.v1.json"
BASELINE_PATH = ROOT / "benchmarks" / "p6" / "duration-evaluation-baseline.v1.json"
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
SCHEMA_PATH = ROOT / "schemas" / "json" / "duration-evaluation-report.schema.json"
FORBIDDEN_KEYS = {
    "actual_processing_seconds",
    "dataset_row_id",
    "feature_record",
    "label",
    "records",
    "rows",
    "source_record_id",
}


def _build():  # type: ignore[no-untyped-def]
    return evaluate_duration_paths(
        dataset_path=DATASET_PATH,
        model_bundle_path=MODEL_BUNDLE_PATH,
        model_artifact_path=MODEL_ARTIFACT_PATH,
        profile_path=PROFILE_PATH,
    )


def _load(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def test_frozen_profile_and_aggregate_baseline_are_exact() -> None:
    build = _build()
    baseline = _load(BASELINE_PATH)

    assert build_baseline_projection(build.gate_report) == baseline
    assert baseline["expected_gate_decision"] == {
        "blocking_gaps": [],
        "decision": "READY_FOR_SIMULATION_RUNTIME",
        "gate_contract": "p6-duration-offline-confidence-fallback-gate.v1",
    }
    overall = baseline["expected_metrics"]["overall"]
    assert overall["model_mae_seconds"] == {"numerator": 11, "denominator": 1}
    assert overall["standard_duration_mae_seconds"] == {
        "numerator": 20,
        "denominator": 1,
    }
    assert overall["p90_coverage"] == {
        "covered_count": 4,
        "ratio": {"numerator": 1, "denominator": 1},
        "total_count": 4,
    }


def test_p6_02_measurement_carrier_remains_schema_compatible() -> None:
    measurement = _build().measurement_report
    schema = _load(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(measurement),
        key=lambda error: list(error.absolute_path),
    )

    assert errors == []
    assert measurement["gate_assessment"] == {
        "gate_contract": "duration-evaluation-gate.planned-p6-05",
        "decision": "NOT_EVALUATED_BY_P6_02",
        "thresholds_embedded": False,
    }
    metrics = {item["metric_name"]: item for item in measurement["metrics"]}
    assert metrics["MAE_SECONDS"]["value"] == 11
    assert metrics["P50_ABSOLUTE_ERROR_SECONDS"]["value"] == 10
    assert metrics["P90_COVERAGE_RATIO"]["value"] == 1
    assert metrics["STANDARD_DURATION_MAE_SECONDS"]["value"] == 20


def test_gate_report_is_strict_aggregate_only_and_has_zero_train_label_reads() -> None:
    build = _build()
    profile = load_evaluation_profile(PROFILE_PATH)

    validate_offline_gate_report(build.gate_report, profile)
    assert build.gate_report["selection"] == {
        "included_partitions": ["validation", "test"],
        "partition_counts": {"validation": 2, "test": 2},
        "heldout_row_count": 4,
        "operation_family_counts": {"milling": 2, "turning": 2},
        "train_label_reads": 0,
        "train_label_read_limit": 0,
    }
    assert _walk_keys(build.gate_report).isdisjoint(FORBIDDEN_KEYS)
    assert build.gate_report["governance_boundary"] == {
        "open_authority_gaps": ["OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015"],
        "planning_authority": "NONE",
        "production_authorized": False,
        "promotion_authorized": False,
        "runtime_authorized": False,
    }


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"confidence": None}, "FALLBACK_CONFIDENCE_MISSING"),
        ({"confidence": Fraction(11, 10)}, "FALLBACK_CONFIDENCE_INVALID"),
        ({"confidence": Fraction(89, 100)}, "FALLBACK_CONFIDENCE_BELOW_THRESHOLD"),
        ({"p50_seconds": 580, "p90_seconds": 570}, "FALLBACK_QUANTILES_INVALID"),
        ({"lineage_compatible": False}, "FALLBACK_LINEAGE_INCOMPATIBLE"),
        ({"model_valid": False}, "FALLBACK_MODEL_INVALID"),
        ({"timed_out": True}, "FALLBACK_TIMEOUT"),
        ({"model_authorized": False}, "FALLBACK_AUTHORITY_UNAVAILABLE"),
        ({"privacy_safe": False}, "FALLBACK_PRIVACY_BOUNDARY"),
    ],
)
def test_every_frozen_fallback_reason_selects_exact_standard_duration(
    kwargs: dict[str, object], expected_reason: str
) -> None:
    arguments: dict[str, Any] = {
        "standard_duration_seconds": 600,
        "p50_seconds": 540,
        "p90_seconds": 570,
        "confidence": Fraction(19, 20),
    }
    arguments.update(kwargs)

    decision = select_duration_with_fallback(**arguments)

    assert decision == {
        "fallback_used": True,
        "fallback_reason": expected_reason,
        "selected_duration_seconds": 600,
        "selected_source": "STANDARD_DURATION",
    }


def test_exact_confidence_at_threshold_selects_model_candidate() -> None:
    decision = select_duration_with_fallback(
        standard_duration_seconds=600,
        p50_seconds=100,
        p90_seconds=110,
        confidence=interval_tightness_confidence(100, 110),
    )

    assert interval_tightness_confidence(100, 110) == Fraction(9, 10)
    assert decision == {
        "fallback_used": False,
        "fallback_reason": None,
        "selected_duration_seconds": 100,
        "selected_source": "MODEL_P50",
    }


def test_invalid_standard_duration_fails_closed_before_model_selection() -> None:
    with pytest.raises(P6EvaluationError) as captured:
        select_duration_with_fallback(
            standard_duration_seconds=0,
            p50_seconds=100,
            p90_seconds=110,
            confidence=Fraction(9, 10),
        )

    assert captured.value.code == "INVALID_INTEGER"


def test_atomic_gate_report_writer_replays_exact_bytes(tmp_path: Path) -> None:
    build = _build()
    profile = load_evaluation_profile(PROFILE_PATH)
    target = tmp_path / "evaluation.json"

    write_duration_evaluation_report(build.gate_report, target, profile)

    assert target.read_bytes() == canonical_json_bytes(build.gate_report) + b"\n"


def test_machine_reporter_replays_baseline_and_writes_safe_report(tmp_path: Path) -> None:
    report = run_evaluation_checks(ROOT)
    target = tmp_path / "machine.json"

    exit_code = evaluation_check_main(
        ["--root", str(ROOT), "--report", str(target)]
    )

    assert report["result"] == "PASS"
    assert report["issues"] == []
    assert report["gate_decision"]["decision"] == "READY_FOR_SIMULATION_RUNTIME"
    assert exit_code == 0
    written = _load(target)
    assert written == report
    assert _walk_keys(written["gate_report"]).isdisjoint(FORBIDDEN_KEYS)


def test_full_validation_runs_reporter_and_isolates_post_frozen_paths() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count(
        "uv run python scripts/p6_duration_evaluation_check.py"
    ) == 1
    assert workflow.count(
        "--report build/validation/ci-p6-duration-evaluation.json"
    ) == 1
    replay_removals = workflow.split("          rm -- \\\n", maxsplit=1)[1].split(
        "\n          git -C", maxsplit=1
    )[0]
    for relative_path in (
        "backend/app/duration_prediction/evaluation.py",
        "backend/tests/contract/test_p6_duration_evaluation.py",
        "backend/tests/property/test_p6_duration_evaluation_properties.py",
        "backend/tests/validation/test_p6_duration_evaluation_mutations.py",
    ):
        assert f'"${{replay_root}}/{relative_path}"' in replay_removals
