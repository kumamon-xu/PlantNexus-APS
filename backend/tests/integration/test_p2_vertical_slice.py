"""TASK-P2-13 complete P2 vertical-slice Gate integration evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.application import p2_gate_report
from app.application.p2_gate_report import validate_p2_vertical_slice_report


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_SCENARIOS = [
    "P2-GOLDEN-JSSP",
    "P2-GOLDEN-FJSP",
    "P2-CROSS-WORKSHOP",
    "P2-CALENDAR",
    "P2-MATERIAL-DELAY",
    "P2-RUNNING",
    "P2-HARD-LOCK",
]
EXPECTED_CONSTRAINTS = [f"C-{index:03d}" for index in range(1, 12)]


@pytest.fixture(scope="module")
def gate_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    report_path = tmp_path_factory.mktemp("p2-gate") / "report.json"
    assert (
        p2_gate_report.main(
            [
                "--root",
                str(ROOT),
                "--repeat",
                "2",
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    report = cast(
        dict[str, Any], json.loads(report_path.read_text(encoding="utf-8"))
    )
    validate_p2_vertical_slice_report(report)
    return report


def _checks(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["name"]: check for check in report["checks"]}


def test_gate_runs_two_complete_public_boundary_replays(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["report_version"] == "p2-vertical-slice-report.v1"
    assert gate_report["status"] == "PASS"
    assert gate_report["task_id"] == "TASK-P2-13"
    assert gate_report["repeat_count"] == 2
    assert gate_report["execution"] == {
        "minimum_repeat_count": 2,
        "full_replays_complete": 2,
        "all_public_boundaries_reexecuted": True,
        "stage_order": [
            "correctness",
            "benchmark_xs",
            "benchmark_s",
            "benchmark_m",
            "export",
        ],
    }
    assert [replay["status"] for replay in gate_report["replays"]] == [
        "PASS",
        "PASS",
    ]
    assert gate_report["check_count"] == 11
    assert all(check["status"] == "PASS" for check in gate_report["checks"])


def test_gate_aggregates_seven_scenarios_and_c001_through_c011(
    gate_report: dict[str, Any],
) -> None:
    for replay in gate_report["replays"]:
        correctness = replay["correctness"]
        checks = _checks(correctness)
        rows = checks["formal-ingress-snapshot-problem-replay"]["details"]
        assert [row["scenario_id"] for row in rows] == EXPECTED_SCENARIOS
        assert all(
            row["solver_status"] in {"OPTIMAL", "FEASIBLE"}
            and row["validator_status"] == "PASS"
            and row["hard_violation_count"] == 0
            and row["problem_hash"].startswith("sha256:")
            and row["snapshot_hash"].startswith("sha256:")
            for row in rows
        )
        mutations = checks[
            "formula-free-exact-c001-c011-validator-mutations"
        ]["details"]
        assert [row["constraint_id"] for row in mutations] == EXPECTED_CONSTRAINTS
        assert all(
            row["status"] == "FAIL"
            and row["hard_violation_count"] >= 1
            and row["deterministic_replay"] is True
            for row in mutations
        )
    assert gate_report["counts"]["correctness_scenario_executions"] == 14
    assert gate_report["counts"]["correctness_mutation_executions"] == 22


def test_gate_aggregates_xs_s_m_status_objective_model_timing_memory_and_export(
    gate_report: dict[str, Any],
) -> None:
    for replay in gate_report["replays"]:
        assert set(replay["benchmarks"]) == {"XS", "S", "M"}
        for size, benchmark in replay["benchmarks"].items():
            assert benchmark["benchmark_report_version"] == "benchmark-report.v1"
            assert benchmark["status"] == "PASS"
            assert benchmark["profile"]["size"] == size
            assert benchmark["warnings"] == []
            assert benchmark["baseline"]["status"] == "PASS"
            assert benchmark["problem"]["problem_hash"].startswith("sha256:")
            solver = benchmark["global_solver"]
            assert solver["status"] in {"OPTIMAL", "FEASIBLE"}
            assert solver["validation"]["status"] == "PASS"
            assert solver["validation"]["fresh_formal"] is True
            assert solver["model_metrics"]["variables"] > 0
            assert solver["model_metrics"]["constraints"] > 0
            assert set(solver["quality"]) >= {
                "objective",
                "best_bound",
                "relative_gap",
                "weighted_tardiness_seconds",
            }
            assert set(solver["timings"]) == {
                "model_build_seconds",
                "first_solution_seconds",
                "solve_seconds",
                "validation_seconds",
                "total_seconds",
            }
            assert solver["memory_peak_mb"]["maximum"] >= 0
            assert benchmark["pipeline"]["kpi_version"] == "kpi.v2"
            assert (
                benchmark["pipeline"]["export_package_profile"]
                == "p2-internal-export.v1"
            )
            assert benchmark["pipeline"]["export_file_count"] == 9
            assert benchmark["pipeline"]["export_manifest_fingerprint"].startswith(
                "sha256:"
            )
            assert len(benchmark["reference_schedulers"]) == 5
            assert all(
                reference["status"] == "FEASIBLE"
                and reference["validation"]["status"] == "PASS"
                and reference["deterministic_replay"] is True
                for reference in benchmark["reference_schedulers"]
            )
        output = replay["export"]
        assert output["report_version"] == "p2-output-contract-report.v1"
        assert output["status"] == "PASS"
        assert output["package_profile"] == "p2-internal-export.v1"
        assert output["counts"]["package_files_excluding_manifest"] == 9
    assert gate_report["counts"]["benchmark_profile_executions"] == 6
    assert gate_report["counts"]["benchmark_validator_passes"] == 108
    assert gate_report["counts"]["embedded_benchmark_export_executions"] == 6


def test_gate_semantic_projection_is_stable_but_preserves_run_evidence(
    gate_report: dict[str, Any],
) -> None:
    consistency = gate_report["hash_consistency"]
    assert consistency["projection_version"] == "p2-gate-semantic-projection.v1"
    assert consistency["status"] == "PASS"
    assert consistency["unique_combined_fingerprints"] == 1
    assert len(set(consistency["combined_fingerprints"])) == 1
    for size in ("XS", "S", "M"):
        assert len(set(consistency["benchmark_fingerprints"][size])) == 1
    assert len(set(consistency["correctness_fingerprints"])) == 1
    assert len(set(consistency["export_fingerprints"])) == 1
    assert "FULL_REPORT_EXPORT_KPI_AND_SOLVER_REPORT_HASHES_ARE_COLLECTED" in (
        consistency["run_specific_hash_policy"]
    )
    assert all(
        replay["stage_seconds"]["benchmark_m"] >= 0
        and replay["total_seconds"] >= 0
        for replay in gate_report["replays"]
    )


def test_gate_keeps_exit_p3_and_production_boundaries_closed(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["blocking_gaps"] == []
    assert gate_report["boundaries"] == {
        "current_phase": "P2",
        "data_plane": "SIMULATION_ONLY",
        "gate_kind": "P2_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT",
        "exit_gate_decision": "NOT_PERFORMED",
        "p2_14": "NOT_STARTED",
        "p3": "NOT_STARTED",
        "production_readiness": "NOT_CLAIMED",
        "production_capacity_sla": "NOT_ESTABLISHED_OPEN_011_012",
        "remediation": "NONE_MIXED_INTO_GATE",
        "schema_migration_dependency_adr_changes": "NONE",
    }
    serialized = json.dumps(gate_report, sort_keys=True)
    assert '"exit_gate_decision": "READY"' not in serialized
    assert '"p3": "STARTED"' not in serialized


def test_cli_writes_fail_report_and_returns_nonzero_on_stage_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "failed.json"

    def fail_gate(*, root: Path, repeat: int) -> dict[str, Any]:
        del root, repeat
        raise RuntimeError("bounded synthetic failure")

    monkeypatch.setattr(p2_gate_report, "run_p2_vertical_slice_gate", fail_gate)
    assert (
        p2_gate_report.main(
            [
                "--root",
                str(ROOT),
                "--repeat",
                "2",
                "--report",
                str(report_path),
            ]
        )
        == 1
    )
    failed = json.loads(report_path.read_text(encoding="utf-8"))
    assert failed["status"] == "FAIL"
    assert failed["blocking_gaps"] == [
        {
            "gap_id": "P2-GATE-EXECUTION-001",
            "stage": "orchestrator",
            "status": "BLOCKING",
            "remediation": "REQUIRES_SEPARATE_BOUNDED_TASK",
        }
    ]
    assert failed["boundaries"]["exit_gate_decision"] == "NOT_PERFORMED"
