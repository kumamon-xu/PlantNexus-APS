"""TASK-P3-05 generated query/comparison documents honor frozen P3 Schemas."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
import json

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.application.schedule_comparison import ScheduleComparisonService
from app.application.schedule_version_lifecycle_check import lifecycle_context
from app.application.workspace_queries import WorkspaceQueryService
from app.application.workspace_read_model_check import (
    load_read_model_fixtures,
    sources_for,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace import (
    WorkspaceView,
    build_workspace_query_request,
    version_reference,
)
from app.domain.workspace_contracts import (
    comparison_fingerprint,
    workspace_query_fingerprint,
)


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"


def _validator(name: str) -> Draft202012Validator:
    resources: list[tuple[str, Resource[Any]]] = []
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.json")):
        schema = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


class _ScheduleRepository:
    def __init__(self, *documents: Mapping[str, object]) -> None:
        self.documents = {
            cast(str, value["schedule_version_id"]): dict(value) for value in documents
        }

    def get(self, schedule_version_id: str) -> dict[str, object] | None:
        value = self.documents.get(schedule_version_id)
        return dict(value) if value is not None else None


class _AuditRepository:
    def list_for_aggregate(
        self, *, aggregate_type: str, aggregate_id: str
    ) -> tuple[dict[str, object], ...]:
        return ()


def _fixture() -> tuple[object, ...]:
    (base_output, _), (compared_output, _) = load_read_model_fixtures(ROOT)
    base = build_reviewable_schedule_documents(
        base_output, lifecycle_context("a"), data_plane="SIMULATION"
    ).ready_for_review
    compared = build_reviewable_schedule_documents(
        compared_output,
        lifecycle_context(
            "b",
            reason="Create a second immutable synthetic Version for comparison.",
            correlation_id="correlation-p3-05-compared-version",
        ),
        data_plane="SIMULATION",
    ).ready_for_review
    return base_output, compared_output, base, compared


def _request(
    view: WorkspaceView, base_output: object, base: Mapping[str, object]
) -> dict[str, object]:
    sources = sources_for(cast(Any, base_output))
    return build_workspace_query_request(
        view=view,
        data_plane="SIMULATION",
        environment="TEST",
        synthetic=True,
        correlation_id=f"correlation-contract-{view.value.lower().replace('_', '-')}",
        schedule_version_reference=version_reference(base),
        synthetic_provenance=cast(
            Mapping[str, object], sources.snapshot["synthetic_provenance"]
        ),
    )


def test_generated_read_result_validates_without_embedding_payloads() -> None:
    base_output, _, base, compared = _fixture()
    base_mapping = cast(Mapping[str, object], base)
    repository = _ScheduleRepository(base_mapping, cast(Mapping[str, object], compared))
    request = _request(WorkspaceView.GANTT, base_output, base_mapping)
    result = WorkspaceQueryService(
        data_plane="SIMULATION",
        schedule_repository=repository,
        audit_repository=_AuditRepository(),
    ).query(
        request,
        sources=sources_for(cast(Any, base_output)),
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    _validator("workspace-query.schema.json").validate(result.document)
    body = cast(Mapping[str, object], result.document["result"])
    carrier_items = cast(list[Mapping[str, object]], body["items"])
    assert carrier_items
    assert all(
        set(item) == {"item_id", "item_type", "payload_fingerprint"}
        for item in carrier_items
    )
    assert result.document["query_fingerprint"] == workspace_query_fingerprint(
        result.document
    )


def test_generated_comparison_validates_and_remains_a_p3_read_dto() -> None:
    base_output, compared_output, base, compared = _fixture()
    base_mapping = cast(Mapping[str, object], base)
    compared_mapping = cast(Mapping[str, object], compared)
    repository = _ScheduleRepository(base_mapping, compared_mapping)
    result = ScheduleComparisonService(
        data_plane="SIMULATION", schedule_repository=repository
    ).compare(
        _request(WorkspaceView.VERSION_COMPARISON, base_output, base_mapping),
        compared_version_precondition=version_reference(compared_mapping),
        base_sources=sources_for(cast(Any, base_output)),
        compared_sources=sources_for(cast(Any, compared_output)),
        generated_at_utc="2026-08-24T08:00:00Z",
    )
    _validator("schedule-version-comparison.schema.json").validate(result.comparison)
    _validator("workspace-query.schema.json").validate(result.query.document)
    assert result.comparison["comparison_fingerprint"] == comparison_fingerprint(
        result.comparison
    )
    rendered = json.dumps(result.comparison, sort_keys=True).lower()
    assert "change_report" not in rendered
    assert "replan" not in rendered
