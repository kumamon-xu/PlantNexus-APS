"""Fixed-seed properties for the formal independent ScheduleValidator."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any, cast

from hypothesis import given, seed, settings, strategies as st

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import validate_problem_schedule
from app.planning.validation.problem_validator_check import (
    formal_validation_vector,
    materialize_formal_mutation,
)


type JsonObject = dict[str, Any]


def _operation(problem: JsonObject, operation_id: str) -> JsonObject:
    return next(
        value
        for value in cast(list[JsonObject], problem["operation_instances"])
        if value["operation_id"] == operation_id
    )


def _assignment(candidate: JsonObject, operation_id: str) -> JsonObject:
    return next(
        value
        for value in cast(list[JsonObject], candidate["assignments"])
        if value["operation_id"] == operation_id
    )


def _refresh(problem: JsonObject, candidate: JsonObject) -> None:
    problem["problem_hash"] = problem_v2_hash_for(problem)
    reference = cast(JsonObject, candidate["problem"])
    reference["problem_hash"] = problem["problem_hash"]


@seed(20260820)
@settings(max_examples=48, deadline=None)
@given(
    duration_seconds=st.integers(min_value=1, max_value=600),
    start_tick=st.integers(min_value=6, max_value=300),
)
def test_legal_duration_and_horizon_variations_are_accepted(
    duration_seconds: int, start_tick: int
) -> None:
    problem, candidate = formal_validation_vector()
    tick_seconds = cast(int, problem["tick_seconds"])
    duration_ticks = (duration_seconds + tick_seconds - 1) // tick_seconds
    operation = _operation(problem, "OP-E")
    option = cast(list[JsonObject], operation["resource_options"])[0]
    option["cycle_seconds_per_unit"] = duration_seconds
    option["final_duration_seconds"] = duration_seconds
    assignment = _assignment(candidate, "OP-E")
    assignment["start_tick"] = start_tick
    assignment["end_tick"] = start_tick + duration_ticks
    assignment["duration_ticks"] = duration_ticks
    assignment["duration_seconds"] = duration_seconds
    horizon_start = parse_utc_instant(str(problem["horizon_start_utc"]))
    assignment["start_at_utc"] = format_utc_instant(
        horizon_start + timedelta(seconds=start_tick * tick_seconds)
    )
    assignment["end_at_utc"] = format_utc_instant(
        horizon_start + timedelta(seconds=(start_tick + duration_ticks) * tick_seconds)
    )
    _refresh(problem, candidate)

    report = validate_problem_schedule(problem, candidate)

    assert report["status"] == "PASS"
    assert report["hard_violation_count"] == 0
    assert duration_ticks * tick_seconds >= duration_seconds
    assert (duration_ticks - 1) * tick_seconds < duration_seconds


@seed(20260821)
@settings(max_examples=48, deadline=None)
@given(
    mutation_class=st.sampled_from(
        (
            "missing_operation",
            "wrong_resource",
            "machine_overlap",
            "calendar_overlap",
            "material_early",
            "completed_rescheduled",
            "running_moved",
            "hard_lock_moved",
            "precedence_lag",
            "cross_workshop_lag",
            "wrong_duration",
            "horizon_overflow",
        )
    )
)
def test_any_sampled_rule_mutation_is_rejected(mutation_class: str) -> None:
    problem, candidate = formal_validation_vector()
    changed_problem, changed_candidate = materialize_formal_mutation(
        problem, candidate, mutation_class
    )

    report = validate_problem_schedule(changed_problem, changed_candidate)

    assert report["status"] == "FAIL"
    assert report["hard_violation_count"] >= 1
    assert report["violations"]


@seed(20260822)
@settings(max_examples=32, deadline=None)
@given(
    reverse_problem=st.booleans(),
    reverse_candidate=st.booleans(),
)
def test_collection_order_does_not_change_the_validation_report(
    reverse_problem: bool, reverse_candidate: bool
) -> None:
    problem, candidate = formal_validation_vector()
    expected = validate_problem_schedule(problem, candidate)
    changed_problem = deepcopy(problem)
    changed_candidate = deepcopy(candidate)
    if reverse_problem:
        for collection in (
            "resources",
            "operation_instances",
            "historical_completion_anchors",
            "precedence_edges",
            "operation_locks",
            "resource_unavailable_intervals",
        ):
            cast(list[object], changed_problem[collection]).reverse()
    if reverse_candidate:
        cast(list[object], changed_candidate["assignments"]).reverse()

    assert validate_problem_schedule(changed_problem, changed_candidate) == expected
