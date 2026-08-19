"""TEST-IDEMPOTENCY P0 primitive and worker lease evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.jobs.contracts import (
    JobStatus,
    JobTransitionError,
    LeaseExpiredError,
    LeaseOwnershipError,
    claim_job,
    complete_job,
    heartbeat_job,
    mark_stalled,
    new_job,
)
from app.jobs.idempotency import (
    IdempotencyConflictError,
    InMemoryIdempotencyStore,
)

START = datetime(2026, 8, 19, 0, 0, tzinfo=UTC)


def _new_job():  # type annotation inferred as the immutable contract type
    return new_job(
        job_id="job-001",
        job_kind="engineering-test",
        idempotency_key="idem-001",
        request_fingerprint="a" * 64,
        now=START,
    )


def test_heartbeat_extends_lease_and_expiry_becomes_stalled_retry() -> None:
    queued = _new_job()
    running = claim_job(
        queued,
        worker_id="worker-a",
        now=START,
        lease_seconds=120,
    )
    assert running.status is JobStatus.RUNNING
    assert running.attempt == 1
    assert running.lease_expires_at == START + timedelta(seconds=120)

    heartbeated = heartbeat_job(
        running,
        worker_id="worker-a",
        now=START + timedelta(seconds=30),
        lease_seconds=120,
    )
    assert heartbeated.heartbeat_at == START + timedelta(seconds=30)
    assert heartbeated.lease_expires_at == START + timedelta(seconds=150)
    assert mark_stalled(
        heartbeated,
        now=START + timedelta(seconds=149),
    ) is heartbeated

    stalled = mark_stalled(
        heartbeated,
        now=START + timedelta(seconds=150),
    )
    assert stalled.status is JobStatus.STALLED
    assert stalled.worker_id is None
    assert stalled.lease_expires_at is None

    retried = claim_job(
        stalled,
        worker_id="worker-b",
        now=START + timedelta(seconds=151),
        lease_seconds=120,
    )
    assert retried.status is JobStatus.RUNNING
    assert retried.attempt == 2
    assert retried.worker_id == "worker-b"


def test_lease_owner_expiry_and_terminal_transition_are_distinct() -> None:
    running = claim_job(
        _new_job(),
        worker_id="worker-a",
        now=START,
        lease_seconds=60,
    )
    with pytest.raises(LeaseOwnershipError):
        heartbeat_job(
            running,
            worker_id="worker-b",
            now=START + timedelta(seconds=1),
            lease_seconds=60,
        )
    with pytest.raises(LeaseExpiredError):
        complete_job(
            running,
            worker_id="worker-a",
            now=START + timedelta(seconds=60),
            succeeded=True,
        )

    succeeded = complete_job(
        running,
        worker_id="worker-a",
        now=START + timedelta(seconds=59),
        succeeded=True,
    )
    assert succeeded.status is JobStatus.SUCCEEDED
    assert succeeded.finished_at == START + timedelta(seconds=59)
    with pytest.raises(JobTransitionError):
        claim_job(
            succeeded,
            worker_id="worker-c",
            now=START + timedelta(seconds=61),
            lease_seconds=60,
        )


def test_failed_job_requires_stable_failure_code() -> None:
    running = claim_job(
        _new_job(),
        worker_id="worker-a",
        now=START,
        lease_seconds=60,
    )
    with pytest.raises(ValueError):
        complete_job(
            running,
            worker_id="worker-a",
            now=START + timedelta(seconds=1),
            succeeded=False,
        )
    failed = complete_job(
        running,
        worker_id="worker-a",
        now=START + timedelta(seconds=1),
        succeeded=False,
        failure_code="DEPENDENCY_UNAVAILABLE",
    )
    assert failed.status is JobStatus.FAILED
    assert failed.failure_code == "DEPENDENCY_UNAVAILABLE"


def test_job_timestamps_require_utc() -> None:
    with pytest.raises(ValueError):
        new_job(
            job_id="job-001",
            job_kind="engineering-test",
            idempotency_key="idem-001",
            request_fingerprint="a" * 64,
            now=datetime(2026, 8, 19),
        )
    with pytest.raises(ValueError):
        new_job(
            job_id="job-001",
            job_kind="engineering-test",
            idempotency_key="idem-001",
            request_fingerprint="a" * 64,
            now=datetime(2026, 8, 19, tzinfo=timezone(timedelta(hours=8))),
        )
    with pytest.raises(ValueError):
        new_job(
            job_id="job-001",
            job_kind="engineering-test",
            idempotency_key="idem-001",
            request_fingerprint="not-a-sha256",
            now=START,
        )


def test_idempotent_replay_and_conflict_are_atomic() -> None:
    store = InMemoryIdempotencyStore()

    def register_once(_: int):
        return store.register(
            scope="engineering-test",
            key="idem-001",
            request_fingerprint="b" * 64,
            logical_id="logical-001",
            now=START,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(register_once, range(32)))
    assert len(store) == 1
    assert {result.logical_id for result in results} == {"logical-001"}
    assert len(set(results)) == 1

    with pytest.raises(IdempotencyConflictError):
        store.register(
            scope="engineering-test",
            key="idem-001",
            request_fingerprint="c" * 64,
            logical_id="logical-002",
            now=START + timedelta(seconds=1),
        )


def test_idempotency_scope_and_fingerprint_are_validated() -> None:
    store = InMemoryIdempotencyStore()
    with pytest.raises(ValueError):
        store.register(
            scope="",
            key="idem-001",
            request_fingerprint="b" * 64,
            logical_id="logical-001",
            now=START,
        )
    with pytest.raises(ValueError):
        store.register(
            scope="engineering-test",
            key="idem-001",
            request_fingerprint="not-a-sha256",
            logical_id="logical-001",
            now=START,
        )
