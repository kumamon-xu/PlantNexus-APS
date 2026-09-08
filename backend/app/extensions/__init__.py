"""APS Runtime Extension loader, Registry, and SPI adapter surface."""

from app.extensions.contracts import (
    RuntimeExtensionArtifact,
    RuntimeExtensionError,
    RuntimeExtensionErrorCode,
    RuntimeExtensionLimits,
)
from app.extensions.loader import load_runtime_extensions
from app.extensions.registry import LoadedRuntimeExtensionAdapter


__all__ = [
    "LoadedRuntimeExtensionAdapter",
    "RuntimeExtensionArtifact",
    "RuntimeExtensionError",
    "RuntimeExtensionErrorCode",
    "RuntimeExtensionLimits",
    "load_runtime_extensions",
]
