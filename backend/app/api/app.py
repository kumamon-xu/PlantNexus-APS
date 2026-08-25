"""FastAPI composition root for health and the P3 planning workspace."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
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
from app.api.routers.planning_workspace import router as planning_workspace_router
from app.infrastructure.config import Settings, load_settings
from app.infrastructure.database import create_database_client
from app.infrastructure.health import Probe, liveness_report, readiness_report
from app.infrastructure.logging import configure_logging
from app.infrastructure.redis_client import create_redis_client


def create_app(
    settings: Settings | None = None,
    *,
    probes: Mapping[str, Probe] | None = None,
    planning_workspace_application: PlanningWorkspaceApplicationPort | None = None,
    authorization_provider: AuthorizationProvider | None = None,
    authorization_audit_sink: AuthorizationAuditSink | None = None,
    planning_workspace_clock: Callable[[], str] | None = None,
) -> FastAPI:
    resolved_settings = settings or load_settings()
    configure_logging(
        resolved_settings.log_level,
        include_otel_context=resolved_settings.otel_trace_context_enabled,
    )

    closers: list[Callable[[], None]] = []
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
    application.state.authorization_provider = (
        authorization_provider or UnavailableAuthorizationProvider()
    )
    application.state.authorization_audit_sink = (
        authorization_audit_sink or NullAuthorizationAuditSink()
    )
    if planning_workspace_clock is not None:
        application.state.planning_workspace_clock = planning_workspace_clock

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

    return application


app = create_app()

__all__ = ["app", "create_app"]
