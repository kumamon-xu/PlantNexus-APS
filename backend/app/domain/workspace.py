"""Pure, solver-neutral P3 workspace projections and comparison semantics.

The strict ``workspace-query.v1`` carrier intentionally stores projection
references.  ``WorkspaceProjection`` keeps the complete in-process payload for
future API consumers while binding every payload to the carrier by SHA-256.
This module performs no repository access, authorization, state transition,
Solver execution, validation, publication, export, or P4 replanning.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import base64
import json
from typing import Never, cast

from app.domain.types import parse_utc_instant
from app.domain.workspace_contracts import (
    CANONICALIZATION_VERSION,
    WORKSPACE_V1_SCHEMA_SET_VERSION as SCHEMA_SET_VERSION,
    canonical_workspace_bytes,
    comparison_fingerprint,
    require_workspace_document,
    workspace_fingerprint,
    workspace_query_fingerprint,
)


WORKSPACE_READ_MODEL_VERSION = "workspace-read-model.v1"
WORKSPACE_CURSOR_VERSION = "workspace-cursor.v1"
SCHEDULE_COMPARISON_VERSION = "schedule-version-comparison.v1"


class WorkspaceView(StrEnum):
    DATA_HEALTH = "DATA_HEALTH"
    IMPORT_RUNS = "IMPORT_RUNS"
    PLANNING_RUNS = "PLANNING_RUNS"
    ORDERS = "ORDERS"
    OPERATIONS = "OPERATIONS"
    RESOURCES = "RESOURCES"
    CALENDARS = "CALENDARS"
    GANTT = "GANTT"
    RESOURCE_LOAD = "RESOURCE_LOAD"
    KPI = "KPI"
    DIAGNOSTICS = "DIAGNOSTICS"
    LOCKS = "LOCKS"
    AUDIT = "AUDIT"
    VERSION_COMPARISON = "VERSION_COMPARISON"


class WorkspaceReadFailure(StrEnum):
    INVALID_QUERY = "INVALID_QUERY"
    SOURCE_MISSING = "SOURCE_MISSING"
    MIXED_LINEAGE = "MIXED_LINEAGE"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    STALE_VERSION = "STALE_VERSION"
    STALE_CURSOR = "STALE_CURSOR"
    KPI_MISMATCH = "KPI_MISMATCH"


class WorkspaceReadError(ValueError):
    """Sanitized, stable read-side rejection without source payload leakage."""

    def __init__(
        self,
        reason: WorkspaceReadFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value}: {field}: {message}")


def _reject(
    reason: WorkspaceReadFailure,
    *,
    field: str,
    message: str,
) -> Never:
    raise WorkspaceReadError(reason, field=field, message=message)


@dataclass(frozen=True, slots=True)
class WorkspaceSourceDocuments:
    """Immutable upstream artifacts used to project one ScheduleVersion."""

    snapshot: Mapping[str, object]
    problem: Mapping[str, object]
    solution: Mapping[str, object]
    solver_report: Mapping[str, object]
    validation_report: Mapping[str, object]
    import_quality_report: Mapping[str, object]
    kpi: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class WorkspaceProjection:
    """A complete internal payload and its strict carrier reference."""

    item_id: str
    item_type: str
    payload: dict[str, object]
    payload_fingerprint: str

    @property
    def carrier_reference(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "payload_fingerprint": self.payload_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceProjectionPage:
    """Stable page result before the application wraps it in a query carrier."""

    items: tuple[WorkspaceProjection, ...]
    next_cursor: str | None
    observed_count: int
    collection_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkspaceQuerySpec:
    view: WorkspaceView
    query_fingerprint: str
    data_plane: str
    environment: str
    resource_type: str
    resource_id: str | None
    schedule_version_precondition: Mapping[str, object] | None
    sort: tuple[Mapping[str, object], ...]
    filters: Mapping[str, object]
    page_size: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class BoundWorkspaceSources:
    """Validated source bundle indexes shared by all projections."""

    source_fingerprint: str
    assignments: tuple[Mapping[str, object], ...]
    assignments_by_operation: Mapping[str, Mapping[str, object]]
    operations: tuple[Mapping[str, object], ...]
    operations_by_id: Mapping[str, Mapping[str, object]]
    resources: tuple[Mapping[str, object], ...]
    resources_by_id: Mapping[str, Mapping[str, object]]
    kpi_resources_by_id: Mapping[str, Mapping[str, object]]


_WORKSPACE_VIEWS = frozenset(
    {
        WorkspaceView.DATA_HEALTH,
        WorkspaceView.IMPORT_RUNS,
        WorkspaceView.PLANNING_RUNS,
    }
)
_SCHEDULE_VIEWS = frozenset(set(WorkspaceView) - _WORKSPACE_VIEWS)
_SORT_FIELDS = frozenset(
    {
        "ITEM_ID",
        "START_AT_UTC",
        "END_AT_UTC",
        "RESOURCE_ID",
        "ORDER_ID",
        "OCCURRED_AT_UTC",
    }
)
_ITEM_TYPES: Mapping[WorkspaceView, str] = {
    WorkspaceView.DATA_HEALTH: "DATA_HEALTH",
    WorkspaceView.IMPORT_RUNS: "IMPORT_RUN",
    WorkspaceView.PLANNING_RUNS: "PLANNING_RUN",
    WorkspaceView.ORDERS: "ORDER",
    WorkspaceView.OPERATIONS: "OPERATION",
    WorkspaceView.RESOURCES: "RESOURCE",
    WorkspaceView.CALENDARS: "CALENDAR",
    WorkspaceView.GANTT: "GANTT_SEGMENT",
    WorkspaceView.RESOURCE_LOAD: "RESOURCE_LOAD",
    WorkspaceView.KPI: "KPI",
    WorkspaceView.DIAGNOSTICS: "DIAGNOSTIC",
    WorkspaceView.LOCKS: "LOCK",
    WorkspaceView.AUDIT: "AUDIT_REFERENCE",
    WorkspaceView.VERSION_COMPARISON: "VERSION_COMPARISON",
}


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(
            WorkspaceReadFailure.SOURCE_MISSING,
            field=field,
            message="authoritative source must be an object",
        )
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        _reject(
            WorkspaceReadFailure.SOURCE_MISSING,
            field=field,
            message="authoritative source must be an array",
        )
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _reject(
            WorkspaceReadFailure.SOURCE_MISSING,
            field=field,
            message="authoritative source requires bounded non-empty text",
        )
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _reject(
            WorkspaceReadFailure.SOURCE_MISSING,
            field=field,
            message="authoritative source requires a bounded integer",
        )
    return value


def _number(value: object, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(
            WorkspaceReadFailure.SOURCE_MISSING,
            field=field,
            message="authoritative source requires a finite number",
        )
    return value


def _clone(value: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(canonical_workspace_bytes(value)))


def _rows(value: object, field: str) -> tuple[Mapping[str, object], ...]:
    return tuple(
        _mapping(row, f"{field}[{index}]")
        for index, row in enumerate(_sequence(value, field))
    )


def _index(
    rows: Sequence[Mapping[str, object]],
    *,
    id_field: str,
    field: str,
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for index, row in enumerate(rows):
        identity = _text(row.get(id_field), f"{field}[{index}].{id_field}")
        if identity in result:
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field=f"{field}.{id_field}",
                message="duplicate authoritative identity",
            )
        result[identity] = row
    return result


def _require_equal(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        _reject(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field=field,
            message="does not bind the authoritative source lineage",
        )


def _artifact_fingerprint(document: Mapping[str, object]) -> str:
    return workspace_fingerprint(document)


def _expected_locks(problem: Mapping[str, object]) -> list[dict[str, object]]:
    mapping = {"HARD_LOCK": "HARD", "SOFT_LOCK": "SOFT"}
    values: list[dict[str, object]] = []
    for index, raw in enumerate(
        _rows(problem.get("operation_locks"), "problem.operation_locks")
    ):
        lock_type = mapping.get(
            _text(raw.get("lock_type"), f"problem.operation_locks[{index}].lock_type")
        )
        if lock_type is None:
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field=f"problem.operation_locks[{index}].lock_type",
                message="unsupported source lock type",
            )
        values.append(
            {
                "lock_id": _text(raw.get("lock_id"), "lock.lock_id"),
                "operation_id": _text(raw.get("operation_id"), "lock.operation_id"),
                "lock_type": lock_type,
                "resource_id": _text(raw.get("resource_id"), "lock.resource_id"),
                "start_at_utc": _text(raw.get("start_at_utc"), "lock.start_at_utc"),
                "end_at_utc": _text(raw.get("end_at_utc"), "lock.end_at_utc"),
            }
        )
    values.sort(key=lambda row: cast(str, row["lock_id"]))
    return values


def require_workspace_sources(sources: WorkspaceSourceDocuments) -> str:
    """Verify the intrinsic P1/P2 lineage shared by every workspace view."""

    snapshot_id = _text(sources.snapshot.get("snapshot_id"), "snapshot.snapshot_id")
    snapshot_hash = _text(
        sources.snapshot.get("snapshot_hash"), "snapshot.snapshot_hash"
    )
    problem_hash = _text(sources.problem.get("problem_hash"), "problem.problem_hash")
    solution_id = _text(sources.solution.get("solution_id"), "solution.solution_id")
    solution_fingerprint = _artifact_fingerprint(sources.solution)
    validation_fingerprint = _artifact_fingerprint(sources.validation_report)
    solver_fingerprint = _artifact_fingerprint(sources.solver_report)
    quality_fingerprint = _artifact_fingerprint(sources.import_quality_report)

    _require_equal(
        sources.problem.get("snapshot_id"), snapshot_id, "problem.snapshot_id"
    )
    for field, value in (
        ("solution.problem", sources.solution.get("problem")),
        ("solver_report.problem", sources.solver_report.get("problem")),
    ):
        reference = _mapping(value, field)
        _require_equal(
            reference.get("snapshot_id"), snapshot_id, f"{field}.snapshot_id"
        )
        _require_equal(
            reference.get("problem_hash"), problem_hash, f"{field}.problem_hash"
        )
    _require_equal(
        sources.validation_report.get("problem_hash"),
        problem_hash,
        "validation_report.problem_hash",
    )
    solver_solution = _mapping(
        sources.solver_report.get("solution"), "solver_report.solution"
    )
    _require_equal(
        solver_solution.get("solution_id"), solution_id, "solver_report.solution_id"
    )
    _require_equal(
        solver_solution.get("solution_fingerprint"),
        solution_fingerprint,
        "solver_report.solution_fingerprint",
    )

    quality_reference = _mapping(
        sources.snapshot.get("import_quality_report"),
        "snapshot.import_quality_report",
    )
    _require_equal(
        quality_reference.get("report_id"),
        sources.import_quality_report.get("report_id"),
        "snapshot.import_quality_report.report_id",
    )
    _require_equal(
        quality_reference.get("status"),
        sources.import_quality_report.get("status"),
        "snapshot.import_quality_report.status",
    )

    kpi_inputs = _mapping(sources.kpi.get("inputs"), "kpi.inputs")
    expected_inputs: Mapping[str, Mapping[str, object]] = {
        "snapshot": {
            "snapshot_id": snapshot_id,
            "snapshot_hash": snapshot_hash,
        },
        "problem": {"problem_hash": problem_hash},
        "solution": {
            "solution_id": solution_id,
            "solution_fingerprint": solution_fingerprint,
        },
        "validation_report": {
            "validation_report_fingerprint": validation_fingerprint,
        },
        "solver_report": {
            "report_id": sources.solver_report.get("report_id"),
            "solver_report_fingerprint": solver_fingerprint,
        },
        "import_quality_report": {
            "report_id": sources.import_quality_report.get("report_id"),
            "import_quality_report_fingerprint": quality_fingerprint,
        },
    }
    for name, expected in expected_inputs.items():
        reference = _mapping(kpi_inputs.get(name), f"kpi.inputs.{name}")
        for field, value in expected.items():
            _require_equal(reference.get(field), value, f"kpi.inputs.{name}.{field}")
    _require_equal(
        sources.kpi.get("synthetic"),
        sources.snapshot.get("synthetic"),
        "kpi.synthetic",
    )
    if sources.snapshot.get("synthetic") is True:
        _require_equal(
            sources.kpi.get("synthetic_provenance"),
            sources.snapshot.get("synthetic_provenance"),
            "kpi.synthetic_provenance",
        )
    return workspace_fingerprint(
        {
            "workspace_source_set_version": "workspace-source-set.v1",
            "documents": [
                _artifact_fingerprint(document)
                for document in (
                    sources.snapshot,
                    sources.problem,
                    sources.solution,
                    sources.solver_report,
                    sources.validation_report,
                    sources.import_quality_report,
                    sources.kpi,
                )
            ],
        }
    )


def bind_workspace_sources(
    schedule_version: Mapping[str, object],
    sources: WorkspaceSourceDocuments,
    *,
    expected_data_plane: str,
) -> BoundWorkspaceSources:
    """Cross-check exact ScheduleVersion lineage and read-side KPI consistency."""

    require_workspace_sources(sources)
    try:
        require_workspace_document(schedule_version)
    except (TypeError, ValueError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="schedule_version",
            message="stored ScheduleVersion failed its immutable carrier contract",
        ) from error
    _require_equal(
        schedule_version.get("data_plane"),
        expected_data_plane,
        "schedule_version.data_plane",
    )
    lineage = _mapping(schedule_version.get("lineage"), "schedule_version.lineage")
    snapshot = sources.snapshot
    problem = sources.problem
    solution = sources.solution
    validation = sources.validation_report
    solver_report = sources.solver_report
    kpi = sources.kpi

    actual_references: Mapping[str, tuple[str, str, str]] = {
        "snapshot": (
            _text(snapshot.get("snapshot_id"), "snapshot.snapshot_id"),
            _text(snapshot.get("snapshot_hash"), "snapshot.snapshot_hash"),
            "planning-snapshot.v2",
        ),
        "problem": (
            f"planning-problem-{_text(problem.get('problem_hash'), 'problem.problem_hash').removeprefix('sha256:')}",
            _text(problem.get("problem_hash"), "problem.problem_hash"),
            "planning-problem.v2",
        ),
        "planning_solution": (
            _text(solution.get("solution_id"), "solution.solution_id"),
            _artifact_fingerprint(solution),
            "planning-solution.v1",
        ),
        "validation_report": (
            f"validation-report-{_artifact_fingerprint(validation).removeprefix('sha256:')}",
            _artifact_fingerprint(validation),
            "validation-report.v2",
        ),
        "kpi": (
            _text(kpi.get("kpi_id"), "kpi.kpi_id"),
            _artifact_fingerprint(kpi),
            "kpi.v2",
        ),
        "solver_report": (
            _text(solver_report.get("report_id"), "solver_report.report_id"),
            _artifact_fingerprint(solver_report),
            "solver-report.v1",
        ),
    }
    for name, (artifact_id, fingerprint, version) in actual_references.items():
        reference = _mapping(lineage.get(name), f"lineage.{name}")
        _require_equal(
            reference.get("artifact_id"), artifact_id, f"lineage.{name}.artifact_id"
        )
        _require_equal(
            reference.get("fingerprint"), fingerprint, f"lineage.{name}.fingerprint"
        )
        _require_equal(
            reference.get("document_version"),
            version,
            f"lineage.{name}.document_version",
        )

    planning_run_id = _text(
        solver_report.get("planning_run_id"), "solver_report.planning_run_id"
    )
    _require_equal(
        lineage.get("planning_run_id"), planning_run_id, "lineage.planning_run_id"
    )
    _require_equal(kpi.get("planning_run_id"), planning_run_id, "kpi.planning_run_id")
    provenance = _mapping(solver_report.get("provenance"), "solver_report.provenance")
    _require_equal(
        lineage.get("code_commit"), provenance.get("code_commit"), "lineage.code_commit"
    )
    if (
        validation.get("status") != "PASS"
        or validation.get("hard_violation_count") != 0
    ):
        _reject(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="validation_report",
            message="workspace projection requires the stored fresh PASS lineage",
        )

    content = _mapping(schedule_version.get("content"), "schedule_version.content")
    assignments = tuple(
        sorted(
            _rows(content.get("assignments"), "schedule_version.content.assignments"),
            key=lambda row: _text(row.get("operation_id"), "assignment.operation_id"),
        )
    )
    solution_assignments = [
        _clone(row)
        for row in sorted(
            _rows(solution.get("assignments"), "solution.assignments"),
            key=lambda row: _text(
                row.get("operation_id"), "solution.assignment.operation_id"
            ),
        )
    ]
    _require_equal(
        [_clone(row) for row in assignments],
        solution_assignments,
        "schedule_version.content.assignments",
    )
    _require_equal(
        [
            _clone(row)
            for row in _rows(content.get("locks"), "schedule_version.content.locks")
        ],
        _expected_locks(problem),
        "schedule_version.content.locks",
    )

    operations = tuple(
        sorted(
            _rows(problem.get("operation_instances"), "problem.operation_instances"),
            key=lambda row: _text(row.get("operation_id"), "operation.operation_id"),
        )
    )
    resources = tuple(
        sorted(
            _rows(problem.get("resources"), "problem.resources"),
            key=lambda row: _text(row.get("resource_id"), "resource.resource_id"),
        )
    )
    assignments_by_operation = _index(
        assignments,
        id_field="operation_id",
        field="schedule_version.content.assignments",
    )
    operations_by_id = _index(
        operations,
        id_field="operation_id",
        field="problem.operation_instances",
    )
    resources_by_id = _index(
        resources, id_field="resource_id", field="problem.resources"
    )
    kpi_root = _mapping(kpi, "kpi")
    kpi_resources = _rows(kpi_root.get("resources"), "kpi.resources")
    kpi_resources_by_id = _index(
        kpi_resources,
        id_field="resource_id",
        field="kpi.resources",
    )

    busy_seconds: dict[str, int] = {identity: 0 for identity in resources_by_id}
    for assignment in assignments:
        operation_id = _text(assignment.get("operation_id"), "assignment.operation_id")
        resource_id = _text(assignment.get("resource_id"), "assignment.resource_id")
        if operation_id not in operations_by_id or resource_id not in resources_by_id:
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="schedule_version.content.assignments",
                message="assignment references an absent Problem operation or resource",
            )
        busy_seconds[resource_id] += _integer(
            assignment.get("duration_seconds"), "assignment.duration_seconds"
        )
    for resource_id, seconds in busy_seconds.items():
        kpi_row = kpi_resources_by_id.get(resource_id)
        if kpi_row is None:
            _reject(
                WorkspaceReadFailure.KPI_MISMATCH,
                field="kpi.resources",
                message="resource KPI row is absent",
            )
        if kpi_row.get("planned_busy_seconds") != seconds:
            _reject(
                WorkspaceReadFailure.KPI_MISMATCH,
                field="kpi.resources.planned_busy_seconds",
                message="resource load differs from immutable assignments",
            )

    source_fingerprint = workspace_fingerprint(
        {
            "read_model_version": WORKSPACE_READ_MODEL_VERSION,
            "schedule_version_id": schedule_version.get("schedule_version_id"),
            "content_fingerprint": schedule_version.get("content_fingerprint"),
            "lineage": lineage,
        }
    )
    return BoundWorkspaceSources(
        source_fingerprint=source_fingerprint,
        assignments=assignments,
        assignments_by_operation=assignments_by_operation,
        operations=operations,
        operations_by_id=operations_by_id,
        resources=resources,
        resources_by_id=resources_by_id,
        kpi_resources_by_id=kpi_resources_by_id,
    )


def _projection(
    item_id: str, item_type: str, payload: Mapping[str, object]
) -> WorkspaceProjection:
    frozen = _clone(payload)
    return WorkspaceProjection(
        item_id=item_id,
        item_type=item_type,
        payload=frozen,
        payload_fingerprint=workspace_fingerprint(frozen),
    )


def _derived_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}-{workspace_fingerprint(payload).removeprefix('sha256:')}"


def _record_indexes(
    snapshot: Mapping[str, object],
) -> Mapping[str, Mapping[str, Mapping[str, object]]]:
    records = _mapping(snapshot.get("records"), "snapshot.records")
    collections: Mapping[str, str] = {
        "demand_orders": "demand_order_id",
        "calendars": "calendar_id",
        "resources": "resource_id",
    }
    return {
        name: _index(
            _rows(records.get(name), f"snapshot.records.{name}"),
            id_field=id_field,
            field=f"snapshot.records.{name}",
        )
        for name, id_field in collections.items()
    }


def _data_health(sources: WorkspaceSourceDocuments) -> list[WorkspaceProjection]:
    snapshot = sources.snapshot
    quality = sources.import_quality_report
    package = _mapping(snapshot.get("import_package"), "snapshot.import_package")
    payload: dict[str, object] = {
        "snapshot_id": _text(snapshot.get("snapshot_id"), "snapshot.snapshot_id"),
        "snapshot_hash": _text(snapshot.get("snapshot_hash"), "snapshot.snapshot_hash"),
        "cutoff_at_utc": _text(snapshot.get("cutoff_at_utc"), "snapshot.cutoff_at_utc"),
        "import_package_id": _text(
            package.get("package_id"), "snapshot.import_package.package_id"
        ),
        "dataset_hash": _text(
            package.get("dataset_hash"), "snapshot.import_package.dataset_hash"
        ),
        "quality_report_id": _text(quality.get("report_id"), "quality.report_id"),
        "quality_status": _text(quality.get("status"), "quality.status"),
        "quality_error_count": _integer(
            quality.get("error_count"), "quality.error_count"
        ),
        "entity_counts": _clone(
            _mapping(snapshot.get("entity_counts"), "snapshot.entity_counts")
        ),
        "source_versions": _clone(
            _mapping(snapshot.get("source_versions"), "snapshot.source_versions")
        ),
        "synthetic": snapshot.get("synthetic"),
    }
    return [_projection(_derived_id("data-health", payload), "DATA_HEALTH", payload)]


def _import_runs(sources: WorkspaceSourceDocuments) -> list[WorkspaceProjection]:
    snapshot = sources.snapshot
    quality = sources.import_quality_report
    package = _mapping(snapshot.get("import_package"), "snapshot.import_package")
    payload: dict[str, object] = {
        "import_run_id": _text(quality.get("report_id"), "quality.report_id"),
        "import_package_id": _text(
            package.get("package_id"), "snapshot.import_package.package_id"
        ),
        "import_package_version": package.get("import_package_version"),
        "dataset_hash": package.get("dataset_hash"),
        "status": quality.get("status"),
        "error_count": quality.get("error_count"),
        "source_versions": _clone(
            _mapping(snapshot.get("source_versions"), "snapshot.source_versions")
        ),
        "snapshot_id": snapshot.get("snapshot_id"),
        "snapshot_hash": snapshot.get("snapshot_hash"),
    }
    return [_projection(cast(str, payload["import_run_id"]), "IMPORT_RUN", payload)]


def _planning_runs(sources: WorkspaceSourceDocuments) -> list[WorkspaceProjection]:
    report = sources.solver_report
    outcome = _mapping(
        report.get("planning_run_outcome"), "solver_report.planning_run_outcome"
    )
    payload: dict[str, object] = {
        "planning_run_id": _text(
            report.get("planning_run_id"), "solver_report.planning_run_id"
        ),
        "state": outcome.get("state"),
        "solver_status": report.get("solver_status"),
        "started_at_utc": report.get("started_at_utc"),
        "finished_at_utc": report.get("finished_at_utc"),
        "timings": _clone(_mapping(report.get("timings"), "solver_report.timings")),
        "model_metrics": _clone(
            _mapping(report.get("model_metrics"), "solver_report.model_metrics")
        ),
        "problem": _clone(_mapping(report.get("problem"), "solver_report.problem")),
        "solution": _clone(_mapping(report.get("solution"), "solver_report.solution")),
        "validation_status": sources.validation_report.get("status"),
        "snapshot_id": sources.snapshot.get("snapshot_id"),
    }
    return [_projection(cast(str, payload["planning_run_id"]), "PLANNING_RUN", payload)]


def _orders(
    sources: WorkspaceSourceDocuments,
    bound: BoundWorkspaceSources,
) -> list[WorkspaceProjection]:
    delivery = _mapping(sources.kpi.get("delivery"), "kpi.delivery")
    demands = _rows(delivery.get("demands"), "kpi.delivery.demands")
    demand_sources = _record_indexes(sources.snapshot)["demand_orders"]
    operation_counts: dict[str, int] = {}
    for operation in bound.operations:
        order_id = _text(operation.get("demand_order_id"), "operation.demand_order_id")
        operation_counts[order_id] = operation_counts.get(order_id, 0) + 1
    values: list[WorkspaceProjection] = []
    for demand in demands:
        order_id = _text(demand.get("demand_order_id"), "kpi.delivery.demand_order_id")
        source_record = demand_sources.get(order_id)
        payload = {
            "order_id": order_id,
            "due_at_utc": demand.get("due_at_utc"),
            "completion_at_utc": demand.get("completion_at_utc"),
            "completion_tick": demand.get("completion_tick"),
            "tardiness_seconds": demand.get("tardiness_seconds"),
            "priority_weight": demand.get("priority_weight"),
            "priority_weighted_tardiness_seconds": demand.get(
                "priority_weighted_tardiness_seconds"
            ),
            "on_time": demand.get("on_time"),
            "operation_count": operation_counts.get(order_id, 0),
            "source": (
                _clone(_mapping(source_record.get("source"), "demand.source"))
                if source_record is not None
                else None
            ),
        }
        values.append(_projection(order_id, "ORDER", payload))
    return values


def _operations(
    bound: BoundWorkspaceSources,
) -> list[WorkspaceProjection]:
    values: list[WorkspaceProjection] = []
    for operation in bound.operations:
        operation_id = _text(operation.get("operation_id"), "operation.operation_id")
        assignment = bound.assignments_by_operation.get(operation_id)
        payload: dict[str, object] = {
            "operation_id": operation_id,
            "order_id": operation.get("demand_order_id"),
            "status": operation.get("status"),
            "release_at_utc": operation.get("release_at_utc"),
            "material_ready_at_utc": operation.get("material_ready_at_utc"),
            "required_capabilities": list(
                cast(Sequence[object], operation.get("required_capabilities", []))
            ),
            "scheduled": assignment is not None,
            "resource_id": assignment.get("resource_id")
            if assignment is not None
            else None,
            "start_at_utc": assignment.get("start_at_utc")
            if assignment is not None
            else None,
            "end_at_utc": assignment.get("end_at_utc")
            if assignment is not None
            else None,
            "duration_seconds": assignment.get("duration_seconds")
            if assignment is not None
            else None,
            "start_tick": assignment.get("start_tick")
            if assignment is not None
            else None,
            "end_tick": assignment.get("end_tick") if assignment is not None else None,
            "lock_ids": list(cast(Sequence[object], assignment.get("lock_ids", [])))
            if assignment is not None
            else [],
            "execution_fact_ids": list(
                cast(Sequence[object], assignment.get("execution_fact_ids", []))
            )
            if assignment is not None
            else [],
        }
        values.append(_projection(operation_id, "OPERATION", payload))
    return values


def _resource_assignment_stats(
    bound: BoundWorkspaceSources,
) -> tuple[dict[str, int], dict[str, int]]:
    counts = {identity: 0 for identity in bound.resources_by_id}
    busy = {identity: 0 for identity in bound.resources_by_id}
    for assignment in bound.assignments:
        resource_id = _text(assignment.get("resource_id"), "assignment.resource_id")
        counts[resource_id] += 1
        busy[resource_id] += _integer(
            assignment.get("duration_seconds"), "assignment.duration_seconds"
        )
    return counts, busy


def _resources(bound: BoundWorkspaceSources) -> list[WorkspaceProjection]:
    counts, busy = _resource_assignment_stats(bound)
    values: list[WorkspaceProjection] = []
    for resource in bound.resources:
        resource_id = _text(resource.get("resource_id"), "resource.resource_id")
        kpi = bound.kpi_resources_by_id[resource_id]
        payload = {
            "resource_id": resource_id,
            "resource_code": resource.get("resource_code"),
            "resource_type": resource.get("resource_type"),
            "status": resource.get("status"),
            "factory_id": resource.get("factory_id"),
            "workshop_id": resource.get("workshop_id"),
            "production_line_id": resource.get("production_line_id"),
            "resource_group_id": resource.get("resource_group_id"),
            "calendar_id": resource.get("calendar_id"),
            "capabilities": list(
                cast(Sequence[object], resource.get("capabilities", []))
            ),
            "capacity": resource.get("capacity"),
            "assignment_count": counts[resource_id],
            "planned_busy_seconds": busy[resource_id],
            "available_seconds": kpi.get("available_seconds"),
            "utilization": kpi.get("utilization"),
        }
        values.append(_projection(resource_id, "RESOURCE", payload))
    return values


def _calendars(
    sources: WorkspaceSourceDocuments,
    bound: BoundWorkspaceSources,
) -> list[WorkspaceProjection]:
    calendars = _record_indexes(sources.snapshot)["calendars"]
    resource_ids_by_calendar: dict[str, list[str]] = {}
    for resource in bound.resources:
        calendar_id = _text(resource.get("calendar_id"), "resource.calendar_id")
        resource_ids_by_calendar.setdefault(calendar_id, []).append(
            _text(resource.get("resource_id"), "resource.resource_id")
        )
    values: list[WorkspaceProjection] = []
    for calendar_id in sorted(resource_ids_by_calendar):
        calendar = calendars.get(calendar_id)
        if calendar is None:
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="snapshot.records.calendars",
                message="Problem resource calendar is absent from Snapshot",
            )
        payload = {
            "calendar_id": calendar_id,
            "timezone": calendar.get("timezone"),
            "resource_ids": sorted(resource_ids_by_calendar[calendar_id]),
            "unavailable_intervals": [
                _clone(row)
                for row in _rows(
                    calendar.get("unavailable_intervals"),
                    "calendar.unavailable_intervals",
                )
            ],
            "source": _clone(_mapping(calendar.get("source"), "calendar.source")),
        }
        values.append(_projection(calendar_id, "CALENDAR", payload))
    return values


def _gantt(bound: BoundWorkspaceSources) -> list[WorkspaceProjection]:
    values: list[WorkspaceProjection] = []
    for assignment in bound.assignments:
        operation_id = _text(assignment.get("operation_id"), "assignment.operation_id")
        resource_id = _text(assignment.get("resource_id"), "assignment.resource_id")
        operation = bound.operations_by_id[operation_id]
        resource = bound.resources_by_id[resource_id]
        payload = {
            "operation_id": operation_id,
            "order_id": operation.get("demand_order_id"),
            "resource_id": resource_id,
            "resource_code": resource.get("resource_code"),
            "factory_id": resource.get("factory_id"),
            "workshop_id": resource.get("workshop_id"),
            "production_line_id": resource.get("production_line_id"),
            "resource_group_id": resource.get("resource_group_id"),
            "start_at_utc": assignment.get("start_at_utc"),
            "end_at_utc": assignment.get("end_at_utc"),
            "duration_seconds": assignment.get("duration_seconds"),
            "start_tick": assignment.get("start_tick"),
            "end_tick": assignment.get("end_tick"),
            "lock_ids": list(cast(Sequence[object], assignment.get("lock_ids", []))),
            "execution_fact_ids": list(
                cast(Sequence[object], assignment.get("execution_fact_ids", []))
            ),
        }
        values.append(_projection(f"gantt-{operation_id}", "GANTT_SEGMENT", payload))
    return values


def _resource_load(
    sources: WorkspaceSourceDocuments,
    bound: BoundWorkspaceSources,
) -> list[WorkspaceProjection]:
    counts, busy = _resource_assignment_stats(bound)
    horizon_start = sources.problem.get("horizon_start_utc")
    horizon_end = sources.problem.get("horizon_end_utc")
    values: list[WorkspaceProjection] = []
    for resource in bound.resources:
        resource_id = _text(resource.get("resource_id"), "resource.resource_id")
        kpi = bound.kpi_resources_by_id[resource_id]
        payload = {
            "resource_id": resource_id,
            "resource_code": resource.get("resource_code"),
            "calendar_id": resource.get("calendar_id"),
            "start_at_utc": horizon_start,
            "end_at_utc": horizon_end,
            "bucket_kind": "PLANNING_HORIZON",
            "assignment_count": counts[resource_id],
            "planned_busy_seconds": busy[resource_id],
            "available_seconds": kpi.get("available_seconds"),
            "utilization": kpi.get("utilization"),
        }
        values.append(
            _projection(f"resource-load-{resource_id}", "RESOURCE_LOAD", payload)
        )
    return values


def _kpi(sources: WorkspaceSourceDocuments) -> list[WorkspaceProjection]:
    payload = _clone(sources.kpi)
    return [_projection(_text(payload.get("kpi_id"), "kpi.kpi_id"), "KPI", payload)]


def _diagnostics(sources: WorkspaceSourceDocuments) -> list[WorkspaceProjection]:
    values: list[WorkspaceProjection] = []
    report = sources.solver_report
    for raw in _rows(report.get("diagnostics"), "solver_report.diagnostics"):
        payload = {
            "diagnostic_source": "SOLVER_REPORT",
            "code": raw.get("code"),
            "message": raw.get("message"),
            "solver_status": report.get("solver_status"),
            "planning_run_id": report.get("planning_run_id"),
        }
        values.append(
            _projection(_derived_id("diagnostic", payload), "DIAGNOSTIC", payload)
        )
    validation_payload = {
        "diagnostic_source": "VALIDATION_REPORT",
        "status": sources.validation_report.get("status"),
        "hard_violation_count": sources.validation_report.get("hard_violation_count"),
        "violations": [
            _clone(row)
            for row in _rows(
                sources.validation_report.get("violations"),
                "validation_report.violations",
            )
        ],
    }
    values.append(
        _projection(
            _derived_id("validation-diagnostic", validation_payload),
            "DIAGNOSTIC",
            validation_payload,
        )
    )
    return values


def _locks(schedule_version: Mapping[str, object]) -> list[WorkspaceProjection]:
    content = _mapping(schedule_version.get("content"), "schedule_version.content")
    return [
        _projection(_text(lock.get("lock_id"), "lock.lock_id"), "LOCK", lock)
        for lock in _rows(content.get("locks"), "schedule_version.content.locks")
    ]


def _audit(audit_events: Sequence[Mapping[str, object]]) -> list[WorkspaceProjection]:
    values: list[WorkspaceProjection] = []
    for event in audit_events:
        try:
            require_workspace_document(event)
        except (TypeError, ValueError) as error:
            raise WorkspaceReadError(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="audit_events",
                message="stored AuditEvent failed its append-only carrier contract",
            ) from error
        values.append(
            _projection(
                _text(event.get("audit_event_id"), "audit_event.audit_event_id"),
                "AUDIT_REFERENCE",
                event,
            )
        )
    return values


def build_workspace_projections(
    view: WorkspaceView,
    *,
    sources: WorkspaceSourceDocuments,
    schedule_version: Mapping[str, object] | None = None,
    bound: BoundWorkspaceSources | None = None,
    audit_events: Sequence[Mapping[str, object]] = (),
    comparison: Mapping[str, object] | None = None,
) -> tuple[WorkspaceProjection, ...]:
    """Build the complete deterministic projection collection for one view."""

    if view is WorkspaceView.DATA_HEALTH:
        values = _data_health(sources)
    elif view is WorkspaceView.IMPORT_RUNS:
        values = _import_runs(sources)
    elif view is WorkspaceView.PLANNING_RUNS:
        values = _planning_runs(sources)
    else:
        if schedule_version is None or bound is None:
            _reject(
                WorkspaceReadFailure.SOURCE_MISSING,
                field="schedule_version",
                message="schedule-scoped view requires an authoritative Version",
            )
        if view is WorkspaceView.ORDERS:
            values = _orders(sources, bound)
        elif view is WorkspaceView.OPERATIONS:
            values = _operations(bound)
        elif view is WorkspaceView.RESOURCES:
            values = _resources(bound)
        elif view is WorkspaceView.CALENDARS:
            values = _calendars(sources, bound)
        elif view is WorkspaceView.GANTT:
            values = _gantt(bound)
        elif view is WorkspaceView.RESOURCE_LOAD:
            values = _resource_load(sources, bound)
        elif view is WorkspaceView.KPI:
            values = _kpi(sources)
        elif view is WorkspaceView.DIAGNOSTICS:
            values = _diagnostics(sources)
        elif view is WorkspaceView.LOCKS:
            values = _locks(schedule_version)
        elif view is WorkspaceView.AUDIT:
            values = _audit(audit_events)
        elif view is WorkspaceView.VERSION_COMPARISON:
            if comparison is None:
                _reject(
                    WorkspaceReadFailure.SOURCE_MISSING,
                    field="comparison",
                    message="comparison view requires a P3 comparison document",
                )
            values = [
                _projection(
                    _text(comparison.get("comparison_id"), "comparison.comparison_id"),
                    "VERSION_COMPARISON",
                    comparison,
                )
            ]
        else:  # pragma: no cover - exhaustive enum guard
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="view",
                message="unsupported workspace view",
            )
    values.sort(key=lambda item: item.item_id)
    return tuple(values)


def parse_workspace_query(document: Mapping[str, object]) -> WorkspaceQuerySpec:
    """Validate the strict request carrier and derive a typed read specification."""

    try:
        require_workspace_document(document)
    except (TypeError, ValueError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.INVALID_QUERY,
            field="query",
            message="workspace query failed its strict carrier precheck",
        ) from error
    if document.get("direction") != "REQUEST" or document.get("result") is not None:
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="direction/result",
            message="query service accepts REQUEST carriers only",
        )
    try:
        view = WorkspaceView(_text(document.get("view"), "view"))
    except ValueError as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.INVALID_QUERY,
            field="view",
            message="unsupported workspace view",
        ) from error
    resource = _mapping(document.get("resource"), "resource")
    resource_type = _text(resource.get("resource_type"), "resource.resource_type")
    resource_id_value = resource.get("resource_id")
    resource_id = resource_id_value if isinstance(resource_id_value, str) else None
    precondition_value = document.get("schedule_version_precondition")
    precondition = (
        _mapping(precondition_value, "schedule_version_precondition")
        if precondition_value is not None
        else None
    )
    if view in _WORKSPACE_VIEWS:
        if (
            resource_type != "WORKSPACE"
            or resource_id is not None
            or precondition is not None
        ):
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="resource",
                message="workspace view requires WORKSPACE/null and no Version precondition",
            )
    elif view in _SCHEDULE_VIEWS:
        if (
            resource_type != "SCHEDULE_VERSION"
            or resource_id is None
            or precondition is None
        ):
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="resource",
                message="schedule view requires exact Version identity and precondition",
            )
        _require_equal(
            precondition.get("schedule_version_id"),
            resource_id,
            "schedule_version_precondition.schedule_version_id",
        )

    sort = tuple(
        _mapping(value, "sort") for value in _sequence(document.get("sort"), "sort")
    )
    if not sort or len(sort) > 4:
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="sort",
            message="requires one to four stable sort terms",
        )
    for term in sort:
        if term.get("field") not in _SORT_FIELDS or term.get("direction") not in {
            "ASC",
            "DESC",
        }:
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="sort",
                message="contains an unsupported field or direction",
            )
    filters = _mapping(document.get("filters"), "filters")
    page = _mapping(document.get("page"), "page")
    size = page.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 500:
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="page.size",
            message="must be between 1 and 500",
        )
    cursor = page.get("cursor")
    if cursor is not None and not isinstance(cursor, str):
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="page.cursor",
            message="must be null or opaque text",
        )
    return WorkspaceQuerySpec(
        view=view,
        query_fingerprint=_text(document.get("query_fingerprint"), "query_fingerprint"),
        data_plane=_text(document.get("data_plane"), "data_plane"),
        environment=_text(document.get("environment"), "environment"),
        resource_type=resource_type,
        resource_id=resource_id,
        schedule_version_precondition=precondition,
        sort=sort,
        filters=filters,
        page_size=size,
        cursor=cursor,
    )


def build_workspace_query_request(
    *,
    view: WorkspaceView,
    data_plane: str,
    environment: str,
    synthetic: bool,
    correlation_id: str,
    schedule_version_reference: Mapping[str, object] | None = None,
    synthetic_provenance: Mapping[str, object] | None = None,
    sort: Sequence[Mapping[str, object]] | None = None,
    filters: Mapping[str, object] | None = None,
    page_size: int = 100,
    cursor: str | None = None,
) -> dict[str, object]:
    """Create a strict REQUEST carrier without hidden business defaults."""

    is_workspace = view in _WORKSPACE_VIEWS
    query_kind = (
        "AUDIT_LOG"
        if view is WorkspaceView.AUDIT
        else "SCHEDULE_VERSION_COMPARISON"
        if view is WorkspaceView.VERSION_COMPARISON
        else "WORKSPACE_VIEW"
    )
    default_sort: Sequence[Mapping[str, object]] = (
        (
            {"field": "OCCURRED_AT_UTC", "direction": "ASC"},
            {"field": "ITEM_ID", "direction": "ASC"},
        )
        if view is WorkspaceView.AUDIT
        else ({"field": "ITEM_ID", "direction": "ASC"},)
    )
    default_filters: Mapping[str, object] = {
        "order_ids": [],
        "operation_ids": [],
        "resource_ids": [],
        "states": [],
        "start_at_or_after_utc": None,
        "start_before_utc": None,
    }
    resource_id = None
    if schedule_version_reference is not None:
        resource_id = schedule_version_reference.get("schedule_version_id")
    document: dict[str, object] = {
        "workspace_query_version": "workspace-query.v1",
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "direction": "REQUEST",
        "query_kind": query_kind,
        "data_plane": data_plane,
        "environment": environment,
        "synthetic": synthetic,
        "resource": {
            "resource_type": "WORKSPACE" if is_workspace else "SCHEDULE_VERSION",
            "resource_id": None if is_workspace else resource_id,
        },
        "view": view.value,
        "schedule_version_precondition": None
        if is_workspace
        else (
            _clone(schedule_version_reference)
            if schedule_version_reference is not None
            else None
        ),
        "sort": [_clone(term) for term in (sort or default_sort)],
        "filters": _clone(filters or default_filters),
        "page": {"size": page_size, "cursor": cursor},
        "query_fingerprint": "sha256:" + "0" * 64,
        "correlation_id": correlation_id,
        "result": None,
    }
    if synthetic_provenance is not None:
        document["synthetic_provenance"] = _clone(synthetic_provenance)
    document["query_fingerprint"] = workspace_query_fingerprint(document)
    parse_workspace_query(document)
    return document


def _filter_values(filters: Mapping[str, object], field: str) -> frozenset[str]:
    values = filters.get(field)
    if not isinstance(values, list) or any(
        not isinstance(value, str) for value in values
    ):
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field=f"filters.{field}",
            message="must be an array of stable identities",
        )
    return frozenset(cast(list[str], values))


def _payload_identity(payload: Mapping[str, object], *fields: str) -> str | None:
    for field in fields:
        value = payload.get(field)
        if isinstance(value, str):
            return value
    return None


def _filtered(
    items: Sequence[WorkspaceProjection],
    spec: WorkspaceQuerySpec,
    *,
    schedule_state: str | None,
) -> list[WorkspaceProjection]:
    order_ids = _filter_values(spec.filters, "order_ids")
    operation_ids = _filter_values(spec.filters, "operation_ids")
    resource_ids = _filter_values(spec.filters, "resource_ids")
    states = _filter_values(spec.filters, "states")
    start_after = spec.filters.get("start_at_or_after_utc")
    start_before = spec.filters.get("start_before_utc")
    for value, field in (
        (start_after, "start_at_or_after_utc"),
        (start_before, "start_before_utc"),
    ):
        if value is not None:
            if not isinstance(value, str) or not value.endswith("Z"):
                _reject(
                    WorkspaceReadFailure.INVALID_QUERY,
                    field=f"filters.{field}",
                    message="must be null or an explicit UTC instant",
                )
            try:
                parse_utc_instant(value)
            except (TypeError, ValueError) as error:
                raise WorkspaceReadError(
                    WorkspaceReadFailure.INVALID_QUERY,
                    field=f"filters.{field}",
                    message="must be a valid UTC instant",
                ) from error
    if (
        start_after is not None
        and start_before is not None
        and cast(str, start_after) >= cast(str, start_before)
    ):
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="filters.start_at_or_after_utc/start_before_utc",
            message="must describe a non-empty half-open range",
        )
    result: list[WorkspaceProjection] = []
    for item in items:
        payload = item.payload
        order_id = _payload_identity(payload, "order_id", "demand_order_id")
        operation_id = _payload_identity(payload, "operation_id")
        resource_id = _payload_identity(payload, "resource_id")
        start = _payload_identity(payload, "start_at_utc", "occurred_at_utc")
        if order_ids and order_id not in order_ids:
            continue
        if operation_ids and operation_id not in operation_ids:
            continue
        if resource_ids and resource_id not in resource_ids:
            continue
        if (
            states
            and schedule_state not in states
            and payload.get("state") not in states
        ):
            continue
        if start_after is not None and (
            start is None or start < cast(str, start_after)
        ):
            continue
        if start_before is not None and (
            start is None or start >= cast(str, start_before)
        ):
            continue
        result.append(item)
    return result


def _sort_value(item: WorkspaceProjection, field: str) -> str:
    payload = item.payload
    values: Mapping[str, str | None] = {
        "ITEM_ID": item.item_id,
        "START_AT_UTC": _payload_identity(payload, "start_at_utc"),
        "END_AT_UTC": _payload_identity(payload, "end_at_utc"),
        "RESOURCE_ID": _payload_identity(payload, "resource_id"),
        "ORDER_ID": _payload_identity(payload, "order_id", "demand_order_id"),
        "OCCURRED_AT_UTC": _payload_identity(payload, "occurred_at_utc"),
    }
    return values[field] or ""


def _sorted(
    items: Sequence[WorkspaceProjection], spec: WorkspaceQuerySpec
) -> list[WorkspaceProjection]:
    values = sorted(items, key=lambda item: item.item_id)
    for term in reversed(spec.sort):
        field = cast(str, term["field"])
        values.sort(
            key=lambda item, sort_field=field: _sort_value(item, sort_field),
            reverse=term["direction"] == "DESC",
        )
    return values


def _encode_cursor(payload: Mapping[str, object]) -> str:
    raw = canonical_workspace_bytes(payload)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> Mapping[str, object]:
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        decoded = json.loads(raw)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.INVALID_QUERY,
            field="page.cursor",
            message="opaque cursor is malformed",
        ) from error
    if not isinstance(decoded, Mapping):
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="page.cursor",
            message="opaque cursor payload is invalid",
        )
    return cast(Mapping[str, object], decoded)


def paginate_workspace_projections(
    items: Sequence[WorkspaceProjection],
    spec: WorkspaceQuerySpec,
    *,
    schedule_state: str | None,
    source_fingerprint: str,
) -> WorkspaceProjectionPage:
    """Apply stable filter/sort/cursor paging and reject mixed-page replay."""

    ordered = _sorted(_filtered(items, spec, schedule_state=schedule_state), spec)
    query_scope_fingerprint = workspace_fingerprint(
        {
            "cursor_scope_version": "workspace-query-cursor-scope.v1",
            "data_plane": spec.data_plane,
            "environment": spec.environment,
            "resource_type": spec.resource_type,
            "resource_id": spec.resource_id,
            "schedule_version_precondition": spec.schedule_version_precondition,
            "view": spec.view.value,
            "sort": list(spec.sort),
            "filters": spec.filters,
            "page_size": spec.page_size,
        }
    )
    collection_fingerprint = workspace_fingerprint(
        {
            "read_model_version": WORKSPACE_READ_MODEL_VERSION,
            "query_scope_fingerprint": query_scope_fingerprint,
            "source_fingerprint": source_fingerprint,
            "items": [item.carrier_reference for item in ordered],
        }
    )
    offset = 0
    if spec.cursor is not None:
        cursor = _decode_cursor(spec.cursor)
        expected = {
            "cursor_version": WORKSPACE_CURSOR_VERSION,
            "query_scope_fingerprint": query_scope_fingerprint,
            "source_fingerprint": source_fingerprint,
            "collection_fingerprint": collection_fingerprint,
            "view": spec.view.value,
        }
        for field, value in expected.items():
            if cursor.get(field) != value:
                _reject(
                    WorkspaceReadFailure.STALE_CURSOR,
                    field="page.cursor",
                    message="cursor no longer binds this query and immutable source",
                )
        offset_value = cursor.get("offset")
        if (
            isinstance(offset_value, bool)
            or not isinstance(offset_value, int)
            or offset_value < 0
        ):
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="page.cursor",
                message="cursor offset is invalid",
            )
        offset = offset_value
    page_items = tuple(ordered[offset : offset + spec.page_size])
    next_offset = offset + len(page_items)
    next_cursor = None
    if next_offset < len(ordered):
        next_cursor = _encode_cursor(
            {
                "cursor_version": WORKSPACE_CURSOR_VERSION,
                "query_scope_fingerprint": query_scope_fingerprint,
                "source_fingerprint": source_fingerprint,
                "collection_fingerprint": collection_fingerprint,
                "view": spec.view.value,
                "offset": next_offset,
            }
        )
    return WorkspaceProjectionPage(
        items=page_items,
        next_cursor=next_cursor,
        observed_count=len(ordered),
        collection_fingerprint=collection_fingerprint,
    )


def version_reference(schedule_version: Mapping[str, object]) -> dict[str, object]:
    return {
        "schedule_version_id": _text(
            schedule_version.get("schedule_version_id"),
            "schedule_version.schedule_version_id",
        ),
        "state": _text(schedule_version.get("state"), "schedule_version.state"),
        "content_fingerprint": _text(
            schedule_version.get("content_fingerprint"),
            "schedule_version.content_fingerprint",
        ),
    }


def require_query_precondition(
    spec: WorkspaceQuerySpec,
    schedule_version: Mapping[str, object],
) -> None:
    precondition = spec.schedule_version_precondition
    if precondition is None:
        return
    reference = version_reference(schedule_version)
    if any(precondition.get(field) != reference[field] for field in reference):
        _reject(
            WorkspaceReadFailure.STALE_VERSION,
            field="schedule_version_precondition",
            message="authoritative Version state or content fingerprint changed",
        )
    if schedule_version.get("environment") != spec.environment:
        _reject(
            WorkspaceReadFailure.DATA_PLANE_MISMATCH,
            field="environment",
            message="query environment differs from the authoritative Version",
        )


def _assignment_delta(
    operation_id: str,
    base: Mapping[str, object] | None,
    compared: Mapping[str, object] | None,
) -> dict[str, object]:
    if base is None:
        kind = "ADDED"
    elif compared is None:
        kind = "REMOVED"
    elif base.get("resource_id") != compared.get("resource_id"):
        kind = "RESOURCE_CHANGE"
    elif base.get("duration_seconds") != compared.get("duration_seconds"):
        kind = "DURATION_CHANGE"
    elif base.get("start_at_utc") != compared.get("start_at_utc"):
        kind = "START_SHIFT"
    else:
        kind = "UNCHANGED"
    return {
        "operation_id": operation_id,
        "change_kind": kind,
        "base_resource_id": base.get("resource_id") if base is not None else None,
        "compared_resource_id": compared.get("resource_id")
        if compared is not None
        else None,
        "base_start_at_utc": base.get("start_at_utc") if base is not None else None,
        "compared_start_at_utc": compared.get("start_at_utc")
        if compared is not None
        else None,
        "base_end_at_utc": base.get("end_at_utc") if base is not None else None,
        "compared_end_at_utc": compared.get("end_at_utc")
        if compared is not None
        else None,
    }


def _seconds_between(left: object, right: object) -> int:
    if not isinstance(left, str) or not isinstance(right, str):
        return 0
    try:
        first = parse_utc_instant(left)
        second = parse_utc_instant(right)
    except (TypeError, ValueError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="comparison.operation.start_at_utc",
            message="assignment instant is invalid",
        ) from error
    return abs(int((second - first).total_seconds()))


def _kpi_metric_values(sources: WorkspaceSourceDocuments) -> Mapping[str, int | float]:
    delivery = _mapping(sources.kpi.get("delivery"), "kpi.delivery")
    planning = _mapping(sources.kpi.get("planning"), "kpi.planning")
    return {
        "WEIGHTED_TARDINESS": _number(
            delivery.get("priority_weighted_tardiness_seconds"),
            "kpi.delivery.priority_weighted_tardiness_seconds",
        ),
        "MAKESPAN_SECONDS": _number(
            planning.get("makespan_seconds"), "kpi.planning.makespan_seconds"
        ),
        "LATE_ORDER_COUNT": _number(
            delivery.get("late_order_count"), "kpi.delivery.late_order_count"
        ),
        "SCHEDULED_OPERATION_COUNT": _number(
            planning.get("scheduled_operation_count"),
            "kpi.planning.scheduled_operation_count",
        ),
    }


def build_schedule_version_comparison(
    *,
    base_version: Mapping[str, object],
    compared_version: Mapping[str, object],
    base_sources: WorkspaceSourceDocuments,
    compared_sources: WorkspaceSourceDocuments,
    query_fingerprint: str,
    generated_at_utc: str,
) -> dict[str, object]:
    """Build a deterministic P3 comparison DTO; never a P4 ChangeReport."""

    if not generated_at_utc.endswith("Z"):
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="generated_at_utc",
            message="must be an explicit UTC instant",
        )
    try:
        parse_utc_instant(generated_at_utc)
    except (TypeError, ValueError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.INVALID_QUERY,
            field="generated_at_utc",
            message="must be a valid UTC instant",
        ) from error
    data_plane = _text(base_version.get("data_plane"), "base_version.data_plane")
    if compared_version.get("data_plane") != data_plane:
        _reject(
            WorkspaceReadFailure.DATA_PLANE_MISMATCH,
            field="compared_version.data_plane",
            message="comparison cannot cross data planes",
        )
    environment = _text(base_version.get("environment"), "base_version.environment")
    if compared_version.get("environment") != environment:
        _reject(
            WorkspaceReadFailure.DATA_PLANE_MISMATCH,
            field="compared_version.environment",
            message="comparison cannot cross environments",
        )
    base_bound = bind_workspace_sources(
        base_version, base_sources, expected_data_plane=data_plane
    )
    compared_bound = bind_workspace_sources(
        compared_version, compared_sources, expected_data_plane=data_plane
    )
    base_id = _text(
        base_version.get("schedule_version_id"), "base_version.schedule_version_id"
    )
    compared_id = _text(
        compared_version.get("schedule_version_id"),
        "compared_version.schedule_version_id",
    )
    if base_id == compared_id:
        _reject(
            WorkspaceReadFailure.INVALID_QUERY,
            field="compared_version.schedule_version_id",
            message="must differ from the base Version",
        )
    base_assignments = _index(
        base_bound.assignments,
        id_field="operation_id",
        field="base_version.content.assignments",
    )
    compared_assignments = _index(
        compared_bound.assignments,
        id_field="operation_id",
        field="compared_version.content.assignments",
    )
    operation_ids = sorted(set(base_assignments) | set(compared_assignments))
    deltas = [
        _assignment_delta(
            operation_id,
            base_assignments.get(operation_id),
            compared_assignments.get(operation_id),
        )
        for operation_id in operation_ids
    ]
    changed = [delta for delta in deltas if delta["change_kind"] != "UNCHANGED"]
    start_shift_seconds = sum(
        _seconds_between(
            base_assignments[operation_id].get("start_at_utc"),
            compared_assignments[operation_id].get("start_at_utc"),
        )
        for operation_id in sorted(set(base_assignments) & set(compared_assignments))
    )
    resource_changed_count = sum(
        1
        for operation_id in set(base_assignments) & set(compared_assignments)
        if base_assignments[operation_id].get("resource_id")
        != compared_assignments[operation_id].get("resource_id")
    )
    base_metrics = _kpi_metric_values(base_sources)
    compared_metrics = _kpi_metric_values(compared_sources)
    kpi_deltas = [
        {
            "metric": metric,
            "base_value": base_metrics[metric],
            "compared_value": compared_metrics[metric],
            "delta": compared_metrics[metric] - base_metrics[metric],
        }
        for metric in (
            "WEIGHTED_TARDINESS",
            "MAKESPAN_SECONDS",
            "LATE_ORDER_COUNT",
            "SCHEDULED_OPERATION_COUNT",
        )
    ]
    kpi_deltas.extend(
        [
            {
                "metric": "START_SHIFT_SECONDS",
                "base_value": 0,
                "compared_value": start_shift_seconds,
                "delta": start_shift_seconds,
            },
            {
                "metric": "RESOURCE_CHANGED_COUNT",
                "base_value": 0,
                "compared_value": resource_changed_count,
                "delta": resource_changed_count,
            },
        ]
    )
    identity_basis = {
        "comparison_version": SCHEDULE_COMPARISON_VERSION,
        "query_fingerprint": query_fingerprint,
        "base_version": version_reference(base_version),
        "compared_version": version_reference(compared_version),
    }
    document: dict[str, object] = {
        "schedule_version_comparison_version": SCHEDULE_COMPARISON_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "comparison_id": _derived_id("comparison", identity_basis),
        "data_plane": data_plane,
        "environment": environment,
        "synthetic": base_version.get("synthetic"),
        "base_version": version_reference(base_version),
        "compared_version": version_reference(compared_version),
        "query_fingerprint": query_fingerprint,
        "operation_deltas": deltas,
        "kpi_deltas": kpi_deltas,
        "summary": {
            "operation_count": len(operation_ids),
            "changed_operation_count": len(changed),
            "added_operation_count": sum(
                delta["change_kind"] == "ADDED" for delta in deltas
            ),
            "removed_operation_count": sum(
                delta["change_kind"] == "REMOVED" for delta in deltas
            ),
            "resource_changed_count": resource_changed_count,
        },
        "comparison_fingerprint": "sha256:" + "0" * 64,
        "generated_at_utc": generated_at_utc,
    }
    if document["synthetic"] is True:
        provenance = base_version.get("synthetic_provenance")
        if not isinstance(provenance, Mapping):
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="base_version.synthetic_provenance",
                message="synthetic Version requires provenance",
            )
        document["synthetic_provenance"] = _clone(
            cast(Mapping[str, object], provenance)
        )
    document["comparison_fingerprint"] = comparison_fingerprint(document)
    try:
        require_workspace_document(document)
    except (TypeError, ValueError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="comparison",
            message="constructed comparison failed its strict P3 carrier",
        ) from error
    return document


def comparison_query_fingerprint(
    *,
    workspace_query_fingerprint_value: str,
    base_schedule_version_id: str,
    compared_schedule_version_id: str,
) -> str:
    """Bind the two explicit Version IDs absent from the generic query carrier."""

    return workspace_fingerprint(
        {
            "comparison_query_version": "schedule-version-comparison-query.v1",
            "workspace_query_fingerprint": workspace_query_fingerprint_value,
            "base_schedule_version_id": base_schedule_version_id,
            "compared_schedule_version_id": compared_schedule_version_id,
        }
    )


__all__ = [
    "BoundWorkspaceSources",
    "SCHEDULE_COMPARISON_VERSION",
    "WORKSPACE_CURSOR_VERSION",
    "WORKSPACE_READ_MODEL_VERSION",
    "WorkspaceProjection",
    "WorkspaceProjectionPage",
    "WorkspaceQuerySpec",
    "WorkspaceReadError",
    "WorkspaceReadFailure",
    "WorkspaceSourceDocuments",
    "WorkspaceView",
    "bind_workspace_sources",
    "build_schedule_version_comparison",
    "build_workspace_projections",
    "build_workspace_query_request",
    "comparison_query_fingerprint",
    "paginate_workspace_projections",
    "parse_workspace_query",
    "require_query_precondition",
    "require_workspace_sources",
    "version_reference",
]
