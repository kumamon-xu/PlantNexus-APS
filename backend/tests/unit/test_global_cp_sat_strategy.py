"""TASK-P2-08 OBJ-001, GlobalCpSatStrategy, status, and report evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any, cast

import pytest
from ortools.sat.python import cp_model

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import backend as backend_module
from app.planning.backends.cp_sat.core_model_check import synthetic_core_problem
from app.planning.backends.cp_sat.objectives import (
    DeliveryObjectiveError,
    DeliveryObjectiveReason,
)
from app.planning.contracts import validate_contract_bundle
from app.planning.policy.contracts import PlanningPolicyDocument, SolveLimitsDocument
from app.planning.policy.delivery import (
    DeliveryPolicyError,
    DeliveryPolicyReason,
    SIMULATION_DELIVERY_SOURCE_SYSTEM,
    SIMULATION_DELIVERY_SOURCE_VERSION,
    simulation_delivery_policy,
    simulation_solve_limits,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.strategies import GlobalCpSatStrategy


def _limits(*, wall_time: float = 3.0) -> SolveLimitsDocument:
    return simulation_solve_limits(
        limits_id="LIMITS-TASK-P2-08-UNIT",
        limits_revision="1.0.0",
        source_record_id="LIMITS-TASK-P2-08-UNIT",
        max_wall_time_seconds=wall_time,
        max_workers=1,
        random_seed=20260821,
    )


def delivery_problem(
    durations: list[int],
    due_ticks: list[int],
    weights: list[int],
    *,
    tick_seconds: int = 60,
    horizon_ticks: int | None = None,
    tag: str = "DELIVERY",
) -> PlanningProblemDocumentV2:
    """Create independent one-operation demands sharing one unary resource."""

    if not (len(durations) == len(due_ticks) == len(weights)):
        raise ValueError("delivery vectors must have equal lengths")
    horizon = sum(durations) if horizon_ticks is None else horizon_ticks
    problem = synthetic_core_problem(
        [[("RESOURCE-001", duration)] for duration in durations],
        horizon_ticks=horizon,
        tick_seconds=tick_seconds,
        tag=tag,
    )
    horizon_start = parse_utc_instant(problem["horizon_start_utc"])
    template = problem["delivery_demands"][0]
    demands = []
    for index, (due_tick, weight) in enumerate(zip(due_ticks, weights, strict=True)):
        demand_id = f"DEMAND-{index:03d}"
        demand = deepcopy(template)
        demand.update(
            {
                "demand_order_id": demand_id,
                "due_at_utc": format_utc_instant(
                    horizon_start + timedelta(seconds=due_tick * tick_seconds)
                ),
                "due_source_record_id": f"DUE-{tag}-{index:03d}",
                "priority_weight": weight,
                "priority_source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
                "priority_source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
                "priority_source_record_id": f"PRIORITY-{tag}-{index:03d}",
            }
        )
        demands.append(demand)
        problem["operation_instances"][index]["demand_order_id"] = demand_id
    problem["delivery_demands"] = demands
    problem["problem_hash"] = problem_v2_hash_for(
        cast(dict[str, object], problem)
    )
    return problem


def _solve(problem: PlanningProblemDocumentV2):  # type: ignore[no-untyped-def]
    policy = simulation_delivery_policy()
    limits = _limits()
    result = GlobalCpSatStrategy().solve(
        problem,
        policy,
        limits,
        planning_run_id="PLANNING-RUN-TASK-P2-08-UNIT",
        code_commit="uncommitted",
    )
    validate_contract_bundle(policy, limits, result.solution, result.solver_report)
    return result


def test_weighted_tardiness_changes_the_global_sequence_and_is_proven() -> None:
    problem = delivery_problem([2, 2], [2, 2], [1, 3], tag="PRIORITY")
    result = _solve(problem)
    by_operation = {
        assignment["operation_id"]: assignment
        for assignment in result.solution["assignments"]
    }
    stage = result.solution["objective_stage_results"][0]

    assert result.solution["solver_status"] == "OPTIMAL"
    assert by_operation["OP-001"]["start_tick"] == 0
    assert by_operation["OP-000"]["end_tick"] == 4
    assert stage == {
        "stage_index": 1,
        "objective_id": "OBJ-001",
        "metric": "WEIGHTED_TARDINESS",
        "sense": "MINIMIZE",
        "status": "OPTIMAL",
        "objective_value": 120,
        "best_bound": 120,
        "relative_gap": 0.0,
        "allocated_wall_time_seconds": 3.0,
        "solve_seconds": stage["solve_seconds"],
        "stop_reason": "OBJ001_OPTIMALITY_PROVEN",
    }
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"
    assert result.solver_report["solver_status"] == "OPTIMAL"
    assert result.solver_report["provenance"]["code_commit"] == "uncommitted"
    assert result.solver_report["model_metrics"]["variables"] > 0
    assert result.solver_report["timings"]["validation_seconds"] is not None


def test_due_after_horizon_has_exact_zero_objective_and_replayable_report() -> None:
    result = _solve(delivery_problem([1, 2], [4, 4], [2, 5], tag="ZERO"))
    stage = result.solution["objective_stage_results"][0]

    assert result.solution["solver_status"] == "OPTIMAL"
    assert stage["objective_value"] == stage["best_bound"] == 0
    assert stage["relative_gap"] == 0
    parameter_names = [
        parameter["name"] for parameter in result.solver_report["solver"]["parameters"]
    ]
    assert parameter_names == sorted(parameter_names)
    assert {
        "max_wall_time_seconds",
        "max_workers",
        "random_seed",
        "max_time_in_seconds",
        "num_search_workers",
        "log_search_progress",
    } == set(parameter_names)


def test_complete_hard_domain_can_prove_infeasible_without_candidate() -> None:
    result = _solve(
        delivery_problem(
            [3, 3],
            [4, 4],
            [1, 1],
            horizon_ticks=4,
            tag="INFEASIBLE",
        )
    )

    assert result.solution["solver_status"] == "INFEASIBLE"
    assert result.solution["assignments"] == []
    assert result.validation_report is None
    assert result.solver_report["planning_run_outcome"]["state"] == "INFEASIBLE"
    assert result.solver_report["timings"]["first_feasible_seconds"] is None


def test_limit_without_candidate_remains_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnknownSolver:
        wall_time = 0.0
        best_objective_bound = 0.0

        def solve(self, model: object, observer: object) -> cp_model.CpSolverStatus:
            del model, observer
            return cp_model.UNKNOWN

    monkeypatch.setattr(
        backend_module,
        "_configured_solver",
        lambda limits: cast(Any, UnknownSolver()),
    )
    result = _solve(delivery_problem([1], [0], [1], tag="UNKNOWN"))

    assert result.solution["solver_status"] == "UNKNOWN"
    assert result.solution["assignments"] == []
    assert result.solution["objective_stage_results"][0]["best_bound"] == 0
    assert result.solver_report["planning_run_outcome"] == {
        "state": "NO_SOLUTION_WITHIN_LIMIT",
        "product_error": {
            "category": "NO_SOLUTION_WITHIN_LIMIT",
            "code": "NO_SOLUTION_WITHIN_LIMIT",
        },
    }


def test_stopped_search_with_candidate_is_feasible_not_optimal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def first_solution_solver(limits: SolveLimitsDocument) -> cp_model.CpSolver:
        solver = cp_model.CpSolver()
        solver.parameters.log_search_progress = False
        solver.parameters.max_time_in_seconds = limits["max_wall_time_seconds"]
        solver.parameters.num_search_workers = limits["max_workers"]
        solver.parameters.random_seed = limits["random_seed"]
        solver.parameters.stop_after_first_solution = True
        return solver

    monkeypatch.setattr(backend_module, "_configured_solver", first_solution_solver)
    result = _solve(delivery_problem([2, 2], [0, 0], [1, 3], tag="FEASIBLE"))
    stage = result.solution["objective_stage_results"][0]

    assert result.solution["solver_status"] == "FEASIBLE"
    assert stage["status"] == "FEASIBLE"
    assert isinstance(stage["best_bound"], int)
    assert isinstance(stage["objective_value"], int)
    assert stage["best_bound"] <= stage["objective_value"]
    assert stage["stop_reason"] == "OBJ001_FEASIBLE_CANDIDATE_OPTIMALITY_NOT_PROVEN"
    assert result.validation_report is not None
    assert result.validation_report["status"] == "PASS"


def test_validator_failure_discards_an_optimized_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        backend_module,
        "validate_problem_schedule",
        lambda problem, solution: cast(Any, {"status": "FAIL"}),
    )
    result = _solve(delivery_problem([1], [0], [1], tag="VALIDATOR-FAIL"))

    assert result.solution["solver_status"] == "FAILED"
    assert result.solution["assignments"] == []
    assert result.solution["objective_stage_results"][0]["objective_value"] is None
    assert result.solver_report["planning_run_outcome"]["state"] == "FAILED"
    assert result.solver_report["timings"]["first_feasible_seconds"] is None


def test_only_approved_simulation_policy_and_priority_source_can_run() -> None:
    problem = delivery_problem([1], [1], [1], tag="POLICY")
    production_policy = cast(
        PlanningPolicyDocument, deepcopy(simulation_delivery_policy())
    )
    production_limits = cast(SolveLimitsDocument, deepcopy(_limits()))
    production_policy["data_plane"] = "PRODUCTION"
    production_limits["data_plane"] = "PRODUCTION"
    with pytest.raises(DeliveryPolicyError) as production_error:
        GlobalCpSatStrategy().solve(
            problem,
            production_policy,
            production_limits,
            planning_run_id="RUN-PRODUCTION-BLOCKED",
            code_commit="uncommitted",
        )
    assert (
        production_error.value.reason
        is DeliveryPolicyReason.PRODUCTION_NOT_AUTHORIZED
    )

    mismatched_limits = cast(SolveLimitsDocument, deepcopy(_limits()))
    mismatched_limits["data_plane"] = "PRODUCTION"
    with pytest.raises(DeliveryPolicyError) as mismatch_error:
        GlobalCpSatStrategy().solve(
            problem,
            simulation_delivery_policy(),
            mismatched_limits,
            planning_run_id="RUN-DATA-PLANE-MISMATCH",
            code_commit="uncommitted",
        )
    assert mismatch_error.value.reason is DeliveryPolicyReason.DATA_PLANE_MISMATCH

    wrong_limits_source = cast(SolveLimitsDocument, deepcopy(_limits()))
    wrong_limits_source["limits_source"]["source_version"] = "2.0.0"
    with pytest.raises(DeliveryPolicyError) as limits_source_error:
        GlobalCpSatStrategy().solve(
            problem,
            simulation_delivery_policy(),
            wrong_limits_source,
            planning_run_id="RUN-LIMITS-SOURCE-BLOCKED",
            code_commit="uncommitted",
        )
    assert (
        limits_source_error.value.reason
        is DeliveryPolicyReason.UNAPPROVED_LIMITS_SOURCE
    )

    wrong_source = deepcopy(problem)
    wrong_source["delivery_demands"][0]["priority_source_version"] = "2.0.0"
    wrong_source["problem_hash"] = problem_v2_hash_for(
        cast(dict[str, object], wrong_source)
    )
    with pytest.raises(DeliveryPolicyError) as source_error:
        _solve(wrong_source)
    assert source_error.value.reason is DeliveryPolicyReason.UNAPPROVED_PRIORITY_SOURCE


def test_objective_int64_overflow_fails_before_solver_search() -> None:
    problem = delivery_problem([1], [0], [1 << 63], tag="OVERFLOW")
    with pytest.raises(DeliveryObjectiveError) as captured:
        _solve(problem)
    assert captured.value.reason is DeliveryObjectiveReason.OBJECTIVE_INTEGER_OVERFLOW


def test_strategy_makes_exactly_one_global_backend_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = backend_module.CpSatBackend()
    original = backend.solve_delivery_with_evidence
    calls = 0

    def counted(
        problem: PlanningProblemDocumentV2,
        policy: PlanningPolicyDocument,
        limits: SolveLimitsDocument,
    ):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(problem, policy, limits)

    monkeypatch.setattr(backend, "solve_delivery_with_evidence", counted)
    result = GlobalCpSatStrategy(backend).solve(
        delivery_problem([1, 1], [2, 2], [1, 1], tag="ONE-CALL"),
        simulation_delivery_policy(),
        _limits(),
        planning_run_id="RUN-ONE-GLOBAL-CALL",
        code_commit="0" * 40,
    )

    assert calls == 1
    assert result.solution["solver_status"] == "OPTIMAL"
    assert result.solver_report["provenance"]["code_commit"] == "0" * 40
