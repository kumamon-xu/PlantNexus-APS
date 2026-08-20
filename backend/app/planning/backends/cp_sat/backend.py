"""Bounded CP-SAT adapter foundation without business model construction."""

from __future__ import annotations

from typing import Literal, NoReturn

import ortools
from ortools.sat.python import cp_model

from app.planning.backends.contracts import (
    BackendFailureReason,
    BackendIdentityDocument,
    BackendModelMetricsDocument,
    BackendSmokeResultDocument,
    SolverBackendError,
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
from app.planning.problem.hashing import validate_built_problem_v2


BACKEND_ID = "cp-sat"
BACKEND_VERSION = "cp-sat-backend.v1"
SOLVER_NAME = "Google OR-Tools CP-SAT"
ORTOOLS_VERSION = "9.15.6755"


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
    """Structural SolverBackend adapter reserved for later model builders."""

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
        """Validate the boundary, then fail closed until P2 model construction."""

        validate_built_problem_v2(problem)
        validate_planning_policy(policy)
        validate_solve_limits(limits)
        self._model_builder_not_implemented()

    @staticmethod
    def _model_builder_not_implemented() -> NoReturn:
        raise SolverBackendError(
            BackendFailureReason.MODEL_BUILDER_NOT_IMPLEMENTED,
            solver_status=SolverStatus.MODEL_INVALID,
            message=(
                "CP-SAT business model construction is outside TASK-P2-03 and "
                "remains unavailable"
            ),
        )


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "CpSatBackend",
    "ORTOOLS_VERSION",
    "SOLVER_NAME",
    "backend_identity",
    "parameters_for_limits",
    "probe_empty_model",
    "probe_model_invalid",
]
