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
from app.domain.schedule_commands import (
    ScheduleCommandContext,
    build_review_submission_documents,
    build_schedule_command_documents,
    prepare_review_submission,
    prepare_schedule_command,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.planning.validation import validate_problem_schedule


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


def test_generated_command_new_draft_and_audit_validate_against_frozen_p3_schemas() -> (
    None
):
    output, _ = load_fixed_validated_output(ROOT)
    source = build_reviewable_schedule_documents(
        output, lifecycle_context(), data_plane="SIMULATION"
    ).ready_for_review
    assignment = cast(
        list[dict[str, object]],
        cast(dict[str, object], source["content"])["assignments"],
    )[0]
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": "command-p3-contract-move-001",
        "command_type": "MOVE_OPERATION",
        "required_capability": "edit",
        "idempotency_key": "p3-contract-move-001",
        "idempotency_scope": (
            f"SIMULATION/MOVE_OPERATION/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": source["state"],
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Validate one generated P3 command result carrier.",
        "correlation_id": "correlation-p3-contract-move-001",
        "payload": {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": "2026-09-01T00:03:00Z",
            "end_at_utc": "2026-09-01T00:04:00Z",
        },
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    context = ScheduleCommandContext(
        actor_ref="actor:p3-command-contract",
        resolved_capabilities=frozenset({"edit"}),
        auth_policy_version="simulation-command-policy.v1",
        occurred_at_utc="2026-08-24T10:40:00Z",
        code_commit="uncommitted",
    )
    prepared = prepare_schedule_command(
        source, output.problem, command, context, data_plane="SIMULATION"
    )
    report = validate_problem_schedule(output.problem, prepared.validator_candidate)
    documents = build_schedule_command_documents(prepared, report)

    _validator("workspace-command.schema.json").validate(command)
    _validator("schedule-version.schema.json").validate(documents.draft)
    _validator("audit-event.schema.json").validate(documents.audit_event)
    assert documents.draft["state"] == "DRAFT"
    assert documents.audit_event["result"] == {
        "outcome": "SUCCEEDED",
        "replayed": False,
        "retryable": False,
        "error": None,
    }

    submit: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": "command-p3-contract-submit-001",
        "command_type": "SUBMIT_FOR_REVIEW",
        "required_capability": "edit",
        "idempotency_key": "p3-contract-submit-001",
        "idempotency_scope": (
            f"SIMULATION/SUBMIT_FOR_REVIEW/{documents.draft['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": documents.draft["schedule_version_id"],
        "expected_state": "DRAFT",
        "expected_content_fingerprint": documents.draft["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": documents.draft["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Submit one generated manual DRAFT for review.",
        "correlation_id": "correlation-p3-contract-submit-001",
        "payload": {},
    }
    submit["request_fingerprint"] = workspace_command_fingerprint(submit)
    prepared_submit = prepare_review_submission(
        documents.draft,
        output.problem,
        submit,
        context,
        data_plane="SIMULATION",
    )
    submit_report = validate_problem_schedule(
        output.problem, prepared_submit.validator_candidate
    )
    review = build_review_submission_documents(prepared_submit, submit_report)

    _validator("workspace-command.schema.json").validate(submit)
    _validator("schedule-version.schema.json").validate(review.ready_for_review)
    _validator("audit-event.schema.json").validate(review.audit_event)
    assert review.ready_for_review["state"] == "READY_FOR_REVIEW"
    assert review.audit_event["action"] == "SUBMIT_FOR_REVIEW"
