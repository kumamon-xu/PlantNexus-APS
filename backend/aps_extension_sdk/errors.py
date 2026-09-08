"""Stable, dependency-free error surface for APS Extension SDK v1."""

from __future__ import annotations

from enum import StrEnum
from typing import NoReturn


ERROR_REGISTRY_VERSION = "extension-error-code-registry.v1"
ERROR_NAMESPACE = "APS_EXTENSION_SDK"


class ExtensionErrorCode(StrEnum):
    """Fail-closed codes shared by the SDK carrier and conformance tools."""

    INVALID_MANIFEST = "INVALID_MANIFEST"
    UNKNOWN_EXTENSION_POINT = "UNKNOWN_EXTENSION_POINT"
    DUPLICATE_EXTENSION_ID = "DUPLICATE_EXTENSION_ID"
    DUPLICATE_CONTRIBUTION_ID = "DUPLICATE_CONTRIBUTION_ID"
    MISSING_VALIDATION_PAIR = "MISSING_VALIDATION_PAIR"
    INVALID_VALIDATION_PAIR = "INVALID_VALIDATION_PAIR"
    INVALID_OBJECTIVE_STAGE = "INVALID_OBJECTIVE_STAGE"
    MUTABLE_VALUE = "MUTABLE_VALUE"
    INCOMPATIBLE_SDK_VERSION = "INCOMPATIBLE_SDK_VERSION"
    MIXED_SDK_VERSION = "MIXED_SDK_VERSION"
    UNSUPPORTED_MANIFEST_VERSION = "UNSUPPORTED_MANIFEST_VERSION"
    UNSUPPORTED_REGISTRY_PROTOCOL = "UNSUPPORTED_REGISTRY_PROTOCOL"
    REGISTRY_CONFLICT = "REGISTRY_CONFLICT"
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
    FORBIDDEN_BOUNDARY_ACCESS = "FORBIDDEN_BOUNDARY_ACCESS"
    DEPRECATED_UNSUPPORTED = "DEPRECATED_UNSUPPORTED"


class ExtensionContractError(ValueError):
    """Deterministic rejection carrying no payload, stack, or secret details."""

    namespace = ERROR_NAMESPACE

    def __init__(
        self,
        code: ExtensionErrorCode,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.safe_message = message
        super().__init__(f"{self.namespace}/{code.value} at {field}: {message}")


def fail(code: ExtensionErrorCode, field: str, message: str) -> NoReturn:
    """Raise the sole public SDK contract exception."""

    raise ExtensionContractError(code, field=field, message=message)


__all__ = [
    "ERROR_NAMESPACE",
    "ERROR_REGISTRY_VERSION",
    "ExtensionContractError",
    "ExtensionErrorCode",
]
