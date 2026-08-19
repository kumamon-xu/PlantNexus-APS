"""JSON-compatible top-level domain contract type skeletons."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class ImportPackageDocument(TypedDict):
    """P0 metadata envelope; canonical record fields are defined in P1."""

    import_package_version: Literal["import-package.v1"]
    package_id: str
    source_versions: dict[str, str]
    synthetic: bool
    records: dict[str, list[dict[str, JsonValue]]]
    scenario_id: NotRequired[str]


class DeliveryKpis(TypedDict):
    on_time_order_ratio: float
    total_tardiness_seconds: int
    weighted_tardiness: float
    late_order_count: int


class PlanningKpis(TypedDict):
    makespan_seconds: int
    scheduled_operation_count: int
    unscheduled_operation_count: int


class ResourceKpi(TypedDict):
    resource_id: str
    available_seconds: int
    planned_busy_seconds: int
    utilization: float | None


class StabilityKpis(TypedDict):
    changed_operation_count: int
    resource_changed_count: int
    start_shift_seconds: int
    schedule_stability_ratio: float


class SolverKpis(TypedDict):
    model_build_seconds: float
    first_feasible_seconds: float | None
    solve_seconds: float
    objective: float | None
    best_bound: float | None
    relative_gap: float | None
    variables: int
    constraints: int
    optional_intervals: int
    memory_peak_mb: float


class KpiDocument(TypedDict):
    kpi_version: Literal["kpi.v1"]
    problem_hash: str
    tick_seconds: int
    delivery: DeliveryKpis
    planning: PlanningKpis
    resources: list[ResourceKpi]
    stability: StabilityKpis
    solver: SolverKpis


class ErrorDetailDocument(TypedDict):
    entity_id: NotRequired[str]
    field: NotRequired[str]
    observed_value: NotRequired[JsonValue]
    expected_contract: NotRequired[str]
    source_location: NotRequired[str]


class ErrorDocument(TypedDict):
    """Historical error.v1 envelope retained as an explicit compatibility boundary."""

    error_version: Literal["error.v1"]
    category: Literal[
        "DATA_ERROR",
        "UNSUPPORTED_CAPABILITY",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "SYSTEM_ERROR",
    ]
    code: str
    message: str
    details: list[ErrorDetailDocument]


class ValidationViolationDocument(TypedDict):
    constraint_id: str
    severity: str
    entity_ids: list[str]
    observed_value: JsonValue
    expected_rule: str
    message: str


class ValidationReportDocument(TypedDict):
    """Historical validation-report.v1 envelope retained unchanged."""

    validation_report_version: Literal["validation-report.v1"]
    problem_hash: str
    status: Literal["PASS", "FAIL"]
    violations: list[ValidationViolationDocument]


class ErrorDocumentV2(TypedDict):
    error_version: Literal["error.v2"]
    category: Literal[
        "DATA_ERROR",
        "UNSUPPORTED_CAPABILITY",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "SYSTEM_ERROR",
    ]
    code: str
    message: str
    details: list[ErrorDetailDocument]


class ValidationViolationDocumentV2(TypedDict):
    constraint_id: Literal[
        "C-001",
        "C-002",
        "C-003",
        "C-004",
        "C-005",
        "C-006",
        "C-007",
        "C-008",
        "C-009",
        "C-010",
        "C-011",
    ]
    severity: Literal["HARD"]
    entity_ids: list[str]
    observed_value: JsonValue
    expected_rule: str
    message: str


class ValidationReportDocumentV2(TypedDict):
    validation_report_version: Literal["validation-report.v2"]
    problem_hash: str
    status: Literal["PASS", "FAIL"]
    hard_violation_count: int
    violations: list[ValidationViolationDocumentV2]


__all__ = [
    "ErrorDocument",
    "ErrorDocumentV2",
    "ImportPackageDocument",
    "JsonValue",
    "KpiDocument",
    "ValidationReportDocument",
    "ValidationReportDocumentV2",
]
