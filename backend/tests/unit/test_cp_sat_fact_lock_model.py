"""TASK-P2-07 execution-fact and HARD/SOFT lock model evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any, cast

import pytest

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import (
    FACT_LOCK_CONSTRAINT_IDS,
    CoreModelInputError,
    CoreModelReason,
    CpSatBackend,
    build_core_model,
    exact_tick_offset,
)
from app.planning.backends.cp_sat.core_model_check import (
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


def _at(problem: PlanningProblemDocumentV2, seconds: int) -> str:
    return format_utc_instant(
        parse_utc_instant(problem["horizon_start_utc"])
        + timedelta(seconds=seconds)
    )


def _rehash(problem: PlanningProblemDocumentV2) -> PlanningProblemDocumentV2:
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    return problem


def _enable(problem: PlanningProblemDocumentV2, *capabilities: str) -> None:
    problem["required_capabilities"] = sorted(
        set(problem["required_capabilities"]) | set(capabilities)
    )


def _make_running(
    problem: PlanningProblemDocumentV2,
    *,
    resource_id: str,
    remaining_seconds: int,
    operation_index: int = 0,
) -> None:
    operation = cast(dict[str, Any], problem["operation_instances"][operation_index])
    operation.update(
        {
            "status": "RUNNING",
            "actual_start_at_utc": _at(problem, -120),
            "assigned_resource_id": resource_id,
            "remaining_seconds": remaining_seconds,
        }
    )
    _enable(problem, "RUNNING_OPERATION")


def _lock(
    problem: PlanningProblemDocumentV2,
    *,
    lock_id: str,
    operation_id: str = "OP-000",
    lock_type: str = "HARD_LOCK",
    resource_id: str = "RESOURCE-001",
    start_seconds: int = 0,
    end_seconds: int = 60,
) -> dict[str, Any]:
    return {
        "lock_id": lock_id,
        "operation_id": operation_id,
        "lock_type": lock_type,
        "resource_id": resource_id,
        "start_at_utc": _at(problem, start_seconds),
        "end_at_utc": _at(problem, end_seconds),
        "source_system": "TASK-P2-07-TEST",
        "source_version": "1.0.0",
        "source_record_id": lock_id,
    }


def _solve(problem: PlanningProblemDocumentV2):
    return CpSatBackend().solve_with_evidence(
        _rehash(problem), synthetic_core_policy(), synthetic_core_limits()
    )


def test_exact_tick_projection_and_fact_lock_model_shape() -> None:
    assert FACT_LOCK_CONSTRAINT_IDS == ("C-007", "C-008")
    assert exact_tick_offset(
        "2026-08-19T23:59:00Z", "2026-08-20T00:00:00Z", 60
    ) == -1
    with pytest.raises(ValueError, match="tick grid"):
        exact_tick_offset(
            "2026-08-20T00:00:01Z", "2026-08-20T00:00:00Z", 60
        )


def test_running_resource_remainder_and_future_occupancy_are_fixed() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 4), ("RESOURCE-002", 1)]],
        horizon_ticks=6,
        tag="UNIT-RUNNING",
    )
    _make_running(problem, resource_id="RESOURCE-002", remaining_seconds=61)

    result = _solve(problem)
    assignment = result.solution["assignments"][0]

    assert result.solution["solver_status"] == "FEASIBLE"
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"
    assert assignment["resource_id"] == "RESOURCE-002"
    assert assignment["start_tick"] == 0
    assert assignment["end_tick"] == 2
    assert assignment["duration_ticks"] == 2
    assert assignment["duration_seconds"] == 61
    assert assignment["execution_fact_ids"] == []
    assert result.telemetry["fact_lock_metrics"] == {
        "running_operations": 1,
        "hard_locks": 0,
        "soft_locks": 0,
        "lock_references": 0,
        "fixed_operation_intervals": 1,
        "resource_fix_constraints": 1,
        "start_fix_constraints": 1,
        "end_fix_constraints": 1,
    }


def test_hard_lock_is_exact_and_soft_lock_remains_metadata_only() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=6,
        tag="UNIT-HARD-SOFT",
    )
    problem["operation_locks"] = cast(
        Any,
        [
            _lock(
                problem,
                lock_id="LOCK-HARD",
                resource_id="RESOURCE-002",
                start_seconds=120,
                end_seconds=180,
            ),
            _lock(
                problem,
                lock_id="LOCK-SOFT",
                lock_type="SOFT_LOCK",
                resource_id="RESOURCE-001",
                start_seconds=240,
                end_seconds=300,
            ),
        ],
    )
    _enable(problem, "HARD_SOFT_LOCK")

    result = _solve(problem)
    assignment = result.solution["assignments"][0]

    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"
    assert (
        assignment["resource_id"],
        assignment["start_tick"],
        assignment["end_tick"],
    ) == ("RESOURCE-002", 2, 3)
    assert assignment["lock_ids"] == ["LOCK-HARD", "LOCK-SOFT"]
    assert result.telemetry["fact_lock_metrics"]["hard_locks"] == 1
    assert result.telemetry["fact_lock_metrics"]["soft_locks"] == 1

    hard_moved = deepcopy(result.solution)
    changed = hard_moved["assignments"][0]
    changed["start_tick"] = 3
    changed["end_tick"] = 4
    changed["start_at_utc"] = _at(problem, 180)
    changed["end_at_utc"] = _at(problem, 240)
    violations = validate_problem_schedule(problem, hard_moved)["violations"]
    assert tuple(item["constraint_id"] for item in violations) == ("C-008",)


def test_soft_lock_can_move_when_its_resource_is_unavailable() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=4,
        tag="UNIT-SOFT-MOVEMENT",
    )
    problem["operation_locks"] = cast(
        Any,
        [
            _lock(
                problem,
                lock_id="LOCK-SOFT",
                lock_type="SOFT_LOCK",
                resource_id="RESOURCE-002",
                start_seconds=120,
                end_seconds=180,
            )
        ],
    )
    problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-002",
            "resource_id": "RESOURCE-002",
            "start_utc": _at(problem, 0),
            "end_utc": _at(problem, 240),
        }
    ]
    _enable(problem, "HARD_SOFT_LOCK", "MACHINE_CALENDAR")

    result = _solve(problem)
    assignment = result.solution["assignments"][0]

    assert assignment["resource_id"] == "RESOURCE-001"
    assert assignment["lock_ids"] == ["LOCK-SOFT"]
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("running-lock", CoreModelReason.FACT_LOCK_SELF_CONFLICT),
        ("hard-duration", CoreModelReason.FACT_LOCK_SELF_CONFLICT),
        ("hard-grid", CoreModelReason.HARD_LOCK_NOT_TICK_ALIGNED),
        ("running-future-start", CoreModelReason.FACT_LOCK_SELF_CONFLICT),
    ],
)
def test_fact_lock_self_conflicts_fail_before_model_build(
    mutation: str, expected_reason: CoreModelReason
) -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=6,
        tag=f"UNIT-PRECHECK-{mutation}",
    )
    if mutation == "running-lock":
        _make_running(problem, resource_id="RESOURCE-001", remaining_seconds=60)
        problem["operation_locks"] = cast(
            Any,
            [
                _lock(
                    problem,
                    lock_id="LOCK-CONFLICT",
                    resource_id="RESOURCE-002",
                )
            ],
        )
        _enable(problem, "HARD_SOFT_LOCK")
    elif mutation == "hard-duration":
        problem["operation_locks"] = cast(
            Any,
            [_lock(problem, lock_id="LOCK-DURATION", end_seconds=120)],
        )
        _enable(problem, "HARD_SOFT_LOCK")
    elif mutation == "hard-grid":
        problem["operation_locks"] = cast(
            Any,
            [
                _lock(
                    problem,
                    lock_id="LOCK-GRID",
                    start_seconds=1,
                    end_seconds=61,
                )
            ],
        )
        _enable(problem, "HARD_SOFT_LOCK")
    else:
        _make_running(problem, resource_id="RESOURCE-001", remaining_seconds=60)
        cast(dict[str, Any], problem["operation_instances"][0])[
            "actual_start_at_utc"
        ] = _at(problem, 1)

    with pytest.raises(CoreModelInputError) as captured:
        build_core_model(_rehash(problem))
    assert captured.value.reason is expected_reason
    assert captured.value.solver_status.value == "MODEL_INVALID"


@pytest.mark.parametrize("mutation", ["calendar", "overlap", "horizon"])
def test_valid_fact_lock_conflicts_are_certified_infeasible(mutation: str) -> None:
    if mutation == "overlap":
        problem = synthetic_core_problem(
            [[("RESOURCE-001", 1)], [("RESOURCE-001", 1)]],
            horizon_ticks=4,
            tag="UNIT-LOCK-OVERLAP",
        )
        problem["operation_locks"] = cast(
            Any,
            [
                _lock(problem, lock_id="LOCK-A", operation_id="OP-000"),
                _lock(problem, lock_id="LOCK-B", operation_id="OP-001"),
            ],
        )
    else:
        problem = synthetic_core_problem(
            [[("RESOURCE-001", 1)]],
            horizon_ticks=4,
            tag=f"UNIT-LOCK-{mutation.upper()}",
        )
        if mutation == "calendar":
            problem["operation_locks"] = cast(
                Any, [_lock(problem, lock_id="LOCK-CALENDAR")]
            )
            problem["resource_unavailable_intervals"] = [
                {
                    "calendar_id": "CAL-RESOURCE-001",
                    "resource_id": "RESOURCE-001",
                    "start_utc": _at(problem, 0),
                    "end_utc": _at(problem, 60),
                }
            ]
            _enable(problem, "MACHINE_CALENDAR")
        else:
            problem["operation_locks"] = cast(
                Any,
                [
                    _lock(
                        problem,
                        lock_id="LOCK-HORIZON",
                        start_seconds=240,
                        end_seconds=300,
                    )
                ],
            )
    _enable(problem, "HARD_SOFT_LOCK")

    result = _solve(problem)

    assert result.solution["solver_status"] == "INFEASIBLE"
    assert result.solution["assignments"] == []
    assert result.validation_report is None


def test_running_mutation_is_independently_rejected_as_c007() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=4,
        tag="UNIT-RUNNING-MUTATION",
    )
    _make_running(problem, resource_id="RESOURCE-001", remaining_seconds=60)
    result = _solve(problem)
    moved = deepcopy(result.solution)
    moved["assignments"][0]["resource_id"] = "RESOURCE-002"

    violations = validate_problem_schedule(problem, moved)["violations"]

    assert tuple(item["constraint_id"] for item in violations) == ("C-007",)
