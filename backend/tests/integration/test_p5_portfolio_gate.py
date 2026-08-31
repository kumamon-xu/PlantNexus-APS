"""TASK-P5-21 empty-selected portfolio Gate integration contract."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.application import p5_portfolio_gate_report as gate
from app.application.p5_portfolio_gate_report import (
    DIFF_BASE,
    IMPACT_RULES,
    P5_TEST_IDS,
    P5PortfolioGateContractError,
    REPORT_VERSION,
    load_portfolio_manifest,
    run_p5_portfolio_gate,
    validate_p5_portfolio_gate_report,
)


ROOT = Path(__file__).resolve().parents[3]


def _strategy() -> dict[str, Any]:
    return {
        "report_version": "objective-strategy-report.v1",
        "task_id": "TASK-P2-08",
        "status": "PASS",
        "code_commit": "uncommitted",
        "check_count": 7,
        "boundaries": {
            "strategy": "ONE_GLOBAL_CP_SAT_MODEL_NO_DECOMPOSITION_OR_FALLBACK",
            "formal_validator_changes": "NONE",
        },
    }


def _formal() -> dict[str, Any]:
    return {
        "report_version": "formal-schedule-validator-report.v1",
        "task_id": "TASK-P2-04",
        "status": "PASS",
        "code_commit": "uncommitted",
        "check_count": 6,
    }


def _mutation() -> dict[str, Any]:
    return {
        "schema_version": "validator-mutation-report.v1",
        "result": "PASS",
        "counts": {"cases": 13, "constraints_covered": 11},
        "test_ids": ["TEST-VALIDATOR-MUTATION"],
        "issues": [],
    }


def _benchmark(profile: str) -> dict[str, Any]:
    return {
        "status": "PASS",
        "code_commit": "uncommitted",
        "profile": {"size": profile.upper()},
        "global_solver": {"validation": {"status": "PASS"}},
    }


def _p4() -> dict[str, Any]:
    return {
        "report_version": "p4-vertical-slice-report.v1",
        "code_commit": "uncommitted",
        "repeat_count": 2,
        "counts": {
            "continuous_scenario_step_executions": 10,
            "standard_event_executions": 16,
            "fresh_validator_passes": 10,
            "complete_change_reports": 10,
        },
    }


@pytest.fixture()
def report(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    manifest, document_sha256 = load_portfolio_manifest(
        ROOT / "docs/core/p5-portfolio-amendment-manifest.md"
    )

    def owner_machine_contract(*, stage: str, **_: object) -> dict[str, Any]:
        return {
            "global_strategy": _strategy(),
            "formal_validator": _formal(),
            "validator_mutation": _mutation(),
        }[stage]

    monkeypatch.setattr(gate, "_run_owner_machine_contract", owner_machine_contract)
    monkeypatch.setattr(
        gate,
        "run_benchmark",
        lambda *, profile_name, **_: _benchmark(profile_name),
    )
    monkeypatch.setattr(gate, "validate_benchmark_report", lambda _: None)
    monkeypatch.setattr(gate, "run_p4_vertical_slice_gate", lambda **_: _p4())
    monkeypatch.setattr(gate, "validate_p4_vertical_slice_report", lambda _: None)
    value = run_p5_portfolio_gate(
        root=ROOT,
        portfolio_manifest=manifest,
        portfolio_document_sha256=document_sha256,
        frontend_report={},
        p2_report={},
        p3_report={},
        repeat=2,
    )
    validate_p5_portfolio_gate_report(value)
    return value


def test_gate_binds_task_base_profile_checks_and_zero_gaps(
    report: dict[str, Any],
) -> None:
    assert report["report_version"] == REPORT_VERSION
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P5-21"
    assert report["diff_base"] == DIFF_BASE
    assert report["validation_profile"] == "PHASE_GATE"
    assert report["impact_rules"] == list(IMPACT_RULES)
    assert report["test_ids"] == list(P5_TEST_IDS)
    assert report["check_count"] == 12
    assert all(check["status"] == "PASS" for check in report["checks"])
    assert report["issues"] == []
    assert report["blocking_gaps"] == []


def test_gate_retains_empty_owner_manifest_and_exact_cancelled_topology(
    report: dict[str, Any],
) -> None:
    assert report["portfolio"] == {
        "selected": [],
        "selected_count": 0,
        "deferred_count": 9,
        "cancelled_task_count": 18,
    }
    owners = report["selected_owner_evidence_manifest"]
    assert owners["status"] == "PASS_EMPTY_SELECTED"
    assert owners["owner_reports"] == []
    assert owners["owner_report_count"] == 0
    assert owners["unselected_owner_invocations"] == []
    assert len(owners["cancelled_tasks"]) == 18
    assert report["combination"]["composition_result"] == (
        "VACUOUS_EMPTY_PORTFOLIO_IDENTITY"
    )


def test_gate_rejects_all_c012_c018_and_preserves_global_only(
    report: dict[str, Any],
) -> None:
    rows = report["unsupported_rejections"]
    assert [row["constraint_id"] for row in rows] == [
        "C-012",
        "C-013",
        "C-014",
        "C-015",
        "C-016",
        "C-017",
        "C-018",
    ]
    assert all(row["error_code"] == "UNSUPPORTED_CAPABILITY" for row in rows)
    assert report["global_strategy_evidence"]["boundaries"]["strategy"] == (
        "ONE_GLOBAL_CP_SAT_MODEL_NO_DECOMPOSITION_OR_FALLBACK"
    )

    rejection_tamper = deepcopy(report)
    rejection_tamper["unsupported_rejections"][0]["error_code"] = "ACCEPTED"
    with pytest.raises(P5PortfolioGateContractError, match="rejection set"):
        validate_p5_portfolio_gate_report(rejection_tamper)

    combination_tamper = deepcopy(report)
    combination_tamper["combination"]["owner_invocations"] = ["TASK-P5-04"]
    with pytest.raises(P5PortfolioGateContractError, match="composition boundary"):
        validate_p5_portfolio_gate_report(combination_tamper)


def test_gate_embeds_fresh_validator_benchmark_and_p4_regression(
    report: dict[str, Any],
) -> None:
    assert report["formal_validator_evidence"]["status"] == "PASS"
    assert report["validator_mutation_evidence"]["counts"]["cases"] == 13
    assert [row["profile"]["size"] for row in report["benchmark_evidence"]] == [
        "XS",
        "S",
        "M",
    ]
    assert report["p4_regression_evidence"]["repeat_count"] == 2


def test_gate_is_not_exit_p6_production_or_successor_start(
    report: dict[str, Any],
) -> None:
    assert report["boundaries"] == {
        "current_phase": "P5",
        "data_plane": "SIMULATION_DEVELOPMENT_ONLY",
        "gate_kind": "P5_PORTFOLIO_INTEGRATION_GATE_NOT_EXIT_AUDIT",
        "selected_portfolio": "EMPTY_PROVIDER_VERIFIED",
        "p5_22_exit_gate_audit": "NOT_STARTED",
        "p6_plus": "NOT_ENTERED",
        "hybrid_planning": "EXCLUDED",
        "production_identity_and_approval_authority": "NOT_FORMED",
        "external_publish_integration_or_transfer": "NONE",
        "deployment": "NOT_PERFORMED",
        "capacity_and_sla": "NOT_ESTABLISHED",
        "uat": "NOT_PERFORMED",
        "schema_migration_dependency_adr_state_changes": "NONE",
        "remediation": "NONE_MIXED_INTO_GATE",
    }
