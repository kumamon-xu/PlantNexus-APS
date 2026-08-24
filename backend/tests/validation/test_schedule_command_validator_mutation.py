from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
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
    build_schedule_command_documents,
    prepare_schedule_command,
)
from app.domain.schedule_version import (
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
)
from app.domain.types import format_utc_instant, parse_utc_instant
from app.domain.workspace_contracts import (
    schedule_content_fingerprint,
    workspace_command_fingerprint,
    workspace_fingerprint,
)
from app.planning.reporting import build_kpi_v2
from app.planning.validation import validate_problem_schedule
from app.simulation.scenarios.p2_correctness import (
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)


ROOT = Path(__file__).resolve().parents[3]
CONTEXT = ScheduleCommandContext(
    actor_ref="actor:p3-command-validation",
    resolved_capabilities=frozenset({"edit"}),
    auth_policy_version="simulation-command-policy.v1",
    occurred_at_utc="2026-08-24T10:20:00Z",
    code_commit="uncommitted",
)


def _command(
    source: dict[str, object],
    command_type: str,
    payload: dict[str, object],
    key: str,
) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": "edit",
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
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Exercise the independent command validation boundary.",
        "correlation_id": f"correlation-{key}",
        "payload": payload,
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def test_server_accepted_move_is_still_rejected_after_formula_independent_mutation() -> (
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
    command = _command(
        source,
        "MOVE_OPERATION",
        {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": "2026-09-01T00:03:00Z",
            "end_at_utc": "2026-09-01T00:04:00Z",
        },
        "p3-validation-move1",
    )
    prepared = prepare_schedule_command(
        source, output.problem, command, CONTEXT, data_plane="SIMULATION"
    )
    assert (
        validate_problem_schedule(output.problem, prepared.validator_candidate)[
            "status"
        ]
        == "PASS"
    )

    mutated_candidate = deepcopy(prepared.validator_candidate)
    mutated_assignments = cast(
        list[dict[str, object]], mutated_candidate["assignments"]
    )
    mutated_assignments[0]["resource_id"] = "resource-not-a-candidate"
    failed_report = validate_problem_schedule(output.problem, mutated_candidate)

    assert failed_report["status"] == "FAIL"
    assert failed_report["hard_violation_count"] >= 1
    assert "C-003" in {
        violation["constraint_id"]
        for violation in cast(list[dict[str, object]], failed_report["violations"])
    }
    with pytest.raises(ScheduleCommandError) as captured:
        build_schedule_command_documents(prepared, failed_report)
    assert captured.value.reason is ScheduleCommandFailure.VALIDATION_FAILED


def _fjsp_assignable_source() -> tuple[dict[str, object], dict[str, object], str, str]:
    case = next(
        value
        for value in load_correctness_cases(ROOT)
        if value.scenario_id == "P2-GOLDEN-FJSP"
    )
    replay = execute_correctness_case(case, root=ROOT)
    verify_correctness_replay(replay)
    kpi = build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )
    output = ValidatedPlanningOutput(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        kpi=kpi.document,
    )
    original = build_reviewable_schedule_documents(
        output,
        lifecycle_context(
            "f",
            correlation_id="correlation-p3-fjsp-source",
        ),
        data_plane="SIMULATION",
    ).ready_for_review
    solution = deepcopy(replay.solution)
    operations = {
        value["operation_id"]: value for value in replay.problem["operation_instances"]
    }
    operation_id = next(
        value["operation_id"]
        for value in replay.problem["operation_instances"]
        if len(value["resource_options"]) >= 2
    )
    options = operations[operation_id]["resource_options"]
    source_resource = options[0]["resource_id"]
    target_resource = options[1]["resource_id"]
    assignment = next(
        value
        for value in solution["assignments"]
        if value["operation_id"] == operation_id
    )
    tick_seconds = replay.problem["tick_seconds"]
    horizon_start = parse_utc_instant(replay.problem["horizon_start_utc"])
    duration_seconds = options[0]["final_duration_seconds"]
    duration_ticks = (duration_seconds + tick_seconds - 1) // tick_seconds
    assignment.update(
        {
            "resource_id": source_resource,
            "start_tick": 1,
            "end_tick": 1 + duration_ticks,
            "duration_ticks": duration_ticks,
            "start_at_utc": format_utc_instant(
                horizon_start + timedelta(seconds=tick_seconds)
            ),
            "end_at_utc": format_utc_instant(
                horizon_start + timedelta(seconds=(1 + duration_ticks) * tick_seconds)
            ),
            "duration_seconds": duration_seconds,
        }
    )
    source_report = validate_problem_schedule(replay.problem, solution)
    assert source_report["status"] == "PASS"
    source = deepcopy(original)
    source["schedule_version_id"] = "schedule-version-fjsp-assignable-source"
    source["revision"] = 2
    source["state"] = "DRAFT"
    source["source_kind"] = "MANUAL_EDIT"
    source["parent_schedule_version"] = {
        "schedule_version_id": original["schedule_version_id"],
        "state": original["state"],
        "content_fingerprint": original["content_fingerprint"],
    }
    cast(dict[str, object], source["content"])["assignments"] = solution["assignments"]
    report_fingerprint = workspace_fingerprint(source_report)
    report_reference = {
        "document_version": "validation-report.v2",
        "artifact_id": f"validation-report-{report_fingerprint.removeprefix('sha256:')}",
        "fingerprint": report_fingerprint,
    }
    cast(dict[str, object], source["lineage"])["validation_report"] = report_reference
    source["validation"] = {
        "validation_report": report_reference,
        "status": "PASS",
        "hard_violation_count": 0,
        "validated_at_utc": "2026-08-24T10:15:00Z",
    }
    source["allowed_actions"] = ["view", "edit", "lock"]
    source["content_fingerprint"] = schedule_content_fingerprint(source)
    return source, dict(replay.problem), operation_id, cast(str, target_resource)


def test_assign_resource_preserves_start_recomputes_duration_and_passes_formal_validator() -> (
    None
):
    source, problem, operation_id, target_resource = _fjsp_assignable_source()
    command = _command(
        source,
        "ASSIGN_RESOURCE",
        {"operation_id": operation_id, "resource_id": target_resource},
        "p3-validation-assign1",
    )
    prepared = prepare_schedule_command(
        source, problem, command, CONTEXT, data_plane="SIMULATION"
    )
    report = validate_problem_schedule(problem, prepared.validator_candidate)
    documents = build_schedule_command_documents(prepared, report)
    assignment = next(
        value
        for value in cast(
            list[dict[str, object]],
            cast(dict[str, object], documents.draft["content"])["assignments"],
        )
        if value["operation_id"] == operation_id
    )

    assert report["status"] == "PASS"
    assert assignment["resource_id"] == target_resource
    assert assignment["start_tick"] == 1
    assert documents.draft["source_kind"] == "MANUAL_EDIT"
