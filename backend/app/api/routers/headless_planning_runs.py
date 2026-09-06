"""Thin HTTP adapter for canonical ingress and durable PlanningRun commands."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, NoReturn, cast

from fastapi import APIRouter, Header, Path, Request
from fastapi.responses import JSONResponse

from app.application.planning_runs import (
    PlanningRunCancelCommand,
    PlanningRunOrchestrationError,
    PlanningRunRetryCommand,
)
from app.application.host_authorization import (
    AuthorizedHostPrincipal,
    HostAuthorizationRequest,
)
from app.application.runtime_facade import (
    APSRuntimeApplicationFacade,
    RuntimeFacadeError,
)
from app.application.runtime_http_adapter import (
    RuntimeHttpAdapterError,
    RuntimeHttpContextAdapter,
    RuntimeHttpPrincipal,
    RuntimeHttpRequestedScope,
)
from app.domain.types import format_utc_instant, parse_utc_instant
from app.api.dependencies.host_authorization import authorize_headless_request
from app.api.headless_contracts import (
    MAX_ACTION_REQUEST_BYTES,
    MAX_CANONICAL_REQUEST_BYTES,
    PlanningRunCancelAction,
    PlanningRunRetryAction,
    correlation_id,
    from_contract_error,
    headless_status,
    public_headless_error,
    read_strict_json,
    require_cancel_action,
    require_canonical_envelope,
    require_idempotency_key,
    require_retry_action,
    response_headers,
)
from app.data_validation.canonical_ingress import CanonicalIngressContractError
from app.domain.planning_run import PLANNING_RUN_TERMINAL_STATES


_HEADLESS_ERROR_RESPONSE = {
    "description": "Stable sanitized Headless Runtime error",
    "content": {
        "application/json": {"schema": {"$ref": "#/components/schemas/HeadlessError"}}
    },
}
_AUTH_ERROR_RESPONSE = {
    "description": "Existing v1 authentication or authorization error",
    "content": {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/PlanningWorkspaceErrorEnvelope"}
        }
    },
}
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _HEADLESS_ERROR_RESPONSE,
    401: _AUTH_ERROR_RESPONSE,
    403: {
        "description": "Authorization or Headless scope denial",
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        {"$ref": "#/components/schemas/PlanningWorkspaceErrorEnvelope"},
                        {"$ref": "#/components/schemas/HeadlessError"},
                    ]
                }
            }
        },
    },
    404: _HEADLESS_ERROR_RESPONSE,
    409: _HEADLESS_ERROR_RESPONSE,
    413: _HEADLESS_ERROR_RESPONSE,
    415: _HEADLESS_ERROR_RESPONSE,
    422: _HEADLESS_ERROR_RESPONSE,
    500: _HEADLESS_ERROR_RESPONSE,
    503: {
        "description": "Runtime or authorization provider unavailable",
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        {"$ref": "#/components/schemas/PlanningWorkspaceErrorEnvelope"},
                        {"$ref": "#/components/schemas/HeadlessError"},
                    ]
                }
            }
        },
    },
}
_CREATE_REJECTION_RESPONSE = {
    "description": "Canonical ingress rejection or sanitized Headless error",
    "content": {
        "application/json": {
            "schema": {
                "oneOf": [
                    {"$ref": "#/components/schemas/CanonicalIngressResult"},
                    {"$ref": "#/components/schemas/HeadlessError"},
                ]
            }
        }
    },
}
_CREATE_AUTH_REJECTION_RESPONSE = {
    "description": "Authorization denial, canonical rejection, or Runtime error",
    "content": {
        "application/json": {
            "schema": {
                "oneOf": [
                    {"$ref": "#/components/schemas/PlanningWorkspaceErrorEnvelope"},
                    {"$ref": "#/components/schemas/CanonicalIngressResult"},
                    {"$ref": "#/components/schemas/HeadlessError"},
                ]
            }
        }
    },
}
_CREATE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_ERROR_RESPONSES,
    403: _CREATE_AUTH_REJECTION_RESPONSE,
    409: _CREATE_REJECTION_RESPONSE,
    422: _CREATE_REJECTION_RESPONSE,
    500: _CREATE_REJECTION_RESPONSE,
    503: _CREATE_AUTH_REJECTION_RESPONSE,
}

_CREATE_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/CanonicalIngressRequest"}
            }
        },
    }
}
_CANCEL_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/PlanningRunCancelAction"}
            }
        },
    }
}
_RETRY_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/PlanningRunRetryAction"}
            }
        },
    }
}

router = APIRouter(prefix="/api/v1", tags=["headless-planning-runs"])


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _occurred_at(request: Request) -> str:
    clock = getattr(request.app.state, "headless_clock", _now)
    try:
        value = clock()
    except Exception:
        raise public_headless_error(
            "SYSTEM_ERROR", correlation_id=correlation_id(request)
        ) from None
    if not isinstance(value, str):
        raise public_headless_error(
            "SYSTEM_ERROR", correlation_id=correlation_id(request)
        )
    try:
        parsed = parse_utc_instant(value)
    except (TypeError, ValueError):
        raise public_headless_error(
            "SYSTEM_ERROR", correlation_id=correlation_id(request)
        ) from None
    if format_utc_instant(parsed) != value:
        raise public_headless_error(
            "SYSTEM_ERROR", correlation_id=correlation_id(request)
        )
    return value


def _ports(
    request: Request, correlation: str
) -> tuple[APSRuntimeApplicationFacade, RuntimeHttpContextAdapter]:
    application = getattr(request.app.state, "aps_runtime_application", None)
    adapter = getattr(request.app.state, "aps_runtime_http_context", None)
    if not isinstance(application, APSRuntimeApplicationFacade) or not isinstance(
        adapter, RuntimeHttpContextAdapter
    ):
        raise public_headless_error(
            "RUNTIME_RESOLUTION_FAILED",
            correlation_id=correlation,
            status_code=503,
        )
    return application, adapter


def _principal(value: AuthorizedHostPrincipal) -> RuntimeHttpPrincipal:
    return RuntimeHttpPrincipal(
        actor_reference=value.actor_reference,
        capabilities=(value.application_capability,),
        auth_policy_version=value.auth_policy_version,
        production_binding=value.production_binding,
    )


def _scope(
    *, tenant_id: str, factory_id: str, planning_scope_id: str
) -> RuntimeHttpRequestedScope:
    return RuntimeHttpRequestedScope.create(
        tenant_id=tenant_id,
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
    )


def _raise_application_error(
    error: RuntimeHttpAdapterError | RuntimeFacadeError | PlanningRunOrchestrationError,
    *,
    correlation: str,
    planning_run_id: str | None = None,
    create_operation: bool = False,
) -> NoReturn:
    raw_code = getattr(error.code, "value", error.code)
    code = cast(str, raw_code)
    status_override: int | None = None
    if code in {"STALE_RUN", "STALE_ATTEMPT", "ATTEMPT_NOT_RETRYABLE"}:
        code = "INVALID_STATE_TRANSITION"
    elif code == "SCOPE_MISMATCH" and planning_run_id is not None:
        code = "INVALID_REFERENCE"
        status_override = 404
    elif code in {"QUEUE_FAILED", "APPEND_ONLY", "UNKNOWN_OUTCOME"}:
        code = "SYSTEM_ERROR"
        status_override = 503 if raw_code == "QUEUE_FAILED" else 500
    elif code == "PRODUCTION_AUTHORITY_UNAVAILABLE":
        code = "RUNTIME_RESOLUTION_FAILED"
        status_override = 503
    elif code == "INVALID_REFERENCE" and create_operation:
        status_override = 422
    raise public_headless_error(
        code,
        correlation_id=correlation,
        pointer=f"/{error.field.replace('.', '/')}",
        entity_reference=planning_run_id,
        status_code=status_override,
    ) from None


def _raise_unexpected(*, correlation: str) -> NoReturn:
    raise public_headless_error(
        "SYSTEM_ERROR",
        correlation_id=correlation,
    ) from None


def _run_response(
    model: object,
    *,
    correlation: str,
    status_code: int,
) -> JSONResponse:
    aggregate = getattr(model, "aggregate", None)
    document = getattr(aggregate, "document", None)
    if not isinstance(document, dict):
        raise public_headless_error("SYSTEM_ERROR", correlation_id=correlation)
    headers = response_headers(correlation)
    fingerprint = document.get("run_fingerprint")
    if isinstance(fingerprint, str):
        headers["ETag"] = f'"{fingerprint}"'
    state = document.get("state")
    if isinstance(state, str):
        headers["X-APS-Planning-Run-State"] = state
    return JSONResponse(status_code=status_code, content=document, headers=headers)


@router.post(
    "/planning-runs",
    operation_id="createHeadlessPlanningRun",
    response_model=None,
    status_code=202,
    summary="Create a PlanningRun from canonical JSON",
    responses={
        202: {
            "description": "Canonical request accepted and PlanningRun created or replayed",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/CanonicalIngressResult"}
                }
            },
        },
        **_CREATE_ERROR_RESPONSES,
    },
    openapi_extra=_CREATE_OPENAPI,
)
async def create_headless_planning_run(
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    x_correlation_id: Annotated[
        str | None,
        Header(alias="X-Correlation-Id", max_length=256, pattern=r"^[!-~]{1,256}$"),
    ] = None,
) -> JSONResponse:
    del idempotency_key, x_correlation_id
    initial_correlation = correlation_id(request)
    raw, document = await read_strict_json(
        request,
        max_bytes=MAX_CANONICAL_REQUEST_BYTES,
        correlation=initial_correlation,
    )
    correlation = correlation_id(request, document)
    require_canonical_envelope(document, correlation)
    require_idempotency_key(request, correlation=correlation, document=document)
    raw_scope = document.get("requested_scope")
    if not isinstance(raw_scope, dict) or not all(
        isinstance(raw_scope.get(field), str)
        for field in ("tenant_id", "factory_id", "planning_scope_id")
    ):
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/requested_scope",
        )
    try:
        requested_scope = _scope(
            tenant_id=cast(str, raw_scope["tenant_id"]),
            factory_id=cast(str, raw_scope["factory_id"]),
            planning_scope_id=cast(str, raw_scope["planning_scope_id"]),
        )
    except RuntimeHttpAdapterError as error:
        _raise_application_error(error, correlation=correlation, create_operation=True)
    occurred_at = _occurred_at(request)
    try:
        authorization = HostAuthorizationRequest.create(
            operation_id="createHeadlessPlanningRun",
            tenant_id=requested_scope.tenant_id,
            factory_id=requested_scope.factory_id,
            planning_scope_id=requested_scope.planning_scope_id,
            resource_type="PLANNING_SCOPE",
            resource_id=requested_scope.planning_scope_id,
            correlation_id=correlation,
            occurred_at_utc=occurred_at,
        )
    except ValueError:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/requested_scope",
        ) from None
    principal = authorize_headless_request(request, authorization)
    application, adapter = _ports(request, correlation)
    try:
        trusted = adapter.ingress_context(
            document,
            principal=_principal(principal),
            occurred_at_utc=occurred_at,
        )
        submission = application.submit_canonical(
            raw,
            context=trusted.context,
            dispatch_window=trusted.dispatch_window,
        )
    except CanonicalIngressContractError as error:
        raise from_contract_error(error, correlation_id=correlation) from None
    except (
        RuntimeHttpAdapterError,
        RuntimeFacadeError,
        PlanningRunOrchestrationError,
    ) as error:
        _raise_application_error(error, correlation=correlation, create_operation=True)
    except Exception:
        _raise_unexpected(correlation=correlation)
    if submission.ingress is None:
        raise public_headless_error("SYSTEM_ERROR", correlation_id=correlation)
    result = submission.ingress.result
    disposition = result.get("disposition")
    status_code = 202
    if disposition == "REJECTED":
        rejection = result.get("rejection")
        code = rejection.get("code") if isinstance(rejection, dict) else "SYSTEM_ERROR"
        status_code = headless_status(cast(str, code))
        if code == "INVALID_REFERENCE":
            status_code = 422
    elif disposition != "ACCEPTED":
        raise public_headless_error("SYSTEM_ERROR", correlation_id=correlation)
    headers = response_headers(correlation)
    accepted = result.get("accepted")
    run_reference = accepted.get("planning_run") if isinstance(accepted, dict) else None
    planning_run_id = (
        run_reference.get("planning_run_id")
        if isinstance(run_reference, dict)
        else None
    )
    if isinstance(planning_run_id, str):
        headers["Location"] = f"/api/v1/planning-runs/{planning_run_id}/status"
    return JSONResponse(status_code=status_code, content=result, headers=headers)


def _command_context(
    request: Request,
    *,
    correlation: str,
    planning_run_id: str,
    tenant_id: str,
    factory_id: str,
    planning_scope_id: str,
    operation_id: str,
    capability: str,
) -> tuple[
    APSRuntimeApplicationFacade,
    RuntimeHttpContextAdapter,
    RuntimeHttpRequestedScope,
    object,
]:
    try:
        requested = _scope(
            tenant_id=tenant_id,
            factory_id=factory_id,
            planning_scope_id=planning_scope_id,
        )
    except RuntimeHttpAdapterError as error:
        _raise_application_error(
            error, correlation=correlation, planning_run_id=planning_run_id
        )
    occurred_at = _occurred_at(request)
    try:
        authorization = HostAuthorizationRequest.create(
            operation_id=operation_id,
            tenant_id=requested.tenant_id,
            factory_id=requested.factory_id,
            planning_scope_id=requested.planning_scope_id,
            resource_type="PLANNING_RUN",
            resource_id=planning_run_id,
            correlation_id=correlation,
            occurred_at_utc=occurred_at,
        )
    except ValueError:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/request",
        ) from None
    principal = authorize_headless_request(request, authorization)
    if principal.application_capability != capability:
        raise public_headless_error("SYSTEM_ERROR", correlation_id=correlation)
    application, adapter = _ports(request, correlation)
    try:
        context = adapter.command_context(
            requested,
            principal=_principal(principal),
            correlation_id=correlation,
            occurred_at_utc=occurred_at,
        )
    except RuntimeHttpAdapterError as error:
        _raise_application_error(
            error, correlation=correlation, planning_run_id=planning_run_id
        )
    except Exception:
        _raise_unexpected(correlation=correlation)
    return application, adapter, requested, context


@router.get(
    "/planning-runs/{planning_run_id}/status",
    operation_id="getHeadlessPlanningRunStatus",
    response_model=None,
    summary="Read the current PlanningRun status",
    responses={
        200: {
            "description": "Current immutable PlanningRun read model",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlanningRun"}
                }
            },
        },
        **_ERROR_RESPONSES,
    },
)
def get_headless_planning_run_status(
    request: Request,
    planning_run_id: Annotated[str, Path(min_length=1, max_length=256)],
    tenant_id: Annotated[str, Header(alias="X-APS-Tenant-Id")],
    factory_id: Annotated[str, Header(alias="X-APS-Factory-Id")],
    planning_scope_id: Annotated[str, Header(alias="X-APS-Planning-Scope-Id")],
    x_correlation_id: Annotated[
        str | None,
        Header(alias="X-Correlation-Id", max_length=256, pattern=r"^[!-~]{1,256}$"),
    ] = None,
) -> JSONResponse:
    del x_correlation_id
    correlation = correlation_id(request)
    application, _, _, context = _command_context(
        request,
        correlation=correlation,
        planning_run_id=planning_run_id,
        tenant_id=tenant_id,
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        operation_id="getHeadlessPlanningRunStatus",
        capability="view",
    )
    try:
        model = application.read_planning_run(
            planning_run_id, context=cast(Any, context)
        )
    except (RuntimeFacadeError, PlanningRunOrchestrationError) as error:
        _raise_application_error(
            error, correlation=correlation, planning_run_id=planning_run_id
        )
    except Exception:
        _raise_unexpected(correlation=correlation)
    return _run_response(model, correlation=correlation, status_code=200)


@router.post(
    "/planning-runs/{planning_run_id}/cancel",
    operation_id="cancelHeadlessPlanningRun",
    response_model=None,
    summary="Cancel an active PlanningRun",
    responses={
        200: {
            "description": "Cancelled PlanningRun or idempotent replay",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlanningRun"}
                }
            },
        },
        **_ERROR_RESPONSES,
    },
    openapi_extra=_CANCEL_OPENAPI,
)
async def cancel_headless_planning_run(
    request: Request,
    planning_run_id: Annotated[str, Path(min_length=1, max_length=256)],
    tenant_id: Annotated[str, Header(alias="X-APS-Tenant-Id")],
    factory_id: Annotated[str, Header(alias="X-APS-Factory-Id")],
    planning_scope_id: Annotated[str, Header(alias="X-APS-Planning-Scope-Id")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    x_correlation_id: Annotated[
        str | None,
        Header(alias="X-Correlation-Id", max_length=256, pattern=r"^[!-~]{1,256}$"),
    ] = None,
) -> JSONResponse:
    del idempotency_key, x_correlation_id
    initial_correlation = correlation_id(request)
    _, document = await read_strict_json(
        request,
        max_bytes=MAX_ACTION_REQUEST_BYTES,
        correlation=initial_correlation,
    )
    correlation = correlation_id(request)
    key = require_idempotency_key(request, correlation=correlation)
    action: PlanningRunCancelAction = require_cancel_action(document, correlation)
    application, _, _, context = _command_context(
        request,
        correlation=correlation,
        planning_run_id=planning_run_id,
        tenant_id=tenant_id,
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        operation_id="cancelHeadlessPlanningRun",
        capability="edit",
    )
    try:
        model = application.cancel_planning_run(
            PlanningRunCancelCommand(
                planning_run_id=planning_run_id,
                expected_revision=action.expected_revision,
                expected_state=action.expected_state,
                expected_run_fingerprint=action.expected_run_fingerprint,
                idempotency_key=key,
                reason=action.reason,
            ),
            context=cast(Any, context),
        )
    except (RuntimeFacadeError, PlanningRunOrchestrationError) as error:
        _raise_application_error(
            error, correlation=correlation, planning_run_id=planning_run_id
        )
    except Exception:
        _raise_unexpected(correlation=correlation)
    return _run_response(model, correlation=correlation, status_code=200)


@router.post(
    "/planning-runs/{planning_run_id}/retry",
    operation_id="retryHeadlessPlanningRun",
    response_model=None,
    status_code=202,
    summary="Retry a terminal retryable PlanningRun attempt",
    responses={
        202: {
            "description": "Retry queued or idempotently replayed",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlanningRun"}
                }
            },
        },
        **_ERROR_RESPONSES,
    },
    openapi_extra=_RETRY_OPENAPI,
)
async def retry_headless_planning_run(
    request: Request,
    planning_run_id: Annotated[str, Path(min_length=1, max_length=256)],
    tenant_id: Annotated[str, Header(alias="X-APS-Tenant-Id")],
    factory_id: Annotated[str, Header(alias="X-APS-Factory-Id")],
    planning_scope_id: Annotated[str, Header(alias="X-APS-Planning-Scope-Id")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    x_correlation_id: Annotated[
        str | None,
        Header(alias="X-Correlation-Id", max_length=256, pattern=r"^[!-~]{1,256}$"),
    ] = None,
) -> JSONResponse:
    del idempotency_key, x_correlation_id
    initial_correlation = correlation_id(request)
    _, document = await read_strict_json(
        request,
        max_bytes=MAX_ACTION_REQUEST_BYTES,
        correlation=initial_correlation,
    )
    correlation = correlation_id(request)
    key = require_idempotency_key(request, correlation=correlation)
    action: PlanningRunRetryAction = require_retry_action(document, correlation)
    application, adapter, requested, context = _command_context(
        request,
        correlation=correlation,
        planning_run_id=planning_run_id,
        tenant_id=tenant_id,
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        operation_id="retryHeadlessPlanningRun",
        capability="edit",
    )
    occurred_at = cast(Any, context).occurred_at_utc
    try:
        dispatch_window = adapter.dispatch_window(
            requested, occurred_at_utc=occurred_at
        )
        submission = application.retry_planning_run(
            PlanningRunRetryCommand(
                planning_run_id=planning_run_id,
                expected_revision=action.expected_revision,
                expected_state=action.expected_state,
                expected_run_fingerprint=action.expected_run_fingerprint,
                failed_attempt_id=action.failed_attempt_id,
                failed_attempt_number=action.failed_attempt_number,
                idempotency_key=key,
                reason=action.reason,
                available_at_utc=dispatch_window.available_at_utc,
                timeout_at_utc=dispatch_window.timeout_at_utc,
            ),
            context=cast(Any, context),
        )
    except (
        RuntimeHttpAdapterError,
        RuntimeFacadeError,
        PlanningRunOrchestrationError,
    ) as error:
        _raise_application_error(
            error, correlation=correlation, planning_run_id=planning_run_id
        )
    except Exception:
        _raise_unexpected(correlation=correlation)
    if submission.planning_run is None:
        raise public_headless_error("SYSTEM_ERROR", correlation_id=correlation)
    return _run_response(
        submission.planning_run, correlation=correlation, status_code=202
    )


@router.get(
    "/planning-runs/{planning_run_id}/result",
    operation_id="getHeadlessPlanningRunResult",
    response_model=None,
    summary="Read a terminal PlanningRun result",
    responses={
        200: {
            "description": "Terminal PlanningRun result",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlanningRun"}
                }
            },
        },
        **_ERROR_RESPONSES,
    },
)
def get_headless_planning_run_result(
    request: Request,
    planning_run_id: Annotated[str, Path(min_length=1, max_length=256)],
    tenant_id: Annotated[str, Header(alias="X-APS-Tenant-Id")],
    factory_id: Annotated[str, Header(alias="X-APS-Factory-Id")],
    planning_scope_id: Annotated[str, Header(alias="X-APS-Planning-Scope-Id")],
    x_correlation_id: Annotated[
        str | None,
        Header(alias="X-Correlation-Id", max_length=256, pattern=r"^[!-~]{1,256}$"),
    ] = None,
) -> JSONResponse:
    del x_correlation_id
    correlation = correlation_id(request)
    application, _, _, context = _command_context(
        request,
        correlation=correlation,
        planning_run_id=planning_run_id,
        tenant_id=tenant_id,
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        operation_id="getHeadlessPlanningRunResult",
        capability="view",
    )
    try:
        model = application.read_planning_run(
            planning_run_id, context=cast(Any, context)
        )
    except (RuntimeFacadeError, PlanningRunOrchestrationError) as error:
        _raise_application_error(
            error, correlation=correlation, planning_run_id=planning_run_id
        )
    except Exception:
        _raise_unexpected(correlation=correlation)
    document = model.aggregate.document
    if (
        document.get("terminal") is not True
        or document.get("state") not in PLANNING_RUN_TERMINAL_STATES
    ):
        raise public_headless_error(
            "INVALID_STATE_TRANSITION",
            correlation_id=correlation,
            pointer="/state",
            entity_reference=planning_run_id,
        )
    return _run_response(model, correlation=correlation, status_code=200)


__all__ = ["router"]
