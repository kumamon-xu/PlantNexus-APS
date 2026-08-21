"""Validated P2 KPI and SolverReport output boundary."""

from app.planning.reporting.kpi import (
    ImmutableKpiV2,
    KPI_CANONICALIZATION_VERSION,
    KPI_SCHEMA_SET_VERSION,
    KPI_VERSION,
    STABILITY_STATUS,
    build_kpi_v2,
)
from app.planning.reporting.solver_report import (
    FrozenSolverReport,
    ReportingContractError,
    ReportingContractErrorCode,
    freeze_solver_report,
)

__all__ = [
    "FrozenSolverReport",
    "ImmutableKpiV2",
    "KPI_CANONICALIZATION_VERSION",
    "KPI_SCHEMA_SET_VERSION",
    "KPI_VERSION",
    "ReportingContractError",
    "ReportingContractErrorCode",
    "STABILITY_STATUS",
    "build_kpi_v2",
    "freeze_solver_report",
]
