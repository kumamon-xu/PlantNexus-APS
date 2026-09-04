"""Strict, read-only presentation projections for the CNC Demo.

The models in this module are deliberately not planning contracts.  They are
immutable, SIMULATION-only views assembled from already committed formal
artifacts.  No method invokes a solver or changes run, schedule, publication,
or replanning state.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, NoReturn, cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.change_report_queries import (
    ChangeReportQuery,
    ChangeReportQueryService,
    ChangeReportReadContext,
)
from app.domain.execution_contracts import contract_fingerprint, require_p4_document
from app.domain.workspace_contracts import (
    require_workspace_document,
)
from app.infrastructure.replan_repository import SqlAlchemyReplanLineageRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.planning.contracts import validate_planning_solution, validate_solver_report
from app.planning.problem.hashing import validate_built_problem_v2
from app.snapshots import SnapshotDataPlane

from .assets import DemoAssets, load_demo_assets
from .orchestration import DemoOperationError
from .persistence import ControlStore, DemoRuntimePaths, RunDatabase, fingerprint
from .security import DEMO_ACTOR_REF


Identifier = Annotated[str, Field(min_length=1, max_length=256)]
Fingerprint = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
UtcInstant = Annotated[str, Field(pattern=r"Z$")]
LocalInstant = Annotated[str, Field(min_length=20, max_length=40)]


class StrictView(BaseModel):
    """Shared strict/frozen contract behavior for every emitted object."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TimePair(StrictView):
    utc: UtcInstant
    local: LocalInstant


class ArtifactReferenceView(StrictView):
    document_version: Identifier
    artifact_id: Identifier
    fingerprint: Fingerprint


class PresentationBoundary(StrictView):
    data_plane: Literal["SIMULATION"]
    environment: Literal["DEVELOPMENT", "TEST", "BENCHMARK"]
    simulation_only: Literal[True]
    production_authority: Literal[False]
    publishable: Literal[False]


class PageInfo(StrictView):
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    returned: int = Field(ge=0)
    filtered_total: int = Field(ge=0)
    unfiltered_total: int = Field(ge=0)
    has_more: bool


class UnavailableIntervalView(StrictView):
    interval_id: Identifier
    kind: Literal["SHIFT", "MAINTENANCE"]
    reason: str = Field(min_length=1, max_length=256)
    start: TimePair
    end: TimePair


class FactoryResourceView(StrictView):
    resource_id: Identifier
    source_resource_id: Identifier
    resource_code: Identifier
    resource_name: str = Field(min_length=1, max_length=128)
    family: Identifier
    status: Literal["ACTIVE"]
    capabilities: tuple[Identifier, ...]
    calendar_id: Identifier
    unavailable_intervals: tuple[UnavailableIntervalView, ...]


class FactoryResourceGroupView(StrictView):
    resource_group_id: Identifier
    source_resource_group_id: Identifier
    resource_group_code: Identifier
    resources: tuple[FactoryResourceView, ...]


class FactoryProductionLineView(StrictView):
    production_line_id: Identifier
    source_production_line_id: Identifier
    production_line_code: Identifier
    resource_groups: tuple[FactoryResourceGroupView, ...]


class FactoryWorkshopView(StrictView):
    workshop_id: Identifier
    source_workshop_id: Identifier
    workshop_code: Identifier
    workshop_name: str = Field(min_length=1, max_length=128)
    production_line: FactoryProductionLineView


class FactoryNodeView(StrictView):
    factory_id: Identifier
    source_factory_id: Identifier
    factory_code: Identifier
    factory_name: str = Field(min_length=1, max_length=128)
    timezone: Identifier
    workshops: tuple[FactoryWorkshopView, ...]


class MaintenanceEventView(StrictView):
    event_id: Identifier
    resource_id: Identifier
    source_resource_id: Identifier
    resource_code: Identifier
    reason: str = Field(min_length=1, max_length=256)
    start: TimePair
    end: TimePair


class FactoryCounts(StrictView):
    workshops: int = Field(ge=1)
    production_lines: int = Field(ge=1)
    resource_groups: int = Field(ge=1)
    resources: int = Field(ge=1)
    maintenance_events: int = Field(ge=0)
    unavailable_intervals: int = Field(ge=0)


class FactoryProvenance(StrictView):
    asset_pack_version: Identifier
    asset_pack_fingerprint: Fingerprint
    snapshot: ArtifactReferenceView


class DemoFactoryView(StrictView):
    view_version: Literal["cnc-demo-factory-view.v1"]
    run_id: Identifier
    scenario_id: Identifier
    profile_name: Literal["smoke", "showcase", "upper"]
    seed: int = Field(ge=0)
    horizon_start: TimePair
    horizon_end: TimePair
    factory: FactoryNodeView
    maintenance_events: tuple[MaintenanceEventView, ...]
    counts: FactoryCounts
    provenance: FactoryProvenance
    boundary: PresentationBoundary
    view_fingerprint: Fingerprint


ScheduleSort = Literal["START_ASC", "RESOURCE_START_ASC", "ORDER_START_ASC"]


class SchedulePresentationQuery(StrictView):
    resource_ids: tuple[Identifier, ...] = ()
    workshop_ids: tuple[Identifier, ...] = ()
    demand_order_ids: tuple[Identifier, ...] = ()
    states: tuple[Literal["NOT_STARTED", "RUNNING"], ...] = ()
    start_at_utc: UtcInstant | None = None
    end_at_utc: UtcInstant | None = None
    sort: ScheduleSort = "START_ASC"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=200, ge=1, le=500)

    @model_validator(mode="after")
    def validate_query(self) -> SchedulePresentationQuery:
        for field_name in (
            "resource_ids",
            "workshop_ids",
            "demand_order_ids",
            "states",
        ):
            values = cast(tuple[str, ...], getattr(self, field_name))
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        _validate_window(self.start_at_utc, self.end_at_utc)
        return self


class ScheduleVersionSummary(StrictView):
    schedule_version_id: Identifier
    contract_version: Literal["schedule-version.v1", "schedule-version.v2"]
    revision: int = Field(ge=1)
    state: Literal[
        "DRAFT",
        "READY_FOR_REVIEW",
        "APPROVED",
        "PUBLISHED",
        "SUPERSEDED",
        "REJECTED",
    ]
    source_kind: Identifier
    parent_schedule_version_id: Identifier | None
    content_fingerprint: Fingerprint
    created_at: TimePair


class SolverSummary(StrictView):
    solver_report_version: Literal["solver-report.v1", "solver-report.v2"]
    report_id: Identifier
    solver_status: Literal["OPTIMAL", "FEASIBLE"]
    evidence_kind: Literal["SOLVER_RUN"]
    limit_seconds: float = Field(gt=0)
    objective_value: int | float | None
    best_bound: int | float | None
    relative_gap: float | None = Field(default=None, ge=0)
    solve_seconds: float = Field(ge=0)
    total_seconds: float = Field(ge=0)
    optimality_claim: bool


class ValidationSummary(StrictView):
    validation_report_version: Literal["validation-report.v2"]
    status: Literal["PASS"]
    hard_violation_count: Literal[0]
    fingerprint: Fingerprint


class DeliverySummary(StrictView):
    order_count: int = Field(ge=0)
    on_time_order_count: int = Field(ge=0)
    on_time_order_ratio: float | None = Field(default=None, ge=0, le=1)
    late_order_count: int = Field(ge=0)
    total_tardiness_seconds: int = Field(ge=0)
    priority_weighted_tardiness_seconds: int = Field(ge=0)


class PlanningSummary(StrictView):
    makespan_seconds: int = Field(ge=0)
    scheduled_operation_count: int = Field(ge=0)
    unscheduled_operation_count: int = Field(ge=0)


class KpiStabilitySummary(StrictView):
    status: Identifier
    changed_operation_count: int | None = Field(default=None, ge=0)
    resource_changed_count: int | None = Field(default=None, ge=0)
    start_shift_seconds: int | None = Field(default=None, ge=0)
    schedule_stability_ratio: float | None = Field(default=None, ge=0, le=1)


class KpiSummary(StrictView):
    kpi_id: Identifier
    kpi_version: Literal["kpi.v2"]
    fingerprint: Fingerprint
    delivery: DeliverySummary
    planning: PlanningSummary
    stability: KpiStabilitySummary


class OrderView(StrictView):
    demand_order_id: Identifier
    order_code: Identifier
    product_code: Identifier
    quantity: int | float = Field(gt=0)
    quantity_unit: Identifier
    priority_class: Literal["NORMAL", "KEY", "URGENT"]
    priority_weight: int = Field(ge=1)
    release_at: TimePair
    material_ready_at: TimePair
    due_at: TimePair
    completion_at: TimePair
    tardiness_seconds: int = Field(ge=0)
    on_time: bool
    operation_count: int = Field(ge=1)
    scheduled_operation_count: int = Field(ge=0)
    completed_operation_count: int = Field(ge=0)
    running_operation_count: int = Field(ge=0)


class ScheduleAssignmentView(StrictView):
    operation_id: Identifier
    operation_code: Identifier
    operation_name: str = Field(min_length=1, max_length=128)
    operation_sequence: int = Field(ge=1)
    demand_order_id: Identifier
    order_code: Identifier
    product_code: Identifier
    resource_id: Identifier
    source_resource_id: Identifier
    resource_code: Identifier
    resource_name: str = Field(min_length=1, max_length=128)
    workshop_id: Identifier
    source_workshop_id: Identifier
    workshop_code: Identifier
    workshop_name: str = Field(min_length=1, max_length=128)
    start: TimePair
    end: TimePair
    duration_seconds: int = Field(ge=1)
    operation_state: Literal["NOT_STARTED", "RUNNING"]
    candidate_resource_count: int = Field(ge=1, le=3)
    lock_ids: tuple[Identifier, ...]
    execution_fact_ids: tuple[Identifier, ...]
    protection: Literal["FREE", "RUNNING", "HARD_LOCK", "SOFT_LOCK"]


class ExecutionSegmentView(StrictView):
    execution_fact_id: Identifier
    operation_id: Identifier
    demand_order_id: Identifier
    resource_id: Identifier
    resource_code: Identifier
    status: Literal["COMPLETED", "RUNNING"]
    actual_start: TimePair
    actual_end: TimePair | None
    remaining_seconds: int | None = Field(default=None, ge=0)


class ResourceLoadView(StrictView):
    resource_id: Identifier
    source_resource_id: Identifier
    resource_code: Identifier
    resource_name: str = Field(min_length=1, max_length=128)
    workshop_id: Identifier
    workshop_code: Identifier
    available_seconds: int = Field(ge=0)
    planned_busy_seconds: int = Field(ge=0)
    utilization: float | None = Field(default=None, ge=0, le=1)
    formula: Literal["planned_busy_seconds / available_seconds"]
    evidence: ArtifactReferenceView


class ScheduleProvenance(StrictView):
    planning_run_id: Identifier
    schedule_content_fingerprint: Fingerprint
    artifacts: tuple[ArtifactReferenceView, ...]


class DemoScheduleView(StrictView):
    view_version: Literal["cnc-demo-schedule-view.v1"]
    run_id: Identifier
    scenario_id: Identifier
    timezone: Identifier
    version: ScheduleVersionSummary
    solver: SolverSummary
    validation: ValidationSummary
    kpis: KpiSummary
    orders: tuple[OrderView, ...]
    resources: tuple[ResourceLoadView, ...]
    execution_segments: tuple[ExecutionSegmentView, ...]
    assignments: tuple[ScheduleAssignmentView, ...]
    query: SchedulePresentationQuery
    page: PageInfo
    provenance: ScheduleProvenance
    boundary: PresentationBoundary
    view_fingerprint: Fingerprint


ComparisonSort = Literal["OPERATION_ASC", "SHIFT_DESC", "START_ASC"]
ChangeClass = Literal["UNCHANGED", "CHANGED", "ADDED", "REMOVED_BY_FACT"]


class ComparisonPresentationQuery(StrictView):
    classifications: tuple[ChangeClass, ...] = ("ADDED", "CHANGED")
    resource_ids: tuple[Identifier, ...] = ()
    workshop_ids: tuple[Identifier, ...] = ()
    demand_order_ids: tuple[Identifier, ...] = ()
    start_at_utc: UtcInstant | None = None
    end_at_utc: UtcInstant | None = None
    sort: ComparisonSort = "OPERATION_ASC"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=200, ge=1, le=500)

    @model_validator(mode="after")
    def validate_query(self) -> ComparisonPresentationQuery:
        for field_name in (
            "classifications",
            "resource_ids",
            "workshop_ids",
            "demand_order_ids",
        ):
            values = cast(tuple[str, ...], getattr(self, field_name))
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        _validate_window(self.start_at_utc, self.end_at_utc)
        return self


class ComparisonAssignmentView(StrictView):
    resource_id: Identifier
    source_resource_id: Identifier
    resource_code: Identifier
    workshop_id: Identifier
    workshop_code: Identifier
    start: TimePair
    end: TimePair
    duration_seconds: int = Field(ge=1)


class OperationDeltasView(StrictView):
    resource_changed: bool
    start_shift_seconds: int
    absolute_start_shift_seconds: int = Field(ge=0)
    end_shift_seconds: int
    duration_delta_seconds: int


class ChangeOperationView(StrictView):
    operation_id: Identifier
    operation_code: Identifier
    operation_name: str = Field(min_length=1, max_length=128)
    demand_order_id: Identifier
    order_code: Identifier
    classification: ChangeClass
    base_assignment: ComparisonAssignmentView | None
    new_assignment: ComparisonAssignmentView | None
    deltas: OperationDeltasView
    reason_codes: tuple[Identifier, ...]


class ChangeCounts(StrictView):
    unchanged: int = Field(ge=0)
    changed: int = Field(ge=0)
    added: int = Field(ge=0)
    removed_by_fact: int = Field(ge=0)


class StabilitySummary(StrictView):
    soft_lock_violations: int = Field(ge=0)
    changed_existing_operations: int = Field(ge=0)
    resource_changes: int = Field(ge=0)
    absolute_start_shift_seconds: int = Field(ge=0)
    unchanged_existing: int = Field(ge=0)
    comparable_existing: int = Field(ge=0)
    unchanged_ratio: float | None = Field(default=None, ge=0, le=1)


class DeliveryDelta(StrictView):
    order_count: int
    on_time_order_count: int
    on_time_order_ratio: float | None
    late_order_count: int
    total_tardiness_seconds: int
    priority_weighted_tardiness_seconds: int
    makespan_seconds: int
    formula: Literal["after - before"]


class AffectedOrderView(StrictView):
    demand_order_id: Identifier
    order_code: Identifier
    change_count: int = Field(ge=1)


class ComparisonProvenance(StrictView):
    attempt_id: Identifier
    result_id: Identifier
    result_fingerprint: Fingerprint
    change_report: ArtifactReferenceView
    before_kpi: ArtifactReferenceView
    after_kpi: ArtifactReferenceView
    validation_status: Literal["PASS"]


class DemoComparisonView(StrictView):
    view_version: Literal["cnc-demo-comparison-view.v1"]
    run_id: Identifier
    scenario_id: Identifier
    request_id: Identifier
    timezone: Identifier
    before: ScheduleVersionSummary
    after: ScheduleVersionSummary
    before_kpis: KpiSummary
    after_kpis: KpiSummary
    delivery_delta: DeliveryDelta
    operation_universe_count: int = Field(ge=0)
    change_counts: ChangeCounts
    stability: StabilitySummary
    affected_orders: tuple[AffectedOrderView, ...]
    operations: tuple[ChangeOperationView, ...]
    query: ComparisonPresentationQuery
    page: PageInfo
    provenance: ComparisonProvenance
    boundary: PresentationBoundary
    view_fingerprint: Fingerprint


@dataclass(frozen=True, slots=True)
class _SchedulePackage:
    schedule: dict[str, object]
    snapshot: dict[str, object]
    problem: dict[str, object]
    solver: dict[str, object]
    validation: dict[str, object]
    kpi: dict[str, object]
    references: tuple[dict[str, object], ...]
    change_report: dict[str, object] | None = None
    replan_result: dict[str, object] | None = None
    attempt_id: str | None = None


def _reject(code: str, field: str) -> NoReturn:
    raise DemoOperationError(
        code,
        field=field,
        message="Demo presentation evidence is unavailable or inconsistent",
    )


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    return cast(Sequence[object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    return float(value)


def _parse_utc(value: str, field: str = "instant") -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    if parsed.tzinfo is None or parsed.utcoffset() is None or not value.endswith("Z"):
        _reject("PRESENTATION_CONTRACT_REJECTED", field)
    return parsed.astimezone(UTC)


def _validate_window(start: str | None, end: str | None) -> None:
    def parse(value: str | None, field: str) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field} must be a UTC instant") from error
        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
            or not value.endswith("Z")
        ):
            raise ValueError(f"{field} must be a UTC instant")
        return parsed.astimezone(UTC)

    start_value = parse(start, "start_at_utc")
    end_value = parse(end, "end_at_utc")
    if start_value is not None and end_value is not None and start_value >= end_value:
        raise ValueError("start_at_utc must precede end_at_utc")


def _to_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _time_pair(value: str, timezone: ZoneInfo) -> TimePair:
    parsed = _parse_utc(value)
    return TimePair(
        utc=_to_utc(parsed),
        local=parsed.astimezone(timezone).replace(microsecond=0).isoformat(),
    )


def _boundary(environment: str) -> PresentationBoundary:
    if environment not in {"DEVELOPMENT", "TEST", "BENCHMARK"}:
        _reject("PRESENTATION_CONTRACT_REJECTED", "environment")
    return PresentationBoundary(
        data_plane="SIMULATION",
        environment=cast(Literal["DEVELOPMENT", "TEST", "BENCHMARK"], environment),
        simulation_only=True,
        production_authority=False,
        publishable=False,
    )


def _finalize(model: type[BaseModel], document: dict[str, object]) -> BaseModel:
    try:
        provisional = model.model_validate(
            document | {"view_fingerprint": "sha256:" + "0" * 64}
        )
        canonical = provisional.model_dump(
            mode="json", exclude={"view_fingerprint"}
        )
        return provisional.model_copy(
            update={"view_fingerprint": fingerprint(canonical)}
        )
    except Exception:
        _reject("PRESENTATION_CONTRACT_REJECTED", "presentation")


def _source_id(document: Mapping[str, object], field: str) -> str:
    return _text(_mapping(document.get("source"), field).get("source_record_id"), field)


def _record_sequence(
    snapshot: Mapping[str, object], collection: str
) -> tuple[Mapping[str, object], ...]:
    records = _mapping(snapshot.get("records"), "snapshot.records")
    return tuple(
        _mapping(item, f"snapshot.records.{collection}")
        for item in _sequence(records.get(collection), f"snapshot.records.{collection}")
    )


def _artifact_reference(value: object, field: str) -> dict[str, object]:
    reference = _mapping(value, field)
    result: dict[str, object] = {
        "document_version": _text(reference.get("document_version"), field),
        "artifact_id": _text(reference.get("artifact_id"), field),
        "fingerprint": _text(reference.get("fingerprint"), field),
    }
    try:
        ArtifactReferenceView.model_validate(result)
    except Exception:
        _reject("PRESENTATION_LINEAGE_MISMATCH", field)
    return result


def _reference_view(reference: Mapping[str, object]) -> ArtifactReferenceView:
    return ArtifactReferenceView.model_validate(dict(reference))


def _semantic_document(document: Mapping[str, object]) -> Mapping[str, object]:
    formal = document.get("formal_validation")
    return _mapping(formal, "validation.formal_validation") if formal is not None else document


def _semantic_version(document: Mapping[str, object]) -> str | None:
    candidate = _semantic_document(document)
    for field in (
        "snapshot_version",
        "problem_version",
        "planning_solution_version",
        "solver_report_version",
        "validation_report_version",
        "kpi_version",
        "change_report_version",
        "replan_request_version",
    ):
        value = candidate.get(field)
        if isinstance(value, str):
            return value
    return None


def _semantic_fingerprint(document: Mapping[str, object]) -> str:
    candidate = _semantic_document(document)
    version = _semantic_version(document)
    fingerprint_fields = {
        "planning-snapshot.v2": "snapshot_hash",
        "planning-problem.v2": "problem_hash",
        "solver-report.v2": "report_fingerprint",
        "change-report.v1": "report_fingerprint",
        "replan-request.v1": "request_fingerprint",
        "replan-candidate.v1": "candidate_fingerprint",
    }
    fingerprint_field = (
        None if version is None else fingerprint_fields.get(version)
    )
    if fingerprint_field is not None:
        value = candidate.get(fingerprint_field)
        if isinstance(value, str) and value.startswith("sha256:"):
            return value
        _reject("PRESENTATION_CONTRACT_REJECTED", fingerprint_field)
    return contract_fingerprint(candidate)


def _expected_embedded_id(
    kind: str, document: Mapping[str, object], semantic_fingerprint: str
) -> str | None:
    fields = {
        "SNAPSHOT": "snapshot_id",
        "PLANNING_SOLUTION": "solution_id",
        "SOLVER_REPORT": "report_id",
        "KPI": "kpi_id",
        "CHANGE_REPORT": "report_id",
        "REPLAN_REQUEST": "request_id",
    }
    field = fields.get(kind)
    if field is not None:
        value = document.get(field)
        return value if isinstance(value, str) else None
    if kind == "PLANNING_PROBLEM":
        # P3 names this v2 document ``planning-problem-<digest>`` while P4
        # names it ``planning-problem-v2-<digest>``.  The reference check below
        # accepts either exact, fingerprint-derived identity.
        return None
    if kind == "VALIDATION_REPORT":
        return "validation-report-" + semantic_fingerprint.removeprefix("sha256:")
    return None


def _resolve_artifact(
    database: RunDatabase,
    *,
    kind: str,
    reference: Mapping[str, object],
) -> dict[str, object]:
    artifact_id = _text(reference.get("artifact_id"), "artifact.artifact_id")
    expected_version = _text(
        reference.get("document_version"), "artifact.document_version"
    )
    expected_fingerprint = _text(
        reference.get("fingerprint"), "artifact.fingerprint"
    )

    def matches(document: Mapping[str, object]) -> bool:
        semantic_fingerprint = _semantic_fingerprint(document)
        embedded_id = _expected_embedded_id(kind, document, semantic_fingerprint)
        problem_ids = {
            "planning-problem-" + semantic_fingerprint.removeprefix("sha256:"),
            "planning-problem-v2-" + semantic_fingerprint.removeprefix("sha256:"),
        }
        return (
            _semantic_version(document) == expected_version
            and semantic_fingerprint == expected_fingerprint
            and (embedded_id is None or embedded_id == artifact_id)
            and (kind != "PLANNING_PROBLEM" or artifact_id in problem_ids)
        )

    direct = database.get_artifact(artifact_kind=kind, artifact_id=artifact_id)
    if direct is not None:
        if not matches(direct):
            _reject("PRESENTATION_LINEAGE_MISMATCH", f"artifact.{kind}")
        return direct

    # TASK-DEMO-01/02 runtimes used storage fallback IDs for initial Problem
    # and Validation artifacts.  The immutable document fingerprint is still
    # authoritative, so resolve exactly one legacy copy; ambiguity fails.
    legacy_matches: list[dict[str, object]] = []
    for metadata in database.list_artifacts():
        if metadata.get("artifact_kind") != kind:
            continue
        candidate_id = metadata.get("artifact_id")
        if not isinstance(candidate_id, str):
            continue
        candidate = database.get_artifact(
            artifact_kind=kind, artifact_id=candidate_id
        )
        if candidate is not None and matches(candidate):
            legacy_matches.append(candidate)
    if len(legacy_matches) != 1:
        _reject("PRESENTATION_LINEAGE_MISMATCH", f"artifact.{kind}")
    return legacy_matches[0]


def _snapshot_reference(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {
        "document_version": _text(snapshot.get("snapshot_version"), "snapshot"),
        "artifact_id": _text(snapshot.get("snapshot_id"), "snapshot"),
        "fingerprint": _text(snapshot.get("snapshot_hash"), "snapshot"),
    }


def _overlaps(
    start: str,
    end: str,
    *,
    window_start: str | None,
    window_end: str | None,
) -> bool:
    start_value = _parse_utc(start)
    end_value = _parse_utc(end)
    return (
        window_start is None or end_value > _parse_utc(window_start)
    ) and (window_end is None or start_value < _parse_utc(window_end))


class _PresentationContext:
    """Validated lookup indexes over one immutable Snapshot and asset pack."""

    def __init__(self, snapshot: Mapping[str, object], assets: DemoAssets) -> None:
        self.snapshot = snapshot
        self.assets = assets
        timezone_name = _text(
            _record_sequence(snapshot, "factories")[0].get("factory_timezone"),
            "factory_timezone",
        )
        if timezone_name != assets.manifest["factory_timezone"]:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "factory.timezone")
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)
        self.factories = self._index("factories", "factory_id")
        self.workshops = self._index("workshops", "workshop_id")
        self.lines = self._index("production_lines", "production_line_id")
        self.groups = self._index("resource_groups", "resource_group_id")
        self.resources = self._index("resources", "resource_id")
        self.calendars = self._index("calendars", "calendar_id")
        self.demands = self._index("demand_orders", "demand_order_id")
        self.products = self._index("products", "product_id")
        self.routing_operations = self._index(
            "routing_operations", "routing_operation_id"
        )
        self.operation_instances = {
            _text(item.get("operation_instance_id"), "operation_instance_id"): item
            for item in (
                _mapping(value, "snapshot.operation_instances")
                for value in _sequence(
                    snapshot.get("operation_instances"),
                    "snapshot.operation_instances",
                )
            )
        }
        self.source_resources = {
            _source_id(item, "resource.source"): item
            for item in self.resources.values()
        }
        self.asset_resources = {
            _text(cast(Mapping[str, object], item).get("resource_id"), "asset.resource"):
            cast(Mapping[str, object], item)
            for item in cast(Sequence[object], assets.resource_catalog["resources"])
        }
        self.asset_workshops = {
            _text(cast(Mapping[str, object], item).get("workshop_id"), "asset.workshop"):
            cast(Mapping[str, object], item)
            for item in cast(Sequence[object], assets.factory["workshops"])
        }
        self.operation_names = self._operation_names()

    def _index(
        self, collection: str, identity_field: str
    ) -> dict[str, Mapping[str, object]]:
        indexed: dict[str, Mapping[str, object]] = {}
        for item in _record_sequence(self.snapshot, collection):
            identity = _text(item.get(identity_field), f"{collection}.{identity_field}")
            if identity in indexed:
                _reject("PRESENTATION_CONTRACT_REJECTED", collection)
            indexed[identity] = item
        return indexed

    def _operation_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for template_value in cast(
            Sequence[object], self.assets.route_templates["templates"]
        ):
            template = cast(Mapping[str, object], template_value)
            for step_value in cast(Sequence[object], template["steps"]):
                step = cast(Mapping[str, object], step_value)
                code = _text(step.get("operation_code"), "route.operation_code")
                name = _text(step.get("operation_name_zh"), "route.operation_name")
                names.setdefault(code, name)
        return names

    def resource_path(
        self, resource_id: str
    ) -> tuple[
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
    ]:
        resource = self.resources.get(resource_id)
        if resource is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "resource_id")
        group = self.groups.get(_text(resource.get("resource_group_id"), "resource"))
        if group is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "resource_group_id")
        line = self.lines.get(_text(group.get("production_line_id"), "resource_group"))
        if line is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "production_line_id")
        workshop = self.workshops.get(_text(line.get("workshop_id"), "line"))
        if workshop is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "workshop_id")
        return resource, group, line, workshop

    def resource_labels(self, resource_id: str) -> dict[str, str]:
        resource, _, _, workshop = self.resource_path(resource_id)
        source_resource_id = _source_id(resource, "resource.source")
        asset_resource = self.asset_resources.get(source_resource_id)
        source_workshop_id = _source_id(workshop, "workshop.source")
        asset_workshop = self.asset_workshops.get(source_workshop_id)
        if asset_resource is None or asset_workshop is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "factory.assets")
        return {
            "resource_id": resource_id,
            "source_resource_id": source_resource_id,
            "resource_code": _text(resource.get("resource_code"), "resource_code"),
            "resource_name": _text(
                asset_resource.get("resource_name_zh"), "resource_name_zh"
            ),
            "workshop_id": _text(workshop.get("workshop_id"), "workshop_id"),
            "source_workshop_id": source_workshop_id,
            "workshop_code": _text(workshop.get("workshop_code"), "workshop_code"),
            "workshop_name": _text(
                asset_workshop.get("workshop_name_zh"), "workshop_name_zh"
            ),
        }

    def operation_labels(self, operation_id: str) -> dict[str, object]:
        operation = self.operation_instances.get(operation_id)
        if operation is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "operation_id")
        routing_id = _text(
            operation.get("routing_operation_id"), "routing_operation_id"
        )
        routing = self.routing_operations.get(routing_id)
        if routing is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "routing_operation_id")
        demand_id = _text(operation.get("demand_order_id"), "demand_order_id")
        demand = self.demands.get(demand_id)
        if demand is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "demand_order_id")
        product = self.products.get(_text(demand.get("product_id"), "product_id"))
        if product is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "product_id")
        operation_code = _text(routing.get("operation_code"), "operation_code")
        code_key = operation_code.rsplit("-", 1)[0]
        source_operation_id = _source_id(routing, "routing_operation.source")
        try:
            sequence = int(source_operation_id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            _reject("PRESENTATION_CONTRACT_REJECTED", "operation_sequence")
        return {
            "operation": operation,
            "operation_code": operation_code,
            "operation_name": self.operation_names.get(code_key, code_key),
            "operation_sequence": sequence,
            "demand_order_id": demand_id,
            "order_code": _source_id(demand, "demand.source"),
            "product_code": _text(product.get("product_code"), "product_code"),
        }


class DemoPresentationService:
    """Build strict immutable views from the active Demo run."""

    def __init__(
        self,
        *,
        repository_root: Path,
        paths: DemoRuntimePaths,
        control: ControlStore,
        assets: DemoAssets | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.paths = paths
        self.control = control
        self.assets = load_demo_assets() if assets is None else assets

    def _database(self) -> tuple[str, RunDatabase, dict[str, object]]:
        active = self.control.active_run()
        if active is None:
            _reject("DEMO_NOT_INITIALIZED", "active_run")
        database = RunDatabase(
            repository_root=self.repository_root,
            database_path=self.paths.resolve_relative_database(
                active.database_relative_path
            ),
        )
        try:
            manifest = database.get_manifest()
            if manifest is None:
                _reject("DEMO_NOT_INITIALIZED", "scenario_manifest")
            if manifest.get("run_id") != active.run_id:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "scenario_manifest.run_id")
            return active.run_id, database, manifest
        except BaseException:
            database.close()
            raise

    def _snapshot(
        self, database: RunDatabase, reference: Mapping[str, object]
    ) -> dict[str, object]:
        snapshot_id = _text(reference.get("artifact_id"), "snapshot.artifact_id")
        stored = SqlAlchemySnapshotRepository(
            database.engine, data_plane=SnapshotDataPlane.SIMULATION
        ).get_by_id(snapshot_id)
        if stored is None:
            _reject("PRESENTATION_NOT_FOUND", "snapshot")
        document = cast(dict[str, object], stored.document)
        if (
            document.get("snapshot_version") != reference.get("document_version")
            or document.get("snapshot_hash") != reference.get("fingerprint")
        ):
            _reject("PRESENTATION_LINEAGE_MISMATCH", "snapshot")
        artifact = _resolve_artifact(database, kind="SNAPSHOT", reference=reference)
        if artifact != document:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "snapshot.artifact")
        return document

    def _initial_package(
        self,
        database: RunDatabase,
        schedule: dict[str, object],
    ) -> _SchedulePackage:
        try:
            if require_workspace_document(schedule) != "schedule-version.v1":
                _reject("PRESENTATION_CONTRACT_REJECTED", "schedule_version")
        except DemoOperationError:
            raise
        except Exception:
            _reject("PRESENTATION_CONTRACT_REJECTED", "schedule_version")
        lineage = _mapping(schedule.get("lineage"), "schedule.lineage")
        references = tuple(
            _artifact_reference(lineage.get(field), f"schedule.lineage.{field}")
            for field in (
                "snapshot",
                "problem",
                "planning_solution",
                "validation_report",
                "kpi",
                "solver_report",
            )
        )
        by_version = {
            cast(str, reference["document_version"]): reference
            for reference in references
        }
        snapshot = self._snapshot(database, by_version["planning-snapshot.v2"])
        problem = _resolve_artifact(
            database,
            kind="PLANNING_PROBLEM",
            reference=by_version["planning-problem.v2"],
        )
        solution = _resolve_artifact(
            database,
            kind="PLANNING_SOLUTION",
            reference=by_version["planning-solution.v1"],
        )
        validation = _resolve_artifact(
            database,
            kind="VALIDATION_REPORT",
            reference=by_version["validation-report.v2"],
        )
        kpi = _resolve_artifact(
            database, kind="KPI", reference=by_version["kpi.v2"]
        )
        solver = _resolve_artifact(
            database,
            kind="SOLVER_REPORT",
            reference=by_version["solver-report.v1"],
        )
        try:
            validate_built_problem_v2(cast(Any, problem))
            validate_planning_solution(solution)
            validate_solver_report(solver)
        except Exception:
            _reject("PRESENTATION_CONTRACT_REJECTED", "initial_artifacts")
        solution_problem = _mapping(solution.get("problem"), "solution.problem")
        if (
            problem.get("snapshot_id") != snapshot.get("snapshot_id")
            or solution_problem.get("problem_hash") != problem.get("problem_hash")
            or solution_problem.get("snapshot_id") != snapshot.get("snapshot_id")
        ):
            _reject("PRESENTATION_LINEAGE_MISMATCH", "problem/solution")
        self._validate_kpi(
            schedule=schedule,
            snapshot=snapshot,
            problem=problem,
            solver=solver,
            validation=validation,
            kpi=kpi,
        )
        return _SchedulePackage(
            schedule=schedule,
            snapshot=snapshot,
            problem=problem,
            solver=solver,
            validation=validation,
            kpi=kpi,
            references=references,
        )

    def _dynamic_package(
        self,
        database: RunDatabase,
        schedule: dict[str, object],
    ) -> _SchedulePackage:
        try:
            if require_p4_document(schedule) != "schedule-version.v2":
                _reject("PRESENTATION_CONTRACT_REJECTED", "schedule_version")
        except DemoOperationError:
            raise
        except Exception:
            _reject("PRESENTATION_CONTRACT_REJECTED", "schedule_version")
        version_id = _text(schedule.get("schedule_version_id"), "schedule_version_id")
        with database.engine.connect() as connection:
            rows = connection.exec_driver_sql(
                """
                SELECT attempt_id FROM replan_results
                WHERE data_plane = 'SIMULATION'
                  AND new_schedule_version_id = ?
                ORDER BY attempt_id
                """,
                (version_id,),
            ).all()
        if len(rows) != 1:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "replan_result")
        attempt_id = _text(rows[0][0], "attempt_id")
        lineage_repository = SqlAlchemyReplanLineageRepository(
            database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        )
        stored = lineage_repository.get_applied_result_for_attempt(attempt_id)
        if stored is None:
            _reject("PRESENTATION_NOT_FOUND", "replan_result")
        result = stored.result
        change_report = stored.change_report
        query_service = ChangeReportQueryService(
            lineage_repository=lineage_repository,
            schedule_repository=SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            ),
        )
        try:
            validated = query_service.query(
                ChangeReportQuery(
                    attempt_id=attempt_id,
                    expected_result_fingerprint=_text(
                        result.get("result_fingerprint"), "result_fingerprint"
                    ),
                    expected_schedule_version_id=version_id,
                    expected_schedule_content_fingerprint=_text(
                        schedule.get("content_fingerprint"), "content_fingerprint"
                    ),
                    expected_report_id=_text(
                        change_report.get("report_id"), "change_report.report_id"
                    ),
                    expected_report_fingerprint=_text(
                        change_report.get("report_fingerprint"),
                        "change_report.report_fingerprint",
                    ),
                    limit=200,
                ),
                ChangeReportReadContext(
                    actor_ref=DEMO_ACTOR_REF,
                    authenticated=True,
                    resolved_capabilities=frozenset({"view"}),
                    attempt_scope=frozenset({attempt_id}),
                    schedule_version_scope=frozenset({version_id}),
                    data_plane="SIMULATION",
                    environment=cast(str, schedule["environment"]),
                    production_binding=False,
                ),
                generated_at_utc=_text(
                    change_report.get("generated_at_utc"),
                    "change_report.generated_at_utc",
                ),
            )
        except Exception:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "change_report")
        if validated.schedule_version != schedule:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "schedule_version")

        lineage = _mapping(schedule.get("lineage"), "schedule.lineage")
        reference_fields = (
            "base_snapshot",
            "base_problem",
            "new_snapshot",
            "new_problem",
            "candidate",
            "validation_report",
            "kpi",
            "solver_report",
        )
        report_artifact_reference: dict[str, object] = {
            "document_version": "change-report.v1",
            "artifact_id": _text(change_report.get("report_id"), "report_id"),
            "fingerprint": _text(
                change_report.get("report_fingerprint"), "report_fingerprint"
            ),
        }
        references = tuple(
            _artifact_reference(lineage.get(field), f"schedule.lineage.{field}")
            for field in reference_fields
        ) + (report_artifact_reference,)
        references_by_version = {
            cast(str, value["document_version"]): value for value in references
        }
        snapshot = self._snapshot(
            database, references_by_version["planning-snapshot.v2"]
        )
        problem = _resolve_artifact(
            database,
            kind="PLANNING_PROBLEM",
            reference=references_by_version["planning-problem.v2"],
        )
        resolved_documents = (
            (
                "SOLVER_REPORT",
                references_by_version["solver-report.v2"],
                stored.solver_report,
            ),
            (
                "VALIDATION_REPORT",
                references_by_version["validation-report.v2"],
                stored.validation_report,
            ),
            ("KPI", references_by_version["kpi.v2"], stored.kpi),
            (
                "CHANGE_REPORT",
                references_by_version["change-report.v1"],
                stored.change_report,
            ),
        )
        for kind, reference, expected in resolved_documents:
            if _resolve_artifact(database, kind=kind, reference=reference) != expected:
                _reject("PRESENTATION_LINEAGE_MISMATCH", f"artifact.{kind}")
        replan_reference = _mapping(lineage.get("replan_request"), "replan_request")
        request_reference: dict[str, object] = {
            "document_version": "replan-request.v1",
            "artifact_id": _text(replan_reference.get("request_id"), "request_id"),
            "fingerprint": _text(
                replan_reference.get("request_fingerprint"), "request_fingerprint"
            ),
        }
        request_document = _resolve_artifact(
            database, kind="REPLAN_REQUEST", reference=request_reference
        )
        try:
            require_p4_document(request_document)
            require_p4_document(stored.solver_report)
            require_p4_document(stored.change_report)
            validate_built_problem_v2(cast(Any, problem))
        except Exception:
            _reject("PRESENTATION_CONTRACT_REJECTED", "dynamic_artifacts")
        candidate_reference = references_by_version["replan-candidate.v1"]
        candidate = _mapping(stored.solver_report.get("candidate"), "solver.candidate")
        if (
            candidate.get("candidate_fingerprint")
            != candidate_reference.get("fingerprint")
            or "replan-candidate-"
            + _text(candidate.get("candidate_fingerprint"), "candidate_fingerprint").removeprefix(
                "sha256:"
            )
            != candidate_reference.get("artifact_id")
            or _sequence(candidate.get("assignments"), "candidate.assignments")
            != _sequence(
                _mapping(schedule.get("content"), "schedule.content").get(
                    "assignments"
                ),
                "schedule.assignments",
            )
        ):
            _reject("PRESENTATION_LINEAGE_MISMATCH", "candidate")
        self._validate_kpi(
            schedule=schedule,
            snapshot=snapshot,
            problem=problem,
            solver=stored.solver_report,
            validation=stored.validation_report,
            kpi=stored.kpi,
        )
        return _SchedulePackage(
            schedule=schedule,
            snapshot=snapshot,
            problem=problem,
            solver=stored.solver_report,
            validation=stored.validation_report,
            kpi=stored.kpi,
            references=tuple([*references, request_reference]),
            change_report=stored.change_report,
            replan_result=result,
            attempt_id=attempt_id,
        )

    def _package(
        self, database: RunDatabase, version_id: str
    ) -> _SchedulePackage:
        repository = SqlAlchemyScheduleVersionRepository(
            database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        )
        schedule = repository.get(version_id)
        if schedule is None:
            _reject("PRESENTATION_NOT_FOUND", "schedule_version_id")
        if schedule.get("data_plane") != "SIMULATION" or schedule.get(
            "synthetic"
        ) is not True:
            _reject("PRESENTATION_CONTRACT_REJECTED", "schedule.boundary")
        version = schedule.get("schedule_version_version")
        if version == "schedule-version.v1":
            return self._initial_package(database, schedule)
        if version == "schedule-version.v2":
            return self._dynamic_package(database, schedule)
        _reject("PRESENTATION_CONTRACT_REJECTED", "schedule_version_version")

    def _validate_kpi(
        self,
        *,
        schedule: Mapping[str, object],
        snapshot: Mapping[str, object],
        problem: Mapping[str, object],
        solver: Mapping[str, object],
        validation: Mapping[str, object],
        kpi: Mapping[str, object],
    ) -> None:
        formal_validation = _semantic_document(validation)
        if (
            kpi.get("kpi_version") != "kpi.v2"
            or formal_validation.get("validation_report_version")
            != "validation-report.v2"
            or formal_validation.get("status") != "PASS"
            or formal_validation.get("hard_violation_count") != 0
            or formal_validation.get("violations") != []
        ):
            _reject("PRESENTATION_CONTRACT_REJECTED", "kpi/validation")
        lineage = _mapping(schedule.get("lineage"), "schedule.lineage")
        planning_run_id = _text(lineage.get("planning_run_id"), "planning_run_id")
        if kpi.get("planning_run_id") != planning_run_id:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "kpi.planning_run_id")
        inputs = _mapping(kpi.get("inputs"), "kpi.inputs")
        checks = (
            ("snapshot", "snapshot_hash", snapshot.get("snapshot_hash")),
            ("problem", "problem_hash", problem.get("problem_hash")),
            (
                "validation_report",
                "validation_report_fingerprint",
                contract_fingerprint(formal_validation),
            ),
        )
        for container, field, expected in checks:
            if _mapping(inputs.get(container), f"kpi.inputs.{container}").get(
                field
            ) != expected:
                _reject("PRESENTATION_LINEAGE_MISMATCH", f"kpi.inputs.{container}")
        solver_input = _mapping(inputs.get("solver_report"), "kpi.inputs.solver")
        expected_solver_fingerprint = (
            solver.get("report_fingerprint")
            if solver.get("solver_report_version") == "solver-report.v2"
            else contract_fingerprint(solver)
        )
        input_fingerprint = solver_input.get("solver_report_fingerprint")
        # Replan KPI v2 deliberately points to its final stage v1 report, while
        # the v2 envelope remains the ScheduleVersion solver lineage authority.
        if schedule.get("schedule_version_version") == "schedule-version.v1" and (
            input_fingerprint != expected_solver_fingerprint
        ):
            _reject("PRESENTATION_LINEAGE_MISMATCH", "kpi.inputs.solver_report")

    def factory(self) -> DemoFactoryView:
        run_id, database, manifest = self._database()
        try:
            if manifest.get("assets_digest") != self.assets.asset_digest:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "assets_digest")
            profile_name = _text(manifest.get("profile_name"), "profile_name")
            try:
                profile = self.assets.profile(profile_name)
            except Exception:
                _reject("PRESENTATION_CONTRACT_REJECTED", "profile_name")
            snapshot_reference = {
                "document_version": "planning-snapshot.v2",
                "artifact_id": _text(manifest.get("snapshot_id"), "snapshot_id"),
                "fingerprint": _text(manifest.get("snapshot_hash"), "snapshot_hash"),
            }
            snapshot = self._snapshot(database, snapshot_reference)
            context = _PresentationContext(snapshot, self.assets)
            selected_source_resources = set(
                cast(
                    Sequence[str],
                    self.assets.resource_catalog["profile_resource_ids"][
                        profile.resource_profile
                    ],
                )
            )
            if set(context.source_resources) != selected_source_resources:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "factory.resources")

            horizon_start = _text(manifest.get("horizon_start_utc"), "horizon_start")
            horizon_end = _text(manifest.get("horizon_end_utc"), "horizon_end")
            maintenance_by_interval: dict[
                tuple[str, str, str], Mapping[str, object]
            ] = {}
            maintenance_views: list[MaintenanceEventView] = []
            for raw_event in cast(
                Sequence[object], self.assets.maintenance_plan["events"]
            ):
                event = cast(Mapping[str, object], raw_event)
                source_resource_id = _text(
                    event.get("resource_id"), "maintenance.resource_id"
                )
                if source_resource_id not in selected_source_resources:
                    continue
                start_value = datetime.fromisoformat(
                    _text(event.get("start_local"), "maintenance.start_local")
                ).astimezone(UTC)
                end_value = datetime.fromisoformat(
                    _text(event.get("end_local"), "maintenance.end_local")
                ).astimezone(UTC)
                start_utc = _to_utc(start_value)
                end_utc = _to_utc(end_value)
                if not _overlaps(
                    start_utc,
                    end_utc,
                    window_start=horizon_start,
                    window_end=horizon_end,
                ):
                    continue
                resource = context.source_resources[source_resource_id]
                resource_id = _text(resource.get("resource_id"), "resource_id")
                key = (resource_id, start_utc, end_utc)
                maintenance_by_interval[key] = event
                maintenance_views.append(
                    MaintenanceEventView(
                        event_id=_text(event.get("event_id"), "event_id"),
                        resource_id=resource_id,
                        source_resource_id=source_resource_id,
                        resource_code=_text(
                            resource.get("resource_code"), "resource_code"
                        ),
                        reason=_text(event.get("reason"), "maintenance.reason"),
                        start=_time_pair(start_utc, context.timezone),
                        end=_time_pair(end_utc, context.timezone),
                    )
                )

            resource_views: dict[str, FactoryResourceView] = {}
            maintenance_observed: set[tuple[str, str, str]] = set()
            interval_count = 0
            for resource_id, resource in context.resources.items():
                labels = context.resource_labels(resource_id)
                calendar_id = _text(resource.get("calendar_id"), "calendar_id")
                calendar = context.calendars.get(calendar_id)
                if calendar is None:
                    _reject("PRESENTATION_LINEAGE_MISMATCH", "resource.calendar")
                intervals: list[UnavailableIntervalView] = []
                for raw_interval in _sequence(
                    calendar.get("unavailable_intervals"),
                    "calendar.unavailable_intervals",
                ):
                    interval = _mapping(raw_interval, "calendar.interval")
                    start_utc = _text(interval.get("start_at_utc"), "interval.start")
                    end_utc = _text(interval.get("end_at_utc"), "interval.end")
                    maintenance = maintenance_by_interval.get(
                        (resource_id, start_utc, end_utc)
                    )
                    if maintenance is not None:
                        maintenance_observed.add((resource_id, start_utc, end_utc))
                    intervals.append(
                        UnavailableIntervalView(
                            interval_id=_text(
                                interval.get("interval_id"), "interval_id"
                            ),
                            kind=(
                                "MAINTENANCE" if maintenance is not None else "SHIFT"
                            ),
                            reason=_text(interval.get("reason"), "interval.reason"),
                            start=_time_pair(start_utc, context.timezone),
                            end=_time_pair(end_utc, context.timezone),
                        )
                    )
                intervals.sort(key=lambda item: (item.start.utc, item.interval_id))
                interval_count += len(intervals)
                asset = context.asset_resources[
                    cast(str, labels["source_resource_id"])
                ]
                resource_views[resource_id] = FactoryResourceView(
                    resource_id=resource_id,
                    source_resource_id=cast(str, labels["source_resource_id"]),
                    resource_code=cast(str, labels["resource_code"]),
                    resource_name=cast(str, labels["resource_name"]),
                    family=_text(asset.get("family"), "resource.family"),
                    status=cast(Literal["ACTIVE"], resource.get("status")),
                    capabilities=tuple(
                        sorted(
                            _text(value, "resource.capability")
                            for value in _sequence(
                                resource.get("capabilities"), "resource.capabilities"
                            )
                        )
                    ),
                    calendar_id=calendar_id,
                    unavailable_intervals=tuple(intervals),
                )
            if maintenance_observed != set(maintenance_by_interval):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "maintenance.calendar")

            workshop_views: list[FactoryWorkshopView] = []
            for workshop in sorted(
                context.workshops.values(),
                key=lambda item: _text(item.get("workshop_code"), "workshop_code"),
            ):
                workshop_id = _text(workshop.get("workshop_id"), "workshop_id")
                source_workshop_id = _source_id(workshop, "workshop.source")
                asset_workshop = context.asset_workshops.get(source_workshop_id)
                if asset_workshop is None:
                    _reject("PRESENTATION_LINEAGE_MISMATCH", "workshop.asset")
                lines = [
                    line
                    for line in context.lines.values()
                    if line.get("workshop_id") == workshop_id
                ]
                if len(lines) != 1:
                    _reject("PRESENTATION_LINEAGE_MISMATCH", "workshop.line")
                line = lines[0]
                line_id = _text(line.get("production_line_id"), "line_id")
                group_views: list[FactoryResourceGroupView] = []
                for group in sorted(
                    (
                        value
                        for value in context.groups.values()
                        if value.get("production_line_id") == line_id
                    ),
                    key=lambda item: _text(
                        item.get("resource_group_code"), "resource_group_code"
                    ),
                ):
                    group_id = _text(group.get("resource_group_id"), "group_id")
                    resources = sorted(
                        (
                            resource_views[resource_id]
                            for resource_id, value in context.resources.items()
                            if value.get("resource_group_id") == group_id
                        ),
                        key=lambda item: item.resource_code,
                    )
                    group_views.append(
                        FactoryResourceGroupView(
                            resource_group_id=group_id,
                            source_resource_group_id=_source_id(
                                group, "resource_group.source"
                            ),
                            resource_group_code=_text(
                                group.get("resource_group_code"), "group_code"
                            ),
                            resources=tuple(resources),
                        )
                    )
                workshop_views.append(
                    FactoryWorkshopView(
                        workshop_id=workshop_id,
                        source_workshop_id=source_workshop_id,
                        workshop_code=_text(
                            workshop.get("workshop_code"), "workshop_code"
                        ),
                        workshop_name=_text(
                            asset_workshop.get("workshop_name_zh"), "workshop_name"
                        ),
                        production_line=FactoryProductionLineView(
                            production_line_id=line_id,
                            source_production_line_id=_source_id(line, "line.source"),
                            production_line_code=_text(
                                line.get("production_line_code"), "line_code"
                            ),
                            resource_groups=tuple(group_views),
                        ),
                    )
                )
            factory_records = tuple(context.factories.values())
            if len(factory_records) != 1:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "factory")
            factory = factory_records[0]
            factory_asset = cast(Mapping[str, object], self.assets.factory["factory"])
            if _source_id(factory, "factory.source") != factory_asset.get("factory_id"):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "factory.asset")
            maintenance_views.sort(key=lambda item: (item.start.utc, item.event_id))
            document: dict[str, object] = {
                "view_version": "cnc-demo-factory-view.v1",
                "run_id": run_id,
                "scenario_id": _text(manifest.get("scenario_id"), "scenario_id"),
                "profile_name": profile_name,
                "seed": _integer(manifest.get("seed"), "seed"),
                "horizon_start": _time_pair(horizon_start, context.timezone),
                "horizon_end": _time_pair(horizon_end, context.timezone),
                "factory": FactoryNodeView(
                    factory_id=_text(factory.get("factory_id"), "factory_id"),
                    source_factory_id=_source_id(factory, "factory.source"),
                    factory_code=_text(factory.get("factory_code"), "factory_code"),
                    factory_name=_text(
                        factory_asset.get("factory_name_zh"), "factory_name"
                    ),
                    timezone=context.timezone_name,
                    workshops=tuple(workshop_views),
                ),
                "maintenance_events": tuple(maintenance_views),
                "counts": FactoryCounts(
                    workshops=len(context.workshops),
                    production_lines=len(context.lines),
                    resource_groups=len(context.groups),
                    resources=len(context.resources),
                    maintenance_events=len(maintenance_views),
                    unavailable_intervals=interval_count,
                ),
                "provenance": FactoryProvenance(
                    asset_pack_version=_text(
                        self.assets.manifest.get("asset_pack_version"),
                        "asset_pack_version",
                    ),
                    asset_pack_fingerprint="sha256:" + self.assets.asset_digest,
                    snapshot=_reference_view(snapshot_reference),
                ),
                "boundary": _boundary("TEST"),
            }
            return cast(DemoFactoryView, _finalize(DemoFactoryView, document))
        finally:
            database.close()

    def _version_summary(
        self, schedule: Mapping[str, object], timezone: ZoneInfo
    ) -> ScheduleVersionSummary:
        parent = schedule.get("parent_schedule_version")
        parent_id = (
            None
            if parent is None
            else _text(
                _mapping(parent, "parent_schedule_version").get(
                    "schedule_version_id"
                ),
                "parent_schedule_version.schedule_version_id",
            )
        )
        return ScheduleVersionSummary(
            schedule_version_id=_text(
                schedule.get("schedule_version_id"), "schedule_version_id"
            ),
            contract_version=cast(
                Literal["schedule-version.v1", "schedule-version.v2"],
                schedule.get("schedule_version_version"),
            ),
            revision=_integer(schedule.get("revision"), "revision"),
            state=cast(Any, schedule.get("state")),
            source_kind=_text(schedule.get("source_kind"), "source_kind"),
            parent_schedule_version_id=parent_id,
            content_fingerprint=_text(
                schedule.get("content_fingerprint"), "content_fingerprint"
            ),
            created_at=_time_pair(
                _text(schedule.get("created_at_utc"), "created_at_utc"), timezone
            ),
        )

    def _solver_summary(self, solver: Mapping[str, object]) -> SolverSummary:
        stages = _sequence(
            solver.get("objective_stage_results"), "solver.objective_stage_results"
        )
        if not stages:
            _reject("PRESENTATION_CONTRACT_REJECTED", "solver.objective_stage_results")
        first = _mapping(stages[0], "solver.objective_stage_results[0]")
        limits = _mapping(solver.get("limits"), "solver.limits")
        timings = _mapping(solver.get("timings"), "solver.timings")
        objective = first.get("objective_value")
        best_bound = first.get("best_bound")
        if objective is not None and (
            isinstance(objective, bool) or not isinstance(objective, (int, float))
        ):
            _reject("PRESENTATION_CONTRACT_REJECTED", "solver.objective_value")
        if best_bound is not None and (
            isinstance(best_bound, bool) or not isinstance(best_bound, (int, float))
        ):
            _reject("PRESENTATION_CONTRACT_REJECTED", "solver.best_bound")
        gap_value = first.get("relative_gap")
        relative_gap = None if gap_value is None else _number(gap_value, "relative_gap")
        status = _text(solver.get("solver_status"), "solver_status")
        return SolverSummary(
            solver_report_version=cast(Any, solver.get("solver_report_version")),
            report_id=_text(solver.get("report_id"), "solver.report_id"),
            solver_status=cast(Any, status),
            evidence_kind=cast(Any, solver.get("evidence_kind")),
            limit_seconds=_number(
                limits.get("max_wall_time_seconds"), "max_wall_time_seconds"
            ),
            objective_value=cast(int | float | None, objective),
            best_bound=cast(int | float | None, best_bound),
            relative_gap=relative_gap,
            solve_seconds=_number(timings.get("solve_seconds"), "solve_seconds"),
            total_seconds=_number(timings.get("total_seconds"), "total_seconds"),
            optimality_claim=status == "OPTIMAL",
        )

    def _kpi_summary(self, kpi: Mapping[str, object]) -> KpiSummary:
        delivery = _mapping(kpi.get("delivery"), "kpi.delivery")
        planning = _mapping(kpi.get("planning"), "kpi.planning")
        stability = _mapping(kpi.get("stability"), "kpi.stability")

        def optional_int(value: object, field: str) -> int | None:
            return None if value is None else _integer(value, field)

        def optional_float(value: object, field: str) -> float | None:
            return None if value is None else _number(value, field)

        return KpiSummary(
            kpi_id=_text(kpi.get("kpi_id"), "kpi_id"),
            kpi_version=cast(Literal["kpi.v2"], kpi.get("kpi_version")),
            fingerprint=contract_fingerprint(kpi),
            delivery=DeliverySummary(
                order_count=_integer(delivery.get("order_count"), "order_count"),
                on_time_order_count=_integer(
                    delivery.get("on_time_order_count"), "on_time_order_count"
                ),
                on_time_order_ratio=optional_float(
                    delivery.get("on_time_order_ratio"), "on_time_order_ratio"
                ),
                late_order_count=_integer(
                    delivery.get("late_order_count"), "late_order_count"
                ),
                total_tardiness_seconds=_integer(
                    delivery.get("total_tardiness_seconds"),
                    "total_tardiness_seconds",
                ),
                priority_weighted_tardiness_seconds=_integer(
                    delivery.get("priority_weighted_tardiness_seconds"),
                    "priority_weighted_tardiness_seconds",
                ),
            ),
            planning=PlanningSummary(
                makespan_seconds=_integer(
                    planning.get("makespan_seconds"), "makespan_seconds"
                ),
                scheduled_operation_count=_integer(
                    planning.get("scheduled_operation_count"),
                    "scheduled_operation_count",
                ),
                unscheduled_operation_count=_integer(
                    planning.get("unscheduled_operation_count"),
                    "unscheduled_operation_count",
                ),
            ),
            stability=KpiStabilitySummary(
                status=_text(stability.get("status"), "stability.status"),
                changed_operation_count=optional_int(
                    stability.get("changed_operation_count"),
                    "changed_operation_count",
                ),
                resource_changed_count=optional_int(
                    stability.get("resource_changed_count"),
                    "resource_changed_count",
                ),
                start_shift_seconds=optional_int(
                    stability.get("start_shift_seconds"), "start_shift_seconds"
                ),
                schedule_stability_ratio=optional_float(
                    stability.get("schedule_stability_ratio"),
                    "schedule_stability_ratio",
                ),
            ),
        )

    def _assignment(
        self,
        raw_assignment: Mapping[str, object],
        *,
        context: _PresentationContext,
        problem_operations: Mapping[str, Mapping[str, object]],
        locks_by_operation: Mapping[str, tuple[str, ...]],
        lock_types: Mapping[str, str],
    ) -> ScheduleAssignmentView:
        operation_id = _text(raw_assignment.get("operation_id"), "operation_id")
        problem_operation = problem_operations.get(operation_id)
        if problem_operation is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "assignment.operation_id")
        labels = context.operation_labels(operation_id)
        resource_id = _text(raw_assignment.get("resource_id"), "resource_id")
        resource_labels = context.resource_labels(resource_id)
        operation_state = _text(
            problem_operation.get("status"), "problem.operation.status"
        )
        assignment_lock_ids = tuple(
            sorted(
                _text(value, "assignment.lock_ids")
                for value in _sequence(
                    raw_assignment.get("lock_ids"), "assignment.lock_ids"
                )
            )
        )
        expected_locks = locks_by_operation.get(operation_id, ())
        if assignment_lock_ids != expected_locks:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "assignment.lock_ids")
        if operation_state == "RUNNING":
            protection = "RUNNING"
        elif any(lock_types.get(value) == "HARD" for value in assignment_lock_ids):
            protection = "HARD_LOCK"
        elif any(lock_types.get(value) == "SOFT" for value in assignment_lock_ids):
            protection = "SOFT_LOCK"
        else:
            protection = "FREE"
        return ScheduleAssignmentView(
            operation_id=operation_id,
            operation_code=cast(str, labels["operation_code"]),
            operation_name=cast(str, labels["operation_name"]),
            operation_sequence=cast(int, labels["operation_sequence"]),
            demand_order_id=cast(str, labels["demand_order_id"]),
            order_code=cast(str, labels["order_code"]),
            product_code=cast(str, labels["product_code"]),
            resource_id=resource_id,
            source_resource_id=cast(str, resource_labels["source_resource_id"]),
            resource_code=cast(str, resource_labels["resource_code"]),
            resource_name=cast(str, resource_labels["resource_name"]),
            workshop_id=cast(str, resource_labels["workshop_id"]),
            source_workshop_id=cast(
                str, resource_labels["source_workshop_id"]
            ),
            workshop_code=cast(str, resource_labels["workshop_code"]),
            workshop_name=cast(str, resource_labels["workshop_name"]),
            start=_time_pair(
                _text(raw_assignment.get("start_at_utc"), "start_at_utc"),
                context.timezone,
            ),
            end=_time_pair(
                _text(raw_assignment.get("end_at_utc"), "end_at_utc"),
                context.timezone,
            ),
            duration_seconds=_integer(
                raw_assignment.get("duration_seconds"), "duration_seconds"
            ),
            operation_state=cast(Any, operation_state),
            candidate_resource_count=len(
                _sequence(
                    problem_operation.get("resource_options"),
                    "problem.operation.resource_options",
                )
            ),
            lock_ids=assignment_lock_ids,
            execution_fact_ids=tuple(
                sorted(
                    _text(value, "assignment.execution_fact_ids")
                    for value in _sequence(
                        raw_assignment.get("execution_fact_ids"),
                        "assignment.execution_fact_ids",
                    )
                )
            ),
            protection=cast(Any, protection),
        )

    def _execution_segments(
        self, context: _PresentationContext
    ) -> tuple[ExecutionSegmentView, ...]:
        by_route_lot: dict[tuple[str, str], Mapping[str, object]] = {}
        for operation in context.operation_instances.values():
            key = (
                _text(operation.get("routing_operation_id"), "routing_operation_id"),
                _text(operation.get("production_lot_id"), "production_lot_id"),
            )
            if key in by_route_lot:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "operation_instance")
            by_route_lot[key] = operation
        segments: list[ExecutionSegmentView] = []
        for fact in _record_sequence(context.snapshot, "execution_facts"):
            status = _text(fact.get("status"), "execution_fact.status")
            if status not in {"COMPLETED", "RUNNING"}:
                continue
            key = (
                _text(fact.get("routing_operation_id"), "routing_operation_id"),
                _text(fact.get("production_lot_id"), "production_lot_id"),
            )
            operation = by_route_lot.get(key)
            if operation is None:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "execution_fact.operation")
            resource_id = _text(fact.get("resource_id"), "execution_fact.resource_id")
            labels = context.resource_labels(resource_id)
            end_value = fact.get("actual_end_at_utc")
            remaining_value = fact.get("remaining_seconds")
            segments.append(
                ExecutionSegmentView(
                    execution_fact_id=_text(
                        fact.get("execution_fact_id"), "execution_fact_id"
                    ),
                    operation_id=_text(
                        operation.get("operation_instance_id"), "operation_id"
                    ),
                    demand_order_id=_text(
                        operation.get("demand_order_id"), "demand_order_id"
                    ),
                    resource_id=resource_id,
                    resource_code=cast(str, labels["resource_code"]),
                    status=cast(Any, status),
                    actual_start=_time_pair(
                        _text(fact.get("actual_start_at_utc"), "actual_start"),
                        context.timezone,
                    ),
                    actual_end=(
                        None
                        if end_value is None
                        else _time_pair(_text(end_value, "actual_end"), context.timezone)
                    ),
                    remaining_seconds=(
                        None
                        if remaining_value is None
                        else _integer(remaining_value, "remaining_seconds")
                    ),
                )
            )
        segments.sort(key=lambda item: (item.actual_start.utc, item.execution_fact_id))
        return tuple(segments)

    def _orders(
        self,
        *,
        package: _SchedulePackage,
        context: _PresentationContext,
        assignments: Sequence[ScheduleAssignmentView],
    ) -> tuple[OrderView, ...]:
        kpi_delivery = _mapping(package.kpi.get("delivery"), "kpi.delivery")
        demands = _sequence(kpi_delivery.get("demands"), "kpi.delivery.demands")
        if _integer(kpi_delivery.get("order_count"), "order_count") != len(demands):
            _reject("PRESENTATION_LINEAGE_MISMATCH", "kpi.delivery.order_count")
        operations_by_demand: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for operation in context.operation_instances.values():
            operations_by_demand[
                _text(operation.get("demand_order_id"), "demand_order_id")
            ].append(operation)
        scheduled_by_demand = Counter(item.demand_order_id for item in assignments)
        priority_classes = {
            _integer(
                cast(Mapping[str, object], item).get("priority_weight"),
                "priority_weight",
            ): _text(cast(Mapping[str, object], item).get("class_id"), "class_id")
            for item in cast(Sequence[object], self.assets.priority_policy["classes"])
        }
        result: list[OrderView] = []
        for demand_value in demands:
            kpi_demand = _mapping(demand_value, "kpi.delivery.demand")
            demand_id = _text(kpi_demand.get("demand_order_id"), "demand_order_id")
            demand = context.demands.get(demand_id)
            order_operations = operations_by_demand.get(demand_id, [])
            if demand is None or not order_operations:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "order")
            product = context.products.get(_text(demand.get("product_id"), "product_id"))
            if product is None or demand.get("due_at_utc") != kpi_demand.get("due_at_utc"):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "order.kpi")
            priority_weight = _integer(
                kpi_demand.get("priority_weight"), "priority_weight"
            )
            priority_class = priority_classes.get(priority_weight)
            if priority_class is None:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "priority_weight")
            release = min(
                _text(item.get("release_at_utc"), "release_at_utc")
                for item in order_operations
            )
            material = min(
                _text(item.get("material_ready_at_utc"), "material_ready_at_utc")
                for item in order_operations
            )
            statuses = Counter(
                _text(item.get("status"), "operation.status")
                for item in order_operations
            )
            quantity = demand.get("quantity")
            if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
                _reject("PRESENTATION_CONTRACT_REJECTED", "demand.quantity")
            result.append(
                OrderView(
                    demand_order_id=demand_id,
                    order_code=_source_id(demand, "demand.source"),
                    product_code=_text(product.get("product_code"), "product_code"),
                    quantity=quantity,
                    quantity_unit=_text(demand.get("quantity_unit"), "quantity_unit"),
                    priority_class=cast(Any, priority_class),
                    priority_weight=priority_weight,
                    release_at=_time_pair(release, context.timezone),
                    material_ready_at=_time_pair(material, context.timezone),
                    due_at=_time_pair(
                        _text(kpi_demand.get("due_at_utc"), "due_at_utc"),
                        context.timezone,
                    ),
                    completion_at=_time_pair(
                        _text(
                            kpi_demand.get("completion_at_utc"),
                            "completion_at_utc",
                        ),
                        context.timezone,
                    ),
                    tardiness_seconds=_integer(
                        kpi_demand.get("tardiness_seconds"), "tardiness_seconds"
                    ),
                    on_time=cast(bool, kpi_demand.get("on_time")),
                    operation_count=len(order_operations),
                    scheduled_operation_count=scheduled_by_demand[demand_id],
                    completed_operation_count=statuses["COMPLETED"],
                    running_operation_count=statuses["RUNNING"],
                )
            )
        result.sort(key=lambda item: item.order_code)
        return tuple(result)

    def _resource_loads(
        self,
        *,
        package: _SchedulePackage,
        context: _PresentationContext,
    ) -> tuple[ResourceLoadView, ...]:
        kpi_reference = next(
            (
                value
                for value in package.references
                if value.get("document_version") == "kpi.v2"
                and value.get("artifact_id") == package.kpi.get("kpi_id")
            ),
            None,
        )
        if kpi_reference is None:
            _reject("PRESENTATION_LINEAGE_MISMATCH", "kpi.reference")
        resources = _sequence(package.kpi.get("resources"), "kpi.resources")
        result: list[ResourceLoadView] = []
        for value in resources:
            row = _mapping(value, "kpi.resources[]")
            resource_id = _text(row.get("resource_id"), "resource_id")
            labels = context.resource_labels(resource_id)
            available = _integer(row.get("available_seconds"), "available_seconds")
            busy = _integer(row.get("planned_busy_seconds"), "planned_busy_seconds")
            utilization_value = row.get("utilization")
            utilization = (
                None
                if utilization_value is None
                else _number(utilization_value, "utilization")
            )
            expected = None if available == 0 else busy / available
            if (
                (expected is None) != (utilization is None)
                or expected is not None
                and utilization is not None
                and abs(expected - utilization) > 1e-12
            ):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "kpi.resources.utilization")
            result.append(
                ResourceLoadView(
                    resource_id=resource_id,
                    source_resource_id=cast(str, labels["source_resource_id"]),
                    resource_code=cast(str, labels["resource_code"]),
                    resource_name=cast(str, labels["resource_name"]),
                    workshop_id=cast(str, labels["workshop_id"]),
                    workshop_code=cast(str, labels["workshop_code"]),
                    available_seconds=available,
                    planned_busy_seconds=busy,
                    utilization=utilization,
                    formula="planned_busy_seconds / available_seconds",
                    evidence=_reference_view(kpi_reference),
                )
            )
        if len(result) != len(context.resources):
            _reject("PRESENTATION_LINEAGE_MISMATCH", "kpi.resources")
        result.sort(key=lambda item: item.resource_code)
        return tuple(result)

    def schedule(
        self,
        version_id: str,
        query: SchedulePresentationQuery | None = None,
    ) -> DemoScheduleView:
        selected_query = SchedulePresentationQuery() if query is None else query
        run_id, database, manifest = self._database()
        try:
            package = self._package(database, version_id)
            context = _PresentationContext(package.snapshot, self.assets)
            content = _mapping(package.schedule.get("content"), "schedule.content")
            raw_locks = _sequence(content.get("locks"), "schedule.content.locks")
            locks_by_operation_values: dict[str, list[str]] = defaultdict(list)
            lock_types: dict[str, str] = {}
            for value in raw_locks:
                lock = _mapping(value, "schedule.content.locks[]")
                lock_id = _text(lock.get("lock_id"), "lock_id")
                operation_id = _text(lock.get("operation_id"), "operation_id")
                if lock_id in lock_types:
                    _reject("PRESENTATION_CONTRACT_REJECTED", "schedule.locks")
                lock_types[lock_id] = _text(lock.get("lock_type"), "lock_type")
                locks_by_operation_values[operation_id].append(lock_id)
            locks_by_operation = {
                key: tuple(sorted(values))
                for key, values in locks_by_operation_values.items()
            }
            problem_operations = {
                _text(value.get("operation_id"), "problem.operation_id"): value
                for value in (
                    _mapping(item, "problem.operation_instances[]")
                    for item in _sequence(
                        package.problem.get("operation_instances"),
                        "problem.operation_instances",
                    )
                )
            }
            assignments = [
                self._assignment(
                    _mapping(value, "schedule.content.assignments[]"),
                    context=context,
                    problem_operations=problem_operations,
                    locks_by_operation=locks_by_operation,
                    lock_types=lock_types,
                )
                for value in _sequence(
                    content.get("assignments"), "schedule.content.assignments"
                )
            ]
            if len(assignments) != self._kpi_summary(
                package.kpi
            ).planning.scheduled_operation_count:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "assignment_count")

            resource_filter = set(selected_query.resource_ids)
            workshop_filter = set(selected_query.workshop_ids)
            demand_filter = set(selected_query.demand_order_ids)
            state_filter = set(selected_query.states)
            filtered = [
                item
                for item in assignments
                if (
                    not resource_filter
                    or item.resource_id in resource_filter
                    or item.source_resource_id in resource_filter
                )
                and (
                    not workshop_filter
                    or item.workshop_id in workshop_filter
                    or item.source_workshop_id in workshop_filter
                )
                and (not demand_filter or item.demand_order_id in demand_filter)
                and (not state_filter or item.operation_state in state_filter)
                and _overlaps(
                    item.start.utc,
                    item.end.utc,
                    window_start=selected_query.start_at_utc,
                    window_end=selected_query.end_at_utc,
                )
            ]
            if selected_query.sort == "RESOURCE_START_ASC":
                filtered.sort(
                    key=lambda item: (
                        item.resource_code,
                        item.start.utc,
                        item.operation_id,
                    )
                )
            elif selected_query.sort == "ORDER_START_ASC":
                filtered.sort(
                    key=lambda item: (
                        item.order_code,
                        item.start.utc,
                        item.operation_id,
                    )
                )
            else:
                filtered.sort(key=lambda item: (item.start.utc, item.operation_id))
            start = selected_query.offset
            page_assignments = tuple(filtered[start : start + selected_query.limit])
            kpi_summary = self._kpi_summary(package.kpi)
            references = tuple(
                sorted(
                    (_reference_view(value) for value in package.references),
                    key=lambda item: (item.document_version, item.artifact_id),
                )
            )
            validation_document = _semantic_document(package.validation)
            document: dict[str, object] = {
                "view_version": "cnc-demo-schedule-view.v1",
                "run_id": run_id,
                "scenario_id": _text(manifest.get("scenario_id"), "scenario_id"),
                "timezone": context.timezone_name,
                "version": self._version_summary(
                    package.schedule, context.timezone
                ),
                "solver": self._solver_summary(package.solver),
                "validation": ValidationSummary(
                    validation_report_version="validation-report.v2",
                    status="PASS",
                    hard_violation_count=0,
                    fingerprint=contract_fingerprint(validation_document),
                ),
                "kpis": kpi_summary,
                "orders": self._orders(
                    package=package,
                    context=context,
                    assignments=assignments,
                ),
                "resources": self._resource_loads(
                    package=package, context=context
                ),
                "execution_segments": self._execution_segments(context),
                "assignments": page_assignments,
                "query": selected_query,
                "page": PageInfo(
                    offset=selected_query.offset,
                    limit=selected_query.limit,
                    returned=len(page_assignments),
                    filtered_total=len(filtered),
                    unfiltered_total=len(assignments),
                    has_more=start + len(page_assignments) < len(filtered),
                ),
                "provenance": ScheduleProvenance(
                    planning_run_id=_text(
                        _mapping(
                            package.schedule.get("lineage"), "schedule.lineage"
                        ).get("planning_run_id"),
                        "planning_run_id",
                    ),
                    schedule_content_fingerprint=_text(
                        package.schedule.get("content_fingerprint"),
                        "content_fingerprint",
                    ),
                    artifacts=references,
                ),
                "boundary": _boundary(
                    _text(package.schedule.get("environment"), "environment")
                ),
            }
            return cast(DemoScheduleView, _finalize(DemoScheduleView, document))
        finally:
            database.close()

    def _comparison_assignment(
        self,
        raw: object,
        *,
        context: _PresentationContext,
    ) -> ComparisonAssignmentView | None:
        if raw is None:
            return None
        assignment = _mapping(raw, "change_report.assignment")
        resource_id = _text(assignment.get("resource_id"), "resource_id")
        labels = context.resource_labels(resource_id)
        return ComparisonAssignmentView(
            resource_id=resource_id,
            source_resource_id=cast(str, labels["source_resource_id"]),
            resource_code=cast(str, labels["resource_code"]),
            workshop_id=cast(str, labels["workshop_id"]),
            workshop_code=cast(str, labels["workshop_code"]),
            start=_time_pair(
                _text(assignment.get("start_at_utc"), "start_at_utc"),
                context.timezone,
            ),
            end=_time_pair(
                _text(assignment.get("end_at_utc"), "end_at_utc"),
                context.timezone,
            ),
            duration_seconds=_integer(
                assignment.get("duration_seconds"), "duration_seconds"
            ),
        )

    def _change_operation(
        self,
        raw: Mapping[str, object],
        *,
        context: _PresentationContext,
    ) -> ChangeOperationView:
        operation_id = _text(raw.get("operation_id"), "operation_id")
        labels = context.operation_labels(operation_id)
        deltas = _mapping(raw.get("deltas"), "change_report.deltas")
        reasons = tuple(
            _text(
                _mapping(value, "change_report.reasons[]").get("reason_code"),
                "reason_code",
            )
            for value in _sequence(raw.get("reasons"), "change_report.reasons")
        )
        return ChangeOperationView(
            operation_id=operation_id,
            operation_code=cast(str, labels["operation_code"]),
            operation_name=cast(str, labels["operation_name"]),
            demand_order_id=cast(str, labels["demand_order_id"]),
            order_code=cast(str, labels["order_code"]),
            classification=cast(Any, raw.get("classification")),
            base_assignment=self._comparison_assignment(
                raw.get("base_assignment"), context=context
            ),
            new_assignment=self._comparison_assignment(
                raw.get("new_assignment"), context=context
            ),
            deltas=OperationDeltasView(
                resource_changed=cast(bool, deltas.get("resource_changed")),
                start_shift_seconds=_integer(
                    deltas.get("start_shift_seconds"), "start_shift_seconds"
                ),
                absolute_start_shift_seconds=_integer(
                    deltas.get("absolute_start_shift_seconds"),
                    "absolute_start_shift_seconds",
                ),
                end_shift_seconds=_integer(
                    deltas.get("end_shift_seconds"), "end_shift_seconds"
                ),
                duration_delta_seconds=_integer(
                    deltas.get("duration_delta_seconds"),
                    "duration_delta_seconds",
                ),
            ),
            reason_codes=reasons,
        )

    def comparison(
        self,
        request_id: str,
        query: ComparisonPresentationQuery | None = None,
    ) -> DemoComparisonView:
        selected_query = ComparisonPresentationQuery() if query is None else query
        run_id, database, manifest = self._database()
        try:
            with database.engine.connect() as connection:
                rows = connection.exec_driver_sql(
                    """
                    SELECT attempt_id, new_schedule_version_id
                    FROM replan_results
                    WHERE data_plane = 'SIMULATION' AND request_id = ?
                    ORDER BY attempt_id
                    """,
                    (request_id,),
                ).all()
            if len(rows) != 1 or rows[0][1] is None:
                _reject("PRESENTATION_NOT_FOUND", "request_id")
            attempt_id = _text(rows[0][0], "attempt_id")
            after_version_id = _text(rows[0][1], "new_schedule_version_id")
            after_package = self._package(database, after_version_id)
            if (
                after_package.attempt_id != attempt_id
                or after_package.replan_result is None
                or after_package.replan_result.get("request_id") != request_id
                or after_package.change_report is None
            ):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "comparison.result")
            report = after_package.change_report
            base_reference = _mapping(
                report.get("base_schedule_version"),
                "change_report.base_schedule_version",
            )
            before_version_id = _text(
                base_reference.get("schedule_version_id"),
                "base_schedule_version.schedule_version_id",
            )
            before_package = self._package(database, before_version_id)
            if (
                before_package.schedule.get("content_fingerprint")
                != base_reference.get("content_fingerprint")
                or before_package.schedule.get("state") != "PUBLISHED"
            ):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "comparison.base")
            before_kpi_reference = _artifact_reference(
                report.get("before_kpi"), "change_report.before_kpi"
            )
            after_kpi_reference = _artifact_reference(
                report.get("after_kpi"), "change_report.after_kpi"
            )
            before_kpi = _resolve_artifact(
                database, kind="KPI", reference=before_kpi_reference
            )
            after_kpi = _resolve_artifact(
                database, kind="KPI", reference=after_kpi_reference
            )
            if before_kpi != before_package.kpi or after_kpi != after_package.kpi:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "comparison.kpi")

            context = _PresentationContext(after_package.snapshot, self.assets)
            raw_operations = tuple(
                _mapping(value, "change_report.operations[]")
                for value in _sequence(
                    report.get("operations"), "change_report.operations"
                )
            )
            universe = _integer(
                report.get("operation_universe_count"),
                "operation_universe_count",
            )
            if len(raw_operations) != universe:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "operation_universe_count")
            class_counter = Counter(
                _text(value.get("classification"), "classification")
                for value in raw_operations
            )
            if set(class_counter).difference(
                {"UNCHANGED", "CHANGED", "ADDED", "REMOVED_BY_FACT"}
            ):
                _reject("PRESENTATION_CONTRACT_REJECTED", "classification")
            changes = [
                self._change_operation(value, context=context)
                for value in raw_operations
            ]
            if len({item.operation_id for item in changes}) != universe:
                _reject("PRESENTATION_LINEAGE_MISMATCH", "operations.operation_id")

            resource_filter = set(selected_query.resource_ids)
            workshop_filter = set(selected_query.workshop_ids)
            demand_filter = set(selected_query.demand_order_ids)
            class_filter = set(selected_query.classifications)

            def assignment_matches(
                item: ComparisonAssignmentView | None,
            ) -> bool:
                if item is None:
                    return False
                workshop = context.workshops.get(item.workshop_id)
                if workshop is None:
                    _reject("PRESENTATION_LINEAGE_MISMATCH", "workshop_id")
                return (
                    not resource_filter
                    or item.resource_id in resource_filter
                    or item.source_resource_id in resource_filter
                ) and (
                    not workshop_filter
                    or item.workshop_id in workshop_filter
                    or _source_id(workshop, "workshop.source") in workshop_filter
                )

            filtered: list[ChangeOperationView] = []
            for item in changes:
                selected_assignment = item.new_assignment or item.base_assignment
                if item.classification not in class_filter:
                    continue
                if demand_filter and item.demand_order_id not in demand_filter:
                    continue
                if (resource_filter or workshop_filter) and not (
                    assignment_matches(item.base_assignment)
                    or assignment_matches(item.new_assignment)
                ):
                    continue
                if selected_assignment is None or not _overlaps(
                    selected_assignment.start.utc,
                    selected_assignment.end.utc,
                    window_start=selected_query.start_at_utc,
                    window_end=selected_query.end_at_utc,
                ):
                    continue
                filtered.append(item)
            if selected_query.sort == "SHIFT_DESC":
                filtered.sort(
                    key=lambda item: (
                        -item.deltas.absolute_start_shift_seconds,
                        item.operation_id,
                    )
                )
            elif selected_query.sort == "START_ASC":
                filtered.sort(
                    key=lambda item: (
                        cast(
                            ComparisonAssignmentView,
                            item.new_assignment or item.base_assignment,
                        ).start.utc,
                        item.operation_id,
                    )
                )
            else:
                filtered.sort(key=lambda item: item.operation_id)
            page_start = selected_query.offset
            page_operations = tuple(
                filtered[page_start : page_start + selected_query.limit]
            )

            changed_order_counts = Counter(
                item.demand_order_id
                for item in changes
                if item.classification != "UNCHANGED"
            )
            affected_orders = tuple(
                sorted(
                    (
                        AffectedOrderView(
                            demand_order_id=demand_id,
                            order_code=cast(
                                str,
                                context.operation_labels(
                                    next(
                                        item.operation_id
                                        for item in changes
                                        if item.demand_order_id == demand_id
                                    )
                                )["order_code"],
                            ),
                            change_count=count,
                        )
                        for demand_id, count in changed_order_counts.items()
                    ),
                    key=lambda item: item.order_code,
                )
            )
            stability = _mapping(report.get("stability"), "change_report.stability")
            ratio_evidence = _mapping(
                stability.get("unchanged_ratio"), "stability.unchanged_ratio"
            )
            ratio_status = _text(ratio_evidence.get("status"), "ratio.status")
            numerator = _integer(ratio_evidence.get("numerator"), "ratio.numerator")
            denominator = _integer(
                ratio_evidence.get("denominator"), "ratio.denominator"
            )
            unchanged_ratio = None if denominator == 0 else numerator / denominator
            if (
                (ratio_status == "APPLICABLE") != (denominator > 0)
                or numerator
                != _integer(
                    stability.get("unchanged_existing"), "unchanged_existing"
                )
                or denominator
                != _integer(
                    stability.get("comparable_existing"), "comparable_existing"
                )
            ):
                _reject("PRESENTATION_LINEAGE_MISMATCH", "stability.unchanged_ratio")

            before_summary = self._kpi_summary(before_kpi)
            after_summary = self._kpi_summary(after_kpi)
            before_delivery = before_summary.delivery
            after_delivery = after_summary.delivery
            before_ratio = before_delivery.on_time_order_ratio
            after_ratio = after_delivery.on_time_order_ratio
            ratio_delta = (
                None
                if before_ratio is None or after_ratio is None
                else after_ratio - before_ratio
            )
            report_reference = {
                "document_version": "change-report.v1",
                "artifact_id": _text(report.get("report_id"), "report_id"),
                "fingerprint": _text(
                    report.get("report_fingerprint"), "report_fingerprint"
                ),
            }
            document: dict[str, object] = {
                "view_version": "cnc-demo-comparison-view.v1",
                "run_id": run_id,
                "scenario_id": _text(manifest.get("scenario_id"), "scenario_id"),
                "request_id": request_id,
                "timezone": context.timezone_name,
                "before": self._version_summary(
                    before_package.schedule, context.timezone
                ),
                "after": self._version_summary(
                    after_package.schedule, context.timezone
                ),
                "before_kpis": before_summary,
                "after_kpis": after_summary,
                "delivery_delta": DeliveryDelta(
                    order_count=(
                        after_delivery.order_count - before_delivery.order_count
                    ),
                    on_time_order_count=(
                        after_delivery.on_time_order_count
                        - before_delivery.on_time_order_count
                    ),
                    on_time_order_ratio=ratio_delta,
                    late_order_count=(
                        after_delivery.late_order_count
                        - before_delivery.late_order_count
                    ),
                    total_tardiness_seconds=(
                        after_delivery.total_tardiness_seconds
                        - before_delivery.total_tardiness_seconds
                    ),
                    priority_weighted_tardiness_seconds=(
                        after_delivery.priority_weighted_tardiness_seconds
                        - before_delivery.priority_weighted_tardiness_seconds
                    ),
                    makespan_seconds=(
                        after_summary.planning.makespan_seconds
                        - before_summary.planning.makespan_seconds
                    ),
                    formula="after - before",
                ),
                "operation_universe_count": universe,
                "change_counts": ChangeCounts(
                    unchanged=class_counter["UNCHANGED"],
                    changed=class_counter["CHANGED"],
                    added=class_counter["ADDED"],
                    removed_by_fact=class_counter["REMOVED_BY_FACT"],
                ),
                "stability": StabilitySummary(
                    soft_lock_violations=_integer(
                        stability.get("soft_lock_violations"),
                        "soft_lock_violations",
                    ),
                    changed_existing_operations=_integer(
                        stability.get("changed_existing_operations"),
                        "changed_existing_operations",
                    ),
                    resource_changes=_integer(
                        stability.get("resource_changes"), "resource_changes"
                    ),
                    absolute_start_shift_seconds=_integer(
                        stability.get("absolute_start_shift_seconds"),
                        "absolute_start_shift_seconds",
                    ),
                    unchanged_existing=numerator,
                    comparable_existing=denominator,
                    unchanged_ratio=unchanged_ratio,
                ),
                "affected_orders": affected_orders,
                "operations": page_operations,
                "query": selected_query,
                "page": PageInfo(
                    offset=selected_query.offset,
                    limit=selected_query.limit,
                    returned=len(page_operations),
                    filtered_total=len(filtered),
                    unfiltered_total=universe,
                    has_more=(
                        page_start + len(page_operations) < len(filtered)
                    ),
                ),
                "provenance": ComparisonProvenance(
                    attempt_id=attempt_id,
                    result_id=_text(
                        after_package.replan_result.get("result_id"), "result_id"
                    ),
                    result_fingerprint=_text(
                        after_package.replan_result.get("result_fingerprint"),
                        "result_fingerprint",
                    ),
                    change_report=_reference_view(report_reference),
                    before_kpi=_reference_view(before_kpi_reference),
                    after_kpi=_reference_view(after_kpi_reference),
                    validation_status="PASS",
                ),
                "boundary": _boundary(
                    _text(after_package.schedule.get("environment"), "environment")
                ),
            }
            return cast(
                DemoComparisonView,
                _finalize(DemoComparisonView, document),
            )
        finally:
            database.close()


def presentation_contract_schemas() -> dict[str, dict[str, Any]]:
    """Return the three generated strict JSON Schemas for contract tests."""

    return {
        "cnc-demo-factory-view.v1": DemoFactoryView.model_json_schema(),
        "cnc-demo-schedule-view.v1": DemoScheduleView.model_json_schema(),
        "cnc-demo-comparison-view.v1": DemoComparisonView.model_json_schema(),
    }


__all__ = [
    "ComparisonPresentationQuery",
    "DemoComparisonView",
    "DemoFactoryView",
    "DemoPresentationService",
    "DemoScheduleView",
    "SchedulePresentationQuery",
    "presentation_contract_schemas",
]
