"""Map CP-SAT core outcomes to the solver-neutral PlanningSolution contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from hashlib import sha256
import math
from typing import cast

from ortools.sat.python import cp_model

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.model import CoreCpSatModel
from app.planning.contracts import (
    CANONICALIZATION_VERSION,
    PLANNING_SOLUTION_VERSION,
    SCHEMA_SET_VERSION,
    DiagnosticDocument,
    LimitsReferenceDocument,
    ObjectiveStageResultDocument,
    OperationAssignmentDocument,
    PlanningSolutionDocument,
    PolicyReferenceDocument,
    ProblemReferenceDocument,
    SolverStatus,
    canonical_contract_bytes,
    contract_fingerprint,
    outcome_document_for_status,
    validate_planning_solution,
)
from app.planning.policy.contracts import PlanningPolicyDocument, SolveLimitsDocument
from app.planning.problem.contracts import PlanningProblemDocumentV2


def _problem_reference(problem: PlanningProblemDocumentV2) -> ProblemReferenceDocument:
    return {
        "problem_version": problem["problem_version"],
        "problem_builder_version": problem["problem_builder_version"],
        "problem_hash_projection_version": problem["problem_hash_projection_version"],
        "problem_hash": problem["problem_hash"],
        "snapshot_id": problem["snapshot_id"],
        "tick_seconds": problem["tick_seconds"],
        "horizon_start_utc": problem["horizon_start_utc"],
        "horizon_end_utc": problem["horizon_end_utc"],
    }


def _policy_reference(policy: PlanningPolicyDocument) -> PolicyReferenceDocument:
    return {
        "planning_policy_version": policy["planning_policy_version"],
        "policy_id": policy["policy_id"],
        "policy_revision": policy["policy_revision"],
        "policy_fingerprint": contract_fingerprint(cast(Mapping[str, object], policy)),
    }


def _limits_reference(limits: SolveLimitsDocument) -> LimitsReferenceDocument:
    return {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(cast(Mapping[str, object], limits)),
        "max_wall_time_seconds": float(limits["max_wall_time_seconds"]),
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }


def _solution_id(payload: Mapping[str, object]) -> str:
    digest = sha256(canonical_contract_bytes(payload)).hexdigest()
    return f"planning-solution-core-{digest}"


def _assignments(
    problem: PlanningProblemDocumentV2,
    core_model: CoreCpSatModel,
    solver: cp_model.CpSolver,
) -> list[OperationAssignmentDocument]:
    horizon_start = parse_utc_instant(problem["horizon_start_utc"])
    tick_seconds = problem["tick_seconds"]
    assignments: list[OperationAssignmentDocument] = []
    for operation in core_model.operations:
        selected = [
            option for option in operation.options if solver.value(option.presence) == 1
        ]
        if len(selected) != 1:
            raise ValueError("CP-SAT candidate does not select exactly one core option")
        option = selected[0]
        start_tick = int(solver.value(operation.start))
        end_tick = int(solver.value(operation.end))
        assignments.append(
            {
                "operation_id": operation.operation_id,
                "resource_id": option.resource_id,
                "start_tick": start_tick,
                "end_tick": end_tick,
                "duration_ticks": option.duration_ticks,
                "start_at_utc": format_utc_instant(
                    horizon_start + timedelta(seconds=start_tick * tick_seconds)
                ),
                "end_at_utc": format_utc_instant(
                    horizon_start + timedelta(seconds=end_tick * tick_seconds)
                ),
                "duration_seconds": option.duration_seconds,
                "lock_ids": [],
                "execution_fact_ids": [],
            }
        )
    assignments.sort(key=lambda assignment: assignment["operation_id"])
    return assignments


def _measured_weighted_tardiness_seconds(
    problem: PlanningProblemDocumentV2,
    assignments: list[OperationAssignmentDocument],
) -> int:
    """Measure the candidate only; this does not add or optimize OBJ-001."""

    demand_by_operation = {
        operation["operation_id"]: operation["demand_order_id"]
        for operation in problem["operation_instances"]
    }
    completion_by_demand: dict[str, datetime] = {}
    for assignment in assignments:
        demand_id = demand_by_operation[assignment["operation_id"]]
        completion = parse_utc_instant(assignment["end_at_utc"])
        previous = completion_by_demand.get(demand_id)
        if previous is None or completion > previous:
            completion_by_demand[demand_id] = completion

    total = 0
    for demand in problem["delivery_demands"]:
        completion_value = completion_by_demand.get(demand["demand_order_id"])
        if completion_value is None:
            continue
        completion = completion_value
        due = parse_utc_instant(demand["due_at_utc"])
        tardiness_seconds = max(
            0, math.ceil((completion - due).total_seconds())
        )
        total += demand["priority_weight"] * tardiness_seconds
    return total


def _candidate_stage(
    *,
    limits: SolveLimitsDocument,
    solve_seconds: float,
    objective_value: int,
    native_status: str,
) -> ObjectiveStageResultDocument:
    best_bound = 0
    relative_gap = (objective_value - best_bound) / max(1, objective_value)
    return {
        "stage_index": 1,
        "objective_id": "OBJ-001",
        "metric": "WEIGHTED_TARDINESS",
        "sense": "MINIMIZE",
        "status": "FEASIBLE",
        "objective_value": objective_value,
        "best_bound": best_bound,
        "relative_gap": relative_gap,
        "allocated_wall_time_seconds": float(limits["max_wall_time_seconds"]),
        "solve_seconds": min(
            max(0.0, solve_seconds), float(limits["max_wall_time_seconds"])
        ),
        "stop_reason": (
            f"CORE_FEASIBILITY_ONLY_NATIVE_{native_status}_OBJECTIVE_NOT_OPTIMIZED"
        ),
    }


def map_core_candidate_solution(
    problem: PlanningProblemDocumentV2,
    policy: PlanningPolicyDocument,
    limits: SolveLimitsDocument,
    core_model: CoreCpSatModel,
    solver: cp_model.CpSolver,
    *,
    native_status: str,
    solve_seconds: float,
) -> PlanningSolutionDocument:
    """Create an honest FEASIBLE solution from a complete native candidate."""

    assignments = _assignments(problem, core_model, solver)
    objective_value = _measured_weighted_tardiness_seconds(problem, assignments)
    stage = _candidate_stage(
        limits=limits,
        solve_seconds=solve_seconds,
        objective_value=objective_value,
        native_status=native_status,
    )
    identity_payload: Mapping[str, object] = {
        "problem_hash": problem["problem_hash"],
        "policy_fingerprint": contract_fingerprint(
            cast(Mapping[str, object], policy)
        ),
        "limits_fingerprint": contract_fingerprint(
            cast(Mapping[str, object], limits)
        ),
        "assignments": cast(object, assignments),
        "solver_status": "FEASIBLE",
    }
    solution = cast(
        PlanningSolutionDocument,
        {
            "planning_solution_version": PLANNING_SOLUTION_VERSION,
            "schema_set_version": SCHEMA_SET_VERSION,
            "solution_id": _solution_id(identity_payload),
            "evidence_kind": "SOLVER_RUN",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "problem": _problem_reference(problem),
            "policy": _policy_reference(policy),
            "limits": _limits_reference(limits),
            "solver_status": "FEASIBLE",
            "planning_run_outcome": outcome_document_for_status(
                SolverStatus.FEASIBLE
            ),
            "assignments": assignments,
            "objective_stage_results": [stage],
            "diagnostics": [
                {
                    "code": "CP_SAT_CORE_FEASIBILITY_ONLY",
                    "message": (
                        "Candidate satisfies the bounded core model; OBJ-001 was "
                        "measured after solve but was not optimized"
                    ),
                }
            ],
        },
    )
    validate_planning_solution(cast(Mapping[str, object], solution))
    return solution


def map_core_non_candidate_solution(
    problem: PlanningProblemDocumentV2,
    policy: PlanningPolicyDocument,
    limits: SolveLimitsDocument,
    *,
    status: SolverStatus,
    diagnostic: DiagnosticDocument,
    solve_seconds: float,
) -> PlanningSolutionDocument:
    """Map a certified non-candidate status without leaking partial assignments."""

    if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        raise ValueError("candidate statuses require map_core_candidate_solution")
    objective_stage = cast(
        ObjectiveStageResultDocument,
        {
            "stage_index": 1,
            "objective_id": "OBJ-001",
            "metric": "WEIGHTED_TARDINESS",
            "sense": "MINIMIZE",
            "status": status.value,
            "objective_value": None,
            "best_bound": None,
            "relative_gap": None,
            "allocated_wall_time_seconds": float(limits["max_wall_time_seconds"]),
            "solve_seconds": min(
                max(0.0, solve_seconds), float(limits["max_wall_time_seconds"])
            ),
            "stop_reason": f"CORE_SOLVE_{status.value}",
        },
    )
    diagnostics = sorted([diagnostic], key=lambda item: (item["code"], item["message"]))
    identity_payload: Mapping[str, object] = {
        "problem_hash": problem["problem_hash"],
        "policy_fingerprint": contract_fingerprint(
            cast(Mapping[str, object], policy)
        ),
        "limits_fingerprint": contract_fingerprint(
            cast(Mapping[str, object], limits)
        ),
        "solver_status": status.value,
        "diagnostics": cast(object, diagnostics),
    }
    solution = cast(
        PlanningSolutionDocument,
        {
            "planning_solution_version": PLANNING_SOLUTION_VERSION,
            "schema_set_version": SCHEMA_SET_VERSION,
            "solution_id": _solution_id(identity_payload),
            "evidence_kind": "SOLVER_RUN",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "problem": _problem_reference(problem),
            "policy": _policy_reference(policy),
            "limits": _limits_reference(limits),
            "solver_status": status.value,
            "planning_run_outcome": outcome_document_for_status(status),
            "assignments": [],
            "objective_stage_results": [objective_stage],
            "diagnostics": diagnostics,
        },
    )
    validate_planning_solution(cast(Mapping[str, object], solution))
    return solution


__all__ = ["map_core_candidate_solution", "map_core_non_candidate_solution"]
