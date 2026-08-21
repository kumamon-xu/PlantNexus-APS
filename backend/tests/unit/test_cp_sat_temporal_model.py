"""TASK-P2-06 exact temporal/calendar/material CP-SAT model evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any, cast

import pytest

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import CoreModelInputError, CoreModelReason, CpSatBackend
from app.planning.backends.cp_sat.core_model_check import (
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.backends.cp_sat.temporal_constraints import (
    TEMPORAL_CONSTRAINT_IDS,
    calendar_tick_blocks,
    ceil_seconds_to_ticks,
    floor_seconds_to_ticks,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import validate_problem_schedule


def _at(problem: PlanningProblemDocumentV2, seconds: int) -> str:
    return format_utc_instant(
        parse_utc_instant(problem["horizon_start_utc"])
        + timedelta(seconds=seconds)
    )


def _rehash(problem: PlanningProblemDocumentV2) -> PlanningProblemDocumentV2:
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    return problem


def _edge(
    *,
    predecessor: str = "OP-000",
    successor: str = "OP-001",
    minimum: int = 0,
    transport: int = 0,
    maximum: int | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "precedence_edge_id": "EDGE-TEMPORAL-001",
        "predecessor_operation_id": predecessor,
        "successor_operation_id": successor,
        "min_lag_seconds": minimum,
        "transport_lag_seconds": transport,
    }
    if maximum is not None:
        value["max_lag_seconds"] = maximum
    return value


def _two_resource_problem(
    *, horizon_ticks: int = 8, tick_seconds: int = 60
) -> PlanningProblemDocumentV2:
    return synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-002", 1)]],
        horizon_ticks=horizon_ticks,
        tick_seconds=tick_seconds,
        tag="UNIT-TEMPORAL",
    )


def test_signed_tick_rounding_and_calendar_projection_are_exact() -> None:
    assert ceil_seconds_to_ticks(61, 60) == 2
    assert floor_seconds_to_ticks(119, 60) == 1
    assert ceil_seconds_to_ticks(-61, 60) == -1
    assert floor_seconds_to_ticks(-61, 60) == -2

    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=5, tag="UNIT-CALENDAR-PROJECTION"
    )
    problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(problem, 61),
            "end_utc": _at(problem, 119),
        },
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(problem, 118),
            "end_utc": _at(problem, 181),
        },
    ]
    _rehash(problem)

    assert calendar_tick_blocks(problem, horizon_ticks=5) == {
        "RESOURCE-001": ((1, 4),)
    }


def test_min_uses_ceil_max_uses_floor_and_never_relaxes_window() -> None:
    impossible = _two_resource_problem()
    impossible["precedence_edges"] = [
        cast(Any, _edge(minimum=61, maximum=119))
    ]
    _rehash(impossible)
    result = CpSatBackend().solve_with_evidence(
        impossible, synthetic_core_policy(), synthetic_core_limits()
    )
    assert result.solution["solver_status"] == "INFEASIBLE"
    assert result.validation_report is None

    exact = _two_resource_problem()
    exact["precedence_edges"] = [cast(Any, _edge(minimum=61, maximum=120))]
    _rehash(exact)
    exact_result = CpSatBackend().solve_with_evidence(
        exact, synthetic_core_policy(), synthetic_core_limits()
    )
    assert exact_result.solution["solver_status"] == "FEASIBLE"
    by_id = {
        assignment["operation_id"]: assignment
        for assignment in exact_result.solution["assignments"]
    }
    observed = (
        by_id["OP-001"]["start_tick"] - by_id["OP-000"]["end_tick"]
    ) * exact["tick_seconds"]
    assert observed == 120
    assert exact_result.validation_report is not None
    assert exact_result.validation_report["status"] == "PASS"


def test_release_material_and_half_open_calendar_boundaries_are_enforced() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=6, tag="UNIT-GATE-CALENDAR"
    )
    operation = problem["operation_instances"][0]
    operation["release_at_utc"] = _at(problem, 61)
    operation["material_ready_at_utc"] = _at(problem, 119)
    problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(problem, 120),
            "end_utc": _at(problem, 180),
        }
    ]
    _rehash(problem)

    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    assignment = result.solution["assignments"][0]
    assert assignment["start_tick"] >= 3
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"
    assert build_core_model(problem).temporal_metrics == {
        "precedence_edges": 0,
        "precedence_min_constraints": 0,
        "precedence_max_constraints": 0,
        "calendar_input_intervals": 1,
        "calendar_fixed_intervals": 1,
        "release_gate_constraints": 1,
        "material_gate_constraints": 1,
        "transport_conditional_constraints": 0,
    }

    before = deepcopy(problem)
    before["operation_instances"][0]["release_at_utc"] = _at(before, 60)
    before["operation_instances"][0]["material_ready_at_utc"] = _at(before, 0)
    _rehash(before)
    before_solution = CpSatBackend().solve(
        before, synthetic_core_policy(), synthetic_core_limits()
    )
    assert before_solution["assignments"][0]["start_tick"] == 1
    assert before_solution["assignments"][0]["end_tick"] == 2


def test_transport_is_conditional_independent_and_not_added_to_min_lag() -> None:
    problem = _two_resource_problem(horizon_ticks=5)
    problem["resources"][0]["workshop_id"] = "WORKSHOP-A"
    problem["resources"][1]["workshop_id"] = "WORKSHOP-B"
    problem["precedence_edges"] = [
        cast(Any, _edge(minimum=61, transport=121, maximum=180))
    ]
    _rehash(problem)

    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    assert result.solution["solver_status"] == "FEASIBLE"
    by_id = {
        assignment["operation_id"]: assignment
        for assignment in result.solution["assignments"]
    }
    observed = (
        by_id["OP-001"]["start_tick"] - by_id["OP-000"]["end_tick"]
    ) * problem["tick_seconds"]
    assert observed == 180
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"

    same_workshop = deepcopy(problem)
    same_workshop["resources"][1]["workshop_id"] = "WORKSHOP-A"
    same_workshop["precedence_edges"] = [
        cast(Any, _edge(minimum=0, transport=300, maximum=0))
    ]
    _rehash(same_workshop)
    same_result = CpSatBackend().solve_with_evidence(
        same_workshop, synthetic_core_policy(), synthetic_core_limits()
    )
    assert same_result.solution["solver_status"] == "FEASIBLE"
    assert same_result.validation_report is not None
    assert same_result.validation_report["status"] == "PASS"


def test_historical_anchor_uses_absolute_inclusive_lag_and_workshop_transport() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-002", 1)]], horizon_ticks=4, tag="UNIT-ANCHOR"
    )
    problem["resources"].append(
        {
            "resource_id": "RESOURCE-001",
            "resource_code": "RESOURCE-001",
            "resource_type": "MACHINE",
            "status": "AVAILABLE",
            "factory_id": "FACTORY-CORE",
            "workshop_id": "WORKSHOP-A",
            "production_line_id": "LINE-CORE",
            "resource_group_id": "GROUP-CORE",
            "calendar_id": "CAL-RESOURCE-001",
            "capabilities": ["CORE"],
            "capacity": 1,
        }
    )
    problem["resources"][0]["workshop_id"] = "WORKSHOP-B"
    problem["resources"].sort(key=lambda resource: resource["resource_id"])
    problem["historical_completion_anchors"] = [
        {
            "operation_id": "OP-HISTORICAL",
            "execution_fact_id": "FACT-HISTORICAL",
            "resource_id": "RESOURCE-001",
            "actual_start_at_utc": _at(problem, -90),
            "actual_end_at_utc": _at(problem, -30),
            "source_system": "TASK-P2-06-TEST",
            "source_version": "1.0.0",
            "source_record_id": "FACT-HISTORICAL",
        }
    ]
    problem["precedence_edges"] = [
        cast(
            Any,
            _edge(
                predecessor="OP-HISTORICAL",
                successor="OP-000",
                minimum=31,
                transport=61,
                maximum=90,
            ),
        )
    ]
    _rehash(problem)

    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    assert result.solution["assignments"][0]["start_tick"] == 1
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"


def test_temporal_validator_mutation_and_fail_closed_precision_and_overflow() -> None:
    problem = _two_resource_problem(horizon_ticks=5)
    problem["resources"][0]["workshop_id"] = "WORKSHOP-A"
    problem["resources"][1]["workshop_id"] = "WORKSHOP-B"
    problem["precedence_edges"] = [
        cast(Any, _edge(minimum=61, transport=121, maximum=180))
    ]
    _rehash(problem)
    solution = CpSatBackend().solve(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    by_id = {
        assignment["operation_id"]: assignment for assignment in solution["assignments"]
    }
    mutated = deepcopy(solution)
    mutated_by_id = {
        assignment["operation_id"]: assignment
        for assignment in mutated["assignments"]
    }
    predecessor_end = by_id["OP-000"]["end_tick"]
    successor = mutated_by_id["OP-001"]
    successor["start_tick"] = predecessor_end
    successor["end_tick"] = predecessor_end + successor["duration_ticks"]
    successor["start_at_utc"] = _at(problem, successor["start_tick"] * 60)
    successor["end_at_utc"] = _at(problem, successor["end_tick"] * 60)
    violations = {
        item["constraint_id"] for item in validate_problem_schedule(problem, mutated)["violations"]
    }
    assert {"C-002", "C-009"}.issubset(violations)

    fractional = _two_resource_problem()
    fractional["operation_instances"][0]["release_at_utc"] = (
        "2026-08-20T00:00:00.500000Z"
    )
    _rehash(fractional)
    with pytest.raises(CoreModelInputError) as fractional_error:
        build_core_model(fractional)
    assert (
        fractional_error.value.reason
        is CoreModelReason.TEMPORAL_INSTANT_NOT_SECOND_PRECISION
    )

    overflow = _two_resource_problem()
    overflow["precedence_edges"] = [
        cast(Any, _edge(minimum=((1 << 63) + 1) * 60))
    ]
    _rehash(overflow)
    with pytest.raises(CoreModelInputError) as overflow_error:
        build_core_model(overflow)
    assert overflow_error.value.reason is CoreModelReason.TICK_VALUE_OUT_OF_RANGE
    assert TEMPORAL_CONSTRAINT_IDS == ("C-002", "C-005", "C-006", "C-009")
