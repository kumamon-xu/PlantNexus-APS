"""TASK-P4-03 pure persistence-record and state-boundary tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from app.infrastructure.replan_persistence import (
    TERMINAL_PLANNING_RUN_STATES,
    ArtifactReference,
    ProjectionCheckpoint,
    ReplanAttemptReference,
    ReplanAuditAction,
    build_replan_attempt,
    build_replan_audit_record,
    build_replan_result,
    validate_projection_checkpoint,
    validate_replan_attempt,
    validate_replan_audit_record,
    validate_replan_result,
)
from app.infrastructure.workspace_persistence import (
    PersistenceFailure,
    WorkspacePersistenceError,
)

ROOT = Path(__file__).resolve().parents[3]
SHA_A = f"sha256:{'a' * 64}"
SHA_B = f"sha256:{'b' * 64}"
SHA_C = f"sha256:{'c' * 64}"
SHA_D = f"sha256:{'d' * 64}"


def _attempt() -> ReplanAttemptReference:
    return build_replan_attempt(
        request_id="replan-request-unit-001",
        request_fingerprint=SHA_A,
        planning_run_id="planning-run-unit-001",
        attempt_number=1,
        idempotency_scope="replan-attempt/replan-request-unit-001",
        idempotency_key_reference=SHA_B,
        correlation_id="correlation-unit-001",
        created_at_utc="2026-08-27T08:00:00Z",
    )


def test_projection_checkpoint_is_canonical_and_requires_monotonic_shape() -> None:
    checkpoint = ProjectionCheckpoint(
        factory_id="factory-unit-001",
        planning_scope_id="scope-unit-001",
        authority_id="authority-unit-001",
        stream_id="stream-unit-001",
        stream_version="1.0.0",
        last_applied_position=1,
        prefix_fingerprint=SHA_A,
        fact_checkpoint=ArtifactReference(
            "execution-fact-checkpoint.v1", "fact-checkpoint-unit-001", SHA_B
        ),
        updated_at_utc="2026-08-27T08:00:00Z",
    )
    assert validate_projection_checkpoint(checkpoint) == (
        validate_projection_checkpoint(checkpoint)
    )

    with pytest.raises(WorkspacePersistenceError) as invalid:
        validate_projection_checkpoint(
            replace(checkpoint, last_applied_position=0)
        )
    assert invalid.value.reason is PersistenceFailure.INVALID_DOCUMENT


def test_attempt_identity_is_deterministic_and_content_bound() -> None:
    attempt = _attempt()
    assert attempt == _attempt()
    assert validate_replan_attempt(attempt) == validate_replan_attempt(attempt)

    with pytest.raises(WorkspacePersistenceError) as changed:
        validate_replan_attempt(replace(attempt, planning_run_id="changed"))
    assert changed.value.reason is PersistenceFailure.INVALID_DOCUMENT


def test_result_uses_existing_planning_run_terminals_without_new_state_machine() -> None:
    registry = yaml.safe_load(
        (ROOT / "schemas/rules/state-machines.v1.yaml").read_text(encoding="utf-8")
    )
    planning_run = next(
        machine
        for machine in registry["machines"]
        if machine["machine"] == "PLANNING_RUN"
    )
    assert TERMINAL_PLANNING_RUN_STATES == frozenset(
        planning_run["terminal_states"]
    )
    assert all(machine["machine"] != "REPLAN_REQUEST" for machine in registry["machines"])

    attempt = _attempt()
    result = build_replan_result(
        attempt=attempt,
        planning_run_terminal_state="COMPLETED",
        solver_report=ArtifactReference("solver-report.v2", "solver-unit-001", SHA_A),
        validation_report=ArtifactReference(
            "validation-report.v2", "validation-unit-001", SHA_B
        ),
        new_schedule_version=ArtifactReference(
            "schedule-version.v2", "schedule-version-unit-001", SHA_C
        ),
        change_report=ArtifactReference(
            "change-report.v1", "change-report-unit-001", SHA_D
        ),
        correlation_id="correlation-unit-001",
        finished_at_utc="2026-08-27T08:01:00Z",
    )
    assert result == build_replan_result(
        attempt=attempt,
        planning_run_terminal_state="COMPLETED",
        solver_report=ArtifactReference("solver-report.v2", "solver-unit-001", SHA_A),
        validation_report=ArtifactReference(
            "validation-report.v2", "validation-unit-001", SHA_B
        ),
        new_schedule_version=ArtifactReference(
            "schedule-version.v2", "schedule-version-unit-001", SHA_C
        ),
        change_report=ArtifactReference(
            "change-report.v1", "change-report-unit-001", SHA_D
        ),
        correlation_id="correlation-unit-001",
        finished_at_utc="2026-08-27T08:01:00Z",
    )
    validate_replan_result(result)

    incomplete = replace(result, change_report=None)
    with pytest.raises(WorkspacePersistenceError) as missing:
        validate_replan_result(incomplete)
    assert missing.value.reason is PersistenceFailure.STATE_CONFLICT

    failed_with_success = build_replan_result(
        attempt=attempt,
        planning_run_terminal_state="FAILED",
        solver_report=None,
        validation_report=None,
        new_schedule_version=ArtifactReference(
            "schedule-version.v2", "schedule-version-unit-001", SHA_C
        ),
        change_report=None,
        correlation_id="correlation-unit-001",
        finished_at_utc="2026-08-27T08:01:00Z",
    )
    with pytest.raises(WorkspacePersistenceError) as false_success:
        validate_replan_result(failed_with_success)
    assert false_success.value.reason is PersistenceFailure.STATE_CONFLICT


def test_audit_record_identity_is_deterministic_and_idempotency_bound() -> None:
    record = build_replan_audit_record(
        action=ReplanAuditAction.REPLAN_ATTEMPT_LINKED,
        aggregate_type="REPLAN_ATTEMPT",
        aggregate_id="replan-attempt-unit-001",
        correlation_id="correlation-unit-001",
        idempotency_scope="audit/replan-attempt-unit-001",
        idempotency_key_reference=SHA_A,
        request_fingerprint=SHA_B,
        occurred_at_utc="2026-08-27T08:00:00Z",
    )
    assert record == build_replan_audit_record(
        action=ReplanAuditAction.REPLAN_ATTEMPT_LINKED,
        aggregate_type="REPLAN_ATTEMPT",
        aggregate_id="replan-attempt-unit-001",
        correlation_id="correlation-unit-001",
        idempotency_scope="audit/replan-attempt-unit-001",
        idempotency_key_reference=SHA_A,
        request_fingerprint=SHA_B,
        occurred_at_utc="2026-08-27T08:00:00Z",
    )
    validate_replan_audit_record(record)

    with pytest.raises(WorkspacePersistenceError) as changed:
        validate_replan_audit_record(
            replace(record, aggregate_id="different-aggregate")
        )
    assert changed.value.reason is PersistenceFailure.INVALID_DOCUMENT
