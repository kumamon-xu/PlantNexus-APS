"""Unit contract for the JSON-only P8 PlanningRun Celery adapter."""

from __future__ import annotations

from celery import Celery
import pytest

from app.jobs.planning_run_solver_worker import (
    PlanningRunWorkerExecution,
    WorkerDisposition,
)
from app.jobs.planning_run_task import (
    PLANNING_RUN_SOLVER_MESSAGE_VERSION,
    PLANNING_RUN_SOLVER_TASK,
    bind_planning_run_task_executor,
    clear_planning_run_task_executor,
    execute_planning_run_message,
    register_planning_run_task,
)
from app.jobs.planning_run_worker_contracts import (
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
)


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def execute(
        self,
        *,
        planning_run_id: str,
        work_item_id: str,
        worker_id: str,
    ) -> PlanningRunWorkerExecution:
        self.calls.append((planning_run_id, work_item_id, worker_id))
        return PlanningRunWorkerExecution(
            job_id="0" * 64,
            planning_run_id=planning_run_id,
            attempt_id="ATTEMPT-P8-TASK-001",
            work_item_id=work_item_id,
            disposition=WorkerDisposition.COMPLETED,
            planning_run_state="COMPLETED",
            checkpoint_replayed=False,
            publication_replayed=False,
        )


@pytest.fixture(autouse=True)
def clear_executor_binding():
    clear_planning_run_task_executor()
    try:
        yield
    finally:
        clear_planning_run_task_executor()


def test_data_only_message_invokes_server_bound_executor() -> None:
    executor = RecordingExecutor()
    bind_planning_run_task_executor(executor)

    result = execute_planning_run_message(
        {
            "message_version": PLANNING_RUN_SOLVER_MESSAGE_VERSION,
            "planning_run_id": "RUN-P8-TASK-001",
            "work_item_id": "WORK-P8-TASK-001",
            "worker_id": "worker:p8-task",
        }
    )

    assert executor.calls == [("RUN-P8-TASK-001", "WORK-P8-TASK-001", "worker:p8-task")]
    assert result["disposition"] == "COMPLETED"
    assert result["planning_run_state"] == "COMPLETED"


def test_task_registration_is_late_ack_json_and_operationally_retryable() -> None:
    application = Celery("p8-task-contract", broker="memory://")
    register_planning_run_task(application)

    task = application.tasks[PLANNING_RUN_SOLVER_TASK]
    assert task.acks_late is True
    assert task.reject_on_worker_lost is True
    assert task.serializer == "json"
    assert task.max_retries is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("planning_run_id", ""),
        ("work_item_id", "WORK WITH SPACE"),
        ("worker_id", "x" * 257),
    ],
)
def test_task_identity_values_are_bounded(field: str, value: str) -> None:
    message = {
        "message_version": PLANNING_RUN_SOLVER_MESSAGE_VERSION,
        "planning_run_id": "RUN-P8-TASK-001",
        "work_item_id": "WORK-P8-TASK-001",
        "worker_id": "worker:p8-task",
    }
    message[field] = value

    with pytest.raises(PlanningRunWorkerError) as captured:
        execute_planning_run_message(message)
    assert captured.value.code is PlanningRunWorkerErrorCode.INVALID_MESSAGE
