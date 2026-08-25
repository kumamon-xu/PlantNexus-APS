"""Fail-closed publication authorization and default-deny evidence."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Never, cast

import pytest

from app.application.publication import PublicationService
from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.publication import (
    PublicationContext,
    PublicationError,
    PublicationFailure,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)


ROOT = Path(__file__).resolve().parents[3]


def _source() -> dict[str, object]:
    output, _ = load_fixed_validated_output(ROOT)
    ready = build_reviewable_schedule_documents(
        output, lifecycle_context("a"), data_plane="SIMULATION"
    ).ready_for_review
    approved = deepcopy(ready)
    approved.update(
        {
            "state": "APPROVED",
            "allowed_actions": ["view", "publish"],
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:p3-publication-security-approver",
                "capability": "approve",
                "reason": "Approve this isolated security fixture.",
                "decided_at_utc": "2026-08-25T09:00:00Z",
                "audit_event_id": "audit-event-p3-08-security-approve",
            },
        }
    )
    return approved


def _command(source: dict[str, object], *, key: str) -> dict[str, object]:
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
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "SIMULATION_INTERNAL",
        "reason": "Publish this isolated synthetic security fixture.",
        "correlation_id": "correlation-p3-publication-security",
        "payload": {"previous_current_version": None},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _context(
    source: dict[str, object],
    *capabilities: str,
    actor_ref: str = "actor:p3-publication-security",
    authenticated: bool = True,
    scope: bool = True,
) -> PublicationContext:
    return PublicationContext(
        actor_ref=actor_ref,
        authenticated=authenticated,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=(
            frozenset({cast(str, source["schedule_version_id"])})
            if scope
            else frozenset({"schedule-version-out-of-scope"})
        ),
        auth_policy_version="simulation-test-publication-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T09:10:00Z",
        code_commit="uncommitted",
    )


class _ScheduleLookupMustNotRun:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, schedule_version_id: str) -> Never:
        del schedule_version_id
        self.calls += 1
        raise AssertionError("authorization must precede schedule lookup")

    def get_record(self, schedule_version_id: str) -> Never:
        del schedule_version_id
        self.calls += 1
        raise AssertionError("authorization must precede schedule lookup")

    def transition_in_transaction(self, connection: object, **kwargs: object) -> Never:
        del connection, kwargs
        raise AssertionError("denied publication must not transition state")


class _CurrentLookupMustNotRun:
    def __init__(self) -> None:
        self.calls = 0

    def get_current(self, *, target: str = "SIMULATION_INTERNAL") -> Never:
        del target
        self.calls += 1
        raise AssertionError("authorization must precede current lookup")

    def persist_and_set_current_in_transaction(
        self,
        connection: object,
        document: Mapping[str, object],
        *,
        expected_current: object,
    ) -> Never:
        del connection, document, expected_current
        raise AssertionError("denied publication must not persist a result")


@dataclass(frozen=True)
class _WriteResult:
    document: dict[str, object]
    replayed: bool


class _MemoryAuditRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}
        self.get_calls = 0
        self.append_calls = 0

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
    publication_repository: _CurrentLookupMustNotRun,
) -> PublicationService:
    return PublicationService(
        data_plane=data_plane,
        transaction_factory=lambda: nullcontext(object()),
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
        publication_repository=publication_repository,
    )


@pytest.mark.parametrize("denial", ["capability", "scope", "authentication"])
def test_denial_precedes_all_resource_lookup_and_records_one_sanitized_event(
    denial: str,
) -> None:
    source = _source()
    command = _command(source, key=f"p3-security-publication-{denial}-0001")
    contexts = {
        "capability": _context(source, "view"),
        "scope": _context(source, "publish", scope=False),
        "authentication": _context(source, "publish", authenticated=False),
    }
    schedule_repository = _ScheduleLookupMustNotRun()
    publication_repository = _CurrentLookupMustNotRun()
    audit_repository = _MemoryAuditRepository()
    service = _service(
        "SIMULATION", schedule_repository, audit_repository, publication_repository
    )

    for _ in range(2):
        with pytest.raises(PublicationError) as captured:
            service.execute(command, contexts[denial])
        assert captured.value.reason is PublicationFailure.AUTHORIZATION_DENIED

    assert schedule_repository.calls == 0
    assert publication_repository.calls == 0
    assert audit_repository.append_calls == 1
    assert len(audit_repository.documents) == 1
    event = next(iter(audit_repository.documents.values()))
    assert cast(dict[str, object], event["result"])["outcome"] == "DENIED"
    assert event["lineage"] is None
    assert event["source_version"] is None
    assert event["new_version"] is None
    rendered = canonical_workspace_bytes(event)
    assert cast(str, command["idempotency_key"]).encode() not in rendered


def test_production_is_default_denied_and_audited_as_workspace_internal() -> None:
    source = _source()
    command = _command(source, key="p3-security-publication-production-0001")
    command.update(
        {
            "data_plane": "PRODUCTION",
            "environment": "PRODUCTION",
            "synthetic": False,
            "idempotency_scope": (
                f"PRODUCTION/PUBLISH/{source['schedule_version_id']}"
                "/SIMULATION_INTERNAL"
            ),
        }
    )
    del command["synthetic_provenance"]
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    context = replace(
        _context(source, "publish"),
        actor_ref="actor:production-unbound",
        auth_policy_version="production-publication-policy-unconfigured.v1",
        occurred_at_utc="2026-08-25T09:20:00Z",
    )
    schedule_repository = _ScheduleLookupMustNotRun()
    publication_repository = _CurrentLookupMustNotRun()
    audit_repository = _MemoryAuditRepository()

    with pytest.raises(PublicationError) as captured:
        _service(
            "PRODUCTION",
            schedule_repository,
            audit_repository,
            publication_repository,
        ).execute(command, context)
    assert (
        captured.value.reason
        is PublicationFailure.PRODUCTION_AUTHORITY_UNAVAILABLE
    )
    assert schedule_repository.calls == 0
    assert publication_repository.calls == 0
    event = next(iter(audit_repository.documents.values()))
    assert event["data_plane"] == "PRODUCTION"
    assert event["target"] == "WORKSPACE_INTERNAL"
    assert event["synthetic"] is False
    assert "synthetic_provenance" not in event


def test_invalid_actor_and_secret_reason_are_rejected_before_audit_write() -> None:
    source = _source()
    schedule_repository = _ScheduleLookupMustNotRun()
    publication_repository = _CurrentLookupMustNotRun()
    audit_repository = _MemoryAuditRepository()
    service = _service(
        "SIMULATION", schedule_repository, audit_repository, publication_repository
    )

    with pytest.raises(PublicationError) as actor_error:
        service.execute(
            _command(source, key="p3-security-publication-invalid-actor"),
            _context(source, "publish", actor_ref="planner@example.com"),
        )
    assert actor_error.value.reason is PublicationFailure.INVALID_REQUEST

    secret = _command(source, key="p3-security-publication-secret-reason")
    secret["reason"] = "password=must-never-enter-publication-audit"
    secret["request_fingerprint"] = workspace_command_fingerprint(secret)
    with pytest.raises(PublicationError) as secret_error:
        service.execute(secret, _context(source, "publish"))
    assert secret_error.value.reason is PublicationFailure.INVALID_REQUEST
    assert schedule_repository.calls == 0
    assert publication_repository.calls == 0
    assert audit_repository.get_calls == 0
    assert audit_repository.append_calls == 0
