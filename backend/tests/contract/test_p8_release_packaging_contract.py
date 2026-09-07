"""Distribution-shape and immutable-manifest contracts for P8-09."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.infrastructure.release.builder import (
    build_license_report,
    load_release_policy,
    runtime_dependency_graph,
)
from app.infrastructure.release.contracts import (
    COMPATIBILITY_PATH,
    LICENSE_PATH,
    MIGRATION_PATH,
    SBOM_PATH,
    ReleaseContractError,
    strict_json_document,
    verify_release_archive,
)
from backend.tests.p8_release_support import ROOT, TEST_COMMIT, load_test_release_files


def test_release_manifest_binds_every_independent_version(tmp_path) -> None:
    artifact, files = load_test_release_files(tmp_path)
    verified = verify_release_archive(
        artifact.archive_path,
        expected_runtime_version="0.1.0",
        expected_code_commit=TEST_COMMIT,
    )
    assert verified.manifest["versions"] == {
        "runtime": "0.1.0",
        "application": "0.0.0",
        "core": "0.0.0",
        "api": "headless-http.v1",
        "schema": "2.10.0",
        "spec": "0.3.0",
        "database": "0009_host_authorization_audit",
        "extension_sdk": "0.0.0-not-published",
        "developer_kit": "0.0.0-not-published",
        "plugin_registry": "plugin-registry.v1",
    }
    assert verified.payload_file_count == 144
    assert files["runtime/openapi/headless-api.v1.json"]


def test_distribution_contains_required_machine_metadata(tmp_path) -> None:
    _, files = load_test_release_files(tmp_path)
    compatibility = strict_json_document(files[COMPATIBILITY_PATH])
    migration = strict_json_document(files[MIGRATION_PATH])
    licenses = strict_json_document(files[LICENSE_PATH])
    sbom = strict_json_document(files[SBOM_PATH])
    assert compatibility["automatic_upgrade"] is False
    assert migration["revision_count"] == 9
    assert licenses["component_count"] == 51
    assert licenses["issues"] == []
    assert len(sbom["components"]) == 51


def test_distribution_excludes_demo_frontend_connectors_and_extensions(tmp_path) -> None:
    _, files = load_test_release_files(tmp_path)
    forbidden = ("demo/", "frontend/", "third-party/", "enterprise-extension/")
    assert not [path for path in files if path.startswith(forbidden)]
    manifest = strict_json_document(files["metadata/release-manifest.json"])
    assert manifest["extension_boundary"] == {
        "bundled_extensions": [],
        "enterprise_extension_loading": "DISABLED_UNTIL_COMPATIBILITY_VERIFIED",
        "frontend_bundled": False,
        "third_party_connectors_bundled": False,
    }


def test_content_address_and_sidecar_bind_archive_bytes(tmp_path) -> None:
    artifact, _ = load_test_release_files(tmp_path)
    digest = artifact.archive_sha256.removeprefix("sha256:")
    assert artifact.archive_path.parent.name == digest
    assert artifact.checksum_path.read_text(encoding="utf-8") == (
        f"{digest}  {artifact.archive_path.name}\n"
    )


def test_unreviewed_or_unknown_license_fails_release() -> None:
    packages, _ = runtime_dependency_graph((ROOT / "uv.lock").read_bytes())
    policy = deepcopy(load_release_policy(ROOT))
    del policy["license_policy"]["reviewed_expressions"]["starlette"]
    with pytest.raises(ReleaseContractError, match="LICENSE_POLICY_FAILED"):
        build_license_report(packages, policy)
