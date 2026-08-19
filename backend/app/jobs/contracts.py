"""Pure heartbeat, lease, attempt, and STALLED job transitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import re

_SHA256 = re.compile(r"[0-9a-f]{64}")


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STALLED = "STALLED"


class JobTransitionError(ValueError):
    pass


class LeaseOwnershipError(JobTransitionError):
    pass


class LeaseExpiredError(JobTransitionError):
    pass


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    job_kind: str
    idempotency_key: str
    request_fingerprint: str
    status: JobStatus
    attempt: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    finished_at: datetime | None = None
    worker_id: str | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        for name in ("job_id", "job_kind", "idempotency_key", "request_fingerprint"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")
        if _SHA256.fullmatch(self.request_fingerprint) is None:
            raise ValueError("request_fingerprint must be a lowercase SHA-256 hex digest")
        if self.attempt < 0:
            raise ValueError("attempt must not be negative")
        for name in (
            "created_at",
            "updated_at",
            "started_at",
            "heartbeat_at",
            "lease_expires_at",
            "finished_at",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_utc(value, name)


def new_job(
    *,
    job_id: str,
    job_kind: str,
    idempotency_key: str,
    request_fingerprint: str,
    now: datetime,
) -> JobRecord:
    _require_utc(now, "now")
    return JobRecord(
        job_id=job_id,
        job_kind=job_kind,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        status=JobStatus.QUEUED,
        attempt=0,
        created_at=now,
        updated_at=now,
    )


def claim_job(
    record: JobRecord,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
) -> JobRecord:
    _require_utc(now, "now")
    if not worker_id:
        raise ValueError("worker_id must not be empty")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    if record.status not in {JobStatus.QUEUED, JobStatus.STALLED}:
        raise JobTransitionError(f"cannot claim a {record.status} job")
    return replace(
        record,
        status=JobStatus.RUNNING,
        attempt=record.attempt + 1,
        updated_at=now,
        started_at=now,
        heartbeat_at=now,
        lease_expires_at=now + timedelta(seconds=lease_seconds),
        finished_at=None,
        worker_id=worker_id,
        failure_code=None,
    )


def _assert_active_lease(record: JobRecord, *, worker_id: str, now: datetime) -> None:
    _require_utc(now, "now")
    if record.status is not JobStatus.RUNNING:
        raise JobTransitionError(f"job is not running: {record.status}")
    if record.worker_id != worker_id:
        raise LeaseOwnershipError("worker does not own the active job lease")
    if record.lease_expires_at is None or now >= record.lease_expires_at:
        raise LeaseExpiredError("job lease has expired")


def heartbeat_job(
    record: JobRecord,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
) -> JobRecord:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    _assert_active_lease(record, worker_id=worker_id, now=now)
    return replace(
        record,
        updated_at=now,
        heartbeat_at=now,
        lease_expires_at=now + timedelta(seconds=lease_seconds),
    )


def mark_stalled(record: JobRecord, *, now: datetime) -> JobRecord:
    _require_utc(now, "now")
    if record.status is not JobStatus.RUNNING:
        return record
    if record.lease_expires_at is None or now < record.lease_expires_at:
        return record
    return replace(
        record,
        status=JobStatus.STALLED,
        updated_at=now,
        worker_id=None,
        lease_expires_at=None,
    )


def complete_job(
    record: JobRecord,
    *,
    worker_id: str,
    now: datetime,
    succeeded: bool,
    failure_code: str | None = None,
) -> JobRecord:
    _assert_active_lease(record, worker_id=worker_id, now=now)
    if succeeded and failure_code is not None:
        raise ValueError("a successful job cannot have a failure code")
    if not succeeded and not failure_code:
        raise ValueError("a failed job requires a non-empty failure code")
    return replace(
        record,
        status=JobStatus.SUCCEEDED if succeeded else JobStatus.FAILED,
        updated_at=now,
        finished_at=now,
        worker_id=None,
        lease_expires_at=None,
        failure_code=failure_code,
    )


def utc_now() -> datetime:
    """Clock adapter for callers; tests should pass explicit timestamps."""

    return datetime.now(UTC)


__all__ = [
    "JobRecord",
    "JobStatus",
    "JobTransitionError",
    "LeaseExpiredError",
    "LeaseOwnershipError",
    "claim_job",
    "complete_job",
    "heartbeat_job",
    "mark_stalled",
    "new_job",
    "utc_now",
]
