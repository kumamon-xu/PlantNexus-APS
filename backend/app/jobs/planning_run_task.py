"""Celery JSON adapter for the plane-bound P8 PlanningRun Solver Worker."""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any, Protocol, cast

from celery import Celery

from app.jobs.planning_run_solver_worker import PlanningRunWorkerExecution
from app.jobs.planning_run_worker_contracts import (
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
    reject_worker,
)


PLANNING_RUN_SOLVER_TASK = "plantnexus.planning_run.solve.v1"
PLANNING_RUN_SOLVER_MESSAGE_VERSION = "planning-run-solver-message.v1"


class PlanningRunTaskExecutor(Protocol):
    def execute(
        self,
        *,
        planning_run_id: str,
        work_item_id: str,
        worker_id: str,
    ) -> PlanningRunWorkerExecution: ...


_BINDING_LOCK = Lock()
_BOUND_EXECUTOR: PlanningRunTaskExecutor | None = None


def bind_planning_run_task_executor(executor: PlanningRunTaskExecutor) -> None:
    """Bind the server-owned Runtime executor during Worker process startup."""

    global _BOUND_EXECUTOR
    with _BINDING_LOCK:
        _BOUND_EXECUTOR = executor


def clear_planning_run_task_executor() -> None:
    """Remove a test/startup binding; a task then fails closed."""

    global _BOUND_EXECUTOR
    with _BINDING_LOCK:
        _BOUND_EXECUTOR = None


def _text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.INVALID_MESSAGE,
            field=field,
            message="Task identity must be bounded non-empty text without whitespace",
        )
    return value


def execute_planning_run_message(message: Mapping[str, object]) -> dict[str, object]:
    """Validate the data-only message and call the startup-bound executor."""

    if (
        set(message)
        != {
            "message_version",
            "planning_run_id",
            "work_item_id",
            "worker_id",
        }
        or message.get("message_version") != PLANNING_RUN_SOLVER_MESSAGE_VERSION
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.INVALID_MESSAGE,
            field="task_message",
            message="Task message version or field set is invalid",
        )
    planning_run_id = _text(message.get("planning_run_id"), "planning_run_id")
    work_item_id = _text(message.get("work_item_id"), "work_item_id")
    worker_id = _text(message.get("worker_id"), "worker_id")
    with _BINDING_LOCK:
        executor = _BOUND_EXECUTOR
    if executor is None:
        reject_worker(
            PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
            field="runtime_composition",
            message="PlanningRun Worker Runtime is not bound",
            retryable=True,
        )
    return executor.execute(
        planning_run_id=planning_run_id,
        work_item_id=work_item_id,
        worker_id=worker_id,
    ).as_document()


def register_planning_run_task(application: Celery) -> None:
    """Register one late-ack task without accepting code/config selectors."""

    if PLANNING_RUN_SOLVER_TASK in application.tasks:
        return

    @application.task(
        bind=True,
        name=PLANNING_RUN_SOLVER_TASK,
        acks_late=True,
        reject_on_worker_lost=True,
        serializer="json",
        max_retries=None,
    )
    def planning_run_solver_task(task: Any, message: object) -> dict[str, object]:
        if not isinstance(message, Mapping):
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_MESSAGE,
                field="task_message",
                message="Task body must be a JSON object",
            )
        try:
            return execute_planning_run_message(cast(Mapping[str, object], message))
        except PlanningRunWorkerError as error:
            if error.retryable:
                raise task.retry(exc=error, countdown=30)
            raise


__all__ = [
    "PLANNING_RUN_SOLVER_MESSAGE_VERSION",
    "PLANNING_RUN_SOLVER_TASK",
    "bind_planning_run_task_executor",
    "clear_planning_run_task_executor",
    "execute_planning_run_message",
    "register_planning_run_task",
]
