"""Public CP-SAT adapter foundation; native objects remain inside this package."""

from app.planning.backends.cp_sat.backend import (
    BACKEND_ID,
    BACKEND_VERSION,
    ORTOOLS_VERSION,
    SOLVER_NAME,
    CpSatBackend,
    backend_identity,
    parameters_for_limits,
    probe_empty_model,
    probe_model_invalid,
)
from app.planning.backends.cp_sat.status import (
    native_status_contract,
    native_status_name,
    solver_status_from_cp_sat,
)

__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "CpSatBackend",
    "ORTOOLS_VERSION",
    "SOLVER_NAME",
    "backend_identity",
    "native_status_contract",
    "native_status_name",
    "parameters_for_limits",
    "probe_empty_model",
    "probe_model_invalid",
    "solver_status_from_cp_sat",
]
