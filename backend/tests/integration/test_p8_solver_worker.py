"""TEST-P8-SOLVER-WORKER-001 durable execution and recovery integration."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, cast

from alembic import command
import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.jobs.contracts import JobStatus
from app.jobs.planning_run_solver_worker import WorkerDisposition
from app.jobs.planning_run_worker_repository import (
    SqlAlchemyPlanningRunWorkerRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from backend.tests.p8_solver_worker_support import (
    FixedContextProvider,
    alembic_configuration,
    materialize_worker_run,
    migrated_engine,
    worker_for,
)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    value, configuration = migrated_engine(tmp_path / "p8-worker.db")
    try:
        yield value
    finally:
        value.dispose()
        command.downgrade(configuration, "base")


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))


def test_real_solver_fresh_validator_checkpoint_and_schedule_publish_once(
    engine: Engine,
    record_testsuite_property,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    run_id = cast(str, work["planning_run_id"])
    work_id = cast(str, work["work_item_id"])
    worker = worker_for(engine, orchestration=orchestration, resolved=resolved)

    first = worker.execute(
        planning_run_id=run_id,
        work_item_id=work_id,
        worker_id="worker:p8-integration-1",
    )
    replay = worker.execute(
        planning_run_id=run_id,
        work_item_id=work_id,
        worker_id="worker:p8-integration-2",
    )
    model = orchestration.read(
        run_id,
        context=FixedContextProvider().context_for(
            run_id, occurred_at_utc="2026-09-05T00:00:10Z"
        ),
    )
    run = model.aggregate.document

    assert first.disposition is WorkerDisposition.COMPLETED
    assert first.checkpoint_replayed is False
    assert replay.disposition is WorkerDisposition.EXACT_REPLAY
    assert run["state"] == "COMPLETED"
    assert run["revision"] == 9
    assert model.attempts[-1].document["status"] == "SUCCEEDED"
    assert all(run["artifacts"][name] is not None for name in run["artifacts"])
    assert _count(engine, "planning_run_worker_jobs") == 1
    assert _count(engine, "planning_run_worker_results") == 1
    assert _count(engine, "schedule_versions") == 1
    assert _count(engine, "audit_events") == 1

    repository = SqlAlchemyPlanningRunWorkerRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    job = repository.get_job(first.job_id)
    assert job is not None
    assert job.status is JobStatus.SUCCEEDED
    assert job.attempt == 1
    checkpoint = repository.get_result_for_work_item(work_id)
    assert checkpoint is not None
    serialized = checkpoint.canonical_bytes.decode("utf-8")
    assert "p8-worker-ingress-key-0001" not in serialized
    assert "redis://" not in serialized

    for name, value in {
        "task_id": "TASK-P8-05",
        "test_id": "TEST-P8-SOLVER-WORKER-001",
        "validation_profile": "HIGH_RISK",
        "migration_head": "0008_planning_run_solver_worker",
        "result_semantics": "CHECKPOINT_CAS_THEN_EXISTING_PUBLICATION",
        "production_sla": "NOT_DEFINED",
    }.items():
        record_testsuite_property(name, value)


def test_worker_tables_are_append_only_and_migration_is_reversible(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    worker_for(engine, orchestration=orchestration, resolved=resolved).execute(
        planning_run_id=cast(str, work["planning_run_id"]),
        work_item_id=cast(str, work["work_item_id"]),
        worker_id="worker:p8-guards",
    )
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE planning_run_worker_results SET outcome_state='FAILED'")
            )
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM planning_run_worker_jobs"))
    assert set(inspect(engine).get_table_names()).issuperset(
        {"planning_run_worker_jobs", "planning_run_worker_results"}
    )


def test_populated_worker_migration_downgrade_preserves_p8_04_source_and_replays(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "p8-worker-migration-replay.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = alembic_configuration(database_url)
    command.upgrade(configuration, "0008_planning_run_solver_worker")
    engine = create_engine(database_url)
    try:
        created, orchestration, resolved = materialize_worker_run(engine)
        assert created.work_item is not None
        work = created.work_item.document
        worker_for(engine, orchestration=orchestration, resolved=resolved).execute(
            planning_run_id=cast(str, work["planning_run_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-migration",
        )
        assert _count(engine, "planning_run_worker_results") == 1
        assert _count(engine, "planning_runs") == 1
    finally:
        engine.dispose()

    command.downgrade(configuration, "0007_planning_run_orchestration")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "planning_run_worker_jobs" not in tables
        assert "planning_run_worker_results" not in tables
        assert _count(engine, "planning_runs") == 1
        assert _count(engine, "planning_run_attempts") == 1
        assert _count(engine, "planning_run_work_items") == 1
        with engine.connect() as connection:
            p8_jobs = connection.scalar(
                text(
                    "SELECT count(*) FROM engineering_job_records "
                    "WHERE job_kind='P8_PLANNING_RUN_SOLVER'"
                )
            )
        assert p8_jobs == 0
    finally:
        engine.dispose()

    command.upgrade(configuration, "0008_planning_run_solver_worker")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "planning_run_worker_jobs",
            "planning_run_worker_results",
        } <= tables
        assert _count(engine, "planning_run_worker_jobs") == 0
        assert _count(engine, "planning_run_worker_results") == 0
        assert _count(engine, "planning_runs") == 1
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")
