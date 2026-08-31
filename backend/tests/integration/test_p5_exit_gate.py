"""TASK-P5-22 independent P5 Exit audit integration contract."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from app.application import p5_exit_gate_audit as audit
from app.application.p5_exit_gate_audit import (
    DIFF_BASE,
    IMPACT_RULES,
    P5ExitGateAuditError,
    REPORT_VERSION,
    TEST_IDS,
    run_p5_exit_gate_audit,
    validate_p5_exit_gate_report,
)


ROOT = Path(__file__).resolve().parents[3]


def _observation() -> dict[str, Any]:
    return json.loads(
        (ROOT / "docs/p5-exit-gate-audit-observations.v1.json").read_text(
            encoding="utf-8"
        )
    )


def _qualification(code_commit: str) -> dict[str, Any]:
    return {
        "report_version": "p5-capability-qualification-report.v1",
        "status": "PASS",
        "task_id": "TASK-P5-01",
        "code_commit": code_commit,
        "diff_base": "4ccb2ed99ffe73abeb0462efff4a5342cd7c5522",
        "validation_profile": "HIGH_RISK",
        "semantic_projection_fingerprint": audit.P5_QUALIFICATION_FINGERPRINT,
        "check_count": 11,
        "checks": [{"status": "PASS"} for _ in range(11)],
        "issues": [],
        "blocking_issues": [],
        "decisions": [
            {"candidate_id": candidate, "decision": "DEFERRED"}
            for candidate in audit._P5_CANDIDATES
        ],
        "portfolio": {
            "selected": [],
            "deferred": list(audit._P5_CANDIDATES),
            "selected_count": 0,
            "deferred_count": 9,
            "p5_02_authorized": False,
        },
        "benchmark_observations": [
            {
                "status": "PASS",
                "profile": {"size": profile},
                "quality": {"validation": {"status": "PASS"}},
                "boundaries": {
                    "production_capacity_sla": "NOT_ESTABLISHED_OPEN_012"
                },
            }
            for profile in ("XS", "S", "M")
        ],
    }


def _p4(code_commit: str) -> dict[str, Any]:
    semantic = {
        "combined_fingerprints": ["sha256:" + "1" * 64] * 2,
        "stage_fingerprints": {"frozen": ["sha256:" + "2" * 64] * 2},
    }
    return {
        "report_version": "p4-vertical-slice-report.v1",
        "status": "PASS",
        "task_id": "TASK-P4-14",
        "code_commit": code_commit,
        "repeat_count": 2,
        "check_count": 14,
        "blocking_gaps": [],
        "counts": {
            "continuous_scenario_step_executions": 10,
            "standard_event_executions": 16,
            "fresh_validator_passes": 10,
            "complete_change_reports": 10,
        },
        "semantic_consistency": semantic,
    }


def _p5(code_commit: str, p4: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_version": "p5-portfolio-gate-report.v1",
        "status": "PASS",
        "task_id": "TASK-P5-21",
        "code_commit": code_commit,
        "check_count": 12,
        "issues": [],
        "blocking_gaps": [],
        "portfolio": {
            "selected": [],
            "selected_count": 0,
            "deferred_count": 9,
            "cancelled_task_count": 18,
        },
        "selected_owner_evidence_manifest": {
            "owner_report_count": 0,
            "owner_reports": [],
            "unselected_owner_invocations": [],
            "cancelled_tasks": list(audit._CANCELLED_TASKS),
        },
        "unsupported_rejections": [
            {
                "constraint_id": constraint,
                "error_code": "UNSUPPORTED_CAPABILITY",
            }
            for constraint in audit._UNSUPPORTED_CONSTRAINTS
        ],
        "p4_regression_evidence": deepcopy(p4),
    }


@pytest.fixture()
def report(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    code_commit = audit._code_commit(ROOT)
    p4 = _p4(code_commit)
    p5 = _p5(code_commit, p4)
    monkeypatch.setattr(audit, "validate_p5_portfolio_gate_report", lambda _: None)
    monkeypatch.setattr(audit, "validate_p4_vertical_slice_report", lambda _: None)
    value = run_p5_exit_gate_audit(
        root=ROOT,
        provider_observation=_observation(),
        qualification_report=_qualification(code_commit),
        p5_gate_report=p5,
        p4_gate_report=p4,
        p4_exit_observation=json.loads(
            (ROOT / "docs/p4-exit-gate-audit-observations.v1.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    validate_p5_exit_gate_report(value)
    return value


def test_exit_report_binds_task_base_profile_checks_and_zero_gaps(
    report: dict[str, Any],
) -> None:
    assert report["manifest_version"] == REPORT_VERSION
    assert report["audit_task"] == "TASK-P5-22"
    assert report["diff_base"] == DIFF_BASE
    assert report["validation_profile"] == "PHASE_GATE"
    assert report["decision"] == "READY"
    assert report["impact_rules"] == list(IMPACT_RULES)
    assert report["test_ids"] == list(TEST_IDS)
    assert report["check_count"] == 15
    assert all(check["status"] == "PASS" for check in report["checks"])
    assert report["issues"] == []
    assert report["blocking_gaps"] == []


def test_exit_report_retains_empty_portfolio_provider_and_frozen_contracts(
    report: dict[str, Any],
) -> None:
    assert report["task_topology"]["selected_count"] == 0
    assert report["task_topology"]["deferred_count"] == 9
    assert len(report["task_topology"]["cancelled"]) == 18
    assert report["predecessor_provider_audit"]["artifact_count"] == 22
    assert report["predecessor_provider_audit"]["digest_mismatch_count"] == 0
    assert report["contracts"]["schema_set_version"] == "2.8.0"
    assert report["contracts"]["formed_strategy"] == "GLOBAL_ONLY"
    assert report["contracts"][
        "advanced_contract_schema_solver_validator_feature_flag_changes"
    ] == []


def test_exit_report_embeds_fresh_qualification_p5_and_p4_replay(
    report: dict[str, Any],
) -> None:
    fresh = report["fresh_evidence"]
    assert fresh["qualification"]["profiles"] == ["XS", "S", "M"]
    assert fresh["qualification"]["selected_count"] == 0
    assert fresh["p5_portfolio_gate"]["check_count"] == 12
    assert fresh["p4_regression"] == {
        **fresh["p4_regression"],
        "status": "PASS",
        "check_count": 14,
        "repeat_count": 2,
        "continuous_scenario_step_executions": 10,
        "standard_event_executions": 16,
        "fresh_validator_passes": 10,
        "complete_change_reports": 10,
    }


def test_exit_ready_does_not_start_p6_or_claim_production(
    report: dict[str, Any],
) -> None:
    assert report["boundaries"]["current_phase"] == "P5"
    assert report["boundaries"]["p5_milestone"] == (
        "ACTIVE_AWAITING_USER_TRANSITION"
    )
    assert report["boundaries"]["p6_plus"] == "NOT_ENTERED"
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"
    assert report["boundaries"]["automatic_phase_transition"] == "PROHIBITED"
    assert report["implementation_provider"] == "PENDING_EXACT_SHA"


def test_independent_p4_semantic_mismatch_is_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code_commit = audit._code_commit(ROOT)
    p4 = _p4(code_commit)
    p5 = _p5(code_commit, p4)
    p5["p4_regression_evidence"]["semantic_consistency"][
        "combined_fingerprints"
    ] = ["sha256:" + "9" * 64] * 2
    monkeypatch.setattr(audit, "validate_p5_portfolio_gate_report", lambda _: None)
    monkeypatch.setattr(audit, "validate_p4_vertical_slice_report", lambda _: None)
    with pytest.raises(P5ExitGateAuditError, match="replays disagree"):
        run_p5_exit_gate_audit(
            root=ROOT,
            provider_observation=_observation(),
            qualification_report=_qualification(code_commit),
            p5_gate_report=p5,
            p4_gate_report=p4,
            p4_exit_observation=json.loads(
                (ROOT / "docs/p4-exit-gate-audit-observations.v1.json").read_text(
                    encoding="utf-8"
                )
            ),
        )


def test_serialized_p4_object_order_is_restored_without_value_change() -> None:
    sorted_stages = {
        stage: {"stage": stage} for stage in sorted(audit._P4_STAGE_ORDER)
    }
    serialized = {
        "backend_replays": [{"raw_subreports": sorted_stages}],
        "preserved": [{"array": [3, 2, 1]}],
    }
    normalized = audit._normalize_p4_serialized_object_order(serialized)

    reports = normalized["backend_replays"][0]["raw_subreports"]
    assert tuple(reports) == audit._P4_STAGE_ORDER
    assert json.dumps(normalized, sort_keys=True) == json.dumps(serialized, sort_keys=True)


def test_serialized_p4_stage_key_drift_fails_closed() -> None:
    stages = {stage: {} for stage in audit._P4_STAGE_ORDER[:-1]}
    with pytest.raises(P5ExitGateAuditError, match="stage key set changed"):
        audit._normalize_p4_serialized_object_order(
            {"backend_replays": [{"raw_subreports": stages}]}
        )
