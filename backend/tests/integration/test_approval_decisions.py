"""TASK-P3-07 transactional approval/rejection integration evidence."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any, cast

import pytest

from app.application.approval import ApprovalDecisionResult, ApprovalDecisionService
from app.application.schedule_version_lifecycle_check import (
    _service as lifecycle_service,
    _workspace_engine,
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import (
    ApprovalDecisionContext,
    ApprovalDecisionError,
    ApprovalDecisionFailure,
)
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.infrastructure import (
    SqlAlchemyAuditRepository,
    SqlAlchemyScheduleVersionRepository,
    WorkspaceDataPlane,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def approval_workspace(tmp_path: Path) -> Iterator[tuple[Any, Any, Any]]:
    engine, configuration = _workspace_engine(ROOT, tmp_path / "approval.db")
    output, _ = load_fixed_validated_output(ROOT)
    try:
        yield engine, configuration, output
    finally:
        engine.dispose()
        from alembic import command as alembic_command

        alembic_command.downgrade(configuration, "base")


def _repositories(
    engine: Any, plane: WorkspaceDataPlane = WorkspaceDataPlane.SIMULATION
) -> tuple[Any, Any]:
    return (
        SqlAlchemyScheduleVersionRepository(engine, data_plane=plane),
        SqlAlchemyAuditRepository(engine, data_plane=plane),
    )


def _source(engine: Any, output: Any, key_character: str) -> Any:
    return lifecycle_service(engine, "SIMULATION").create_reviewable(
        output,
        lifecycle_context(
            key_character,
            reason=f"Create reviewable source {key_character} for decision testing.",
            correlation_id=f"correlation-p3-07-source-{key_character}",
        ),
    )


def _service(
    engine: Any, audit_repository: Any | None = None
) -> ApprovalDecisionService:
    schedule_repository, default_audit = _repositories(engine)
    return ApprovalDecisionService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository or default_audit,
    )


def _context(
    source: Mapping[str, object], *capabilities: str
) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref="actor:p3-approval-integration",
        authenticated=True,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T03:00:00Z",
        code_commit="uncommitted",
        parent_audit_event_id=None,
    )


def _command(
    source: Mapping[str, object],
    command_type: str,
    *,
    key: str,
    reason: str | None = None,
) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": command_type.lower(),
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/{command_type}/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "READY_FOR_REVIEW",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": source["synthetic"],
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": reason or f"{command_type.title()} this synthetic Version.",
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


def test_approve_is_atomic_exact_replayable_and_conflicting_reuse_is_rejected(
    approval_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = approval_workspace
    lifecycle = _source(engine, output, "a")
    source = lifecycle.schedule_version
    command = _command(source, "APPROVE", key="p3-integration-approve-0001")
    service = _service(engine)
    before_content = source["content"]

    result = service.execute(command, _context(source, "approve"))
    replay = service.execute(command, _context(source, "approve"))

    assert result.new_version["state"] == "APPROVED"
    assert not result.exact_replay
    assert replay.exact_replay
    assert replay.new_version == result.new_version
    schedule_repository, audit_repository = _repositories(engine)
    stored = schedule_repository.get(cast(str, source["schedule_version_id"]))
    assert stored is not None
    assert stored["state"] == "APPROVED"
    assert stored["content"] == before_content
    assert cast(dict[str, object], stored["decision"])["audit_event_id"] == (
        result.audit_event_id
    )
    decision_audits = [
        event
        for event in audit_repository.list_for_aggregate(
            aggregate_type="SCHEDULE_VERSION",
            aggregate_id=cast(str, source["schedule_version_id"]),
        )
        if event["action"] in {"APPROVE", "REJECT"}
    ]
    assert len(decision_audits) == 1

    conflicting = _command(
        source,
        "APPROVE",
        key="p3-integration-approve-0001",
        reason="A different decision reason reuses the same key.",
    )
    with pytest.raises(ApprovalDecisionError) as conflict:
        service.execute(conflicting, _context(source, "approve"))
    assert conflict.value.reason is ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT
    assert _counts(engine) == {"schedule_versions": 1, "audit_events": 2}


def test_reject_is_terminal_and_a_second_decision_has_no_side_effect(
    approval_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = approval_workspace
    lifecycle = _source(engine, output, "b")
    source = lifecycle.schedule_version
    service = _service(engine)
    rejected = service.execute(
        _command(source, "REJECT", key="p3-integration-reject-0001"),
        _context(source, "reject"),
    )
    before_counts = _counts(engine)

    with pytest.raises(ApprovalDecisionError) as invalid:
        service.execute(
            _command(source, "APPROVE", key="p3-integration-after-reject-0001"),
            _context(source, "approve"),
        )
    assert invalid.value.reason is ApprovalDecisionFailure.INVALID_STATE_TRANSITION
    assert _counts(engine) == before_counts
    schedule_repository, _ = _repositories(engine)
    stored = schedule_repository.get(cast(str, source["schedule_version_id"]))
    assert stored is not None and stored["state"] == "REJECTED"
    assert rejected.new_version["content_fingerprint"] == source["content_fingerprint"]


class _FailingAuditRepository:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        return self._delegate.get(audit_event_id)

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Any:
        del connection, document
        raise RuntimeError("synthetic audit failure that must be sanitized")


def test_audit_failure_rolls_back_decision_state(
    approval_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = approval_workspace
    lifecycle = _source(engine, output, "c")
    source = lifecycle.schedule_version
    schedule_repository, audit_repository = _repositories(engine)
    service = _service(engine, _FailingAuditRepository(audit_repository))
    before = schedule_repository.get_record(cast(str, source["schedule_version_id"]))
    before_counts = _counts(engine)

    with pytest.raises(ApprovalDecisionError) as captured:
        service.execute(
            _command(source, "APPROVE", key="p3-integration-rollback-0001"),
            _context(source, "approve"),
        )
    assert captured.value.reason is ApprovalDecisionFailure.PERSISTENCE_FAILED
    after = schedule_repository.get_record(cast(str, source["schedule_version_id"]))
    assert before is not None and after is not None
    assert after.document == before.document
    assert after.state_revision == before.state_revision
    assert _counts(engine) == before_counts


def test_concurrent_approve_reject_has_one_cas_winner_and_one_decision_audit(
    approval_workspace: tuple[Any, Any, Any],
) -> None:
    engine, _, output = approval_workspace
    lifecycle = _source(engine, output, "d")
    source = lifecycle.schedule_version
    commands = {
        "APPROVE": _command(source, "APPROVE", key="p3-integration-race-approve"),
        "REJECT": _command(source, "REJECT", key="p3-integration-race-reject"),
    }
    barrier = Barrier(2)

    def invoke(command_type: str) -> ApprovalDecisionResult:
        barrier.wait()
        return _service(engine).execute(
            commands[command_type], _context(source, command_type.lower())
        )

    successes: list[ApprovalDecisionResult] = []
    failures: list[ApprovalDecisionFailure] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in [
            executor.submit(invoke, command_type)
            for command_type in ("APPROVE", "REJECT")
        ]:
            try:
                successes.append(future.result())
            except ApprovalDecisionError as error:
                failures.append(error.reason)

    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0] in {
        ApprovalDecisionFailure.STALE_SOURCE,
        ApprovalDecisionFailure.INVALID_STATE_TRANSITION,
        ApprovalDecisionFailure.PERSISTENCE_FAILED,
    }
    winning = successes[0]
    schedule_repository, audit_repository = _repositories(engine)
    stored = schedule_repository.get(cast(str, source["schedule_version_id"]))
    assert stored is not None and stored["state"] == winning.new_version["state"]
    decision_audits = [
        event
        for event in audit_repository.list_for_aggregate(
            aggregate_type="SCHEDULE_VERSION",
            aggregate_id=cast(str, source["schedule_version_id"]),
        )
        if event["action"] in {"APPROVE", "REJECT"}
    ]
    assert len(decision_audits) == 1
    assert (
        _service(engine)
        .execute(
            commands[winning.command_type],
            _context(source, winning.command_type.lower()),
        )
        .exact_replay
    )
