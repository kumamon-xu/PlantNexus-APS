"""FastAPI application exposing liveness and readiness only."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.infrastructure.config import Settings, load_settings
from app.infrastructure.database import create_database_client
from app.infrastructure.health import Probe, liveness_report, readiness_report
from app.infrastructure.logging import configure_logging
from app.infrastructure.redis_client import create_redis_client


def create_app(
    settings: Settings | None = None,
    *,
    probes: Mapping[str, Probe] | None = None,
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
        title="PlantNexus APS health",
        version=resolved_settings.build_metadata()["code_version"],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
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

    return application


app = create_app()

__all__ = ["app", "create_app"]
