"""TASK-P3-05 pure workspace projection and query tests."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from app.application.schedule_comparison import ScheduleComparisonService
from app.application.schedule_version_lifecycle_check import lifecycle_context
from app.application.workspace_queries import WorkspaceQueryService
from app.application.workspace_read_model_check import (
    load_read_model_fixtures,
    sources_for,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace import (
    WorkspaceReadError,
    WorkspaceReadFailure,
    WorkspaceSourceDocuments,
    WorkspaceView,
    bind_workspace_sources,
    build_workspace_projections,
    build_workspace_query_request,
    version_reference,
)
from app.domain.workspace_contracts import workspace_fingerprint


ROOT = Path(__file__).resolve().parents[3]
TEST_WORKSPACE_READ_MODEL_ID = "TEST-WORKSPACE-READ-MODEL-001"


class _ScheduleRepository:
    def __init__(self, *documents: Mapping[str, object]) -> None:
        self.documents = {
            cast(str, document["schedule_version_id"]): dict(document)
            for document in documents
        }

    def get(self, schedule_version_id: str) -> dict[str, object] | None:
        document = self.documents.get(schedule_version_id)
        return dict(document) if document is not None else None


class _AuditRepository:
    def __init__(self, *events: Mapping[str, object]) -> None:
        self.events = tuple(dict(event) for event in events)

    def list_for_aggregate(
        self, *, aggregate_type: str, aggregate_id: str
    ) -> tuple[dict[str, object], ...]:
        return tuple(
            event
            for event in self.events
            if event["aggregate_type"] == aggregate_type
            and event["aggregate_id"] == aggregate_id
        )


@dataclass(frozen=True)
class _Artifacts:
    sources: WorkspaceSourceDocuments
    schedule: dict[str, object]
    audit: dict[str, object]
    compared_sources: WorkspaceSourceDocuments
    compared_schedule: dict[str, object]


@pytest.fixture(scope="module")
def artifacts() -> _Artifacts:
    (base_output, _), (compared_output, _) = load_read_model_fixtures(ROOT)
    base = build_reviewable_schedule_documents(
        base_output, lifecycle_context("a"), data_plane="SIMULATION"
    )
    compared = build_reviewable_schedule_documents(
        compared_output,
        lifecycle_context(
            "b",
            reason="Create a second immutable synthetic Version for comparison.",
            correlation_id="correlation-p3-05-compared-version",
        ),
        data_plane="SIMULATION",
    )
    return _Artifacts(
        sources=sources_for(base_output),
        schedule=base.ready_for_review,
        audit=base.audit_event,
        compared_sources=sources_for(compared_output),
        compared_schedule=compared.ready_for_review,
    )


def _request(
    view: WorkspaceView,
    artifacts: _Artifacts,
    *,
    reference: Mapping[str, object] | None = None,
    filters: Mapping[str, object] | None = None,
) -> dict[str, object]:
    workspace_views = {
        WorkspaceView.DATA_HEALTH,
        WorkspaceView.IMPORT_RUNS,
        WorkspaceView.PLANNING_RUNS,
    }
    return build_workspace_query_request(
        view=view,
        data_plane="SIMULATION",
        environment="TEST",
        synthetic=True,
        correlation_id=f"correlation-unit-{view.value.lower().replace('_', '-')}",
        schedule_version_reference=None
        if view in workspace_views
        else (reference or version_reference(artifacts.schedule)),
        synthetic_provenance=cast(
            Mapping[str, object], artifacts.sources.snapshot["synthetic_provenance"]
        ),
        filters=filters,
    )


def _service(artifacts: _Artifacts) -> WorkspaceQueryService:
    return WorkspaceQueryService(
        data_plane="SIMULATION",
        schedule_repository=_ScheduleRepository(
            artifacts.schedule, artifacts.compared_schedule
        ),
        audit_repository=_AuditRepository(artifacts.audit),
    )


def test_all_p3_read_models_are_bound_to_exact_authoritative_facts(
    artifacts: _Artifacts,
) -> None:
    bound = bind_workspace_sources(
        artifacts.schedule, artifacts.sources, expected_data_plane="SIMULATION"
    )
    expected_types = {
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
    }
    for view, expected_type in expected_types.items():
        projections = build_workspace_projections(
            view,
            sources=artifacts.sources,
            schedule_version=artifacts.schedule,
            bound=bound,
            audit_events=(artifacts.audit,),
        )
        assert all(item.item_type == expected_type for item in projections)
        assert all(
            item.payload_fingerprint == workspace_fingerprint(item.payload)
            for item in projections
        )
    assert TEST_WORKSPACE_READ_MODEL_ID == "TEST-WORKSPACE-READ-MODEL-001"


def test_resource_load_is_the_exact_sum_of_schedule_assignments(
    artifacts: _Artifacts,
) -> None:
    result = _service(artifacts).query(
        _request(WorkspaceView.RESOURCE_LOAD, artifacts),
        sources=artifacts.sources,
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    actual = {
        cast(str, item.payload["resource_id"]): item.payload["planned_busy_seconds"]
        for item in result.items
    }
    expected: dict[str, int] = {}
    for assignment in cast(
        list[Mapping[str, object]], artifacts.sources.solution["assignments"]
    ):
        resource_id = cast(str, assignment["resource_id"])
        expected[resource_id] = expected.get(resource_id, 0) + cast(
            int, assignment["duration_seconds"]
        )
    assert actual == expected


def test_found_empty_missing_and_stale_are_distinct(artifacts: _Artifacts) -> None:
    service = _service(artifacts)
    empty = service.query(
        _request(WorkspaceView.LOCKS, artifacts),
        sources=artifacts.sources,
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    missing_ref = {
        "schedule_version_id": "schedule-version-missing-unit",
        "state": "READY_FOR_REVIEW",
        "content_fingerprint": f"sha256:{'f' * 64}",
    }
    missing = service.query(
        _request(WorkspaceView.OPERATIONS, artifacts, reference=missing_ref),
        sources=artifacts.sources,
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    stale_ref = dict(version_reference(artifacts.schedule))
    stale_ref["state"] = "DRAFT"
    with pytest.raises(WorkspaceReadError) as raised:
        service.query(
            _request(WorkspaceView.OPERATIONS, artifacts, reference=stale_ref),
            sources=artifacts.sources,
            generated_at_utc="2026-08-24T08:00:00Z",
        )
    assert empty.found and empty.items == ()
    assert not missing.found
    assert raised.value.reason is WorkspaceReadFailure.STALE_VERSION


def test_workspace_scoped_view_rejects_an_intrinsically_mixed_source_set(
    artifacts: _Artifacts,
) -> None:
    tampered_kpi = cast(dict[str, object], deepcopy(artifacts.sources.kpi))
    inputs = cast(dict[str, object], tampered_kpi["inputs"])
    problem = cast(dict[str, object], inputs["problem"])
    problem["problem_hash"] = f"sha256:{'e' * 64}"
    with pytest.raises(WorkspaceReadError) as raised:
        _service(artifacts).query(
            _request(WorkspaceView.DATA_HEALTH, artifacts),
            sources=WorkspaceSourceDocuments(
                snapshot=artifacts.sources.snapshot,
                problem=artifacts.sources.problem,
                solution=artifacts.sources.solution,
                solver_report=artifacts.sources.solver_report,
                validation_report=artifacts.sources.validation_report,
                import_quality_report=artifacts.sources.import_quality_report,
                kpi=tampered_kpi,
            ),
            generated_at_utc="2026-08-24T08:00:00Z",
        )
    assert raised.value.reason is WorkspaceReadFailure.MIXED_LINEAGE


def test_comparison_replays_and_contains_no_p4_change_report(
    artifacts: _Artifacts,
) -> None:
    repository = _ScheduleRepository(artifacts.schedule, artifacts.compared_schedule)
    service = ScheduleComparisonService(
        data_plane="SIMULATION", schedule_repository=repository
    )
    request = _request(WorkspaceView.VERSION_COMPARISON, artifacts)
    first = service.compare(
        request,
        compared_version_precondition=version_reference(artifacts.compared_schedule),
        base_sources=artifacts.sources,
        compared_sources=artifacts.compared_sources,
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    second = service.compare(
        request,
        compared_version_precondition=version_reference(artifacts.compared_schedule),
        base_sources=artifacts.sources,
        compared_sources=artifacts.compared_sources,
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    assert first == second
    assert first.query.items[0].payload == first.comparison
    assert "change_report" not in first.comparison
    assert "replan" not in first.comparison
    assert service.solver_invocations == 0
