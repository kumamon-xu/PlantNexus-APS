"""TEST-VALIDATOR-MUTATION independent P4 candidate rejection vectors."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from app.domain.execution_contracts import contract_fingerprint
from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.replan_backend import LexicographicReplanBackend
from app.planning.policy.delivery import simulation_solve_limits
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import build_freeze_window_fixture
from app.planning.validation.replan_candidate_validator import (
    ReplanCandidateValidationInputError,
    validate_replan_candidate,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_MUTATION_ID = "TEST-VALIDATOR-MUTATION"


def _fixture():  # type: ignore[no-untyped-def]
    fixture = build_freeze_window_fixture(ROOT)
    projection = project_effective_locks(
        snapshot=fixture.snapshot,
        problem=fixture.problem,
        base_schedule=fixture.base_schedule,
        policy=fixture.policy,
    ).document
    limits = simulation_solve_limits(
        limits_id="LIMITS-TASK-P4-07-MUTATION",
        limits_revision="1.0.0",
        source_record_id="LIMITS-TASK-P4-07-MUTATION",
        max_wall_time_seconds=6.0,
        max_workers=1,
        random_seed=20260828,
    )
    content = cast(dict[str, object], fixture.base_schedule["content"])
    base = cast(list[dict[str, object]], content["assignments"])
    solved = LexicographicReplanBackend().solve_with_evidence(
        fixture.problem.document,
        base_assignments=base,
        effective_locks=projection,
        limits=limits,
    )
    return fixture, projection, base, solved


def _rehash_candidate(candidate: dict[str, object]) -> None:
    basis = {
        "candidate_version": candidate["candidate_version"],
        "assignment_count": candidate["assignment_count"],
        "assignments": candidate["assignments"],
    }
    candidate["candidate_fingerprint"] = contract_fingerprint(basis)


def test_positive_candidate_recomputes_formal_locks_and_change_universe() -> None:
    fixture, projection, base, solved = _fixture()
    report = validate_replan_candidate(
        problem=fixture.problem.document,
        base_assignments=base,
        effective_locks=projection,
        candidate=cast(dict[str, object], solved.candidate),
        objective_evidence=cast(dict[str, object], solved.objective_values),
    )

    assert report["status"] == "PASS"
    assert report["hard_violation_count"] == 0
    assert report["formal_validation"]["status"] == "PASS"
    assert report["change_report_projection"]["complete"] is True
    assert report["independence"] == {
        "cp_sat_imported": False,
        "backend_imported": False,
        "reporting_calculator_imported": False,
        "solver_status_trusted": False,
        "formal_validator_fresh": True,
        "side_effects": "NONE",
    }


def test_running_or_freeze_tuple_movement_is_rejected_independently() -> None:
    fixture, projection, base, solved = _fixture()
    candidate = cast(dict[str, object], deepcopy(solved.candidate))
    assignments = cast(list[dict[str, object]], candidate["assignments"])
    running = next(
        item for item in assignments if item["operation_id"] == fixture.first_operation_id
    )
    tick_seconds = fixture.problem.document["tick_seconds"]
    running["start_tick"] = cast(int, running["start_tick"]) + 1
    running["end_tick"] = cast(int, running["end_tick"]) + 1
    running["start_at_utc"] = format_utc_instant(
        parse_utc_instant(cast(str, running["start_at_utc"]))
        + timedelta(seconds=tick_seconds)
    )
    running["end_at_utc"] = format_utc_instant(
        parse_utc_instant(cast(str, running["end_at_utc"]))
        + timedelta(seconds=tick_seconds)
    )
    _rehash_candidate(candidate)

    report = validate_replan_candidate(
        problem=fixture.problem.document,
        base_assignments=base,
        effective_locks=projection,
        candidate=candidate,
        objective_evidence=cast(dict[str, object], solved.objective_values),
    )

    assert report["status"] == "FAIL"
    codes = {item["code"] for item in report["violations"]}
    assert "FORMAL_VALIDATOR_FAILED" in codes
    assert "EFFECTIVE_HARD_LOCK_VIOLATION" in codes


def test_missing_operation_and_objective_tamper_are_not_partial_success() -> None:
    fixture, projection, base, solved = _fixture()
    missing = cast(dict[str, object], deepcopy(solved.candidate))
    assignments = cast(list[dict[str, object]], missing["assignments"])
    assignments.pop()
    missing["assignment_count"] = len(assignments)
    _rehash_candidate(missing)
    missing_report = validate_replan_candidate(
        problem=fixture.problem.document,
        base_assignments=base,
        effective_locks=projection,
        candidate=missing,
        objective_evidence=cast(dict[str, object], solved.objective_values),
    )
    assert missing_report["status"] == "FAIL"
    assert "ACTIVE_UNIVERSE_MISMATCH" in {
        item["code"] for item in missing_report["violations"]
    }

    objective = cast(dict[str, object], deepcopy(solved.objective_values))
    stability = cast(dict[str, object], objective["stability"])
    stability["absolute_start_shift_seconds"] = (
        cast(int, stability["absolute_start_shift_seconds"]) + 1
    )
    objective_report = validate_replan_candidate(
        problem=fixture.problem.document,
        base_assignments=base,
        effective_locks=projection,
        candidate=cast(dict[str, object], solved.candidate),
        objective_evidence=objective,
    )
    assert objective_report["status"] == "FAIL"
    assert "OBJECTIVE_EVIDENCE_MISMATCH" in {
        item["code"] for item in objective_report["violations"]
    }


def test_projection_identity_tamper_fails_before_rule_evaluation() -> None:
    fixture, projection, base, solved = _fixture()
    tampered = deepcopy(projection)
    tampered["projection_fingerprint"] = "sha256:" + "0" * 64

    with pytest.raises(ReplanCandidateValidationInputError):
        validate_replan_candidate(
            problem=fixture.problem.document,
            base_assignments=base,
            effective_locks=tampered,
            candidate=cast(dict[str, object], solved.candidate),
            objective_evidence=cast(dict[str, object], solved.objective_values),
        )


def test_validator_source_has_no_solver_backend_or_reporting_dependency() -> None:
    source = (
        ROOT
        / "backend/app/planning/validation/replan_candidate_validator.py"
    ).read_text(encoding="utf-8")

    assert "ortools" not in source
    assert "app.planning.backends" not in source
    assert "app.planning.reporting" not in source
    assert TEST_MUTATION_ID == "TEST-VALIDATOR-MUTATION"
