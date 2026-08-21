"""Fixed-seed properties for exact TASK-P2-06 seconds/tick boundaries."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from hypothesis import given, seed, settings, strategies as st

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import CpSatBackend
from app.planning.backends.cp_sat.core_model_check import (
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.backends.cp_sat.temporal_constraints import (
    calendar_tick_blocks,
    ceil_seconds_to_ticks,
    floor_seconds_to_ticks,
)
from app.planning.problem.hashing import problem_v2_hash_for


@seed(20260821)
@settings(max_examples=80, deadline=None)
@given(
    seconds=st.integers(min_value=-100_000, max_value=100_000),
    tick_seconds=st.integers(min_value=1, max_value=600),
)
def test_signed_ceil_and_floor_ticks_bracket_every_whole_second(
    seconds: int, tick_seconds: int
) -> None:
    lower = floor_seconds_to_ticks(seconds, tick_seconds)
    upper = ceil_seconds_to_ticks(seconds, tick_seconds)
    assert lower * tick_seconds <= seconds < (lower + 1) * tick_seconds
    assert (upper - 1) * tick_seconds < seconds <= upper * tick_seconds
    assert lower <= upper <= lower + 1


@seed(20260822)
@settings(max_examples=36, deadline=None)
@given(
    tick_seconds=st.integers(min_value=1, max_value=120),
    minimum=st.integers(min_value=0, max_value=240),
    width=st.integers(min_value=0, max_value=240),
)
def test_cp_sat_min_max_window_matches_exact_seconds_without_relaxation(
    tick_seconds: int, minimum: int, width: int
) -> None:
    maximum = minimum + width
    lower_tick = ceil_seconds_to_ticks(minimum, tick_seconds)
    upper_tick = floor_seconds_to_ticks(maximum, tick_seconds)
    horizon_ticks = max(3, upper_tick + 3)
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-002", 1)]],
        horizon_ticks=horizon_ticks,
        tick_seconds=tick_seconds,
        tag=f"PROPERTY-TEMPORAL-{tick_seconds}-{minimum}-{maximum}",
    )
    problem["precedence_edges"] = [
        cast(
            Any,
            {
                "precedence_edge_id": "EDGE-PROPERTY",
                "predecessor_operation_id": "OP-000",
                "successor_operation_id": "OP-001",
                "min_lag_seconds": minimum,
                "max_lag_seconds": maximum,
                "transport_lag_seconds": 0,
            },
        )
    ]
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )

    expected_feasible = lower_tick <= upper_tick
    assert (result.solution["solver_status"] == "FEASIBLE") is expected_feasible
    if expected_feasible:
        by_id = {
            assignment["operation_id"]: assignment
            for assignment in result.solution["assignments"]
        }
        observed = (
            by_id["OP-001"]["start_tick"] - by_id["OP-000"]["end_tick"]
        ) * tick_seconds
        assert minimum <= observed <= maximum
        assert result.validation_report is not None
        assert result.validation_report["status"] == "PASS"
    else:
        assert result.solution["solver_status"] == "INFEASIBLE"
        assert result.validation_report is None


@seed(20260823)
@settings(max_examples=60, deadline=None)
@given(
    tick_seconds=st.integers(min_value=1, max_value=120),
    unavailable_start=st.integers(min_value=-120, max_value=480),
    unavailable_length=st.integers(min_value=1, max_value=240),
    assignment_tick=st.integers(min_value=0, max_value=7),
)
def test_calendar_tick_projection_matches_raw_half_open_intersection(
    tick_seconds: int,
    unavailable_start: int,
    unavailable_length: int,
    assignment_tick: int,
) -> None:
    horizon_ticks = 8
    horizon_seconds = horizon_ticks * tick_seconds
    unavailable_end = unavailable_start + unavailable_length
    if unavailable_start >= horizon_seconds or unavailable_end <= 0:
        return
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)]],
        horizon_ticks=horizon_ticks,
        tick_seconds=tick_seconds,
        tag="PROPERTY-CALENDAR",
    )
    origin = parse_utc_instant(problem["horizon_start_utc"])
    problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": format_utc_instant(
                origin + timedelta(seconds=unavailable_start)
            ),
            "end_utc": format_utc_instant(
                origin + timedelta(seconds=unavailable_end)
            ),
        }
    ]
    block = calendar_tick_blocks(problem, horizon_ticks=horizon_ticks)[
        "RESOURCE-001"
    ]
    assignment_start = assignment_tick * tick_seconds
    assignment_end = (assignment_tick + 1) * tick_seconds
    raw_overlap = (
        assignment_start < unavailable_end
        and unavailable_start < assignment_end
    )
    tick_overlap = any(
        assignment_tick < end and start < assignment_tick + 1
        for start, end in block
    )
    assert tick_overlap is raw_overlap
