"""Fail-closed startup loader for explicitly allow-listed local Extensions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import hmac
from pathlib import Path, PurePosixPath
import re
from time import monotonic
from typing import Any, cast

from aps_extension_sdk import (
    PROTOCOLS_BY_POINT,
    REGISTRY_PROTOCOL_VERSION,
    SDK_API_VERSION,
    ContributionManifest,
    ExtensionContractError,
    ExtensionManifest,
    ExtensionPoint,
    RegistryResolution,
    SemanticVersion,
    parse_compatibility_policy,
    parse_extension_manifest,
    resolve_manifest_set,
    validate_protocol_output,
)

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
    parse_strict_json,
)
from app.extensions.contracts import (
    MAX_EXTENSION_ARTIFACTS,
    MAX_EXTENSION_CATALOG_BYTES,
    MAX_EXTENSION_CONTRIBUTIONS,
    MAX_EXTENSION_DOCUMENT_BYTES,
    RUNTIME_EXTENSION_CATALOG_VERSION,
    RUNTIME_EXTENSION_SIGNATURE_VERSION,
    RuntimeExtensionArtifact,
    RuntimeExtensionError,
    RuntimeExtensionErrorCode,
    RuntimeExtensionLimits,
    reject_extension,
)
from app.extensions.registry import (
    LoadedRuntimeExtensionAdapter,
    RuntimeExtensionBinding,
    RuntimeExtensionMetrics,
    build_loaded_adapter,
    invoke_trusted_extension,
)


type JsonObject = dict[str, Any]

_CATALOG_KEYS = {
    "catalog_version",
    "runtime_version",
    "sdk_api_version",
    "registry_protocol_version",
    "compatibility",
    "invocation_timeout_ms",
    "startup_timeout_ms",
    "extensions",
    "catalog_fingerprint",
}
_ENTRY_KEYS = {
    "extension_id",
    "extension_version",
    "manifest_path",
    "artifact_digest",
    "manifest_fingerprint",
    "configuration_path",
    "configuration_fingerprint",
    "allowed_capabilities",
    "signature_key_id",
    "signature",
}
_CONFIGURATION_KEYS = {
    "configuration_contract_version",
    "extension_id",
    "values",
    "configuration_fingerprint",
}
_SAFE_KEY_ID_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+")


def _object(value: object, *, field: str) -> JsonObject:
    if not isinstance(value, dict):
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field=field,
            message="value must be a strict JSON object",
        )
    return cast(JsonObject, value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field=field,
            message="value must be bounded non-empty text",
        )
    return value


def _exact_keys(document: Mapping[str, object], expected: set[str], *, field: str) -> None:
    if set(document) != expected:
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field=field,
            message="object fields differ from the closed Runtime contract",
        )


def _relative_document(
    catalog_path: Path,
    value: object,
    *,
    field: str,
) -> JsonObject:
    raw = _text(value, field=field)
    relative = PurePosixPath(raw)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or relative.suffix != ".json"
        or relative.as_posix() != raw
    ):
        reject_extension(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
            field=field,
            message="document path must be a normalized relative JSON path",
        )
    base = catalog_path.parent.resolve(strict=True)
    candidate = catalog_path.parent.joinpath(*relative.parts)
    try:
        if candidate.is_symlink():
            raise OSError
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(base) or not resolved.is_file() or resolved.is_symlink():
            raise OSError
        size = resolved.stat().st_size
        if not 2 <= size <= MAX_EXTENSION_DOCUMENT_BYTES:
            raise OSError
        return parse_strict_json(resolved.read_bytes())
    except Exception as error:  # noqa: BLE001 - configured paths and bytes remain private
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID.value,
            field=field,
            message="configured Extension document could not be safely loaded",
        ) from error


def _load_catalog(path: Path) -> JsonObject:
    try:
        if path.is_symlink():
            raise OSError
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or resolved.is_symlink():
            raise OSError
        size = resolved.stat().st_size
        if not 2 <= size <= MAX_EXTENSION_CATALOG_BYTES:
            raise OSError
        document = parse_strict_json(resolved.read_bytes())
    except Exception as error:  # noqa: BLE001 - configured paths and bytes remain private
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.CATALOG_INVALID.value,
            field="runtime_extension_catalog_path",
            message="Runtime Extension catalog could not be safely loaded",
        ) from error
    _exact_keys(document, _CATALOG_KEYS, field="$catalog")
    provided = _text(document["catalog_fingerprint"], field="catalog_fingerprint")
    projection = dict(document)
    projection.pop("catalog_fingerprint")
    if canonical_fingerprint(projection) != provided:
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INTEGRITY_FAILED,
            field="catalog_fingerprint",
            message="catalog fingerprint does not match canonical content",
        )
    return document


def runtime_extension_signature(
    entry: Mapping[str, object],
    *,
    verification_key: bytes,
) -> str:
    """Return the v1 HMAC tag over identity/digest/capability fields only."""

    basis = {
        "signature_version": RUNTIME_EXTENSION_SIGNATURE_VERSION,
        "extension_id": entry["extension_id"],
        "extension_version": entry["extension_version"],
        "artifact_digest": entry["artifact_digest"],
        "manifest_fingerprint": entry["manifest_fingerprint"],
        "configuration_fingerprint": entry["configuration_fingerprint"],
        "allowed_capabilities": entry["allowed_capabilities"],
        "signature_key_id": entry["signature_key_id"],
    }
    digest = hmac.new(verification_key, canonical_json_bytes(basis), sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def _verify_signature(
    entry: Mapping[str, object],
    *,
    verification_key_id: str,
    verification_key: bytes,
) -> None:
    if entry.get("signature_key_id") != verification_key_id:
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_SIGNATURE_INVALID,
            field="signature_key_id",
            message="artifact signature key does not match Runtime configuration",
        )
    provided = entry.get("signature")
    expected = runtime_extension_signature(entry, verification_key=verification_key)
    if not isinstance(provided, str) or not hmac.compare_digest(provided, expected):
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_SIGNATURE_INVALID,
            field="signature",
            message="artifact signature verification failed",
        )


def _configuration(
    catalog_path: Path,
    entry: Mapping[str, object],
    manifest: ExtensionManifest,
) -> tuple[bytes, str]:
    document = _relative_document(
        catalog_path,
        entry["configuration_path"],
        field="extensions.configuration_path",
    )
    _exact_keys(document, _CONFIGURATION_KEYS, field="$configuration")
    if (
        document.get("extension_id") != manifest.extension_id
        or document.get("configuration_contract_version")
        != manifest.configuration_contract
        or not isinstance(document.get("values"), dict)
    ):
        reject_extension(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
            field="extension_configuration",
            message="Extension configuration identity or contract is invalid",
        )
    provided = _text(
        document["configuration_fingerprint"], field="configuration_fingerprint"
    )
    projection = dict(document)
    projection.pop("configuration_fingerprint")
    if (
        canonical_fingerprint(projection) != provided
        or provided != entry.get("configuration_fingerprint")
    ):
        reject_extension(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
            field="configuration_fingerprint",
            message="Extension configuration fingerprint is invalid",
        )
    return canonical_json_bytes(document), provided


def _manifest(
    catalog_path: Path,
    entry: Mapping[str, object],
) -> ExtensionManifest:
    document = _relative_document(
        catalog_path,
        entry["manifest_path"],
        field="extensions.manifest_path",
    )
    try:
        manifest = parse_extension_manifest(document)
    except ExtensionContractError as error:
        raise RuntimeExtensionError(
            error.code.value,
            field=error.field,
            message="Extension manifest violated the SDK contract",
        ) from error
    if (
        manifest.extension_id != entry.get("extension_id")
        or str(manifest.extension_version) != entry.get("extension_version")
        or manifest.artifact_digest != entry.get("artifact_digest")
        or manifest.manifest_fingerprint != entry.get("manifest_fingerprint")
    ):
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_NOT_ALLOW_LISTED,
            field="extensions",
            message="manifest identity differs from the exact artifact allow-list",
        )
    return manifest


def _artifact_map(
    artifacts: Sequence[RuntimeExtensionArtifact],
) -> dict[str, RuntimeExtensionArtifact]:
    if len(artifacts) > MAX_EXTENSION_ARTIFACTS:
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field="artifacts",
            message="artifact count exceeds the Runtime limit",
        )
    result: dict[str, RuntimeExtensionArtifact] = {}
    for artifact in artifacts:
        if not isinstance(artifact, RuntimeExtensionArtifact):
            reject_extension(
                RuntimeExtensionErrorCode.ARTIFACT_NOT_ALLOW_LISTED,
                field="artifacts",
                message="artifact provider violated the Runtime contract",
            )
        if artifact.extension_id in result:
            reject_extension(
                RuntimeExtensionErrorCode.ARTIFACT_NOT_ALLOW_LISTED,
                field="artifacts.extension_id",
                message="artifact provider returned a duplicate Extension identity",
            )
        result[artifact.extension_id] = artifact
    return result


def _binding_for(
    manifest: ExtensionManifest,
    *,
    artifact: RuntimeExtensionArtifact,
    configuration_bytes: bytes,
    configuration_fingerprint: str,
    signature_key_id: str,
    limits: RuntimeExtensionLimits,
    metrics: RuntimeExtensionMetrics,
) -> tuple[RuntimeExtensionBinding, ...]:
    digest = f"sha256:{sha256(artifact.artifact_bytes).hexdigest()}"
    if digest != manifest.artifact_digest:
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_INTEGRITY_FAILED,
            field=manifest.extension_id,
            message="local artifact bytes differ from the allow-listed digest",
        )
    expected_names = tuple(sorted(item.implementation for item in manifest.contributions))
    observed_names = tuple(name for name, _ in artifact.implementations)
    if observed_names != expected_names:
        reject_extension(
            RuntimeExtensionErrorCode.ENTRYPOINT_UNAVAILABLE,
            field=manifest.extension_id,
            message="local artifact entrypoints differ from the manifest",
        )
    implementations = dict(artifact.implementations)
    bindings: list[RuntimeExtensionBinding] = []
    for descriptor in manifest.contributions:
        implementation = implementations[descriptor.implementation]
        binding = RuntimeExtensionBinding(
            extension_id=manifest.extension_id,
            extension_version=str(manifest.extension_version),
            artifact_digest=manifest.artifact_digest,
            manifest_fingerprint=manifest.manifest_fingerprint,
            configuration_fingerprint=configuration_fingerprint,
            signature_key_id=signature_key_id,
            descriptor=descriptor,
            configuration_bytes=configuration_bytes,
            implementation=implementation,
        )
        protocol = PROTOCOLS_BY_POINT[descriptor.extension_point]
        try:
            protocol_matches = isinstance(implementation, protocol)
        except Exception:  # noqa: BLE001 - implementation introspection is untrusted
            protocol_matches = False
        if not protocol_matches:
            reject_extension(
                RuntimeExtensionErrorCode.ENTRYPOINT_CONTRACT_MISMATCH,
                field=descriptor.contribution_id,
                message="implementation does not satisfy its declared SDK Protocol",
            )
        actual_descriptor = invoke_trusted_extension(
            binding,
            lambda implementation=implementation: getattr(implementation, "descriptor"),
            timeout_ms=limits.invocation_timeout_ms,
            metrics=metrics,
        )
        if not isinstance(actual_descriptor, ContributionManifest) or (
            actual_descriptor != descriptor
        ):
            reject_extension(
                RuntimeExtensionErrorCode.ENTRYPOINT_CONTRACT_MISMATCH,
                field=descriptor.contribution_id,
                message="implementation descriptor differs from the manifest",
            )
        bindings.append(binding)
    return tuple(bindings)


def _check_startup_budget(started: float, limits: RuntimeExtensionLimits) -> None:
    if (monotonic() - started) * 1_000 > limits.startup_timeout_ms:
        reject_extension(
            RuntimeExtensionErrorCode.STARTUP_BUDGET_EXCEEDED,
            field="extension_registry",
            message="Extension startup exceeded its configured budget",
        )


def load_runtime_extensions(
    catalog_path: Path,
    *,
    artifacts: Sequence[RuntimeExtensionArtifact],
    runtime_version: str,
    verification_key_id: str,
    verification_key: bytes,
) -> LoadedRuntimeExtensionAdapter:
    """Resolve and atomically commit one trusted local Extension set."""

    started = monotonic()
    if not isinstance(verification_key, bytes) or not 32 <= len(
        verification_key
    ) <= 4096:
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_SIGNATURE_INVALID,
            field="runtime_extension_verification_key",
            message="Runtime Extension verification key length is invalid",
        )
    if (
        not isinstance(verification_key_id, str)
        or len(verification_key_id) > 256
        or _SAFE_KEY_ID_PATTERN.fullmatch(verification_key_id) is None
    ):
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_SIGNATURE_INVALID,
            field="runtime_extension_verification_key_id",
            message="Runtime Extension verification key identity is invalid",
        )
    catalog = _load_catalog(catalog_path)
    if (
        catalog.get("catalog_version") != RUNTIME_EXTENSION_CATALOG_VERSION
        or catalog.get("runtime_version") != runtime_version
        or catalog.get("sdk_api_version") != SDK_API_VERSION
        or catalog.get("registry_protocol_version") != REGISTRY_PROTOCOL_VERSION
    ):
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field="$catalog",
            message="catalog versions differ from this Runtime and SDK",
        )
    limits = RuntimeExtensionLimits(
        invocation_timeout_ms=cast(int, catalog["invocation_timeout_ms"]),
        startup_timeout_ms=cast(int, catalog["startup_timeout_ms"]),
    )
    raw_entries = catalog.get("extensions")
    if not isinstance(raw_entries, list) or not 1 <= len(raw_entries) <= MAX_EXTENSION_ARTIFACTS:
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field="extensions",
            message="loaded catalog must contain a bounded non-empty Extension list",
        )
    entries = tuple(_object(value, field="extensions") for value in raw_entries)
    for entry in entries:
        _exact_keys(entry, _ENTRY_KEYS, field="extensions")
    extension_ids = tuple(_text(entry["extension_id"], field="extension_id") for entry in entries)
    if extension_ids != tuple(sorted(extension_ids)) or len(extension_ids) != len(set(extension_ids)):
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field="extensions.extension_id",
            message="Extension allow-list must be unique and canonically sorted",
        )
    try:
        policy = parse_compatibility_policy(
            _object(catalog["compatibility"], field="compatibility")
        )
    except ExtensionContractError as error:
        raise RuntimeExtensionError(
            error.code.value,
            field=error.field,
            message="Runtime compatibility policy violated the SDK contract",
        ) from error
    artifact_by_id = _artifact_map(artifacts)
    if set(artifact_by_id) != set(extension_ids):
        reject_extension(
            RuntimeExtensionErrorCode.ARTIFACT_NOT_ALLOW_LISTED,
            field="artifacts",
            message="local artifact set differs from the catalog allow-list",
        )

    manifests: list[ExtensionManifest] = []
    configuration_by_id: dict[str, tuple[bytes, str]] = {}
    for entry in entries:
        _verify_signature(
            entry,
            verification_key_id=verification_key_id,
            verification_key=verification_key,
        )
        manifest = _manifest(catalog_path, entry)
        try:
            runtime = SemanticVersion.parse(runtime_version, field="runtime_version")
        except ExtensionContractError as error:
            raise RuntimeExtensionError(
                RuntimeExtensionErrorCode.INCOMPATIBLE_RUNTIME_VERSION.value,
                field="runtime_version",
                message="Runtime version is not a canonical release version",
            ) from error
        if not manifest.runtime_compatibility.contains(runtime):
            reject_extension(
                RuntimeExtensionErrorCode.INCOMPATIBLE_RUNTIME_VERSION,
                field=manifest.extension_id,
                message="Extension artifact excludes this Runtime version",
            )
        capabilities = tuple(
            sorted(
                {
                    capability
                    for contribution in manifest.contributions
                    for capability in contribution.capabilities
                }
            )
        )
        allowed = entry.get("allowed_capabilities")
        if not isinstance(allowed, list) or tuple(allowed) != capabilities:
            reject_extension(
                RuntimeExtensionErrorCode.CAPABILITY_DENIED,
                field=manifest.extension_id,
                message="manifest capabilities differ from the exact Runtime allow-list",
            )
        configuration_by_id[manifest.extension_id] = _configuration(
            catalog_path, entry, manifest
        )
        manifests.append(manifest)
        _check_startup_budget(started, limits)
    try:
        resolution = resolve_manifest_set(tuple(manifests), policy)
    except ExtensionContractError as error:
        raise RuntimeExtensionError(
            error.code.value,
            field=error.field,
            message="Extension set could not be deterministically resolved",
        ) from error
    if len(resolution.contributions) > MAX_EXTENSION_CONTRIBUTIONS:
        reject_extension(
            RuntimeExtensionErrorCode.CATALOG_INVALID,
            field="extensions.contributions",
            message="resolved contribution count exceeds the Runtime limit",
        )

    provisional_metrics = RuntimeExtensionMetrics(resolution.resolution_fingerprint)
    bindings_by_id: dict[str, RuntimeExtensionBinding] = {}
    entry_by_id = {cast(str, entry["extension_id"]): entry for entry in entries}
    for manifest in manifests:
        configuration_bytes, configuration_fingerprint = configuration_by_id[
            manifest.extension_id
        ]
        entry = entry_by_id[manifest.extension_id]
        for binding in _binding_for(
            manifest,
            artifact=artifact_by_id[manifest.extension_id],
            configuration_bytes=configuration_bytes,
            configuration_fingerprint=configuration_fingerprint,
            signature_key_id=verification_key_id,
            limits=limits,
            metrics=provisional_metrics,
        ):
            bindings_by_id[binding.descriptor.contribution_id] = binding
        _check_startup_budget(started, limits)
    bindings = tuple(
        bindings_by_id[item.contribution_id] for item in resolution.contributions
    )

    registry_bindings = tuple(
        binding
        for binding in bindings
        if binding.descriptor.extension_point is ExtensionPoint.PLUGIN_REGISTRY
    )
    if registry_bindings:
        registry_binding = registry_bindings[0]
        resolved_by_extension = invoke_trusted_extension(
            registry_binding,
            lambda: cast(Any, getattr(registry_binding.implementation, "resolve"))(
                tuple(manifests), policy
            ),
            timeout_ms=limits.invocation_timeout_ms,
            metrics=provisional_metrics,
            validate=lambda output: validate_protocol_output(
                registry_binding.descriptor, (tuple(manifests), policy), output
            ),
        )
        if not isinstance(resolved_by_extension, RegistryResolution) or (
            resolved_by_extension != resolution
        ):
            reject_extension(
                RuntimeExtensionErrorCode.REGISTRY_RESOLUTION_MISMATCH,
                field=registry_binding.descriptor.contribution_id,
                message="Extension Registry resolution differs from Runtime authority",
            )
    _check_startup_budget(started, limits)
    return build_loaded_adapter(
        catalog_fingerprint=cast(str, catalog["catalog_fingerprint"]),
        policy=policy,
        manifests=tuple(manifests),
        resolution=resolution,
        bindings=bindings,
        limits=limits,
        signature_key_id=verification_key_id,
    )


__all__ = ["load_runtime_extensions", "runtime_extension_signature"]
