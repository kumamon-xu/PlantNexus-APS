"""Pinned CP-SAT adapter with the bounded P2-05 through P2-07 model."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import tracemalloc
from typing import Literal, TypedDict

import ortools
from ortools.sat.python import cp_model

from app.domain.contracts import ValidationReportDocumentV2
from app.planning.backends.contracts import (
    BackendFailureReason,
    BackendIdentityDocument,
    BackendModelMetricsDocument,
    BackendSmokeResultDocument,
    SolverBackendError,
)
from app.planning.backends.cp_sat.fact_lock_constraints import (
    FactLockConstraintMetricsDocument,
)
from app.planning.backends.cp_sat.model import (
    CoreModelMetricsDocument,
    build_core_model,
)
from app.planning.backends.cp_sat.solution_mapper import (
    map_core_candidate_solution,
    map_core_non_candidate_solution,
)
from app.planning.backends.cp_sat.status import (
    native_status_name,
    solver_status_from_cp_sat,
)
from app.planning.contracts import (
    PlanningSolutionDocument,
    SolverParameterDocument,
    SolverStatus,
)
from app.planning.policy.contracts import (
    PlanningPolicyDocument,
    SolveLimitsDocument,
    validate_planning_policy,
    validate_solve_limits,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


BACKEND_ID = "cp-sat"
BACKEND_VERSION = "cp-sat-backend.v1"
SOLVER_NAME = "Google OR-Tools CP-SAT"
ORTOOLS_VERSION = "9.15.6755"


class CoreSolveTelemetryDocument(TypedDict):
    native_status: str
    solver_status: str
    model_build_seconds: float
    first_feasible_seconds: float | None
    solve_seconds: float
    solver_wall_time_seconds: float
    python_memory_peak_mb: float
    model_metrics: CoreModelMetricsDocument
    fact_lock_metrics: FactLockConstraintMetricsDocument
    validator_status: str | None
    objective_optimized: bool


@dataclass(frozen=True)
class CoreSolveResult:
    solution: PlanningSolutionDocument
    validation_report: ValidationReportDocumentV2 | None
    telemetry: CoreSolveTelemetryDocument


class _FirstFeasibleObserver(cp_model.CpSolverSolutionCallback):
    def __init__(self) -> None:
        super().__init__()
        self.first_feasible_seconds: float | None = None

    def on_solution_callback(self) -> None:
        if self.first_feasible_seconds is None:
            self.first_feasible_seconds = max(0.0, float(self.wall_time))


def backend_identity() -> BackendIdentityDocument:
    """Return exact backend identity or fail closed on dependency drift."""

    observed_version = getattr(ortools, "__version__", None)
    if observed_version != ORTOOLS_VERSION:
        raise SolverBackendError(
            BackendFailureReason.VERSION_MISMATCH,
            solver_status=SolverStatus.FAILED,
            message="Installed OR-Tools version differs from the accepted exact pin",
        )
    return {
        "backend_id": BACKEND_ID,
        "backend_version": BACKEND_VERSION,
        "solver_name": SOLVER_NAME,
        "solver_version": observed_version,
    }


def parameters_for_limits(
    limits: SolveLimitsDocument,
) -> list[SolverParameterDocument]:
    """Capture the only accepted SolveLimits-to-CP-SAT parameter mapping."""

    validate_solve_limits(limits)
    return [
        {
            "name": "log_search_progress",
            "value": False,
            "source": "BACKEND",
        },
        {
            "name": "max_time_in_seconds",
            "value": float(limits["max_wall_time_seconds"]),
            "source": "SOLVE_LIMITS",
        },
        {
            "name": "num_search_workers",
            "value": limits["max_workers"],
            "source": "SOLVE_LIMITS",
        },
        {
            "name": "random_seed",
            "value": limits["random_seed"],
            "source": "SOLVE_LIMITS",
        },
    ]


def _configured_solver(limits: SolveLimitsDocument) -> cp_model.CpSolver:
    parameters_for_limits(limits)
    solver = cp_model.CpSolver()
    try:
        solver.parameters.log_search_progress = False
        solver.parameters.max_time_in_seconds = float(
            limits["max_wall_time_seconds"]
        )
        solver.parameters.num_search_workers = limits["max_workers"]
        solver.parameters.random_seed = limits["random_seed"]
    except (OverflowError, TypeError, ValueError) as error:
        raise SolverBackendError(
            BackendFailureReason.INVALID_PARAMETERS,
            solver_status=SolverStatus.MODEL_INVALID,
            message=(
                "SolveLimits cannot be represented by the pinned CP-SAT "
                "parameter contract"
            ),
        ) from error
    return solver


def _model_metrics(model: cp_model.CpModel) -> BackendModelMetricsDocument:
    return {
        "variables": len(model.proto.variables),
        "constraints": len(model.proto.constraints),
        "optional_intervals": 0,
    }


def _smoke_result(
    *,
    smoke_kind: Literal["EMPTY_MODEL", "MODEL_INVALID"],
    model: cp_model.CpModel,
    solver: cp_model.CpSolver,
    native_status: cp_model.CpSolverStatus,
    diagnostic_code: str,
    diagnostic_message: str,
) -> BackendSmokeResultDocument:
    return {
        "smoke_kind": smoke_kind,
        "native_status": native_status_name(native_status),
        "solver_status": solver_status_from_cp_sat(native_status).value,
        "business_feasibility": "NOT_EVALUATED",
        "candidate_produced": False,
        "model_metrics": _model_metrics(model),
        "wall_time_seconds": max(0.0, float(solver.wall_time)),
        "diagnostics": [
            {"code": diagnostic_code, "message": diagnostic_message}
        ],
    }


def probe_empty_model(
    limits: SolveLimitsDocument,
) -> BackendSmokeResultDocument:
    """Run a zero-variable engineering smoke, never a feasibility claim."""

    backend_identity()
    model = cp_model.CpModel()
    solver = _configured_solver(limits)
    native_status = solver.solve(model)
    if solver_status_from_cp_sat(native_status) is not SolverStatus.OPTIMAL:
        raise SolverBackendError(
            BackendFailureReason.ADAPTER_FAILURE,
            solver_status=SolverStatus.FAILED,
            message="Pinned CP-SAT empty-model smoke did not complete as expected",
        )
    return _smoke_result(
        smoke_kind="EMPTY_MODEL",
        model=model,
        solver=solver,
        native_status=native_status,
        diagnostic_code="CP_SAT_EMPTY_MODEL_SMOKE_ONLY",
        diagnostic_message=(
            "Empty model verifies the native adapter only; business feasibility "
            "was not evaluated"
        ),
    )


def probe_model_invalid(
    limits: SolveLimitsDocument,
) -> BackendSmokeResultDocument:
    """Run an intentionally invalid-domain model to prove status mapping."""

    backend_identity()
    model = cp_model.CpModel()
    model.new_bool_var("foundation-invalid-domain")
    model.proto.variables[0].domain.clear()
    if not model.validate():
        raise AssertionError("engineering model was expected to be invalid")
    solver = _configured_solver(limits)
    native_status = solver.solve(model)
    if solver_status_from_cp_sat(native_status) is not SolverStatus.MODEL_INVALID:
        raise SolverBackendError(
            BackendFailureReason.ADAPTER_FAILURE,
            solver_status=SolverStatus.FAILED,
            message="Pinned CP-SAT invalid-model smoke did not return MODEL_INVALID",
        )
    return _smoke_result(
        smoke_kind="MODEL_INVALID",
        model=model,
        solver=solver,
        native_status=native_status,
        diagnostic_code="CP_SAT_INTENTIONAL_MODEL_INVALID_SMOKE",
        diagnostic_message=(
            "An intentionally empty variable domain verified MODEL_INVALID; "
            "business feasibility was not evaluated"
        ),
    )


class CpSatBackend:
    """SolverBackend for bounded core, temporal, and fact/lock feasibility."""

    def __init__(self) -> None:
        self._identity = backend_identity()

    @property
    def identity(self) -> BackendIdentityDocument:
        return {
            "backend_id": self._identity["backend_id"],
            "backend_version": self._identity["backend_version"],
            "solver_name": self._identity["solver_name"],
            "solver_version": self._identity["solver_version"],
        }

    def solve(
        self,
        problem: PlanningProblemDocumentV2,
        policy: PlanningPolicyDocument,
        limits: SolveLimitsDocument,
    ) -> PlanningSolutionDocument:
        """Return a bounded PlanningSolution while retaining detailed evidence."""

        return self.solve_with_evidence(problem, policy, limits).solution

    def solve_with_evidence(
        self,
        problem: PlanningProblemDocumentV2,
        policy: PlanningPolicyDocument,
        limits: SolveLimitsDocument,
    ) -> CoreSolveResult:
        """Solve, map, and independently validate the bounded P2-07 model."""

        validate_planning_policy(policy)
        validate_solve_limits(limits)
        backend_identity()

        owns_trace = not tracemalloc.is_tracing()
        if owns_trace:
            tracemalloc.start()
        baseline_peak = tracemalloc.get_traced_memory()[1]
        try:
            core_model = build_core_model(problem)
            solver = _configured_solver(limits)
            observer = _FirstFeasibleObserver()
            solve_started = perf_counter()
            native_status = solver.solve(core_model.model, observer)
            solve_seconds = max(0.0, perf_counter() - solve_started)
            native_name = native_status_name(native_status)
            mapped_status = solver_status_from_cp_sat(native_status)
            first_feasible = observer.first_feasible_seconds
            if mapped_status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
                if first_feasible is None:
                    first_feasible = min(
                        max(0.0, float(solver.wall_time)), solve_seconds
                    )
                solution = map_core_candidate_solution(
                    problem,
                    policy,
                    limits,
                    core_model,
                    solver,
                    native_status=native_name,
                    solve_seconds=float(solver.wall_time),
                )
                validation_report = validate_problem_schedule(problem, solution)
                if validation_report["status"] != "PASS":
                    product_status = SolverStatus.FAILED
                    solution = map_core_non_candidate_solution(
                        problem,
                        policy,
                        limits,
                        status=product_status,
                        diagnostic={
                            "code": "CP_SAT_BOUNDED_CANDIDATE_VALIDATION_FAILED",
                            "message": (
                                "Independent validation rejected the bounded candidate; "
                                "assignments were discarded"
                            ),
                        },
                        solve_seconds=float(solver.wall_time),
                    )
                else:
                    product_status = SolverStatus.FEASIBLE
            else:
                product_status = mapped_status
                validation_report = None
                solution = map_core_non_candidate_solution(
                    problem,
                    policy,
                    limits,
                    status=product_status,
                    diagnostic={
                        "code": f"CP_SAT_BOUNDED_{product_status.value}",
                        "message": (
                            "Pinned CP-SAT completed the bounded P2-07 model without "
                            "an accepted candidate"
                        ),
                    },
                    solve_seconds=float(solver.wall_time),
                )
            observed_peak = tracemalloc.get_traced_memory()[1]
            telemetry: CoreSolveTelemetryDocument = {
                "native_status": native_name,
                "solver_status": product_status.value,
                "model_build_seconds": core_model.model_build_seconds,
                "first_feasible_seconds": first_feasible,
                "solve_seconds": solve_seconds,
                "solver_wall_time_seconds": max(0.0, float(solver.wall_time)),
                "python_memory_peak_mb": max(
                    0.0, (observed_peak - baseline_peak) / (1024 * 1024)
                ),
                "model_metrics": core_model.metrics,
                "fact_lock_metrics": core_model.fact_lock_metrics,
                "validator_status": (
                    None
                    if validation_report is None
                    else str(validation_report["status"])
                ),
                "objective_optimized": False,
            }
            return CoreSolveResult(
                solution=solution,
                validation_report=validation_report,
                telemetry=telemetry,
            )
        finally:
            if owns_trace:
                tracemalloc.stop()


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "CoreSolveResult",
    "CoreSolveTelemetryDocument",
    "CpSatBackend",
    "ORTOOLS_VERSION",
    "SOLVER_NAME",
    "backend_identity",
    "parameters_for_limits",
    "probe_empty_model",
    "probe_model_invalid",
]
