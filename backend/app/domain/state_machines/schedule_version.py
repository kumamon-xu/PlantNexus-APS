"""Pure persistence-facing ScheduleVersion transition invariants for P3."""

from __future__ import annotations

from hashlib import sha256
import json

from app.domain.state_machines.contracts import (
    ScheduleVersionState,
    StateMachineName,
    StateTransitionError,
    require_transition,
)

_MUTABLE_STATE_FIELDS = frozenset(
    {"state", "decision", "publication", "superseded_by", "allowed_actions"}
)


class ScheduleVersionPersistenceTransitionError(ValueError):
    """A CAS candidate violates the frozen state/content contract."""


def immutable_schedule_projection(document: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in document.items()
        if key not in _MUTABLE_STATE_FIELDS
    }


def immutable_schedule_fingerprint(document: dict[str, object]) -> str:
    canonical = json.dumps(
        immutable_schedule_projection(document),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def require_schedule_version_transition(
    current: dict[str, object],
    candidate: dict[str, object],
) -> tuple[str, str]:
    """Require an existing state pair while preserving all version content."""

    source = current.get("state")
    target = candidate.get("state")
    if not isinstance(source, str) or not isinstance(target, str):
        raise ScheduleVersionPersistenceTransitionError(
            "ScheduleVersion state must be non-empty text"
        )
    try:
        require_transition(StateMachineName.SCHEDULE_VERSION, source, target)
    except StateTransitionError as error:
        raise ScheduleVersionPersistenceTransitionError(
            f"unsupported ScheduleVersion transition: {source} -> {target}"
        ) from error
    if immutable_schedule_fingerprint(current) != immutable_schedule_fingerprint(
        candidate
    ):
        raise ScheduleVersionPersistenceTransitionError(
            "ScheduleVersion immutable identity, lineage, validation, or content changed"
        )
    return source, target


def is_published_content_immutable(state: str) -> bool:
    """Published content is immutable even though PUBLISHED may be superseded."""

    return state in {
        ScheduleVersionState.PUBLISHED.value,
        ScheduleVersionState.SUPERSEDED.value,
    }


__all__ = [
    "ScheduleVersionPersistenceTransitionError",
    "immutable_schedule_fingerprint",
    "immutable_schedule_projection",
    "is_published_content_immutable",
    "require_schedule_version_transition",
]
