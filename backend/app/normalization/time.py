"""Strict RFC3339-offset to UTC-second normalization."""

from __future__ import annotations

from datetime import UTC, datetime
import re

from .contracts import NormalizationError, NormalizationErrorCode

_RFC3339_SECONDS = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})"
)


def normalize_utc_instant(
    value: object,
    *,
    source_location: str,
    field: str,
) -> str:
    """Normalize an explicit RFC3339 numeric offset to canonical UTC Z."""

    if (
        not isinstance(value, str)
        or _RFC3339_SECONDS.fullmatch(value) is None
        or value.endswith("-00:00")
    ):
        raise NormalizationError(
            NormalizationErrorCode.INVALID_TIMEZONE,
            source_location=source_location,
            field=field,
            expected_contract="RFC3339 second precision with Z or explicit ±HH:MM offset",
            message="timestamp is missing an explicit valid offset or second precision",
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        offset = parsed.utcoffset()
        if offset is None or abs(offset.total_seconds()) > 14 * 60 * 60:
            raise ValueError
        normalized = parsed.astimezone(UTC)
    except (OverflowError, ValueError) as error:
        raise NormalizationError(
            NormalizationErrorCode.INVALID_TIMEZONE,
            source_location=source_location,
            field=field,
            expected_contract="valid RFC3339 timestamp with an offset from -14:00 to +14:00",
            message="timestamp or UTC offset is invalid",
        ) from error
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["normalize_utc_instant"]
