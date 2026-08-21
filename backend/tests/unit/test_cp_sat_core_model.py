"""TASK-P2-05 core CP-SAT model, mapping, and Validator evidence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from app.planning.backends.cp_sat import (
    CORE_CONSTRAINT_IDS,
    CoreModelInputError,
    CoreModelReason,
    CpSatBackend,
    build_core_model,
    precheck_core_problem,
)
from app.planning.backends.cp_sat.core_model_check import (
    run_core_model_checks,
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.contracts import validate_planning_solution
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


ROOT = Path(__file__).resolve().parents[3]


def _jssp() -> PlanningProblemDocumentV2:
    return synthetic_core_problem(
        [
            [("RESOURCE-001", 2)],
            [("RESOURCE-001", 3)],
            [("RESOURCE-001", 1)],
        ],
        horizon_ticks=6,
        tag="UNIT-JSSP",
    )


def _fjsp() -> PlanningProblemDocumentV2:
    return synthetic_core_problem(
        [
            [("RESOURCE-001", 2), ("RESOURCE-002", 3)],
            [("RESOURCE-001", 3), ("RESOURCE-002", 1)],
        ],
        horizon_ticks=6,
        tag="UNIT-FJSP",
    )


def test_core_model_has_exact_five_cid_shape_and_no_objective() -> None:
    jssp_model = build_core_model(_jssp())
    fjsp_model = build_core_model(_fjsp())

    assert CORE_CONSTRAINT_IDS == ("C-001", "C-003", "C-004", "C-010", "C-011")
    assert jssp_model.metrics == {
        "variables": 9,
        "constraints": 7,
        "optional_intervals": 3,
    }
    assert fjsp_model.metrics == {
        "variables": 8,
        "constraints": 8,
        "optional_intervals": 4,
    }
    assert not jssp_model.model.has_objective()
    assert not fjsp_model.model.has_objective()


def test_tight_jssp_is_complete_back_to_back_and_formally_valid() -> None:
    problem = _jssp()
    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    solution = result.solution

    validate_planning_solution(cast(dict[str, object], solution))
    assert solution["solver_status"] == "FEASIBLE"
    assert result.telemetry["native_status"] == "OPTIMAL"
    assert result.telemetry["solver_status"] == "FEASIBLE"
    assert result.telemetry["objective_optimized"] is False
    assert result.validation_report is not None
    assert result.validation_report == validate_problem_schedule(problem, solution)
    assert result.validation_report["status"] == "PASS"
    assert len(solution["assignments"]) == 3
    ordered = sorted(solution["assignments"], key=lambda item: item["start_tick"])
    assert ordered[0]["start_tick"] == 0
    assert ordered[-1]["end_tick"] == 6
    assert all(
        left["end_tick"] == right["start_tick"]
        for left, right in zip(ordered, ordered[1:])
    )


def test_fjsp_selects_one_candidate_with_its_own_duration() -> None:
    problem = _fjsp()
    solution = CpSatBackend().solve(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )

    assert solution["solver_status"] == "FEASIBLE"
    assert len(solution["assignments"]) == len(problem["operation_instances"])
    operation_by_id = {
        operation["operation_id"]: operation
        for operation in problem["operation_instances"]
    }
    for assignment in solution["assignments"]:
        operation = operation_by_id[assignment["operation_id"]]
        option = next(
            item
            for item in operation["resource_options"]
            if item["resource_id"] == assignment["resource_id"]
        )
        assert assignment["duration_seconds"] == option["final_duration_seconds"]
        assert assignment["duration_ticks"] == (
            option["final_duration_seconds"] + problem["tick_seconds"] - 1
        ) // problem["tick_seconds"]
        assert assignment["end_tick"] <= 6
    assert validate_problem_schedule(problem, solution)["status"] == "PASS"


def test_core_feasibility_downgrades_native_optimal_and_measures_without_optimizing() -> None:
    problem = _fjsp()
    problem["delivery_demands"][0]["due_at_utc"] = problem["horizon_start_utc"]
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    first = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    second = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )

    assert first.telemetry["native_status"] == second.telemetry["native_status"] == "OPTIMAL"
    assert first.solution["solver_status"] == second.solution["solver_status"] == "FEASIBLE"
    assert first.solution["solution_id"] == second.solution["solution_id"]
    assert first.solution["assignments"] == second.solution["assignments"]
    stage = first.solution["objective_stage_results"][0]
    assert stage["status"] == "FEASIBLE"
    assert stage["objective_value"] is not None
    assert stage["objective_value"] > 0
    assert stage["best_bound"] == 0
    assert stage["relative_gap"] == 1
    assert "OBJECTIVE_NOT_OPTIMIZED" in stage["stop_reason"]
    assert not build_core_model(problem).model.has_objective()


def test_unary_overload_is_infeasible_without_partial_candidate() -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 4)], [("RESOURCE-001", 4)]],
        horizon_ticks=6,
        tag="UNIT-INFEASIBLE",
    )
    result = CpSatBackend().solve_with_evidence(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )

    assert result.solution["solver_status"] == "INFEASIBLE"
    assert result.solution["assignments"] == []
    assert result.validation_report is None
    assert result.telemetry["first_feasible_seconds"] is None
    assert result.telemetry["validator_status"] is None
    assert result.solution["planning_run_outcome"] == {
        "state": "INFEASIBLE",
        "product_error": {"category": "INFEASIBLE", "code": "INFEASIBLE"},
    }


def test_zero_candidate_and_horizon_overflow_fail_before_model_construction() -> None:
    zero = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=2, tag="UNIT-ZERO"
    )
    zero["operation_instances"][0]["resource_options"] = []
    with pytest.raises(CoreModelInputError) as zero_error:
        precheck_core_problem(cast(dict[str, object], zero))
    assert zero_error.value.reason is CoreModelReason.ZERO_RESOURCE_OPTIONS
    assert zero_error.value.solver_status.value == "MODEL_INVALID"
    with pytest.raises(CoreModelInputError) as backend_zero_error:
        CpSatBackend().solve(zero, synthetic_core_policy(), synthetic_core_limits())
    assert backend_zero_error.value.reason is CoreModelReason.ZERO_RESOURCE_OPTIONS

    overflow = synthetic_core_problem(
        [[("RESOURCE-001", 7)]], horizon_ticks=6, tag="UNIT-OVERFLOW"
    )
    with pytest.raises(CoreModelInputError) as overflow_error:
        build_core_model(overflow)
    assert overflow_error.value.reason is CoreModelReason.DURATION_EXCEEDS_HORIZON
    assert overflow_error.value.diagnostic()["code"].endswith(
        "DURATION_EXCEEDS_HORIZON"
    )


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("running", CoreModelReason.UNSUPPORTED_RUNNING_FACT),
        ("lock", CoreModelReason.UNSUPPORTED_LOCK_FACT),
    ],
)
def test_still_deferred_p2_07_facts_are_rejected_not_silently_ignored(
    mutation: str, expected_reason: CoreModelReason
) -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-001", 1)]],
        horizon_ticks=6,
        tag=f"UNIT-FUTURE-{mutation}",
    )
    first = cast(dict[str, Any], problem["operation_instances"][0])
    if mutation == "running":
        first.update(
            {
                "status": "RUNNING",
                "actual_start_at_utc": "2026-08-19T23:59:00Z",
                "assigned_resource_id": "RESOURCE-001",
                "remaining_seconds": 60,
            }
        )
    else:
        problem["operation_locks"] = [
            {
                "lock_id": "LOCK-001",
                "operation_id": "OP-000",
                "lock_type": "HARD_LOCK",
                "resource_id": "RESOURCE-001",
                "start_at_utc": "2026-08-20T00:00:00Z",
                "end_at_utc": "2026-08-20T00:01:00Z",
                "source_system": "TASK-P2-05-TEST",
                "source_version": "1.0.0",
                "source_record_id": "LOCK-001",
            }
        ]

    with pytest.raises(CoreModelInputError) as captured:
        build_core_model(problem)
    assert captured.value.reason is expected_reason


def test_independent_validator_rejects_missing_and_wrong_duration_mutations() -> None:
    problem = _jssp()
    solution = CpSatBackend().solve(
        problem, synthetic_core_policy(), synthetic_core_limits()
    )
    missing = deepcopy(solution)
    missing["assignments"].pop()
    wrong_duration = deepcopy(solution)
    wrong_duration["assignments"][0]["duration_seconds"] += 1

    assert tuple(
        item["constraint_id"]
        for item in validate_problem_schedule(problem, missing)["violations"]
    ) == ("C-001",)
    assert tuple(
        item["constraint_id"]
        for item in validate_problem_schedule(problem, wrong_duration)["violations"]
    ) == ("C-010",)


def test_core_machine_report_is_complete_and_telemetry_is_real() -> None:
    report = run_core_model_checks(ROOT)

    assert report["report_version"] == "cp-sat-core-model-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-05"
    assert report["check_count"] == 6
    assert report["counts"] == {
        "core_constraint_ids": 5,
        "candidate_cases": 2,
        "infeasible_cases": 1,
        "precheck_rejections": 2,
        "validator_mutations": 2,
        "brute_force_cases": 4,
    }
    assert report["boundaries"]["objective"] == (
        "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED"
    )
    assert report["boundaries"]["benchmark"] == (
        "TINY_CORRECTNESS_ONLY_NO_XS_S_M_BASELINE"
    )
