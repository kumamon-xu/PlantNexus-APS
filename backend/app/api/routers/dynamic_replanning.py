"""Thin FastAPI transport adapter for P4 dynamic replanning."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import re
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.contracts import (
    PlanningWorkspaceErrorEnvelope,
    PlanningWorkspaceHttpError,
    application_error_to_http,
    public_http_error,
)
from app.api.dependencies.authorization import (
    PrincipalContext,
    authorize_request,
    carrier_environment,
    carrier_plane,
)
from app.api.replanning_contracts import (
    DYNAMIC_REPLANNING_ACTION_VERSION,
    DYNAMIC_REPLANNING_API_VERSION,
    DYNAMIC_REPLANNING_QUERY_VERSION,
    DYNAMIC_REPLANNING_RESPONSE_VERSION,
    DynamicReplanningApplicationError,
    DynamicReplanningApplicationPort,
    DynamicReplanningApplicationRequest,
    DynamicReplanningOperation,
    DynamicReplanningRequestContext,
    DynamicReplanningResponseEnvelope,
    ReplanAttemptActionDocument,
    idempotency_key_reference,
    require_execution_event,
    require_replan_action,
    require_replan_request,
    require_replanning_query,
    validate_response_envelope,
)
from app.infrastructure.config import DataPlane, Settings


_CORRELATION = re.compile(r"[^\s\x00-\x1f\x7f]{1,256}")

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
        "description": "Lineage, state, stream, or idempotency conflict",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    422: {
        "description": "Strict carrier, query, or validation failure",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    500: {
        "description": "Sanitized integrity or persistence failure",
        "model": PlanningWorkspaceErrorEnvelope,
    },
    503: {
        "description": "Application unavailable or outcome unknown",
        "model": PlanningWorkspaceErrorEnvelope,
    },
}

_BASE_EXTRA = {
    "x-plantnexus-api-contract": DYNAMIC_REPLANNING_API_VERSION,
    "x-plantnexus-response-contract": DYNAMIC_REPLANNING_RESPONSE_VERSION,
    "x-plantnexus-response-authority": "application-service",
    "x-plantnexus-production-authority": "DEFAULT_DENY_OPEN_010_015",
    "x-plantnexus-p5-capabilities": "NOT_ADVERTISED",
}
_EVENT_COMMAND_EXTRA = {
    **_BASE_EXTRA,
    "x-plantnexus-request-contract": "execution-event.v1",
    "x-plantnexus-json-schema-id": "urn:plantnexus:aps:schema:execution-event:v1",
    "x-plantnexus-idempotency-binding": "hashed Idempotency-Key plus event fingerprint",
}
_REPLAN_COMMAND_EXTRA = {
    **_BASE_EXTRA,
    "x-plantnexus-request-contract": "replan-request.v1",
    "x-plantnexus-json-schema-id": "urn:plantnexus:aps:schema:replan-request:v1",
    "x-plantnexus-idempotency-binding": "hashed Idempotency-Key plus request fingerprint",
}
_ACTION_EXTRA = {
    **_BASE_EXTRA,
    "x-plantnexus-request-contract": DYNAMIC_REPLANNING_ACTION_VERSION,
    "x-plantnexus-idempotency-binding": "Idempotency-Key hash equals body reference",
    "x-plantnexus-state-authority": "expected PlanningRun attempt CAS; ReplanRequest has no state",
}
_QUERY_EXTRA = {
    **_BASE_EXTRA,
    "x-plantnexus-request-contract": DYNAMIC_REPLANNING_QUERY_VERSION,
    "x-plantnexus-query-serialization": "url-encoded canonical JSON query parameter",
}


router = APIRouter(prefix="/api/v1", tags=["dynamic-replanning"])


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_correlation() -> str:
    return f"correlation-replan-http-{uuid4().hex}"


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


def _require_runtime_boundary(
    request: Request,
    document: Mapping[str, object],
    correlation_id: str,
) -> None:
    settings: Settings = request.app.state.settings
    # A valid Simulation carrier presented to a Production composition must reach
    # the shared authorization guard so it is denied and audited before provider
    # or application lookup.  No Production carrier exists in this P4 contract.
    if settings.data_plane is DataPlane.PRODUCTION:
        return
    try:
        expected_plane = carrier_plane(settings)
        expected_environment = carrier_environment(settings)
    except ValueError as error:
        raise application_error_to_http(
            DynamicReplanningApplicationError(
                "SERVICE_UNAVAILABLE",
                field="runtime_environment",
                message="dynamic replanning carrier environment is unavailable",
            ),
            correlation_id=correlation_id,
        ) from error
    if (
        document.get("data_plane") != expected_plane
        or document.get("environment") != expected_environment
        or document.get("production_binding") is not False
    ):
        raise public_http_error(
            "DATA_PLANE_MISMATCH",
            correlation_id=correlation_id,
            field="data_plane/environment/production_binding",
        )


def _context(
    request: Request,
    *,
    correlation_id: str,
    principal: PrincipalContext,
    key_reference: str | None,
) -> DynamicReplanningRequestContext:
    settings: Settings = request.app.state.settings
    clock = getattr(request.app.state, "dynamic_replanning_clock", _now)
    return DynamicReplanningRequestContext(
        correlation_id=correlation_id,
        actor_ref=principal.actor_ref,
        authenticated=True,
        resolved_capabilities=principal.resolved_capabilities,
        planning_scope_scope=principal.planning_scope_scope,
        auth_policy_version=principal.auth_policy_version,
        production_binding=principal.production_binding,
        occurred_at_utc=clock(),
        code_commit=settings.code_commit,
        data_plane=carrier_plane(settings),
        environment=carrier_environment(settings),
        idempotency_key_reference=key_reference,
    )


def _invoke(
    request: Request,
    *,
    operation: DynamicReplanningOperation,
    correlation_id: str,
    capability: str,
    resource_type: str,
    resource_id: str | None,
    planning_scope_id: str,
    document: dict[str, object] | None = None,
    query: dict[str, object] | None = None,
    key_reference: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    try:
        principal = authorize_request(
            request,
            correlation_id=correlation_id,
            required_capability=capability,
            resource_type="PLANNING_SCOPE",
            resource_id=planning_scope_id,
        )
        application: DynamicReplanningApplicationPort = (
            request.app.state.dynamic_replanning_application
        )
        result = application.execute(
            DynamicReplanningApplicationRequest(
                operation=operation,
                context=_context(
                    request,
                    correlation_id=correlation_id,
                    principal=principal,
                    key_reference=key_reference,
                ),
                resource_id=resource_id,
                planning_scope_id=planning_scope_id,
                document=document,
                query=query,
            )
        )
        payload = validate_response_envelope(
            result,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
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


def _validated_query(
    request: Request,
    raw_query: str,
    *,
    query_kind: str,
    resource_id: str | None,
) -> tuple[dict[str, object], str, str]:
    try:
        document = require_replanning_query(
            raw_query,
            query_kind=query_kind,
            resource_id=resource_id,
        )
        correlation_id = _correlation(request, document)
        _require_runtime_boundary(request, document, correlation_id)
        planning_scope_id = document["planning_scope_id"]
        if not isinstance(planning_scope_id, str):
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY",
                field="planning_scope_id",
                message="planning scope is invalid",
            )
        return document, correlation_id, planning_scope_id
    except PlanningWorkspaceHttpError:
        raise
    except Exception as error:
        correlation_id = _correlation(request)
        raise application_error_to_http(
            error,
            correlation_id=correlation_id,
            resource=_resource(query_kind, resource_id),
        ) from None


@router.post(
    "/execution-events",
    operation_id="appendExecutionEvent",
    response_model=DynamicReplanningResponseEnvelope,
    status_code=202,
    responses=_ERROR_RESPONSES,
    openapi_extra=_EVENT_COMMAND_EXTRA,
)
def append_execution_event(
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    try:
        carrier = require_execution_event(document)
        correlation_id = _correlation(request, carrier)
        _require_runtime_boundary(request, carrier, correlation_id)
        planning_scope_id = carrier["planning_scope_id"]
        event_id = carrier["event_id"]
        if not isinstance(planning_scope_id, str) or not isinstance(event_id, str):
            raise DynamicReplanningApplicationError(
                "INVALID_INPUT",
                field="execution_event",
                message="event identity is invalid",
            )
        key_reference = idempotency_key_reference(idempotency_key)
    except PlanningWorkspaceHttpError:
        raise
    except Exception as error:
        raise application_error_to_http(
            error,
            correlation_id=_correlation(request),
            resource=_resource("EXECUTION_EVENT", None),
        ) from None
    return _invoke(
        request,
        operation=DynamicReplanningOperation.APPEND_EXECUTION_EVENT,
        correlation_id=correlation_id,
        capability="event_ingest",
        resource_type="EXECUTION_EVENT",
        resource_id=event_id,
        planning_scope_id=planning_scope_id,
        document=carrier,
        key_reference=key_reference,
        status_code=202,
    )


@router.get(
    "/execution-events/{event_id}",
    operation_id="getExecutionEvent",
    response_model=DynamicReplanningResponseEnvelope,
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def get_execution_event(
    event_id: str,
    request: Request,
    replanning_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    query, correlation_id, scope = _validated_query(
        request,
        replanning_query,
        query_kind="EXECUTION_EVENT",
        resource_id=event_id,
    )
    return _invoke(
        request,
        operation=DynamicReplanningOperation.GET_EXECUTION_EVENT,
        correlation_id=correlation_id,
        capability="event_view",
        resource_type="EXECUTION_EVENT",
        resource_id=event_id,
        planning_scope_id=scope,
        query=query,
    )


@router.get(
    "/execution-events",
    operation_id="listExecutionEvents",
    response_model=DynamicReplanningResponseEnvelope,
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def list_execution_events(
    request: Request,
    replanning_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    query, correlation_id, scope = _validated_query(
        request,
        replanning_query,
        query_kind="EXECUTION_EVENT_STREAM",
        resource_id=None,
    )
    return _invoke(
        request,
        operation=DynamicReplanningOperation.LIST_EXECUTION_EVENTS,
        correlation_id=correlation_id,
        capability="event_view",
        resource_type="EXECUTION_EVENT_STREAM",
        resource_id=None,
        planning_scope_id=scope,
        query=query,
    )


@router.post(
    "/replan-requests",
    operation_id="createReplanRequest",
    response_model=DynamicReplanningResponseEnvelope,
    status_code=202,
    responses=_ERROR_RESPONSES,
    openapi_extra=_REPLAN_COMMAND_EXTRA,
)
def create_replan_request(
    request: Request,
    document: Annotated[dict[str, object], Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    try:
        carrier = require_replan_request(document)
        correlation_id = _correlation(request, carrier)
        _require_runtime_boundary(request, carrier, correlation_id)
        planning_scope_id = carrier["planning_scope_id"]
        request_id = carrier["request_id"]
        if not isinstance(planning_scope_id, str) or not isinstance(request_id, str):
            raise DynamicReplanningApplicationError(
                "INVALID_INPUT",
                field="replan_request",
                message="request identity is invalid",
            )
        key_reference = idempotency_key_reference(idempotency_key)
    except PlanningWorkspaceHttpError:
        raise
    except Exception as error:
        raise application_error_to_http(
            error,
            correlation_id=_correlation(request),
            resource=_resource("REPLAN_REQUEST", None),
        ) from None
    return _invoke(
        request,
        operation=DynamicReplanningOperation.CREATE_REPLAN_REQUEST,
        correlation_id=correlation_id,
        capability="replan",
        resource_type="REPLAN_REQUEST",
        resource_id=request_id,
        planning_scope_id=planning_scope_id,
        document=carrier,
        key_reference=key_reference,
        status_code=202,
    )


def _replan_query_response(
    request: Request,
    *,
    raw_query: str,
    request_id: str,
    result: bool,
) -> JSONResponse:
    query_kind = "REPLAN_RESULT" if result else "REPLAN_REQUEST"
    query, correlation_id, scope = _validated_query(
        request,
        raw_query,
        query_kind=query_kind,
        resource_id=request_id,
    )
    return _invoke(
        request,
        operation=(
            DynamicReplanningOperation.GET_REPLAN_RESULT
            if result
            else DynamicReplanningOperation.GET_REPLAN_REQUEST
        ),
        correlation_id=correlation_id,
        capability="replan_view",
        resource_type=query_kind,
        resource_id=request_id,
        planning_scope_id=scope,
        query=query,
    )


@router.get(
    "/replan-requests/{request_id}",
    operation_id="getReplanRequest",
    response_model=DynamicReplanningResponseEnvelope,
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def get_replan_request(
    request_id: str,
    request: Request,
    replanning_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    return _replan_query_response(
        request,
        raw_query=replanning_query,
        request_id=request_id,
        result=False,
    )


def _replan_action_response(
    request: Request,
    *,
    request_id: str,
    document: ReplanAttemptActionDocument,
    idempotency_key: str,
    action: str,
) -> JSONResponse:
    raw_document = document.model_dump(mode="json")
    try:
        correlation_id = _correlation(request, raw_document)
        _require_runtime_boundary(request, raw_document, correlation_id)
        key_reference = idempotency_key_reference(idempotency_key)
        carrier = require_replan_action(
            raw_document,
            action=action,
            request_id=request_id,
            key_reference=key_reference,
        )
        planning_scope_id = request.headers.get("X-Planning-Scope-Id")
        if (
            planning_scope_id is None
            or _CORRELATION.fullmatch(planning_scope_id) is None
        ):
            raise DynamicReplanningApplicationError(
                "INVALID_REQUEST",
                field="X-Planning-Scope-Id",
                message="planning scope header is required",
            )
    except PlanningWorkspaceHttpError:
        raise
    except Exception as error:
        raise application_error_to_http(
            error,
            correlation_id=_correlation(request),
            resource=_resource("REPLAN_REQUEST", request_id),
        ) from None
    return _invoke(
        request,
        operation=(
            DynamicReplanningOperation.CANCEL_REPLAN_REQUEST
            if action == "CANCEL"
            else DynamicReplanningOperation.RETRY_REPLAN_REQUEST
        ),
        correlation_id=correlation_id,
        capability="replan_control",
        resource_type="REPLAN_REQUEST",
        resource_id=request_id,
        planning_scope_id=planning_scope_id,
        document=carrier,
        key_reference=key_reference,
        status_code=202,
    )


@router.post(
    "/replan-requests/{request_id}/cancel",
    operation_id="cancelReplanRequest",
    response_model=DynamicReplanningResponseEnvelope,
    status_code=202,
    responses=_ERROR_RESPONSES,
    openapi_extra=_ACTION_EXTRA,
)
def cancel_replan_request(
    request_id: str,
    request: Request,
    document: Annotated[ReplanAttemptActionDocument, Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _replan_action_response(
        request,
        request_id=request_id,
        document=document,
        idempotency_key=idempotency_key,
        action="CANCEL",
    )


@router.post(
    "/replan-requests/{request_id}/retry",
    operation_id="retryReplanRequest",
    response_model=DynamicReplanningResponseEnvelope,
    status_code=202,
    responses=_ERROR_RESPONSES,
    openapi_extra=_ACTION_EXTRA,
)
def retry_replan_request(
    request_id: str,
    request: Request,
    document: Annotated[ReplanAttemptActionDocument, Body()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
    ],
) -> JSONResponse:
    return _replan_action_response(
        request,
        request_id=request_id,
        document=document,
        idempotency_key=idempotency_key,
        action="RETRY",
    )


@router.get(
    "/replan-requests/{request_id}/result",
    operation_id="getReplanResult",
    response_model=DynamicReplanningResponseEnvelope,
    responses=_ERROR_RESPONSES,
    openapi_extra=_QUERY_EXTRA,
)
def get_replan_result(
    request_id: str,
    request: Request,
    replanning_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    return _replan_query_response(
        request,
        raw_query=replanning_query,
        request_id=request_id,
        result=True,
    )


@router.get(
    "/change-reports/{report_id}",
    operation_id="getChangeReport",
    response_model=DynamicReplanningResponseEnvelope,
    responses=_ERROR_RESPONSES,
    openapi_extra={
        **_QUERY_EXTRA,
        "x-plantnexus-result-contract": "change-report.v1",
        "x-plantnexus-read-authority": "P4-11 durable read model",
    },
)
def get_change_report(
    report_id: str,
    request: Request,
    replanning_query: Annotated[
        str, Query(alias="query", min_length=2, max_length=16_384)
    ],
) -> JSONResponse:
    query, correlation_id, scope = _validated_query(
        request,
        replanning_query,
        query_kind="CHANGE_REPORT",
        resource_id=report_id,
    )
    return _invoke(
        request,
        operation=DynamicReplanningOperation.GET_CHANGE_REPORT,
        correlation_id=correlation_id,
        capability="replan_view",
        resource_type="CHANGE_REPORT",
        resource_id=report_id,
        planning_scope_id=scope,
        query=query,
    )


__all__ = ["router"]
