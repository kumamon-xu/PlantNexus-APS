"""TASK-P2-09 generated replay properties with shrinking support."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from hypothesis import given, settings, strategies as st
import pytest

from app.planning.validation import validate_problem_schedule
from app.simulation.scenarios.p2_correctness import (
    SCENARIO_IDS,
    CorrectnessCase,
    CorrectnessReplay,
    assignment_projection,
    execute_correctness_case,
    load_correctness_cases,
)

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _cases() -> dict[str, CorrectnessCase]:
    return {case.scenario_id: case for case in load_correctness_cases(ROOT)}


@lru_cache(maxsize=14)
def _replay(scenario_id: str, reverse_rows: bool) -> CorrectnessReplay:
    return execute_correctness_case(
        _cases()[scenario_id], root=ROOT, reverse_rows=reverse_rows
    )


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
@settings(max_examples=2, deadline=None, derandomize=True)
@given(reverse_rows=st.booleans())
def test_source_row_order_cannot_change_business_artifacts_or_schedule(
    scenario_id: str, reverse_rows: bool
) -> None:
    baseline = _replay(scenario_id, False)
    candidate = _replay(scenario_id, reverse_rows)

    assert candidate.import_dataset_hash == baseline.import_dataset_hash
    assert candidate.snapshot_hash == baseline.snapshot_hash
    assert candidate.problem["problem_hash"] == baseline.problem["problem_hash"]
    assert assignment_projection(candidate) == assignment_projection(baseline)
    assert candidate.validation_report == baseline.validation_report


@settings(max_examples=14, deadline=None, derandomize=True)
@given(scenario_id=st.sampled_from(SCENARIO_IDS))
def test_every_solver_candidate_passes_a_fresh_independent_validator(
    scenario_id: str,
) -> None:
    replay = _replay(scenario_id, False)
    independent_report = validate_problem_schedule(replay.problem, replay.solution)

    assert independent_report == replay.validation_report
    assert independent_report["status"] == "PASS"
    assert independent_report["hard_violation_count"] == 0
    assert replay.solution["solver_status"] == "OPTIMAL"
