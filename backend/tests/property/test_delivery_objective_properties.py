"""TASK-P2-08 generated exact-oracle properties for OBJ-001."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from itertools import permutations
from typing import cast

from hypothesis import given, settings, strategies as st

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.core_model_check import synthetic_core_problem
from app.planning.policy.delivery import (
    SIMULATION_DELIVERY_SOURCE_SYSTEM,
    SIMULATION_DELIVERY_SOURCE_VERSION,
    simulation_delivery_policy,
    simulation_solve_limits,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.strategies import GlobalCpSatStrategy


@st.composite
def delivery_vectors(
    draw: st.DrawFn,
) -> tuple[list[int], list[int], list[int]]:
    count = draw(st.integers(min_value=2, max_value=5))
    durations = draw(
        st.lists(
            st.integers(min_value=1, max_value=3),
            min_size=count,
            max_size=count,
        )
    )
    horizon = sum(durations)
    due_ticks = draw(
        st.lists(
            st.integers(min_value=0, max_value=horizon + 1),
            min_size=count,
            max_size=count,
        )
    )
    weights = draw(
        st.lists(
            st.integers(min_value=1, max_value=5),
            min_size=count,
            max_size=count,
        )
    )
    return durations, due_ticks, weights


def _problem(
    durations: list[int],
    due_ticks: list[int],
    weights: list[int],
    *,
    tick_seconds: int = 60,
) -> PlanningProblemDocumentV2:
    horizon = sum(durations)
    problem = synthetic_core_problem(
        [[("RESOURCE-001", duration)] for duration in durations],
        horizon_ticks=horizon,
        tick_seconds=tick_seconds,
        tag="PROPERTY-OBJ001",
    )
    start = parse_utc_instant(problem["horizon_start_utc"])
    template = problem["delivery_demands"][0]
    demands = []
    for index, (due_tick, weight) in enumerate(zip(due_ticks, weights, strict=True)):
        demand = deepcopy(template)
        demand_id = f"DEMAND-PROPERTY-{index:03d}"
        demand.update(
            {
                "demand_order_id": demand_id,
                "due_at_utc": format_utc_instant(
                    start + timedelta(seconds=due_tick * tick_seconds)
                ),
                "due_source_record_id": f"DUE-PROPERTY-{index:03d}",
                "priority_weight": weight,
                "priority_source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
                "priority_source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
                "priority_source_record_id": f"PRIORITY-PROPERTY-{index:03d}",
            }
        )
        demands.append(demand)
        problem["operation_instances"][index]["demand_order_id"] = demand_id
    problem["delivery_demands"] = demands
    problem["problem_hash"] = problem_v2_hash_for(
        cast(dict[str, object], problem)
    )
    return problem


def _brute_force_optimum(
    durations: list[int],
    due_ticks: list[int],
    weights: list[int],
    *,
    tick_seconds: int,
) -> int:
    best: int | None = None
    for ordering in permutations(range(len(durations))):
        completion = 0
        objective = 0
        for index in ordering:
            completion += durations[index]
            objective += (
                weights[index]
                * max(0, completion - due_ticks[index])
                * tick_seconds
            )
        best = objective if best is None else min(best, objective)
    if best is None:
        raise AssertionError("property vectors are non-empty")
    return best


def _solve(problem: PlanningProblemDocumentV2):  # type: ignore[no-untyped-def]
    return GlobalCpSatStrategy().solve(
        problem,
        simulation_delivery_policy(),
        simulation_solve_limits(
            limits_id="LIMITS-TASK-P2-08-PROPERTY",
            limits_revision="1.0.0",
            source_record_id="LIMITS-TASK-P2-08-PROPERTY",
            max_wall_time_seconds=3.0,
            max_workers=1,
            random_seed=20260821,
        ),
        planning_run_id="RUN-TASK-P2-08-PROPERTY",
        code_commit="uncommitted",
    )


@settings(max_examples=16, deadline=None, derandomize=True)
@given(delivery_vectors())
def test_global_obj001_matches_exhaustive_single_machine_optimum(
    vectors: tuple[list[int], list[int], list[int]],
) -> None:
    durations, due_ticks, weights = vectors
    result = _solve(_problem(durations, due_ticks, weights))
    stage = result.solution["objective_stage_results"][0]

    assert result.solution["solver_status"] == "OPTIMAL"
    assert stage["objective_value"] == _brute_force_optimum(
        durations, due_ticks, weights, tick_seconds=60
    )
    assert stage["best_bound"] == stage["objective_value"]
    assert stage["relative_gap"] == 0
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"


def test_non_grid_due_instant_uses_exact_tardiness_seconds() -> None:
    problem = _problem([1], [0], [3])
    start = parse_utc_instant(problem["horizon_start_utc"])
    problem["delivery_demands"][0]["due_at_utc"] = format_utc_instant(
        start + timedelta(seconds=30)
    )
    problem["problem_hash"] = problem_v2_hash_for(
        cast(dict[str, object], problem)
    )
    result = _solve(problem)

    assert result.solution["objective_stage_results"][0]["objective_value"] == 90


@settings(max_examples=12, deadline=None, derandomize=True)
@given(
    duration=st.integers(min_value=1, max_value=4),
    slack=st.integers(min_value=0, max_value=4),
    weight=st.integers(min_value=1, max_value=20),
)
def test_single_demand_objective_is_exact_priority_scaled_tardiness(
    duration: int,
    slack: int,
    weight: int,
) -> None:
    result = _solve(_problem([duration], [slack], [weight]))
    expected = weight * max(0, duration - slack) * 60

    assert result.solution["solver_status"] == "OPTIMAL"
    assert result.solution["objective_stage_results"][0]["objective_value"] == expected
