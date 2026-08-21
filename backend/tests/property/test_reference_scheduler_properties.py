"""Shrinkable properties for TASK-P2-10 reference scheduling boundaries."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import cast

from hypothesis import given, seed, settings, strategies as st

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import (
    ProblemScheduleValidator,
)
from app.simulation.baselines.contracts import (
    ReferenceAlgorithm,
    ReferenceSchedulerStatus,
)
from app.simulation.baselines.reference_schedulers import schedule_reference
from app.simulation.scenarios.p2_correctness import (
    SCENARIO_IDS,
    execute_correctness_case,
    load_correctness_cases,
)


ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _problems() -> dict[str, PlanningProblemDocumentV2]:
    return {
        case.scenario_id: cast(
            PlanningProblemDocumentV2,
            execute_correctness_case(case, root=ROOT).problem,
        )
        for case in load_correctness_cases(ROOT)
    }


@seed(20260821)
@settings(max_examples=60, deadline=None)
@given(
    algorithm=st.sampled_from(tuple(ReferenceAlgorithm)),
    duration_seconds=st.integers(min_value=1, max_value=120),
    release_seconds=st.integers(min_value=0, max_value=180),
    material_seconds=st.integers(min_value=0, max_value=180),
    due_seconds=st.integers(min_value=0, max_value=360),
    priority_weight=st.integers(min_value=1, max_value=8),
)
def test_generated_gate_duration_and_due_values_keep_exact_validator_and_kpi_semantics(
    algorithm: ReferenceAlgorithm,
    duration_seconds: int,
    release_seconds: int,
    material_seconds: int,
    due_seconds: int,
    priority_weight: int,
) -> None:
    problem = deepcopy(_problems()["P2-CALENDAR"])
    problem["resource_unavailable_intervals"] = []
    start = parse_utc_instant(problem["horizon_start_utc"])
    operation = problem["operation_instances"][0]
    option = operation["resource_options"][0]
    option["cycle_seconds_per_unit"] = duration_seconds
    option["final_duration_seconds"] = duration_seconds
    operation["release_at_utc"] = format_utc_instant(
        start + timedelta(seconds=release_seconds)
    )
    operation["material_ready_at_utc"] = format_utc_instant(
        start + timedelta(seconds=material_seconds)
    )
    demand = problem["delivery_demands"][0]
    demand["due_at_utc"] = format_utc_instant(start + timedelta(seconds=due_seconds))
    demand["priority_weight"] = priority_weight
    problem["problem_hash"] = problem_v2_hash_for(problem)

    first = schedule_reference(problem, algorithm)
    second = schedule_reference(problem, algorithm)

    assert first["status"] is ReferenceSchedulerStatus.FEASIBLE
    assert first["candidate"] == second["candidate"]
    candidate = first["candidate"]
    assert candidate is not None
    assert len(candidate["assignments"]) == 1
    assignment = candidate["assignments"][0]
    tick_seconds = problem["tick_seconds"]
    expected_start = (
        max(release_seconds, material_seconds) + tick_seconds - 1
    ) // tick_seconds
    expected_duration = (duration_seconds + tick_seconds - 1) // tick_seconds
    expected_end = expected_start + expected_duration
    assert assignment["start_tick"] == expected_start
    assert assignment["end_tick"] == expected_end
    assert assignment["duration_seconds"] == duration_seconds
    assert first["metrics"]["weighted_tardiness_seconds"] == (
        priority_weight * max(0, expected_end * tick_seconds - due_seconds)
    )
    assert first["metrics"]["makespan_seconds"] == expected_end * tick_seconds
    report = ProblemScheduleValidator().validate(problem, candidate)
    assert report["status"] == "PASS"
    assert report["hard_violation_count"] == 0


@settings(max_examples=35, deadline=None, derandomize=True)
@given(
    scenario_id=st.sampled_from(SCENARIO_IDS),
    algorithm=st.sampled_from(tuple(ReferenceAlgorithm)),
)
def test_sampled_authoritative_problem_and_algorithm_pairs_are_complete_and_valid(
    scenario_id: str, algorithm: ReferenceAlgorithm
) -> None:
    problem = _problems()[scenario_id]

    result = schedule_reference(problem, algorithm)

    assert result["status"] is ReferenceSchedulerStatus.FEASIBLE
    candidate = result["candidate"]
    assert candidate is not None
    assert len(candidate["assignments"]) == len(problem["operation_instances"])
    assert {value["operation_id"] for value in candidate["assignments"]} == {
        value["operation_id"] for value in problem["operation_instances"]
    }
    report = ProblemScheduleValidator().validate(problem, candidate)
    assert report["status"] == "PASS"
    assert report["hard_violation_count"] == 0
