from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.publication import (
    CurrentPublicationState,
    PublicationContext,
    build_publication_authorization_denial_audit,
    build_publication_documents,
    prepare_publication,
    publication_identity,
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


def _approved(key: str) -> dict[str, object]:
    output, _ = load_fixed_validated_output(ROOT)
    ready = build_reviewable_schedule_documents(
        output,
        lifecycle_context(
            key,
            reason=f"Create publication contract source {key}.",
            correlation_id=f"correlation-p3-08-contract-source-{key}",
        ),
        data_plane="SIMULATION",
    ).ready_for_review
    approved = deepcopy(ready)
    approved.update(
        {
            "state": "APPROVED",
            "allowed_actions": ["view", "publish"],
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:p3-publication-contract-approver",
                "capability": "approve",
                "reason": "Approve this synthetic publication contract fixture.",
                "decided_at_utc": "2026-08-25T07:00:00Z",
                "audit_event_id": f"audit-event-p3-08-contract-approve-{key}",
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
    key: str,
    previous: dict[str, object] | None,
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
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "SIMULATION_INTERNAL",
        "reason": "Publish this synthetic contract Version internally.",
        "correlation_id": f"correlation-{key}",
        "payload": {"previous_current_version": previous},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _context(source: dict[str, object], capability: str) -> PublicationContext:
    return PublicationContext(
        actor_ref="actor:p3-publication-contract",
        authenticated=True,
        resolved_capabilities=frozenset({capability}),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-publication-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T07:10:00Z",
        code_commit="uncommitted",
    )


def test_publish_supersede_result_audit_and_denial_validate_frozen_schemas() -> None:
    schedule_validator = _validator("schedule-version.schema.json")
    command_validator = _validator("workspace-command.schema.json")
    publication_validator = _validator("publication-result.schema.json")
    audit_validator = _validator("audit-event.schema.json")

    old_source = _approved("a")
    old_command = _command(old_source, "p3-contract-publish-old-0001", None)
    old_documents = build_publication_documents(
        prepare_publication(
            old_source,
            None,
            None,
            old_command,
            _context(old_source, "publish"),
            data_plane="SIMULATION",
        )
    )
    old_published = old_documents.published_schedule
    evidence = cast(dict[str, object], old_published["publication"])
    current = CurrentPublicationState(
        target="SIMULATION_INTERNAL",
        schedule_version_id=cast(str, old_published["schedule_version_id"]),
        content_fingerprint=cast(str, old_published["content_fingerprint"]),
        publication_id=cast(str, evidence["publication_id"]),
    )
    source = _approved("b")
    command = _command(
        source,
        "p3-contract-publish-new-0001",
        _reference(old_published, "PUBLISHED"),
    )
    documents = build_publication_documents(
        prepare_publication(
            source,
            old_published,
            current,
            command,
            _context(source, "publish"),
            data_plane="SIMULATION",
        )
    )

    command_validator.validate(command)
    schedule_validator.validate(documents.published_schedule)
    assert documents.superseded_schedule is not None
    schedule_validator.validate(documents.superseded_schedule)
    publication_validator.validate(documents.publication_result)
    audit_validator.validate(documents.audit_event)
    assert documents.publication_result["target"] == "SIMULATION_INTERNAL"
    assert documents.audit_event["intent_type"] == "PUBLICATION"

    denied = build_publication_authorization_denial_audit(
        command,
        _context(source, "view"),
        publication_identity(command, data_plane="SIMULATION"),
        data_plane="SIMULATION",
    )
    audit_validator.validate(denied)
    assert denied["lineage"] is None
    assert denied["source_version"] is None
    assert denied["new_version"] is None
    assert cast(dict[str, object], denied["result"])["outcome"] == "DENIED"
