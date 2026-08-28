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
from app.planning.backends.cp_sat.fact_lock_constraints import (
    FACT_LOCK_CONSTRAINT_IDS,
    FactLockConstraintMetricsDocument,
    exact_tick_offset,
)
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.backends.cp_sat.status import (
    native_status_contract,
    native_status_name,
    solver_status_from_cp_sat,
)
from app.planning.backends.cp_sat.replan_backend import (
    REPLAN_BACKEND_ID,
    REPLAN_BACKEND_VERSION,
    LexicographicReplanBackend,
    ReplanBackendResult,
)
from app.planning.backends.cp_sat.replan_model import (
    REPLAN_MODEL_VERSION,
    ReplanCpSatModel,
    StabilityObjectiveModel,
    build_replan_model,
)
from app.planning.backends.cp_sat.temporal_constraints import (
    TEMPORAL_CONSTRAINT_IDS,
    calendar_tick_blocks,
    ceil_seconds_to_ticks,
    floor_seconds_to_ticks,
)

__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "CORE_CONSTRAINT_IDS",
    "FACT_LOCK_CONSTRAINT_IDS",
    "FactLockConstraintMetricsDocument",
    "CoreModelInputError",
    "CoreModelReason",
    "CoreSolveResult",
    "CoreSolveTelemetryDocument",
    "CpSatBackend",
    "ORTOOLS_VERSION",
    "REPLAN_BACKEND_ID",
    "REPLAN_BACKEND_VERSION",
    "REPLAN_MODEL_VERSION",
    "SOLVER_NAME",
    "LexicographicReplanBackend",
    "ReplanBackendResult",
    "ReplanCpSatModel",
    "StabilityObjectiveModel",
    "TEMPORAL_CONSTRAINT_IDS",
    "backend_identity",
    "build_core_model",
    "build_replan_model",
    "calendar_tick_blocks",
    "ceil_seconds_to_ticks",
    "floor_seconds_to_ticks",
    "exact_tick_offset",
    "native_status_contract",
    "native_status_name",
    "parameters_for_limits",
    "probe_empty_model",
    "probe_model_invalid",
    "precheck_core_problem",
    "solver_status_from_cp_sat",
]
