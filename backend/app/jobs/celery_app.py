"""Celery adapter configured for reliable JSON-only delivery."""

from __future__ import annotations

from celery import Celery

from app.infrastructure.config import Settings, load_settings
from app.jobs.planning_run_task import (
    PlanningRunTaskExecutor,
    bind_planning_run_task_executor,
    register_planning_run_task,
)


def create_celery_app(
    settings: Settings | None = None,
    *,
    executor: PlanningRunTaskExecutor | None = None,
) -> Celery:
    resolved = settings or load_settings()
    application = Celery(
        "plantnexus",
        broker=resolved.celery_broker_url.get_secret_value(),
        backend=resolved.celery_result_backend_url.get_secret_value(),
    )
    application.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        enable_utc=True,
        result_expires=3600,
        result_serializer="json",
        task_acks_late=True,
        task_default_queue="plantnexus.engineering",
        task_reject_on_worker_lost=True,
        task_send_sent_event=True,
        task_serializer="json",
        task_track_started=True,
        timezone="UTC",
        worker_prefetch_multiplier=1,
        worker_send_task_events=True,
    )
    register_planning_run_task(application)
    if executor is not None:
        bind_planning_run_task_executor(executor)
    return application


def create_runtime_celery_app(settings: Settings | None = None) -> Celery:
    """Create the deployable Worker entrypoint from the shared Runtime root."""

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
                message="Production Worker requires explicit Runtime composition",
            )
        return create_celery_app(resolved)
    composition = compose_runtime(resolved, process=RuntimeProcess.WORKER)
    if composition.worker is None:
        composition.close()
        raise RuntimeCompositionError(
            "RUNTIME_PORT_MISSING",
            field="worker",
            message="Solver Worker Runtime port was not composed",
        )
    application = create_celery_app(resolved, executor=composition.worker)
    setattr(application, "plantnexus_runtime_composition", composition)
    return application


celery_app = create_runtime_celery_app()

__all__ = ["celery_app", "create_celery_app", "create_runtime_celery_app"]
