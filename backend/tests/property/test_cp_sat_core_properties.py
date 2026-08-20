"""Fixed-seed brute-force properties for the TASK-P2-05 core model."""

from __future__ import annotations

from typing import Sequence

from hypothesis import given, seed, settings, strategies as st

from app.planning.backends.cp_sat import CoreModelInputError, CoreModelReason, CpSatBackend
from app.planning.backends.cp_sat.core_model_check import (
    brute_force_core_feasible,
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


type OptionTicks = tuple[str, int]


@st.composite
def _tiny_core_cases(
    draw: st.DrawFn,
) -> tuple[tuple[tuple[OptionTicks, ...], ...], int]:
    horizon_ticks = draw(st.integers(min_value=1, max_value=10))
    resource_count = draw(st.integers(min_value=1, max_value=3))
    resources = [f"RESOURCE-{index:03d}" for index in range(resource_count)]
    operation_count = draw(st.integers(min_value=1, max_value=5))
    operations: list[tuple[OptionTicks, ...]] = []
    for _ in range(operation_count):
        selected_resources = draw(
            st.lists(
                st.sampled_from(resources),
                min_size=1,
                max_size=resource_count,
                unique=True,
            )
        )
        options = tuple(
            (resource_id, draw(st.integers(min_value=1, max_value=horizon_ticks)))
            for resource_id in sorted(selected_resources)
        )
        operations.append(options)
    return tuple(operations), horizon_ticks


@seed(20260820)
@settings(max_examples=36, deadline=None)
@given(case=_tiny_core_cases())
def test_cp_sat_feasibility_matches_independent_choice_and_load_enumeration(
    case: tuple[tuple[tuple[OptionTicks, ...], ...], int]
) -> None:
    operation_options, horizon_ticks = case
    expected = brute_force_core_feasible(operation_options, horizon_ticks)
    problem = synthetic_core_problem(
        operation_options,
        horizon_ticks=horizon_ticks,
        tag="PROPERTY-FEASIBILITY",
    )
    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )

    assert (result.solution["solver_status"] == "FEASIBLE") is expected
    if expected:
        assert len(result.solution["assignments"]) == len(operation_options)
        assert result.validation_report is not None
        assert result.validation_report["status"] == "PASS"
        assert validate_problem_schedule(problem, result.solution)["status"] == "PASS"
    else:
        assert result.solution["solver_status"] == "INFEASIBLE"
        assert result.solution["assignments"] == []
        assert result.validation_report is None


@seed(20260821)
@settings(max_examples=24, deadline=None)
@given(
    horizon_ticks=st.integers(min_value=1, max_value=20),
    extra_ticks=st.integers(min_value=1, max_value=20),
)
def test_every_overflowing_option_is_rejected_instead_of_silently_removed(
    horizon_ticks: int, extra_ticks: int
) -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", horizon_ticks + extra_ticks)]],
        horizon_ticks=horizon_ticks,
        tag="PROPERTY-OVERFLOW",
    )

    try:
        CpSatBackend().solve(problem, synthetic_core_policy(), synthetic_core_limits())
    except CoreModelInputError as error:
        assert error.reason is CoreModelReason.DURATION_EXCEEDS_HORIZON
        assert error.solver_status.value == "MODEL_INVALID"
    else:
        raise AssertionError("overflowing option was silently accepted or removed")


def _selected_duration(
    options: Sequence[OptionTicks], resource_id: str
) -> int:
    return next(duration for resource, duration in options if resource == resource_id)


@seed(20260822)
@settings(max_examples=24, deadline=None)
@given(case=_tiny_core_cases())
def test_every_accepted_assignment_uses_the_selected_candidate_duration(
    case: tuple[tuple[tuple[OptionTicks, ...], ...], int]
) -> None:
    operation_options, horizon_ticks = case
    if not brute_force_core_feasible(operation_options, horizon_ticks):
        return
    problem = synthetic_core_problem(
        operation_options,
        horizon_ticks=horizon_ticks,
        tag="PROPERTY-DURATION",
    )
    solution = CpSatBackend().solve(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )

    for operation_index, assignment in enumerate(solution["assignments"]):
        expected_ticks = _selected_duration(
            operation_options[operation_index], assignment["resource_id"]
        )
        assert assignment["duration_ticks"] == expected_ticks
        assert assignment["end_tick"] - assignment["start_tick"] == expected_ticks
        assert 0 <= assignment["start_tick"] < assignment["end_tick"] <= horizon_ticks
