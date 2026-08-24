from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, Never, cast

import pytest

from app.application.schedule_commands import ScheduleCommandService
from app.application.schedule_version_lifecycle_check import (
    _service,
    _workspace_engine,
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.schedule_commands import (
    ScheduleCommandContext,
    ScheduleCommandError,
    ScheduleCommandFailure,
    schedule_command_identity,
)
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.infrastructure import (
    SqlAlchemyAuditRepository,
    SqlAlchemyScheduleVersionRepository,
    WorkspaceDataPlane,
)
from app.planning.validation import ProblemScheduleValidator


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def command_workspace(tmp_path: Path) -> Iterator[tuple[Any, Any, Any, Any]]:
    engine, configuration = _workspace_engine(ROOT, tmp_path / "commands.db")
    output, _ = load_fixed_validated_output(ROOT)
    lifecycle = _service(engine, "SIMULATION").create_reviewable(
        output, lifecycle_context()
    )
    try:
        yield engine, configuration, output, lifecycle
    finally:
        engine.dispose()
        from alembic import command as alembic_command

        alembic_command.downgrade(configuration, "base")


def _repositories(engine: Any) -> tuple[Any, Any]:
    return (
        SqlAlchemyScheduleVersionRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
        SqlAlchemyAuditRepository(engine, data_plane=WorkspaceDataPlane.SIMULATION),
    )


def _context(parent_audit_event_id: str, *capabilities: str) -> ScheduleCommandContext:
    return ScheduleCommandContext(
        actor_ref="actor:p3-command-integration",
        resolved_capabilities=frozenset(capabilities),
        auth_policy_version="simulation-command-policy.v1",
        occurred_at_utc="2026-08-24T10:30:00Z",
        code_commit="uncommitted",
        parent_audit_event_id=parent_audit_event_id,
    )


def _move_command(
    source: Mapping[str, object],
    *,
    key: str,
    start_at_utc: str = "2026-09-01T00:03:00Z",
    end_at_utc: str = "2026-09-01T00:04:00Z",
    reason: str = "Move one synthetic operation by one tick.",
) -> dict[str, object]:
    content = cast(Mapping[str, object], source["content"])
    assignment = cast(list[Mapping[str, object]], content["assignments"])[0]
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "MOVE_OPERATION",
        "required_capability": "edit",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/MOVE_OPERATION/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": source["state"],
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": source["synthetic"],
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": reason,
        "correlation_id": f"correlation-{key}",
        "payload": {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": start_at_utc,
            "end_at_utc": end_at_utc,
        },
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _submit_command(
    source: Mapping[str, object],
    *,
    key: str,
    reason: str = "Submit one freshly validated manual DRAFT for review.",
) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "SUBMIT_FOR_REVIEW",
        "required_capability": "edit",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/SUBMIT_FOR_REVIEW/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": source["state"],
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": source["synthetic"],
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": reason,
        "correlation_id": f"correlation-{key}",
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "schedule_versions": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM schedule_versions"
                ).scalar_one()
            ),
            "audit_events": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM audit_events"
                ).scalar_one()
            ),
        }


def test_command_transaction_exact_replay_conflict_and_validation_failure_have_honest_side_effects(
    command_workspace: tuple[Any, Any, Any, Any],
) -> None:
    engine, _, output, lifecycle = command_workspace
    schedule_repository, audit_repository = _repositories(engine)
    service = ScheduleCommandService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
        validator_factory=ProblemScheduleValidator,
    )
    source_before = schedule_repository.get(lifecycle.schedule_version_id)
    command = _move_command(
        lifecycle.schedule_version,
        key="p3-integration-move1",
    )
    context = _context(lifecycle.audit_event_id, "edit")

    first = service.execute(command, output.problem, context)
    replay = service.execute(command, output.problem, context)
    stored = schedule_repository.get(
        cast(str, first.new_version["schedule_version_id"])
    )
    audits = audit_repository.list_for_aggregate(
        aggregate_type="SCHEDULE_VERSION",
        aggregate_id=cast(str, first.new_version["schedule_version_id"]),
    )

    assert not first.exact_replay
    assert replay.exact_replay
    assert replay.new_version == first.new_version
    assert stored is not None and stored["state"] == "DRAFT"
    assert stored["parent_schedule_version"] == first.source_version
    assert len(audits) == 1 and audits[0]["action"] == "EDIT_SCHEDULE"
    assert schedule_repository.get(lifecycle.schedule_version_id) == source_before
    assert _counts(engine) == {"schedule_versions": 2, "audit_events": 2}

    conflicting = _move_command(
        lifecycle.schedule_version,
        key="p3-integration-move1",
        reason="Reuse the same key with a different command reason.",
    )
    with pytest.raises(ScheduleCommandError) as captured:
        service.execute(conflicting, output.problem, context)
    assert captured.value.reason is ScheduleCommandFailure.IDEMPOTENCY_CONFLICT
    assert _counts(engine) == {"schedule_versions": 2, "audit_events": 2}

    invalid = _move_command(
        lifecycle.schedule_version,
        key="p3-integration-invalid1",
        start_at_utc="2026-09-01T00:00:00Z",
        end_at_utc="2026-09-01T00:01:00Z",
    )
    with pytest.raises(ScheduleCommandError) as invalid_captured:
        service.execute(invalid, output.problem, context)
    assert invalid_captured.value.reason is ScheduleCommandFailure.VALIDATION_FAILED
    assert _counts(engine) == {"schedule_versions": 2, "audit_events": 2}


def test_manual_draft_submit_transitions_same_content_to_ready_with_exact_replay(
    command_workspace: tuple[Any, Any, Any, Any],
) -> None:
    engine, _, output, lifecycle = command_workspace
    schedule_repository, audit_repository = _repositories(engine)
    service = ScheduleCommandService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
        validator_factory=ProblemScheduleValidator,
    )
    move = service.execute(
        _move_command(lifecycle.schedule_version, key="p3-submit-move-001"),
        output.problem,
        _context(lifecycle.audit_event_id, "edit"),
    )
    draft_id = cast(str, move.new_version["schedule_version_id"])
    draft = schedule_repository.get(draft_id)
    assert draft is not None and draft["state"] == "DRAFT"
    draft_content = deepcopy(draft["content"])
    draft_fingerprint = draft["content_fingerprint"]
    submit = _submit_command(draft, key="p3-submit-ready-001")
    submit_context = _context(move.audit_event_id, "edit")

    first = service.execute(submit, output.problem, submit_context)
    replay = service.execute(submit, output.problem, submit_context)
    ready = schedule_repository.get(draft_id)
    audits = audit_repository.list_for_aggregate(
        aggregate_type="SCHEDULE_VERSION",
        aggregate_id=draft_id,
    )

    assert not first.exact_replay
    assert replay.exact_replay
    assert first.new_version == replay.new_version
    assert first.source_version["state"] == "DRAFT"
    assert first.new_version["state"] == "READY_FOR_REVIEW"
    assert ready is not None and ready["state"] == "READY_FOR_REVIEW"
    assert ready["content"] == draft_content
    assert ready["content_fingerprint"] == draft_fingerprint
    assert ready["decision"] is None
    assert {audit["action"] for audit in audits} == {
        "EDIT_SCHEDULE",
        "SUBMIT_FOR_REVIEW",
    }
    assert _counts(engine) == {"schedule_versions": 2, "audit_events": 3}

    with pytest.raises(ScheduleCommandError) as unauthorized:
        service.execute(
            submit,
            output.problem,
            _context(move.audit_event_id),
        )
    assert unauthorized.value.reason is ScheduleCommandFailure.UNAUTHORIZED
    assert _counts(engine) == {"schedule_versions": 2, "audit_events": 3}

    conflicting = _submit_command(
        draft,
        key="p3-submit-ready-001",
        reason="Reuse the same submit key for a different request.",
    )
    with pytest.raises(ScheduleCommandError) as captured:
        service.execute(conflicting, output.problem, submit_context)
    assert captured.value.reason is ScheduleCommandFailure.IDEMPOTENCY_CONFLICT
    assert _counts(engine) == {"schedule_versions": 2, "audit_events": 3}


class _FailingAuditRepository:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        return cast(dict[str, object] | None, self._delegate.get(audit_event_id))

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Never:
        del connection, document
        raise RuntimeError("sanitized injected audit failure")


def test_audit_failure_rolls_back_new_schedule_version(
    command_workspace: tuple[Any, Any, Any, Any],
) -> None:
    engine, _, output, lifecycle = command_workspace
    schedule_repository, audit_repository = _repositories(engine)
    command = _move_command(
        lifecycle.schedule_version,
        key="p3-integration-rollback1",
    )
    identity = schedule_command_identity(command, data_plane="SIMULATION")
    service = ScheduleCommandService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=_FailingAuditRepository(audit_repository),
        validator_factory=ProblemScheduleValidator,
    )

    with pytest.raises(ScheduleCommandError) as captured:
        service.execute(
            command,
            output.problem,
            _context(lifecycle.audit_event_id, "edit"),
        )

    assert captured.value.reason is ScheduleCommandFailure.PERSISTENCE_FAILED
    assert schedule_repository.get(identity.schedule_version_id) is None
    assert _counts(engine) == {"schedule_versions": 1, "audit_events": 1}


def test_audit_failure_rolls_back_manual_draft_ready_transition(
    command_workspace: tuple[Any, Any, Any, Any],
) -> None:
    engine, _, output, lifecycle = command_workspace
    schedule_repository, audit_repository = _repositories(engine)
    service = ScheduleCommandService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
        validator_factory=ProblemScheduleValidator,
    )
    move = service.execute(
        _move_command(lifecycle.schedule_version, key="p3-submit-rollback-move1"),
        output.problem,
        _context(lifecycle.audit_event_id, "edit"),
    )
    draft_id = cast(str, move.new_version["schedule_version_id"])
    draft = schedule_repository.get(draft_id)
    assert draft is not None
    before_counts = _counts(engine)
    failing_service = ScheduleCommandService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=_FailingAuditRepository(audit_repository),
        validator_factory=ProblemScheduleValidator,
    )

    with pytest.raises(ScheduleCommandError) as captured:
        failing_service.execute(
            _submit_command(draft, key="p3-submit-rollback-ready1"),
            output.problem,
            _context(move.audit_event_id, "edit"),
        )

    stored = schedule_repository.get_record(draft_id)
    assert captured.value.reason is ScheduleCommandFailure.PERSISTENCE_FAILED
    assert stored is not None and stored.document["state"] == "DRAFT"
    assert stored.state_revision == 0
    assert _counts(engine) == before_counts


@pytest.mark.parametrize("historical_state", ["REJECTED", "PUBLISHED"])
def test_historical_source_derives_new_draft_without_mutating_source_state(
    command_workspace: tuple[Any, Any, Any, Any], historical_state: str
) -> None:
    engine, _, output, lifecycle = command_workspace
    schedule_repository, audit_repository = _repositories(engine)
    historical = deepcopy(lifecycle.schedule_version)
    historical["schedule_version_id"] = (
        f"schedule-version-history-{historical_state.lower()}"
    )
    historical["state"] = historical_state
    historical["allowed_actions"] = ["view", "edit", "lock"]
    if historical_state == "REJECTED":
        historical["decision"] = {
            "decision": "REJECTED",
            "actor_ref": "actor:p3-history",
            "capability": "reject",
            "reason": "Synthetic rejected history for copy-on-write testing.",
            "decided_at_utc": "2026-08-24T10:25:00Z",
            "audit_event_id": "audit-event-history-rejected",
        }
    else:
        historical["decision"] = {
            "decision": "APPROVED",
            "actor_ref": "actor:p3-history",
            "capability": "approve",
            "reason": "Synthetic approved history for publication testing.",
            "decided_at_utc": "2026-08-24T10:24:00Z",
            "audit_event_id": "audit-event-history-approved",
        }
        historical["publication"] = {
            "publication_id": "publication-history-001",
            "target": "SIMULATION_INTERNAL",
            "published_at_utc": "2026-08-24T10:25:00Z",
            "audit_event_id": "audit-event-history-published",
        }
    schedule_repository.put(historical)
    stored_before = schedule_repository.get(
        cast(str, historical["schedule_version_id"])
    )
    command = _move_command(
        historical,
        key=f"p3-history-{historical_state.lower()}1",
    )
    service = ScheduleCommandService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
        validator_factory=ProblemScheduleValidator,
    )

    result = service.execute(
        command,
        output.problem,
        _context(lifecycle.audit_event_id, "edit"),
    )

    assert result.new_version["state"] == "DRAFT"
    assert result.source_version["state"] == historical_state
    assert (
        schedule_repository.get(cast(str, historical["schedule_version_id"]))
        == stored_before
    )
