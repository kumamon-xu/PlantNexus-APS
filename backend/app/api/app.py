"""FastAPI composition root for health and versioned planning APIs."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.contracts import (
    PlanningWorkspaceApplicationPort,
    PlanningWorkspaceHttpError,
    UnavailablePlanningWorkspaceApplication,
    public_http_error,
)
from app.api.dependencies.authorization import (
    AuthorizationAuditSink,
    AuthorizationProvider,
    NullAuthorizationAuditSink,
    UnavailableAuthorizationProvider,
)
from app.api.headless_contracts import HeadlessHttpError, public_headless_error
from app.api.headless_openapi import install_headless_openapi
from app.api.routers.headless_planning_runs import (
    router as headless_planning_runs_router,
)
from app.api.routers.planning_workspace import router as planning_workspace_router
from app.api.replanning_contracts import (
    DynamicReplanningApplicationPort,
    UnavailableDynamicReplanningApplication,
)
from app.api.routers.dynamic_replanning import router as dynamic_replanning_router
from app.infrastructure.config import Settings, load_settings
from app.infrastructure.database import create_database_client
from app.infrastructure.health import Probe, liveness_report, readiness_report
from app.infrastructure.logging import configure_logging
from app.infrastructure.redis_client import create_redis_client

if TYPE_CHECKING:
    from app.application.runtime_facade import APSRuntimeApplicationFacade
    from app.application.runtime_http_adapter import RuntimeHttpContextAdapter
    from app.runtime_composition import RuntimeCompositionDescriptor


def create_app(
    settings: Settings | None = None,
    *,
    probes: Mapping[str, Probe] | None = None,
    planning_workspace_application: PlanningWorkspaceApplicationPort | None = None,
    authorization_provider: AuthorizationProvider | None = None,
    authorization_audit_sink: AuthorizationAuditSink | None = None,
    planning_workspace_clock: Callable[[], str] | None = None,
    dynamic_replanning_application: DynamicReplanningApplicationPort | None = None,
    dynamic_replanning_clock: Callable[[], str] | None = None,
    runtime_application: APSRuntimeApplicationFacade | None = None,
    runtime_descriptor: RuntimeCompositionDescriptor | None = None,
    runtime_http_context: RuntimeHttpContextAdapter | None = None,
    headless_clock: Callable[[], str] | None = None,
    runtime_closers: tuple[Callable[[], None], ...] = (),
) -> FastAPI:
    resolved_settings = settings or load_settings()
    configure_logging(
        resolved_settings.log_level,
        include_otel_context=resolved_settings.otel_trace_context_enabled,
    )

    closers: list[Callable[[], None]] = list(runtime_closers)
    if probes is None:
        database = create_database_client(
            resolved_settings.database_url,
            timeout_seconds=resolved_settings.readiness_timeout_seconds,
        )
        redis = create_redis_client(
            resolved_settings.redis_url,
            timeout_seconds=resolved_settings.readiness_timeout_seconds,
        )
        resolved_probes: Mapping[str, Probe] = {
            "database": database.probe,
            "redis": redis.probe,
        }
        closers.extend((database.close, redis.close))
    else:
        resolved_probes = dict(probes)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for close in reversed(closers):
            close()

    application = FastAPI(
        title="PlantNexus APS planning workspace",
        version=resolved_settings.build_metadata()["code_version"],
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.planning_workspace_application = (
        planning_workspace_application or UnavailablePlanningWorkspaceApplication()
    )
    application.state.dynamic_replanning_application = (
        dynamic_replanning_application or UnavailableDynamicReplanningApplication()
    )
    application.state.authorization_provider = (
        authorization_provider or UnavailableAuthorizationProvider()
    )
    application.state.authorization_audit_sink = (
        authorization_audit_sink or NullAuthorizationAuditSink()
    )
    application.state.aps_runtime_application = runtime_application
    application.state.aps_runtime_descriptor = runtime_descriptor
    application.state.aps_runtime_http_context = runtime_http_context
    if planning_workspace_clock is not None:
        application.state.planning_workspace_clock = planning_workspace_clock
    if dynamic_replanning_clock is not None:
        application.state.dynamic_replanning_clock = dynamic_replanning_clock
    if headless_clock is not None:
        application.state.headless_clock = headless_clock

    @application.exception_handler(HeadlessHttpError)
    async def headless_error_handler(
        _: Request, error: HeadlessHttpError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error.document,
            headers=error.headers,
        )

    @application.exception_handler(PlanningWorkspaceHttpError)
    async def planning_workspace_error_handler(
        _: Request, error: PlanningWorkspaceHttpError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error.envelope.model_dump(mode="json"),
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, _: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/"):
            return JSONResponse(status_code=422, content={"detail": "Invalid request."})
        raw_correlation = request.headers.get("X-Correlation-Id")
        correlation_id = (
            raw_correlation
            if raw_correlation is not None
            and raw_correlation
            and len(raw_correlation) <= 256
            and not any(character.isspace() for character in raw_correlation)
            else f"correlation-http-{uuid4().hex}"
        )
        path_parts = request.url.path.strip("/").split("/")
        is_headless_request = (
            request.method == "POST"
            and path_parts == ["api", "v1", "planning-runs"]
        ) or (
            len(path_parts) == 5
            and path_parts[:3] == ["api", "v1", "planning-runs"]
            and path_parts[4] in {"status", "cancel", "retry", "result"}
        )
        if is_headless_request:
            error = public_headless_error(
                "CONTRACT_VIOLATION",
                correlation_id=correlation_id,
                pointer="/request",
                status_code=422,
            )
            return JSONResponse(
                status_code=error.status_code,
                content=error.document,
                headers=error.headers,
            )
        error = public_http_error(
            "INVALID_REQUEST",
            correlation_id=correlation_id,
            field="request",
            status_code=422,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=error.envelope.model_dump(mode="json"),
            headers=error.headers,
        )

    @application.get("/health/live", response_model=None)
    def live() -> JSONResponse:
        report = liveness_report(
            service=resolved_settings.service_name,
            build=resolved_settings.build_metadata(),
        )
        return JSONResponse(status_code=200, content=report.to_dict())

    @application.get("/health/ready", response_model=None)
    def ready() -> JSONResponse:
        report = readiness_report(
            service=resolved_settings.service_name,
            build=resolved_settings.build_metadata(),
            probes=resolved_probes,
        )
        return JSONResponse(
            status_code=200 if report.ready else 503,
            content=report.to_dict(),
        )

    application.include_router(planning_workspace_router)
    application.include_router(dynamic_replanning_router)
    application.include_router(headless_planning_runs_router)
    install_headless_openapi(application, resolved_settings.runtime_schema_directory)

    return application


def create_runtime_app(settings: Settings | None = None) -> FastAPI:
    """Create the deployable API entrypoint from the shared Runtime root."""

    from app.runtime_composition import (
        RuntimeCompositionError,
        RuntimeProcess,
        compose_runtime,
    )

    resolved = settings or load_settings()
    if not resolved.runtime_composition_enabled:
        if resolved.runtime_environment.value == "production":
            raise RuntimeCompositionError(
                "RUNTIME_COMPOSITION_DISABLED",
                field="runtime_composition_enabled",
                message="Production API requires explicit Runtime composition",
            )
        return create_app(resolved)
    composition = compose_runtime(resolved, process=RuntimeProcess.API)
    if composition.application is None:
        composition.close()
        raise RuntimeCompositionError(
            "RUNTIME_PORT_MISSING",
            field="application",
            message="API Runtime application port was not composed",
        )
    return create_app(
        resolved,
        probes=composition.probes,
        runtime_application=composition.application,
        runtime_descriptor=composition.descriptor,
        runtime_http_context=composition.http_context_adapter,
        runtime_closers=(composition.close,),
    )


app = create_runtime_app()

__all__ = ["app", "create_app", "create_runtime_app"]
