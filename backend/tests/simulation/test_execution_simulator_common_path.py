"""TEST-SIM-ISOLATION P4-09 public-common-path machine evidence."""

from __future__ import annotations

from pathlib import Path

from app.simulation.execution.simulator_check import run_execution_simulator_checks


ROOT = Path(__file__).resolve().parents[3]


def test_execution_simulator_machine_evidence_is_complete_and_isolated() -> None:
    report = run_execution_simulator_checks(ROOT)

    assert report["report_version"] == "p4-execution-simulator-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-09"
    assert report["diff_base"] == "e4874735166be93473ccaebaf1090980db957552"
    assert report["impact_rules"] == [
        "IMPACT-DOCS",
        "IMPACT-INFRA",
        "IMPACT-SIM-EXECUTION",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "scheduled_events": 3,
        "same_offset_events": 2,
        "event_types": 3,
        "same_input_full_runs": 2,
        "checkpoint_batches": 2,
        "public_ingress_calls": 6,
        "frozen_boundary_files": 8,
        "machine_checks": 8,
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "time_source": "VERSIONED_VIRTUAL_CLOCK_ONLY",
        "event_output": "STANDARD_EXECUTION_EVENT_V1_ONLY",
        "common_ingress": (
            "P4_04_EXECUTION_FACT_PROJECTION_SERVICE_INGEST_EVENT"
        ),
        "database_solver_replan_schedule_write": "NONE_IN_SIMULATOR_CORE",
        "fact_checkpoint": "EXPLICIT_CALLER_SUPPLIED_REFERENCE_ONLY",
        "five_disruption_continuous_replay": "P4_10_NOT_IMPLEMENTED",
        "business_state_transition": "NONE",
        "p5_plus": "EXPLICITLY_REJECTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
