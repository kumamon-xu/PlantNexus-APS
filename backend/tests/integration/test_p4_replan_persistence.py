"""TASK-P4-03 durable event/replan persistence and transaction tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.domain.execution_contracts import execution_event_fingerprint
from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.replan_persistence import (
    ArtifactReference,
    ProjectionCheckpoint,
    ReplanAuditAction,
    build_replan_attempt,
    build_replan_audit_record,
    build_replan_result,
)
from app.infrastructure.replan_repository import (
    SqlAlchemyProjectionCheckpointRepository,
    SqlAlchemyReplanAuditRepository,
    SqlAlchemyReplanLineageRepository,
    SqlAlchemyReplanRequestRepository,
)
from app.infrastructure.workspace_persistence import (
    PersistenceFailure,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
)

ROOT = Path(__file__).resolve().parents[3]
SHA_A = f"sha256:{'a' * 64}"
SHA_B = f"sha256:{'b' * 64}"
SHA_C = f"sha256:{'c' * 64}"
SHA_D = f"sha256:{'d' * 64}"


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    database_path = tmp_path / "p4-replan.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "head")
    database = create_engine(database_url)
    try:
        yield database
    finally:
        database.dispose()
        command.downgrade(configuration, "base")


def _sample(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ROOT / "schemas" / "samples" / name).read_text(encoding="utf-8")),
    )


def _checkpoint(request: dict[str, object]) -> ProjectionCheckpoint:
    stream = cast(dict[str, object], request["event_stream"])
    authority = cast(dict[str, object], stream["authority"])
    source_stream = cast(dict[str, object], stream["source_stream"])
    fact = cast(dict[str, object], stream["fact_checkpoint"])
    return ProjectionCheckpoint(
        factory_id=cast(str, request["factory_id"]),
        planning_scope_id=cast(str, request["planning_scope_id"]),
        authority_id=cast(str, authority["authority_id"]),
        stream_id=cast(str, source_stream["stream_id"]),
        stream_version=cast(str, source_stream["stream_version"]),
        last_applied_position=cast(int, stream["through_position"]),
        prefix_fingerprint=cast(str, stream["stream_fingerprint"]),
        fact_checkpoint=ArtifactReference(
            document_version=cast(str, fact["document_version"]),
            artifact_id=cast(str, fact["artifact_id"]),
            fingerprint=cast(str, fact["fingerprint"]),
        ),
        updated_at_utc=cast(str, request["requested_at_utc"]),
    )


def _seed_request(
    engine: Engine,
) -> tuple[
    dict[str, object],
    dict[str, object],
    ProjectionCheckpoint,
    SqlAlchemyReplanLineageRepository,
]:
    event = _sample("execution-event.v1.synthetic.json")
    request = _sample("replan-request.v1.synthetic.json")
    checkpoint = _checkpoint(request)
    SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).append(event)
    SqlAlchemyProjectionCheckpointRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).put_initial(checkpoint)
    SqlAlchemyReplanRequestRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).append(request)
    return (
        event,
        request,
        checkpoint,
        SqlAlchemyReplanLineageRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
    )


def _assert_failure(
    reason: PersistenceFailure, operation: Callable[[], object]
) -> WorkspacePersistenceError:
    with pytest.raises(WorkspacePersistenceError) as failure:
        operation()
    assert failure.value.reason is reason
    return failure.value


def test_migration_creates_bounded_p4_table_topology(engine: Engine) -> None:
    inspector = inspect(engine)
    expected = {
        "execution_event_ledger",
        "replan_projection_checkpoints",
        "replan_requests",
        "replan_request_events",
        "replan_attempts",
        "replan_results",
        "replan_audit_records",
    }
    assert expected <= set(inspector.get_table_names())
    assert {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("execution_event_ledger")
    } == {"uq_execution_event_ledger_stream_position"}
    assert len(inspector.get_foreign_keys("replan_request_events")) == 2
    assert len(inspector.get_foreign_keys("replan_results")) == 2


def test_execution_event_ledger_exact_replay_and_position_conflict(
    engine: Engine,
) -> None:
    repository = SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    event = _sample("execution-event.v1.synthetic.json")
    first = repository.append(event)
    replay = repository.append(event)
    assert first.replayed is False
    assert replay.replayed is True
    assert repository.get(cast(str, event["event_id"])) == event
    assert repository.list_stream(
        authority_id="authority-sim-execution-001",
        stream_id="execution-stream-sim-001",
        stream_version="1.0.0",
    ) == (event,)

    same_identity_different_observation = deepcopy(event)
    same_identity_different_observation["received_at_utc"] = "2026-08-27T06:00:06Z"
    _assert_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append(same_identity_different_observation),
    )

    position_collision = deepcopy(event)
    position_collision["occurred_at_utc"] = "2026-08-27T06:00:01Z"
    position_collision["event_fingerprint"] = execution_event_fingerprint(
        position_collision
    )
    position_collision["event_id"] = (
        "execution-event-"
        + cast(str, position_collision["event_fingerprint"]).removeprefix("sha256:")
    )
    _assert_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append(position_collision),
    )


def test_checkpoint_cas_and_replan_request_lineage_are_exact(engine: Engine) -> None:
    event = _sample("execution-event.v1.synthetic.json")
    request = _sample("replan-request.v1.synthetic.json")
    event_repository = SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    checkpoint_repository = SqlAlchemyProjectionCheckpointRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    request_repository = SqlAlchemyReplanRequestRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    event_repository.append(event)

    _assert_failure(
        PersistenceFailure.STATE_CONFLICT,
        lambda: request_repository.append(request),
    )
    checkpoint = _checkpoint(request)
    first = checkpoint_repository.put_initial(checkpoint)
    replay = checkpoint_repository.put_initial(checkpoint)
    assert first.replayed is False and first.state_revision == 0
    assert replay.replayed is True and replay.state_revision == 0

    appended = request_repository.append(request)
    request_replay = request_repository.append(request)
    assert appended.replayed is False
    assert request_replay.replayed is True
    assert request_repository.list_event_ids(cast(str, request["request_id"])) == (
        cast(str, event["event_id"]),
    )

    advanced = ProjectionCheckpoint(
        factory_id=checkpoint.factory_id,
        planning_scope_id=checkpoint.planning_scope_id,
        authority_id=checkpoint.authority_id,
        stream_id=checkpoint.stream_id,
        stream_version=checkpoint.stream_version,
        last_applied_position=2,
        prefix_fingerprint=SHA_A,
        fact_checkpoint=ArtifactReference(
            "execution-fact-checkpoint.v1", "fact-checkpoint-002", SHA_B
        ),
        updated_at_utc="2026-08-27T06:01:00Z",
    )
    changed = checkpoint_repository.advance(
        expected_position=1,
        expected_state_revision=0,
        checkpoint=advanced,
    )
    assert changed.replayed is False and changed.state_revision == 1
    exact = checkpoint_repository.advance(
        expected_position=1,
        expected_state_revision=0,
        checkpoint=advanced,
    )
    assert exact.replayed is True and exact.state_revision == 1

    stale = replace(
        advanced,
        last_applied_position=3,
        prefix_fingerprint=SHA_C,
        updated_at_utc="2026-08-27T06:02:00Z",
    )
    _assert_failure(
        PersistenceFailure.STATE_CONFLICT,
        lambda: checkpoint_repository.advance(
            expected_position=1,
            expected_state_revision=0,
            checkpoint=stale,
        ),
    )


def test_attempt_and_terminal_result_are_append_only_and_idempotent(
    engine: Engine,
) -> None:
    _, request, _, lineage = _seed_request(engine)
    request_fingerprint = cast(str, request["request_fingerprint"])
    attempt = build_replan_attempt(
        request_id=cast(str, request["request_id"]),
        request_fingerprint=request_fingerprint,
        planning_run_id="planning-run-p4-persistence-001",
        attempt_number=1,
        idempotency_scope="replan-attempt/persistence-001",
        idempotency_key_reference=SHA_A,
        correlation_id=cast(str, request["correlation_id"]),
        created_at_utc="2026-08-27T06:00:07Z",
    )
    assert lineage.append_attempt(attempt).replayed is False
    assert lineage.append_attempt(attempt).replayed is True

    conflicting_attempt = build_replan_attempt(
        request_id=attempt.request_id,
        request_fingerprint=attempt.request_fingerprint,
        planning_run_id="planning-run-p4-persistence-conflict",
        attempt_number=2,
        idempotency_scope=attempt.idempotency_scope,
        idempotency_key_reference=attempt.idempotency_key_reference,
        correlation_id=attempt.correlation_id,
        created_at_utc=attempt.created_at_utc,
    )
    _assert_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: lineage.append_attempt(conflicting_attempt),
    )

    result = build_replan_result(
        attempt=attempt,
        planning_run_terminal_state="COMPLETED",
        solver_report=ArtifactReference(
            "solver-report.v2", "solver-report-persistence-001", SHA_A
        ),
        validation_report=ArtifactReference(
            "validation-report.v2", "validation-report-persistence-001", SHA_B
        ),
        new_schedule_version=ArtifactReference(
            "schedule-version.v2", "schedule-version-persistence-001", SHA_C
        ),
        change_report=ArtifactReference(
            "change-report.v1", "change-report-persistence-001", SHA_D
        ),
        correlation_id=attempt.correlation_id,
        finished_at_utc="2026-08-27T06:00:08Z",
    )
    assert lineage.append_result(result).replayed is False
    assert lineage.append_result(result).replayed is True
    assert lineage.get_result_for_attempt(attempt.attempt_id) == result.as_document()

    conflicting_result = build_replan_result(
        attempt=attempt,
        planning_run_terminal_state="FAILED",
        solver_report=None,
        validation_report=None,
        new_schedule_version=None,
        change_report=None,
        correlation_id=attempt.correlation_id,
        finished_at_utc="2026-08-27T06:00:09Z",
    )
    _assert_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: lineage.append_result(conflicting_result),
    )


def test_append_only_audit_and_caller_transaction_rollback(engine: Engine) -> None:
    event = _sample("execution-event.v1.synthetic.json")
    event_repository = SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    audit_repository = SqlAlchemyReplanAuditRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    audit = build_replan_audit_record(
        action=ReplanAuditAction.EXECUTION_EVENT_APPENDED,
        aggregate_type="EXECUTION_EVENT",
        aggregate_id=cast(str, event["event_id"]),
        correlation_id=cast(str, event["correlation_id"]),
        idempotency_scope="event-ingress/execution-stream-sim-001/1",
        idempotency_key_reference=cast(str, event["event_fingerprint"]),
        request_fingerprint=None,
        occurred_at_utc=cast(str, event["received_at_utc"]),
    )
    with pytest.raises(RuntimeError, match="caller rollback"):
        with engine.begin() as connection:
            event_repository.append_in_transaction(connection, event)
            audit_repository.append_in_transaction(connection, audit)
            raise RuntimeError("caller rollback")
    assert event_repository.get(cast(str, event["event_id"])) is None
    assert audit_repository.list_for_aggregate(
        aggregate_type="EXECUTION_EVENT",
        aggregate_id=cast(str, event["event_id"]),
    ) == ()

    with engine.begin() as connection:
        event_repository.append_in_transaction(connection, event)
        audit_repository.append_in_transaction(connection, audit)
    assert audit_repository.append(audit).replayed is True

    conflict = build_replan_audit_record(
        action=ReplanAuditAction.EXECUTION_EVENT_APPENDED,
        aggregate_type="EXECUTION_EVENT",
        aggregate_id="different-event",
        correlation_id=audit.correlation_id,
        idempotency_scope=audit.idempotency_scope,
        idempotency_key_reference=audit.idempotency_key_reference,
        request_fingerprint=None,
        occurred_at_utc=audit.occurred_at_utc,
    )
    _assert_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: audit_repository.append(conflict),
    )


def test_database_guards_and_plane_isolation_fail_closed(engine: Engine) -> None:
    event, request, checkpoint, lineage = _seed_request(engine)
    attempt = build_replan_attempt(
        request_id=cast(str, request["request_id"]),
        request_fingerprint=cast(str, request["request_fingerprint"]),
        planning_run_id="planning-run-guard-001",
        attempt_number=1,
        idempotency_scope="replan-attempt/guard-001",
        idempotency_key_reference=SHA_A,
        correlation_id=cast(str, request["correlation_id"]),
        created_at_utc="2026-08-27T06:00:07Z",
    )
    lineage.append_attempt(attempt)

    rejected = 0
    for statement in (
        "UPDATE execution_event_ledger SET event_type = 'URGENT_ORDER'",
        "DELETE FROM replan_requests",
        "UPDATE replan_projection_checkpoints SET factory_id = 'changed'",
        "DELETE FROM replan_projection_checkpoints",
        "UPDATE replan_attempts SET attempt_number = 2",
    ):
        try:
            with engine.begin() as connection:
                connection.execute(text(statement))
        except SQLAlchemyError:
            rejected += 1
    assert rejected == 5

    production = SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.PRODUCTION
    )
    assert production.get(cast(str, event["event_id"])) is None
    _assert_failure(
        PersistenceFailure.DATA_PLANE_MISMATCH,
        lambda: production.append(event),
    )
    production_checkpoint = SqlAlchemyProjectionCheckpointRepository(
        engine, data_plane=WorkspaceDataPlane.PRODUCTION
    )
    _assert_failure(
        PersistenceFailure.DATA_PLANE_MISMATCH,
        lambda: production_checkpoint.put_initial(checkpoint),
    )
