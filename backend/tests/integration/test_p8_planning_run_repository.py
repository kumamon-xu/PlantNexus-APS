"""TEST-P8-PLANNING-RUN-001 durable transaction, CAS, and migration proof."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Barrier
from time import perf_counter_ns
from typing import Any, Iterator, Mapping, cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.application.canonical_ingress import (
    CanonicalIngressApplicationService,
    CanonicalIngressRecord,
)
from app.application.planning_runs import (
    PlanningRunAttemptFailureCommand,
    PlanningRunCancelCommand,
    PlanningRunOrchestrationService,
    PlanningRunTransitionCommand,
)
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    canonical_json_bytes,
    idempotency_key_reference,
)
from app.domain.planning_run import (
    PlanningRunAttemptStatus,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
)
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.planning_run_repository import (
    SqlAlchemyPlanningRunRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from backend.tests.contract.p8_canonical_ingress_support import (
    ROOT,
    SCHEMA_DIRECTORY,
    request_document,
    trusted_context,
)
from backend.tests.contract.p8_planning_run_support import (
    command_context,
    schemas,
)


P8_RUN_TABLES = (
    "planning_runs",
    "planning_run_attempts",
    "planning_run_work_items",
    "planning_run_audit_records",
    "planning_run_transitions",
    "planning_run_command_records",
)


def _configuration(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'p8-run.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def _ingress(engine: Engine) -> CanonicalIngressRecord:
    request = request_document()
    context = trusted_context(request)
    repository = SqlAlchemyCanonicalIngressRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    outcome = CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=repository,
    ).submit(canonical_json_bytes(request), context=context)
    assert outcome.result["disposition"] == "ACCEPTED"
    record = repository.get_by_idempotency(
        scope_fingerprint=context.idempotency_scope_fingerprint(),
        key_reference=idempotency_key_reference(cast(str, request["idempotency_key"])),
    )
    assert record is not None
    return record


def _service(engine: Engine) -> PlanningRunOrchestrationService:
    return PlanningRunOrchestrationService(
        schemas=schemas(),
        repository=SqlAlchemyPlanningRunRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
    )


def _materialize(engine: Engine, record: CanonicalIngressRecord | None = None):
    return _service(engine).materialize(
        record or _ingress(engine),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )


def _counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            table: cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))
            for table in P8_RUN_TABLES
        }


def test_atomic_materialize_restart_read_exact_replay_and_append_only_guards(
    migrated_engine: Engine,
    record_testsuite_property: Any,
) -> None:
    for name, value in {
        "task_id": "TASK-P8-04",
        "test_id": "TEST-P8-PLANNING-RUN-001",
        "diff_base": "29000eeaf73fb1306f1bcb6f7cb7ab761283d682",
        "validation_profile": "HIGH_RISK",
        "migration_head": "0007_planning_run_orchestration",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "WORKING_TREE"),
    }.items():
        record_testsuite_property(name, value)

    record = _ingress(migrated_engine)
    created = _materialize(migrated_engine, record)
    replayed = _materialize(migrated_engine, record)
    run_id = cast(str, created.aggregate.document["planning_run_id"])
    loaded = _service(migrated_engine).read(run_id, context=command_context())

    assert replayed.replayed is True
    assert loaded.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert len(loaded.attempts) == len(loaded.work_items) == 1
    assert _counts(migrated_engine) == {
        "planning_runs": 1,
        "planning_run_attempts": 1,
        "planning_run_work_items": 1,
        "planning_run_audit_records": 1,
        "planning_run_transitions": 1,
        "planning_run_command_records": 1,
    }

    with pytest.raises(DBAPIError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE planning_run_transitions SET to_state='FAILED' "
                    "WHERE planning_run_id=:run_id"
                ),
                {"run_id": run_id},
            )
    with pytest.raises(DBAPIError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM planning_runs WHERE planning_run_id=:run_id"),
                {"run_id": run_id},
            )
    assert _counts(migrated_engine)["planning_runs"] == 1


def test_development_command_read_and_transition_latency_is_observed_without_sla(
    migrated_engine: Engine,
    record_testsuite_property: Any,
) -> None:
    service = _service(migrated_engine)
    ingress = _ingress(migrated_engine)

    started_ns = perf_counter_ns()
    created = service.materialize(
        ingress,
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    materialize_elapsed_us = (perf_counter_ns() - started_ns) // 1_000

    run = created.aggregate.document
    started_ns = perf_counter_ns()
    loaded = service.read(
        cast(str, run["planning_run_id"]),
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    read_elapsed_us = (perf_counter_ns() - started_ns) // 1_000

    started_ns = perf_counter_ns()
    transitioned = service.transition(
        PlanningRunTransitionCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=cast(int, run["revision"]),
            expected_state=cast(str, run["state"]),
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            to_state="INGESTING",
            idempotency_key="p8-latency-observation-transition-0001",
            reason="Record a development-only transition timing observation.",
            artifacts=cast(Mapping[str, object], run["artifacts"]),
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:03Z"),
    )
    transition_elapsed_us = (perf_counter_ns() - started_ns) // 1_000

    assert loaded.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert transitioned.aggregate.document["state"] == "INGESTING"
    assert materialize_elapsed_us >= 0
    assert read_elapsed_us >= 0
    assert transition_elapsed_us >= 0
    record_testsuite_property(
        "p8_latency_semantics", "DEVELOPMENT_OBSERVATION_NO_SLA"
    )
    record_testsuite_property(
        "p8_materialize_elapsed_us", str(materialize_elapsed_us)
    )
    record_testsuite_property("p8_read_elapsed_us", str(read_elapsed_us))
    record_testsuite_property(
        "p8_transition_elapsed_us", str(transition_elapsed_us)
    )


def test_cancel_is_one_cas_transition_and_direct_invalid_updates_are_rejected(
    migrated_engine: Engine,
) -> None:
    created = _materialize(migrated_engine)
    run = created.aggregate.document
    cancelled = _service(migrated_engine).cancel(
        PlanningRunCancelCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            idempotency_key="p8-repository-cancel-0001",
            reason="Cancel the queued durable attempt.",
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    run_id = cast(str, run["planning_run_id"])

    assert cancelled.aggregate.document["state"] == "CANCELLED"
    assert cancelled.attempt is not None
    assert cancelled.attempt.document["status"] == "CANCELLED"
    counts = _counts(migrated_engine)
    assert counts["planning_run_transitions"] == 2
    assert counts["planning_run_audit_records"] == 2
    assert counts["planning_run_command_records"] == 2

    with pytest.raises(DBAPIError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE planning_runs SET revision=3,state='INGESTING' "
                    "WHERE planning_run_id=:run_id"
                ),
                {"run_id": run_id},
            )


def test_dispatch_failure_is_retryable_without_reopening_or_advancing_run(
    migrated_engine: Engine,
) -> None:
    created = _materialize(migrated_engine)
    assert created.attempt is not None
    run = created.aggregate.document
    attempt = created.attempt.document
    service = _service(migrated_engine)
    failed = service.record_attempt_failure(
        PlanningRunAttemptFailureCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            attempt_id=cast(str, attempt["attempt_id"]),
            attempt_number=1,
            expected_attempt_revision=1,
            outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
            failure_code="QUEUE_UNAVAILABLE",
            idempotency_key="p8-repository-dispatch-failure-0001",
            reason="Persist a pre-worker dispatch failure.",
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    assert failed.attempt is not None
    assert failed.attempt.document["status"] == "DISPATCH_FAILED"

    from app.application.planning_runs import PlanningRunRetryCommand

    retried = service.retry(
        PlanningRunRetryCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            failed_attempt_id=cast(str, failed.attempt.document["attempt_id"]),
            failed_attempt_number=1,
            idempotency_key="p8-repository-retry-0001",
            reason="Retry using the identical frozen work inputs.",
            available_at_utc="2026-09-05T00:00:04Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:03Z"),
    )
    loaded = _service(migrated_engine).read(
        cast(str, run["planning_run_id"]), context=command_context()
    )

    assert retried.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert [item.document["status"] for item in loaded.attempts] == [
        "DISPATCH_FAILED",
        "QUEUED",
    ]
    assert len(loaded.work_items) == 2
    counts = _counts(migrated_engine)
    assert counts["planning_run_transitions"] == 1
    assert counts["planning_run_audit_records"] == 3
    assert counts["planning_run_command_records"] == 3


def test_work_item_failure_rolls_back_the_whole_orchestration_transaction(
    migrated_engine: Engine,
) -> None:
    record = _ingress(migrated_engine)
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER trg_p8_run_injected_queue_failure "
                "BEFORE INSERT ON planning_run_work_items "
                "BEGIN SELECT RAISE(ABORT, 'injected queue failure'); END"
            )
        )

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        _materialize(migrated_engine, record)
    assert captured.value.code is PlanningRunErrorCode.QUEUE_FAILED
    assert _counts(migrated_engine) == {table: 0 for table in P8_RUN_TABLES}
    with migrated_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM canonical_ingress_records"))
            == 1
        )
    with migrated_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER trg_p8_run_injected_queue_failure"))


def test_concurrent_exact_materialize_commits_one_resource_set(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'p8-run-concurrent.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(
        database_url, connect_args={"check_same_thread": False, "timeout": 30}
    )
    record = _ingress(engine)
    barrier = Barrier(8)

    def submit() -> bool:
        barrier.wait(timeout=10)
        return _materialize(engine, record).replayed

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(lambda _index: submit(), range(8)))
        assert outcomes.count(False) == 1
        assert outcomes.count(True) == 7
        assert _counts(engine) == {table: 1 for table in P8_RUN_TABLES}
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def test_concurrent_exact_transition_commits_one_cas_and_replays_the_rest(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'p8-run-transition-race.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(
        database_url, connect_args={"check_same_thread": False, "timeout": 30}
    )
    created = _materialize(engine)
    run = created.aggregate.document
    transition = PlanningRunTransitionCommand(
        planning_run_id=cast(str, run["planning_run_id"]),
        expected_revision=1,
        expected_state="CREATED",
        expected_run_fingerprint=cast(str, run["run_fingerprint"]),
        to_state="INGESTING",
        idempotency_key="p8-concurrent-transition-0001",
        reason="Commit one exact CAS transition under concurrent replay.",
        artifacts=cast(Mapping[str, object], run["artifacts"]),
    )
    barrier = Barrier(8)

    def submit() -> bool:
        barrier.wait(timeout=10)
        return _service(engine).transition(
            transition,
            context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
        ).replayed

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(lambda _index: submit(), range(8)))
        assert outcomes.count(False) == 1
        assert outcomes.count(True) == 7
        loaded = _service(engine).read(
            cast(str, run["planning_run_id"]), context=command_context()
        )
        assert loaded.aggregate.document["state"] == "INGESTING"
        assert loaded.aggregate.document["revision"] == 2
        counts = _counts(engine)
        assert counts["planning_run_transitions"] == 2
        assert counts["planning_run_audit_records"] == 2
        assert counts["planning_run_command_records"] == 2
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def test_concurrent_conflicting_transitions_have_one_winner_and_one_stale_cas(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'p8-run-conflicting-race.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(
        database_url, connect_args={"check_same_thread": False, "timeout": 30}
    )
    created = _materialize(engine)
    assert created.attempt is not None
    run = created.aggregate.document
    attempt_id = cast(str, created.attempt.document["attempt_id"])
    commands = (
        PlanningRunTransitionCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            to_state="INGESTING",
            idempotency_key="p8-conflicting-transition-ingest-0001",
            reason="Compete to start ingestion.",
            artifacts=cast(Mapping[str, object], run["artifacts"]),
        ),
        PlanningRunTransitionCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            to_state="CANCELLED",
            idempotency_key="p8-conflicting-transition-cancel-0001",
            reason="Compete to cancel before ingestion.",
            artifacts=cast(Mapping[str, object], run["artifacts"]),
            attempt_id=attempt_id,
        ),
    )
    barrier = Barrier(2)

    def submit(transition: PlanningRunTransitionCommand) -> str:
        barrier.wait(timeout=10)
        try:
            return cast(
                str,
                _service(engine)
                .transition(
                    transition,
                    context=command_context(
                        occurred_at_utc="2026-09-05T00:00:02Z"
                    ),
                )
                .aggregate.document["state"],
            )
        except PlanningRunOrchestrationError as error:
            return error.code.value

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(submit, commands))
        winners = [value for value in outcomes if value in {"INGESTING", "CANCELLED"}]
        assert len(winners) == 1
        assert outcomes.count(PlanningRunErrorCode.STALE_RUN.value) == 1
        loaded = _service(engine).read(
            cast(str, run["planning_run_id"]), context=command_context()
        )
        assert loaded.aggregate.document["state"] == winners[0]
        assert loaded.aggregate.document["revision"] == 2
        counts = _counts(engine)
        assert counts["planning_run_transitions"] == 2
        assert counts["planning_run_audit_records"] == 2
        assert counts["planning_run_command_records"] == 2
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def test_populated_downgrade_is_destructive_only_for_p8_04_and_can_replay(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'p8-run-replay.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    record = _ingress(engine)
    created = _materialize(engine, record)
    engine.dispose()

    command.downgrade(configuration, "0006_canonical_ingress_application")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert set(P8_RUN_TABLES).isdisjoint(tables)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM canonical_ingress_records"))
            == 1
        )
    engine.dispose()

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    replayed = _materialize(engine, record)
    try:
        assert replayed.replayed is False
        assert replayed.aggregate.canonical_bytes == created.aggregate.canonical_bytes
        assert _counts(engine) == {table: 1 for table in P8_RUN_TABLES}
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")
