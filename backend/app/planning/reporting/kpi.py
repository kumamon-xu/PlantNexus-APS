"""Deterministic KPI v2 calculation from one formally validated P2 solution."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Any, Never, cast

from app.data_validation.validator import validate_quality_report_contract
from app.domain.canonical_records import (
    PlanningSnapshotDocumentV2,
    validate_planning_snapshot_v2,
)
from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.contracts import canonical_contract_bytes, contract_fingerprint
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import validate_built_problem_v2
from app.planning.reporting.solver_report import (
    FrozenSolverReport,
    ReportingContractError,
    ReportingContractErrorCode,
    freeze_solver_report,
)
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)
from app.snapshots.canonical import snapshot_hash_for


KPI_VERSION = "kpi.v2"
KPI_SCHEMA_SET_VERSION = "2.5.0"
KPI_CANONICALIZATION_VERSION = "canonical-json.v1"
STABILITY_STATUS = "NOT_APPLICABLE_NO_BASE_SCHEDULE"

type JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImmutableKpiV2:
    """A KPI v2 value backed only by canonical JSON bytes."""

    canonical_bytes: bytes
    fingerprint: str
    kpi_id: str
    planning_run_id: str

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))


@dataclass(frozen=True, slots=True)
class ScheduleKpiMetrics:
    """Pure schedule-level KPI projection shared by Solver and benchmark paths."""

    delivery_rows: tuple[JsonObject, ...]
    resource_rows: tuple[JsonObject, ...]
    order_count: int
    on_time_order_count: int
    total_tardiness_seconds: int
    priority_weighted_tardiness_seconds: int
    makespan_seconds: int
    scheduled_operation_count: int
    unscheduled_operation_count: int

    @property
    def delivery_document(self) -> JsonObject:
        return {
            "order_count": self.order_count,
            "on_time_order_count": self.on_time_order_count,
            "on_time_order_ratio": (
                None
                if self.order_count == 0
                else round(self.on_time_order_count / self.order_count, 12)
            ),
            "late_order_count": self.order_count - self.on_time_order_count,
            "total_tardiness_seconds": self.total_tardiness_seconds,
            "priority_weighted_tardiness_seconds": (
                self.priority_weighted_tardiness_seconds
            ),
            "demands": [dict(row) for row in self.delivery_rows],
        }

    @property
    def planning_document(self) -> JsonObject:
        return {
            "makespan_seconds": self.makespan_seconds,
            "scheduled_operation_count": self.scheduled_operation_count,
            "unscheduled_operation_count": self.unscheduled_operation_count,
        }

    @property
    def resource_documents(self) -> list[JsonObject]:
        return [dict(row) for row in self.resource_rows]


def _reject(code: ReportingContractErrorCode, field: str, message: str) -> Never:
    raise ReportingContractError(code, field=field, message=message)


def _exact_seconds(later: datetime, earlier: datetime, field: str) -> int:
    value = later - earlier
    if value.microseconds:
        _reject(
            ReportingContractErrorCode.INVALID_CONTRACT,
            field,
            "timestamps must resolve to exact integer seconds",
        )
    return value.days * 86400 + value.seconds


def _merged_interval_seconds(
    intervals: list[tuple[datetime, datetime]],
) -> int:
    if not intervals:
        return 0
    ordered = sorted(intervals)
    merged: list[tuple[datetime, datetime]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        elif end > merged[-1][1]:
            merged[-1] = (merged[-1][0], end)
    return sum(_exact_seconds(end, start, "resource interval") for start, end in merged)


def _resource_rows(
    problem: PlanningProblemDocumentV2,
    assignments: list[JsonObject],
) -> list[JsonObject]:
    horizon_start = parse_utc_instant(problem["horizon_start_utc"])
    horizon_end = parse_utc_instant(problem["horizon_end_utc"])
    horizon_seconds = _exact_seconds(horizon_end, horizon_start, "problem.horizon")
    tick_seconds = problem["tick_seconds"]
    busy: defaultdict[str, int] = defaultdict(int)
    for assignment in assignments:
        busy[cast(str, assignment["resource_id"])] += (
            cast(int, assignment["end_tick"])
            - cast(int, assignment["start_tick"])
        ) * tick_seconds

    unavailable: defaultdict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    for item in problem["resource_unavailable_intervals"]:
        start = max(parse_utc_instant(item["start_utc"]), horizon_start)
        end = min(parse_utc_instant(item["end_utc"]), horizon_end)
        if end > start:
            unavailable[item["resource_id"]].append((start, end))

    rows: list[JsonObject] = []
    for resource in sorted(problem["resources"], key=lambda value: value["resource_id"]):
        resource_id = resource["resource_id"]
        available = horizon_seconds - _merged_interval_seconds(unavailable[resource_id])
        planned_busy = busy[resource_id]
        if planned_busy > available:
            _reject(
                ReportingContractErrorCode.INVALID_COUNT,
                f"resources.{resource_id}.planned_busy_seconds",
                "planned busy time exceeds available calendar time",
            )
        rows.append(
            {
                "resource_id": resource_id,
                "resource_code": resource["resource_code"],
                "calendar_id": resource["calendar_id"],
                "available_seconds": available,
                "planned_busy_seconds": planned_busy,
                "utilization": (
                    None if available == 0 else round(planned_busy / available, 12)
                ),
            }
        )
    return rows


def _delivery_rows(
    problem: PlanningProblemDocumentV2,
    assignments: list[JsonObject],
) -> list[JsonObject]:
    horizon_start = parse_utc_instant(problem["horizon_start_utc"])
    operations = {
        operation["operation_id"]: operation
        for operation in problem["operation_instances"]
    }
    assignment_ids = [cast(str, item["operation_id"]) for item in assignments]
    if set(assignment_ids) != set(operations) or len(assignment_ids) != len(operations):
        _reject(
            ReportingContractErrorCode.INVALID_COUNT,
            "solution.assignments",
            "candidate assignments must cover every active Problem operation exactly once",
        )

    completion_ticks: defaultdict[str, list[int]] = defaultdict(list)
    for assignment in assignments:
        operation = operations[cast(str, assignment["operation_id"])]
        completion_ticks[operation["demand_order_id"]].append(
            cast(int, assignment["end_tick"])
        )

    rows: list[JsonObject] = []
    for demand in sorted(
        problem["delivery_demands"], key=lambda value: value["demand_order_id"]
    ):
        demand_id = demand["demand_order_id"]
        if not completion_ticks[demand_id]:
            _reject(
                ReportingContractErrorCode.INVALID_COUNT,
                f"delivery_demands.{demand_id}",
                "every active demand must own at least one active operation",
            )
        completion_tick = max(completion_ticks[demand_id])
        completion_at = horizon_start + timedelta(
            seconds=completion_tick * problem["tick_seconds"]
        )
        due_at = parse_utc_instant(demand["due_at_utc"])
        tardiness = max(0, _exact_seconds(completion_at, due_at, demand_id))
        weight = demand["priority_weight"]
        rows.append(
            {
                "demand_order_id": demand_id,
                "due_at_utc": demand["due_at_utc"],
                "priority_weight": weight,
                "completion_tick": completion_tick,
                "completion_at_utc": format_utc_instant(completion_at),
                "tardiness_seconds": tardiness,
                "priority_weighted_tardiness_seconds": weight * tardiness,
                "on_time": tardiness == 0,
            }
        )
    return rows


def calculate_schedule_kpi_metrics(
    problem: Mapping[str, object],
    assignments: Sequence[Mapping[str, object]],
) -> ScheduleKpiMetrics:
    """Recompute delivery, planning, and resource metrics without solver trust.

    The function consumes only a PlanningProblem and a complete assignment set.
    It performs no I/O, does not mutate either input, and is therefore the common
    schedule-quality boundary for KPI v2, Global CP-SAT benchmark rows, and all
    five Reference Scheduler benchmark rows.
    """

    problem_document = cast(PlanningProblemDocumentV2, problem)
    assignment_documents = [cast(JsonObject, dict(value)) for value in assignments]
    delivery_rows = _delivery_rows(problem_document, assignment_documents)
    resource_rows = _resource_rows(problem_document, assignment_documents)
    order_count = len(delivery_rows)
    on_time_count = sum(1 for row in delivery_rows if row["on_time"] is True)
    total_tardiness = sum(
        cast(int, row["tardiness_seconds"]) for row in delivery_rows
    )
    weighted_tardiness = sum(
        cast(int, row["priority_weighted_tardiness_seconds"])
        for row in delivery_rows
    )
    makespan = (
        max(cast(int, assignment["end_tick"]) for assignment in assignment_documents)
        * problem_document["tick_seconds"]
        if assignment_documents
        else 0
    )
    return ScheduleKpiMetrics(
        delivery_rows=tuple(delivery_rows),
        resource_rows=tuple(resource_rows),
        order_count=order_count,
        on_time_order_count=on_time_count,
        total_tardiness_seconds=total_tardiness,
        priority_weighted_tardiness_seconds=weighted_tardiness,
        makespan_seconds=makespan,
        scheduled_operation_count=len(assignment_documents),
        unscheduled_operation_count=(
            len(problem_document["operation_instances"])
            - len(assignment_documents)
        ),
    )


def _validate_inputs(
    snapshot: Mapping[str, object],
    problem: Mapping[str, object],
    solution: Mapping[str, object],
    solver_report: Mapping[str, object],
    validation_report: Mapping[str, object],
    import_quality_report: Mapping[str, object],
) -> FrozenSolverReport:
    try:
        validate_planning_snapshot_v2(cast(PlanningSnapshotDocumentV2, snapshot))
        if snapshot_hash_for(snapshot) != snapshot.get("snapshot_hash"):
            raise ValueError("snapshot hash mismatch")
        validate_built_problem_v2(problem)
        validate_quality_report_contract(import_quality_report)
    except (KeyError, TypeError, ValueError) as error:
        raise ReportingContractError(
            ReportingContractErrorCode.INVALID_CONTRACT,
            field="snapshot/problem/import_quality_report",
            message="input document validation failed",
        ) from error

    if import_quality_report.get("status") != "PASS":
        _reject(
            ReportingContractErrorCode.VALIDATION_FAILED,
            "import_quality_report.status",
            "output requires a PASS import-quality-report.v1",
        )
    if problem.get("snapshot_id") != snapshot.get("snapshot_id"):
        _reject(
            ReportingContractErrorCode.MIXED_LINEAGE,
            "problem.snapshot_id",
            "Problem and Snapshot identifiers differ",
        )
    snapshot_quality = cast(Mapping[str, object], snapshot["import_quality_report"])
    snapshot_import = cast(Mapping[str, object], snapshot["import_package"])
    if (
        snapshot_quality.get("report_id") != import_quality_report.get("report_id")
        or snapshot_quality.get("status") != "PASS"
        or snapshot_import.get("package_id") != import_quality_report.get("package_id")
    ):
        _reject(
            ReportingContractErrorCode.MIXED_LINEAGE,
            "snapshot.import_quality_report",
            "Snapshot does not bind the supplied PASS ImportQualityReport",
        )

    frozen = freeze_solver_report(solution, solver_report, validation_report)
    solution_problem = cast(Mapping[str, object], solution["problem"])
    exact_problem_fields = (
        "problem_version",
        "problem_builder_version",
        "problem_hash_projection_version",
        "problem_hash",
        "snapshot_id",
        "tick_seconds",
        "horizon_start_utc",
        "horizon_end_utc",
    )
    if any(solution_problem.get(field) != problem.get(field) for field in exact_problem_fields):
        _reject(
            ReportingContractErrorCode.MIXED_LINEAGE,
            "solution.problem",
            "PlanningSolution does not bind the supplied PlanningProblem",
        )
    fresh_validation = validate_problem_schedule(problem, solution)
    if fresh_validation != validation_report:
        _reject(
            ReportingContractErrorCode.VALIDATION_FAILED,
            "validation_report",
            "supplied ValidationReport differs from a fresh formal validation",
        )
    return frozen


def build_kpi_v2(
    *,
    snapshot: Mapping[str, object],
    problem: Mapping[str, object],
    solution: Mapping[str, object],
    solver_report: Mapping[str, object],
    validation_report: Mapping[str, object],
    import_quality_report: Mapping[str, object],
) -> ImmutableKpiV2:
    """Calculate one immutable KPI v2 document from an exact lineage bundle."""

    frozen_report = _validate_inputs(
        snapshot,
        problem,
        solution,
        solver_report,
        validation_report,
        import_quality_report,
    )
    assignments = cast(list[JsonObject], solution["assignments"])
    schedule_metrics = calculate_schedule_kpi_metrics(
        problem,
        cast(list[Mapping[str, object]], assignments),
    )
    stage = cast(list[JsonObject], solution["objective_stage_results"])[0]
    if (
        stage["objective_value"]
        != schedule_metrics.priority_weighted_tardiness_seconds
    ):
        _reject(
            ReportingContractErrorCode.MIXED_LINEAGE,
            "solution.objective_stage_results[0].objective_value",
            "OBJ-001 carrier differs from independently calculated weighted tardiness",
        )
    report_document = frozen_report.document
    timings = cast(JsonObject, report_document["timings"])
    model_metrics = cast(JsonObject, report_document["model_metrics"])
    validation_fingerprint = contract_fingerprint(validation_report)
    quality_fingerprint = contract_fingerprint(import_quality_report)
    basis: JsonObject = {
        "kpi_version": KPI_VERSION,
        "schema_set_version": KPI_SCHEMA_SET_VERSION,
        "canonicalization_version": KPI_CANONICALIZATION_VERSION,
        "planning_run_id": frozen_report.planning_run_id,
        "inputs": {
            "snapshot": {
                "snapshot_version": snapshot["snapshot_version"],
                "snapshot_id": snapshot["snapshot_id"],
                "snapshot_hash": snapshot["snapshot_hash"],
            },
            "problem": {
                "problem_version": problem["problem_version"],
                "problem_hash": problem["problem_hash"],
            },
            "solution": {
                "planning_solution_version": solution["planning_solution_version"],
                "solution_id": solution["solution_id"],
                "solution_fingerprint": contract_fingerprint(solution),
            },
            "validation_report": {
                "validation_report_version": validation_report[
                    "validation_report_version"
                ],
                "validation_report_fingerprint": validation_fingerprint,
                "status": validation_report["status"],
            },
            "solver_report": {
                "solver_report_version": solver_report["solver_report_version"],
                "report_id": solver_report["report_id"],
                "solver_report_fingerprint": frozen_report.fingerprint,
            },
            "import_quality_report": {
                "report_version": import_quality_report["report_version"],
                "report_id": import_quality_report["report_id"],
                "import_quality_report_fingerprint": quality_fingerprint,
                "status": import_quality_report["status"],
            },
        },
        "delivery": schedule_metrics.delivery_document,
        "planning": schedule_metrics.planning_document,
        "resources": schedule_metrics.resource_documents,
        "stability": {
            "status": STABILITY_STATUS,
            "changed_operation_count": None,
            "resource_changed_count": None,
            "start_shift_seconds": None,
            "schedule_stability_ratio": None,
        },
        "solver": {
            "solver_status": solution["solver_status"],
            "objective_value": stage["objective_value"],
            "best_bound": stage["best_bound"],
            "relative_gap": stage["relative_gap"],
            "model_build_seconds": timings["model_build_seconds"],
            "first_feasible_seconds": timings["first_feasible_seconds"],
            "solve_seconds": timings["solve_seconds"],
            "validation_seconds": timings["validation_seconds"],
            "total_seconds": timings["total_seconds"],
            "variables": model_metrics["variables"],
            "constraints": model_metrics["constraints"],
            "optional_intervals": model_metrics["optional_intervals"],
            "memory_peak_mb": report_document["memory_peak_mb"],
        },
        "synthetic": snapshot["synthetic"],
    }
    if snapshot["synthetic"] is True:
        basis["synthetic_provenance"] = snapshot["synthetic_provenance"]
    kpi_id = f"kpi-{sha256(canonical_contract_bytes(basis)).hexdigest()}"
    document = {"kpi_id": kpi_id, **basis}
    canonical_bytes = canonical_contract_bytes(document)
    return ImmutableKpiV2(
        canonical_bytes=canonical_bytes,
        fingerprint=contract_fingerprint(document),
        kpi_id=kpi_id,
        planning_run_id=frozen_report.planning_run_id,
    )


__all__ = [
    "ImmutableKpiV2",
    "KPI_CANONICALIZATION_VERSION",
    "KPI_SCHEMA_SET_VERSION",
    "KPI_VERSION",
    "ScheduleKpiMetrics",
    "STABILITY_STATUS",
    "build_kpi_v2",
    "calculate_schedule_kpi_metrics",
]
