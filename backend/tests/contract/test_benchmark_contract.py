"""TASK-P2-12 strict Profile, Report, Baseline, and common KPI contracts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from app.planning.reporting import (
    build_kpi_v2,
    calculate_schedule_kpi_metrics,
)
from app.simulation.baselines import ReferenceAlgorithm, ReferenceSchedulerStatus
from app.simulation.baselines.reference_schedulers import schedule_reference
from app.simulation.benchmarks import (
    BenchmarkContractError,
    BenchmarkContractErrorCode,
    aggregate_samples,
    load_baseline,
    load_profile_set,
    make_baseline_document,
    run_benchmark,
    validate_baseline_document,
    validate_benchmark_report,
)
from app.simulation.benchmarks.reporting import validate_profile_set_document
from app.simulation.scenarios.p2_correctness import (
    execute_correctness_case,
    load_correctness_cases,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def xs_report() -> dict[str, Any]:
    return run_benchmark(root=ROOT, profile_name="xs", require_baseline=True)


def test_profile_set_is_exactly_versioned_xs_s_m_without_release_sizes() -> None:
    profile_set = load_profile_set(ROOT / "benchmarks" / "profiles.yaml")
    assert tuple(profile_set.profiles) == ("xs", "s", "m")
    assert {
        name: (
            profile.size,
            profile.operation_count,
            profile.warmup_runs,
            profile.measured_runs,
        )
        for name, profile in profile_set.profiles.items()
    } == {
        "xs": ("XS", 8, 1, 3),
        "s": ("S", 24, 1, 3),
        "m": ("M", 48, 1, 3),
    }
    assert all(
        profile.baseline_path == f"benchmarks/baselines/p2-{name}.v1.json"
        for name, profile in profile_set.profiles.items()
    )

    raw = yaml.safe_load(
        (ROOT / "benchmarks" / "profiles.yaml").read_text(encoding="utf-8")
    )
    raw["profiles"]["l"] = deepcopy(raw["profiles"]["m"])
    with pytest.raises(BenchmarkContractError) as blocked:
        validate_profile_set_document(raw)
    assert blocked.value.code is BenchmarkContractErrorCode.INVALID_PROFILE


def test_v1_baselines_are_strict_immutable_and_problem_bound() -> None:
    expected_hashes = {
        "xs": "sha256:a70a0549f737b2872185189a010cd89169d1f473f893947869b42cbf99937b04",
        "s": "sha256:42ee217e95dc406a9feb5bf7813a3b73c8a5c6cca028905b0cfad68ffff75bb4",
        "m": "sha256:a49ee150d456da16eda94da8977500543e137ce78710248f0bc6abea5e0c26aa",
    }
    for name, expected_hash in expected_hashes.items():
        path = ROOT / "benchmarks" / "baselines" / f"p2-{name}.v1.json"
        baseline = load_baseline(path)
        assert baseline["problem"]["problem_hash"] == expected_hash
        assert baseline["boundaries"] == {
            "synthetic_only": True,
            "production_sla": "NOT_ESTABLISHED_OPEN_012",
            "overwrite_policy": "IMMUTABLE_CREATE_NEW_VERSION",
        }
        assert json.loads(path.read_text(encoding="utf-8")) == baseline

    tampered = load_baseline(
        ROOT / "benchmarks" / "baselines" / "p2-xs.v1.json"
    )
    tampered["overwrite_existing"] = True
    with pytest.raises(BenchmarkContractError) as rejected:
        validate_baseline_document(tampered)
    assert rejected.value.code is BenchmarkContractErrorCode.INVALID_BASELINE


def test_nearest_rank_aggregates_keep_raw_samples() -> None:
    assert aggregate_samples([3.0, 1.0, 2.0]) == {
        "samples": [3.0, 1.0, 2.0],
        "minimum": 1.0,
        "median": 2.0,
        "p95": 3.0,
        "maximum": 3.0,
    }
    assert aggregate_samples([2.0, 1.0])["median"] == 1.5
    with pytest.raises(BenchmarkContractError):
        aggregate_samples([])


def test_report_validator_rejects_unknown_nested_fields(
    xs_report: dict[str, Any],
) -> None:
    validate_benchmark_report(xs_report)
    baseline = make_baseline_document(xs_report)
    validate_baseline_document(baseline)
    assert baseline["problem"] == {
        "problem_hash": xs_report["problem"]["problem_hash"],
        "complexity": xs_report["problem"]["complexity"],
    }

    unexpected = deepcopy(xs_report)
    unexpected["pipeline"]["implicit_shape"] = "FORBIDDEN"
    with pytest.raises(BenchmarkContractError) as extra:
        validate_benchmark_report(unexpected)
    assert extra.value.code is BenchmarkContractErrorCode.INVALID_REPORT

    missing = deepcopy(xs_report)
    del missing["global_solver"]["memory_peak_mb"]
    with pytest.raises(BenchmarkContractError) as absent:
        validate_benchmark_report(missing)
    assert absent.value.code is BenchmarkContractErrorCode.INVALID_REPORT

    false_summary = deepcopy(xs_report)
    false_summary["global_solver"]["timings"]["solve_seconds"]["median"] += 1.0
    with pytest.raises(BenchmarkContractError) as inconsistent:
        validate_benchmark_report(false_summary)
    assert inconsistent.value.code is BenchmarkContractErrorCode.INVALID_REPORT

    wrong_baseline_type = deepcopy(baseline)
    wrong_baseline_type["observed"]["global"]["objective"] = "0"
    with pytest.raises(BenchmarkContractError) as wrong_type:
        validate_baseline_document(wrong_baseline_type)
    assert wrong_type.value.code is BenchmarkContractErrorCode.INVALID_BASELINE


def test_global_kpi_v2_and_all_references_share_pure_schedule_calculation() -> None:
    replay = execute_correctness_case(load_correctness_cases(ROOT)[1], root=ROOT)
    global_shared = calculate_schedule_kpi_metrics(
        replay.problem,
        cast(list[dict[str, object]], replay.solution["assignments"]),
    )
    immutable = build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )
    assert immutable.document["delivery"] == global_shared.delivery_document
    assert immutable.document["planning"] == global_shared.planning_document
    assert immutable.document["resources"] == global_shared.resource_documents

    for algorithm in ReferenceAlgorithm:
        result = schedule_reference(cast(Any, replay.problem), algorithm)
        assert result["status"] is ReferenceSchedulerStatus.FEASIBLE
        assert result["candidate"] is not None
        shared = calculate_schedule_kpi_metrics(
            replay.problem,
            cast(list[dict[str, object]], result["candidate"]["assignments"]),
        )
        assert (
            result["metrics"]["weighted_tardiness_seconds"]
            == shared.priority_weighted_tardiness_seconds
        )
        assert result["metrics"]["makespan_seconds"] == shared.makespan_seconds
