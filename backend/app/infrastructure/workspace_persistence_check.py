"""Emit machine-checkable TASK-P3-03 workspace persistence evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.domain.workspace_contracts import (
    export_job_fingerprint,
    publication_result_fingerprint,
    state_contract_evidence,
)
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.export_job_repository import SqlAlchemyExportJobRepository
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import (
    PersistenceFailure,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
)

REPORT_VERSION = "p3-persistence-report.v1"
TASK_ID = "TASK-P3-03"
MIGRATION_REVISION = "0004_schedule_versions_audit_export_jobs"

_TABLES = {
    "schedule_versions",
    "audit_events",
    "publication_results",
    "publication_current_references",
    "export_jobs",
}


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


def _ready(draft: dict[str, object]) -> dict[str, object]:
    document = deepcopy(draft)
    document.update(
        {
            "state": "READY_FOR_REVIEW",
            "allowed_actions": ["view", "approve", "reject"],
        }
    )
    return document


def _approved(ready: dict[str, object]) -> dict[str, object]:
    document = deepcopy(ready)
    document.update(
        {
            "state": "APPROVED",
            "allowed_actions": ["view", "publish"],
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:sim-approver-001",
                "capability": "approve",
                "reason": "Approve the synthetic persistence evidence.",
                "decided_at_utc": "2026-08-24T01:06:00Z",
                "audit_event_id": "audit-event-approve-sim-001",
            },
        }
    )
    return document


def _published(approved: dict[str, object]) -> dict[str, object]:
    document = deepcopy(approved)
    document.update(
        {
            "state": "PUBLISHED",
            "allowed_actions": ["view", "export"],
            "publication": {
                "publication_id": "publication-sim-001",
                "target": "SIMULATION_INTERNAL",
                "published_at_utc": "2026-08-24T01:08:00Z",
                "audit_event_id": "audit-event-publish-sim-001",
            },
        }
    )
    return document


def _migration_check(engine: Engine) -> dict[str, object]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not _TABLES <= tables:
        raise ValueError("P3 persistence table set is incomplete")
    index_count = sum(len(inspector.get_indexes(table)) for table in _TABLES)
    foreign_key_count = sum(len(inspector.get_foreign_keys(table)) for table in _TABLES)
    unique_count = sum(
        len(inspector.get_unique_constraints(table)) for table in _TABLES
    )
    return {
        "revision": MIGRATION_REVISION,
        "tables": sorted(_TABLES),
        "index_count": index_count,
        "foreign_key_count": foreign_key_count,
        "unique_constraint_count": unique_count,
        "dialect": "sqlite-test-only",
    }


def _schedule_check(
    root: Path,
    repository: SqlAlchemyScheduleVersionRepository,
) -> tuple[dict[str, object], dict[str, object]]:
    draft = _sample(root, "schedule-version.v1.synthetic.json")
    first = repository.put(draft)
    replay = repository.put(draft)
    if first.replayed or not replay.replayed:
        raise ValueError("ScheduleVersion insert/exact replay contract failed")
    changed = deepcopy(draft)
    changed["revision"] = 2
    _expect_failure(
        PersistenceFailure.IDENTITY_CONFLICT, lambda: repository.put(changed)
    )
    ready = _ready(draft)
    transitioned = repository.transition(
        schedule_version_id=cast(str, draft["schedule_version_id"]),
        expected_state="DRAFT",
        expected_state_revision=0,
        candidate_document=ready,
    )
    _expect_failure(
        PersistenceFailure.STATE_CONFLICT,
        lambda: repository.transition(
            schedule_version_id=cast(str, draft["schedule_version_id"]),
            expected_state="DRAFT",
            expected_state_revision=0,
            candidate_document=ready,
        ),
    )
    return (
        {
            "insert": 1,
            "exact_replay": 1,
            "identity_conflict": 1,
            "cas_success": 1,
            "stale_cas_rejection": 1,
            "state_revision": transitioned.state_revision,
        },
        ready,
    )


def _audit_check(
    root: Path, repository: SqlAlchemyAuditRepository
) -> dict[str, object]:
    event = _sample(root, "audit-event.v1.synthetic.json")
    first = repository.append(event)
    replay = repository.append(event)
    if first.replayed or not replay.replayed:
        raise ValueError("AuditEvent append/exact replay contract failed")
    conflict = deepcopy(event)
    conflict["reason"] = "Conflicting synthetic audit replay."
    _expect_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.append(conflict),
    )
    listed = repository.list_for_aggregate(
        aggregate_type="SCHEDULE_VERSION",
        aggregate_id="schedule-version-sim-001",
    )
    if len(listed) != 1:
        raise ValueError("AuditEvent aggregate index returned unexpected rows")
    return {
        "append": 1,
        "exact_replay": 1,
        "idempotency_conflict": 1,
        "aggregate_rows": len(listed),
    }


def _publication_check(
    root: Path,
    repository: SqlAlchemyPublicationRepository,
) -> dict[str, object]:
    publication = _sample(root, "publication-result.v1.synthetic.json")
    first = repository.persist_and_set_current(publication, expected_current=None)
    replay = repository.persist_and_set_current(publication, expected_current=None)
    if (
        first.replayed
        or not first.current_changed
        or not replay.replayed
        or replay.current_changed
    ):
        raise ValueError("publication persistence exact replay contract failed")
    conflict = deepcopy(publication)
    idempotency = cast(dict[str, object], conflict["idempotency_reference"])
    idempotency["request_fingerprint"] = f"sha256:{'d' * 64}"
    conflict["result_fingerprint"] = publication_result_fingerprint(conflict)
    _expect_failure(
        PersistenceFailure.IDEMPOTENCY_CONFLICT,
        lambda: repository.persist_result(conflict),
    )
    current = repository.get_current()
    if current is None:
        raise ValueError("current publication reference was not stored")
    return {
        "atomic_result_and_current": 1,
        "exact_replay": 1,
        "idempotency_conflict": 1,
        "current_reference_revision": current.reference_revision,
    }


def _export_check(
    root: Path,
    repository: SqlAlchemyExportJobRepository,
) -> dict[str, object]:
    created = _sample(root, "export-job.v1.synthetic.json")
    first = repository.create(created)
    replay = repository.create(created)
    if first.replayed or not replay.replayed:
        raise ValueError("ExportJob create/exact replay contract failed")
    lease = f"sha256:{'f' * 64}"
    exporting = deepcopy(created)
    exporting.update(
        {
            "state": "EXPORTING",
            "attempt": 1,
            "lease_reference": lease,
            "heartbeat_at_utc": "2026-08-24T01:10:00Z",
            "started_at_utc": "2026-08-24T01:10:00Z",
            "updated_at_utc": "2026-08-24T01:10:00Z",
        }
    )
    exporting["job_fingerprint"] = export_job_fingerprint(exporting)
    repository.transition(
        export_job_id="export-job-sim-001",
        expected_state="CREATED",
        expected_state_revision=0,
        candidate_document=exporting,
        observed_at_utc=datetime(2026, 8, 24, 1, 10, tzinfo=UTC),
        lease_expires_at_utc=datetime(2026, 8, 24, 1, 15, tzinfo=UTC),
    )
    heartbeat = deepcopy(exporting)
    heartbeat.update(
        {
            "heartbeat_at_utc": "2026-08-24T01:11:00Z",
            "updated_at_utc": "2026-08-24T01:11:00Z",
        }
    )
    heartbeat["job_fingerprint"] = export_job_fingerprint(heartbeat)
    repository.heartbeat(
        export_job_id="export-job-sim-001",
        expected_state_revision=1,
        expected_lease_reference=lease,
        candidate_document=heartbeat,
        observed_at_utc=datetime(2026, 8, 24, 1, 11, tzinfo=UTC),
        lease_expires_at_utc=datetime(2026, 8, 24, 1, 16, tzinfo=UTC),
    )
    _expect_failure(
        PersistenceFailure.LEASE_CONFLICT,
        lambda: repository.heartbeat(
            export_job_id="export-job-sim-001",
            expected_state_revision=2,
            expected_lease_reference=f"sha256:{'e' * 64}",
            candidate_document=heartbeat,
            observed_at_utc=datetime(2026, 8, 24, 1, 12, tzinfo=UTC),
            lease_expires_at_utc=datetime(2026, 8, 24, 1, 17, tzinfo=UTC),
        ),
    )
    failed = deepcopy(heartbeat)
    failed.update(
        {
            "state": "EXPORT_FAILED",
            "lease_reference": None,
            "heartbeat_at_utc": None,
            "error": {
                "error_namespace": "WORKSPACE_CONTROL",
                "reason": "EXPORT_FAILED",
                "message": "Synthetic persistence evidence failure.",
            },
            "finished_at_utc": "2026-08-24T01:12:00Z",
            "updated_at_utc": "2026-08-24T01:12:00Z",
        }
    )
    failed["job_fingerprint"] = export_job_fingerprint(failed)
    repository.transition(
        export_job_id="export-job-sim-001",
        expected_state="EXPORTING",
        expected_state_revision=2,
        expected_lease_reference=lease,
        candidate_document=failed,
        observed_at_utc=datetime(2026, 8, 24, 1, 12, tzinfo=UTC),
    )
    retry = deepcopy(failed)
    retry.update(
        {
            "state": "EXPORTING",
            "attempt": 2,
            "lease_reference": f"sha256:{'a' * 64}",
            "heartbeat_at_utc": "2026-08-24T01:13:00Z",
            "error": None,
            "finished_at_utc": None,
            "updated_at_utc": "2026-08-24T01:13:00Z",
        }
    )
    retry["job_fingerprint"] = export_job_fingerprint(retry)
    retried = repository.transition(
        export_job_id="export-job-sim-001",
        expected_state="EXPORT_FAILED",
        expected_state_revision=3,
        candidate_document=retry,
        observed_at_utc=datetime(2026, 8, 24, 1, 13, tzinfo=UTC),
        lease_expires_at_utc=datetime(2026, 8, 24, 1, 18, tzinfo=UTC),
    )
    return {
        "create": 1,
        "exact_replay": 1,
        "claim": 1,
        "heartbeat": 1,
        "wrong_lease_rejection": 1,
        "failure": 1,
        "retry": 1,
        "attempt": retry["attempt"],
        "state_revision": retried.state_revision,
    }


def _database_trigger_check(engine: Engine) -> dict[str, object]:
    rejected = 0
    for statement in (
        "UPDATE schedule_versions SET revision = 99",
        "DELETE FROM audit_events",
        "UPDATE publication_results SET target = 'WORKSPACE_INTERNAL'",
        "DELETE FROM export_jobs",
    ):
        try:
            with engine.begin() as connection:
                connection.execute(text(statement))
        except SQLAlchemyError:
            rejected += 1
        else:
            raise ValueError("database immutability trigger did not reject mutation")
    return {"database_mutation_rejections": rejected, "expected": 4}


def _transaction_and_plane_check(
    root: Path,
    engine: Engine,
    schedule_repository: SqlAlchemyScheduleVersionRepository,
) -> dict[str, object]:
    rolled_back = _sample(root, "schedule-version.v1.synthetic.json")
    rolled_back["schedule_version_id"] = "schedule-version-rollback-evidence"
    try:
        with engine.begin() as connection:
            schedule_repository.put_in_transaction(connection, rolled_back)
            raise RuntimeError("synthetic caller rollback")
    except RuntimeError:
        pass
    if schedule_repository.get("schedule-version-rollback-evidence") is not None:
        raise ValueError("caller-owned transaction did not roll back")
    production = SqlAlchemyScheduleVersionRepository(
        engine, data_plane=WorkspaceDataPlane.PRODUCTION
    )
    if production.get("schedule-version-sim-001") is not None:
        raise ValueError("repository query crossed a data-plane boundary")
    _expect_failure(
        PersistenceFailure.DATA_PLANE_MISMATCH, lambda: production.put(rolled_back)
    )
    _expect_failure(
        PersistenceFailure.DATA_PLANE_MISMATCH,
        lambda: SqlAlchemyExportJobRepository(
            engine, data_plane=WorkspaceDataPlane.PRODUCTION
        ),
    )
    return {
        "caller_transaction_rollback": 1,
        "cross_plane_reads": 0,
        "plane_mismatch_rejections": 2,
    }


def run_persistence_checks(root: Path) -> dict[str, object]:
    """Run isolated SQLite evidence without claiming Production capacity."""

    with TemporaryDirectory(prefix="plantnexus-p3-persistence-") as directory:
        database_path = Path(directory) / "workspace.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = _alembic_config(root, database_url)
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            migration = _migration_check(engine)
            schedule_repository = SqlAlchemyScheduleVersionRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            schedule_evidence, ready = _schedule_check(root, schedule_repository)
            approved = _approved(ready)
            schedule_repository.transition(
                schedule_version_id="schedule-version-sim-001",
                expected_state="READY_FOR_REVIEW",
                expected_state_revision=1,
                candidate_document=approved,
            )
            published = _published(approved)
            schedule_repository.transition(
                schedule_version_id="schedule-version-sim-001",
                expected_state="APPROVED",
                expected_state_revision=2,
                candidate_document=published,
            )
            audit = _audit_check(
                root,
                SqlAlchemyAuditRepository(
                    engine, data_plane=WorkspaceDataPlane.SIMULATION
                ),
            )
            publication = _publication_check(
                root,
                SqlAlchemyPublicationRepository(
                    engine, data_plane=WorkspaceDataPlane.SIMULATION
                ),
            )
            export = _export_check(
                root,
                SqlAlchemyExportJobRepository(
                    engine, data_plane=WorkspaceDataPlane.SIMULATION
                ),
            )
            triggers = _database_trigger_check(engine)
            transaction_and_plane = _transaction_and_plane_check(
                root, engine, schedule_repository
            )
        finally:
            engine.dispose()

        command.downgrade(configuration, "0003_planning_snapshots")
        engine = create_engine(database_url)
        try:
            tables_after = set(inspect(engine).get_table_names())
            if _TABLES.intersection(tables_after) or "planning_snapshots" not in (
                tables_after
            ):
                raise ValueError("0004 populated downgrade boundary is invalid")
        finally:
            engine.dispose()
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            if not _TABLES <= set(inspect(engine).get_table_names()):
                raise ValueError("0004 re-upgrade did not recreate all tables")
            with engine.connect() as connection:
                count = connection.execute(
                    text("SELECT count(*) FROM schedule_versions")
                ).scalar_one()
                if count != 0:
                    raise ValueError(
                        "destructive non-production downgrade retained P3 rows"
                    )
        finally:
            engine.dispose()
        command.downgrade(configuration, "base")

    state_evidence = state_contract_evidence()
    checks = [
        _pass("migration-topology-and-indexes", migration),
        _pass("schedule-version-insert-immutability-and-cas", schedule_evidence),
        _pass("append-only-audit-and-exact-replay", audit),
        _pass("publication-result-and-current-reference", publication),
        _pass("export-job-state-attempt-and-lease", export),
        _pass("database-immutability-guards", triggers),
        _pass("transaction-rollback-and-plane-isolation", transaction_and_plane),
        _pass(
            "populated-downgrade-and-phase-boundary",
            {
                "downgrade_target": "0003_planning_snapshots",
                "p3_rows_after_reupgrade": 0,
                "schedule_pairs": len(
                    cast(list[Any], state_evidence["schedule_pairs"])
                ),
                "export_pairs": len(cast(list[Any], state_evidence["export_pairs"])),
                "approval_publish_export_execution": "NOT_IMPLEMENTED",
                "api_ui_worker_external_storage": "NOT_IMPLEMENTED",
                "production_capacity_backup_restore": "NOT_ESTABLISHED",
                "p4_capabilities": "ABSENT",
            },
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "migration_revision": MIGRATION_REVISION,
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "tables": len(_TABLES),
            "repositories": 4,
            "machine_checks": len(checks),
            "database_mutation_rejections": 4,
            "plane_mismatch_rejections": 2,
        },
        "boundaries": {
            "dialect_evidence": "SQLITE_TEST_ONLY",
            "postgresql_ddl": "MIGRATION_DEFINED_NOT_CAPACITY_PROVEN",
            "business_actions": "NOT_IMPLEMENTED",
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
            "error_type": type(error).__name__,
            "error_message": "persistence evidence check failed",
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


__all__ = ["MIGRATION_REVISION", "REPORT_VERSION", "main", "run_persistence_checks"]
