"""Celery adapter configured for reliable JSON-only delivery."""

from __future__ import annotations

from celery import Celery

from app.infrastructure.config import Settings, load_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
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
    return application


celery_app = create_celery_app()

__all__ = ["celery_app", "create_celery_app"]
