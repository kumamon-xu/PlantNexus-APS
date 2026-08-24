from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.schedule_commands import (
    ScheduleCommandContext,
    ScheduleCommandError,
    ScheduleCommandFailure,
    build_review_submission_documents,
    build_schedule_command_documents,
    prepare_review_submission,
    prepare_schedule_command,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)
from app.planning.validation import validate_problem_schedule


ROOT = Path(__file__).resolve().parents[3]


def _source_bundle() -> tuple[dict[str, object], dict[str, object]]:
    output, _ = load_fixed_validated_output(ROOT)
    documents = build_reviewable_schedule_documents(
        output,
        lifecycle_context(),
        data_plane="SIMULATION",
    )
    return documents.ready_for_review, dict(output.problem)


def _context(*capabilities: str) -> ScheduleCommandContext:
    return ScheduleCommandContext(
        actor_ref="actor:p3-command-unit",
        resolved_capabilities=frozenset(capabilities),
        auth_policy_version="simulation-command-policy.v1",
        occurred_at_utc="2026-08-24T10:00:00Z",
        code_commit="uncommitted",
        parent_audit_event_id=None,
    )


def _command(
    source: dict[str, object],
    command_type: str,
    payload: dict[str, object],
    *,
    key: str,
    reason: str = "Apply one bounded synthetic schedule command.",
) -> dict[str, object]:
    capability = (
        "edit"
        if command_type in {"MOVE_OPERATION", "ASSIGN_RESOURCE", "SUBMIT_FOR_REVIEW"}
        else "lock"
    )
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
        "expected_state": source["state"],
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": source["synthetic"],
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": reason,
        "correlation_id": f"correlation-{key}",
        "payload": payload,
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _first_assignment(source: dict[str, object]) -> dict[str, object]:
    content = cast(dict[str, object], source["content"])
    assignments = cast(list[dict[str, object]], content["assignments"])
    return assignments[0]


def test_move_builds_new_draft_fresh_validation_and_audit_without_mutating_source() -> (
    None
):
    source, problem = _source_bundle()
    before = canonical_workspace_bytes(source)
    assignment = _first_assignment(source)
    command = _command(
        source,
        "MOVE_OPERATION",
        {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": "2026-09-01T00:03:00Z",
            "end_at_utc": "2026-09-01T00:04:00Z",
        },
        key="p3-unit-move-0001",
    )

    prepared = prepare_schedule_command(
        source, problem, command, _context("edit"), data_plane="SIMULATION"
    )
    report = validate_problem_schedule(problem, prepared.validator_candidate)
    documents = build_schedule_command_documents(prepared, report)

    assert report["status"] == "PASS"
    assert canonical_workspace_bytes(source) == before
    assert documents.draft["schedule_version_id"] != source["schedule_version_id"]
    assert documents.draft["state"] == "DRAFT"
    assert documents.draft["source_kind"] == "MANUAL_EDIT"
    assert documents.draft["content_fingerprint"] != source["content_fingerprint"]
    assert documents.draft["parent_schedule_version"] == {
        "schedule_version_id": source["schedule_version_id"],
        "state": source["state"],
        "content_fingerprint": source["content_fingerprint"],
    }
    assert documents.audit_event["action"] == "EDIT_SCHEDULE"
    assert (
        documents.audit_event["source_version"]
        == documents.draft["parent_schedule_version"]
    )
    assert documents.audit_event["new_version"]["state"] == "DRAFT"  # type: ignore[index]


def test_set_and_remove_version_lock_are_copy_on_write_and_formally_valid() -> None:
    source, problem = _source_bundle()
    assignment = _first_assignment(source)
    lock = {
        "lock_id": "lock-p3-unit-hard-0001",
        "operation_id": assignment["operation_id"],
        "lock_type": "HARD",
        "resource_id": assignment["resource_id"],
        "start_at_utc": assignment["start_at_utc"],
        "end_at_utc": assignment["end_at_utc"],
    }
    set_command = _command(
        source,
        "SET_LOCK",
        {"lock": lock},
        key="p3-unit-lock-0001",
    )
    prepared_set = prepare_schedule_command(
        source, problem, set_command, _context("lock"), data_plane="SIMULATION"
    )
    set_report = validate_problem_schedule(problem, prepared_set.validator_candidate)
    set_documents = build_schedule_command_documents(prepared_set, set_report)
    set_content = cast(dict[str, object], set_documents.draft["content"])
    assert cast(list[dict[str, object]], set_content["locks"])[0] == lock
    assert set_documents.draft["source_kind"] == "LOCK_CHANGE"
    assert set_documents.audit_event["action"] == "SET_LOCK"

    remove_command = _command(
        set_documents.draft,
        "REMOVE_LOCK",
        {
            "lock_id": lock["lock_id"],
            "operation_id": lock["operation_id"],
        },
        key="p3-unit-unlock-01",
    )
    prepared_remove = prepare_schedule_command(
        set_documents.draft,
        problem,
        remove_command,
        _context("lock"),
        data_plane="SIMULATION",
    )
    remove_report = validate_problem_schedule(
        problem, prepared_remove.validator_candidate
    )
    remove_documents = build_schedule_command_documents(prepared_remove, remove_report)
    remove_content = cast(dict[str, object], remove_documents.draft["content"])
    assert remove_content["locks"] == []
    assert remove_documents.audit_event["action"] == "REMOVE_LOCK"
    assert set_documents.draft["state"] == "DRAFT"


def test_explicit_review_submission_revalidates_manual_draft_without_content_change() -> (
    None
):
    source, problem = _source_bundle()
    assignment = _first_assignment(source)
    move = _command(
        source,
        "MOVE_OPERATION",
        {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": "2026-09-01T00:03:00Z",
            "end_at_utc": "2026-09-01T00:04:00Z",
        },
        key="p3-unit-ready-move1",
    )
    prepared_move = prepare_schedule_command(
        source, problem, move, _context("edit"), data_plane="SIMULATION"
    )
    move_report = validate_problem_schedule(problem, prepared_move.validator_candidate)
    draft = build_schedule_command_documents(prepared_move, move_report).draft
    draft_before = canonical_workspace_bytes(draft)
    submit = _command(
        draft,
        "SUBMIT_FOR_REVIEW",
        {},
        key="p3-unit-ready-submit1",
        reason="Submit the validated manual DRAFT for review.",
    )

    prepared_submit = prepare_review_submission(
        draft,
        problem,
        submit,
        _context("edit"),
        data_plane="SIMULATION",
    )
    submit_report = validate_problem_schedule(
        problem, prepared_submit.validator_candidate
    )
    documents = build_review_submission_documents(prepared_submit, submit_report)

    assert canonical_workspace_bytes(draft) == draft_before
    assert (
        documents.ready_for_review["schedule_version_id"]
        == draft["schedule_version_id"]
    )
    assert documents.ready_for_review["content"] == draft["content"]
    assert (
        documents.ready_for_review["content_fingerprint"]
        == draft["content_fingerprint"]
    )
    assert documents.ready_for_review["state"] == "READY_FOR_REVIEW"
    assert documents.ready_for_review["allowed_actions"] == [
        "view",
        "approve",
        "reject",
    ]
    assert documents.ready_for_review["decision"] is None
    assert documents.audit_event["action"] == "SUBMIT_FOR_REVIEW"
    assert documents.audit_event["source_version"]["state"] == "DRAFT"  # type: ignore[index]
    assert documents.audit_event["new_version"]["state"] == "READY_FOR_REVIEW"  # type: ignore[index]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("stale", ScheduleCommandFailure.STALE_SOURCE),
        ("unauthorized", ScheduleCommandFailure.UNAUTHORIZED),
        ("unknown-resource", ScheduleCommandFailure.INVALID_REFERENCE),
        ("bad-duration", ScheduleCommandFailure.INVALID_TIME),
    ],
)
def test_move_failures_are_stable_and_leave_source_bytes_unchanged(
    mutation: str, expected: ScheduleCommandFailure
) -> None:
    source, problem = _source_bundle()
    before = canonical_workspace_bytes(source)
    assignment = _first_assignment(source)
    payload = {
        "operation_id": assignment["operation_id"],
        "resource_id": assignment["resource_id"],
        "start_at_utc": "2026-09-01T00:03:00Z",
        "end_at_utc": "2026-09-01T00:04:00Z",
    }
    if mutation == "unknown-resource":
        payload["resource_id"] = "resource-absent"
    elif mutation == "bad-duration":
        payload["end_at_utc"] = "2026-09-01T00:05:00Z"
    command = _command(source, "MOVE_OPERATION", payload, key="p3-unit-negative01")
    if mutation == "stale":
        command["expected_content_fingerprint"] = "sha256:" + "f" * 64
        command["request_fingerprint"] = workspace_command_fingerprint(command)
    context = _context() if mutation == "unauthorized" else _context("edit")

    with pytest.raises(ScheduleCommandError) as captured:
        prepare_schedule_command(
            source, problem, command, context, data_plane="SIMULATION"
        )

    assert captured.value.reason is expected
    assert canonical_workspace_bytes(source) == before


def test_production_is_default_denied_even_with_edit_capability() -> None:
    source, problem = _source_bundle()
    production_source = deepcopy(source)
    production_source.update(
        {
            "data_plane": "PRODUCTION",
            "environment": "PRODUCTION",
            "synthetic": False,
        }
    )
    production_source.pop("synthetic_provenance")
    assignment = _first_assignment(source)
    command = _command(
        source,
        "MOVE_OPERATION",
        {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": "2026-09-01T00:03:00Z",
            "end_at_utc": "2026-09-01T00:04:00Z",
        },
        key="p3-unit-production1",
    )
    command.update(
        {
            "data_plane": "PRODUCTION",
            "environment": "PRODUCTION",
            "synthetic": False,
        }
    )
    command.pop("synthetic_provenance")
    command["idempotency_scope"] = (
        f"PRODUCTION/MOVE_OPERATION/{source['schedule_version_id']}/WORKSPACE_INTERNAL"
    )
    command["request_fingerprint"] = workspace_command_fingerprint(command)

    with pytest.raises(ScheduleCommandError) as captured:
        prepare_schedule_command(
            production_source,
            problem,
            command,
            _context("edit"),
            data_plane="PRODUCTION",
        )

    assert captured.value.reason is (
        ScheduleCommandFailure.PRODUCTION_AUTHORITY_UNAVAILABLE
    )
