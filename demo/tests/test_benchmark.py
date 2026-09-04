from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import cast

from plantnexus_demo.assets import load_demo_assets
from plantnexus_demo.benchmark import run_benchmark
from plantnexus_demo.formal_benchmark import (
    FORMAL_SAMPLE_VERSION,
    attach_rss_measurement,
    distribution,
    fingerprint,
    load_formal_protocol,
    nearest_rank,
    showcase_thresholds,
    summarize_profile,
)


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


def test_formal_protocol_freezes_v2_profiles_and_fixture() -> None:
    protocol = load_formal_protocol()
    assets = load_demo_assets()

    assert protocol.document["profile_set_version"] == "cnc-demo-benchmark-profiles.v2"
    assert protocol.document["default_profile"] == "showcase"
    assert protocol.measured_count == 5
    assert assets.profile("smoke").replan_solve_seconds == 10
    assert assets.profile("showcase").initial_solve_seconds == 20
    assert assets.profile("showcase").replan_solve_seconds == 30
    assert assets.profile("upper").initial_solve_seconds == 60
    assert assets.profile("upper").replan_solve_seconds == 90
    assert protocol.urgent_fixture["route_template_id"] == "CNC-ROUTE-5"
    assert protocol.urgent_fixture["quantity"] == 5
    assert protocol.document["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "synthetic_only": True,
        "production_capacity_claim": "NOT_ESTABLISHED",
        "production_sla_claim": "NOT_ESTABLISHED",
        "first_feasible_metric": "NOT_REPORTED_NO_RELIABLE_CALLBACK",
    }


def test_nearest_rank_and_distribution_are_recomputable_for_five_samples() -> None:
    values = [3.0, 1.0, 5.0, 2.0, 4.0]

    assert nearest_rank(values, 0.95) == 5.0
    assert distribution(values) == {
        "raw": values,
        "count": 5,
        "p50": 3.0,
        "p95": 5.0,
        "max": 5.0,
        "percentile_method": "nearest-rank",
    }


def _sample(role: str, sequence: int, value: float = 1.0) -> dict[str, object]:
    sample: dict[str, object] = {
        "sample_version": FORMAL_SAMPLE_VERSION,
        "sample_id": f"showcase-{role}-{sequence:02d}",
        "role": role,
        "sequence": sequence,
        "status": "PASS",
        "b1_data_import": {
            "end_to_end_seconds": value,
            "dataset_hash": "sha256:dataset",
            "snapshot_hash": "sha256:snapshot",
            "problem_hash": "sha256:problem",
            "assets_digest": "sha256:assets",
        },
        "b2_initial_plan": {
            "end_to_end_seconds": value,
            "non_solving_stages_seconds": value,
            "solver": {
                "solver_status": "OPTIMAL",
                "candidate_fingerprint": "sha256:initial",
                "timings": {
                    "solve_seconds": value,
                    "validation_seconds": value,
                },
            },
        },
        "b3_baseline_activation": {"end_to_end_seconds": value},
        "b4_urgent_replan": {
            "end_to_end_seconds": value,
            "non_solving_stages_seconds": value,
            "solver": {
                "solver_status": "FEASIBLE",
                "candidate_fingerprint": f"sha256:replan-{sequence}",
                "timings": {
                    "solve_seconds": value,
                    "validation_seconds": value,
                },
            },
        },
        "b5_presentation": {
            "max_api_seconds": value,
            "max_job_state_api_seconds": value,
        },
        "b6_reset_recovery": {"failure_probe_seconds": value},
        "resources": {
            "backend_peak_rss_bytes": 100,
            "sqlite_database_bytes": 200,
            "artifact_canonical_json_bytes": 300,
        },
        "overall_wall_seconds": value,
        "assertions": {
            "initial_candidate_validator_pass": True,
            "replan_candidate_validator_pass": True,
            "change_report_and_preservation_pass": True,
            "presentation_contract_pass": True,
            "reset_failure_preserves_active": True,
        },
    }
    sample["sample_fingerprint"] = fingerprint(sample)
    return sample


def test_formal_summary_excludes_warmup_and_evaluates_frozen_thresholds() -> None:
    samples = [_sample("preflight", 1, 99), _sample("warmup", 1, 99)] + [
        _sample("measured", index, float(index)) for index in range(1, 6)
    ]

    summary = summarize_profile("showcase", samples)
    thresholds = showcase_thresholds(summary, load_formal_protocol())
    distributions = cast(Mapping[str, object], summary["distributions"])
    initial_e2e = cast(
        Mapping[str, object], distributions["initial_end_to_end_seconds"]
    )
    checks = cast(Mapping[str, object], thresholds["checks"])
    job_state_check = cast(Mapping[str, object], checks["job_state_api_p95"])

    assert summary["status"] == "PASS"
    assert initial_e2e["raw"] == [
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
    ]
    assert initial_e2e["p95"] == 5.0
    assert thresholds["status"] == "FAIL"
    assert job_state_check["status"] == "FAIL"


def test_parent_rss_attachment_replaces_pending_measurement_and_refingerprints() -> None:
    pending = _sample("measured", 1)
    resources = deepcopy(cast(dict[str, object], pending["resources"]))
    resources["backend_peak_rss_bytes"] = None
    resources["backend_peak_rss_method"] = "PARENT_PROCESS_SAMPLER_PENDING"
    pending["resources"] = resources
    pending["sample_fingerprint"] = fingerprint(
        {key: value for key, value in pending.items() if key != "sample_fingerprint"}
    )

    measured = attach_rss_measurement(
        pending,
        peak_rss_bytes=123456,
        samples=42,
        interval_seconds=0.02,
        method="WINDOWS_WORKING_SET_20MS_PARENT_SAMPLER",
    )

    measured_resources = cast(Mapping[str, object], measured["resources"])
    assert measured_resources["backend_peak_rss_bytes"] == 123456
    assert measured_resources["rss_sample_count"] == 42
    original = measured.pop("sample_fingerprint")
    assert original == fingerprint(measured)
