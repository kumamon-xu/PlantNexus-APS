"""Pure domain value helpers for versioned APS contracts.

These helpers deliberately depend only on the Python standard library. They
do not normalize source data, invent defaults, or construct solver objects.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NewType


CanonicalId = NewType("CanonicalId", str)
DurationSeconds = NewType("DurationSeconds", int)
TickSeconds = NewType("TickSeconds", int)


class ContractValueError(ValueError):
    """A value cannot be represented by the P0 contract skeleton."""


def canonical_id(value: str) -> CanonicalId:
    """Return a non-empty, whitespace-free canonical identifier."""

    if not isinstance(value, str) or not value or len(value) > 256:
        raise ContractValueError("canonical ID must contain 1 to 256 characters")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise ContractValueError("canonical ID must not contain whitespace or control characters")
    return CanonicalId(value)


def require_utc(value: datetime) -> datetime:
    """Reject naive or non-UTC datetimes without silently converting them."""

    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ContractValueError("timestamp must be timezone-aware UTC")
    return value.astimezone(UTC)


def parse_utc_instant(value: str) -> datetime:
    """Parse the contract's RFC 3339 UTC form, which must end in ``Z``."""

    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractValueError("timestamp must use RFC 3339 UTC form ending in Z")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as error:
        raise ContractValueError("timestamp is not a valid RFC 3339 instant") from error
    return require_utc(parsed)


def format_utc_instant(value: datetime) -> str:
    """Serialize a UTC datetime in stable second-precision RFC 3339 form."""

    return require_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def require_duration_seconds(value: int, *, allow_zero: bool = True) -> DurationSeconds:
    """Validate an integer duration without accepting booleans or floats."""

    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ContractValueError(f"duration_seconds must be a {qualifier} integer")
    return DurationSeconds(value)


def require_tick_seconds(value: int) -> TickSeconds:
    """Validate a positive integer solver tick size."""

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractValueError("tick_seconds must be a positive integer")
    return TickSeconds(value)


def duration_to_ticks(duration_seconds: int, tick_seconds: int) -> int:
    """Return ``ceil(duration_seconds / tick_seconds)`` using integer math."""

    duration = int(require_duration_seconds(duration_seconds))
    tick = int(require_tick_seconds(tick_seconds))
    return (duration + tick - 1) // tick


__all__ = [
    "CanonicalId",
    "ContractValueError",
    "DurationSeconds",
    "TickSeconds",
    "canonical_id",
    "duration_to_ticks",
    "format_utc_instant",
    "parse_utc_instant",
    "require_duration_seconds",
    "require_tick_seconds",
    "require_utc",
]
