"""TASK-P2-12 end-to-end BenchmarkRunner and CLI evidence."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from app.simulation.baselines import ReferenceAlgorithm
from app.simulation.benchmarks import (
    compare_scheduler_quality,
    generate_benchmark_case,
    load_profile_set,
    run_benchmark,
    validate_benchmark_report,
)
from scripts import run_benchmark as benchmark_cli


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    return run_benchmark(root=ROOT, profile_name="xs", require_baseline=True)


def test_xs_runs_formal_ingress_global_five_references_kpi_export_and_baseline(
    report: dict[str, Any],
) -> None:
    validate_benchmark_report(report)
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-12"
    assert report["profile"] == {
        "profile_id": "P2-BENCHMARK-XS",
        "profile_version": "1.0.0",
        "size": "XS",
        "seed": 20261201,
        "warmup_runs": 1,
        "measured_runs": 3,
        "baseline_path": "benchmarks/baselines/p2-xs.v1.json",
    }
    assert report["problem"]["problem_hash"] == (
        "sha256:a70a0549f737b2872185189a010cd891"
        "69d1f473f893947869b42cbf99937b04"
    )
    assert report["problem"]["complexity"] == {
        "order_count": 4,
        "lot_count": 4,
        "operation_count": 8,
        "precedence_edge_count": 4,
        "resource_count": 3,
        "candidate_option_count": 16,
        "average_candidate_resource_count": 2.0,
        "calendar_fragment_count": 1,
        "historical_anchor_count": 0,
        "hard_lock_count": 0,
        "routing_depth": 2,
        "cross_workshop_ratio": 0.0,
        "material_delay_ratio": 0.25,
        "wip_ratio": 0.0,
        "lock_ratio": 0.0,
        "bottleneck_utilization": 0.067415730337,
        "horizon_ticks": 180,
    }
    assert report["global_solver"]["status"] == "OPTIMAL"
    assert report["global_solver"]["validation"] == {
        "status": "PASS",
        "validation_report_version": "validation-report.v2",
        "pass_count": 3,
        "fresh_formal": True,
    }
    assert report["global_solver"]["quality"]["solver_kpi_matches"] is True
    assert set(report["global_solver"]["model_metrics"]) == {
        "variables",
        "constraints",
        "optional_intervals",
    }

    references = report["reference_schedulers"]
    assert [row["algorithm"] for row in references] == [
        algorithm.value for algorithm in ReferenceAlgorithm
    ]
    assert all(row["status"] == "FEASIBLE" for row in references)
    assert all(row["validation"]["status"] == "PASS" for row in references)
    assert all(row["quality"]["shared_kpi_matches"] for row in references)
    assert all(row["deterministic_replay"] for row in references)
    assert all(len(set(row["sample_fingerprints"])) == 1 for row in references)

    assert report["comparison"] == {
        "same_problem_hash": True,
        "same_formal_validator": True,
        "same_schedule_kpi": "calculate_schedule_kpi_metrics.v1",
        "global_weighted_tardiness_seconds": 0,
        "best_reference_weighted_tardiness_seconds": 0,
        "best_reference_algorithms": ["EDD"],
        "global_minus_best_reference_seconds": 0,
        "global_worse_than_best_reference": False,
        "warning_code": None,
    }
    assert report["baseline"]["benchmark_baseline_version"] == (
        "benchmark-baseline.v1"
    )
    assert report["baseline"]["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert report["check_count"] == 8
    assert all(check["status"] == "PASS" for check in report["checks"])
    assert report["pipeline"]["export_file_count"] == 9


def test_generator_is_pure_self_hashed_and_profile_specific() -> None:
    profiles = load_profile_set(ROOT / "benchmarks" / "profiles.yaml")
    xs = generate_benchmark_case(profiles.select("xs"), root=ROOT)
    again = generate_benchmark_case(profiles.select("xs"), root=ROOT)
    medium = generate_benchmark_case(profiles.select("m"), root=ROOT)
    assert xs == again
    assert xs.manifest["asset_hashes"] == again.manifest["asset_hashes"]
    assert len(xs.blueprint["jobs"]) == 4
    assert len(medium.blueprint["jobs"]) == 12
    assert medium.scenario["complexity"]["factory_size"] == "M"
    assert xs.asset_paths == ()


def test_cp_sat_worse_than_reference_emits_benchmark_warning() -> None:
    global_row = {"quality": {"weighted_tardiness_seconds": 20}}
    references = [
        {
            "algorithm": algorithm.value,
            "quality": {"weighted_tardiness_seconds": index + 1},
        }
        for index, algorithm in enumerate(ReferenceAlgorithm)
    ]
    comparison, warnings = compare_scheduler_quality(global_row, references)
    assert comparison["global_worse_than_best_reference"] is True
    assert comparison["warning_code"] == "BENCHMARK_WARNING"
    assert warnings == [
        {
            "code": "BENCHMARK_WARNING",
            "severity": "WARNING",
            "message": (
                "Global CP-SAT weighted tardiness is worse than the best "
                "deterministic Reference Scheduler on the same Problem"
            ),
        }
    ]


def test_cli_writes_valid_report_without_baseline_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    report: dict[str, Any],
) -> None:
    baseline_paths = sorted((ROOT / "benchmarks" / "baselines").glob("*.json"))
    before = {path: path.read_bytes() for path in baseline_paths}

    def fake_run_benchmark(**_: object) -> dict[str, Any]:
        return deepcopy(report)

    monkeypatch.setattr(benchmark_cli, "run_benchmark", fake_run_benchmark)
    report_path = tmp_path / "xs.json"
    assert (
        benchmark_cli.main(
            [
                "--root",
                str(ROOT),
                "--profile",
                "xs",
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    written = json.loads(report_path.read_text(encoding="utf-8"))
    validate_benchmark_report(written)
    assert {path: path.read_bytes() for path in baseline_paths} == before

    monkeypatch.setenv("PLANTNEXUS_CODE_COMMIT", "not-a-sha-or-safe-provenance")
    failure = benchmark_cli._failure_report("xs", OSError("missing baseline"))
    assert failure["code_commit"] == "uncommitted"


def test_report_keeps_non_production_and_phase_boundaries(
    report: dict[str, Any],
) -> None:
    assert report["environment"]["environment_signature"].startswith("sha256:")
    assert "hostname" not in report["environment"]
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "profiles": "XS_S_M_ONLY",
        "l_xl": "DEFERRED_RELEASE_OR_DEDICATED_ENVIRONMENT",
        "production_capacity_sla": "NOT_ESTABLISHED_OPEN_012",
        "historical_production_baseline": "NOT_AVAILABLE_OPEN_011",
        "approval_publish_external_transfer": "PROHIBITED",
        "p2_13_p2_14_p3": "NOT_STARTED",
    }
