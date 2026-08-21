"""Fixed-seed properties for TASK-P2-07 execution facts and locks."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import pytest
from hypothesis import given, seed, settings, strategies as st

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import (
    CoreModelInputError,
    CoreModelReason,
    CpSatBackend,
    build_core_model,
)
from app.planning.backends.cp_sat.core_model_check import (
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for


def _at(problem: PlanningProblemDocumentV2, seconds: int) -> str:
    return format_utc_instant(
        parse_utc_instant(problem["horizon_start_utc"])
        + timedelta(seconds=seconds)
    )


def _rehash(problem: PlanningProblemDocumentV2) -> None:
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))


def _solve(problem: PlanningProblemDocumentV2):
    _rehash(problem)
    return CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )


@seed(20260824)
@settings(max_examples=36, deadline=None)
@given(
    tick_seconds=st.integers(min_value=1, max_value=120),
    remaining_seconds=st.integers(min_value=1, max_value=960),
    assigned_index=st.integers(min_value=0, max_value=1),
)
def test_running_assignment_always_matches_authoritative_remainder_and_resource(
    tick_seconds: int, remaining_seconds: int, assigned_index: int
) -> None:
    horizon_ticks = max(8, (remaining_seconds + tick_seconds - 1) // tick_seconds)
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 3)]],
        horizon_ticks=horizon_ticks,
        tick_seconds=tick_seconds,
        tag=f"PROPERTY-RUNNING-{tick_seconds}-{remaining_seconds}-{assigned_index}",
    )
    assigned_resource = f"RESOURCE-00{assigned_index + 1}"
    operation = cast(dict[str, Any], problem["operation_instances"][0])
    operation.update(
        {
            "status": "RUNNING",
            "actual_start_at_utc": _at(problem, -tick_seconds),
            "assigned_resource_id": assigned_resource,
            "remaining_seconds": remaining_seconds,
        }
    )
    problem["required_capabilities"] = [
        "ALTERNATIVE_RESOURCE",
        "RUNNING_OPERATION",
    ]

    result = _solve(problem)
    assignment = result.solution["assignments"][0]
    expected_ticks = (remaining_seconds + tick_seconds - 1) // tick_seconds

    assert result.solution["solver_status"] == "FEASIBLE"
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"
    assert assignment["resource_id"] == assigned_resource
    assert assignment["start_tick"] == 0
    assert assignment["end_tick"] == expected_ticks
    assert assignment["duration_ticks"] == expected_ticks
    assert assignment["duration_seconds"] == remaining_seconds


@seed(20260825)
@settings(max_examples=36, deadline=None)
@given(
    tick_seconds=st.integers(min_value=1, max_value=120),
    start_tick=st.integers(min_value=0, max_value=5),
    duration_ticks=st.integers(min_value=1, max_value=3),
    resource_index=st.integers(min_value=0, max_value=1),
    final_remainder=st.integers(min_value=1, max_value=120),
)
def test_hard_lock_exact_tuple_is_preserved_for_every_grid_case(
    tick_seconds: int,
    start_tick: int,
    duration_ticks: int,
    resource_index: int,
    final_remainder: int,
) -> None:
    resource_id = f"RESOURCE-00{resource_index + 1}"
    authoritative_seconds = (
        (duration_ticks - 1) * tick_seconds
        + min(final_remainder, tick_seconds)
    )
    option_ticks = max(1, (authoritative_seconds + tick_seconds - 1) // tick_seconds)
    assert option_ticks == duration_ticks
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=10,
        tick_seconds=tick_seconds,
        tag=(
            f"PROPERTY-HARD-{tick_seconds}-{start_tick}-{duration_ticks}-"
            f"{resource_index}-{final_remainder}"
        ),
    )
    selected = next(
        option
        for option in problem["operation_instances"][0]["resource_options"]
        if option["resource_id"] == resource_id
    )
    selected["final_duration_seconds"] = authoritative_seconds
    problem["operation_locks"] = cast(
        Any,
        [
            {
                "lock_id": "LOCK-PROPERTY",
                "operation_id": "OP-000",
                "lock_type": "HARD_LOCK",
                "resource_id": resource_id,
                "start_at_utc": _at(problem, start_tick * tick_seconds),
                "end_at_utc": _at(
                    problem, (start_tick + duration_ticks) * tick_seconds
                ),
                "source_system": "TASK-P2-07-PROPERTY",
                "source_version": "1.0.0",
                "source_record_id": "LOCK-PROPERTY",
            }
        ],
    )
    problem["required_capabilities"] = [
        "ALTERNATIVE_RESOURCE",
        "HARD_SOFT_LOCK",
    ]

    result = _solve(problem)
    assignment = result.solution["assignments"][0]

    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"
    assert assignment["resource_id"] == resource_id
    assert assignment["start_tick"] == start_tick
    assert assignment["end_tick"] == start_tick + duration_ticks
    assert assignment["duration_seconds"] == authoritative_seconds
    assert assignment["lock_ids"] == ["LOCK-PROPERTY"]


@seed(20260826)
@settings(max_examples=24, deadline=None)
@given(
    tick_seconds=st.integers(min_value=1, max_value=120),
    remaining_seconds=st.integers(min_value=1, max_value=360),
)
def test_running_and_shifted_hard_lock_conflict_always_fails_precheck(
    tick_seconds: int, remaining_seconds: int
) -> None:
    remaining_ticks = (remaining_seconds + tick_seconds - 1) // tick_seconds
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)]],
        horizon_ticks=remaining_ticks + 3,
        tick_seconds=tick_seconds,
        tag=f"PROPERTY-RUNNING-LOCK-CONFLICT-{tick_seconds}-{remaining_seconds}",
    )
    operation = cast(dict[str, Any], problem["operation_instances"][0])
    operation.update(
        {
            "status": "RUNNING",
            "actual_start_at_utc": _at(problem, -tick_seconds),
            "assigned_resource_id": "RESOURCE-001",
            "remaining_seconds": remaining_seconds,
        }
    )
    problem["operation_locks"] = cast(
        Any,
        [
            {
                "lock_id": "LOCK-CONFLICT",
                "operation_id": "OP-000",
                "lock_type": "HARD_LOCK",
                "resource_id": "RESOURCE-001",
                "start_at_utc": _at(problem, tick_seconds),
                "end_at_utc": _at(problem, (remaining_ticks + 1) * tick_seconds),
                "source_system": "TASK-P2-07-PROPERTY",
                "source_version": "1.0.0",
                "source_record_id": "LOCK-CONFLICT",
            }
        ],
    )
    problem["required_capabilities"] = [
        "HARD_SOFT_LOCK",
        "RUNNING_OPERATION",
    ]
    _rehash(problem)

    with pytest.raises(CoreModelInputError) as captured:
        build_core_model(problem)
    assert captured.value.reason is CoreModelReason.FACT_LOCK_SELF_CONFLICT
