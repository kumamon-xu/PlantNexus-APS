from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.publication import (
    CurrentPublicationState,
    PublicationContext,
    PublicationError,
    PublicationFailure,
    build_publication_documents,
    prepare_publication,
    publication_identity,
    require_publication_authorization,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)


ROOT = Path(__file__).resolve().parents[3]


def _reviewable(key: str) -> tuple[dict[str, object], dict[str, object]]:
    output, _ = load_fixed_validated_output(ROOT)
    documents = build_reviewable_schedule_documents(
        output,
        lifecycle_context(
            key,
            reason=f"Create publication unit source {key}.",
            correlation_id=f"correlation-p3-08-unit-source-{key}",
        ),
        data_plane="SIMULATION",
    )
    return documents.draft, documents.ready_for_review


def _approved(key: str) -> dict[str, object]:
    _, ready = _reviewable(key)
    approved = deepcopy(ready)
    approved.update(
        {
            "state": "APPROVED",
            "allowed_actions": ["view", "publish"],
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:p3-publication-unit-approver",
                "capability": "approve",
                "reason": "Approve this isolated synthetic publication fixture.",
                "decided_at_utc": "2026-08-25T06:00:00Z",
                "audit_event_id": f"audit-event-p3-08-unit-approve-{key}",
            },
        }
    )
    return approved


def _reference(schedule: dict[str, object], state: str) -> dict[str, object]:
    return {
        "schedule_version_id": schedule["schedule_version_id"],
        "state": state,
        "content_fingerprint": schedule["content_fingerprint"],
    }


def _command(
    source: dict[str, object],
    *,
    key: str,
    previous: dict[str, object] | None = None,
    reason: str = "Publish this synthetic Version to the internal Simulation target.",
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
        "reason": reason,
        "correlation_id": f"correlation-{key}",
        "payload": {"previous_current_version": previous},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _context(source: dict[str, object], *capabilities: str) -> PublicationContext:
    return PublicationContext(
        actor_ref="actor:p3-publication-unit",
        authenticated=True,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-publication-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T06:10:00Z",
        code_commit="uncommitted",
    )


def test_first_publication_preserves_content_and_builds_frozen_result_and_audit() -> (
    None
):
    source = _approved("a")
    source_bytes = canonical_workspace_bytes(source)
    command = _command(source, key="p3-unit-publish-0001")
    documents = build_publication_documents(
        prepare_publication(
            source,
            None,
            None,
            command,
            _context(source, "publish"),
            data_plane="SIMULATION",
        )
    )

    assert canonical_workspace_bytes(source) == source_bytes
    assert documents.published_schedule["state"] == "PUBLISHED"
    assert documents.published_schedule["content"] == source["content"]
    assert documents.published_schedule["allowed_actions"] == ["view", "export"]
    assert documents.superseded_schedule is None
    assert documents.publication_result["source_approved_version"] == _reference(
        source, "APPROVED"
    )
    assert documents.publication_result["published_version"] == _reference(
        source, "PUBLISHED"
    )
    assert documents.publication_result["previous_current_version"] is None
    assert documents.publication_result["superseded_version"] is None
    assert documents.publication_result["replayed"] is False
    assert documents.audit_event["action"] == "PUBLISH"
    assert documents.audit_event["intent_type"] == "PUBLICATION"
    assert documents.audit_event["before_state"] == "APPROVED"
    assert documents.audit_event["after_state"] == "PUBLISHED"


def test_supersession_changes_only_state_metadata_and_binds_new_current() -> None:
    old_source = _approved("b")
    old_documents = build_publication_documents(
        prepare_publication(
            old_source,
            None,
            None,
            _command(old_source, key="p3-unit-old-publish-0001"),
            _context(old_source, "publish"),
            data_plane="SIMULATION",
        )
    )
    old_published = old_documents.published_schedule
    old_content = deepcopy(old_published["content"])
    old_evidence = cast(dict[str, object], old_published["publication"])
    current = CurrentPublicationState(
        target="SIMULATION_INTERNAL",
        schedule_version_id=cast(str, old_published["schedule_version_id"]),
        content_fingerprint=cast(str, old_published["content_fingerprint"]),
        publication_id=cast(str, old_evidence["publication_id"]),
    )
    source = _approved("c")
    previous = _reference(old_published, "PUBLISHED")
    documents = build_publication_documents(
        prepare_publication(
            source,
            old_published,
            current,
            _command(source, key="p3-unit-new-publish-0001", previous=previous),
            _context(source, "publish"),
            data_plane="SIMULATION",
        )
    )

    assert documents.superseded_schedule is not None
    assert documents.superseded_schedule["state"] == "SUPERSEDED"
    assert documents.superseded_schedule["content"] == old_content
    assert documents.superseded_schedule["publication"] == old_evidence
    assert documents.superseded_schedule["superseded_by"] == _reference(
        source, "PUBLISHED"
    )
    assert documents.publication_result["previous_current_version"] == previous
    assert documents.publication_result["superseded_version"] == _reference(
        old_published, "SUPERSEDED"
    )


def test_publication_authorization_is_exact_capability_scope_and_test_policy() -> None:
    source = _approved("d")
    command = _command(source, key="p3-unit-publication-auth-0001")
    identity = publication_identity(command, data_plane="SIMULATION")
    denied = (
        _context(source, "view"),
        replace(
            _context(source, "publish"),
            schedule_version_scope=frozenset({"schedule-version-other"}),
        ),
        replace(_context(source, "publish"), authenticated=False),
    )
    for context in denied:
        with pytest.raises(PublicationError) as captured:
            require_publication_authorization(
                context,
                identity,
                command,
                data_plane="SIMULATION",
            )
        assert captured.value.reason is PublicationFailure.AUTHORIZATION_DENIED


def test_non_approved_states_and_credential_like_reason_fail_closed() -> None:
    draft, ready = _reviewable("e")
    rejected = deepcopy(ready)
    rejected.update(
        {
            "state": "REJECTED",
            "allowed_actions": ["view", "edit", "lock"],
            "decision": {
                "decision": "REJECTED",
                "actor_ref": "actor:p3-publication-unit-approver",
                "capability": "reject",
                "reason": "Reject this isolated fixture.",
                "decided_at_utc": "2026-08-25T06:00:00Z",
                "audit_event_id": "audit-event-p3-08-unit-reject-e",
            },
        }
    )
    approved = _approved("f")
    published = build_publication_documents(
        prepare_publication(
            approved,
            None,
            None,
            _command(approved, key="p3-unit-published-source-0001"),
            _context(approved, "publish"),
            data_plane="SIMULATION",
        )
    ).published_schedule
    for source in (draft, ready, rejected, published):
        state = cast(str, source["state"])
        command = _command(source, key=f"p3-unit-invalid-{state.lower()}")
        with pytest.raises(PublicationError) as captured:
            prepare_publication(
                source,
                None,
                None,
                command,
                _context(source, "publish"),
                data_plane="SIMULATION",
            )
        assert captured.value.reason is PublicationFailure.INVALID_STATE_TRANSITION

    secret = _command(
        approved,
        key="p3-unit-secret-publication",
        reason="token=credential-material-must-not-be-recorded",
    )
    with pytest.raises(PublicationError) as secret_error:
        publication_identity(secret, data_plane="SIMULATION")
    assert secret_error.value.reason is PublicationFailure.INVALID_REQUEST
