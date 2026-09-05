"""TEST-P8-PLANNING-RUN-001 application orchestration evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import pytest

from app.application.planning_runs import (
    PlanningRunAttemptFailureCommand,
    PlanningRunCancelCommand,
    PlanningRunOrchestrationService,
    PlanningRunRetryCommand,
    PlanningRunTransitionCommand,
)
from app.domain.planning_run import (
    PlanningRunActionResult,
    PlanningRunAttemptStatus,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
)
from backend.tests.contract.p8_planning_run_support import (
    InMemoryPlanningRunRepository,
    canonical_ingress_record,
    command_context,
    schemas,
)


def _materialized() -> tuple[
    PlanningRunOrchestrationService,
    InMemoryPlanningRunRepository,
    PlanningRunActionResult,
]:
    repository = InMemoryPlanningRunRepository()
    service = PlanningRunOrchestrationService(schemas=schemas(), repository=repository)
    result = service.materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    return service, repository, result


def test_materialize_read_and_exact_replay_do_not_duplicate_side_effects() -> None:
    service, repository, created = _materialized()
    replayed = service.materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )

    assert created.aggregate.document["state"] == "CREATED"
    assert created.aggregate.document["attempt"] is None
    assert created.attempt is not None
    assert created.attempt.document["status"] == "QUEUED"
    assert created.work_item is not None
    assert created.work_item.document["expected_run_state"] == "CREATED"
    assert replayed.replayed is True
    assert replayed.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert replayed.attempt is not None
    assert replayed.attempt.canonical_bytes == created.attempt.canonical_bytes
    assert repository.audit_count == 1
    assert repository.transition_count == 1

    run_id = cast(str, created.aggregate.document["planning_run_id"])
    loaded = service.read(run_id, context=command_context(capabilities=("view",)))
    assert loaded.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert len(loaded.attempts) == len(loaded.work_items) == 1


def test_materialize_same_ingress_with_changed_window_is_a_conflict() -> None:
    service, _repository, _created = _materialized()

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        service.materialize(
            canonical_ingress_record(),
            context=command_context(),
            available_at_utc="2026-09-05T00:00:02Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        )

    assert captured.value.code is PlanningRunErrorCode.IDEMPOTENCY_CONFLICT


def test_legal_transition_replay_and_stale_or_self_transition_rejection() -> None:
    service, repository, created = _materialized()
    run = created.aggregate.document
    command = PlanningRunTransitionCommand(
        planning_run_id=cast(str, run["planning_run_id"]),
        expected_revision=cast(int, run["revision"]),
        expected_state=cast(str, run["state"]),
        expected_run_fingerprint=cast(str, run["run_fingerprint"]),
        to_state="INGESTING",
        idempotency_key="p8-transition-ingesting-0001",
        reason="Begin deterministic canonical input ingestion.",
        artifacts=cast(Mapping[str, object], run["artifacts"]),
    )

    transitioned = service.transition(
        command, context=command_context(occurred_at_utc="2026-09-05T00:00:02Z")
    )
    replayed = service.transition(
        command, context=command_context(occurred_at_utc="2026-09-05T00:00:02Z")
    )

    assert transitioned.aggregate.document["state"] == "INGESTING"
    assert transitioned.aggregate.document["revision"] == 2
    assert transitioned.aggregate.document["attempt"] is None
    assert replayed.replayed is True
    assert replayed.aggregate.canonical_bytes == transitioned.aggregate.canonical_bytes
    assert repository.transition_count == 2

    stale = replace(
        command,
        to_state="FAILED",
        idempotency_key="p8-stale-transition-0001",
    )
    with pytest.raises(PlanningRunOrchestrationError) as stale_error:
        service.transition(stale, context=command_context())
    assert stale_error.value.code is PlanningRunErrorCode.STALE_RUN

    current = transitioned.aggregate.document
    self_transition = PlanningRunTransitionCommand(
        planning_run_id=cast(str, current["planning_run_id"]),
        expected_revision=cast(int, current["revision"]),
        expected_state=cast(str, current["state"]),
        expected_run_fingerprint=cast(str, current["run_fingerprint"]),
        to_state="INGESTING",
        idempotency_key="p8-self-transition-0001",
        reason="Self transitions are forbidden.",
        artifacts=cast(Mapping[str, object], current["artifacts"]),
    )
    with pytest.raises(PlanningRunOrchestrationError) as pair_error:
        service.transition(self_transition, context=command_context())
    assert pair_error.value.code is PlanningRunErrorCode.INVALID_STATE_TRANSITION


def test_cancel_updates_queued_attempt_without_forging_started_evidence() -> None:
    service, _repository, created = _materialized()
    run = created.aggregate.document
    cancelled = service.cancel(
        PlanningRunCancelCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=cast(int, run["revision"]),
            expected_state=cast(str, run["state"]),
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            idempotency_key="p8-cancel-created-0001",
            reason="Operator cancelled before dispatch.",
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )

    assert cancelled.aggregate.document["state"] == "CANCELLED"
    assert cancelled.aggregate.document["terminal"] is True
    assert cancelled.aggregate.document["attempt"] is None
    assert cancelled.aggregate.document["error"]["code"] == "RUN_CANCELLED"
    assert cancelled.attempt is not None
    assert cancelled.attempt.document["status"] == "CANCELLED"
    loaded = service.read(cast(str, run["planning_run_id"]), context=command_context())
    assert loaded.attempts[-1].document["status"] == "CANCELLED"

    with pytest.raises(PlanningRunOrchestrationError) as terminal_error:
        service.record_attempt_failure(
            PlanningRunAttemptFailureCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=2,
                expected_state="CANCELLED",
                expected_run_fingerprint=cast(
                    str, cancelled.aggregate.document["run_fingerprint"]
                ),
                attempt_id=cast(str, cancelled.attempt.document["attempt_id"]),
                attempt_number=1,
                expected_attempt_revision=2,
                outcome=PlanningRunAttemptStatus.TIMED_OUT,
                failure_code="ATTEMPT_TIMEOUT",
                idempotency_key="p8-terminal-attempt-0001",
                reason="A terminal run cannot accept a later timeout.",
            ),
            context=command_context(),
        )
    assert terminal_error.value.code is PlanningRunErrorCode.INVALID_STATE_TRANSITION


def test_terminal_transition_requires_latest_durable_attempt_binding() -> None:
    service, _repository, created = _materialized()
    run = created.aggregate.document

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        service.transition(
            PlanningRunTransitionCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=cast(int, run["revision"]),
                expected_state=cast(str, run["state"]),
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                to_state="FAILED",
                idempotency_key="p8-terminal-without-attempt-0001",
                reason="Terminal transition must not orphan the queued attempt.",
                artifacts=cast(Mapping[str, object], run["artifacts"]),
            ),
            context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
        )

    assert captured.value.code is PlanningRunErrorCode.INVALID_REFERENCE


def test_dispatch_failure_retry_and_command_conflict_preserve_run_revision() -> None:
    service, repository, created = _materialized()
    assert created.attempt is not None
    run = created.aggregate.document
    attempt = created.attempt.document
    failure_command = PlanningRunAttemptFailureCommand(
        planning_run_id=cast(str, run["planning_run_id"]),
        expected_revision=cast(int, run["revision"]),
        expected_state=cast(str, run["state"]),
        expected_run_fingerprint=cast(str, run["run_fingerprint"]),
        attempt_id=cast(str, attempt["attempt_id"]),
        attempt_number=cast(int, attempt["attempt_number"]),
        expected_attempt_revision=cast(int, attempt["revision"]),
        outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
        failure_code="QUEUE_UNAVAILABLE",
        idempotency_key="p8-dispatch-failed-0001",
        reason="Queue dispatch failed before worker ownership.",
    )
    failed = service.record_attempt_failure(
        failure_command,
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    failed_replay = service.record_attempt_failure(
        failure_command,
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )

    assert failed.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert failed.attempt is not None
    assert failed.attempt.document["status"] == "DISPATCH_FAILED"
    assert failed_replay.replayed is True

    retry_command = PlanningRunRetryCommand(
        planning_run_id=cast(str, run["planning_run_id"]),
        expected_revision=cast(int, run["revision"]),
        expected_state=cast(str, run["state"]),
        expected_run_fingerprint=cast(str, run["run_fingerprint"]),
        failed_attempt_id=cast(str, failed.attempt.document["attempt_id"]),
        failed_attempt_number=1,
        idempotency_key="p8-retry-attempt-0001",
        reason="Retry the failed dispatch with the same immutable inputs.",
        available_at_utc="2026-09-05T00:00:04Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    retried = service.retry(
        retry_command,
        context=command_context(occurred_at_utc="2026-09-05T00:00:03Z"),
    )

    assert retried.aggregate.canonical_bytes == created.aggregate.canonical_bytes
    assert retried.attempt is not None
    assert retried.attempt.document["attempt_number"] == 2
    assert retried.attempt.document["status"] == "QUEUED"
    assert retried.work_item is not None
    assert (
        retried.work_item.document["attempt_id"]
        == retried.attempt.document["attempt_id"]
    )
    loaded = service.read(cast(str, run["planning_run_id"]), context=command_context())
    assert len(loaded.attempts) == len(loaded.work_items) == 2
    assert repository.audit_count == 3
    assert repository.transition_count == 1

    conflicting = replace(retry_command, reason="Different command content.")
    with pytest.raises(PlanningRunOrchestrationError) as conflict:
        service.retry(conflicting, context=command_context())
    assert conflict.value.code is PlanningRunErrorCode.IDEMPOTENCY_CONFLICT


def test_retryable_terminal_attempt_must_retry_or_explicitly_terminalize_run() -> None:
    service, _repository, created = _materialized()
    assert created.attempt is not None
    run = created.aggregate.document
    attempt = created.attempt.document
    failure_command = PlanningRunAttemptFailureCommand(
        planning_run_id=cast(str, run["planning_run_id"]),
        expected_revision=1,
        expected_state="CREATED",
        expected_run_fingerprint=cast(str, run["run_fingerprint"]),
        attempt_id=cast(str, attempt["attempt_id"]),
        attempt_number=1,
        expected_attempt_revision=1,
        outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
        failure_code="QUEUE_UNAVAILABLE",
        idempotency_key="p8-terminal-attempt-choice-0001",
        reason="Persist dispatch failure before selecting retry or cancellation.",
    )
    failed = service.record_attempt_failure(
        failure_command,
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    assert failed.attempt is not None

    with pytest.raises(PlanningRunOrchestrationError) as progress_error:
        service.transition(
            PlanningRunTransitionCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=1,
                expected_state="CREATED",
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                to_state="INGESTING",
                idempotency_key="p8-progress-dead-attempt-0001",
                reason="A failed attempt cannot continue the run.",
                artifacts=cast(Mapping[str, object], run["artifacts"]),
            ),
            context=command_context(occurred_at_utc="2026-09-05T00:00:03Z"),
        )
    assert progress_error.value.code is PlanningRunErrorCode.ATTEMPT_NOT_RETRYABLE

    cancelled = service.cancel(
        PlanningRunCancelCommand(
            planning_run_id=cast(str, run["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, run["run_fingerprint"]),
            idempotency_key="p8-cancel-after-dispatch-failure-0001",
            reason="Explicitly close the run without rewriting failed attempt evidence.",
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:04Z"),
    )
    assert cancelled.aggregate.document["state"] == "CANCELLED"
    assert cancelled.attempt is not None
    assert cancelled.attempt.canonical_bytes == failed.attempt.canonical_bytes

    replayed_failure = service.record_attempt_failure(
        failure_command,
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    assert replayed_failure.replayed is True
    assert replayed_failure.aggregate.document["state"] == "CREATED"
    assert service.read(
        cast(str, run["planning_run_id"]), context=command_context()
    ).aggregate.document["state"] == "CANCELLED"


def test_unsupported_attempt_outcome_has_stable_unknown_outcome_error() -> None:
    service, _repository, created = _materialized()
    assert created.attempt is not None
    run = created.aggregate.document
    attempt = created.attempt.document

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        service.record_attempt_failure(
            PlanningRunAttemptFailureCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=1,
                expected_state="CREATED",
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                attempt_id=cast(str, attempt["attempt_id"]),
                attempt_number=1,
                expected_attempt_revision=1,
                outcome=PlanningRunAttemptStatus.FAILED,
                failure_code="UNSUPPORTED_OUTCOME",
                idempotency_key="p8-unknown-outcome-0001",
                reason="P8-04 only records dispatch failure or timeout intent.",
            ),
            context=command_context(),
        )

    assert captured.value.code is PlanningRunErrorCode.UNKNOWN_OUTCOME
