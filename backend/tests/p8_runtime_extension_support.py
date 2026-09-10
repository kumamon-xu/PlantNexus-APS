"""Synthetic startup bundle for TEST-P8-PLUGIN-REGISTRY-001."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from pydantic import SecretStr

from aps_extension_sdk import (
    ContributionManifest,
    ExtensionPoint,
    fingerprint_json,
    parse_extension_manifest,
)

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.extensions.contracts import RuntimeExtensionArtifact
from app.extensions.loader import load_runtime_extensions, runtime_extension_signature
from app.extensions.registry import LoadedRuntimeExtensionAdapter
from app.infrastructure.config import Settings
from backend.tests.fixtures.p8_synthetic_extension import (
    SyntheticConstraint,
    SyntheticObjective,
    SyntheticPlanningRule,
    SyntheticRegistry,
    SyntheticReplanPolicy,
    SyntheticValidationRule,
)
from backend.tests.p8_runtime_support import runtime_settings


ROOT = Path(__file__).resolve().parents[2]
SDK_SAMPLES = ROOT / "backend/aps_extension_sdk/contracts/samples"
VERIFICATION_KEY_ID = "p8.runtime.extension.key.v1"
VERIFICATION_KEY = b"p8-13-synthetic-verification-key-material-v1"
ARTIFACT_BYTES = b"P8-13 deterministic synthetic Enterprise Extension artifact\n"
TEST_DEVELOPER_KIT_FINGERPRINT = "sha256:" + "d" * 64


type JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class RuntimeExtensionFixture:
    settings: Settings
    artifact: RuntimeExtensionArtifact
    catalog_path: Path
    catalog: JsonObject
    manifest: JsonObject
    configuration: JsonObject

    def load(self) -> LoadedRuntimeExtensionAdapter:
        return load_runtime_extensions(
            self.catalog_path,
            artifacts=(self.artifact,),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        )


def _sample(name: str) -> JsonObject:
    return cast(
        JsonObject,
        json.loads((SDK_SAMPLES / name).read_text(encoding="utf-8")),
    )


def synthetic_manifest_document(
    *,
    artifact_bytes: bytes = ARTIFACT_BYTES,
    extension_id: str = "com.example.manufacturing",
    extension_version: str = "1.0.0",
) -> JsonObject:
    document = deepcopy(_sample("extension-manifest.v1.synthetic.json"))
    document["extension_id"] = extension_id
    document["extension_version"] = extension_version
    artifact = cast(JsonObject, document["artifact"])
    artifact["digest"] = f"sha256:{sha256(artifact_bytes).hexdigest()}"
    document["manifest_fingerprint"] = ""
    projection = dict(document)
    projection.pop("manifest_fingerprint")
    document["manifest_fingerprint"] = fingerprint_json(projection)
    return document


def synthetic_configuration_document(
    manifest: JsonObject,
    *,
    values: Mapping[str, object] | None = None,
) -> JsonObject:
    configuration_manifest = cast(JsonObject, manifest["configuration"])
    document: JsonObject = {
        "configuration_contract_version": configuration_manifest["contract_version"],
        "extension_id": manifest["extension_id"],
        "values": dict(values or {"capacity_mode": "SYNTHETIC"}),
        "configuration_fingerprint": "",
    }
    projection = dict(document)
    projection.pop("configuration_fingerprint")
    document["configuration_fingerprint"] = canonical_fingerprint(projection)
    return document


def implementation_for(
    descriptor: ContributionManifest,
    *,
    overrides: Mapping[str, Callable[[ContributionManifest], object]] | None = None,
) -> object:
    override = (overrides or {}).get(descriptor.contribution_id)
    if override is not None:
        return override(descriptor)
    classes: dict[ExtensionPoint, Callable[[ContributionManifest], object]] = {
        ExtensionPoint.CONSTRAINT: SyntheticConstraint,
        ExtensionPoint.OBJECTIVE: SyntheticObjective,
        ExtensionPoint.PLANNING_RULE: SyntheticPlanningRule,
        ExtensionPoint.VALIDATION_RULE: SyntheticValidationRule,
        ExtensionPoint.REPLAN_POLICY: SyntheticReplanPolicy,
        ExtensionPoint.PLUGIN_REGISTRY: SyntheticRegistry,
    }
    return classes[descriptor.extension_point](descriptor)


def synthetic_artifact(
    manifest: JsonObject,
    *,
    artifact_bytes: bytes = ARTIFACT_BYTES,
    overrides: Mapping[str, Callable[[ContributionManifest], object]] | None = None,
) -> RuntimeExtensionArtifact:
    parsed = parse_extension_manifest(manifest)
    implementations = tuple(
        sorted(
            (
                descriptor.implementation,
                implementation_for(descriptor, overrides=overrides),
            )
            for descriptor in parsed.contributions
        )
    )
    return RuntimeExtensionArtifact(
        extension_id=parsed.extension_id,
        artifact_bytes=artifact_bytes,
        implementations=implementations,
    )


def write_runtime_extension_bundle(
    directory: Path,
    *,
    manifest: JsonObject,
    configuration: JsonObject,
    invocation_timeout_ms: int = 100,
    startup_timeout_ms: int = 5_000,
    verification_key_id: str = VERIFICATION_KEY_ID,
    verification_key: bytes = VERIFICATION_KEY,
    entry_mutator: Callable[[JsonObject], None] | None = None,
    catalog_mutator: Callable[[JsonObject], None] | None = None,
) -> tuple[Path, JsonObject]:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "extension-manifest.json"
    configuration_path = directory / "extension-configuration.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    configuration_path.write_bytes(canonical_json_bytes(configuration) + b"\n")
    contributions = cast(list[JsonObject], manifest["contributions"])
    capabilities = sorted(
        {
            cast(str, capability)
            for contribution in contributions
            for capability in cast(list[str], contribution["capabilities"])
        }
    )
    artifact = cast(JsonObject, manifest["artifact"])
    entry: JsonObject = {
        "extension_id": manifest["extension_id"],
        "extension_version": manifest["extension_version"],
        "manifest_path": manifest_path.name,
        "artifact_digest": artifact["digest"],
        "manifest_fingerprint": manifest["manifest_fingerprint"],
        "configuration_path": configuration_path.name,
        "configuration_fingerprint": configuration["configuration_fingerprint"],
        "allowed_capabilities": capabilities,
        "signature_key_id": verification_key_id,
        "signature": "",
    }
    if entry_mutator is not None:
        entry_mutator(entry)
    entry["signature"] = runtime_extension_signature(
        entry, verification_key=verification_key
    )
    catalog: JsonObject = {
        "catalog_version": "aps-runtime-extension-catalog.v1",
        "runtime_version": "0.1.0",
        "sdk_api_version": "1.0.0",
        "registry_protocol_version": "plugin-registry.v1",
        "compatibility": _sample("extension-compatibility.v1.synthetic.json"),
        "invocation_timeout_ms": invocation_timeout_ms,
        "startup_timeout_ms": startup_timeout_ms,
        "extensions": [entry],
        "catalog_fingerprint": "",
    }
    if catalog_mutator is not None:
        catalog_mutator(catalog)
    projection = dict(catalog)
    projection.pop("catalog_fingerprint")
    catalog["catalog_fingerprint"] = canonical_fingerprint(projection)
    catalog_path = directory / "runtime-extension-catalog.json"
    catalog_path.write_bytes(canonical_json_bytes(catalog) + b"\n")
    return catalog_path, catalog


def runtime_extension_fixture(
    tmp_path: Path,
    *,
    database_url: str,
    overrides: Mapping[str, Callable[[ContributionManifest], object]] | None = None,
    invocation_timeout_ms: int = 100,
    configuration_values: Mapping[str, object] | None = None,
) -> RuntimeExtensionFixture:
    manifest = synthetic_manifest_document()
    configuration = synthetic_configuration_document(
        manifest, values=configuration_values
    )
    catalog_path, catalog = write_runtime_extension_bundle(
        tmp_path / "runtime-extensions",
        manifest=manifest,
        configuration=configuration,
        invocation_timeout_ms=invocation_timeout_ms,
    )
    base = runtime_settings(tmp_path, database_url=database_url)
    settings = base.model_copy(
        update={
            "developer_kit_version": "1.0.0",
            "developer_kit_fingerprint": TEST_DEVELOPER_KIT_FINGERPRINT,
            "runtime_extension_catalog_path": catalog_path,
            "runtime_extension_verification_key_id": VERIFICATION_KEY_ID,
            "runtime_extension_verification_key": SecretStr(
                VERIFICATION_KEY.decode("utf-8")
            ),
        }
    )
    return RuntimeExtensionFixture(
        settings=settings,
        artifact=synthetic_artifact(manifest, overrides=overrides),
        catalog_path=catalog_path,
        catalog=catalog,
        manifest=manifest,
        configuration=configuration,
    )


__all__ = [
    "ARTIFACT_BYTES",
    "ROOT",
    "RuntimeExtensionFixture",
    "TEST_DEVELOPER_KIT_FINGERPRINT",
    "VERIFICATION_KEY",
    "VERIFICATION_KEY_ID",
    "implementation_for",
    "runtime_extension_fixture",
    "synthetic_artifact",
    "synthetic_configuration_document",
    "synthetic_manifest_document",
    "write_runtime_extension_bundle",
]
