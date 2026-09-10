"""P8 non-Production target bootstrap for the verified Alpha Extension.

This target-owned module is imported only through the explicit Runtime startup
provider setting.  It materializes the exact deterministic Alpha wheel bytes,
binds the two fixed entrypoints, and writes an ephemeral signed catalog beside
the configured /tmp catalog path.  It performs no discovery or network access.
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from importlib import import_module
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from aps_extension_sdk import (
    canonical_json_bytes,
    fingerprint_json,
    parse_extension_manifest,
)
from app.extensions.bootstrap import RuntimeExtensionBootstrapContext
from app.extensions.contracts import RuntimeExtensionArtifact
from app.extensions.loader import runtime_extension_signature


_WORKSPACE = Path("/workspace")
_PROJECT = _WORKSPACE / "extension-alpha"
_CATALOG_PATH = Path("/tmp/plantnexus/runtime-extension-catalog.json")
_KIT_VERSION = "1.0.0"
_KIT_FINGERPRINT = (
    "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361"
)
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _record_digest(value: bytes) -> str:
    encoded = urlsafe_b64encode(sha256(value).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def _deterministic_zip(files: dict[str, bytes]) -> bytes:
    target = BytesIO()
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in sorted(files.items()):
            info = ZipInfo(name, date_time=_ZIP_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, value)
    return target.getvalue()


def _alpha_wheel() -> bytes:
    source_root = _PROJECT / "src"
    package_root = source_root / "example_alpha_extension"
    files = {
        path.relative_to(source_root).as_posix(): path.read_bytes().replace(
            b"\r\n", b"\n"
        )
        for path in sorted(package_root.rglob("*.py"))
    }
    metadata = (
        "Metadata-Version: 2.3\n"
        "Name: example-alpha-aps-extension\n"
        "Version: 1.0.0\n"
        "Author: PlantNexus Synthetic Reference Alpha\n"
        "License: LicenseRef-PlantNexus-Synthetic-Reference\n"
        "Project-URL: Repository, https://example.invalid/plantnexus/alpha-aps-extension\n"
        "Requires-Python: >=3.12,<3.13\n"
        "Requires-Dist: aps-extension-sdk (==1.0.0)\n"
    )
    normalized = re.sub(r"[-_.]+", "_", "example-alpha-aps-extension")
    dist_info = f"{normalized}-1.0.0.dist-info"
    files[f"{dist_info}/METADATA"] = metadata.encode("utf-8")
    files[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: plantnexus-aps-extension-tooling-p8-14\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    record_name = f"{dist_info}/RECORD"
    record_lines = [
        f"{name},{_record_digest(value)},{len(value)}"
        for name, value in sorted(files.items())
    ]
    record_lines.append(f"{record_name},,")
    files[record_name] = ("\n".join(record_lines) + "\n").encode("utf-8")
    return _deterministic_zip(files)


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("target Extension document must be an object")
    return value


def _write_document(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_json_bytes(value) + b"\n")
    temporary.replace(path)


def provide_extension_artifacts(
    context: RuntimeExtensionBootstrapContext,
) -> tuple[RuntimeExtensionArtifact, ...]:
    """Materialize the one frozen non-Production Extension startup set."""

    if (
        context.runtime_version != "0.1.0"
        or context.developer_kit_version != _KIT_VERSION
        or context.developer_kit_fingerprint != _KIT_FINGERPRINT
        or context.catalog_path != _CATALOG_PATH
    ):
        raise ValueError("target Runtime, Kit, or catalog identity is not exact")

    manifest = _read_object(_PROJECT / "extension/extension-manifest.json")
    configuration = _read_object(_PROJECT / "extension/extension-configuration.json")
    compatibility = _read_object(
        _WORKSPACE
        / "backend/aps_extension_sdk/contracts/samples/extension-compatibility.v1.synthetic.json"
    )
    artifact_bytes = _alpha_wheel()
    artifact_digest = f"sha256:{sha256(artifact_bytes).hexdigest()}"
    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("digest") != artifact_digest:
        raise ValueError("target Extension artifact digest does not match its manifest")

    parsed = parse_extension_manifest(manifest)
    constraint_module = import_module("example_alpha_extension.constraint")
    validation_module = import_module("example_alpha_extension.validation")
    implementation_classes = {
        "example_alpha_extension.constraint:AlphaResourceTagConstraint": getattr(
            constraint_module, "AlphaResourceTagConstraint"
        ),
        "example_alpha_extension.validation:AlphaResourceTagValidator": getattr(
            validation_module, "AlphaResourceTagValidator"
        ),
    }
    implementations = {
        descriptor.implementation: implementation_classes[descriptor.implementation](
            descriptor
        )
        for descriptor in parsed.contributions
    }
    runtime_artifact = RuntimeExtensionArtifact.create(
        extension_id=parsed.extension_id,
        artifact_bytes=artifact_bytes,
        implementations=implementations,
    )

    output_directory = context.catalog_path.parent
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / "extension-manifest.json"
    configuration_path = output_directory / "extension-configuration.json"
    _write_document(manifest_path, manifest)
    _write_document(configuration_path, configuration)
    contributions = manifest.get("contributions")
    if not isinstance(contributions, list):
        raise ValueError("target Extension contributions are unavailable")
    capabilities = sorted(
        {
            capability
            for contribution in contributions
            if isinstance(contribution, dict)
            for capability in contribution.get("capabilities", [])
            if isinstance(capability, str)
        }
    )
    configuration_fingerprint = configuration.get("configuration_fingerprint")
    manifest_fingerprint = manifest.get("manifest_fingerprint")
    if not isinstance(configuration_fingerprint, str) or not isinstance(
        manifest_fingerprint, str
    ):
        raise ValueError("target Extension fingerprints are unavailable")
    entry: dict[str, object] = {
        "extension_id": parsed.extension_id,
        "extension_version": str(parsed.extension_version),
        "manifest_path": manifest_path.name,
        "artifact_digest": artifact_digest,
        "manifest_fingerprint": manifest_fingerprint,
        "configuration_path": configuration_path.name,
        "configuration_fingerprint": configuration_fingerprint,
        "allowed_capabilities": capabilities,
        "signature_key_id": context.verification_key_id,
        "signature": "",
    }
    entry["signature"] = runtime_extension_signature(
        entry, verification_key=context.verification_key
    )
    catalog: dict[str, object] = {
        "catalog_version": "aps-runtime-extension-catalog.v1",
        "runtime_version": context.runtime_version,
        "sdk_api_version": "1.0.0",
        "registry_protocol_version": "plugin-registry.v1",
        "compatibility": compatibility,
        "invocation_timeout_ms": 1_000,
        "startup_timeout_ms": 30_000,
        "extensions": [entry],
        "catalog_fingerprint": "",
    }
    projection = dict(catalog)
    projection.pop("catalog_fingerprint")
    catalog["catalog_fingerprint"] = fingerprint_json(projection)
    _write_document(context.catalog_path, catalog)
    return (runtime_artifact,)


__all__ = ["provide_extension_artifacts"]
