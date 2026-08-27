"""Validated P2 KPI and SolverReport output boundary."""

from app.planning.reporting.kpi import (
    ImmutableKpiV2,
    KPI_CANONICALIZATION_VERSION,
    KPI_SCHEMA_SET_VERSION,
    KPI_VERSION,
    ScheduleKpiMetrics,
    STABILITY_STATUS,
    build_kpi_v2,
    calculate_schedule_kpi_metrics,
)
from app.planning.reporting.solver_report import (
    FrozenSolverReport,
    ReportingContractError,
    ReportingContractErrorCode,
    freeze_solver_report,
)
from app.planning.reporting.change_report import (
    CHANGE_REPORT_BUILDER_VERSION,
    build_change_report,
    kpi_evidence_reference,
)
from app.planning.reporting.stability import (
    STABILITY_COMPONENTS,
    STABILITY_OBJECTIVE_VERSION,
    OperationDelta,
    StabilityVector,
    calculate_operation_delta,
    calculate_stability,
)

__all__ = [
    "FrozenSolverReport",
    "CHANGE_REPORT_BUILDER_VERSION",
    "ImmutableKpiV2",
    "KPI_CANONICALIZATION_VERSION",
    "KPI_SCHEMA_SET_VERSION",
    "KPI_VERSION",
    "ReportingContractError",
    "ReportingContractErrorCode",
    "STABILITY_COMPONENTS",
    "STABILITY_OBJECTIVE_VERSION",
    "ScheduleKpiMetrics",
    "OperationDelta",
    "StabilityVector",
    "STABILITY_STATUS",
    "build_kpi_v2",
    "build_change_report",
    "calculate_operation_delta",
    "calculate_schedule_kpi_metrics",
    "calculate_stability",
    "freeze_solver_report",
    "kpi_evidence_reference",
]
