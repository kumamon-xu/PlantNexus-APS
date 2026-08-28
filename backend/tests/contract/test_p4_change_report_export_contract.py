"""TASK-P4-11 consumer tests for frozen P4 export contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
import pytest
from referencing import Registry, Resource

from app.domain.execution_contracts import require_p4_document
from app.domain.export_job import (
    ExportJobError,
    ExportJobFailure,
    build_created_export_job,
    export_job_identity,
)
from app.domain.workspace_contracts import require_workspace_document
from app.exporters.change_report_output_check import (
    ChangeReportOutputFixture,
    build_change_report_output_fixture,
    build_fixture_package,
)
from app.exporters.standard_package import verify_standard_export_package


ROOT = Path(__file__).resolve().parents[3]


def _validator(name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((ROOT / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


@pytest.fixture(scope="module")
def fixture() -> ChangeReportOutputFixture:
    return build_change_report_output_fixture(ROOT)


def test_generated_manifest_job_schedule_and_report_validate_offline(
    fixture: ChangeReportOutputFixture,
) -> None:
    package = build_fixture_package(fixture)
    manifest = package.manifest
    assert require_p4_document(manifest) == "export-manifest.v3"
    assert require_p4_document(fixture.exporting_job) == "export-job.v3"
    assert require_p4_document(fixture.schedule_version) == "schedule-version.v2"
    assert require_p4_document(fixture.change_report) == "change-report.v1"
    _validator("export-manifest.v3.schema.json").validate(manifest)
    _validator("export-job.v3.schema.json").validate(fixture.exporting_job)
    _validator("schedule-version.v2.schema.json").validate(fixture.schedule_version)
    _validator("change-report.schema.json").validate(fixture.change_report)

    assert manifest["schedule_version"] == fixture.exporting_job["schedule_version"]
    assert manifest["change_report"] == fixture.exporting_job["change_report"]
    assert manifest["state_boundary"] == {
        "schedule_version": "PUBLISHED",
        "publication": "COMPLETED",
        "export_job_at_materialization": "EXPORTING",
        "external_transfer": "NOT_STARTED",
        "production": "NOT_AUTHORIZED",
    }


def test_p3_v2_job_and_package_consumer_remain_explicit_and_unchanged(
    fixture: ChangeReportOutputFixture,
) -> None:
    p3_package = cast(Any, fixture.p3_package)
    verify_standard_export_package(p3_package)
    publication = cast(
        dict[str, object], json.loads(p3_package.files["publication_result.json"])
    )
    request = replace(
        fixture.request,
        schedule_version_id=cast(str, fixture.p3_schedule["schedule_version_id"]),
        expected_content_fingerprint=cast(
            str, fixture.p3_schedule["content_fingerprint"]
        ),
        raw_idempotency_key="p3-byte-freeze-regression-key",
        synthetic_provenance=cast(
            dict[str, object], fixture.p3_schedule["synthetic_provenance"]
        ),
        change_report_reference=None,
    )
    context = replace(
        fixture.create_context,
        schedule_version_scope=frozenset({request.schedule_version_id}),
    )
    document = build_created_export_job(
        request,
        export_job_identity(request),
        context,
        fixture.p3_schedule,
        publication,
    )
    assert require_workspace_document(document) == "export-job.v2"
    assert document["schema_set_version"] == "2.7.0"
    assert document["package_profile"] == "p3-standard-export.v1"
    assert "change_report" not in document
    assert "schedule_version_version" not in cast(
        dict[str, object], document["schedule_version"]
    )


def test_v3_is_not_interchangeable_and_requires_exact_change_report_reference(
    fixture: ChangeReportOutputFixture,
) -> None:
    manifest = build_fixture_package(fixture).manifest
    pretending_v2 = deepcopy(manifest)
    pretending_v2["export_manifest_version"] = "export-manifest.v2"
    with pytest.raises(ValidationError):
        _validator("export-manifest.v3.schema.json").validate(pretending_v2)

    wrong_reference = {
        "change_report_version": "change-report.v1",
        "report_id": "change-report-not-content-addressed",
        "report_fingerprint": fixture.change_report["report_fingerprint"],
    }
    with pytest.raises(ExportJobError) as invalid:
        export_job_identity(
            replace(fixture.request, change_report_reference=wrong_reference)
        )
    assert invalid.value.reason is ExportJobFailure.INVALID_REQUEST

    stale_reference = deepcopy(cast(dict[str, object], fixture.created_job["change_report"]))
    stale_reference["report_fingerprint"] = "sha256:" + "f" * 64
    with pytest.raises(ExportJobError) as stale:
        build_created_export_job(
            replace(fixture.request, change_report_reference=stale_reference),
            export_job_identity(
                replace(fixture.request, change_report_reference=stale_reference)
            ),
            fixture.create_context,
            fixture.schedule_version,
            fixture.publication_result,
        )
    assert stale.value.reason is ExportJobFailure.STALE_SOURCE
