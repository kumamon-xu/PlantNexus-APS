"""TEST-DISRUPTION-REPLAY-001 five-step common-path machine evidence."""

from __future__ import annotations

from pathlib import Path

from app.simulation.scenarios.disruption_replay_check import (
    run_disruption_replay_checks,
)


ROOT = Path(__file__).resolve().parents[3]


def test_five_disruptions_form_one_continuous_replay_with_complete_evidence() -> None:
    report = run_disruption_replay_checks(ROOT, verify_owner_reports=False)

    assert report["report_version"] == "p4-disruption-replay-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-10"
    assert report["diff_base"] == "8bbe0c643571e578ec637f135a2390c90de02512"
    assert report["impact_rules"] == [
        "IMPACT-DOCS",
        "IMPACT-FIXTURE",
        "IMPACT-INFRA",
        "IMPACT-SIM-SCENARIO",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "scenario_steps": 5,
        "standard_events": 8,
        "continuous_replan_envelopes": 5,
        "fresh_validator_passes": 5,
        "complete_change_reports": 5,
        "same_seed_runs": 2,
        "negative_vectors": 3,
        "machine_checks": 8,
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "baseline_advance": "SIMULATION_NON_PRODUCTION",
        "automatic_approval_publication_export": "NONE",
        "p4_11_plus": "NOT_STARTED",
        "p5_plus": "UNSUPPORTED",
        "production_readiness_authority_external_capacity_sla": "NOT_ESTABLISHED",
    }
