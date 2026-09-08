"""Immutable JSON views, identifiers, fingerprints, and strict SemVer values."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any

from aps_extension_sdk.errors import ExtensionErrorCode, fail


_SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_ENTRYPOINT_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$"
)
_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, order=True, slots=True)
class SemanticVersion:
    """A strict release-only SemVer value; aliases and floating ranges are absent."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: object, *, field: str = "version") -> SemanticVersion:
        if not isinstance(value, str):
            fail(
                ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
                field,
                "version must be a release-only MAJOR.MINOR.PATCH string",
            )
        match = _SEMVER_PATTERN.fullmatch(value)
        if match is None:
            fail(
                ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
                field,
                "version must be canonical MAJOR.MINOR.PATCH without aliases",
            )
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, slots=True)
class VersionInterval:
    """A bounded half-open compatibility interval."""

    minimum_inclusive: SemanticVersion
    maximum_exclusive: SemanticVersion

    def __post_init__(self) -> None:
        if self.maximum_exclusive <= self.minimum_inclusive:
            fail(
                ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
                "version_interval",
                "maximum_exclusive must be greater than minimum_inclusive",
            )

    def contains(self, version: SemanticVersion) -> bool:
        return self.minimum_inclusive <= version < self.maximum_exclusive


@dataclass(frozen=True, slots=True)
class FrozenJsonObject(Mapping[str, object]):
    """A recursively immutable, canonically ordered JSON object view."""

    _items: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        keys = tuple(key for key, _ in self._items)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                "$",
                "immutable object keys must be unique and canonically sorted",
            )
        for key, value in self._items:
            if not isinstance(key, str):
                fail(
                    ExtensionErrorCode.MUTABLE_VALUE,
                    "$",
                    "immutable object keys must be strings",
                )
            assert_immutable_json(value, field=f"$.{key}")

    def __getitem__(self, key: str) -> object:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def items_tuple(self) -> tuple[tuple[str, object], ...]:
        return self._items


def freeze_json(value: object, *, field: str = "$") -> object:
    """Copy JSON-compatible input into an immutable canonical representation."""

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                field,
                "non-finite numbers are not canonical JSON",
            )
        return value
    if isinstance(value, Mapping):
        pairs: list[tuple[str, object]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                fail(
                    ExtensionErrorCode.MUTABLE_VALUE,
                    field,
                    "JSON object keys must be strings",
                )
            pairs.append((key, freeze_json(item, field=f"{field}.{key}")))
        return FrozenJsonObject(tuple(sorted(pairs)))
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze_json(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        )
    fail(
        ExtensionErrorCode.MUTABLE_VALUE,
        field,
        "value must be copied from finite JSON-compatible data",
    )


def assert_immutable_json(value: object, *, field: str = "$") -> None:
    """Reject mutable containers and non-JSON extension return values."""

    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
    elif isinstance(value, FrozenJsonObject):
        for key, item in value.items_tuple():
            assert_immutable_json(item, field=f"{field}.{key}")
        return
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            assert_immutable_json(item, field=f"{field}[{index}]")
        return
    fail(
        ExtensionErrorCode.MUTABLE_VALUE,
        field,
        "extension values must be recursively immutable canonical JSON",
    )


def thaw_json(value: object) -> Any:
    """Return a fresh JSON-compatible copy for canonical serialization only."""

    assert_immutable_json(value)
    if isinstance(value, FrozenJsonObject):
        return {key: thaw_json(item) for key, item in value.items_tuple()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def canonical_json_bytes(value: object) -> bytes:
    frozen = freeze_json(value) if not isinstance(value, FrozenJsonObject) else value
    return json.dumps(
        thaw_json(frozen),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def fingerprint_json(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def require_identifier(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 256
        or _IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        fail(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "identifier must be a lowercase dotted, dashed, or underscored stable ID",
        )
    return value


def require_entrypoint(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 512
        or _ENTRYPOINT_PATTERN.fullmatch(value) is None
    ):
        fail(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "entrypoint must use the canonical package.module:Object form",
        )
    return value


def require_fingerprint(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT_PATTERN.fullmatch(value) is None:
        fail(
            ExtensionErrorCode.FINGERPRINT_MISMATCH,
            field,
            "fingerprint must be sha256 followed by 64 lowercase hexadecimal digits",
        )
    return value


def require_commit(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _COMMIT_PATTERN.fullmatch(value) is None:
        fail(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "source commit must be an exact 40-character lowercase Git SHA",
        )
    return value


def require_sorted_unique_text(
    value: object,
    *,
    field: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        fail(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "value must be an array of non-empty strings",
        )
    items = tuple(value)
    if (not allow_empty and not items) or items != tuple(sorted(items)) or len(
        items
    ) != len(set(items)):
        fail(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "values must be unique, canonically sorted, and satisfy cardinality",
        )
    return items


__all__ = [
    "FrozenJsonObject",
    "SemanticVersion",
    "VersionInterval",
    "assert_immutable_json",
    "canonical_json_bytes",
    "fingerprint_json",
    "freeze_json",
    "require_commit",
    "require_entrypoint",
    "require_fingerprint",
    "require_identifier",
    "require_sorted_unique_text",
    "thaw_json",
]
