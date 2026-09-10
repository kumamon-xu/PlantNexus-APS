"""Closed Runtime-side contracts for trusted APS Enterprise Extensions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import NoReturn, Protocol


RUNTIME_EXTENSION_CATALOG_VERSION = "aps-runtime-extension-catalog.v1"
RUNTIME_EXTENSION_ADAPTER_VERSION = "runtime-extension-adapter.v2"
RUNTIME_EXTENSION_INPUT_VIEW_VERSION = "runtime.extension.input.v1"
RUNTIME_EXTENSION_METRICS_VERSION = "runtime-extension-metrics.v2"
RUNTIME_EXTENSION_SIGNATURE_VERSION = "runtime-extension-signature.v1"

MAX_EXTENSION_CATALOG_BYTES = 1024 * 1024
MAX_EXTENSION_DOCUMENT_BYTES = 256 * 1024
MAX_EXTENSION_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_EXTENSION_ARTIFACTS = 16
MAX_EXTENSION_CONTRIBUTIONS = 256


class RuntimeExtensionErrorCode(StrEnum):
    """Stable internal failures mapped to the existing Runtime boundary."""

    CATALOG_INVALID = "EXTENSION_CATALOG_INVALID"
    CATALOG_INTEGRITY_FAILED = "EXTENSION_CATALOG_INTEGRITY_FAILED"
    ARTIFACT_NOT_ALLOW_LISTED = "EXTENSION_ARTIFACT_NOT_ALLOW_LISTED"
    ARTIFACT_INTEGRITY_FAILED = "EXTENSION_ARTIFACT_INTEGRITY_FAILED"
    ARTIFACT_SIGNATURE_INVALID = "EXTENSION_ARTIFACT_SIGNATURE_INVALID"
    CONFIGURATION_INVALID = "EXTENSION_CONFIGURATION_INVALID"
    INCOMPATIBLE_RUNTIME_VERSION = "EXTENSION_RUNTIME_INCOMPATIBLE"
    ENTRYPOINT_UNAVAILABLE = "EXTENSION_ENTRYPOINT_UNAVAILABLE"
    ENTRYPOINT_CONTRACT_MISMATCH = "EXTENSION_ENTRYPOINT_CONTRACT_MISMATCH"
    CAPABILITY_DENIED = "EXTENSION_CAPABILITY_DENIED"
    REGISTRY_RESOLUTION_FAILED = "EXTENSION_REGISTRY_RESOLUTION_FAILED"
    REGISTRY_RESOLUTION_MISMATCH = "EXTENSION_REGISTRY_RESOLUTION_MISMATCH"
    EXTENSION_TIMEOUT = "EXTENSION_TIMEOUT"
    EXTENSION_EXECUTION_FAILED = "EXTENSION_EXECUTION_FAILED"
    EXTENSION_OUTPUT_INVALID = "EXTENSION_OUTPUT_INVALID"
    EXTENSION_VALIDATION_FAILED = "EXTENSION_VALIDATION_FAILED"
    EXTENSION_REPLAN_REQUIRED = "EXTENSION_REPLAN_REQUIRED"
    EXTENSION_UNHEALTHY = "EXTENSION_UNHEALTHY"
    STARTUP_BUDGET_EXCEEDED = "EXTENSION_STARTUP_BUDGET_EXCEEDED"
    STARTUP_FAILED = "EXTENSION_STARTUP_FAILED"


class RuntimeExtensionError(RuntimeError):
    """Sanitized failure containing only stable IDs and operator-safe text."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.safe_message = message
        super().__init__(f"{code}: {field}: {message}")


def reject_extension(
    code: RuntimeExtensionErrorCode | str,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise RuntimeExtensionError(str(code), field=field, message=message)


@dataclass(frozen=True, slots=True)
class RuntimeExtensionLimits:
    """Catalog-fingerprinted engineering budgets for trusted in-process code."""

    invocation_timeout_ms: int
    startup_timeout_ms: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.invocation_timeout_ms, bool)
            or not isinstance(self.invocation_timeout_ms, int)
            or not 1 <= self.invocation_timeout_ms <= 30_000
        ):
            reject_extension(
                RuntimeExtensionErrorCode.CATALOG_INVALID,
                field="invocation_timeout_ms",
                message="invocation timeout must be an integer from 1 through 30000",
            )
        if (
            isinstance(self.startup_timeout_ms, bool)
            or not isinstance(self.startup_timeout_ms, int)
            or not 1 <= self.startup_timeout_ms <= 60_000
        ):
            reject_extension(
                RuntimeExtensionErrorCode.CATALOG_INVALID,
                field="startup_timeout_ms",
                message="startup timeout must be an integer from 1 through 60000",
            )


@dataclass(frozen=True, slots=True)
class RuntimeExtensionArtifact:
    """One build/deploy supplied local artifact and its explicit bindings.

    ``artifact_bytes`` are the exact content-addressed distribution bytes. The
    trusted deployment bootstrap owns the mapping from those bytes to the
    already materialized implementation objects; Runtime never scans global
    entry points, downloads packages, or imports a request-selected module.
    """

    extension_id: str
    artifact_bytes: bytes
    implementations: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.extension_id, str)
            or not self.extension_id
            or any(character.isspace() for character in self.extension_id)
        ):
            reject_extension(
                RuntimeExtensionErrorCode.ARTIFACT_NOT_ALLOW_LISTED,
                field="artifact.extension_id",
                message="artifact Extension identity is invalid",
            )
        if not isinstance(self.artifact_bytes, bytes) or not (
            1 <= len(self.artifact_bytes) <= MAX_EXTENSION_ARTIFACT_BYTES
        ):
            reject_extension(
                RuntimeExtensionErrorCode.ARTIFACT_INTEGRITY_FAILED,
                field="artifact.bytes",
                message="artifact bytes are absent or exceed the Runtime limit",
            )
        if (
            not isinstance(self.implementations, tuple)
            or len(self.implementations) > MAX_EXTENSION_CONTRIBUTIONS
        ):
            reject_extension(
                RuntimeExtensionErrorCode.ENTRYPOINT_UNAVAILABLE,
                field="artifact.implementations",
                message="implementation bindings must be a bounded tuple",
            )
        if any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not isinstance(item[0], str)
            for item in self.implementations
        ):
            reject_extension(
                RuntimeExtensionErrorCode.ENTRYPOINT_UNAVAILABLE,
                field="artifact.implementations",
                message="implementation bindings violate the Runtime contract",
            )
        names = tuple(name for name, _ in self.implementations)
        if (
            names != tuple(sorted(names))
            or len(names) != len(set(names))
            or any(
                not name or any(character.isspace() for character in name)
                for name in names
            )
        ):
            reject_extension(
                RuntimeExtensionErrorCode.ENTRYPOINT_UNAVAILABLE,
                field="artifact.implementations",
                message="implementation bindings must be unique and canonically ordered",
            )

    @classmethod
    def create(
        cls,
        *,
        extension_id: str,
        artifact_bytes: bytes,
        implementations: Mapping[str, object],
    ) -> RuntimeExtensionArtifact:
        if not isinstance(artifact_bytes, bytes):
            reject_extension(
                RuntimeExtensionErrorCode.ARTIFACT_INTEGRITY_FAILED,
                field="artifact.bytes",
                message="artifact bytes are absent or exceed the Runtime limit",
            )
        items = tuple(implementations.items())
        if any(not isinstance(name, str) for name, _ in items):
            reject_extension(
                RuntimeExtensionErrorCode.ENTRYPOINT_UNAVAILABLE,
                field="artifact.implementations",
                message="implementation bindings violate the Runtime contract",
            )
        return cls(
            extension_id=extension_id,
            artifact_bytes=artifact_bytes,
            implementations=tuple(sorted(items)),
        )

    @property
    def implementation_map(self) -> Mapping[str, object]:
        return MappingProxyType(dict(self.implementations))


class RuntimeExtensionAdapterPort(Protocol):
    """Small composition-root surface shared by empty and loaded adapters."""

    @property
    def document(self) -> dict[str, object]: ...

    @property
    def contributions(self) -> tuple[object, ...]: ...

    @property
    def extension_set_reference(self) -> dict[str, object]: ...

    @property
    def sdk_api_version(self) -> str: ...

    @property
    def registry_protocol_version(self) -> str: ...

    @property
    def readiness_probe(self) -> object | None: ...


__all__ = [
    "MAX_EXTENSION_ARTIFACTS",
    "MAX_EXTENSION_ARTIFACT_BYTES",
    "MAX_EXTENSION_CATALOG_BYTES",
    "MAX_EXTENSION_CONTRIBUTIONS",
    "MAX_EXTENSION_DOCUMENT_BYTES",
    "RUNTIME_EXTENSION_ADAPTER_VERSION",
    "RUNTIME_EXTENSION_CATALOG_VERSION",
    "RUNTIME_EXTENSION_INPUT_VIEW_VERSION",
    "RUNTIME_EXTENSION_METRICS_VERSION",
    "RUNTIME_EXTENSION_SIGNATURE_VERSION",
    "RuntimeExtensionAdapterPort",
    "RuntimeExtensionArtifact",
    "RuntimeExtensionError",
    "RuntimeExtensionErrorCode",
    "RuntimeExtensionLimits",
    "reject_extension",
]
