"""Pure ExportJob state, attempt, heartbeat, and lease invariants for P3."""

from __future__ import annotations

from datetime import datetime

from app.domain.state_machines.contracts import (
    ExportJobState,
    StateMachineName,
    StateTransitionError,
    require_transition,
)


class ExportJobPersistenceTransitionError(ValueError):
    """A persistence CAS candidate violates the frozen ExportJob contract."""


class ExportJobLeaseError(ExportJobPersistenceTransitionError):
    """The supplied worker lease is absent, expired, or owned elsewhere."""


def _attempt(document: dict[str, object]) -> int:
    value = document.get("attempt")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ExportJobPersistenceTransitionError(
            "ExportJob attempt must be a non-negative integer"
        )
    return value


def require_export_job_transition(
    current: dict[str, object],
    candidate: dict[str, object],
    *,
    lease_expires_at_utc: datetime | None,
) -> tuple[str, str]:
    """Require a frozen state pair plus exact attempt/lease semantics."""

    source = current.get("state")
    target = candidate.get("state")
    if not isinstance(source, str) or not isinstance(target, str):
        raise ExportJobPersistenceTransitionError(
            "ExportJob state must be non-empty text"
        )
    try:
        require_transition(StateMachineName.EXPORT_JOB, source, target)
    except StateTransitionError as error:
        raise ExportJobPersistenceTransitionError(
            f"unsupported ExportJob transition: {source} -> {target}"
        ) from error

    current_attempt = _attempt(current)
    candidate_attempt = _attempt(candidate)
    if target == ExportJobState.EXPORTING.value:
        if candidate_attempt != current_attempt + 1:
            raise ExportJobPersistenceTransitionError(
                "claim/retry must increment ExportJob attempt exactly once"
            )
        if not isinstance(candidate.get("lease_reference"), str):
            raise ExportJobLeaseError("EXPORTING requires a lease reference")
        if lease_expires_at_utc is None:
            raise ExportJobLeaseError("EXPORTING requires an explicit lease expiry")
    else:
        if candidate_attempt != current_attempt:
            raise ExportJobPersistenceTransitionError(
                "non-claim transition must preserve ExportJob attempt"
            )
        if candidate.get("lease_reference") is not None:
            raise ExportJobLeaseError("non-EXPORTING state must release its lease")
        if lease_expires_at_utc is not None:
            raise ExportJobLeaseError("non-EXPORTING state cannot retain lease expiry")
    return source, target


def require_export_job_heartbeat(
    current: dict[str, object],
    candidate: dict[str, object],
    *,
    expected_lease_reference: str,
    stored_lease_expires_at_utc: datetime,
    observed_at_utc: datetime,
    new_lease_expires_at_utc: datetime,
) -> None:
    """Validate a same-state heartbeat without inventing a self-transition."""

    if current.get("state") != ExportJobState.EXPORTING.value:
        raise ExportJobLeaseError("only EXPORTING jobs can heartbeat")
    if candidate.get("state") != ExportJobState.EXPORTING.value:
        raise ExportJobLeaseError("heartbeat cannot change ExportJob state")
    if current.get("lease_reference") != expected_lease_reference:
        raise ExportJobLeaseError("worker does not own the active ExportJob lease")
    if candidate.get("lease_reference") != expected_lease_reference:
        raise ExportJobLeaseError("heartbeat must preserve the active lease reference")
    if observed_at_utc >= stored_lease_expires_at_utc:
        raise ExportJobLeaseError("ExportJob lease has expired")
    if new_lease_expires_at_utc <= observed_at_utc:
        raise ExportJobLeaseError("heartbeat lease expiry must be in the future")
    if _attempt(candidate) != _attempt(current):
        raise ExportJobPersistenceTransitionError(
            "heartbeat must preserve ExportJob attempt"
        )


__all__ = [
    "ExportJobLeaseError",
    "ExportJobPersistenceTransitionError",
    "require_export_job_heartbeat",
    "require_export_job_transition",
]
