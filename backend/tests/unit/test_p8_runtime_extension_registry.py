"""Focused deterministic Registry and startup rejection tests for P8-13."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

from pydantic import SecretStr, ValidationError
import pytest

from app.data_validation.canonical_ingress import canonical_fingerprint, canonical_json_bytes
from app.extensions.contracts import RuntimeExtensionArtifact, RuntimeExtensionError
from app.extensions.loader import load_runtime_extensions
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from backend.tests.fixtures.p8_synthetic_extension import DivergentRegistry
from backend.tests.p8_runtime_extension_support import (
    VERIFICATION_KEY,
    VERIFICATION_KEY_ID,
    runtime_extension_fixture,
    synthetic_artifact,
    synthetic_configuration_document,
    synthetic_manifest_document,
    write_runtime_extension_bundle,
)


def _fixture(tmp_path: Path, **kwargs):
    return runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'registry.db').as_posix()}",
        **kwargs,
    )


def _rewrite_catalog(path: Path, document: dict[str, object]) -> None:
    projection = dict(document)
    projection.pop("catalog_fingerprint")
    document["catalog_fingerprint"] = canonical_fingerprint(projection)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def test_repeated_startup_is_byte_deterministic(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    first = fixture.load()
    second = fixture.load()
    assert first.canonical_bytes == second.canonical_bytes
    assert first.extension_set_reference_bytes == second.extension_set_reference_bytes
    assert first.registry.resolution == second.registry.resolution


def test_signature_and_artifact_tamper_fail_before_registry_commit(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    tampered_catalog = deepcopy(fixture.catalog)
    entry = tampered_catalog["extensions"][0]
    entry["signature"] = f"hmac-sha256:{'0' * 64}"
    _rewrite_catalog(fixture.catalog_path, tampered_catalog)
    with pytest.raises(RuntimeExtensionError) as signature_error:
        fixture.load()
    assert signature_error.value.code == "EXTENSION_ARTIFACT_SIGNATURE_INVALID"

    _rewrite_catalog(fixture.catalog_path, deepcopy(fixture.catalog))
    tampered_artifact = replace(
        fixture.artifact,
        artifact_bytes=fixture.artifact.artifact_bytes + b"tamper",
    )
    with pytest.raises(RuntimeExtensionError) as digest_error:
        load_runtime_extensions(
            fixture.catalog_path,
            artifacts=(tampered_artifact,),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        )
    assert digest_error.value.code == "EXTENSION_ARTIFACT_INTEGRITY_FAILED"


def test_duplicate_provider_and_divergent_plugin_registry_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(RuntimeExtensionError) as duplicate:
        load_runtime_extensions(
            fixture.catalog_path,
            artifacts=(fixture.artifact, fixture.artifact),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        )
    assert duplicate.value.code == "EXTENSION_ARTIFACT_NOT_ALLOW_LISTED"

    divergent = _fixture(
        tmp_path / "divergent",
        overrides={"com.example.registry": DivergentRegistry},
    )
    with pytest.raises(RuntimeExtensionError) as mismatch:
        divergent.load()
    assert mismatch.value.code == "EXTENSION_REGISTRY_RESOLUTION_MISMATCH"


def test_incompatible_runtime_and_configuration_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    incompatible_manifest = synthetic_manifest_document()
    incompatible_manifest["compatibility"]["runtime"][
        "minimum_inclusive"
    ] = "0.2.0"
    incompatible_manifest["manifest_fingerprint"] = ""
    manifest_projection = dict(incompatible_manifest)
    manifest_projection.pop("manifest_fingerprint")
    incompatible_manifest["manifest_fingerprint"] = canonical_fingerprint(
        manifest_projection
    )
    incompatible_configuration = synthetic_configuration_document(
        incompatible_manifest
    )
    incompatible_catalog_path, _ = write_runtime_extension_bundle(
        tmp_path / "incompatible",
        manifest=incompatible_manifest,
        configuration=incompatible_configuration,
    )
    with pytest.raises(RuntimeExtensionError) as incompatible:
        load_runtime_extensions(
            incompatible_catalog_path,
            artifacts=(synthetic_artifact(incompatible_manifest),),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        )
    assert incompatible.value.code == "EXTENSION_RUNTIME_INCOMPATIBLE"

    configuration_fixture = _fixture(tmp_path / "configuration")
    configuration_path = configuration_fixture.catalog_path.parent / cast(
        str,
        configuration_fixture.catalog["extensions"][0]["configuration_path"],
    )
    tampered_configuration = deepcopy(configuration_fixture.configuration)
    tampered_configuration["values"] = {"capacity_mode": "TAMPERED"}
    configuration_path.write_bytes(
        canonical_json_bytes(tampered_configuration) + b"\n"
    )
    with pytest.raises(RuntimeExtensionError) as configuration:
        configuration_fixture.load()
    assert configuration.value.code == "EXTENSION_CONFIGURATION_INVALID"


def test_settings_require_atomic_secret_free_extension_configuration(
    tmp_path: Path,
) -> None:
    common = {
        "runtime_environment": RuntimeEnvironment.TEST,
        "data_plane": DataPlane.SIMULATION,
        "runtime_composition_enabled": True,
        "runtime_planning_policy_path": tmp_path / "policy.json",
        "runtime_solve_limits_path": tmp_path / "limits.json",
    }
    with pytest.raises(ValidationError):
        Settings(
            **common,
            runtime_extension_catalog_path=tmp_path / "catalog.json",
        )
    with pytest.raises(ValidationError):
        Settings(
            **common,
            runtime_extension_catalog_path=tmp_path / "catalog.json",
            runtime_extension_verification_key_id=VERIFICATION_KEY_ID,
            runtime_extension_verification_key=SecretStr("short"),
        )
    configured = Settings(
        **common,
        runtime_extension_catalog_path=tmp_path / "catalog.json",
        runtime_extension_verification_key_id=VERIFICATION_KEY_ID,
        runtime_extension_verification_key=SecretStr(VERIFICATION_KEY.decode()),
    )
    assert configured.safe_summary()["runtime_extension_catalog_configured"] is True
    assert "verification_key" not in str(configured.safe_summary())


def test_direct_loader_and_artifact_carriers_reject_malformed_runtime_values(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(RuntimeExtensionError) as key_error:
        load_runtime_extensions(
            fixture.catalog_path,
            artifacts=(fixture.artifact,),
            runtime_version="0.1.0",
            verification_key_id="unsafe key id",
            verification_key=VERIFICATION_KEY,
        )
    assert key_error.value.code == "EXTENSION_ARTIFACT_SIGNATURE_INVALID"

    with pytest.raises(RuntimeExtensionError) as artifact_error:
        RuntimeExtensionArtifact(
            extension_id=cast(str, 17),
            artifact_bytes=b"artifact",
            implementations=(),
        )
    assert artifact_error.value.code == "EXTENSION_ARTIFACT_NOT_ALLOW_LISTED"
