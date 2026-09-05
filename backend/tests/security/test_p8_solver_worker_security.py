"""P8 Worker runtime/input authority, task-message, and redaction checks."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Iterator, cast

from alembic import command
import pytest
from sqlalchemy import Engine, text

from app.data_validation.canonical_ingress import runtime_resolution_fingerprint
from app.jobs.planning_run_task import (
    PLANNING_RUN_SOLVER_MESSAGE_VERSION,
    clear_planning_run_task_executor,
    execute_planning_run_message,
)
from app.jobs.planning_run_worker_contracts import (
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
)
from backend.tests.p8_solver_worker_support import (
    FixedContextProvider,
    materialize_worker_run,
    migrated_engine,
    worker_for,
)
from backend.tests.contract.p8_canonical_ingress_support import runtime_resolution


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    value, configuration = migrated_engine(tmp_path / "p8-worker-security.db")
    try:
        yield value
    finally:
        clear_planning_run_task_executor()
        value.dispose()
        command.downgrade(configuration, "base")


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))


def test_valid_but_different_runtime_fingerprint_fails_before_claim(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    runtime = deepcopy(runtime_resolution())
    runtime["runtime_version"] = "0.0.1-p8-security-mismatch"
    runtime["resolution_fingerprint"] = runtime_resolution_fingerprint(runtime)

    with pytest.raises(PlanningRunWorkerError) as captured:
        worker_for(
            engine,
            orchestration=orchestration,
            resolved=resolved,
            runtime=runtime,
        ).execute(
            planning_run_id=cast(str, work["planning_run_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-runtime-mismatch",
        )

    assert captured.value.code is PlanningRunWorkerErrorCode.RUNTIME_MISMATCH
    assert captured.value.retryable is False
    assert "0.0.1-p8-security-mismatch" not in str(captured.value)
    model = orchestration.read(
        cast(str, work["planning_run_id"]),
        context=FixedContextProvider().context_for(
            cast(str, work["planning_run_id"]),
            occurred_at_utc="2026-09-05T09:00:00Z",
        ),
    )
    assert model.attempts[-1].document["status"] == "DISPATCH_FAILED"
    assert model.attempts[-1].document["failure_code"] == "RUNTIME_MISMATCH"
    assert _count(engine, "planning_run_worker_jobs") == 0
    assert _count(engine, "engineering_job_records") == 0


def test_task_message_rejects_code_selectors_and_unbound_runtime() -> None:
    clear_planning_run_task_executor()
    message = {
        "message_version": PLANNING_RUN_SOLVER_MESSAGE_VERSION,
        "planning_run_id": "RUN-P8-SECURITY",
        "work_item_id": "WORK-P8-SECURITY",
        "worker_id": "worker:p8-security",
    }
    with pytest.raises(PlanningRunWorkerError) as unbound:
        execute_planning_run_message(message)
    assert unbound.value.code is PlanningRunWorkerErrorCode.PERSISTENCE_FAILED
    assert unbound.value.retryable is True

    injected = {**message, "plugin_path": "C:/private/extension.py"}
    with pytest.raises(PlanningRunWorkerError) as rejected:
        execute_planning_run_message(injected)
    assert rejected.value.code is PlanningRunWorkerErrorCode.INVALID_MESSAGE
    rendered = str(rejected.value)
    assert "private" not in rendered
    assert "extension.py" not in rendered
