"""Stable canonical identifiers derived only from semantic source identity."""

from __future__ import annotations

from hashlib import sha256
import json
import re

from .contracts import NormalizationError, NormalizationErrorCode

_NAMESPACE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,63}")


def _bounded_text(
    value: object,
    *,
    field: str,
    source_location: str,
    maximum: int = 512,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise NormalizationError(
            NormalizationErrorCode.INVALID_VALUE,
            source_location=source_location,
            field=field,
            expected_contract="non-empty bounded text without control characters",
            message="canonical ID input is invalid",
        )
    return value


def stable_canonical_id(
    namespace: object,
    source_system: object,
    source_value: object,
    *,
    source_location: str = "canonical-id",
) -> str:
    """Return a replay-stable, whitespace-free ID for one explicit authority."""

    namespace_text = _bounded_text(
        namespace,
        field="namespace",
        source_location=source_location,
        maximum=64,
    )
    if _NAMESPACE.fullmatch(namespace_text) is None:
        raise NormalizationError(
            NormalizationErrorCode.INVALID_MAPPING_PROFILE,
            source_location=source_location,
            field="id_namespace",
            expected_contract="[A-Za-z][A-Za-z0-9._-]{0,63}",
            message="ID namespace is invalid",
        )
    system_text = _bounded_text(
        source_system,
        field="source_system",
        source_location=source_location,
        maximum=256,
    )
    value_text = _bounded_text(
        source_value,
        field="source_value",
        source_location=source_location,
        maximum=512,
    )
    canonical = json.dumps(
        [namespace_text, system_text, value_text],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{namespace_text.lower()}-{sha256(canonical).hexdigest()}"


__all__ = ["stable_canonical_id"]
