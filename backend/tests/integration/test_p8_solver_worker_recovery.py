"""P8 Solver Worker duplicate, cancel, timeout, crash, and mutation evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any, Iterator, cast

from alembic import command
import pytest
from sqlalchemy import Engine, text

from app.application.planning_runs import (
    PlanningRunCancelCommand,
    PlanningRunRetryCommand,
)
from app.application.schedule_versions import ValidatedSolutionToScheduleVersionService
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.contracts import JobStatus
from app.jobs.planning_run_solver_worker import (
    SolverResult,
    WorkerDisposition,
    WorkerReliabilityPolicy,
)
from app.jobs.planning_run_worker_contracts import (
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
    PlanningRunWorkerResult,
)
from app.jobs.planning_run_worker_repository import (
    SqlAlchemyPlanningRunWorkerRepository,
    WorkerResultWrite,
)
from app.planning.contracts import contract_fingerprint
from app.planning.strategies import GlobalCpSatStrategy
from backend.tests.p8_solver_worker_support import (
    FixedClock,
    FixedContextProvider,
    materialize_worker_run,
    migrated_engine,
    worker_for,
)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    value, configuration = migrated_engine(tmp_path / "p8-worker-recovery.db")
    try:
        yield value
    finally:
        value.dispose()
        command.downgrade(configuration, "base")


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))


class CountingSolver:
    def __init__(self) -> None:
        self.calls = 0
        self._delegate = GlobalCpSatStrategy()

    def solve(self, *args: object, **kwargs: object) -> SolverResult:
        self.calls += 1
        return self._delegate.solve(*args, **kwargs)  # type: ignore[arg-type]


class BlockingSolver(CountingSolver):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()

    def solve(self, *args: object, **kwargs: object) -> SolverResult:
        self.started.set()
        if not self.release.wait(timeout=10):
            raise RuntimeError("test Solver release timed out")
        return super().solve(*args, **kwargs)


class CrashSolver:
    def solve(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise KeyboardInterrupt


class CrashAfterCheckpointRepository(SqlAlchemyPlanningRunWorkerRepository):
    def __init__(self, engine: Engine) -> None:
        super().__init__(engine, data_plane=WorkspaceDataPlane.SIMULATION)
        self.crashed = False

    def put_result(self, result: PlanningRunWorkerResult) -> WorkerResultWrite:
        write = super().put_result(result)
        if not self.crashed:
            self.crashed = True
            raise KeyboardInterrupt
        return write


class TamperedCandidateSolver(CountingSolver):
    def solve(self, *args: object, **kwargs: object) -> SolverResult:
        result = super().solve(*args, **kwargs)
        solution = deepcopy(result.solution)
        report = deepcopy(result.solver_report)
        assignments = cast(list[dict[str, object]], solution["assignments"])
        assignments[0]["resource_id"] = "RESOURCE-NOT-IN-PROBLEM"
        solution_fingerprint = contract_fingerprint(solution)
        cast(dict[str, object], report["solution"])["solution_fingerprint"] = (
            solution_fingerprint
        )
        return cast(
            SolverResult,
            SimpleNamespace(solution=solution, solver_report=report),
        )


class FailOncePublisher:
    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.calls = 0

    def create_reviewable(self, output, context):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("injected publication outage")
        return self.delegate.create_reviewable(output, context)


def _publisher(engine: Engine) -> ValidatedSolutionToScheduleVersionService:
    plane = WorkspaceDataPlane.SIMULATION
    return ValidatedSolutionToScheduleVersionService(
        data_plane=plane.value,
        transaction_factory=engine.begin,
        schedule_repository=SqlAlchemyScheduleVersionRepository(
            engine, data_plane=plane
        ),
        audit_repository=SqlAlchemyAuditRepository(engine, data_plane=plane),
    )


def test_concurrent_duplicate_delivery_cannot_steal_active_lease(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    solver = BlockingSolver()
    worker = worker_for(
        engine, orchestration=orchestration, resolved=resolved, solver=solver
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            worker.execute,
            planning_run_id=cast(str, work["planning_run_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-concurrent-a",
        )
        assert solver.started.wait(timeout=10)
        with pytest.raises(PlanningRunWorkerError) as captured:
            worker.execute(
                planning_run_id=cast(str, work["planning_run_id"]),
                work_item_id=cast(str, work["work_item_id"]),
                worker_id="worker:p8-concurrent-b",
            )
        assert captured.value.code is PlanningRunWorkerErrorCode.LEASE_BUSY
        solver.release.set()
        assert first.result(timeout=15).disposition is WorkerDisposition.COMPLETED

    assert solver.calls == 1
    assert _count(engine, "planning_run_worker_results") == 1
    assert _count(engine, "schedule_versions") == 1


def test_cancel_during_solver_never_checkpoints_or_publishes(engine: Engine) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    run_id = cast(str, work["planning_run_id"])
    solver = BlockingSolver()
    worker = worker_for(
        engine, orchestration=orchestration, resolved=resolved, solver=solver
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            worker.execute,
            planning_run_id=run_id,
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-cancel",
        )
        assert solver.started.wait(timeout=10)
        context = FixedContextProvider().context_for(
            run_id, occurred_at_utc="2026-09-05T00:00:11Z"
        )
        active = orchestration.read(run_id, context=context).aggregate.document
        orchestration.cancel(
            PlanningRunCancelCommand(
                planning_run_id=run_id,
                expected_revision=cast(int, active["revision"]),
                expected_state=cast(str, active["state"]),
                expected_run_fingerprint=cast(str, active["run_fingerprint"]),
                idempotency_key="p8-worker-cancel-race-0001",
                reason="Cancel the active synthetic Solver attempt.",
            ),
            context=context,
        )
        solver.release.set()
        result = future.result(timeout=15)

    assert result.disposition is WorkerDisposition.CANCELLED
    assert _count(engine, "planning_run_worker_results") == 0
    assert _count(engine, "schedule_versions") == 0


def test_work_timeout_wins_over_a_later_solver_candidate(engine: Engine) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    clock = FixedClock()
    solver = BlockingSolver()
    worker = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        solver=solver,
        clock=clock,
        reliability_policy=WorkerReliabilityPolicy(
            heartbeat_seconds=30, lease_seconds=7200
        ),
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            worker.execute,
            planning_run_id=cast(str, work["planning_run_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-timeout",
        )
        assert solver.started.wait(timeout=10)
        clock.value = datetime(2026, 9, 5, 1, 0, 1, tzinfo=UTC)
        solver.release.set()
        result = future.result(timeout=15)

    model = orchestration.read(
        cast(str, work["planning_run_id"]),
        context=FixedContextProvider().context_for(
            cast(str, work["planning_run_id"]),
            occurred_at_utc="2026-09-05T01:00:01Z",
        ),
    )
    assert result.disposition is WorkerDisposition.TIMED_OUT
    assert model.aggregate.document["state"] == "SOLVING"
    assert model.attempts[-1].document["status"] == "TIMED_OUT"
    assert _count(engine, "planning_run_worker_results") == 0
    assert _count(engine, "schedule_versions") == 0


def test_process_crash_times_out_attempt_then_explicit_retry_completes(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    first_work = created.work_item.document
    run_id = cast(str, first_work["planning_run_id"])
    clock = FixedClock()
    crashed = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        solver=CrashSolver(),
        clock=clock,
    )
    with pytest.raises(KeyboardInterrupt):
        crashed.execute(
            planning_run_id=run_id,
            work_item_id=cast(str, first_work["work_item_id"]),
            worker_id="worker:p8-crashed",
        )

    clock.value = datetime(2026, 9, 5, 0, 3, tzinfo=UTC)
    recovery = crashed.recover_expired(recovery_worker_id="worker:p8-recovery")
    assert [item.action for item in recovery] == ["TIMED_OUT"]
    context = FixedContextProvider().context_for(
        run_id, occurred_at_utc="2026-09-05T00:03:00Z"
    )
    timed_out = orchestration.read(run_id, context=context)
    failed_attempt = timed_out.attempts[-1].document
    run = timed_out.aggregate.document
    retried = orchestration.retry(
        PlanningRunRetryCommand(
            planning_run_id=run_id,
            expected_revision=cast(int, run["revision"]),
            expected_state=cast(str, run["state"]),
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            failed_attempt_id=cast(str, failed_attempt["attempt_id"]),
            failed_attempt_number=cast(int, failed_attempt["attempt_number"]),
            idempotency_key="p8-worker-explicit-retry-0001",
            reason="Explicitly retry the expired synthetic Worker attempt.",
            available_at_utc="2026-09-05T00:03:01Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        ),
        context=context,
    )
    assert retried.work_item is not None
    clock.value = datetime(2026, 9, 5, 0, 3, 2, tzinfo=UTC)
    completed = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        clock=clock,
    ).execute(
        planning_run_id=run_id,
        work_item_id=cast(str, retried.work_item.document["work_item_id"]),
        worker_id="worker:p8-restarted",
    )
    final = orchestration.read(run_id, context=context)

    assert completed.disposition is WorkerDisposition.COMPLETED
    assert [attempt.document["status"] for attempt in final.attempts] == [
        "TIMED_OUT",
        "SUCCEEDED",
    ]
    assert _count(engine, "schedule_versions") == 1


def test_crash_after_checkpoint_requeues_same_work_without_second_solve(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    run_id = cast(str, work["planning_run_id"])
    work_id = cast(str, work["work_item_id"])
    clock = FixedClock()
    solver = CountingSolver()
    crashed = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        solver=solver,
        clock=clock,
        worker_repository=CrashAfterCheckpointRepository(engine),
    )
    with pytest.raises(KeyboardInterrupt):
        crashed.execute(
            planning_run_id=run_id,
            work_item_id=work_id,
            worker_id="worker:p8-checkpoint-crash",
        )

    before = orchestration.read(
        run_id,
        context=FixedContextProvider().context_for(
            run_id, occurred_at_utc="2026-09-05T00:00:11Z"
        ),
    )
    assert before.aggregate.document["state"] == "SOLVING"
    assert _count(engine, "planning_run_worker_results") == 1
    assert _count(engine, "schedule_versions") == 0

    clock.value = datetime(2026, 9, 5, 0, 3, tzinfo=UTC)
    restarted = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        solver=solver,
        clock=clock,
    )
    recovery = restarted.recover_expired(
        recovery_worker_id="worker:p8-checkpoint-recovery"
    )
    assert [item.action for item in recovery] == ["REQUEUE"]
    replay = restarted.execute(
        planning_run_id=run_id,
        work_item_id=work_id,
        worker_id="worker:p8-checkpoint-replay",
    )

    assert replay.disposition is WorkerDisposition.COMPLETED
    assert replay.checkpoint_replayed is True
    assert solver.calls == 1
    assert _count(engine, "planning_run_worker_results") == 1
    assert _count(engine, "schedule_versions") == 1


def test_result_transaction_outage_leaves_no_partial_business_result(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    clock = FixedClock()
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER trg_p8_injected_result_outage "
                "BEFORE INSERT ON planning_run_worker_results "
                "BEGIN SELECT RAISE(ABORT, 'injected private database detail'); END"
            )
        )
    worker = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        clock=clock,
    )

    with pytest.raises(PlanningRunWorkerError) as captured:
        worker.execute(
            planning_run_id=cast(str, work["planning_run_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-result-outage",
        )
    assert captured.value.code is PlanningRunWorkerErrorCode.PERSISTENCE_FAILED
    assert captured.value.retryable is True
    assert "private database detail" not in str(captured.value)
    assert _count(engine, "planning_run_worker_results") == 0
    assert _count(engine, "schedule_versions") == 0

    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER trg_p8_injected_result_outage"))
    clock.value = datetime(2026, 9, 5, 0, 3, tzinfo=UTC)
    recovery = worker.recover_expired(recovery_worker_id="worker:p8-db-recovery")
    assert [item.action for item in recovery] == ["TIMED_OUT"]
    final = orchestration.read(
        cast(str, work["planning_run_id"]),
        context=FixedContextProvider().context_for(
            cast(str, work["planning_run_id"]),
            occurred_at_utc="2026-09-05T00:03:00Z",
        ),
    )
    assert final.aggregate.document["state"] == "SOLVING"
    assert final.attempts[-1].document["status"] == "TIMED_OUT"


def test_crash_after_completed_cas_replays_checkpoint_without_resolve(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    clock = FixedClock()
    solver = CountingSolver()
    publisher = FailOncePublisher(_publisher(engine))
    worker = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        solver=solver,
        publisher=publisher,
        clock=clock,
    )
    with pytest.raises(PlanningRunWorkerError) as captured:
        worker.execute(
            planning_run_id=cast(str, work["planning_run_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            worker_id="worker:p8-publish-crash",
        )
    assert captured.value.code is PlanningRunWorkerErrorCode.PERSISTENCE_FAILED
    assert captured.value.retryable is True
    assert _count(engine, "planning_run_worker_results") == 1
    assert _count(engine, "schedule_versions") == 0

    clock.value = datetime(2026, 9, 5, 0, 3, tzinfo=UTC)
    recovery = worker.recover_expired(recovery_worker_id="worker:p8-recovery")
    assert [item.action for item in recovery] == ["REQUEUE"]
    replay = worker.execute(
        planning_run_id=cast(str, work["planning_run_id"]),
        work_item_id=cast(str, work["work_item_id"]),
        worker_id="worker:p8-publish-replay",
    )

    assert replay.disposition is WorkerDisposition.COMPLETED
    assert replay.checkpoint_replayed is True
    assert solver.calls == 1
    assert publisher.calls == 2
    assert _count(engine, "schedule_versions") == 1
    repository = SqlAlchemyPlanningRunWorkerRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    job = repository.get_job(replay.job_id)
    assert job is not None and job.status is JobStatus.SUCCEEDED


def test_independent_validator_rejects_a_tampered_solver_candidate(
    engine: Engine,
) -> None:
    created, orchestration, resolved = materialize_worker_run(engine)
    assert created.work_item is not None
    work = created.work_item.document
    result = worker_for(
        engine,
        orchestration=orchestration,
        resolved=resolved,
        solver=TamperedCandidateSolver(),
    ).execute(
        planning_run_id=cast(str, work["planning_run_id"]),
        work_item_id=cast(str, work["work_item_id"]),
        worker_id="worker:p8-validator-mutation",
    )
    final = orchestration.read(
        cast(str, work["planning_run_id"]),
        context=FixedContextProvider().context_for(
            cast(str, work["planning_run_id"]),
            occurred_at_utc="2026-09-05T00:00:10Z",
        ),
    )

    assert result.disposition is WorkerDisposition.TERMINAL_FAILURE
    assert final.aggregate.document["state"] == "VALIDATION_FAILED"
    assert final.aggregate.document["artifacts"]["validation_report"] is not None
    assert final.aggregate.document["artifacts"]["schedule_version"] is None
    assert _count(engine, "schedule_versions") == 0
