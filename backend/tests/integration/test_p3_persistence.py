"""TASK-P3-03 durable workspace persistence and negative-boundary tests."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError

from app.domain.workspace_contracts import (
    export_job_fingerprint,
    publication_result_fingerprint,
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
from app.infrastructure.workspace_persistence_check import (
    main as persistence_check_main,
)

ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def workspace_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'workspace.db').as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def _sample(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ROOT / "schemas" / "samples" / name).read_text(encoding="utf-8")),
    )


def _approved(draft: dict[str, object]) -> dict[str, object]:
    approved = deepcopy(draft)
    approved.update(
        {
            "state": "APPROVED",
            "allowed_actions": ["view", "publish"],
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:sim-approver-001",
                "capability": "approve",
                "reason": "Approve the synthetic persistence fixture.",
                "decided_at_utc": "2026-08-24T01:06:00Z",
                "audit_event_id": "audit-event-approve-sim-001",
            },
        }
    )
    return approved


def _published(approved: dict[str, object]) -> dict[str, object]:
    published = deepcopy(approved)
    published.update(
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
    return published


def _put_published_schedule(
    repository: SqlAlchemyScheduleVersionRepository,
) -> dict[str, object]:
    draft = _sample("schedule-version.v1.synthetic.json")
    assert repository.put(draft).replayed is False
    ready = deepcopy(draft)
    ready.update(
        {"state": "READY_FOR_REVIEW", "allowed_actions": ["view", "approve", "reject"]}
    )
    assert (
        repository.transition(
            schedule_version_id=cast(str, draft["schedule_version_id"]),
            expected_state="DRAFT",
            expected_state_revision=0,
            candidate_document=ready,
        ).state_revision
        == 1
    )
    approved = _approved(ready)
    assert (
        repository.transition(
            schedule_version_id=cast(str, draft["schedule_version_id"]),
            expected_state="READY_FOR_REVIEW",
            expected_state_revision=1,
            candidate_document=approved,
        ).state_revision
        == 2
    )
    published = _published(approved)
    assert (
        repository.transition(
            schedule_version_id=cast(str, draft["schedule_version_id"]),
            expected_state="APPROVED",
            expected_state_revision=2,
            candidate_document=published,
        ).state_revision
        == 3
    )
    return published


def test_schedule_version_is_exact_replayable_content_immutable_and_cas_guarded(
    workspace_engine: Engine,
) -> None:
    repository = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    draft = _sample("schedule-version.v1.synthetic.json")
    assert repository.put(draft).replayed is False
    assert repository.put(draft).replayed is True
    stored_draft = repository.get_record(cast(str, draft["schedule_version_id"]))
    assert stored_draft is not None
    assert stored_draft.state_revision == 0

    conflict = deepcopy(draft)
    conflict["revision"] = 2
    with pytest.raises(WorkspacePersistenceError) as identity_error:
        repository.put(conflict)
    assert identity_error.value.reason is PersistenceFailure.IDENTITY_CONFLICT

    malformed = deepcopy(draft)
    malformed.pop("created_by_actor_ref")
    with pytest.raises(WorkspacePersistenceError) as malformed_error:
        repository.put(malformed)
    assert malformed_error.value.reason is PersistenceFailure.INVALID_DOCUMENT

    ready = deepcopy(draft)
    ready.update(
        {"state": "READY_FOR_REVIEW", "allowed_actions": ["view", "approve", "reject"]}
    )
    transitioned = repository.transition(
        schedule_version_id=cast(str, draft["schedule_version_id"]),
        expected_state="DRAFT",
        expected_state_revision=0,
        candidate_document=ready,
    )
    assert transitioned.state_revision == 1
    with pytest.raises(WorkspacePersistenceError) as stale_error:
        repository.transition(
            schedule_version_id=cast(str, draft["schedule_version_id"]),
            expected_state="DRAFT",
            expected_state_revision=0,
            candidate_document=ready,
        )
    assert stale_error.value.reason is PersistenceFailure.STATE_CONFLICT

    mutated = deepcopy(ready)
    mutated["revision"] = 2
    rejected = deepcopy(mutated)
    rejected["state"] = "REJECTED"
    rejected["decision"] = {
        "decision": "REJECTED",
        "actor_ref": "actor:sim-approver-001",
        "capability": "reject",
        "reason": "Reject mutation attempt.",
        "decided_at_utc": "2026-08-24T01:06:00Z",
        "audit_event_id": "audit-event-reject-sim-001",
    }
    with pytest.raises(WorkspacePersistenceError) as mutation_error:
        repository.transition(
            schedule_version_id=cast(str, draft["schedule_version_id"]),
            expected_state="READY_FOR_REVIEW",
            expected_state_revision=1,
            candidate_document=rejected,
        )
    assert mutation_error.value.reason is PersistenceFailure.STATE_CONFLICT

    production_repository = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.PRODUCTION
    )
    assert production_repository.get(cast(str, draft["schedule_version_id"])) is None
    with pytest.raises(WorkspacePersistenceError) as plane_error:
        production_repository.put(draft)
    assert plane_error.value.reason is PersistenceFailure.DATA_PLANE_MISMATCH

    production_published = _published(_approved(ready))
    production_published.update(
        {
            "data_plane": "PRODUCTION",
            "environment": "PRODUCTION",
            "synthetic": False,
        }
    )
    production_published.pop("synthetic_provenance")
    with pytest.raises(WorkspacePersistenceError) as production_state_error:
        production_repository.put(production_published)
    assert (
        production_state_error.value.reason is PersistenceFailure.DATA_PLANE_MISMATCH
    )

    with workspace_engine.begin() as connection:
        with pytest.raises(DatabaseError):
            connection.execute(
                text(
                    "UPDATE schedule_versions SET revision = 99 "
                    "WHERE schedule_version_id = :version_id"
                ),
                {"version_id": draft["schedule_version_id"]},
            )


def test_audit_append_only_exact_replay_and_transaction_rollback(
    workspace_engine: Engine,
) -> None:
    audit_repository = SqlAlchemyAuditRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    schedule_repository = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    event = _sample("audit-event.v1.synthetic.json")
    assert audit_repository.append(event).replayed is False
    assert audit_repository.append(event).replayed is True
    assert (
        len(
            audit_repository.list_for_aggregate(
                aggregate_type="SCHEDULE_VERSION",
                aggregate_id="schedule-version-sim-001",
            )
        )
        == 1
    )
    changed = deepcopy(event)
    changed["reason"] = "Different content for the same audit identity."
    with pytest.raises(WorkspacePersistenceError) as conflict:
        audit_repository.append(changed)
    assert conflict.value.reason is PersistenceFailure.IDEMPOTENCY_CONFLICT

    with workspace_engine.begin() as connection:
        with pytest.raises(DatabaseError):
            connection.execute(
                text("DELETE FROM audit_events WHERE audit_event_id = :audit_event_id"),
                {"audit_event_id": event["audit_event_id"]},
            )

    rolled_back = _sample("schedule-version.v1.synthetic.json")
    rolled_back["schedule_version_id"] = "schedule-version-rollback-001"
    with pytest.raises(RuntimeError):
        with workspace_engine.begin() as connection:
            schedule_repository.put_in_transaction(connection, rolled_back)
            raise RuntimeError("synthetic caller rollback")
    assert schedule_repository.get("schedule-version-rollback-001") is None


def test_publication_result_and_current_reference_are_atomic_and_idempotent(
    workspace_engine: Engine,
) -> None:
    schedule_repository = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    _put_published_schedule(schedule_repository)
    publication_repository = SqlAlchemyPublicationRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    publication = _sample("publication-result.v1.synthetic.json")
    first = publication_repository.persist_and_set_current(
        publication, expected_current=None
    )
    assert first.replayed is False
    assert first.current_changed is True
    assert first.current_reference is not None
    assert first.current_reference.schedule_version_id == "schedule-version-sim-001"
    replay = publication_repository.persist_and_set_current(
        publication, expected_current=None
    )
    assert replay.replayed is True
    assert replay.current_changed is False

    conflict = deepcopy(publication)
    idempotency = cast(dict[str, object], conflict["idempotency_reference"])
    idempotency["request_fingerprint"] = f"sha256:{'d' * 64}"
    conflict["result_fingerprint"] = publication_result_fingerprint(conflict)
    with pytest.raises(WorkspacePersistenceError) as error:
        publication_repository.persist_result(conflict)
    assert error.value.reason is PersistenceFailure.IDEMPOTENCY_CONFLICT

    second_draft = _sample("schedule-version.v1.synthetic.json")
    second_draft.update(
        {
            "schedule_version_id": "schedule-version-sim-002",
            "revision": 2,
            "parent_schedule_version": {
                "schedule_version_id": "schedule-version-sim-001",
                "state": "PUBLISHED",
                "content_fingerprint": second_draft["content_fingerprint"],
            },
        }
    )
    assert schedule_repository.put(second_draft).replayed is False
    second_ready = deepcopy(second_draft)
    second_ready.update(
        {"state": "READY_FOR_REVIEW", "allowed_actions": ["view", "approve", "reject"]}
    )
    schedule_repository.transition(
        schedule_version_id="schedule-version-sim-002",
        expected_state="DRAFT",
        expected_state_revision=0,
        candidate_document=second_ready,
    )
    second_approved = _approved(second_ready)
    schedule_repository.transition(
        schedule_version_id="schedule-version-sim-002",
        expected_state="READY_FOR_REVIEW",
        expected_state_revision=1,
        candidate_document=second_approved,
    )
    second_published = _published(second_approved)
    second_publication_evidence = cast(
        dict[str, object], second_published["publication"]
    )
    second_publication_evidence["publication_id"] = "publication-sim-002"
    schedule_repository.transition(
        schedule_version_id="schedule-version-sim-002",
        expected_state="APPROVED",
        expected_state_revision=2,
        candidate_document=second_published,
    )

    second_publication = deepcopy(publication)
    second_publication.update(
        {
            "publication_id": "publication-sim-002",
            "source_approved_version": {
                "schedule_version_id": "schedule-version-sim-002",
                "state": "APPROVED",
                "content_fingerprint": second_draft["content_fingerprint"],
            },
            "published_version": {
                "schedule_version_id": "schedule-version-sim-002",
                "state": "PUBLISHED",
                "content_fingerprint": second_draft["content_fingerprint"],
            },
            "previous_current_version": {
                "schedule_version_id": "schedule-version-sim-001",
                "state": "PUBLISHED",
                "content_fingerprint": second_draft["content_fingerprint"],
            },
            "superseded_version": {
                "schedule_version_id": "schedule-version-sim-001",
                "state": "SUPERSEDED",
                "content_fingerprint": second_draft["content_fingerprint"],
            },
            "published_at_utc": "2026-08-24T01:18:00Z",
            "audit_event_id": "audit-event-publish-sim-002",
        }
    )
    second_idempotency = cast(
        dict[str, object], second_publication["idempotency_reference"]
    )
    second_idempotency.update(
        {
            "scope": "SIMULATION/PUBLISH/schedule-version-sim-002/SIMULATION_INTERNAL",
            "key_reference": f"sha256:{'2' * 64}",
            "request_fingerprint": f"sha256:{'3' * 64}",
        }
    )
    second_publication["result_fingerprint"] = publication_result_fingerprint(
        second_publication
    )
    advanced = publication_repository.persist_and_set_current(
        second_publication,
        expected_current=first.current_reference,
    )
    assert advanced.current_changed is True
    assert advanced.current_reference is not None
    assert advanced.current_reference.schedule_version_id == "schedule-version-sim-002"
    assert advanced.current_reference.reference_revision == 1

    stale = deepcopy(second_publication)
    stale["publication_id"] = "publication-sim-stale-003"
    stale_idempotency = cast(dict[str, object], stale["idempotency_reference"])
    stale_idempotency.update(
        {
            "scope": "SIMULATION/PUBLISH/stale-cas-003/SIMULATION_INTERNAL",
            "key_reference": f"sha256:{'4' * 64}",
            "request_fingerprint": f"sha256:{'5' * 64}",
        }
    )
    stale["result_fingerprint"] = publication_result_fingerprint(stale)
    with pytest.raises(WorkspacePersistenceError) as stale_current:
        publication_repository.persist_and_set_current(
            stale,
            expected_current=first.current_reference,
        )
    assert stale_current.value.reason is PersistenceFailure.STATE_CONFLICT
    assert publication_repository.persist_result(stale).replayed is False

def test_export_job_claim_heartbeat_failure_retry_and_plane_isolation(
    workspace_engine: Engine,
) -> None:
    schedule_repository = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    _put_published_schedule(schedule_repository)
    repository = SqlAlchemyExportJobRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    created = _sample("export-job.v1.synthetic.json")
    assert repository.create(created).replayed is False
    assert repository.create(created).replayed is True

    with pytest.raises(WorkspacePersistenceError) as revision_type_error:
        repository.heartbeat(
            export_job_id="export-job-sim-001",
            expected_state_revision=True,
            expected_lease_reference=f"sha256:{'a' * 64}",
            candidate_document=created,
            observed_at_utc=datetime(2026, 8, 24, 1, 10, tzinfo=UTC),
            lease_expires_at_utc=datetime(2026, 8, 24, 1, 15, tzinfo=UTC),
        )
    assert revision_type_error.value.reason is PersistenceFailure.INVALID_DOCUMENT

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
    claimed = repository.transition(
        export_job_id="export-job-sim-001",
        expected_state="CREATED",
        expected_state_revision=0,
        candidate_document=exporting,
        observed_at_utc=datetime(2026, 8, 24, 1, 10, tzinfo=UTC),
        lease_expires_at_utc=datetime(2026, 8, 24, 1, 15, tzinfo=UTC),
    )
    assert claimed.state_revision == 1

    heartbeat = deepcopy(exporting)
    heartbeat.update(
        {
            "heartbeat_at_utc": "2026-08-24T01:11:00Z",
            "updated_at_utc": "2026-08-24T01:11:00Z",
        }
    )
    heartbeat["job_fingerprint"] = export_job_fingerprint(heartbeat)
    beat = repository.heartbeat(
        export_job_id="export-job-sim-001",
        expected_state_revision=1,
        expected_lease_reference=lease,
        candidate_document=heartbeat,
        observed_at_utc=datetime(2026, 8, 24, 1, 11, tzinfo=UTC),
        lease_expires_at_utc=datetime(2026, 8, 24, 1, 16, tzinfo=UTC),
    )
    assert beat.state_revision == 2

    with pytest.raises(WorkspacePersistenceError) as wrong_owner:
        repository.heartbeat(
            export_job_id="export-job-sim-001",
            expected_state_revision=2,
            expected_lease_reference=f"sha256:{'e' * 64}",
            candidate_document=heartbeat,
            observed_at_utc=datetime(2026, 8, 24, 1, 12, tzinfo=UTC),
            lease_expires_at_utc=datetime(2026, 8, 24, 1, 17, tzinfo=UTC),
        )
    assert wrong_owner.value.reason is PersistenceFailure.LEASE_CONFLICT

    failed = deepcopy(heartbeat)
    failed.update(
        {
            "state": "EXPORT_FAILED",
            "lease_reference": None,
            "heartbeat_at_utc": None,
            "error": {
                "error_namespace": "WORKSPACE_CONTROL",
                "reason": "EXPORT_FAILED",
                "message": "Synthetic exporter failure.",
            },
            "finished_at_utc": "2026-08-24T01:12:00Z",
            "updated_at_utc": "2026-08-24T01:12:00Z",
        }
    )
    failed["job_fingerprint"] = export_job_fingerprint(failed)
    failed_result = repository.transition(
        export_job_id="export-job-sim-001",
        expected_state="EXPORTING",
        expected_state_revision=2,
        expected_lease_reference=lease,
        candidate_document=failed,
        observed_at_utc=datetime(2026, 8, 24, 1, 12, tzinfo=UTC),
    )
    assert failed_result.state_revision == 3

    retry_lease = f"sha256:{'a' * 64}"
    retry = deepcopy(failed)
    retry.update(
        {
            "state": "EXPORTING",
            "attempt": 2,
            "lease_reference": retry_lease,
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
    assert retried.state_revision == 4
    stored = repository.get("export-job-sim-001")
    assert stored is not None
    assert stored.document["state"] == "EXPORTING"
    assert stored.document["attempt"] == 2

    with pytest.raises(WorkspacePersistenceError) as plane_error:
        SqlAlchemyExportJobRepository(
            workspace_engine, data_plane=WorkspaceDataPlane.PRODUCTION
        )
    assert plane_error.value.reason is PersistenceFailure.DATA_PLANE_MISMATCH


def test_p3_persistence_machine_report_is_complete(tmp_path: Path) -> None:
    report_path = tmp_path / "p3-persistence.json"
    assert (
        persistence_check_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-persistence-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-03"
    assert report["check_count"] == 8
    assert report["counts"]["tables"] == 5
    assert report["counts"]["repositories"] == 4
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"
