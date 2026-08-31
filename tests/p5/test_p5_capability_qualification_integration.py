"""Executable TASK-P5-01 portfolio evidence and provider artifact contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.p5_capability_qualification import (
    DIFF_BASE,
    EXPECTED_CANDIDATES,
    IMPACT_RULES,
    REPORT_VERSION,
    TASK_ID,
    decide_record,
    load_qualification_bundle,
    main,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    code_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if len(code_commit) == 40 and all(
        character in "0123456789abcdef" for character in code_commit
    ):
        report_path = ROOT / "build/validation/ci-p5-capability-qualification.json"
    else:
        report_path = tmp_path_factory.mktemp("p5-qualification") / "report.json"
    assert main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    return cast(
        dict[str, Any], json.loads(report_path.read_text(encoding="utf-8"))
    )


def test_machine_report_binds_task_base_profile_checks_and_zero_blocking(
    report: dict[str, Any],
) -> None:
    assert report["report_version"] == REPORT_VERSION
    assert report["status"] == "PASS"
    assert report["task_id"] == TASK_ID
    assert report["diff_base"] == DIFF_BASE
    assert report["validation_profile"] == "HIGH_RISK"
    assert report["impact_rules"] == list(IMPACT_RULES)
    assert report["check_count"] == 11
    assert all(check["status"] == "PASS" for check in report["checks"])
    assert report["issues"] == []
    assert report["blocking_issues"] == []


def test_all_nine_candidates_are_independently_deferred_without_auto_start(
    report: dict[str, Any],
) -> None:
    decisions = report["decisions"]
    assert tuple(row["candidate_id"] for row in decisions) == EXPECTED_CANDIDATES
    assert all(row["decision"] == "DEFERRED" for row in decisions)
    assert all(row["evidence_gaps"] for row in decisions)
    assert report["portfolio"] == {
        "selected": [],
        "deferred": list(EXPECTED_CANDIDATES),
        "selected_count": 0,
        "deferred_count": 9,
        "p5_02_authorized": False,
    }


def test_xs_s_m_replay_preserves_runtime_memory_model_quality_observations(
    report: dict[str, Any],
) -> None:
    observations = report["benchmark_observations"]
    assert [row["profile"]["size"] for row in observations] == ["XS", "S", "M"]
    assert all(row["status"] == "PASS" for row in observations)
    assert all(set(row) >= {"runtime", "memory", "model_size", "quality"} for row in observations)
    assert all(row["quality"]["validation"]["status"] == "PASS" for row in observations)
    assert all(row["boundaries"]["production_capacity_sla"] == "NOT_ESTABLISHED_OPEN_012" for row in observations)


def test_decision_records_match_fresh_semantic_replay(report: dict[str, Any]) -> None:
    bundle = load_qualification_bundle(ROOT)
    fresh = [decide_record(record, bundle.profile) for record in bundle.records]
    assert [row["decision_fingerprint"] for row in report["decisions"]] == [
        row["decision_fingerprint"] for row in fresh
    ]


def test_support_and_phase_boundaries_remain_frozen(report: dict[str, Any]) -> None:
    assert report["boundaries"] == {
        "candidate_support_states": "UNCHANGED_UNSUPPORTED",
        "planning_problem_solver_validator": "UNCHANGED",
        "schema_migration_dependency_state_workflow": "UNCHANGED",
        "p4_execution_replan_freeze_stability_change_report_simulator": "FROZEN_REGRESSION_CONTEXT",
        "new_sim_assumption": "NONE",
        "p5_02_and_capability_implementation": "NOT_AUTHORIZED_NOT_STARTED",
        "p6_plus": "EXCLUDED",
        "production_authority_external_deployment_capacity_sla": "NOT_ESTABLISHED",
    }
