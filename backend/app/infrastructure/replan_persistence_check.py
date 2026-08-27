"""Emit machine-checkable TASK-P4-03 persistence evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from alembic import command
from alembic.config import Config
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
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import (
    PersistenceFailure,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
)

REPORT_VERSION = "p4-replan-persistence-report.v1"
TASK_ID = "TASK-P4-03"
DIFF_BASE = "7b9bfc3069de5d3738e5cc5827d27d197ed3d226"
MIGRATION_REVISION = "0005_replan_event_persistence"

_TABLES = {
    "execution_event_ledger",
    "replan_projection_checkpoints",
    "replan_requests",
    "replan_request_events",
    "replan_attempts",
    "replan_results",
    "replan_audit_records",
}
_SHA_A = f"sha256:{'a' * 64}"
_SHA_B = f"sha256:{'b' * 64}"
_SHA_C = f"sha256:{'c' * 64}"
_SHA_D = f"sha256:{'d' * 64}"


def _alembic_config(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(root / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _sample(root: Path, name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((root / "schemas" / "samples" / name).read_text(encoding="utf-8")),
    )


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _expect_failure(
    expected: PersistenceFailure,
    operation: Callable[[], object],
) -> None:
    try:
        operation()
    except WorkspacePersistenceError as error:
        if error.reason is expected:
            return
        raise ValueError(
            f"expected {expected.value}, observed {error.reason.value}"
        ) from error
    raise ValueError(f"expected {expected.value} rejection")


def _checkpoint(request: Mapping[str, object]) -> ProjectionCheckpoint:
    stream = cast(Mapping[str, object], request["event_stream"])
    authority = cast(Mapping[str, object], stream["authority"])
    source_stream = cast(Mapping[str, object], stream["source_stream"])
    fact = cast(Mapping[str, object], stream["fact_checkpoint"])
    return ProjectionCheckpoint(
        factory_id=cast(str, request["factory_id"]),
        planning_scope_id=cast(str, request["planning_scope_id"]),
        authority_id=cast(str, authority["authority_id"]),
        stream_id=cast(str, source_stream["stream_id"]),
        stream_version=cast(str, source_stream["stream_version"]),
        last_applied_position=cast(int, stream["through_position"]),
        prefix_fingerprint=cast(str, stream["stream_fingerprint"]),
        fact_checkpoint=ArtifactReference(
            cast(str, fact["document_version"]),
            cast(str, fact["artifact_id"]),
            cast(str, fact["fingerprint"]),
        ),
        updated_at_utc=cast(str, request["requested_at_utc"]),
    )


def _migration_check(engine: Engine) -> dict[str, object]:
    inspector = inspect(engine)
    if not _TABLES <= set(inspector.get_table_names()):
        raise ValueError("P4 persistence table set is incomplete")
    return {
        "revision": MIGRATION_REVISION,
        "tables": sorted(_TABLES),
        "index_count": sum(len(inspector.get_indexes(table)) for table in _TABLES),
        "foreign_key_count": sum(
            len(inspector.get_foreign_keys(table)) for table in _TABLES
        ),
        "unique_constraint_count": sum(
            len(inspector.get_unique_constraints(table)) for table in _TABLES
        ),
        "dialect": "sqlite-test-only",
    }


def _event_check(
    root: Path, repository: SqlAlchemyExecutionEventRepository
) -> tuple[dict[str, object], dict[str, object]]:
    event = _sample(root, "execution-event.v1.synthetic.json")
    first = repository.append(event)
    replay = repository.append(event)
    if first.replayed or not replay.replayed:
        raise ValueError("ExecutionEvent exact replay contract failed")
    conflict = deepcopy(event)
    conflict["received_at_utc"] = "2026-08-27T06:00:06Z"
    _expect_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append(conflict),
    )
    listed = repository.list_stream(
        authority_id="authority-sim-execution-001",
        stream_id="execution-stream-sim-001",
        stream_version="1.0.0",
    )
    if listed != (event,):
        raise ValueError("ExecutionEvent stream ordering failed")
    return (
        {
            "append": 1,
            "exact_replay": 1,
            "identity_conflict": 1,
            "ordered_stream_rows": len(listed),
        },
        event,
    )


def _checkpoint_request_check(
    root: Path,
    checkpoint_repository: SqlAlchemyProjectionCheckpointRepository,
    request_repository: SqlAlchemyReplanRequestRepository,
) -> tuple[dict[str, object], dict[str, object], ProjectionCheckpoint]:
    request = _sample(root, "replan-request.v1.synthetic.json")
    _expect_failure(
        PersistenceFailure.STATE_CONFLICT,
        lambda: request_repository.append(request),
    )
    checkpoint = _checkpoint(request)
    first = checkpoint_repository.put_initial(checkpoint)
    replay = checkpoint_repository.put_initial(checkpoint)
    inserted = request_repository.append(request)
    request_replay = request_repository.append(request)
    if first.replayed or not replay.replayed or inserted.replayed or not (
        request_replay.replayed
    ):
        raise ValueError("checkpoint/request exact replay contract failed")
    event_ids = request_repository.list_event_ids(cast(str, request["request_id"]))
    if len(event_ids) != 1:
        raise ValueError("ReplanRequest event links are incomplete")
    advanced = ProjectionCheckpoint(
        factory_id=checkpoint.factory_id,
        planning_scope_id=checkpoint.planning_scope_id,
        authority_id=checkpoint.authority_id,
        stream_id=checkpoint.stream_id,
        stream_version=checkpoint.stream_version,
        last_applied_position=2,
        prefix_fingerprint=_SHA_A,
        fact_checkpoint=ArtifactReference(
            "execution-fact-checkpoint.v1", "fact-checkpoint-002", _SHA_B
        ),
        updated_at_utc="2026-08-27T06:01:00Z",
    )
    changed = checkpoint_repository.advance(
        expected_position=1,
        expected_state_revision=0,
        checkpoint=advanced,
    )
    exact = checkpoint_repository.advance(
        expected_position=1,
        expected_state_revision=0,
        checkpoint=advanced,
    )
    stale = ProjectionCheckpoint(
        factory_id=advanced.factory_id,
        planning_scope_id=advanced.planning_scope_id,
        authority_id=advanced.authority_id,
        stream_id=advanced.stream_id,
        stream_version=advanced.stream_version,
        last_applied_position=3,
        prefix_fingerprint=_SHA_C,
        fact_checkpoint=ArtifactReference(
            "execution-fact-checkpoint.v1", "fact-checkpoint-003", _SHA_D
        ),
        updated_at_utc="2026-08-27T06:02:00Z",
    )
    _expect_failure(
        PersistenceFailure.STATE_CONFLICT,
        lambda: checkpoint_repository.advance(
            expected_position=1,
            expected_state_revision=0,
            checkpoint=stale,
        ),
    )
    return (
        {
            "missing_checkpoint_rejection": 1,
            "checkpoint_insert": 1,
            "checkpoint_exact_replay": 1,
            "request_append": 1,
            "request_exact_replay": 1,
            "event_links": len(event_ids),
            "checkpoint_cas": 1,
            "checkpoint_cas_exact_replay": int(exact.replayed),
            "stale_cas_rejection": 1,
            "state_revision": changed.state_revision,
        },
        request,
        advanced,
    )


def _lineage_check(
    request: Mapping[str, object],
    repository: SqlAlchemyReplanLineageRepository,
) -> tuple[dict[str, object], object]:
    attempt = build_replan_attempt(
        request_id=cast(str, request["request_id"]),
        request_fingerprint=cast(str, request["request_fingerprint"]),
        planning_run_id="planning-run-p4-persistence-001",
        attempt_number=1,
        idempotency_scope="replan-attempt/persistence-001",
        idempotency_key_reference=_SHA_A,
        correlation_id=cast(str, request["correlation_id"]),
        created_at_utc="2026-08-27T06:00:07Z",
    )
    first = repository.append_attempt(attempt)
    replay = repository.append_attempt(attempt)
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
    _expect_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append_attempt(conflicting_attempt),
    )
    result = build_replan_result(
        attempt=attempt,
        planning_run_terminal_state="COMPLETED",
        solver_report=ArtifactReference(
            "solver-report.v2", "solver-report-persistence-001", _SHA_A
        ),
        validation_report=ArtifactReference(
            "validation-report.v2", "validation-report-persistence-001", _SHA_B
        ),
        new_schedule_version=ArtifactReference(
            "schedule-version.v2", "schedule-version-persistence-001", _SHA_C
        ),
        change_report=ArtifactReference(
            "change-report.v1", "change-report-persistence-001", _SHA_D
        ),
        correlation_id=attempt.correlation_id,
        finished_at_utc="2026-08-27T06:00:08Z",
    )
    result_first = repository.append_result(result)
    result_replay = repository.append_result(result)
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
    _expect_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append_result(conflicting_result),
    )
    if (
        first.replayed
        or not replay.replayed
        or result_first.replayed
        or not result_replay.replayed
    ):
        raise ValueError("attempt/result exact replay contract failed")
    return (
        {
            "attempt_append": 1,
            "attempt_exact_replay": 1,
            "attempt_idempotency_conflict": 1,
            "terminal_result_append": 1,
            "terminal_result_exact_replay": 1,
            "result_conflict": 1,
            "replan_request_state_machine": "ABSENT",
            "planning_run_terminal_reference": "COMPLETED",
        },
        attempt,
    )


def _audit_check(
    event: Mapping[str, object],
    repository: SqlAlchemyReplanAuditRepository,
) -> dict[str, object]:
    record = build_replan_audit_record(
        action=ReplanAuditAction.EXECUTION_EVENT_APPENDED,
        aggregate_type="EXECUTION_EVENT",
        aggregate_id=cast(str, event["event_id"]),
        correlation_id=cast(str, event["correlation_id"]),
        idempotency_scope="event-ingress/execution-stream-sim-001/1",
        idempotency_key_reference=cast(str, event["event_fingerprint"]),
        request_fingerprint=None,
        occurred_at_utc=cast(str, event["received_at_utc"]),
    )
    first = repository.append(record)
    replay = repository.append(record)
    conflict = build_replan_audit_record(
        action=record.action,
        aggregate_type=record.aggregate_type,
        aggregate_id="different-event",
        correlation_id=record.correlation_id,
        idempotency_scope=record.idempotency_scope,
        idempotency_key_reference=record.idempotency_key_reference,
        request_fingerprint=None,
        occurred_at_utc=record.occurred_at_utc,
    )
    _expect_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append(conflict),
    )
    listed = repository.list_for_aggregate(
        aggregate_type="EXECUTION_EVENT",
        aggregate_id=record.aggregate_id,
    )
    if first.replayed or not replay.replayed or len(listed) != 1:
        raise ValueError("replan audit exact replay contract failed")
    return {
        "append": 1,
        "exact_replay": 1,
        "idempotency_conflict": 1,
        "aggregate_rows": len(listed),
    }


def _database_guard_check(engine: Engine) -> dict[str, object]:
    rejected = 0
    for statement in (
        "UPDATE execution_event_ledger SET event_type = 'URGENT_ORDER'",
        "UPDATE replan_requests SET correlation_id = 'changed'",
        "DELETE FROM replan_request_events",
        "UPDATE replan_attempts SET attempt_number = 2",
        "UPDATE replan_results SET planning_run_terminal_state = 'FAILED'",
        "DELETE FROM replan_audit_records",
        "UPDATE replan_projection_checkpoints SET factory_id = 'changed'",
        "DELETE FROM replan_projection_checkpoints",
    ):
        try:
            with engine.begin() as connection:
                connection.execute(text(statement))
        except SQLAlchemyError:
            rejected += 1
    if rejected != 8:
        raise ValueError("database append-only/CAS guards are incomplete")
    return {"database_mutation_rejections": rejected, "expected": 8}


def _transaction_and_plane_check(
    root: Path,
    engine: Engine,
    event_repository: SqlAlchemyExecutionEventRepository,
) -> dict[str, object]:
    event = _sample(root, "execution-event.v1.synthetic.json")
    event["source_position"] = 2
    event["occurred_at_utc"] = "2026-08-27T06:00:01Z"
    event["received_at_utc"] = "2026-08-27T06:00:07Z"
    event["event_fingerprint"] = execution_event_fingerprint(event)
    event["event_id"] = (
        "execution-event-"
        + cast(str, event["event_fingerprint"]).removeprefix("sha256:")
    )
    audit = build_replan_audit_record(
        action=ReplanAuditAction.EXECUTION_EVENT_APPENDED,
        aggregate_type="EXECUTION_EVENT",
        aggregate_id=cast(str, event["event_id"]),
        correlation_id=cast(str, event["correlation_id"]),
        idempotency_scope="event-ingress/execution-stream-sim-001/2",
        idempotency_key_reference=cast(str, event["event_fingerprint"]),
        request_fingerprint=None,
        occurred_at_utc=cast(str, event["received_at_utc"]),
    )
    audit_repository = SqlAlchemyReplanAuditRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    try:
        with engine.begin() as connection:
            event_repository.append_in_transaction(connection, event)
            audit_repository.append_in_transaction(connection, audit)
            raise RuntimeError("synthetic caller rollback")
    except RuntimeError:
        pass
    if event_repository.get(cast(str, event["event_id"])) is not None:
        raise ValueError("caller-owned transaction did not roll back")
    production = SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.PRODUCTION
    )
    if production.get(cast(str, event["event_id"])) is not None:
        raise ValueError("repository query crossed a data-plane boundary")
    _expect_failure(
        PersistenceFailure.DATA_PLANE_MISMATCH,
        lambda: production.append(event),
    )
    return {
        "caller_transaction_rollback": 1,
        "cross_plane_reads": 0,
        "production_write_rejections": 1,
        "external_side_effects": 0,
    }


def run_persistence_checks(root: Path) -> dict[str, object]:
    """Run isolated SQLite evidence without claiming Production capacity."""

    with TemporaryDirectory(prefix="plantnexus-p4-replan-persistence-") as directory:
        database_path = Path(directory) / "replan.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = _alembic_config(root, database_url)
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            migration = _migration_check(engine)
            schedule_document = _sample(root, "schedule-version.v1.synthetic.json")
            schedule_repository = SqlAlchemyScheduleVersionRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            schedule_repository.put(schedule_document)
            event_repository = SqlAlchemyExecutionEventRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            event_evidence, event = _event_check(root, event_repository)
            checkpoint_repository = SqlAlchemyProjectionCheckpointRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            request_repository = SqlAlchemyReplanRequestRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            checkpoint_evidence, request, _ = _checkpoint_request_check(
                root, checkpoint_repository, request_repository
            )
            lineage_evidence, _ = _lineage_check(
                request,
                SqlAlchemyReplanLineageRepository(
                    engine, data_plane=WorkspaceDataPlane.SIMULATION
                ),
            )
            audit_evidence = _audit_check(
                event,
                SqlAlchemyReplanAuditRepository(
                    engine, data_plane=WorkspaceDataPlane.SIMULATION
                ),
            )
            guards = _database_guard_check(engine)
            transaction_plane = _transaction_and_plane_check(
                root, engine, event_repository
            )
            if schedule_repository.get("schedule-version-sim-001") != (
                schedule_document
            ):
                raise ValueError("P3 ScheduleVersion row changed under P4 persistence")
        finally:
            engine.dispose()

        command.downgrade(configuration, "0004_schedule_versions_audit_export_jobs")
        engine = create_engine(database_url)
        try:
            tables_after = set(inspect(engine).get_table_names())
            if _TABLES.intersection(tables_after) or "schedule_versions" not in (
                tables_after
            ):
                raise ValueError("0005 populated downgrade boundary is invalid")
            with engine.connect() as connection:
                p3_rows_after_downgrade = connection.execute(
                    text("SELECT count(*) FROM schedule_versions")
                ).scalar_one()
        finally:
            engine.dispose()
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            if not _TABLES <= set(inspect(engine).get_table_names()):
                raise ValueError("0005 re-upgrade did not recreate all P4 tables")
            with engine.connect() as connection:
                p4_rows_after_reupgrade = sum(
                    cast(
                        int,
                        connection.execute(
                            text(f"SELECT count(*) FROM {table}")
                        ).scalar_one(),
                    )
                    for table in _TABLES
                )
                p3_rows_after_reupgrade = connection.execute(
                    text("SELECT count(*) FROM schedule_versions")
                ).scalar_one()
            if p4_rows_after_reupgrade != 0 or p3_rows_after_reupgrade != 1:
                raise ValueError("0005 downgrade/re-upgrade retention boundary failed")
        finally:
            engine.dispose()
        command.downgrade(configuration, "base")

    checks = [
        _pass("migration-topology-and-indexes", migration),
        _pass("execution-event-append-replay-and-stream-position", event_evidence),
        _pass("projection-checkpoint-cas-and-request-lineage", checkpoint_evidence),
        _pass("planning-run-attempt-and-terminal-result-references", lineage_evidence),
        _pass("append-only-transaction-audit", audit_evidence),
        _pass("database-immutability-and-cas-guards", guards),
        _pass("transaction-rollback-and-plane-isolation", transaction_plane),
        _pass(
            "populated-downgrade-and-p3-retention",
            {
                "downgrade_target": "0004_schedule_versions_audit_export_jobs",
                "p3_rows_after_downgrade": p3_rows_after_downgrade,
                "p3_rows_after_reupgrade": p3_rows_after_reupgrade,
                "p4_rows_after_reupgrade": p4_rows_after_reupgrade,
            },
        ),
        _pass(
            "phase-capability-boundary",
            {
                "event_payload_interpretation": "NOT_IMPLEMENTED",
                "fact_projection_and_snapshot": "NOT_IMPLEMENTED",
                "solver_validator_simulator": "NOT_CALLED",
                "change_report_generation": "NOT_IMPLEMENTED",
                "schedule_version_creation": "NOT_IMPLEMENTED",
                "api_ui_worker_external": "NOT_IMPLEMENTED",
                "p5_capabilities": "ABSENT",
                "production_readiness_capacity_sla": "NOT_ESTABLISHED",
            },
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "diff_base": DIFF_BASE,
        "migration_revision": MIGRATION_REVISION,
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "counts": {
            "tables": len(_TABLES),
            "repositories": 5,
            "machine_checks": len(checks),
            "database_mutation_rejections": 8,
            "production_write_rejections": 1,
            "p3_rows_retained": 1,
        },
        "boundaries": {
            "dialect_evidence": "SQLITE_TEST_ONLY",
            "postgresql_ddl": "MIGRATION_DEFINED_NOT_CAPACITY_PROVEN",
            "business_projection": "NOT_IMPLEMENTED",
            "external_side_effects": "NONE",
            "production_readiness": "NOT_CLAIMED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_persistence_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "error_type": type(error).__name__,
            "error_message": "replan persistence evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "MIGRATION_REVISION",
    "REPORT_VERSION",
    "main",
    "run_persistence_checks",
]
