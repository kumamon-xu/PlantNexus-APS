"""P9 sealed catalog, deterministic generation and fail-closed budgets."""

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from app.simulation.benchmarks.p9_catalog import (
    CATALOG_PATH,
    SEAL_PATH,
    child_value,
    evaluate_budget,
    freeze_budget,
    generate_input,
    read_catalog,
)

ROOT = Path(__file__).resolve().parents[3]


def test_successor_catalog_is_sealed_disjoint_and_development_is_unchanged():
    old = read_catalog(ROOT)
    new = read_catalog(ROOT, "v2")
    assert set(new["splits"]["holdout"].values()).isdisjoint(
        set(old["splits"]["holdout"].values()) | set(old["splits"]["development"].values())
    )
    for size in ("xs", "s", "m"):
        original = generate_input(ROOT, "development", size)
        successor = generate_input(ROOT, "development", size, version="v2")
        assert original["input_fingerprint"] == successor["input_fingerprint"]
        assert original["profile"] == successor["profile"]
    with pytest.raises(ValueError, match="P9_HOLDOUT_ACCESS_NOT_RECORDED"):
        generate_input(ROOT, "holdout", "m", version="v2")


@pytest.mark.parametrize("size,operations", [("xs", 8), ("s", 24), ("m", 48)])
def test_named_generation_replays_without_reading_holdout(size, operations):
    first = generate_input(ROOT, "development", size)
    child_value(1, "unrelated", 10)
    second = generate_input(ROOT, "development", size)
    assert first == second
    assert sum(len(j["operations"]) for j in first["blueprint"]["jobs"]) == operations
    assert first["package"]["synthetic"] is True
    assert first["seed"] not in read_catalog(ROOT)["splits"]["holdout"].values()


def test_holdout_is_closed_without_frozen_budget_access_record():
    with pytest.raises(ValueError, match="P9_HOLDOUT_ACCESS_NOT_RECORDED"):
        generate_input(ROOT, "holdout", "xs")


def test_catalog_tamper_is_rejected_before_generation(tmp_path):
    for filename in (CATALOG_PATH, SEAL_PATH):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, path)
    path = tmp_path / CATALOG_PATH
    path.write_bytes(path.read_bytes().replace(b"910901", b"910101"))
    with pytest.raises(ValueError, match="P9_CATALOG_SEAL_MISMATCH"):
        read_catalog(tmp_path)


def calibration():
    return {
        "split": "development",
        "result": "PASS",
        "environment": {"cpu": "fixed"},
        "catalog_sha256": "fixed",
        "samples": {
            size: [
                {
                    "measurements": {
                        "end_to_end_seconds": 2.0,
                        "solve_seconds": 0.1,
                        "memory_peak_mb": 2.0,
                    }
                }
                for _ in range(3)
            ]
            for size in ("xs", "s", "m")
        },
    }


def test_budget_frozen_before_holdout_and_exact_boundary():
    report = calibration()
    baseline = freeze_budget(report, read_catalog(ROOT))
    assert baseline["budgets"]["xs"]["end_to_end_seconds"] == 5.0
    assert evaluate_budget(report, baseline) == []
    report["samples"]["xs"][0]["measurements"]["end_to_end_seconds"] = 5.0
    assert evaluate_budget(report, baseline) == []
    report["samples"]["xs"][0]["measurements"]["end_to_end_seconds"] = 5.001
    assert evaluate_budget(report, baseline)


@pytest.mark.parametrize(
    "mutation",
    [
        "environment",
        "catalog",
        "missing_profile",
        "missing_sample",
        "nan",
        "negative",
        "missing_metric",
    ],
)
def test_incomplete_or_incomparable_measurements_cannot_pass(mutation):
    original = calibration()
    baseline = freeze_budget(original, read_catalog(ROOT))
    report = deepcopy(original)
    if mutation == "environment":
        report["environment"] = {}
    elif mutation == "catalog":
        report["catalog_sha256"] = "changed"
    elif mutation == "missing_profile":
        report["samples"].pop("m")
    elif mutation == "missing_sample":
        report["samples"]["xs"].pop()
    else:
        metrics = report["samples"]["xs"][0]["measurements"]
        if mutation == "missing_metric":
            metrics.pop("solve_seconds")
        else:
            metrics["solve_seconds"] = float("nan") if mutation == "nan" else -1
    assert evaluate_budget(report, baseline)


def test_holdout_results_cannot_become_development_baseline():
    report = calibration()
    report["split"] = "holdout"
    with pytest.raises(ValueError, match="P9_BASELINE_REQUIRES_SUCCESSFUL_DEVELOPMENT"):
        freeze_budget(report, read_catalog(ROOT))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, None])
def test_invalid_calibration_cannot_freeze_a_budget(value):
    report = calibration()
    report["samples"]["xs"][0]["measurements"]["solve_seconds"] = value
    with pytest.raises(ValueError, match="P9_BASELINE_INVALID_MEASUREMENTS"):
        freeze_budget(report, read_catalog(ROOT))


@pytest.mark.parametrize("limits", [{}, {"solve_seconds": float("nan")}])
def test_empty_or_nonfinite_budget_cannot_pass(limits):
    report = calibration()
    baseline = freeze_budget(report, read_catalog(ROOT))
    baseline["budgets"]["xs"] = limits
    assert evaluate_budget(report, baseline)
