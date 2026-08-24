"""TASK-P3-05 stable replay, pagination, and filter properties."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import cast

from hypothesis import given, settings, strategies as st

from app.application.schedule_version_lifecycle_check import lifecycle_context
from app.application.workspace_queries import WorkspaceQueryService
from app.application.workspace_read_model_check import (
    load_read_model_fixtures,
    sources_for,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace import (
    WorkspaceSourceDocuments,
    WorkspaceView,
    build_workspace_query_request,
    version_reference,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_PROPERTY_ID = "TEST-PROPERTY"


class _ScheduleRepository:
    def __init__(self, document: Mapping[str, object]) -> None:
        self.document = dict(document)

    def get(self, schedule_version_id: str) -> dict[str, object] | None:
        if schedule_version_id != self.document["schedule_version_id"]:
            return None
        return dict(self.document)


class _AuditRepository:
    def list_for_aggregate(
        self, *, aggregate_type: str, aggregate_id: str
    ) -> tuple[dict[str, object], ...]:
        return ()


@lru_cache(maxsize=1)
def _artifacts() -> tuple[
    WorkspaceSourceDocuments, dict[str, object], WorkspaceQueryService
]:
    (output, _), _ = load_read_model_fixtures(ROOT)
    schedule = build_reviewable_schedule_documents(
        output, lifecycle_context("a"), data_plane="SIMULATION"
    ).ready_for_review
    sources = sources_for(output)
    return (
        sources,
        schedule,
        WorkspaceQueryService(
            data_plane="SIMULATION",
            schedule_repository=_ScheduleRepository(schedule),
            audit_repository=_AuditRepository(),
        ),
    )


def _query(
    *,
    page_size: int,
    direction: str,
    cursor: str | None,
    filters: Mapping[str, object] | None = None,
) -> dict[str, object]:
    sources, schedule, _ = _artifacts()
    return build_workspace_query_request(
        view=WorkspaceView.OPERATIONS,
        data_plane="SIMULATION",
        environment="TEST",
        synthetic=True,
        correlation_id="correlation-property-workspace-operations",
        schedule_version_reference=version_reference(schedule),
        synthetic_provenance=cast(
            Mapping[str, object], sources.snapshot["synthetic_provenance"]
        ),
        sort=({"field": "ITEM_ID", "direction": direction},),
        filters=filters,
        page_size=page_size,
        cursor=cursor,
    )


@settings(max_examples=16, deadline=None, derandomize=True)
@given(
    page_size=st.integers(min_value=1, max_value=4),
    direction=st.sampled_from(["ASC", "DESC"]),
)
def test_cursor_pages_are_complete_unique_and_exactly_replayable(
    page_size: int, direction: str
) -> None:
    sources, _, service = _artifacts()
    cursor: str | None = None
    observed: list[str] = []
    collection_fingerprint: str | None = None
    while True:
        result = service.query(
            _query(page_size=page_size, direction=direction, cursor=cursor),
            sources=sources,
            generated_at_utc="2026-08-24T08:00:00Z",
        )
        replay = service.query(
            _query(page_size=page_size, direction=direction, cursor=cursor),
            sources=sources,
            generated_at_utc="2026-08-24T08:00:00Z",
        )
        assert replay == result
        if collection_fingerprint is None:
            collection_fingerprint = result.collection_fingerprint
        assert result.collection_fingerprint == collection_fingerprint
        observed.extend(item.item_id for item in result.items)
        body = cast(Mapping[str, object], result.document["result"])
        cursor = cast(str | None, body["next_cursor"])
        if cursor is None:
            assert body["observed_count"] == len(observed)
            break
    assert len(observed) == len(set(observed)) == 4
    assert observed == sorted(observed, reverse=direction == "DESC")
    assert TEST_PROPERTY_ID == "TEST-PROPERTY"


@settings(max_examples=8, deadline=None, derandomize=True)
@given(resource_index=st.integers(min_value=0, max_value=1))
def test_resource_filter_never_leaks_another_resource(resource_index: int) -> None:
    sources, _, service = _artifacts()
    assignments = cast(list[Mapping[str, object]], sources.solution["assignments"])
    resource_ids = sorted({cast(str, value["resource_id"]) for value in assignments})
    selected = resource_ids[resource_index]
    filters = {
        "order_ids": [],
        "operation_ids": [],
        "resource_ids": [selected],
        "states": [],
        "start_at_or_after_utc": None,
        "start_before_utc": None,
    }
    result = service.query(
        _query(page_size=500, direction="ASC", cursor=None, filters=filters),
        sources=sources,
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    assert result.items
    assert {item.payload["resource_id"] for item in result.items} == {selected}
