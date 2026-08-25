"""Fail-closed authorization, default-deny, and redaction evidence."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Never, cast

import pytest

from app.application.approval import ApprovalDecisionService
from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import (
    ApprovalDecisionContext,
    ApprovalDecisionError,
    ApprovalDecisionFailure,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)


ROOT = Path(__file__).resolve().parents[3]


def _source() -> dict[str, object]:
    output, _ = load_fixed_validated_output(ROOT)
    return build_reviewable_schedule_documents(
        output, lifecycle_context(), data_plane="SIMULATION"
    ).ready_for_review


def _command(source: dict[str, object], *, key: str) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "APPROVE",
        "required_capability": "approve",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/APPROVE/{source['schedule_version_id']}/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "READY_FOR_REVIEW",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Approve this isolated synthetic security fixture.",
        "correlation_id": "correlation-p3-approval-security",
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _context(
    source: dict[str, object],
    *capabilities: str,
    actor_ref: str = "actor:p3-approval-security",
    authenticated: bool = True,
    scope: bool = True,
) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref=actor_ref,
        authenticated=authenticated,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=(
            frozenset({cast(str, source["schedule_version_id"])})
            if scope
            else frozenset({"schedule-version-out-of-scope"})
        ),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T04:00:00Z",
        code_commit="uncommitted",
    )


class _ScheduleLookupMustNotRun:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, schedule_version_id: str) -> Never:
        del schedule_version_id
        self.calls += 1
        raise AssertionError("authorization must run before stored result lookup")

    def get_record(self, schedule_version_id: str) -> Never:
        del schedule_version_id
        self.calls += 1
        raise AssertionError("authorization must run before source lookup")

    def transition_in_transaction(
        self,
        connection: object,
        *,
        schedule_version_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
    ) -> Never:
        del (
            connection,
            schedule_version_id,
            expected_state,
            expected_state_revision,
            candidate_document,
        )
        raise AssertionError("denied requests must not transition state")


@dataclass(frozen=True)
class _WriteResult:
    document: dict[str, object]
    replayed: bool


class _MemoryAuditRepository:
    def __init__(self, initial: dict[str, object] | None = None) -> None:
        self.documents: dict[str, dict[str, object]] = {}
        self.get_calls = 0
        self.append_calls = 0
        if initial is not None:
            self.documents[cast(str, initial["audit_event_id"])] = initial

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        self.get_calls += 1
        return self.documents.get(audit_event_id)

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Any:
        del connection
        self.append_calls += 1
        candidate = dict(document)
        audit_id = cast(str, candidate["audit_event_id"])
        existing = self.documents.get(audit_id)
        if existing is not None:
            return _WriteResult(document=existing, replayed=True)
        self.documents[audit_id] = candidate
        return _WriteResult(document=candidate, replayed=False)


def _service(
    data_plane: str,
    schedule_repository: _ScheduleLookupMustNotRun,
    audit_repository: _MemoryAuditRepository,
) -> ApprovalDecisionService:
    return ApprovalDecisionService(
        data_plane=data_plane,
        transaction_factory=lambda: nullcontext(object()),
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
    )


@pytest.mark.parametrize(
    "context",
    [
        "missing-capability",
        "out-of-scope",
        "unauthenticated",
    ],
)
def test_denial_precedes_source_lookup_and_records_one_sanitized_event(
    context: str,
) -> None:
    source = _source()
    command = _command(source, key=f"p3-security-{context}-0001")
    contexts = {
        "missing-capability": _context(source, "view"),
        "out-of-scope": _context(source, "approve", scope=False),
        "unauthenticated": _context(
            source,
            "approve",
            actor_ref="actor:unauthenticated",
            authenticated=False,
        ),
    }
    schedule_repository = _ScheduleLookupMustNotRun()
    audit_repository = _MemoryAuditRepository()
    service = _service("SIMULATION", schedule_repository, audit_repository)

    for _ in range(2):
        with pytest.raises(ApprovalDecisionError) as captured:
            service.execute(command, contexts[context])
        assert captured.value.reason is ApprovalDecisionFailure.AUTHORIZATION_DENIED

    assert schedule_repository.calls == 0
    assert audit_repository.append_calls == 1
    assert len(audit_repository.documents) == 1
    event = next(iter(audit_repository.documents.values()))
    assert cast(dict[str, object], event["result"])["outcome"] == "DENIED"
    assert event["source_version"] is None
    assert event["lineage"] is None
    rendered = canonical_workspace_bytes(event)
    assert cast(str, command["idempotency_key"]).encode() not in rendered


def test_production_is_default_denied_and_audited_without_resource_lookup() -> None:
    source = _source()
    command = _command(source, key="p3-security-production-0001")
    command.update(
        {
            "data_plane": "PRODUCTION",
            "environment": "PRODUCTION",
            "synthetic": False,
            "idempotency_scope": (
                f"PRODUCTION/APPROVE/{source['schedule_version_id']}/WORKSPACE_INTERNAL"
            ),
        }
    )
    del command["synthetic_provenance"]
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    context = ApprovalDecisionContext(
        actor_ref="actor:production-unbound",
        authenticated=True,
        resolved_capabilities=frozenset({"approve"}),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="production-approval-policy-unconfigured.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T04:10:00Z",
        code_commit="uncommitted",
    )
    schedule_repository = _ScheduleLookupMustNotRun()
    audit_repository = _MemoryAuditRepository()

    with pytest.raises(ApprovalDecisionError) as captured:
        _service("PRODUCTION", schedule_repository, audit_repository).execute(
            command, context
        )
    assert (
        captured.value.reason
        is ApprovalDecisionFailure.PRODUCTION_AUTHORITY_UNAVAILABLE
    )
    assert schedule_repository.calls == 0
    assert len(audit_repository.documents) == 1
    event = next(iter(audit_repository.documents.values()))
    assert event["data_plane"] == "PRODUCTION"
    assert event["environment"] == "PRODUCTION"
    assert event["synthetic"] is False
    assert "synthetic_provenance" not in event


def test_invalid_actor_and_secret_reason_are_rejected_before_any_audit_write() -> None:
    source = _source()
    schedule_repository = _ScheduleLookupMustNotRun()
    audit_repository = _MemoryAuditRepository()
    service = _service("SIMULATION", schedule_repository, audit_repository)

    command = _command(source, key="p3-security-invalid-actor")
    with pytest.raises(ApprovalDecisionError) as actor_error:
        service.execute(
            command,
            _context(source, "approve", actor_ref="planner@example.com"),
        )
    assert actor_error.value.reason is ApprovalDecisionFailure.INVALID_REQUEST

    secret_command = _command(source, key="p3-security-secret-reason")
    secret_command["reason"] = "password=must-never-enter-audit"
    secret_command["request_fingerprint"] = workspace_command_fingerprint(
        secret_command
    )
    with pytest.raises(ApprovalDecisionError) as secret_error:
        service.execute(secret_command, _context(source, "approve"))
    assert secret_error.value.reason is ApprovalDecisionFailure.INVALID_REQUEST
    assert schedule_repository.calls == 0
    assert audit_repository.get_calls == 0
    assert audit_repository.append_calls == 0
