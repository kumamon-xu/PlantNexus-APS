"""Deterministic P3 comparison of two immutable ScheduleVersions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Never, cast

from app.application.workspace_queries import (
    ScheduleVersionReadRepositoryPort,
    WorkspaceQueryResult,
    build_workspace_query_result,
    require_query_source_context,
    require_schedule_source_context,
    workspace_source_fingerprint,
)
from app.domain.workspace import (
    WorkspaceReadError,
    WorkspaceReadFailure,
    WorkspaceSourceDocuments,
    WorkspaceView,
    bind_workspace_sources,
    build_schedule_version_comparison,
    build_workspace_projections,
    comparison_query_fingerprint,
    paginate_workspace_projections,
    parse_workspace_query,
    require_query_precondition,
    version_reference,
)
from app.domain.workspace_contracts import workspace_fingerprint


@dataclass(frozen=True, slots=True)
class ScheduleComparisonResult:
    comparison: dict[str, object]
    query: WorkspaceQueryResult


def _reject(reason: WorkspaceReadFailure, *, field: str, message: str) -> Never:
    raise WorkspaceReadError(reason, field=field, message=message)


class ScheduleComparisonService:
    """Read and compare two Versions; never produce a P4 ChangeReport."""

    def __init__(
        self,
        *,
        data_plane: str,
        schedule_repository: ScheduleVersionReadRepositoryPort,
    ) -> None:
        self._data_plane = data_plane
        self._schedule_repository = schedule_repository

    @property
    def solver_invocations(self) -> int:
        return 0

    def compare(
        self,
        request: Mapping[str, object],
        *,
        compared_version_precondition: Mapping[str, object],
        base_sources: WorkspaceSourceDocuments,
        compared_sources: WorkspaceSourceDocuments,
        generated_at_utc: str,
    ) -> ScheduleComparisonResult:
        spec = parse_workspace_query(request)
        if spec.view is not WorkspaceView.VERSION_COMPARISON:
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="view",
                message="comparison service requires VERSION_COMPARISON",
            )
        if spec.data_plane != self._data_plane:
            _reject(
                WorkspaceReadFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="comparison cannot cross the configured repository plane",
            )
        assert spec.resource_id is not None
        compared_id = compared_version_precondition.get("schedule_version_id")
        if not isinstance(compared_id, str) or not compared_id:
            _reject(
                WorkspaceReadFailure.INVALID_QUERY,
                field="compared_version_precondition.schedule_version_id",
                message="exact compared Version identity is required",
            )
        compared_id = cast(str, compared_id)
        base = self._schedule_repository.get(spec.resource_id)
        compared = self._schedule_repository.get(compared_id)
        if base is None or compared is None:
            missing = spec.resource_id if base is None else compared_id
            _reject(
                WorkspaceReadFailure.SOURCE_MISSING,
                field="schedule_version",
                message=f"required immutable Version is absent: {missing}",
            )
        if (
            base.get("data_plane") != self._data_plane
            or compared.get("data_plane") != self._data_plane
        ):
            _reject(
                WorkspaceReadFailure.DATA_PLANE_MISMATCH,
                field="schedule_version.data_plane",
                message="comparison cannot consume another repository plane",
            )
        require_query_precondition(spec, base)
        require_query_source_context(request, base_sources, schedule_version=base)
        require_schedule_source_context(compared, compared_sources)
        compared_reference = version_reference(compared)
        if any(
            compared_version_precondition.get(field) != value
            for field, value in compared_reference.items()
        ):
            _reject(
                WorkspaceReadFailure.STALE_VERSION,
                field="compared_version_precondition",
                message="compared Version state or fingerprint changed",
            )
        query_fingerprint = comparison_query_fingerprint(
            workspace_query_fingerprint_value=spec.query_fingerprint,
            base_schedule_version_id=spec.resource_id,
            compared_schedule_version_id=compared_id,
        )
        comparison = build_schedule_version_comparison(
            base_version=base,
            compared_version=compared,
            base_sources=base_sources,
            compared_sources=compared_sources,
            query_fingerprint=query_fingerprint,
            generated_at_utc=generated_at_utc,
        )
        base_bound = bind_workspace_sources(
            base, base_sources, expected_data_plane=self._data_plane
        )
        projections = build_workspace_projections(
            WorkspaceView.VERSION_COMPARISON,
            sources=base_sources,
            schedule_version=base,
            bound=base_bound,
            comparison=comparison,
        )
        source_fingerprint = workspace_fingerprint(
            {
                "comparison_source_set_version": "comparison-source-set.v1",
                "base": workspace_source_fingerprint(base_sources),
                "compared": workspace_source_fingerprint(compared_sources),
                "base_version": version_reference(base),
                "compared_version": compared_reference,
            }
        )
        page = paginate_workspace_projections(
            projections,
            spec,
            schedule_state=str(base["state"]),
            source_fingerprint=source_fingerprint,
        )
        query = build_workspace_query_result(
            request,
            page_items=page.items,
            next_cursor=page.next_cursor,
            observed_count=page.observed_count,
            generated_at_utc=generated_at_utc,
            source_fingerprint=source_fingerprint,
            collection_fingerprint=page.collection_fingerprint,
            schedule_version=base,
        )
        return ScheduleComparisonResult(comparison=comparison, query=query)


__all__ = ["ScheduleComparisonResult", "ScheduleComparisonService"]
