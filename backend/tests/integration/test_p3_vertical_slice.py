"""TASK-P3-14 complete Planning Workspace vertical-slice Gate evidence."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from app.application.p2_gate_report import run_p2_vertical_slice_gate
from app.application.p3_gate_report import (
    DIFF_BASE,
    _stage_semantic_projection,
    run_p3_vertical_slice_gate,
    validate_p3_vertical_slice_report,
)


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_STAGES = [
    "workspace_contracts",
    "persistence",
    "schedule_version_lifecycle",
    "workspace_read_models",
    "schedule_commands",
    "approval_decisions",
    "publication",
    "export_jobs",
    "planning_workspace_api",
]


def _frontend_report() -> dict[str, Any]:
    projection = {
        "projection_version": "p3-playwright-semantic-projection.v1",
        "project_name": "chromium-p3-human-control",
        "spec_count": 12,
        "human_control_spec_count": 8,
        "specs": [{"file": "human-control-actions.spec.ts", "ok": True}],
    }
    fingerprint = (
        "sha256:"
        + sha256(
            json.dumps(
                projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
    )
    raw = {
        "json": {
            "path": "build/playwright/p3-gate/results.json",
            "sha256": f"sha256:{'1' * 64}",
        },
        "junit": {
            "path": "build/playwright/p3-gate/results.xml",
            "sha256": f"sha256:{'2' * 64}",
        },
        "html": {
            "path": "build/playwright/p3-gate/html/index.html",
            "sha256": f"sha256:{'3' * 64}",
        },
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
            "semantic_fingerprint": fingerprint,
        }
        for index in (1, 2)
    ]
    checks = [
        {"id": identity, "status": "PASS", "detail": "test fixture"}
        for identity in (
            "frozen-human-control-report",
            "two-complete-chromium-replays",
            "json-junit-html-and-failure-retention",
            "stable-browser-semantic-projection",
            "phase-boundary",
        )
    ]
    return {
        "report_version": "p3-frontend-gate-report.v1",
        "task_id": "TASK-P3-14",
        "code_commit": "uncommitted",
        "diff_base": DIFF_BASE,
        "status": "PASS",
        "repeat_count": 2,
        "playwright_contract_version": "p3-playwright-semantic-projection.v1",
        "human_control_report": {
            "path": "build/validation/TASK-P3-14-frontend.json",
            "sha256": f"sha256:{'4' * 64}",
            "report_version": "p3-frontend-human-control-report.v1",
            "task_id": "TASK-P3-13",
            "code_commit": "uncommitted",
            "diff_base": "3dacf83c0f0bf87a9fa673aa75d61f8ad8659386",
            "status": "PASS",
            "browser_spec_count": 12,
            "human_control_browser_spec_count": 8,
        },
        "replays": replays,
        "hash_consistency": {
            "projection_version": "p3-playwright-semantic-projection.v1",
            "status": "PASS",
            "semantic_fingerprints": [fingerprint, fingerprint],
            "unique_semantic_fingerprints": 1,
            "raw_runtime_fields_excluded": ["duration"],
        },
        "checks": checks,
        "check_count": len(checks),
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


@pytest.fixture(scope="module")
def gate_report() -> dict[str, Any]:
    p2 = run_p2_vertical_slice_gate(root=ROOT, repeat=2)
    report = run_p3_vertical_slice_gate(
        root=ROOT,
        frontend_report=_frontend_report(),
        p2_report=p2,
        repeat=2,
    )
    validate_p3_vertical_slice_report(report)
    return report


def test_gate_runs_two_complete_public_backend_and_browser_replays(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["report_version"] == "p3-vertical-slice-report.v1"
    assert gate_report["status"] == "PASS"
    assert gate_report["task_id"] == "TASK-P3-14"
    assert gate_report["diff_base"] == DIFF_BASE
    assert gate_report["repeat_count"] == 2
    assert gate_report["execution"] == {
        "minimum_repeat_count": 2,
        "backend_full_replays_complete": 2,
        "frontend_full_replays_complete": 2,
        "all_public_backend_boundaries_reexecuted": True,
        "stage_order": EXPECTED_STAGES,
    }
    assert [replay["stage_order"] for replay in gate_report["backend_replays"]] == [
        EXPECTED_STAGES,
        EXPECTED_STAGES,
    ]
    assert gate_report["counts"]["backend_stage_executions"] == 18
    assert gate_report["counts"]["browser_spec_executions"] == 24


def test_gate_retains_every_raw_subreport_and_business_chain(
    gate_report: dict[str, Any],
) -> None:
    for replay in gate_report["backend_replays"]:
        reports = replay["raw_subreports"]
        assert list(reports) == EXPECTED_STAGES
        assert all(report["status"] == "PASS" for report in reports.values())
        assert all(report["check_count"] == 8 for report in reports.values())
        assert (
            reports["schedule_version_lifecycle"]["counts"][
                "fresh_validation_and_kpi_gate"
            ]
            == 1
        )
        assert reports["schedule_commands"]["counts"]["fresh_validator_passes"] == 5
        assert reports["approval_decisions"]["counts"]["decision_types"] == 2
        assert reports["publication"]["boundaries"]["source_state"] == "APPROVED_ONLY"
        assert reports["export_jobs"]["counts"]["package_payloads"] == 12
        assert reports["planning_workspace_api"]["counts"]["http_operations"] == 18


def test_gate_stable_projection_excludes_only_runtime_noise_and_keeps_raw(
    gate_report: dict[str, Any],
) -> None:
    first, second = gate_report["backend_replays"]
    assert first["stage_microseconds"] != {}
    assert second["stage_microseconds"] != {}
    approval_observations = first["raw_subreports"]["approval_decisions"][
        "observations"
    ]
    assert approval_observations["elapsed_microseconds"] >= 0
    consistency = gate_report["semantic_consistency"]
    assert consistency["projection_version"] == "p3-gate-semantic-projection.v1"
    assert consistency["status"] == "PASS"
    assert consistency["unique_combined_fingerprints"] == 1
    assert len(set(consistency["combined_fingerprints"])) == 1
    assert "elapsed_microseconds" in consistency["excluded_runtime_noise_keys"]
    assert consistency["normalized_concurrency_outcomes"] == {
        "winner": ["APPROVE", "REJECT"],
        "loser_failure": ["INVALID_STATE_TRANSITION", "STALE_SOURCE"],
    }
    assert (
        "ALL_SUBREPORTS_AND_RUNTIME_OBSERVATIONS_RETAINED"
        in consistency["raw_evidence_policy"]
    )

    approval = first["raw_subreports"]["approval_decisions"]
    alternate = deepcopy(approval)
    concurrency = next(
        check
        for check in alternate["checks"]
        if check["check_id"] == "concurrent-decision-single-cas-winner"
    )["evidence"]
    concurrency["winner"] = (
        "REJECT" if concurrency["winner"] == "APPROVE" else "APPROVE"
    )
    concurrency["loser_failure"] = (
        "INVALID_STATE_TRANSITION"
        if concurrency["loser_failure"] == "STALE_SOURCE"
        else "STALE_SOURCE"
    )
    assert _stage_semantic_projection(
        "approval_decisions", approval
    ) == _stage_semantic_projection("approval_decisions", alternate)


def test_gate_aggregates_p2_negative_frontend_and_provider_inputs(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["p2_regression"]["status"] == "PASS"
    assert gate_report["p2_regression"]["repeat_count"] == 2
    assert gate_report["p2_regression"]["blocking_gaps"] == []
    assert gate_report["frontend_evidence"]["repeat_count"] == 2
    assert (
        gate_report["frontend_evidence"]["hash_consistency"][
            "unique_semantic_fingerprints"
        ]
        == 1
    )
    assert gate_report["frozen_inputs"]["activation_provider_audit"] == "PASS"
    assert len(gate_report["frozen_inputs"]["predecessor_closure_commits"]) == 13
    assert [row["case_id"] for row in gate_report["rejection_cases"]] == [
        "DRAFT_CANNOT_PUBLISH",
        "REJECTED_CANNOT_PUBLISH",
        "PUBLISHED_CONTENT_CANNOT_MUTATE",
        "UNPUBLISHED_VERSION_CANNOT_EXPORT",
    ]
    assert all(row["status"] == "PASS" for row in gate_report["rejection_cases"])


def test_gate_remains_non_exit_non_p4_and_non_production(
    gate_report: dict[str, Any],
) -> None:
    assert gate_report["blocking_gaps"] == []
    assert gate_report["boundaries"] == {
        "current_phase": "P3",
        "data_plane": "SIMULATION_ONLY",
        "gate_kind": "P3_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT",
        "exit_gate_audit": "NOT_PERFORMED",
        "p3_15": "NOT_STARTED",
        "p4": "NOT_STARTED",
        "production_identity_and_authority": "NOT_FORMED",
        "production_readiness": "NOT_CLAIMED",
        "external_publish_or_transfer": "NONE",
        "remediation": "NONE_MIXED_INTO_GATE",
        "schema_migration_dependency_adr_changes": "NONE",
    }
    assert gate_report["check_count"] == 14
    assert all(check["status"] == "PASS" for check in gate_report["checks"])
