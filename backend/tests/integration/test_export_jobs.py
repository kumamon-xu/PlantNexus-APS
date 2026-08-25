"""TEST-EXPORT-JOB-001: durable lifecycle, retries, leases, audit, and rollback."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.application.export_jobs import ExportJobService
from app.domain.export_job import (
    ExportJobContext,
    ExportJobError,
    ExportJobFailure,
    ExportJobRequest,
    export_job_identity,
)
from app.domain.workspace_contracts import require_workspace_document
from app.infrastructure import (
    SqlAlchemyAuditRepository,
    SqlAlchemyExportJobRepository,
    SqlAlchemyScheduleVersionRepository,
    WorkspaceDataPlane,
)


ROOT = Path(__file__).resolve().parents[3]


def _sample(name: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((ROOT / "schemas/samples" / name).read_text(encoding="utf-8")))


def _configuration(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend/migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Engine]:
    url = f"sqlite:///{(tmp_path / 'export-jobs.db').as_posix()}"
    config = _configuration(url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


def _repositories(engine: Engine) -> tuple[Any, Any, Any]:
    return (
        SqlAlchemyScheduleVersionRepository(engine, data_plane=WorkspaceDataPlane.SIMULATION),
        SqlAlchemyExportJobRepository(engine, data_plane=WorkspaceDataPlane.SIMULATION),
        SqlAlchemyAuditRepository(engine, data_plane=WorkspaceDataPlane.SIMULATION),
    )


def _published_fixture(engine: Engine) -> tuple[dict[str, object], dict[str, object]]:
    schedule = _sample("schedule-version.v1.synthetic.json")
    publication = _sample("publication-result.v1.synthetic.json")
    schedule.update(
        {
            "state": "PUBLISHED",
            "decision": {
                "decision": "APPROVED", "actor_ref": "actor:export-approver", "capability": "approve",
                "reason": "Approve synthetic export integration source.", "decided_at_utc": "2026-08-25T00:00:00Z",
                "audit_event_id": "audit-export-approval-parent",
            },
            "publication": {
                "publication_id": publication["publication_id"], "target": "SIMULATION_INTERNAL",
                "published_at_utc": publication["published_at_utc"], "audit_event_id": publication["audit_event_id"],
            },
            "allowed_actions": ["view", "export"],
        }
    )
    require_workspace_document(schedule)
    schedule_repository, _, audit_repository = _repositories(engine)
    schedule_repository.put(schedule)
    reference = {
        "schedule_version_id": schedule["schedule_version_id"],
        "state": "PUBLISHED",
        "content_fingerprint": schedule["content_fingerprint"],
    }
    parent = _sample("audit-event.v1.synthetic.json")
    parent.update(
        {
            "audit_event_id": publication["audit_event_id"], "occurred_at_utc": publication["published_at_utc"],
            "actor_ref": "actor:export-publisher", "resolved_capability": "publish", "action": "PUBLISH",
            "aggregate_type": "SCHEDULE_VERSION", "aggregate_id": schedule["schedule_version_id"],
            "target": "SIMULATION_INTERNAL", "intent_type": "PUBLICATION", "reason": "Publish synthetic export integration source.",
            "idempotency_reference": None, "lineage": deepcopy(schedule["lineage"]),
            "before_state": "APPROVED", "after_state": "PUBLISHED",
            "source_version": {**reference, "state": "APPROVED"}, "new_version": reference,
            "correlation_id": "correlation-export-publication", "parent_audit_event_id": None,
            "code_commit": "uncommitted",
        }
    )
    require_workspace_document(parent)
    audit_repository.append(parent)
    return schedule, publication


def _request(schedule: Mapping[str, object], key: str) -> ExportJobRequest:
    return ExportJobRequest(
        schedule_version_id=cast(str, schedule["schedule_version_id"]),
        expected_content_fingerprint=cast(str, schedule["content_fingerprint"]),
        raw_idempotency_key=key,
        reason="Create synthetic standard export.",
        correlation_id=f"correlation-{key}",
        environment="TEST",
        synthetic_provenance=cast(Mapping[str, object], schedule["synthetic_provenance"]),
    )


def _context(at: str, *, schedule_id: str, job_ids: frozenset[str] = frozenset()) -> ExportJobContext:
    return ExportJobContext(
        actor_ref="actor:export-integration", authenticated=True,
        resolved_capabilities=frozenset({"export"}), schedule_version_scope=frozenset({schedule_id}),
        export_job_scope=job_ids, auth_policy_version="simulation-export-policy.v1",
        production_binding=False, occurred_at_utc=at, code_commit="uncommitted",
    )


def _service(engine: Engine, *, audit_repository: Any | None = None) -> ExportJobService:
    schedule, jobs, audits = _repositories(engine)
    return ExportJobService(
        transaction_factory=engine.begin, schedule_repository=schedule,
        export_job_repository=jobs, audit_repository=audit_repository or audits,
    )


def test_create_replay_claim_heartbeat_fail_retry_and_complete(workspace: Engine) -> None:
    schedule, publication = _published_fixture(workspace)
    request = _request(schedule, "export-integration-key-0001")
    identity = export_job_identity(request)
    create_context = _context("2026-08-25T00:02:00Z", schedule_id=cast(str, schedule["schedule_version_id"]))
    service = _service(workspace)
    created = service.create(request, create_context, publication_result=publication)
    replay = service.create(request, create_context, publication_result=publication)
    assert created.document["state"] == "CREATED"
    assert replay.exact_replay is True
    with pytest.raises(ExportJobError) as conflict:
        service.create(
            replace(request, reason="Different request with the same key."),
            create_context,
            publication_result=publication,
        )
    assert conflict.value.reason is ExportJobFailure.IDEMPOTENCY_CONFLICT

    scope = frozenset({identity.export_job_id})
    claimed = service.claim(
        identity.export_job_id, _context("2026-08-25T00:03:00Z", schedule_id=request.schedule_version_id, job_ids=scope),
        owner_reference="worker:integration", lease_expires_at_utc=datetime(2026, 8, 25, 0, 10, tzinfo=UTC),
    )
    lease = cast(str, claimed.document["lease_reference"])
    heartbeat = service.heartbeat(
        identity.export_job_id, _context("2026-08-25T00:04:00Z", schedule_id=request.schedule_version_id, job_ids=scope),
        expected_lease_reference=lease, lease_expires_at_utc=datetime(2026, 8, 25, 0, 11, tzinfo=UTC),
    )
    assert heartbeat.document["state"] == "EXPORTING"
    failed = service.fail(
        identity.export_job_id, _context("2026-08-25T00:05:00Z", schedule_id=request.schedule_version_id, job_ids=scope),
        expected_lease_reference=lease,
    )
    assert failed.document["state"] == "EXPORT_FAILED"
    retried = service.claim(
        identity.export_job_id, _context("2026-08-25T00:06:00Z", schedule_id=request.schedule_version_id, job_ids=scope),
        owner_reference="worker:integration", lease_expires_at_utc=datetime(2026, 8, 25, 0, 12, tzinfo=UTC),
    )
    retry_lease = cast(str, retried.document["lease_reference"])
    completed = service.complete(
        identity.export_job_id, _context("2026-08-25T00:07:00Z", schedule_id=request.schedule_version_id, job_ids=scope),
        expected_lease_reference=retry_lease,
        artifact_manifest={
            "export_manifest_version": "export-manifest.v2", "package_id": "export-package-" + "1" * 64,
            "manifest_fingerprint": "sha256:" + "2" * 64, "storage_reference": "sha256:" + "3" * 64,
        },
    )
    assert completed.document["state"] == "EXPORTED"
    assert completed.document["attempt"] == 2
    _, jobs, audits = _repositories(workspace)
    assert jobs.get(identity.export_job_id).document == completed.document  # type: ignore[union-attr]
    events = audits.list_for_aggregate(aggregate_type="EXPORT_JOB", aggregate_id=identity.export_job_id)
    assert [event["after_state"] for event in events] == ["CREATED", "EXPORTING", "EXPORT_FAILED", "EXPORTING", "EXPORTED"]


def test_cancel_and_expired_lease_recovery_are_durable(workspace: Engine) -> None:
    schedule, publication = _published_fixture(workspace)
    service = _service(workspace)
    first = _request(schedule, "export-cancel-key-000001")
    first_id = export_job_identity(first).export_job_id
    service.create(first, _context("2026-08-25T01:00:00Z", schedule_id=first.schedule_version_id), publication_result=publication)
    cancelled = service.cancel(first_id, _context("2026-08-25T01:01:00Z", schedule_id=first.schedule_version_id, job_ids=frozenset({first_id})))
    assert cancelled.document["state"] == "CANCELLED"

    second = _request(schedule, "export-recovery-key-0001")
    second_id = export_job_identity(second).export_job_id
    service.create(second, _context("2026-08-25T01:02:00Z", schedule_id=second.schedule_version_id), publication_result=publication)
    claimed = service.claim(
        second_id, _context("2026-08-25T01:03:00Z", schedule_id=second.schedule_version_id, job_ids=frozenset({second_id})),
        owner_reference="worker:recovery", lease_expires_at_utc=datetime(2026, 8, 25, 1, 4, tzinfo=UTC),
    )
    recovered = service.fail(
        second_id, _context("2026-08-25T01:05:00Z", schedule_id=second.schedule_version_id, job_ids=frozenset({second_id})),
        expected_lease_reference=cast(str, claimed.document["lease_reference"]), expired_recovery=True,
    )
    assert recovered.document["state"] == "EXPORT_FAILED"


def test_audit_failure_rolls_back_state_transition(workspace: Engine) -> None:
    schedule, publication = _published_fixture(workspace)
    request = _request(schedule, "export-rollback-key-0001")
    identity = export_job_identity(request)
    service = _service(workspace)
    service.create(request, _context("2026-08-25T02:00:00Z", schedule_id=request.schedule_version_id), publication_result=publication)
    _, jobs, audits = _repositories(workspace)

    class FailingAudit:
        def get(self, audit_event_id: str):  # type: ignore[no-untyped-def]
            return audits.get(audit_event_id)
        def append(self, document: Mapping[str, object]):  # type: ignore[no-untyped-def]
            return audits.append(document)
        def append_in_transaction(self, connection: object, document: Mapping[str, object]) -> object:
            raise RuntimeError("injected audit failure")

    failing = _service(workspace, audit_repository=FailingAudit())
    with pytest.raises(ExportJobError) as captured:
        failing.claim(
            identity.export_job_id, _context("2026-08-25T02:01:00Z", schedule_id=request.schedule_version_id, job_ids=frozenset({identity.export_job_id})),
            owner_reference="worker:rollback", lease_expires_at_utc=datetime(2026, 8, 25, 2, 10, tzinfo=UTC),
        )
    assert captured.value.reason is ExportJobFailure.PERSISTENCE_FAILED
    stored = jobs.get(identity.export_job_id)
    assert stored is not None and stored.document["state"] == "CREATED" and stored.state_revision == 0
