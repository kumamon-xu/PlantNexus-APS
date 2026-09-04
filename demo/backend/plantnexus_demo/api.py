"""Business-facing HTTP surface for the Demo runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast, Literal, NoReturn, TYPE_CHECKING
from uuid import uuid4

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.dependencies.authorization import authorize_request

from .orchestration import DemoOperationError
from .persistence import DemoPersistenceError, key_reference, utc_now
from .presentation import (
    ComparisonPresentationQuery,
    DemoComparisonView,
    DemoFactoryView,
    DemoScheduleView,
    SchedulePresentationQuery,
)
from .security import DEMO_SESSION_COOKIE, DemoClientAccessPolicy
from .urgent import UrgentOrderCommand

if TYPE_CHECKING:
    from .composition import DemoRuntime


DEMO_API_PREFIX = "/api/demo/v1"


class DemoApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        field: str,
        correlation_id: str,
        status_code: int,
    ) -> None:
        self.code = code
        self.field = field
        self.correlation_id = correlation_id
        self.status_code = status_code
        super().__init__(f"{code}: {field}")


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_version: Literal["cnc-demo-reset-request.v1"]
    profile_name: Literal["smoke", "showcase", "upper"] = "showcase"


class InitialPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_version: Literal["cnc-demo-initial-plan-request.v1"]
    expected_run_id: str = Field(min_length=1, max_length=128)


class BaselineActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    command_version: Literal["cnc-demo-baseline-activation.v1"]
    expected_run_id: str = Field(min_length=1, max_length=128)
    schedule_version_id: str = Field(min_length=1, max_length=256)
    content_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_state_revision: int = Field(ge=0)
    confirmation: Literal["ACTIVATE_SIMULATION_BASELINE"]


class DemoSessionCookieMiddleware:
    """Translate one HttpOnly same-origin cookie to the formal Bearer boundary."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = list(scope.get("headers", []))
            if not any(name.lower() == b"authorization" for name, _ in headers):
                cookie_value: bytes | None = None
                for name, value in headers:
                    if name.lower() != b"cookie":
                        continue
                    for pair in value.decode("latin-1").split(";"):
                        key, separator, candidate = pair.strip().partition("=")
                        if separator and key == DEMO_SESSION_COOKIE:
                            cookie_value = candidate.encode("latin-1")
                            break
                if cookie_value:
                    headers.append((b"authorization", b"Bearer " + cookie_value))
                    scope = dict(scope)
                    scope["headers"] = headers
        await self.app(scope, receive, send)


def _correlation(request: Request) -> str:
    value = request.headers.get("X-Correlation-Id")
    if (
        value is not None
        and value
        and len(value) <= 256
        and not any(character.isspace() for character in value)
    ):
        return value
    return f"correlation-demo-{uuid4().hex}"


def _status_for(code: str) -> int:
    if code in {
        "DEMO_NOT_INITIALIZED",
        "JOB_NOT_FOUND",
        "PRESENTATION_NOT_FOUND",
    }:
        return 404
    if code in {
        "ACTIVE_JOB_CONFLICT",
        "STALE_RUN",
        "IDEMPOTENCY_CONFLICT",
        "BASELINE_STATE_CONFLICT",
        "STALE_BASE_VERSION",
        "JOB_STATE_CONFLICT",
        "PRESENTATION_LINEAGE_MISMATCH",
    }:
        return 409
    if code in {
        "INVALID_REQUEST",
        "INVALID_IDEMPOTENCY_KEY",
        "BASELINE_CONFIRMATION_REQUIRED",
        "INVALID_IDENTIFIER",
        "INVALID_FINGERPRINT",
        "INVALID_URGENT_ORDER",
        "IMPORT_VALIDATION_FAILED",
        "INVALID_PRESENTATION_QUERY",
    }:
        return 422
    return 500


def _raise_demo(error: BaseException, *, correlation_id: str) -> NoReturn:
    if isinstance(error, DemoOperationError):
        raise DemoApiError(
            error.code,
            field=error.field,
            correlation_id=correlation_id,
            status_code=_status_for(error.code),
        ) from None
    if isinstance(error, DemoPersistenceError):
        raise DemoApiError(
            error.code,
            field=error.field,
            correlation_id=correlation_id,
            status_code=_status_for(error.code),
        ) from None
    raise DemoApiError(
        "PERSISTENCE_FAILED",
        field="demo",
        correlation_id=correlation_id,
        status_code=500,
    ) from None


def demo_error_response(_: Request, error: DemoApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error_version": "cnc-demo-error.v1",
            "code": error.code,
            "field": error.field,
            "message": "The Demo request could not be completed.",
            "correlation_id": error.correlation_id,
        },
        headers={
            "X-Correlation-Id": error.correlation_id,
            "Cache-Control": "no-store",
        },
    )


def _authorize(
    request: Request,
    *,
    correlation_id: str,
    capability: str,
    resource_type: str,
    resource_id: str | None = None,
) -> None:
    authorize_request(
        request,
        correlation_id=correlation_id,
        required_capability=capability,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def _response(
    payload: Mapping[str, object],
    *,
    correlation_id: str,
    active_run_id: str | None,
    status_code: int = 200,
) -> JSONResponse:
    document = dict(payload)
    document["correlation_id"] = correlation_id
    document["active_run_id"] = active_run_id
    headers = {
        "X-Correlation-Id": correlation_id,
        "X-Demo-Active-Run": active_run_id or "none",
        "Cache-Control": "no-store",
    }
    return JSONResponse(status_code=status_code, content=document, headers=headers)


def _immutable_response(
    view: DemoFactoryView | DemoScheduleView | DemoComparisonView,
    *,
    request: Request,
    correlation_id: str,
) -> Response:
    payload = view.model_dump(mode="json")
    view_fingerprint = cast(str, payload["view_fingerprint"])
    etag = f'"{view_fingerprint}"'
    headers = {
        "X-Correlation-Id": correlation_id,
        "X-Demo-Active-Run": view.run_id,
        "Cache-Control": "private, max-age=0, must-revalidate",
        "ETag": etag,
    }
    requested = request.headers.get("If-None-Match")
    if requested is not None:
        candidates = {value.strip() for value in requested.split(",")}
        if "*" in candidates or etag in candidates or f"W/{etag}" in candidates:
            return Response(status_code=304, headers=headers)
    return JSONResponse(status_code=200, content=payload, headers=headers)


def _query_values(request: Request, key: str) -> tuple[str, ...]:
    values = tuple(
        part.strip()
        for raw in request.query_params.getlist(key)
        for part in raw.split(",")
    )
    if any(not value for value in values) or len(values) != len(set(values)):
        raise DemoOperationError(
            "INVALID_PRESENTATION_QUERY",
            field=key,
            message="query values must be non-empty and unique",
        )
    return tuple(sorted(values))


def _query_scalar(request: Request, key: str) -> str | None:
    values = request.query_params.getlist(key)
    if not values:
        return None
    if len(values) != 1 or not values[0]:
        raise DemoOperationError(
            "INVALID_PRESENTATION_QUERY",
            field=key,
            message="query value must be a single non-empty scalar",
        )
    return values[0]


def _query_integer(request: Request, key: str, default: int) -> int:
    value = _query_scalar(request, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise DemoOperationError(
            "INVALID_PRESENTATION_QUERY",
            field=key,
            message="query value must be an integer",
        ) from error


def _require_query_keys(request: Request, allowed: frozenset[str]) -> None:
    unknown = set(request.query_params).difference(allowed)
    if unknown:
        raise DemoOperationError(
            "INVALID_PRESENTATION_QUERY",
            field=sorted(unknown)[0],
            message="unknown query parameter",
        )


def _schedule_query(request: Request) -> SchedulePresentationQuery:
    _require_query_keys(
        request,
        frozenset(
            {
                "resource_id",
                "workshop_id",
                "demand_order_id",
                "state",
                "start_at_utc",
                "end_at_utc",
                "sort",
                "offset",
                "limit",
            }
        ),
    )
    try:
        return SchedulePresentationQuery(
            resource_ids=_query_values(request, "resource_id"),
            workshop_ids=_query_values(request, "workshop_id"),
            demand_order_ids=_query_values(request, "demand_order_id"),
            states=cast(Any, _query_values(request, "state")),
            start_at_utc=_query_scalar(request, "start_at_utc"),
            end_at_utc=_query_scalar(request, "end_at_utc"),
            sort=cast(Any, _query_scalar(request, "sort") or "START_ASC"),
            offset=_query_integer(request, "offset", 0),
            limit=_query_integer(request, "limit", 200),
        )
    except ValidationError as error:
        location = error.errors()[0].get("loc", ())
        field = str(location[0]) if location else "query"
        raise DemoOperationError(
            "INVALID_PRESENTATION_QUERY",
            field=field,
            message="schedule presentation query is invalid",
        ) from error


def _comparison_query(request: Request) -> ComparisonPresentationQuery:
    _require_query_keys(
        request,
        frozenset(
            {
                "classification",
                "resource_id",
                "workshop_id",
                "demand_order_id",
                "start_at_utc",
                "end_at_utc",
                "sort",
                "offset",
                "limit",
            }
        ),
    )
    classifications = _query_values(request, "classification")
    try:
        return ComparisonPresentationQuery(
            classifications=cast(
                Any, classifications or ("ADDED", "CHANGED")
            ),
            resource_ids=_query_values(request, "resource_id"),
            workshop_ids=_query_values(request, "workshop_id"),
            demand_order_ids=_query_values(request, "demand_order_id"),
            start_at_utc=_query_scalar(request, "start_at_utc"),
            end_at_utc=_query_scalar(request, "end_at_utc"),
            sort=cast(Any, _query_scalar(request, "sort") or "OPERATION_ASC"),
            offset=_query_integer(request, "offset", 0),
            limit=_query_integer(request, "limit", 200),
        )
    except ValidationError as error:
        location = error.errors()[0].get("loc", ())
        field = str(location[0]) if location else "query"
        raise DemoOperationError(
            "INVALID_PRESENTATION_QUERY",
            field=field,
            message="comparison presentation query is invalid",
        ) from error


def create_demo_router(
    runtime: DemoRuntime,
    *,
    client_access_policy: DemoClientAccessPolicy | None = None,
) -> APIRouter:
    router = APIRouter(prefix=DEMO_API_PREFIX, tags=["CNC Demo"])
    access_policy = client_access_policy or DemoClientAccessPolicy.loopback_only()

    @router.post("/session", response_model=None)
    def establish_session(request: Request) -> JSONResponse:
        host = request.client.host if request.client is not None else ""
        if not access_policy.allows(host):
            correlation_id = _correlation(request)
            raise DemoApiError(
                "AUTHORIZATION_DENIED",
                field="client",
                correlation_id=correlation_id,
                status_code=403,
            )
        response = JSONResponse(
            status_code=200,
            content={
                "session_version": "cnc-demo-local-session.v1",
                "status": "ESTABLISHED",
                "simulation_only": True,
            },
            headers={"Cache-Control": "no-store"},
        )
        response.set_cookie(
            DEMO_SESSION_COOKIE,
            runtime.local_token,
            max_age=8 * 60 * 60,
            httponly=True,
            secure=False,
            samesite="strict",
            path="/",
        )
        return response

    @router.get("/bootstrap", response_model=None)
    def bootstrap(request: Request) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="view",
            resource_type="PLANNING_SCOPE",
        )
        try:
            state = runtime.story_state()
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            {
                "bootstrap_version": "cnc-demo-bootstrap.v1",
                **state,
                "simulation_only": True,
                "production_authority": False,
            },
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
        )

    @router.get("/state", response_model=None)
    def state(request: Request) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="view",
            resource_type="PLANNING_SCOPE",
        )
        try:
            state_document = runtime.story_state()
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            {"state_version": "cnc-demo-state.v1", **state_document},
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
        )

    @router.get("/factory", response_model=DemoFactoryView)
    def factory(request: Request) -> Response:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="view",
            resource_type="PLANNING_SCOPE",
        )
        try:
            _require_query_keys(request, frozenset())
            view = runtime.presentation.factory()
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _immutable_response(
            view, request=request, correlation_id=correlation_id
        )

    @router.get(
        "/versions/{version_id}",
        response_model=DemoScheduleView,
    )
    def schedule_version(version_id: str, request: Request) -> Response:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="view",
            resource_type="SCHEDULE_VERSION",
            resource_id=version_id,
        )
        try:
            query = _schedule_query(request)
            view = runtime.presentation.schedule(version_id, query)
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _immutable_response(
            view, request=request, correlation_id=correlation_id
        )

    @router.get(
        "/comparisons/{request_id}",
        response_model=DemoComparisonView,
    )
    def comparison(request_id: str, request: Request) -> Response:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="view",
            resource_type="PLANNING_SCOPE",
        )
        try:
            query = _comparison_query(request)
            view = runtime.presentation.comparison(request_id, query)
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _immutable_response(
            view, request=request, correlation_id=correlation_id
        )

    @router.post("/resets", response_model=None, status_code=202)
    def reset(
        request: Request,
        document: ResetRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=16, max_length=128
        ),
    ) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="demo_reset",
            resource_type="PLANNING_SCOPE",
        )
        try:
            accepted = runtime.jobs.accept_reset(
                profile_name=document.profile_name,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            accepted.document,
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
            status_code=202,
        )

    @router.post("/initial-plans", response_model=None, status_code=202)
    def initial_plan(
        request: Request,
        document: InitialPlanRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=16, max_length=128
        ),
    ) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="demo_plan",
            resource_type="PLANNING_SCOPE",
        )
        try:
            accepted = runtime.jobs.accept_initial_plan(
                expected_run_id=document.expected_run_id,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            accepted.document,
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
            status_code=202,
        )

    @router.post("/baseline-activations", response_model=None)
    def activate_baseline(
        request: Request,
        document: BaselineActivationRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=16, max_length=128
        ),
    ) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="demo_activate",
            resource_type="SCHEDULE_VERSION",
            resource_id=document.schedule_version_id,
        )
        try:
            activated = runtime.baseline.execute(
                expected_run_id=document.expected_run_id,
                schedule_version_id=document.schedule_version_id,
                content_fingerprint=document.content_fingerprint,
                expected_state_revision=document.expected_state_revision,
                confirmation=document.confirmation,
                idempotency_key_reference=key_reference(idempotency_key),
                correlation_id=correlation_id,
                occurred_at_utc=utc_now(),
            )
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            activated.document,
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
        )

    @router.post("/urgent-orders", response_model=None, status_code=202)
    def urgent_order(
        request: Request,
        document: UrgentOrderCommand,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=16, max_length=128
        ),
    ) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="replan",
            resource_type="SCHEDULE_VERSION",
            resource_id=document.expected_base_version_id,
        )
        try:
            accepted = runtime.jobs.accept_urgent_order(
                command=document,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            accepted.document,
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
            status_code=202,
        )

    @router.get("/jobs/{job_id}", response_model=None)
    def get_job(job_id: str, request: Request) -> JSONResponse:
        correlation_id = _correlation(request)
        _authorize(
            request,
            correlation_id=correlation_id,
            capability="view",
            resource_type="PLANNING_SCOPE",
        )
        try:
            job = runtime.control.get_job(job_id)
            if job is None:
                raise DemoPersistenceError(
                    "JOB_NOT_FOUND", field="job_id", message="job does not exist"
                )
            payload = {
                "job_version": "cnc-demo-job.v1",
                "job_id": job.job_id,
                "job_kind": job.job_kind,
                "run_id": job.run_id,
                "status": job.status,
                "stage": job.stage,
                "attempt": job.attempt,
                "result": job.result,
                "error_code": job.error_code,
                "created_at_utc": job.created_at_utc,
                "updated_at_utc": job.updated_at_utc,
                "stages": list(runtime.control.job_stages(job_id)),
            }
        except BaseException as error:
            _raise_demo(error, correlation_id=correlation_id)
        return _response(
            payload,
            correlation_id=correlation_id,
            active_run_id=runtime.active_run_id(),
        )

    return router


__all__ = [
    "BaselineActivationRequest",
    "DEMO_API_PREFIX",
    "DemoApiError",
    "DemoSessionCookieMiddleware",
    "InitialPlanRequest",
    "ResetRequest",
    "UrgentOrderCommand",
    "create_demo_router",
    "demo_error_response",
]
