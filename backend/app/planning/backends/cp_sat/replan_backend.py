"""Bounded multi-round CP-SAT backend for P4 lexicographic replanning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
import math
from time import perf_counter
import tracemalloc
from typing import TypedDict, cast

from ortools.sat.python import cp_model

from app.domain.execution_contracts import contract_fingerprint
from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.backend import backend_identity
from app.planning.backends.cp_sat.replan_model import (
    ReplanCpSatModel,
    build_replan_model,
)
from app.planning.backends.cp_sat.status import (
    native_status_name,
    solver_status_from_cp_sat,
)
from app.planning.contracts import SolverStatus
from app.planning.policy.contracts import SolveLimitsDocument, validate_solve_limits
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.validation.replan_candidate_validator import (
    ReplanCandidateValidationReport,
    validate_replan_candidate,
)


REPLAN_BACKEND_ID = "cp-sat-replan"
REPLAN_BACKEND_VERSION = "cp-sat-replan-backend.v1"


class ReplanRoundReport(TypedDict):
    round_id: str
    stage_index: int
    objective_id: str
    component: str | None
    native_status: str
    solver_status: str
    objective_value: int | None
    best_bound: int | None
    allocated_wall_time_seconds: float
    solve_seconds: float
    stop_reason: str
    candidate_fingerprint: str | None
    validation_report_fingerprint: str | None


class ReplanBackendTelemetry(TypedDict):
    model_build_seconds: float
    first_feasible_seconds: float | None
    solve_seconds: float
    validation_seconds: float | None
    total_seconds: float
    python_memory_peak_mb: float
    model_metrics: dict[str, int]
    base_hint_count: int
    effective_hard_lock_count: int
    candidate_validation_count: int


@dataclass(frozen=True)
class ReplanBackendResult:
    solver_status: SolverStatus
    candidate: dict[str, object] | None
    objective_values: dict[str, object] | None
    stage_evidence: dict[str, dict[str, object]]
    round_reports: tuple[ReplanRoundReport, ...]
    validation_reports: tuple[ReplanCandidateValidationReport, ...]
    telemetry: ReplanBackendTelemetry
    diagnostics: tuple[dict[str, str], ...]


class _FirstFeasibleObserver(cp_model.CpSolverSolutionCallback):
    def __init__(self) -> None:
        super().__init__()
        self.first_feasible_seconds: float | None = None

    def on_solution_callback(self) -> None:
        if self.first_feasible_seconds is None:
            self.first_feasible_seconds = max(0.0, float(self.wall_time))


@dataclass(frozen=True)
class _RoundOutcome:
    report: ReplanRoundReport
    status: SolverStatus
    candidate: dict[str, object] | None
    objective_values: dict[str, object] | None
    validation_report: ReplanCandidateValidationReport | None
    first_feasible_seconds: float | None
    validation_seconds: float | None


def _configured_solver(
    limits: SolveLimitsDocument,
    *,
    budget_seconds: float,
) -> cp_model.CpSolver:
    validate_solve_limits(limits)
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = False
    solver.parameters.max_time_in_seconds = budget_seconds
    solver.parameters.num_search_workers = limits["max_workers"]
    solver.parameters.random_seed = limits["random_seed"]
    return solver


def _certified_bound(
    solver: cp_model.CpSolver,
    *,
    status: SolverStatus,
    value: int,
) -> int:
    if status is SolverStatus.OPTIMAL:
        return value
    observed = float(solver.best_objective_bound)
    if not math.isfinite(observed):
        return 0
    return max(0, min(value, math.floor(observed)))


def _metadata_indexes(
    problem: PlanningProblemDocumentV2,
    projection: Mapping[str, object],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    lock_ids: dict[str, list[str]] = {}
    fact_ids: dict[str, list[str]] = {}
    for lock in problem["operation_locks"]:
        lock_ids.setdefault(lock["operation_id"], []).append(lock["lock_id"])
    for section in ("freeze_derived_hard_locks",):
        values = projection.get(section)
        if not isinstance(values, list):
            raise ValueError(f"{section} must be an array")
        for value in values:
            if not isinstance(value, Mapping):
                raise ValueError(f"{section} entries must be objects")
            operation_id = value.get("operation_id")
            lock_id = value.get("lock_id")
            if not isinstance(operation_id, str) or not isinstance(lock_id, str):
                raise ValueError(f"{section} entry lacks operation/lock identity")
            lock_ids.setdefault(operation_id, []).append(lock_id)
    running = projection.get("running_protections")
    if not isinstance(running, list):
        raise ValueError("running_protections must be an array")
    for value in running:
        if not isinstance(value, Mapping):
            raise ValueError("running protection must be an object")
        operation_id = value.get("operation_id")
        reference_id = value.get("reference_id")
        if not isinstance(operation_id, str) or not isinstance(reference_id, str):
            raise ValueError("running protection lacks operation/fact identity")
        fact_ids.setdefault(operation_id, []).append(reference_id)
    return (
        {key: sorted(set(values)) for key, values in lock_ids.items()},
        {key: sorted(set(values)) for key, values in fact_ids.items()},
    )


def _candidate(
    problem: PlanningProblemDocumentV2,
    replan_model: ReplanCpSatModel,
    solver: cp_model.CpSolver,
    projection: Mapping[str, object],
) -> dict[str, object]:
    horizon_start = parse_utc_instant(problem["horizon_start_utc"])
    tick_seconds = problem["tick_seconds"]
    lock_ids, fact_ids = _metadata_indexes(problem, projection)
    assignments: list[dict[str, object]] = []
    for operation in replan_model.core.operations:
        selected = [
            option for option in operation.options if solver.value(option.presence) == 1
        ]
        if len(selected) != 1:
            raise ValueError("CP-SAT replan candidate does not select exactly one option")
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
                "lock_ids": list(lock_ids.get(operation.operation_id, [])),
                "execution_fact_ids": list(fact_ids.get(operation.operation_id, [])),
            }
        )
    assignments.sort(key=lambda item: cast(str, item["operation_id"]))
    basis: dict[str, object] = {
        "candidate_version": "replan-candidate.v1",
        "assignment_count": len(assignments),
        "assignments": assignments,
    }
    return {
        **basis,
        "candidate_fingerprint": contract_fingerprint(basis),
    }


def _objective_values(
    model: ReplanCpSatModel,
    solver: cp_model.CpSolver,
) -> dict[str, object]:
    return {
        "delivery": int(
            solver.value(model.delivery.total_weighted_tardiness_seconds)
        ),
        "stability": {
            name: int(solver.value(variable))
            for name, variable in model.stability.ordered
        },
        "makespan": int(solver.value(model.makespan_seconds)),
    }


def _solve_round(
    *,
    model: ReplanCpSatModel,
    objective: cp_model.IntVar,
    round_id: str,
    stage_index: int,
    objective_id: str,
    component: str | None,
    budget_seconds: float,
    limits: SolveLimitsDocument,
    problem: PlanningProblemDocumentV2,
    base_assignments: Sequence[object],
    effective_locks: Mapping[str, object],
) -> _RoundOutcome:
    model.core.model.clear_objective()
    model.core.model.minimize(objective)
    solver = _configured_solver(limits, budget_seconds=budget_seconds)
    observer = _FirstFeasibleObserver()
    started = perf_counter()
    native_status = solver.solve(model.core.model, observer)
    solve_seconds = max(0.0, perf_counter() - started)
    status = solver_status_from_cp_sat(native_status)
    native_name = native_status_name(native_status)
    if status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        report: ReplanRoundReport = {
            "round_id": round_id,
            "stage_index": stage_index,
            "objective_id": objective_id,
            "component": component,
            "native_status": native_name,
            "solver_status": status.value,
            "objective_value": None,
            "best_bound": None,
            "allocated_wall_time_seconds": budget_seconds,
            "solve_seconds": solve_seconds,
            "stop_reason": f"{objective_id}_{status.value}_NO_CANDIDATE",
            "candidate_fingerprint": None,
            "validation_report_fingerprint": None,
        }
        return _RoundOutcome(
            report=report,
            status=status,
            candidate=None,
            objective_values=None,
            validation_report=None,
            first_feasible_seconds=None,
            validation_seconds=None,
        )

    value = int(solver.value(objective))
    candidate = _candidate(problem, model, solver, effective_locks)
    values = _objective_values(model, solver)
    validation_started = perf_counter()
    validation = validate_replan_candidate(
        problem=problem,
        base_assignments=base_assignments,
        effective_locks=effective_locks,
        candidate=candidate,
        objective_evidence=values,
    )
    validation_seconds = max(0.0, perf_counter() - validation_started)
    stop_reason = (
        f"{objective_id}_OPTIMALITY_PROVEN"
        if status is SolverStatus.OPTIMAL
        else f"{objective_id}_FEASIBLE_CANDIDATE_OPTIMALITY_NOT_PROVEN"
    )
    report = {
        "round_id": round_id,
        "stage_index": stage_index,
        "objective_id": objective_id,
        "component": component,
        "native_status": native_name,
        "solver_status": status.value,
        "objective_value": value,
        "best_bound": _certified_bound(solver, status=status, value=value),
        "allocated_wall_time_seconds": budget_seconds,
        "solve_seconds": solve_seconds,
        "stop_reason": stop_reason,
        "candidate_fingerprint": cast(str, candidate["candidate_fingerprint"]),
        "validation_report_fingerprint": validation["report_fingerprint"],
    }
    return _RoundOutcome(
        report=report,
        status=status,
        candidate=candidate,
        objective_values=values,
        validation_report=validation,
        first_feasible_seconds=observer.first_feasible_seconds,
        validation_seconds=validation_seconds,
    )


def _stage_evidence(
    *,
    final_status: SolverStatus,
    objective_values: Mapping[str, object] | None,
    reports: Sequence[ReplanRoundReport],
    total_budget: float,
) -> dict[str, dict[str, object]]:
    delivery_reports = [report for report in reports if report["stage_index"] == 1]
    stability_reports = [report for report in reports if report["stage_index"] == 2]
    makespan_reports = [report for report in reports if report["stage_index"] == 3]
    candidate_available = objective_values is not None
    delivery_bound = delivery_reports[0]["best_bound"] if delivery_reports else None
    stability_bound: dict[str, int] | None = None
    if len(stability_reports) == 4 and all(
        report["best_bound"] is not None for report in stability_reports
    ):
        stability_bound = {
            cast(str, report["component"]): cast(int, report["best_bound"])
            for report in stability_reports
        }
    makespan_bound = makespan_reports[0]["best_bound"] if makespan_reports else None
    status = final_status.value
    delivery_value = objective_values.get("delivery") if candidate_available else None
    stability_value = objective_values.get("stability") if candidate_available else None
    makespan_value = objective_values.get("makespan") if candidate_available else None
    return {
        "delivery": {
            "status": status,
            "objective_value": delivery_value,
            "best_bound": delivery_bound if candidate_available else None,
            "allocated_wall_time_seconds": total_budget / 3,
            "solve_seconds": sum(report["solve_seconds"] for report in delivery_reports),
            "stop_reason": (
                delivery_reports[-1]["stop_reason"]
                if delivery_reports
                else "OBJ-001_NOT_STARTED"
            ),
        },
        "stability": {
            "status": status,
            "objective_value": stability_value,
            "best_bound": stability_bound if candidate_available else None,
            "allocated_wall_time_seconds": total_budget / 3,
            "solve_seconds": sum(report["solve_seconds"] for report in stability_reports),
            "stop_reason": (
                "OBJ-002_ALL_COMPONENTS_OPTIMALITY_PROVEN"
                if len(stability_reports) == 4
                and all(report["solver_status"] == "OPTIMAL" for report in stability_reports)
                else (
                    stability_reports[-1]["stop_reason"]
                    if stability_reports
                    else "OBJ-002_NOT_STARTED_AFTER_HIGHER_PRIORITY_STOP"
                )
            ),
        },
        "makespan": {
            "status": status,
            "objective_value": makespan_value,
            "best_bound": makespan_bound if candidate_available else None,
            "allocated_wall_time_seconds": total_budget / 3,
            "solve_seconds": sum(report["solve_seconds"] for report in makespan_reports),
            "stop_reason": (
                makespan_reports[-1]["stop_reason"]
                if makespan_reports
                else "OBJ-003_NOT_STARTED_AFTER_HIGHER_PRIORITY_STOP"
            ),
        },
    }


class LexicographicReplanBackend:
    """Reuse one global hard model and freeze each accepted objective value."""

    @property
    def identity(self) -> dict[str, str]:
        native = backend_identity()
        return {
            "backend_id": REPLAN_BACKEND_ID,
            "backend_version": REPLAN_BACKEND_VERSION,
            "solver_name": native["solver_name"],
            "solver_version": native["solver_version"],
        }

    def solve_with_evidence(
        self,
        problem: PlanningProblemDocumentV2,
        *,
        base_assignments: Sequence[object],
        effective_locks: Mapping[str, object],
        limits: SolveLimitsDocument,
    ) -> ReplanBackendResult:
        """Execute Delivery, four Stability rounds, then Makespan."""

        validate_solve_limits(limits)
        backend_identity()
        owns_trace = not tracemalloc.is_tracing()
        if owns_trace:
            tracemalloc.start()
        baseline_peak = tracemalloc.get_traced_memory()[1]
        total_started = perf_counter()
        build_started = perf_counter()
        try:
            model = build_replan_model(
                problem,
                base_assignments=base_assignments,
                effective_locks=effective_locks,
            )
            model_build_seconds = max(0.0, perf_counter() - build_started)
            total_budget = float(limits["max_wall_time_seconds"])
            delivery_budget = total_budget / 3
            stability_round_budget = total_budget / 12
            makespan_budget = total_budget / 3
            reports: list[ReplanRoundReport] = []
            validations: list[ReplanCandidateValidationReport] = []
            validation_total = 0.0
            first_feasible: float | None = None
            accepted_candidate: dict[str, object] | None = None
            accepted_values: dict[str, object] | None = None
            all_rounds_optimal = True
            diagnostic: dict[str, str] | None = None

            rounds: list[tuple[str, int, str, str | None, cp_model.IntVar, float]] = [
                (
                    "OBJ-001",
                    1,
                    "OBJ-001",
                    None,
                    model.delivery.total_weighted_tardiness_seconds,
                    delivery_budget,
                ),
                *[
                    (
                        f"OBJ-002-{index}",
                        2,
                        "OBJ-002",
                        component,
                        variable,
                        stability_round_budget,
                    )
                    for index, (component, variable) in enumerate(
                        model.stability.ordered, start=1
                    )
                ],
                (
                    "OBJ-003",
                    3,
                    "OBJ-003",
                    None,
                    model.makespan_seconds,
                    makespan_budget,
                ),
            ]
            terminal_status: SolverStatus | None = None
            for round_id, stage_index, objective_id, component, variable, budget in rounds:
                outcome = _solve_round(
                    model=model,
                    objective=variable,
                    round_id=round_id,
                    stage_index=stage_index,
                    objective_id=objective_id,
                    component=component,
                    budget_seconds=budget,
                    limits=limits,
                    problem=problem,
                    base_assignments=base_assignments,
                    effective_locks=effective_locks,
                )
                reports.append(outcome.report)
                if outcome.validation_seconds is not None:
                    validation_total += outcome.validation_seconds
                if outcome.first_feasible_seconds is not None and first_feasible is None:
                    first_feasible = outcome.first_feasible_seconds
                if outcome.validation_report is not None:
                    validations.append(outcome.validation_report)
                    if outcome.validation_report["status"] != "PASS":
                        terminal_status = SolverStatus.FAILED
                        accepted_candidate = None
                        accepted_values = None
                        diagnostic = {
                            "code": "REPLAN_CANDIDATE_VALIDATION_FAILED",
                            "message": (
                                "Fresh independent validation rejected a bounded "
                                "candidate; candidate data was discarded"
                            ),
                        }
                        break
                if outcome.candidate is None:
                    if accepted_candidate is None:
                        terminal_status = outcome.status
                        diagnostic = {
                            "code": f"REPLAN_{outcome.status.value}_NO_CANDIDATE",
                            "message": (
                                "The bounded global replan model produced no accepted "
                                "candidate in the highest available objective round"
                            ),
                        }
                    elif outcome.status is SolverStatus.UNKNOWN:
                        terminal_status = SolverStatus.FEASIBLE
                        all_rounds_optimal = False
                        diagnostic = {
                            "code": "REPLAN_LOWER_PRIORITY_LIMIT_RETAINED_CANDIDATE",
                            "message": (
                                "A fresh-validated higher-priority candidate was retained "
                                "after a lower-priority round exhausted its budget"
                            ),
                        }
                    else:
                        terminal_status = SolverStatus.FAILED
                        accepted_candidate = None
                        accepted_values = None
                        diagnostic = {
                            "code": "REPLAN_LEXICOGRAPHIC_ROUND_INCONSISTENT",
                            "message": (
                                "A lower-priority round rejected the already feasible "
                                "frozen objective domain"
                            ),
                        }
                    break
                accepted_candidate = outcome.candidate
                accepted_values = outcome.objective_values
                all_rounds_optimal = (
                    all_rounds_optimal and outcome.status is SolverStatus.OPTIMAL
                )
                value = outcome.report["objective_value"]
                if value is None:
                    raise RuntimeError("accepted CP-SAT round has no objective value")
                model.core.model.add(variable == value)

            if terminal_status is None:
                if accepted_candidate is None or accepted_values is None:
                    raise RuntimeError("lexicographic rounds completed without a candidate")
                terminal_status = (
                    SolverStatus.OPTIMAL if all_rounds_optimal else SolverStatus.FEASIBLE
                )
            if terminal_status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
                accepted_candidate = None
                accepted_values = None
                first_feasible = None

            stage_evidence = _stage_evidence(
                final_status=terminal_status,
                objective_values=accepted_values,
                reports=reports,
                total_budget=total_budget,
            )
            observed_peak = tracemalloc.get_traced_memory()[1]
            total_seconds = max(0.0, perf_counter() - total_started)
            solve_seconds = sum(report["solve_seconds"] for report in reports)
            telemetry: ReplanBackendTelemetry = {
                "model_build_seconds": model_build_seconds,
                "first_feasible_seconds": first_feasible,
                "solve_seconds": solve_seconds,
                "validation_seconds": validation_total if validations else None,
                "total_seconds": max(
                    total_seconds,
                    model_build_seconds + solve_seconds + validation_total,
                ),
                "python_memory_peak_mb": max(
                    0.0, (observed_peak - baseline_peak) / (1024 * 1024)
                ),
                "model_metrics": {
                    "variables": len(model.core.model.proto.variables),
                    "constraints": len(model.core.model.proto.constraints),
                    "optional_intervals": model.core.metrics["optional_intervals"],
                },
                "base_hint_count": model.base_hint_count,
                "effective_hard_lock_count": model.effective_hard_lock_count,
                "candidate_validation_count": len(validations),
            }
            return ReplanBackendResult(
                solver_status=terminal_status,
                candidate=accepted_candidate,
                objective_values=accepted_values,
                stage_evidence=stage_evidence,
                round_reports=tuple(reports),
                validation_reports=tuple(validations),
                telemetry=telemetry,
                diagnostics=() if diagnostic is None else (diagnostic,),
            )
        finally:
            if owns_trace:
                tracemalloc.stop()


__all__ = [
    "REPLAN_BACKEND_ID",
    "REPLAN_BACKEND_VERSION",
    "LexicographicReplanBackend",
    "ReplanBackendResult",
    "ReplanBackendTelemetry",
    "ReplanRoundReport",
]
