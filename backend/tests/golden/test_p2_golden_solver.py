"""TASK-P2-09 fixed JSSP/FJSP optimum and replay vectors."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from app.simulation.scenarios.p2_correctness import (
    CorrectnessCase,
    CorrectnessReplay,
    assignment_projection,
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_IDS = ("P2-GOLDEN-JSSP", "P2-GOLDEN-FJSP")


@lru_cache(maxsize=1)
def _cases() -> dict[str, CorrectnessCase]:
    return {case.scenario_id: case for case in load_correctness_cases(ROOT)}


@lru_cache(maxsize=2)
def _replay(scenario_id: str) -> CorrectnessReplay:
    case = _cases()[scenario_id]
    replay = execute_correctness_case(case, root=ROOT)
    verify_correctness_replay(replay)
    return replay


def _schema(name: str) -> dict[str, object]:
    return json.loads(
        (ROOT / "schemas" / "scenario" / name).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("scenario_id", GOLDEN_IDS)
def test_versioned_golden_assets_validate_and_resolve_provenance(
    scenario_id: str,
) -> None:
    case = _cases()[scenario_id]
    Draft202012Validator(
        _schema("factory-profile.schema.json"), format_checker=FormatChecker()
    ).validate(case.profile)
    Draft202012Validator(
        _schema("scenario-spec.schema.json"), format_checker=FormatChecker()
    ).validate(case.scenario)

    assert case.scenario["scenario_id"] == scenario_id
    assert case.scenario["scenario_version"] == "1.0.0"
    assert case.profile["profile_version"] == "1.0.0"
    assert case.manifest["seed"] == case.scenario["seed"]
    assert case.manifest["solver"] == {
        "backend_version": "cp-sat-backend.v1",
        "solver_version": "9.15.6755",
    }


@pytest.mark.parametrize("scenario_id", GOLDEN_IDS)
def test_hand_checked_golden_schedule_is_exact_optimum_and_validator_passes(
    scenario_id: str,
) -> None:
    replay = _replay(scenario_id)
    expected = replay.case.expected
    stage = replay.solution["objective_stage_results"][0]

    # OBJ-001 is non-negative. A feasible zero-tardiness schedule therefore
    # proves the hand-derived lower bound and optimum are both exactly zero.
    assert stage["objective_value"] == 0
    assert stage["best_bound"] == 0
    assert stage["relative_gap"] == 0
    assert replay.solution["solver_status"] == "OPTIMAL"
    assert replay.validation_report["status"] == "PASS"
    assert replay.validation_report["hard_violation_count"] == 0
    assert assignment_projection(replay) == expected["assignments"]
    assert replay.import_dataset_hash == replay.case.manifest[
        "expected_artifacts"
    ]["import_dataset_hash"]
    assert replay.snapshot_hash == replay.case.manifest["expected_artifacts"][
        "snapshot_hash"
    ]
    assert replay.problem["problem_hash"] == replay.case.manifest[
        "expected_artifacts"
    ]["problem_hash"]
