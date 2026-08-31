"""TASK-P4-14 complete dynamic-replanning vertical-slice Gate evidence."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from app.application.p2_gate_report import run_p2_vertical_slice_gate
from app.application.p3_gate_report import run_p3_vertical_slice_gate
from app.application.p4_gate_report import (
    DIFF_BASE,
    P4_TEST_IDS,
    _code_commit,
    run_p4_vertical_slice_gate,
    validate_p4_vertical_slice_report,
)


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_STAGES = [
    "machine_contracts",
    "replan_persistence",
    "execution_fact_projection",
    "freeze_window",
    "stability_change_report",
    "replan_solver",
    "replan_application",
    "execution_simulator",
    "disruption_replay",
    "change_report_output",
    "replanning_api",
]


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _p3_frontend_report() -> dict[str, Any]:
    code_commit = _code_commit()
    projection = {
        "projection_version": "p3-playwright-semantic-projection.v1",
        "project_name": "chromium-p3-human-control",
        "spec_count": 12,
        "human_control_spec_count": 8,
        "specs": [{"file": "human-control-actions.spec.ts", "ok": True}],
    }
    semantic_fingerprint = _fingerprint(projection)
    raw = {
        kind: {
            "path": f"build/playwright/p3-gate/results.{suffix}",
            "sha256": f"sha256:{digit * 64}",
        }
        for kind, suffix, digit in (
            ("json", "json", "1"),
            ("junit", "xml", "2"),
            ("html", "html", "3"),
        )
    }
    replays = [
        {
            "replay_index": index,
            "status": "PASS",
            "project_name": "chromium-p3-human-control",
            "spec_count": 12,
            "human_control_spec_count": 8,
            "raw_evidence": deepcopy(raw),
            "semantic_projection": deepcopy(projection),
            "semantic_fingerprint": semantic_fingerprint,
        }
        for index in (1, 2)
    ]
    identities = (
        "frozen-human-control-report",
        "two-complete-chromium-replays",
        "json-junit-html-and-failure-retention",
        "stable-browser-semantic-projection",
        "phase-boundary",
    )
    return {
        "report_version": "p3-frontend-gate-report.v1",
        "task_id": "TASK-P3-14",
        "code_commit": code_commit,
        "diff_base": "6a3e02f00bf46f19915cb59c3c4af7daaac95be4",
        "status": "PASS",
        "repeat_count": 2,
        "playwright_contract_version": "p3-playwright-semantic-projection.v1",
        "human_control_report": {
            "path": "build/validation/ci-p3-frontend.json",
            "sha256": f"sha256:{'4' * 64}",
            "report_version": "p3-frontend-human-control-report.v1",
            "task_id": "TASK-P3-13",
            "code_commit": code_commit,
            "diff_base": "3dacf83c0f0bf87a9fa673aa75d61f8ad8659386",
            "status": "PASS",
            "browser_spec_count": 12,
            "human_control_browser_spec_count": 8,
        },
        "replays": replays,
        "hash_consistency": {
            "projection_version": "p3-playwright-semantic-projection.v1",
            "status": "PASS",
            "semantic_fingerprints": [semantic_fingerprint, semantic_fingerprint],
            "unique_semantic_fingerprints": 1,
            "raw_runtime_fields_excluded": ["duration"],
        },
        "checks": [
            {"id": identity, "status": "PASS", "detail": "test fixture"}
            for identity in identities
        ],
        "check_count": len(identities),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": {
            "browser_runtime": "CHROMIUM",
            "data_plane": "SIMULATION_ONLY",
            "mock_transport": True,
            "failure_media_policy": "RETAIN_ON_FAILURE",
            "p3_15_exit_gate_audit": "NOT_PERFORMED",
            "p4": "NOT_STARTED",
            "production_authority": "NOT_FORMED",
            "production_readiness": "NOT_CLAIMED",
        },
    }


def _p4_frontend_report() -> dict[str, Any]:
    code_commit = _code_commit()
    projection = {
        "projection_version": "p4-playwright-semantic-projection.v1",
        "project_name": "chromium-p4-vertical-slice",
        "spec_count": 5,
        "dynamic_replanning_spec_count": 5,
        "specs": [{"file": "dynamic-replanning.spec.ts", "ok": True}],
    }
    semantic_fingerprint = _fingerprint(projection)
    raw = {
        kind: {
            "path": f"build/playwright/p4-gate/results.{suffix}",
            "sha256": f"sha256:{digit * 64}",
        }
        for kind, suffix, digit in (
            ("json", "json", "5"),
            ("junit", "xml", "6"),
            ("html", "html", "7"),
        )
    }
    replays = [
        {
            "replay_index": index,
            "status": "PASS",
            "project_name": "chromium-p4-vertical-slice",
            "spec_count": 5,
            "dynamic_replanning_spec_count": 5,
            "raw_evidence": deepcopy(raw),
            "semantic_projection": deepcopy(projection),
            "semantic_fingerprint": semantic_fingerprint,
        }
        for index in (1, 2)
    ]
    identities = (
        "frozen-p4-replanning-frontend-report",
        "two-complete-p4-chromium-replays",
        "json-junit-html-and-failure-retention",
        "stable-p4-browser-semantic-projection",
        "p4-gate-phase-boundary",
    )
    return {
        "report_version": "p4-frontend-gate-report.v1",
        "task_id": "TASK-P4-14",
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "status": "PASS",
        "repeat_count": 2,
        "playwright_contract_version": "p4-playwright-semantic-projection.v1",
        "replanning_report": {
            "path": "build/validation/ci-p4-replanning-frontend.json",
            "sha256": f"sha256:{'8' * 64}",
            "report_version": "p4-replanning-frontend-report.v1",
            "task_id": "TASK-P4-13",
            "code_commit": code_commit,
            "diff_base": "be2389594f3e224de3f5a73f4b8b62ffcffb5b7b",
            "status": "PASS",
            "check_count": 8,
            "p4_browser_specs": 5,
        },
        "replays": replays,
        "hash_consistency": {
            "projection_version": "p4-playwright-semantic-projection.v1",
            "status": "PASS",
            "semantic_fingerprints": [semantic_fingerprint, semantic_fingerprint],
            "unique_semantic_fingerprints": 1,
            "raw_runtime_fields_excluded": ["duration"],
        },
        "checks": [
            {"id": identity, "status": "PASS", "detail": "test fixture"}
            for identity in identities
        ],
        "check_count": len(identities),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": {
            "browser_runtime": "CHROMIUM",
            "data_plane": "SIMULATION_ONLY",
            "mock_transport": True,
            "failure_media_policy": "RETAIN_ON_FAILURE",
            "p4_exit_gate_audit": "NOT_PERFORMED",
            "p4_15": "NOT_STARTED",
            "p5": "UNSUPPORTED",
            "production_authority": "NOT_FORMED",
            "production_readiness": "NOT_CLAIMED",
        },
    }


@pytest.fixture(scope="module")
def gate_report() -> dict[str, Any]:
    p2 = run_p2_vertical_slice_gate(root=ROOT, repeat=2)
    p3 = run_p3_vertical_slice_gate(
        root=ROOT,
        frontend_report=_p3_frontend_report(),
        p2_report=p2,
        repeat=2,
    )
    report = run_p4_vertical_slice_gate(
        root=ROOT,
        frontend_report=_p4_frontend_report(),
        p2_report=p2,
        p3_report=p3,
        repeat=2,
    )
    validate_p4_vertical_slice_report(report)
    return report


def test_gate_runs_two_complete_backend_browser_and_regression_replays(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["report_version"] == "p4-vertical-slice-report.v1"
    assert gate_report["status"] == "PASS"
    assert gate_report["task_id"] == "TASK-P4-14"
    assert gate_report["diff_base"] == DIFF_BASE
    assert gate_report["execution"] == {
        "minimum_repeat_count": 2,
        "backend_full_replays_complete": 2,
        "frontend_full_replays_complete": 2,
        "all_public_p4_backend_boundaries_reexecuted": True,
        "stage_order": EXPECTED_STAGES,
    }
    assert gate_report["counts"]["backend_stage_executions"] == 22
    assert gate_report["counts"]["backend_subreport_checks"] == 176
    assert gate_report["counts"]["browser_spec_executions"] == 10
    assert gate_report["regressions"]["p2"]["status"] == "PASS"
    assert gate_report["regressions"]["p3"]["status"] == "PASS"


def test_gate_retains_all_raw_owner_reports_and_continuous_disruption_evidence(
    gate_report: dict[str, Any],
) -> None:
    for replay in gate_report["backend_replays"]:
        assert replay["stage_order"] == EXPECTED_STAGES
        reports = replay["raw_subreports"]
        assert list(reports) == EXPECTED_STAGES
        assert all(report["status"] == "PASS" for report in reports.values())
        assert reports["disruption_replay"]["counts"]["scenario_steps"] == 5
        assert reports["disruption_replay"]["counts"]["standard_events"] == 8
        assert reports["disruption_replay"]["counts"]["fresh_validator_passes"] == 5
        assert reports["disruption_replay"]["counts"]["complete_change_reports"] == 5
    assert gate_report["counts"]["continuous_scenario_step_executions"] == 10
    assert gate_report["counts"]["standard_event_executions"] == 16
    assert gate_report["counts"]["fresh_validator_passes"] == 10
    assert gate_report["counts"]["complete_change_reports"] == 10


def test_gate_preserves_semantic_consistency_and_exact_negative_boundaries(
    gate_report: dict[str, Any],
) -> None:
    consistency = gate_report["semantic_consistency"]
    assert consistency["status"] == "PASS"
    assert consistency["projection_version"] == "p4-gate-semantic-projection.v1"
    assert consistency["unique_combined_fingerprints"] == 1
    assert len(set(consistency["combined_fingerprints"])) == 1
    assert [row["case_id"] for row in gate_report["rejection_cases"]] == [
        "TAMPER_COVERAGE_AND_PLANE_FAIL_CLOSED",
        "PRODUCTION_AUTHORITY_DEFAULT_DENY",
        "P5_CAPABILITY_UNSUPPORTED",
        "PARTIAL_RESULT_CANNOT_ADVANCE_STATE",
    ]
    assert all(row["status"] == "PASS" for row in gate_report["rejection_cases"])


def test_gate_registers_every_p4_test_and_provider_input(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["test_ids"] == list(P4_TEST_IDS)
    assert len(gate_report["frozen_inputs"]["predecessor_closure_commits"]) == 13
    assert gate_report["frozen_inputs"]["activation_provider_audit"] == "PASS"
    assert gate_report["frontend_evidence"]["repeat_count"] == 2
    assert gate_report["check_count"] == 14
    assert all(check["status"] == "PASS" for check in gate_report["checks"])


def test_gate_is_non_exit_non_p5_non_production(gate_report: dict[str, Any]) -> None:
    assert gate_report["blocking_gaps"] == []
    assert gate_report["boundaries"] == {
        "current_phase": "P4",
        "data_plane": "SIMULATION_ONLY",
        "gate_kind": "P4_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT",
        "exit_gate_audit": "NOT_PERFORMED",
        "p4_15": "NOT_STARTED",
        "p5_plus": "UNSUPPORTED",
        "production_identity_and_authority": "NOT_FORMED",
        "production_readiness": "NOT_CLAIMED",
        "external_publish_or_transfer": "NONE",
        "capacity_and_sla": "NOT_ESTABLISHED",
        "remediation": "NONE_MIXED_INTO_GATE",
        "schema_migration_dependency_adr_changes": "NONE",
    }
