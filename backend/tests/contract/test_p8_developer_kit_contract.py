"""Release-manifest and compatibility contracts for TASK-P8-15."""

from __future__ import annotations

from typing import cast

from aps_developer_kit.builder import KIT_VERSION
from aps_developer_kit.contracts import (
    COMPATIBILITY_MATRIX_VERSION,
    KIT_LOCK_VERSION,
    KIT_MANIFEST_VERSION,
    strict_json_document,
    verify_kit_archive,
)
from backend.tests.p8_developer_kit_support import TEST_COMMIT, load_test_kit_files


def test_kit_binds_all_independent_versions_and_runtime_lineage(tmp_path) -> None:
    artifact, _, files = load_test_kit_files(tmp_path)
    verified = verify_kit_archive(
        artifact.archive_path,
        expected_kit_version=KIT_VERSION,
        expected_code_commit=TEST_COMMIT,
    )
    manifest = verified.manifest
    assert manifest["manifest_version"] == KIT_MANIFEST_VERSION
    assert manifest["versions"] == {
        "developer_kit": "1.0.0",
        "runtime": "0.1.0",
        "application": "0.0.0",
        "core": "0.0.0",
        "extension_sdk": "1.0.0",
        "extension_tooling": "1.0.0",
        "enterprise_template": "1.0.0",
        "headless_api": "headless-http.v1",
        "schema_set": "2.10.0",
        "database": "0009_host_authorization_audit",
        "plugin_registry": "plugin-registry.v1",
        "spec": "0.3.0",
        "python": "3.12",
    }
    assert verified.runtime_release_fingerprint.startswith("sha256:")
    assert not any(path.startswith("demo/") for path in files)


def test_compatibility_lock_support_and_signing_contracts_are_explicit(tmp_path) -> None:
    _, _, files = load_test_kit_files(tmp_path)
    compatibility = strict_json_document(files["metadata/compatibility-matrix.json"])
    lock = strict_json_document(files["metadata/developer-kit-lock.json"])
    support = strict_json_document(files["metadata/support-deprecation-policy.json"])
    signing = strict_json_document(files["metadata/signing-request.json"])
    assert compatibility["matrix_version"] == COMPATIBILITY_MATRIX_VERSION
    assert compatibility["automatic_upgrade"] is False
    assert lock["lock_version"] == KIT_LOCK_VERSION
    assert set(cast(dict[str, object], lock["artifacts"])) == {
        "runtime",
        "sdk",
        "tooling",
        "template",
        "alpha_extension",
        "beta_extension",
    }
    assert support["current_supported_kit"] == "1.0.0"
    assert support["supported_predecessor_count"] == 0
    assert signing["state"] == "UNSIGNED_ENGINEERING_CANDIDATE"
    assert signing["signature_present"] is False
