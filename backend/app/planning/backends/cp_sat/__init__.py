"""Public CP-SAT adapter foundation; native objects remain inside this package."""

from app.planning.backends.cp_sat.backend import (
    BACKEND_ID,
    BACKEND_VERSION,
    CoreSolveResult,
    CoreSolveTelemetryDocument,
    ORTOOLS_VERSION,
    SOLVER_NAME,
    CpSatBackend,
    backend_identity,
    parameters_for_limits,
    probe_empty_model,
    probe_model_invalid,
)
from app.planning.backends.cp_sat.core_constraints import (
    CORE_CONSTRAINT_IDS,
    CoreModelInputError,
    CoreModelReason,
    precheck_core_problem,
)
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.backends.cp_sat.status import (
    native_status_contract,
    native_status_name,
    solver_status_from_cp_sat,
)

__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "CORE_CONSTRAINT_IDS",
    "CoreModelInputError",
    "CoreModelReason",
    "CoreSolveResult",
    "CoreSolveTelemetryDocument",
    "CpSatBackend",
    "ORTOOLS_VERSION",
    "SOLVER_NAME",
    "backend_identity",
    "build_core_model",
    "native_status_contract",
    "native_status_name",
    "parameters_for_limits",
    "probe_empty_model",
    "probe_model_invalid",
    "precheck_core_problem",
    "solver_status_from_cp_sat",
]
