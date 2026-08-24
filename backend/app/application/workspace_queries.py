"""Read-only P3 workspace query application service.

The strict query document is a transport carrier.  ``WorkspaceQueryResult``
keeps the complete projection payloads next to that carrier so adapters can
render a page without weakening the published Schema.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Never, Protocol, cast

from app.domain.types import parse_utc_instant
from app.domain.workspace import (
    WorkspaceProjection,
    WorkspaceReadError,
    WorkspaceReadFailure,
    WorkspaceSourceDocuments,
    bind_workspace_sources,
    build_workspace_projections,
    paginate_workspace_projections,
    parse_workspace_query,
    require_query_precondition,
    require_workspace_sources,
    version_reference,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    require_workspace_document,
)


class ScheduleVersionReadRepositoryPort(Protocol):
    def get(self, schedule_version_id: str) -> dict[str, object] | None: ...


class AuditReadRepositoryPort(Protocol):
    def list_for_aggregate(
        self, *, aggregate_type: str, aggregate_id: str
    ) -> tuple[dict[str, object], ...]: ...


@dataclass(frozen=True, slots=True)
class WorkspaceQueryResult:
    """Strict result carrier plus the complete payload page it references."""

    document: dict[str, object]
    items: tuple[WorkspaceProjection, ...]
    collection_fingerprint: str | None
    source_fingerprint: str | None

    @property
    def found(self) -> bool:
        result = self.document.get("result")
        return isinstance(result, Mapping) and result.get("found") is True


def workspace_source_fingerprint(sources: WorkspaceSourceDocuments) -> str:
    """Bind all seven immutable P1/P2 source documents in a stable order."""

    return require_workspace_sources(sources)


def require_query_source_context(
    request: Mapping[str, object],
    sources: WorkspaceSourceDocuments,
    *,
    schedule_version: Mapping[str, object] | None = None,
) -> None:
    """Keep carrier provenance aligned with the immutable source authority."""

    synthetic = sources.snapshot.get("synthetic")
    if not isinstance(synthetic, bool) or request.get("synthetic") is not synthetic:
        _reject(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="synthetic",
            message="query synthetic flag differs from the immutable source set",
        )
    if synthetic:
        provenance = sources.snapshot.get("synthetic_provenance")
        if request.get("synthetic_provenance") != provenance:
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="synthetic_provenance",
                message="query provenance differs from the immutable source set",
            )
    if schedule_version is not None:
        require_schedule_source_context(schedule_version, sources)


def require_schedule_source_context(
    schedule_version: Mapping[str, object], sources: WorkspaceSourceDocuments
) -> None:
    synthetic = sources.snapshot.get("synthetic")
    if schedule_version.get("synthetic") is not synthetic:
        _reject(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="schedule_version.synthetic",
            message="Version synthetic flag differs from its immutable sources",
        )
    if synthetic is True and schedule_version.get("synthetic_provenance") != (
        sources.snapshot.get("synthetic_provenance")
    ):
        _reject(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="schedule_version.synthetic_provenance",
            message="Version provenance differs from its immutable sources",
        )


def _clone(document: Mapping[str, object]) -> dict[str, object]:
    import json

    return cast(dict[str, object], json.loads(canonical_workspace_bytes(document)))


def _reject(reason: WorkspaceReadFailure, *, field: str, message: str) -> Never:
    raise WorkspaceReadError(reason, field=field, message=message)


def _validate_generated_at(generated_at_utc: str) -> None:
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


def _empty_result(
    request: Mapping[str, object], *, generated_at_utc: str
) -> WorkspaceQueryResult:
    document = _clone(request)
    document["direction"] = "RESULT"
    document["result"] = {
        "result_version": "workspace-query-result.v1",
        "found": False,
        "authoritative_schedule_version": None,
        "lineage": None,
        "items": [],
        "next_cursor": None,
        "observed_count": 0,
        "allowed_actions": [],
        "freshness": "FRESH",
        "generated_at_utc": generated_at_utc,
    }
    require_workspace_document(document)
    return WorkspaceQueryResult(
        document=document,
        items=(),
        collection_fingerprint=None,
        source_fingerprint=None,
    )


def build_workspace_query_result(
    request: Mapping[str, object],
    *,
    page_items: Sequence[WorkspaceProjection],
    next_cursor: str | None,
    observed_count: int,
    generated_at_utc: str,
    source_fingerprint: str,
    collection_fingerprint: str,
    schedule_version: Mapping[str, object] | None,
) -> WorkspaceQueryResult:
    """Create an exact RESULT carrier for a previously parsed request."""

    document = _clone(request)
    document["direction"] = "RESULT"
    if schedule_version is None:
        authoritative = None
        lineage = None
        allowed_actions: list[object] = []
    else:
        authoritative = version_reference(schedule_version)
        raw_lineage = schedule_version.get("lineage")
        if not isinstance(raw_lineage, Mapping):
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="schedule_version.lineage",
                message="authoritative Version lineage is absent",
            )
        lineage = _clone(cast(Mapping[str, object], raw_lineage))
        raw_actions = schedule_version.get("allowed_actions")
        if not isinstance(raw_actions, list) or any(
            not isinstance(action, str) for action in raw_actions
        ):
            _reject(
                WorkspaceReadFailure.MIXED_LINEAGE,
                field="schedule_version.allowed_actions",
                message="authoritative Version actions are invalid",
            )
        allowed_actions = list(cast(list[str], raw_actions))
    document["result"] = {
        "result_version": "workspace-query-result.v1",
        "found": True,
        "authoritative_schedule_version": authoritative,
        "lineage": lineage,
        "items": [item.carrier_reference for item in page_items],
        "next_cursor": next_cursor,
        "observed_count": observed_count,
        "allowed_actions": allowed_actions,
        "freshness": "FRESH",
        "generated_at_utc": generated_at_utc,
    }
    try:
        require_workspace_document(document)
    except (TypeError, ValueError) as error:
        raise WorkspaceReadError(
            WorkspaceReadFailure.MIXED_LINEAGE,
            field="query_result",
            message="constructed result failed its strict P3 carrier",
        ) from error
    return WorkspaceQueryResult(
        document=document,
        items=tuple(page_items),
        collection_fingerprint=collection_fingerprint,
        source_fingerprint=source_fingerprint,
    )


class WorkspaceQueryService:
    """Project immutable facts without repository writes or Solver execution."""

    def __init__(
        self,
        *,
        data_plane: str,
        schedule_repository: ScheduleVersionReadRepositoryPort,
        audit_repository: AuditReadRepositoryPort,
    ) -> None:
        self._data_plane = data_plane
        self._schedule_repository = schedule_repository
        self._audit_repository = audit_repository

    @property
    def data_plane(self) -> str:
        return self._data_plane

    @property
    def solver_invocations(self) -> int:
        """Boundary evidence: this service has no Solver port to invoke."""

        return 0

    def query(
        self,
        request: Mapping[str, object],
        *,
        sources: WorkspaceSourceDocuments,
        generated_at_utc: str,
    ) -> WorkspaceQueryResult:
        _validate_generated_at(generated_at_utc)
        spec = parse_workspace_query(request)
        if spec.data_plane != self._data_plane:
            _reject(
                WorkspaceReadFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="query cannot cross the configured repository plane",
            )

        schedule_version: dict[str, object] | None = None
        audit_events: Sequence[Mapping[str, object]] = ()
        bound = None
        if spec.resource_type == "SCHEDULE_VERSION":
            assert spec.resource_id is not None
            schedule_version = self._schedule_repository.get(spec.resource_id)
            if schedule_version is None:
                return _empty_result(request, generated_at_utc=generated_at_utc)
            if schedule_version.get("data_plane") != self._data_plane:
                _reject(
                    WorkspaceReadFailure.DATA_PLANE_MISMATCH,
                    field="schedule_version.data_plane",
                    message="authoritative Version belongs to another data plane",
                )
            require_query_precondition(spec, schedule_version)
            bound = bind_workspace_sources(
                schedule_version,
                sources,
                expected_data_plane=self._data_plane,
            )
            require_query_source_context(
                request, sources, schedule_version=schedule_version
            )
            if spec.view.value == "AUDIT":
                audit_events = self._audit_repository.list_for_aggregate(
                    aggregate_type="SCHEDULE_VERSION",
                    aggregate_id=spec.resource_id,
                )

        source_fingerprint = workspace_source_fingerprint(sources)
        if schedule_version is None:
            require_query_source_context(request, sources)
        projections = build_workspace_projections(
            spec.view,
            sources=sources,
            schedule_version=schedule_version,
            bound=bound,
            audit_events=audit_events,
        )
        page = paginate_workspace_projections(
            projections,
            spec,
            schedule_state=(
                str(schedule_version["state"]) if schedule_version is not None else None
            ),
            source_fingerprint=source_fingerprint,
        )
        return build_workspace_query_result(
            request,
            page_items=page.items,
            next_cursor=page.next_cursor,
            observed_count=page.observed_count,
            generated_at_utc=generated_at_utc,
            source_fingerprint=source_fingerprint,
            collection_fingerprint=page.collection_fingerprint,
            schedule_version=schedule_version,
        )


__all__ = [
    "AuditReadRepositoryPort",
    "ScheduleVersionReadRepositoryPort",
    "WorkspaceQueryResult",
    "WorkspaceQueryService",
    "build_workspace_query_result",
    "require_query_source_context",
    "require_schedule_source_context",
    "workspace_source_fingerprint",
]
