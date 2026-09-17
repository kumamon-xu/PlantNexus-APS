"""Runtime read composition over durable, explicitly authorized source sets."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from typing import Any, cast, NoReturn

from app.application.schedule_comparison import ScheduleComparisonService
from app.application.workspace_queries import (
    WorkspaceQueryService,
    build_workspace_query_result,
)
from app.domain.workspace import (
    WorkspaceSourceDocuments,
    paginate_workspace_projections,
    parse_workspace_query,
    WorkspaceReadError,
    WorkspaceReadFailure,
    WorkspaceProjection,
    WorkspaceView,
)
from app.domain.workspace_contracts import workspace_fingerprint


def reject(reason: WorkspaceReadFailure, field: str) -> NoReturn:
    raise WorkspaceReadError(
        reason,
        field=field,
        message="Runtime read source is unavailable or inconsistent",
    )


def in_scope(scope: frozenset[str], identity: str) -> bool:
    return "*" in scope or identity in scope


class RuntimeWorkspaceReads:
    def __init__(
        self,
        *,
        queries: WorkspaceQueryService,
        comparisons: ScheduleComparisonService,
        schedules: Any,
        sources: Callable[[str, Mapping[str, object] | None], WorkspaceSourceDocuments],
        run_ids: Callable[[], Sequence[str]],
        read_run: Callable[[str], Any],
        read_ingress: Callable[[str], Any],
    ) -> None:
        self._queries, self._comparisons, self._schedules = (
            queries,
            comparisons,
            schedules,
        )
        self._sources, self._run_ids, self._read_run = sources, run_ids, read_run
        self._read_ingress = read_ingress

    def _catalog(self, run_id: str, spec: Any, document: Any) -> WorkspaceProjection:
        record, model = self._read_ingress(run_id), self._read_run(run_id)
        if record is None or model is None:
            reject(WorkspaceReadFailure.SOURCE_MISSING, "catalog.source")
        snapshot = record.snapshot.document
        if any(
            document.get(key) != snapshot.get(key)
            for key in ("synthetic", "synthetic_provenance")
        ):
            reject(WorkspaceReadFailure.MIXED_LINEAGE, "catalog.provenance")
        quality, package = (
            record.document["import_quality_report"],
            snapshot["import_package"],
        )
        if spec.view is WorkspaceView.PLANNING_RUNS:
            payload = {
                "planning_run_id": run_id,
                "state": model.aggregate.document["state"],
                "revision": model.aggregate.document["revision"],
                "snapshot_id": snapshot["snapshot_id"],
                "prepared_artifacts": model.aggregate.prepared_artifacts,
            }
            identity, kind = run_id, "PLANNING_RUN"
        elif spec.view is WorkspaceView.IMPORT_RUNS:
            payload = {
                "import_run_id": quality["report_id"],
                "import_package_id": package["package_id"],
                "import_package_version": package["import_package_version"],
                "dataset_hash": package["dataset_hash"],
                "status": quality["status"],
                "error_count": quality["error_count"],
                "source_versions": snapshot["source_versions"],
                "snapshot_id": snapshot["snapshot_id"],
                "snapshot_hash": snapshot["snapshot_hash"],
            }
            identity, kind = quality["report_id"], "IMPORT_RUN"
        else:
            payload = {
                "snapshot_id": snapshot["snapshot_id"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "cutoff_at_utc": snapshot["cutoff_at_utc"],
                "import_package_id": package["package_id"],
                "dataset_hash": package["dataset_hash"],
                "quality_report_id": quality["report_id"],
                "quality_status": quality["status"],
                "quality_error_count": quality["error_count"],
                "entity_counts": snapshot["entity_counts"],
                "source_versions": snapshot["source_versions"],
                "synthetic": snapshot["synthetic"],
            }
            identity, kind = (
                "data-health-" + workspace_fingerprint(payload).removeprefix("sha256:"),
                "DATA_HEALTH",
            )
        return WorkspaceProjection(
            identity, kind, payload, workspace_fingerprint(payload)
        )

    def version_sources(
        self, version: Mapping[str, object]
    ) -> WorkspaceSourceDocuments:
        lineage = version.get("lineage")
        if not isinstance(lineage, Mapping) or not isinstance(
            lineage.get("planning_run_id"), str
        ):
            reject(WorkspaceReadFailure.MIXED_LINEAGE, "source.lineage")
        return self._sources(cast(Any, lineage)["planning_run_id"], version)

    @staticmethod
    def _authorized(request: Any, identity: str, *, run: bool = False) -> None:
        scope = (
            request.context.planning_run_scope
            if run
            else request.context.schedule_version_scope
        )
        if not in_scope(scope, identity):
            # Match the facade's existing sanitized authorization boundary.
            from app.application.runtime_planning_workspace import (
                RuntimePlanningWorkspaceError,
            )

            raise RuntimePlanningWorkspaceError(
                "AUTHORIZATION_DENIED", field="resource_scope"
            )

    @staticmethod
    def _response(result: Any, request: Any) -> dict[str, object]:
        response = asdict(result)
        carrier = response["document"]["result"]
        carrier["allowed_actions"] = [
            action
            for action in carrier["allowed_actions"]
            if action in request.context.resolved_capabilities
        ]
        response["correlation_id"] = request.context.correlation_id
        return response

    def query(self, request: Any) -> Mapping[str, object]:
        document = request.document
        spec = parse_workspace_query(document)
        if (
            spec.environment != request.context.environment
            or spec.data_plane != request.context.data_plane
        ):
            reject(WorkspaceReadFailure.DATA_PLANE_MISMATCH, "query.context")
        if spec.resource_type == "SCHEDULE_VERSION":
            identity = cast(str, spec.resource_id)
            self._authorized(request, identity)
            version = self._schedules.get(identity)
            if version is None:
                from app.application.workspace_queries import _empty_result

                return self._response(
                    _empty_result(
                        document, generated_at_utc=request.context.occurred_at_utc
                    ),
                    request,
                )
            result = self._queries.query(
                document,
                sources=self.version_sources(version),
                generated_at_utc=request.context.occurred_at_utc,
            )
            return self._response(result, request)
        projections = []
        fingerprints = []
        for run_id in self._run_ids():
            if not in_scope(request.context.planning_run_scope, run_id):
                continue
            item = self._catalog(run_id, spec, document)
            fingerprints.append(item.payload_fingerprint)
            projections.append(item)
        # Multiple runs can refer to the same immutable import/snapshot projection.
        unique: dict[str, WorkspaceProjection] = {}
        for item in projections:
            if item.item_id in unique and unique[item.item_id] != item:
                reject(WorkspaceReadFailure.MIXED_LINEAGE, "catalog.identity")
            unique[item.item_id] = item
        source_fingerprint = workspace_fingerprint({"sources": sorted(fingerprints)})
        page = paginate_workspace_projections(
            tuple(unique.values()),
            spec,
            schedule_state=None,
            source_fingerprint=source_fingerprint,
        )
        return self._response(
            build_workspace_query_result(
                document,
                page_items=page.items,
                next_cursor=page.next_cursor,
                observed_count=page.observed_count,
                generated_at_utc=request.context.occurred_at_utc,
                source_fingerprint=source_fingerprint,
                collection_fingerprint=page.collection_fingerprint,
                schedule_version=None,
            ),
            request,
        )

    def compare(self, request: Any) -> Mapping[str, object]:
        spec = parse_workspace_query(request.document)
        if (
            spec.environment != request.context.environment
            or spec.data_plane != request.context.data_plane
        ):
            reject(WorkspaceReadFailure.DATA_PLANE_MISMATCH, "query.context")
        base_id = request.resource_id
        compared_id = request.compared_version_precondition["schedule_version_id"]
        for identity in (base_id, compared_id):
            self._authorized(request, identity)
        base, compared = self._schedules.get(base_id), self._schedules.get(compared_id)
        if base is None or compared is None:
            reject(WorkspaceReadFailure.SOURCE_MISSING, "schedule_version")
        result = self._comparisons.compare(
            request.document,
            compared_version_precondition=request.compared_version_precondition,
            base_sources=self.version_sources(base),
            compared_sources=self.version_sources(compared),
            generated_at_utc=request.context.occurred_at_utc,
        )
        return {
            **self._response(result.query, request),
            "comparison": result.comparison,
        }

    def planning_run(self, request: Any) -> Mapping[str, object]:
        self._authorized(request, request.resource_id, run=True)
        self._read_ingress(request.resource_id)
        model = self._read_run(request.resource_id)
        if model is None:
            reject(WorkspaceReadFailure.SOURCE_MISSING, "planning_run")
        # The old workspace summary remains distinct from planning-run.v1 /status.
        document = model.aggregate.document
        return {
            "planning_run": {
                "planning_run_id": document["planning_run_id"],
                "state": document["state"],
                "revision": document["revision"],
                "prepared_artifacts": dict(model.aggregate.prepared_artifacts),
            },
            "correlation_id": request.context.correlation_id,
        }
