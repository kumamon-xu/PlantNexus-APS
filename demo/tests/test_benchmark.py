from __future__ import annotations

from plantnexus_demo.benchmark import run_benchmark


def test_smoke_benchmark_exposes_only_validator_backed_solver_result() -> None:
    report = run_benchmark("smoke", solve_seconds=2.0)

    assert report["status"] == "PASS"
    assert report["boundaries"]["synthetic_only"] is True
    assert report["boundaries"]["production_capacity_claim"] == "NOT_ESTABLISHED"
    assert report["solver"]["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert report["solver"]["validator"]["status"] == "PASS"
    assert report["solver"]["result_classification"] in {
        "OPTIMAL_FOR_THIS_SYNTHETIC_INSTANCE",
        "VALIDATOR_VERIFIED_FEASIBLE",
    }
    assert report["standard_ingress"]["problem_counts"]["active_operations"] == 102
    assert report["report_fingerprint"].startswith("sha256:")
