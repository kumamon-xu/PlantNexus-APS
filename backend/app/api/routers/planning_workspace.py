"""Thin FastAPI transport adapter for the P3 planning workspace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import re
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import APIRouter, Body, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.api.contracts import (
    API_CONTRACT_VERSION,
    API_PREFIX,
    PlanningWorkspaceApplicationError,
    PlanningWorkspaceApplicationPort,
    PlanningWorkspaceApplicationRequest,
    PlanningWorkspaceDownload,
    PlanningWorkspaceErrorEnvelope,
    PlanningWorkspaceHttpError,
    PlanningWorkspaceOperation,
    PlanningWorkspaceRequestContext,
    application_error_to_http,
    public_http_error,
    require_command_carrier,
    require_query_carrier,
)
from app.api.dependencies.authorization import (
    PrincipalContext,
    authorize_request,
    carrier_environment,
    carrier_plane,
)
from app.infrastructure.config import Settings


_CORRELATION = re.compile(r"[^\s\x00-\x1f\x7f]{1,256}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_DOWNLOAD_FILENAME = re.compile(r"[A-Za-z0-9._-]{1,192}\.zip")
_PACKAGE_ID = re.compile(r"export-package-[0-9a-f]{64}")
_VERSION_STATES = frozenset(
    {"DRAFT", "READY_FOR_REVIEW", "APPROVED", "PUBLISHED", "SUPERSEDED", "REJECTED"}
)
_SCHEDULE_VIEWS = frozenset(
    {
        "ORDERS",
        "OPERATIONS",
        "RESOURCES",
        "CALENDARS",
        "GANTT",
        "RESOURCE_LOAD",
        "KPI",
        "DIAGNOSTICS",
        "LOCKS",
        "AUDIT",
    }
)
_CONTENT_COMMANDS = (
    "MOVE_OPERATION",
    "ASSIGN_RESOURCE",
    "SET_LOCK",
    "REMOVE_LOCK",
    "SUBMIT_FOR_REVIEW",
)

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Authentication required",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    403: {
        "description": "Authorization denied",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    404: {"description": "Resource not found", "model": PlanningWorkspaceErrorEnvelope},
    409: {
        "description": "State, cursor, lease, or idempotency conflict",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    422: {
        "description": "Strict request or validation failure",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    500: {
        "description": "Sanitized system or export failure",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    503: {
        "description": "Application composition unavailable",
        "model": PlanningWorkspaceErrorEnvelope,
    },
}

_DOWNLOAD_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Verified internal Simulation standard export ZIP",
        "content": {"application/zip": {}},
        "headers": {
            "X-PlantNexus-Package-Id": {"schema": {"type": "string"}},
            "X-PlantNexus-Manifest-Fingerprint": {"schema": {"type": "string"}},
            "X-PlantNexus-Archive-Fingerprint": {"schema": {"type": "string"}},
            "X-PlantNexus-Completion-Audit-Event-Id": {"schema": {"type": "string"}},
        },
    },
    **_ERROR_RESPONSES,
}


router = APIRouter(prefix=API_PREFIX, tags=["planning-workspace"])


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_correlation() -> str:
    return f"correlation-http-{uuid4().hex}"


def _correlation(request: Request, document: Mapping[str, object] | None = None) -> str:
    header_value = request.headers.get("X-Correlation-Id")
    carrier_value = document.get("correlation_id") if document is not None else None
    candidate = header_value or (
        carrier_value if isinstance(carrier_value, str) else None
    )
    if candidate is None:
        return _new_correlation()
    if _CORRELATION.fullmatch(candidate) is None:
        raise public_http_error(
            "INVALID_REQUEST",
            correlation_id=_new_correlation(),
            field="X-Correlation-Id",
        )
    if (
        header_value is not None
        and isinstance(carrier_value, str)
        and carrier_value != header_value
    ):
        raise public_http_error(
            "INVALID_REQUEST",
            correlation_id=candidate,
            field="correlation_id",
        )
    return candidate


def _resource(resource_type: str, resource_id: str | None) -> dict[str, str]:
    result = {"resource_type": resource_type}
    if resource_id is not None:
        result["resource_id"] = resource_id
    return result


def _validated_query(
    request: Request,
    raw: str | Mapping[str, object],
    *,
    views: Sequence[str],
    schedule_version_id: str | None = None,
) -> tuple[dict[str, object], str]:
    try:
        document = require_query_carrier(
            raw,
            expected_views=views,
            schedule_version_id=schedule_version_id,
        )
        correlation_id = _correlation(request, document)
        _require_carrier_plane(request, document, correlation_id)
        return document, correlation_id
    except Exception as error:
        correlation_id = _correlation(request)
        raise application_error_to_http(
            error,
            correlation_id=correlation_id,
            resource=(
                _resource("SCHEDULE_VERSION", schedule_version_id)
                if schedule_version_id is not None
                else _resource("WORKSPACE", None)
            ),
        ) from None


def _validated_command(
    request: Request,
    document: Mapping[str, object],
    *,
    command_types: Sequence[str],
    source_id: str,
    idempotency_key: str,
    resource_type: str,
) -> tuple[dict[str, object], str, str]:
    try:
        result, capability = require_command_carrier(
            document,
            expected_command_types=command_types,
            source_id=source_id,
            idempotency_key=idempotency_key,
        )
        correlation_id = _correlation(request, result)
        _require_carrier_plane(request, result, correlation_id)
        return result, capability, correlation_id
    except Exception as error:
        correlation_id = _correlation(request)
        raise application_error_to_http(
            error,
            correlation_id=correlation_id,
            resource=_resource(resource_type, source_id),
        ) from None


def _require_carrier_plane(
    request: Request,
    document: Mapping[str, object],
    correlation_id: str,
) -> None:
    settings: Settings = request.app.state.settings
    try:
        expected_plane = carrier_plane(settings)
        expected_environment = carrier_environment(settings)
    except ValueError as error:
        raise application_error_to_http(
            PlanningWorkspaceApplicationError(
                "SERVICE_UNAVAILABLE",
                field="runtime_environment",
                message="workspace carrier environment is unavailable",
            ),
            correlation_id=correlation_id,
        ) from error
    if (
        document.get("data_plane") != expected_plane
        or document.get("environment") != expected_environment
    ):
        raise public_http_error(
            "DATA_PLANE_MISMATCH",
            correlation_id=correlation_id,
            field="data_plane/environment",
        )


def _context(
    request: Request,
    *,
    correlation_id: str,
    principal: PrincipalContext,
    idempotency_key: str | None,
) -> PlanningWorkspaceRequestContext:
    settings: Settings = request.app.state.settings
    clock = getattr(request.app.state, "planning_workspace_clock", _now)
    return PlanningWorkspaceRequestContext(
        correlation_id=correlation_id,
        actor_ref=principal.actor_ref,
        authenticated=True,
        resolved_capabilities=principal.resolved_capabilities,
        planning_run_scope=principal.planning_run_scope,
        schedule_version_scope=principal.schedule_version_scope,
        export_job_scope=principal.export_job_scope,
        auth_policy_version=principal.auth_policy_version,
        production_binding=principal.production_binding,
        occurred_at_utc=clock(),
        code_commit=settings.code_commit,
        data_plane=carrier_plane(settings),
        environment=carrier_environment(settings),
        idempotency_key=idempotency_key,
    )


def _invoke(
    request: Request,
    *,
    operation: PlanningWorkspaceOperation,
    correlation_id: str,
    capability: str,
    resource_type: str,
    resource_id: str | None = None,
    view: str | None = None,
    document: dict[str, object] | None = None,
    compared_version_precondition: dict[str, object] | None = None,
    additional_schedule_version_id: str | None = None,
    idempotency_key: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    try:
        principal = authorize_request(
            request,
            correlation_id=correlation_id,
            required_capability=capability,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if additional_schedule_version_id is not None:
            authorize_request(
                request,
                correlation_id=correlation_id,
                required_capability=capability,
                resource_type="SCHEDULE_VERSION",
                resource_id=additional_schedule_version_id,
            )
        application: PlanningWorkspaceApplicationPort = (
            request.app.state.planning_workspace_application
        )
        application_request = PlanningWorkspaceApplicationRequest(
            operation=operation,
            context=_context(
                request,
                correlation_id=correlation_id,
                principal=principal,
                idempotency_key=idempotency_key,
            ),
            resource_id=resource_id,
            view=view,
            document=document,
            compared_version_precondition=compared_version_precondition,
        )
        result = application.execute(application_request)
        if not isinstance(result, Mapping):
            raise PlanningWorkspaceApplicationError(
                "PERSISTENCE_FAILED",
                field="application_result",
                message="JSON operation returned a binary result",
            )
        payload = dict(result)
        result_correlation = payload.get("correlation_id")
        if result_correlation is None:
            payload["correlation_id"] = correlation_id
        elif result_correlation != correlation_id:
            raise PlanningWorkspaceApplicationError(
                "PERSISTENCE_FAILED",
                field="application_result.correlation_id",
                message="application result correlation does not match request",
            )
        encoded = jsonable_encoder(payload)
    except PlanningWorkspaceHttpError:
        raise
    except Exception as error:
        raise application_error_to_http(
            error,
            correlation_id=correlation_id,
            resource=_resource(resource_type, resource_id),
        ) from None
    return JSONResponse(
        status_code=status_code,
        content=encoded,
        headers={
            "X-Correlation-Id": correlation_id,
            "Cache-Control": "no-store",
        },
    )


def _invoke_download(
    request: Request,
    *,
    export_job_id: str,
    correlation_id: str,
) -> Response:
    try:
        principal = authorize_request(
            request,
            correlation_id=correlation_id,
            required_capability="export",
            resource_type="EXPORT_JOB",
            resource_id=export_job_id,
        )
        application: PlanningWorkspaceApplicationPort = (
            request.app.state.planning_workspace_application
        )
        result = application.execute(
            PlanningWorkspaceApplicationRequest(
                operation=PlanningWorkspaceOperation.DOWNLOAD_EXPORT_PACKAGE,
                context=_context(
                    request,
                    correlation_id=correlation_id,
                    principal=principal,
                    idempotency_key=None,
                ),
                resource_id=export_job_id,
            )
        )
        if not isinstance(result, PlanningWorkspaceDownload):
            raise PlanningWorkspaceApplicationError(
                "PERSISTENCE_FAILED",
                field="application_result",
                message="download operation returned a JSON result",
            )
        if (
            result.correlation_id != correlation_id
            or _DOWNLOAD_FILENAME.fullmatch(result.filename) is None
            or _PACKAGE_ID.fullmatch(result.package_id) is None
            or result.filename != f"{result.package_id}.zip"
            or not result.content
            or result.media_type != "application/zip"
            or _FINGERPRINT.fullmatch(result.manifest_fingerprint) is None
            or _FINGERPRINT.fullmatch(result.archive_fingerprint) is None
            or _CORRELATION.fullmatch(result.completion_audit_event_id) is None
        ):
            raise PlanningWorkspaceApplicationError(
                "PERSISTENCE_FAILED",
                field="application_result",
                message="download result failed its transport contract",
            )
    except PlanningWorkspaceHttpError:
        raise
    except Exception as error:
        raise application_error_to_http(
            error,
            correlation_id=correlation_id,
            resource=_resource("EXPORT_JOB", export_job_id),
        ) from None
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Correlation-Id": correlation_id,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PlantNexus-Package-Id": result.package_id,
            "X-PlantNexus-Manifest-Fingerprint": result.manifest_fingerprint,
            "X-PlantNexus-Archive-Fingerprint": result.archive_fingerprint,
            "X-PlantNexus-Completion-Audit-Event-Id": (
                result.completion_audit_event_id
            ),
        },
    )


_READ_EXTRA = {
    "x-plantnexus-api-contract": API_CONTRACT_VERSION,
    "x-plantnexus-response-authority": "application-service",
}
_QUERY_EXTRA = {
    **_READ_EXTRA,
    "x-plantnexus-request-contract": "workspace-query.v1",
    "x-plantnexus-query-serialization": "url-encoded canonical JSON query parameter",
}
_COMMAND_EXTRA = {
    **_READ_EXTRA,
    "x-plantnexus-request-contract": "workspace-command.v1",
    "x-plantnexus-idempotency-binding": "Idempotency-Key header equals body",
}
_DOWNLOAD_EXTRA = {
    **_READ_EXTRA,
    "x-plantnexus-response-contract": "export-manifest.v2 verified archive",
    "x-plantnexus-download-boundary": "SIMULATION_INTERNAL EXPORTED only",
}


@router.get(
    "/planning-runs/{planning_run_id}",
    operation_id="getPlanningRun",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_READ_EXTRA,
)
def get_planning_run(planning_run_id: str, request: Request) -> JSONResponse:
    correlation_id = _correlation(request)
    return _invoke(
        request,
        operation=PlanningWorkspaceOperation.GET_PLANNING_RUN,
        correlation_id=correlation_id,
        capability="view",
        resource_type="PLANNING_RUN",
        resource_id=planning_run_id,
    )


@router.get(
    "/schedule-versions/{schedule_version_id}",
    operation_id="getScheduleVersion",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_READ_EXTRA,
)
def get_schedule_version(schedule_version_id: str, request: Request) -> JSONResponse:
    correlation_id = _correlation(request)
    return _invoke(
        request,
        operation=PlanningWorkspaceOperation.GET_SCHEDULE_VERSION,
        correlation_id=correlation_id,
        capability="view",
        resource_type="SCHEDULE_VERSION",
        resource_id=schedule_version_id,
    )


def _schedule_command_response(
    request: Request,
    *,
    schedule_version_id: str,
    document: Mapping[str, object],
    idempotency_key: str,
    command_types: Sequence[str],
    operation: PlanningWorkspaceOperation,
) -> JSONResponse:
    carrier, capability, correlation_id = _validated_command(
        request,
        document,
        command_types=command_types,
        source_id=schedule_version_id,
        idempotency_key=idempotency_key,
        resource_type="SCHEDULE_VERSION",
    )
    return _invoke(
        request,
        operation=operation,
        correlation_id=correlation_id,
        capability=capability,
        resource_type="SCHEDULE_VERSION",
        resource_id=schedule_version_id,
        document=carrier,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/schedule-versions/{schedule_version_id}/validate",
    operation_id="validateScheduleVersion",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def validate_schedule_version(
    schedule_version_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _schedule_command_response(
        request,
        schedule_version_id=schedule_version_id,
        document=document,
        idempotency_key=idempotency_key,
        command_types=("SUBMIT_FOR_REVIEW",),
        operation=PlanningWorkspaceOperation.VALIDATE_SCHEDULE_VERSION,
    )


@router.post(
    "/schedule-versions/{schedule_version_id}/approve",
    operation_id="approveScheduleVersion",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def approve_schedule_version(
    schedule_version_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _schedule_command_response(
        request,
        schedule_version_id=schedule_version_id,
        document=document,
        idempotency_key=idempotency_key,
        command_types=("APPROVE",),
        operation=PlanningWorkspaceOperation.APPROVE_SCHEDULE_VERSION,
    )


@router.post(
    "/schedule-versions/{schedule_version_id}/reject",
    operation_id="rejectScheduleVersion",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def reject_schedule_version(
    schedule_version_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _schedule_command_response(
        request,
        schedule_version_id=schedule_version_id,
        document=document,
        idempotency_key=idempotency_key,
        command_types=("REJECT",),
        operation=PlanningWorkspaceOperation.REJECT_SCHEDULE_VERSION,
    )


@router.post(
    "/schedule-versions/{schedule_version_id}/publish",
    operation_id="publishScheduleVersion",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def publish_schedule_version(
    schedule_version_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _schedule_command_response(
        request,
        schedule_version_id=schedule_version_id,
        document=document,
        idempotency_key=idempotency_key,
        command_types=("PUBLISH",),
        operation=PlanningWorkspaceOperation.PUBLISH_SCHEDULE_VERSION,
    )


def _workspace_query_response(
    request: Request,
    *,
    raw_query: str,
    view: str,
    schedule_version_id: str | None = None,
) -> JSONResponse:
    carrier, correlation_id = _validated_query(
        request,
        raw_query,
        views=(view,),
        schedule_version_id=schedule_version_id,
    )
    capability = "audit" if view == "AUDIT" else "view"
    return _invoke(
        request,
        operation=(
            PlanningWorkspaceOperation.LIST_AUDIT_EVENTS
            if view == "AUDIT"
            else PlanningWorkspaceOperation.QUERY_WORKSPACE
        ),
        correlation_id=correlation_id,
        capability=capability,
        resource_type=("SCHEDULE_VERSION" if schedule_version_id else "WORKSPACE"),
        resource_id=schedule_version_id,
        view=view,
        document=carrier,
    )


@router.get(
    "/workspace/data-health",
    operation_id="getWorkspaceDataHealth",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def get_workspace_data_health(
    request: Request,
    workspace_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    return _workspace_query_response(
        request, raw_query=workspace_query, view="DATA_HEALTH"
    )


@router.get(
    "/workspace/import-runs",
    operation_id="listWorkspaceImportRuns",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def list_workspace_import_runs(
    request: Request,
    workspace_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    return _workspace_query_response(
        request, raw_query=workspace_query, view="IMPORT_RUNS"
    )


@router.get(
    "/workspace/planning-runs",
    operation_id="listWorkspacePlanningRuns",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def list_workspace_planning_runs(
    request: Request,
    workspace_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    return _workspace_query_response(
        request, raw_query=workspace_query, view="PLANNING_RUNS"
    )


@router.get(
    "/schedule-versions/{schedule_version_id}/workspace/{view}",
    operation_id="queryScheduleVersionWorkspace",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def query_schedule_version_workspace(
    schedule_version_id: str,
    view: str,
    request: Request,
    workspace_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    if view not in _SCHEDULE_VIEWS:
        raise public_http_error(
            "INVALID_QUERY",
            correlation_id=_correlation(request),
            field="view",
            resource=_resource("SCHEDULE_VERSION", schedule_version_id),
        )
    return _workspace_query_response(
        request,
        raw_query=workspace_query,
        view=view,
        schedule_version_id=schedule_version_id,
    )


@router.post(
    "/schedule-version-comparisons",
    operation_id="compareScheduleVersions",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra={
        **_QUERY_EXTRA,
        "x-plantnexus-compared-precondition": "versionReference headers",
    },
)
def compare_schedule_versions(
    request: Request,
    document: Annotated[dict[str, object], Body()],
    compared_schedule_version_id: Annotated[
        str, Header(alias="X-Compared-Schedule-Version-Id")
    ],
    compared_state: Annotated[str, Header(alias="X-Compared-State")],
    compared_content_fingerprint: Annotated[
        str, Header(alias="X-Compared-Content-Fingerprint")
    ],
) -> JSONResponse:
    raw_resource = document.get("resource")
    raw_base_id = (
        raw_resource.get("resource_id") if isinstance(raw_resource, Mapping) else None
    )
    if not isinstance(raw_base_id, str):
        raise public_http_error(
            "INVALID_QUERY",
            correlation_id=_correlation(request, document),
            field="resource.resource_id",
        )
    carrier, correlation_id = _validated_query(
        request,
        document,
        views=("VERSION_COMPARISON",),
        schedule_version_id=raw_base_id,
    )
    resource = cast(Mapping[str, object], carrier["resource"])
    base_id = cast(str, resource["resource_id"])
    if (
        compared_schedule_version_id == base_id
        or compared_state not in _VERSION_STATES
        or _FINGERPRINT.fullmatch(compared_content_fingerprint) is None
    ):
        raise public_http_error(
            "INVALID_QUERY",
            correlation_id=correlation_id,
            field="compared_version_precondition",
        )
    return _invoke(
        request,
        operation=PlanningWorkspaceOperation.COMPARE_SCHEDULE_VERSIONS,
        correlation_id=correlation_id,
        capability="view",
        resource_type="SCHEDULE_VERSION",
        resource_id=base_id,
        view="VERSION_COMPARISON",
        document=carrier,
        compared_version_precondition={
            "schedule_version_id": compared_schedule_version_id,
            "state": compared_state,
            "content_fingerprint": compared_content_fingerprint,
        },
        additional_schedule_version_id=compared_schedule_version_id,
    )


@router.post(
    "/schedule-versions/{schedule_version_id}/commands",
    operation_id="executeScheduleVersionCommand",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def execute_schedule_version_command(
    schedule_version_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _schedule_command_response(
        request,
        schedule_version_id=schedule_version_id,
        document=document,
        idempotency_key=idempotency_key,
        command_types=_CONTENT_COMMANDS,
        operation=PlanningWorkspaceOperation.EXECUTE_SCHEDULE_COMMAND,
    )


@router.get(
    "/schedule-versions/{schedule_version_id}/audit-events",
    operation_id="listScheduleVersionAuditEvents",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def list_schedule_version_audit_events(
    schedule_version_id: str,
    request: Request,
    workspace_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    return _workspace_query_response(
        request,
        raw_query=workspace_query,
        view="AUDIT",
        schedule_version_id=schedule_version_id,
    )


@router.post(
    "/schedule-versions/{schedule_version_id}/exports",
    operation_id="createScheduleVersionExport",
    response_model=dict[str, object],
    status_code=202,
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def create_schedule_version_export(
    schedule_version_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    carrier, capability, correlation_id = _validated_command(
        request,
        document,
        command_types=("REQUEST_EXPORT",),
        source_id=schedule_version_id,
        idempotency_key=idempotency_key,
        resource_type="SCHEDULE_VERSION",
    )
    return _invoke(
        request,
        operation=PlanningWorkspaceOperation.CREATE_EXPORT_JOB,
        correlation_id=correlation_id,
        capability=capability,
        resource_type="SCHEDULE_VERSION",
        resource_id=schedule_version_id,
        document=carrier,
        idempotency_key=idempotency_key,
        status_code=202,
    )


@router.get(
    "/export-jobs/{export_job_id}",
    operation_id="getExportJob",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_READ_EXTRA,
)
def get_export_job(export_job_id: str, request: Request) -> JSONResponse:
    correlation_id = _correlation(request)
    return _invoke(
        request,
        operation=PlanningWorkspaceOperation.GET_EXPORT_JOB,
        correlation_id=correlation_id,
        capability="view",
        resource_type="EXPORT_JOB",
        resource_id=export_job_id,
    )


@router.get(
    "/export-jobs/{export_job_id}/download",
    operation_id="downloadExportPackage",
    response_class=Response,
    responses=_DOWNLOAD_RESPONSES,
    openapi_extra=_DOWNLOAD_EXTRA,
)
def download_export_package(export_job_id: str, request: Request) -> Response:
    return _invoke_download(
        request,
        export_job_id=export_job_id,
        correlation_id=_correlation(request),
    )


def _export_job_command_response(
    request: Request,
    *,
    export_job_id: str,
    document: Mapping[str, object],
    idempotency_key: str,
    command_type: str,
    operation: PlanningWorkspaceOperation,
    status_code: int,
) -> JSONResponse:
    carrier, capability, correlation_id = _validated_command(
        request,
        document,
        command_types=(command_type,),
        source_id=export_job_id,
        idempotency_key=idempotency_key,
        resource_type="EXPORT_JOB",
    )
    return _invoke(
        request,
        operation=operation,
        correlation_id=correlation_id,
        capability=capability,
        resource_type="EXPORT_JOB",
        resource_id=export_job_id,
        document=carrier,
        idempotency_key=idempotency_key,
        status_code=status_code,
    )


@router.post(
    "/export-jobs/{export_job_id}/retry",
    operation_id="retryExportJob",
    response_model=dict[str, object],
    status_code=202,
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def retry_export_job(
    export_job_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _export_job_command_response(
        request,
        export_job_id=export_job_id,
        document=document,
        idempotency_key=idempotency_key,
        command_type="RETRY_EXPORT",
        operation=PlanningWorkspaceOperation.RETRY_EXPORT_JOB,
        status_code=202,
    )


@router.post(
    "/export-jobs/{export_job_id}/cancel",
    operation_id="cancelExportJob",
    response_model=dict[str, object],
    responses=_ERROR_RESPONSES,
    openapi_extra=_COMMAND_EXTRA,
)
def cancel_export_job(
    export_job_id: str,
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _export_job_command_response(
        request,
        export_job_id=export_job_id,
        document=document,
        idempotency_key=idempotency_key,
        command_type="CANCEL_EXPORT",
        operation=PlanningWorkspaceOperation.CANCEL_EXPORT_JOB,
        status_code=200,
    )


__all__ = ["router"]
