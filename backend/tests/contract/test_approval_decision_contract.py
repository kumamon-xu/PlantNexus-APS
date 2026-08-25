from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import (
    ApprovalDecisionContext,
    approval_decision_identity,
    build_approval_decision_documents,
    build_authorization_denial_audit,
    prepare_approval_decision,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import workspace_command_fingerprint


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _validator(name: str) -> Draft202012Validator:
    schemas = {path.name: _json(path) for path in SCHEMA_ROOT.glob("*.schema.json")}
    registry = Registry().with_resources(
        [
            (cast(str, schema["$id"]), Resource.from_contents(schema))
            for schema in schemas.values()
        ]
    )
    return Draft202012Validator(
        schemas[name], registry=registry, format_checker=FormatChecker()
    )


def _command(
    source: dict[str, object], command_type: str, key: str
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
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": f"{command_type.title()} the synthetic contract schedule.",
        "correlation_id": f"correlation-{key}",
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _context(source: dict[str, object], capability: str) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref="actor:p3-approval-contract",
        authenticated=True,
        resolved_capabilities=frozenset({capability}),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T02:00:00Z",
        code_commit="uncommitted",
    )


def test_approve_reject_and_denial_documents_validate_against_frozen_p3_schemas() -> (
    None
):
    output, _ = load_fixed_validated_output(ROOT)
    source = build_reviewable_schedule_documents(
        output, lifecycle_context(), data_plane="SIMULATION"
    ).ready_for_review
    command_validator = _validator("workspace-command.schema.json")
    schedule_validator = _validator("schedule-version.schema.json")
    audit_validator = _validator("audit-event.schema.json")

    for command_type, target_state in (
        ("APPROVE", "APPROVED"),
        ("REJECT", "REJECTED"),
    ):
        key = f"p3-contract-{command_type.lower()}-0001"
        command = _command(source, command_type, key)
        context = _context(source, command_type.lower())
        documents = build_approval_decision_documents(
            prepare_approval_decision(
                source,
                command,
                context,
                data_plane="SIMULATION",
            )
        )

        command_validator.validate(command)
        schedule_validator.validate(documents.decided_schedule)
        audit_validator.validate(documents.audit_event)
        assert documents.decided_schedule["state"] == target_state
        assert documents.audit_event["intent_type"] == "DECISION"
        assert documents.audit_event["after_state"] == target_state

    denied_command = _command(source, "APPROVE", "p3-contract-denied-0001")
    denied_context = _context(source, "view")
    denied = build_authorization_denial_audit(
        denied_command,
        denied_context,
        approval_decision_identity(denied_command, data_plane="SIMULATION"),
        data_plane="SIMULATION",
    )
    audit_validator.validate(denied)
    assert denied["source_version"] is None
    assert denied["new_version"] is None
    assert cast(dict[str, object], denied["result"])["outcome"] == "DENIED"
