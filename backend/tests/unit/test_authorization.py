from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import (
    ApprovalDecisionContext,
    ApprovalDecisionError,
    ApprovalDecisionFailure,
    approval_decision_identity,
    build_approval_decision_documents,
    build_authorization_denial_audit,
    prepare_approval_decision,
    require_approval_decision_authorization,
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


def _command(
    source: dict[str, object],
    command_type: str,
    *,
    key: str,
    reason: str = "Approve or reject this synthetic reviewable schedule.",
) -> dict[str, object]:
    capability = command_type.lower()
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": capability,
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
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": reason,
        "correlation_id": f"correlation-{key}",
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _context(source: dict[str, object], *capabilities: str) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref="actor:p3-approval-unit",
        authenticated=True,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T01:00:00Z",
        code_commit="uncommitted",
    )


@pytest.mark.parametrize(
    ("command_type", "target_state", "capability", "allowed_actions"),
    [
        ("APPROVE", "APPROVED", "approve", ["view", "publish"]),
        ("REJECT", "REJECTED", "reject", ["view", "edit", "lock"]),
    ],
)
def test_decision_documents_preserve_source_content_and_bind_actor_reason_audit(
    command_type: str,
    target_state: str,
    capability: str,
    allowed_actions: list[str],
) -> None:
    source = _source()
    source_bytes = canonical_workspace_bytes(source)
    command = _command(source, command_type, key=f"p3-unit-{command_type.lower()}-0001")
    prepared = prepare_approval_decision(
        source,
        command,
        _context(source, capability),
        data_plane="SIMULATION",
    )
    documents = build_approval_decision_documents(prepared)

    assert canonical_workspace_bytes(source) == source_bytes
    assert documents.decided_schedule["state"] == target_state
    assert documents.decided_schedule["content"] == source["content"]
    assert (
        documents.decided_schedule["content_fingerprint"]
        == source["content_fingerprint"]
    )
    assert documents.decided_schedule["allowed_actions"] == allowed_actions
    assert documents.decided_schedule["decision"] == {
        "decision": target_state,
        "actor_ref": "actor:p3-approval-unit",
        "capability": capability,
        "reason": command["reason"],
        "decided_at_utc": "2026-08-25T01:00:00Z",
        "audit_event_id": documents.identity.audit_event_id,
    }
    assert documents.audit_event["before_state"] == "READY_FOR_REVIEW"
    assert documents.audit_event["after_state"] == target_state
    assert documents.audit_event["action"] == command_type
    assert documents.audit_event["intent_type"] == "DECISION"
    assert documents.audit_event["result"] == {
        "outcome": "SUCCEEDED",
        "replayed": False,
        "retryable": False,
        "error": None,
    }


def test_authorization_is_exact_capability_scope_authenticated_and_test_only() -> None:
    source = _source()
    command = _command(source, "APPROVE", key="p3-unit-authz-0001")
    identity = approval_decision_identity(command, data_plane="SIMULATION")
    denied_contexts = (
        ApprovalDecisionContext(
            actor_ref="actor:p3-approval-unit",
            authenticated=True,
            resolved_capabilities=frozenset({"reject"}),
            schedule_version_scope=frozenset(
                {cast(str, source["schedule_version_id"])}
            ),
            auth_policy_version="simulation-test-approval-policy.v1",
            production_binding=False,
            occurred_at_utc="2026-08-25T01:00:00Z",
            code_commit="uncommitted",
        ),
        ApprovalDecisionContext(
            actor_ref="actor:p3-approval-unit",
            authenticated=True,
            resolved_capabilities=frozenset({"approve"}),
            schedule_version_scope=frozenset({"schedule-version-other"}),
            auth_policy_version="simulation-test-approval-policy.v1",
            production_binding=False,
            occurred_at_utc="2026-08-25T01:00:00Z",
            code_commit="uncommitted",
        ),
        ApprovalDecisionContext(
            actor_ref="actor:unauthenticated",
            authenticated=False,
            resolved_capabilities=frozenset({"approve"}),
            schedule_version_scope=frozenset(
                {cast(str, source["schedule_version_id"])}
            ),
            auth_policy_version="simulation-test-approval-policy.v1",
            production_binding=False,
            occurred_at_utc="2026-08-25T01:00:00Z",
            code_commit="uncommitted",
        ),
        ApprovalDecisionContext(
            actor_ref="actor:p3-approval-unit",
            authenticated=True,
            resolved_capabilities=frozenset({"approve"}),
            schedule_version_scope=frozenset(
                {cast(str, source["schedule_version_id"])}
            ),
            auth_policy_version="simulation-test-approval-policy.v1",
            production_binding=True,
            occurred_at_utc="2026-08-25T01:00:00Z",
            code_commit="uncommitted",
        ),
    )
    for context in denied_contexts:
        with pytest.raises(ApprovalDecisionError) as captured:
            require_approval_decision_authorization(
                context,
                identity,
                command,
                data_plane="SIMULATION",
            )
        assert captured.value.reason is ApprovalDecisionFailure.AUTHORIZATION_DENIED


def test_denial_audit_is_sanitized_and_contains_no_resource_lookup_result() -> None:
    source = _source()
    command = _command(source, "REJECT", key="p3-unit-denial-0001")
    identity = approval_decision_identity(command, data_plane="SIMULATION")
    context = _context(source, "view")
    event = build_authorization_denial_audit(
        command,
        context,
        identity,
        data_plane="SIMULATION",
    )

    assert event["lineage"] is None
    assert event["source_version"] is None
    assert event["new_version"] is None
    assert event["before_state"] is None
    assert event["after_state"] is None
    assert cast(dict[str, object], event["result"])["outcome"] == "DENIED"
    rendered = canonical_workspace_bytes(event).lower()
    for forbidden in (b"bearer ", b"password=", b"token=", b"postgresql://"):
        assert forbidden not in rendered


def test_invalid_state_stale_fingerprint_and_credential_like_reason_fail_closed() -> (
    None
):
    source = _source()
    source["state"] = "APPROVED"
    command = _command(source, "APPROVE", key="p3-unit-invalid-0001")
    command["expected_state"] = "READY_FOR_REVIEW"
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    with pytest.raises(ApprovalDecisionError) as invalid_state:
        prepare_approval_decision(
            source,
            command,
            _context(source, "approve"),
            data_plane="SIMULATION",
        )
    assert (
        invalid_state.value.reason is ApprovalDecisionFailure.INVALID_STATE_TRANSITION
    )

    clean_source = _source()
    stale = _command(clean_source, "REJECT", key="p3-unit-stale-0001")
    stale["expected_content_fingerprint"] = "sha256:" + "f" * 64
    stale["request_fingerprint"] = workspace_command_fingerprint(stale)
    with pytest.raises(ApprovalDecisionError) as stale_error:
        prepare_approval_decision(
            clean_source,
            stale,
            _context(clean_source, "reject"),
            data_plane="SIMULATION",
        )
    assert stale_error.value.reason is ApprovalDecisionFailure.STALE_SOURCE

    secret = _command(
        clean_source,
        "APPROVE",
        key="p3-unit-secret-0001",
        reason="Bearer credential-material-must-not-be-recorded",
    )
    with pytest.raises(ApprovalDecisionError) as secret_error:
        approval_decision_identity(secret, data_plane="SIMULATION")
    assert secret_error.value.reason is ApprovalDecisionFailure.INVALID_REQUEST
