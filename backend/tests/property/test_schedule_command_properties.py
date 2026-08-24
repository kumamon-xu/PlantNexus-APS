from __future__ import annotations

from pathlib import Path
from typing import cast

from hypothesis import given, settings, strategies as st

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.schedule_commands import (
    ScheduleCommandContext,
    build_schedule_command_documents,
    prepare_schedule_command,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)
from app.planning.validation import validate_problem_schedule


ROOT = Path(__file__).resolve().parents[3]
_OUTPUT, _ = load_fixed_validated_output(ROOT)
_SOURCE = build_reviewable_schedule_documents(
    _OUTPUT,
    lifecycle_context(),
    data_plane="SIMULATION",
).ready_for_review
_PROBLEM = dict(_OUTPUT.problem)
_ASSIGNMENT = cast(
    list[dict[str, object]],
    cast(dict[str, object], _SOURCE["content"])["assignments"],
)[0]
_CONTEXT = ScheduleCommandContext(
    actor_ref="actor:p3-command-property",
    resolved_capabilities=frozenset({"lock"}),
    auth_policy_version="simulation-command-policy.v1",
    occurred_at_utc="2026-08-24T10:10:00Z",
    code_commit="uncommitted",
)


@settings(max_examples=24, deadline=None)
@given(
    suffix=st.text(
        alphabet=st.sampled_from(tuple("abcdefghijklmnopqrstuvwxyz0123456789")),
        min_size=8,
        max_size=20,
    )
)
def test_soft_lock_commands_are_deterministic_copy_on_write_and_source_immutable(
    suffix: str,
) -> None:
    source_before = canonical_workspace_bytes(_SOURCE)
    key = f"p3-property-{suffix}"
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{suffix}",
        "command_type": "SET_LOCK",
        "required_capability": "lock",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/SET_LOCK/{_SOURCE['schedule_version_id']}/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": _SOURCE["schedule_version_id"],
        "expected_state": _SOURCE["state"],
        "expected_content_fingerprint": _SOURCE["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": _SOURCE["environment"],
        "synthetic": True,
        "synthetic_provenance": _SOURCE["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Add one version-local synthetic soft lock.",
        "correlation_id": f"correlation-{suffix}",
        "payload": {
            "lock": {
                "lock_id": f"lock-property-{suffix}",
                "operation_id": _ASSIGNMENT["operation_id"],
                "lock_type": "SOFT",
                "resource_id": None,
                "start_at_utc": None,
                "end_at_utc": None,
            }
        },
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)

    first = prepare_schedule_command(
        _SOURCE,
        _PROBLEM,
        command,
        _CONTEXT,
        data_plane="SIMULATION",
    )
    second = prepare_schedule_command(
        _SOURCE,
        _PROBLEM,
        command,
        _CONTEXT,
        data_plane="SIMULATION",
    )
    first_report = validate_problem_schedule(_PROBLEM, first.validator_candidate)
    second_report = validate_problem_schedule(_PROBLEM, second.validator_candidate)
    first_documents = build_schedule_command_documents(first, first_report)
    second_documents = build_schedule_command_documents(second, second_report)

    assert first == second
    assert first_report == second_report
    assert first_documents == second_documents
    assert first_report["status"] == "PASS"
    assert (
        first_documents.draft["schedule_version_id"] != _SOURCE["schedule_version_id"]
    )
    assert (
        first_documents.draft["content_fingerprint"] != _SOURCE["content_fingerprint"]
    )
    assert canonical_workspace_bytes(_SOURCE) == source_before
