"""TASK-P3-10 baseline plus TASK-P3-13 additive download API evidence."""

from __future__ import annotations

from typing import cast

from app.api.app import create_app
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


EXPECTED_OPERATIONS = {
    "getPlanningRun",
    "getScheduleVersion",
    "validateScheduleVersion",
    "approveScheduleVersion",
    "rejectScheduleVersion",
    "publishScheduleVersion",
    "getWorkspaceDataHealth",
    "listWorkspaceImportRuns",
    "listWorkspacePlanningRuns",
    "queryScheduleVersionWorkspace",
    "compareScheduleVersions",
    "executeScheduleVersionCommand",
    "listScheduleVersionAuditEvents",
    "createScheduleVersionExport",
    "getExportJob",
    "downloadExportPackage",
    "retryExportJob",
    "cancelExportJob",
}


def _openapi() -> dict[str, object]:
    application = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
    )
    return application.openapi()


def test_openapi_has_exact_p3_route_and_operation_inventory() -> None:
    document = _openapi()
    paths = cast(dict[str, dict[str, object]], document["paths"])
    api_paths = {
        path: value for path, value in paths.items() if path.startswith("/api/v1/")
    }
    operations = {
        cast(str, operation["operationId"])
        for path, value in api_paths.items()
        for method, operation in value.items()
        if path.startswith("/api/v1/")
        and method in {"get", "post"}
        and isinstance(operation, dict)
    }

    assert len(api_paths) == 18
    assert operations == EXPECTED_OPERATIONS
    assert not any("replan" in path or "execution-event" in path for path in api_paths)
    assert "/openapi.json" not in paths


def test_openapi_references_frozen_carriers_and_public_error_model() -> None:
    first = _openapi()
    second = _openapi()
    assert first == second
    paths = cast(dict[str, dict[str, object]], first["paths"])

    command = cast(
        dict[str, object],
        paths["/api/v1/schedule-versions/{schedule_version_id}/commands"]["post"],
    )
    query = cast(dict[str, object], paths["/api/v1/workspace/data-health"]["get"])
    download = cast(
        dict[str, object],
        paths["/api/v1/export-jobs/{export_job_id}/download"]["get"],
    )
    assert command["x-plantnexus-api-contract"] == "planning-workspace-http.v1"
    assert command["x-plantnexus-request-contract"] == "workspace-command.v1"
    assert command["x-plantnexus-idempotency-binding"] == (
        "Idempotency-Key header equals body"
    )
    assert query["x-plantnexus-request-contract"] == "workspace-query.v1"
    assert query["x-plantnexus-query-serialization"] == (
        "url-encoded canonical JSON query parameter"
    )
    assert download["x-plantnexus-response-contract"] == (
        "export-manifest.v2 verified archive"
    )
    assert download["x-plantnexus-download-boundary"] == (
        "SIMULATION_INTERNAL EXPORTED only"
    )
    download_responses = cast(dict[str, dict[str, object]], download["responses"])
    assert "application/zip" in cast(
        dict[str, object], download_responses["200"]["content"]
    )
    for operation in (command, query, download):
        responses = cast(dict[str, dict[str, object]], operation["responses"])
        for status in ("401", "403", "404", "409", "422", "500", "503"):
            schema = cast(
                dict[str, object],
                cast(
                    dict[str, object],
                    cast(dict[str, object], responses[status]["content"])[
                        "application/json"
                    ],
                )["schema"],
            )
            assert schema["$ref"] == (
                "#/components/schemas/PlanningWorkspaceErrorEnvelope"
            )
