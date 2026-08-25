"""TASK-P3-08 transactional publication and supersession evidence."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any, cast

import pytest

from app.application.approval import ApprovalDecisionService
from app.application.publication import PublicationService, PublicationServiceResult
from app.application.schedule_version_lifecycle_check import (
    _service as lifecycle_service,
    _workspace_engine,
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import ApprovalDecisionContext
from app.domain.publication import (
    PublicationContext,
    PublicationError,
    PublicationFailure,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)
from app.infrastructure import (
    SqlAlchemyAuditRepository,
    SqlAlchemyPublicationRepository,
    SqlAlchemyScheduleVersionRepository,
    WorkspaceDataPlane,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def publication_workspace(tmp_path: Path) -> Iterator[tuple[Any, Any, Any]]:
    engine, configuration = _workspace_engine(ROOT, tmp_path / "publication.db")
    output, _ = load_fixed_validated_output(ROOT)
    try:
        yield engine, configuration, output
    finally:
        engine.dispose()
        from alembic import command as alembic_command

        alembic_command.downgrade(configuration, "base")


def _repositories(engine: Any) -> tuple[Any, Any, Any]:
    return (
        SqlAlchemyScheduleVersionRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
        SqlAlchemyAuditRepository(engine, data_plane=WorkspaceDataPlane.SIMULATION),
        SqlAlchemyPublicationRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
    )


def _approval_command(source: Mapping[str, object], key: str) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "APPROVE",
        "required_capability": "approve",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/APPROVE/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "READY_FOR_REVIEW",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Approve this synthetic Version for publication testing.",
        "correlation_id": f"correlation-{key}",
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _approval_context(source: Mapping[str, object]) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref="actor:p3-publication-integration-approver",
        authenticated=True,
        resolved_capabilities=frozenset({"approve"}),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T08:00:00Z",
        code_commit="uncommitted",
    )


def _reviewable(engine: Any, output: Any, key: str) -> dict[str, object]:
    return lifecycle_service(engine, "SIMULATION").create_reviewable(
        output,
        lifecycle_context(
            key,
            reason=f"Create publication integration source {key}.",
            correlation_id=f"correlation-p3-08-integration-source-{key}",
        ),
    ).schedule_version


def _approved(engine: Any, output: Any, key: str) -> dict[str, object]:
    source = _reviewable(engine, output, key)
    schedule_repository, audit_repository, _ = _repositories(engine)
    service = ApprovalDecisionService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
    )
    return service.execute(
        _approval_command(source, f"p3-integration-approve-{key}-0001"),
        _approval_context(source),
    ).new_version | {
        key: value
        for key, value in cast(
            dict[str, object], schedule_repository.get(cast(str, source["schedule_version_id"]))
        ).items()
        if key not in {"state"}
    }


def _context(source: Mapping[str, object], *capabilities: str) -> PublicationContext:
    decision = cast(dict[str, object], source["decision"])
    return PublicationContext(
        actor_ref="actor:p3-publication-integration",
        authenticated=True,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-publication-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T08:10:00Z",
        code_commit="uncommitted",
        parent_audit_event_id=cast(str, decision["audit_event_id"]),
    )


def _version_reference(
    source: Mapping[str, object], state: str
) -> dict[str, object]:
    return {
        "schedule_version_id": source["schedule_version_id"],
        "state": state,
        "content_fingerprint": source["content_fingerprint"],
    }


def _command(
    source: Mapping[str, object],
    *,
    key: str,
    previous: Mapping[str, object] | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "PUBLISH",
        "required_capability": "publish",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/PUBLISH/{source['schedule_version_id']}"
            "/SIMULATION_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "APPROVED",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "SIMULATION_INTERNAL",
        "reason": reason or "Publish this synthetic Version internally.",
        "correlation_id": f"correlation-{key}",
        "payload": {
            "previous_current_version": (
                None if previous is None else dict(previous)
            )
        },
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _service(
    engine: Any,
    *,
    audit_repository: Any | None = None,
    publication_repository: Any | None = None,
) -> PublicationService:
    schedule, audit, publication = _repositories(engine)
    return PublicationService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule,
        audit_repository=audit_repository or audit,
        publication_repository=publication_repository or publication,
    )


def _counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "schedule_versions": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM schedule_versions"
                ).scalar_one()
            ),
            "audit_events": int(
                connection.exec_driver_sql("SELECT COUNT(*) FROM audit_events").scalar_one()
            ),
            "publication_results": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM publication_results"
                ).scalar_one()
            ),
            "current_references": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM publication_current_references"
                ).scalar_one()
            ),
        }


def test_first_publish_is_atomic_replayable_and_conflicting_key_is_rejected(
    publication_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = publication_workspace
    source = _approved(engine, output, "a")
    command = _command(source, key="p3-integration-publish-first-0001")
    service = _service(engine)
    before = _counts(engine)

    result = service.execute(command, _context(source, "publish"))
    after_first = _counts(engine)
    replay = service.execute(command, _context(source, "publish"))

    assert result.document["replayed"] is False
    assert result.exact_replay is False
    assert replay.document["replayed"] is True
    assert replay.exact_replay is True
    assert replay.published_version == result.published_version
    assert _counts(engine) == after_first
    assert after_first == {
        **before,
        "audit_events": before["audit_events"] + 1,
        "publication_results": before["publication_results"] + 1,
        "current_references": before["current_references"] + 1,
    }
    schedule_repository, audit_repository, publication_repository = _repositories(
        engine
    )
    stored = schedule_repository.get(cast(str, source["schedule_version_id"]))
    assert stored is not None and stored["state"] == "PUBLISHED"
    assert stored["content"] == source["content"]
    current = publication_repository.get_current()
    assert current is not None
    assert current.schedule_version_id == source["schedule_version_id"]
    publish_audits = [
        event
        for event in audit_repository.list_for_aggregate(
            aggregate_type="SCHEDULE_VERSION",
            aggregate_id=cast(str, source["schedule_version_id"]),
        )
        if event["action"] == "PUBLISH"
    ]
    assert len(publish_audits) == 1

    conflict = _command(
        source,
        key="p3-integration-publish-first-0001",
        reason="A different reason reuses the publication key.",
    )
    with pytest.raises(PublicationError) as captured:
        service.execute(conflict, _context(source, "publish"))
    assert captured.value.reason is PublicationFailure.IDEMPOTENCY_CONFLICT
    assert _counts(engine) == after_first


def test_supersession_current_switch_and_historical_replay_are_atomic(
    publication_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = publication_workspace
    service = _service(engine)
    old = _approved(engine, output, "b")
    old_result = service.execute(
        _command(old, key="p3-integration-publish-old-0001"),
        _context(old, "publish"),
    )
    old_published = cast(dict[str, object], old_result.document["published_version"])
    old_content = canonical_workspace_bytes(cast(dict[str, object], old["content"]))

    new = _approved(engine, output, "c")
    new_command = _command(
        new,
        key="p3-integration-publish-new-0001",
        previous=old_published,
    )
    new_result = service.execute(new_command, _context(new, "publish"))
    schedule_repository, _, publication_repository = _repositories(engine)
    stored_old = schedule_repository.get(cast(str, old["schedule_version_id"]))
    stored_new = schedule_repository.get(cast(str, new["schedule_version_id"]))
    assert stored_old is not None and stored_old["state"] == "SUPERSEDED"
    assert canonical_workspace_bytes(
        cast(dict[str, object], stored_old["content"])
    ) == old_content
    assert stored_old["superseded_by"] == new_result.published_version
    assert stored_new is not None and stored_new["state"] == "PUBLISHED"
    current = publication_repository.get_current()
    assert current is not None
    assert current.schedule_version_id == new["schedule_version_id"]
    assert current.reference_revision == 1

    third = _approved(engine, output, "d")
    third_result = service.execute(
        _command(
            third,
            key="p3-integration-publish-third-0001",
            previous=new_result.published_version,
        ),
        _context(third, "publish"),
    )
    historical_replay = service.execute(new_command, _context(new, "publish"))
    current_after_replay = publication_repository.get_current()
    assert historical_replay.exact_replay
    assert historical_replay.published_version == new_result.published_version
    assert historical_replay.superseded_version == new_result.superseded_version
    assert current_after_replay is not None
    assert current_after_replay.schedule_version_id == third["schedule_version_id"]
    assert third_result.current_changed


class _FailingAuditRepository:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        return self._delegate.get(audit_event_id)

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Any:
        del connection, document
        raise RuntimeError("synthetic publication audit failure")


def test_audit_failure_rolls_back_publish_result_and_current_reference(
    publication_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = publication_workspace
    source = _approved(engine, output, "e")
    schedule_repository, audit_repository, _ = _repositories(engine)
    before = schedule_repository.get_record(cast(str, source["schedule_version_id"]))
    before_counts = _counts(engine)

    with pytest.raises(PublicationError) as captured:
        _service(
            engine,
            audit_repository=_FailingAuditRepository(audit_repository),
        ).execute(
            _command(source, key="p3-integration-publish-rollback-0001"),
            _context(source, "publish"),
        )
    assert captured.value.reason is PublicationFailure.PERSISTENCE_FAILED
    after = schedule_repository.get_record(cast(str, source["schedule_version_id"]))
    assert before is not None and after is not None
    assert after.document == before.document
    assert after.state_revision == before.state_revision
    assert _counts(engine) == before_counts


def test_two_publish_candidates_have_one_current_cas_winner(
    publication_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = publication_workspace
    initial = _approved(engine, output, "f")
    initial_result = _service(engine).execute(
        _command(initial, key="p3-integration-race-initial-0001"),
        _context(initial, "publish"),
    )
    candidates = {
        key: _approved(engine, output, key) for key in ("a", "b")
    }
    commands = {
        key: _command(
            candidate,
            key=f"p3-integration-race-publish-{key}-0001",
            previous=initial_result.published_version,
        )
        for key, candidate in candidates.items()
    }
    barrier = Barrier(2)

    def invoke(key: str) -> PublicationServiceResult:
        barrier.wait()
        return _service(engine).execute(
            commands[key], _context(candidates[key], "publish")
        )

    successes: list[PublicationServiceResult] = []
    failures: list[PublicationFailure] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in [executor.submit(invoke, key) for key in ("a", "b")]:
            try:
                successes.append(future.result())
            except PublicationError as error:
                failures.append(error.reason)

    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0] in {
        PublicationFailure.CURRENT_REFERENCE_CONFLICT,
        PublicationFailure.STALE_SOURCE,
        PublicationFailure.PERSISTENCE_FAILED,
    }
    schedule_repository, audit_repository, publication_repository = _repositories(
        engine
    )
    current = publication_repository.get_current()
    assert current is not None
    assert current.schedule_version_id == successes[0].current_schedule_version_id
    candidate_states: dict[str, str] = {
        key: cast(str, cast(dict[str, object], schedule_repository.get(
            cast(str, source["schedule_version_id"])
        ))["state"])
        for key, source in candidates.items()
    }
    assert sorted(candidate_states.values()) == ["APPROVED", "PUBLISHED"]
    candidate_publish_audits = sum(
        len(
            [
                event
                for event in audit_repository.list_for_aggregate(
                    aggregate_type="SCHEDULE_VERSION",
                    aggregate_id=cast(str, source["schedule_version_id"]),
                )
                if event["action"] == "PUBLISH"
            ]
        )
        for source in candidates.values()
    )
    assert candidate_publish_audits == 1
