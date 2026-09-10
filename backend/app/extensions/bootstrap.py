"""Explicit build/deploy/startup-only Enterprise Extension artifact provider."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Callable, cast

from app import RUNTIME_VERSION
from app.extensions.contracts import (
    MAX_EXTENSION_ARTIFACTS,
    RuntimeExtensionArtifact,
    RuntimeExtensionError,
    RuntimeExtensionErrorCode,
    reject_extension,
)
from app.infrastructure.config import Settings


RUNTIME_EXTENSION_BOOTSTRAP_VERSION = "runtime-extension-bootstrap.v1"
RUNTIME_EXTENSION_BOOTSTRAP_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class RuntimeExtensionBootstrapContext:
    """Minimum explicit context granted to a trusted deployment provider."""

    bootstrap_version: str
    runtime_version: str
    catalog_path: Path
    verification_key_id: str
    verification_key: bytes
    developer_kit_version: str
    developer_kit_fingerprint: str


RuntimeExtensionArtifactProvider = Callable[
    [RuntimeExtensionBootstrapContext], tuple[RuntimeExtensionArtifact, ...]
]


def _context(settings: Settings) -> RuntimeExtensionBootstrapContext:
    catalog = settings.runtime_extension_catalog_path
    key_id = settings.runtime_extension_verification_key_id
    key = settings.runtime_extension_verification_key
    kit_version = settings.developer_kit_version
    kit_fingerprint = settings.developer_kit_fingerprint
    if (
        catalog is None
        or key_id is None
        or key is None
        or kit_version is None
        or kit_fingerprint is None
    ):
        reject_extension(
            RuntimeExtensionErrorCode.STARTUP_FAILED,
            field="runtime_extension_artifact_provider",
            message="Extension bootstrap configuration is incomplete",
        )
    return RuntimeExtensionBootstrapContext(
        bootstrap_version=RUNTIME_EXTENSION_BOOTSTRAP_VERSION,
        runtime_version=RUNTIME_VERSION,
        catalog_path=cast(Path, catalog),
        verification_key_id=cast(str, key_id),
        verification_key=key.get_secret_value().encode("utf-8"),
        developer_kit_version=cast(str, kit_version),
        developer_kit_fingerprint=cast(str, kit_fingerprint),
    )


def _provider_result(
    provider_reference: str,
    context: RuntimeExtensionBootstrapContext,
) -> tuple[RuntimeExtensionArtifact, ...]:
    module_name, callable_name = provider_reference.split(":", 1)
    module = import_module(module_name)
    provider = getattr(module, callable_name)
    if not callable(provider):
        raise TypeError("configured Extension artifact provider is not callable")
    value = cast(RuntimeExtensionArtifactProvider, provider)(context)
    if (
        not isinstance(value, tuple)
        or not 1 <= len(value) <= MAX_EXTENSION_ARTIFACTS
        or any(not isinstance(item, RuntimeExtensionArtifact) for item in value)
    ):
        raise TypeError("configured Extension artifact provider returned invalid data")
    extension_ids = tuple(item.extension_id for item in value)
    if extension_ids != tuple(sorted(extension_ids)) or len(extension_ids) != len(
        set(extension_ids)
    ):
        raise TypeError("configured Extension artifact set is not canonical")
    return value


def materialize_runtime_extension_artifacts(
    settings: Settings,
    *,
    explicit_artifacts: tuple[RuntimeExtensionArtifact, ...] | None,
) -> tuple[RuntimeExtensionArtifact, ...]:
    """Resolve exactly one explicit artifact source before Runtime composition."""

    provider_reference = settings.runtime_extension_artifact_provider
    if explicit_artifacts is not None:
        if provider_reference is not None:
            reject_extension(
                RuntimeExtensionErrorCode.STARTUP_FAILED,
                field="runtime_extension_artifact_provider",
                message="Extension artifact sources are ambiguous",
            )
        return explicit_artifacts
    if provider_reference is None:
        return ()

    result_queue: Queue[tuple[bool, object]] = Queue(maxsize=1)
    context = _context(settings)

    def invoke() -> None:
        try:
            result_queue.put((True, _provider_result(provider_reference, context)))
        except Exception as error:  # noqa: BLE001 - provider details remain private
            result_queue.put((False, error))

    thread = Thread(
        target=invoke,
        name="aps-extension-bootstrap",
        daemon=True,
    )
    thread.start()
    thread.join(RUNTIME_EXTENSION_BOOTSTRAP_TIMEOUT_SECONDS)
    if thread.is_alive():
        reject_extension(
            RuntimeExtensionErrorCode.STARTUP_BUDGET_EXCEEDED,
            field="runtime_extension_artifact_provider",
            message="Extension artifact provider exceeded its startup budget",
        )
    try:
        succeeded, value = result_queue.get_nowait()
    except Empty:
        succeeded, value = False, None
    if not succeeded:
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.STARTUP_FAILED.value,
            field="runtime_extension_artifact_provider",
            message="Extension artifact provider failed",
        ) from (value if isinstance(value, Exception) else None)
    return cast(tuple[RuntimeExtensionArtifact, ...], value)


__all__ = [
    "RUNTIME_EXTENSION_BOOTSTRAP_TIMEOUT_SECONDS",
    "RUNTIME_EXTENSION_BOOTSTRAP_VERSION",
    "RuntimeExtensionArtifactProvider",
    "RuntimeExtensionBootstrapContext",
    "materialize_runtime_extension_artifacts",
]
