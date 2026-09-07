"""Rebuild and preflight integration tests for the P8-09 distribution."""

from __future__ import annotations

import pytest

from app.infrastructure.release.builder import load_release_policy
from app.infrastructure.release.contracts import ReleaseContractError
from app.infrastructure.release.preflight import preflight_release
from backend.tests.p8_release_support import (
    ROOT,
    TEST_COMMIT,
    build_test_release,
    load_test_release_files,
)


def _configuration_names() -> set[str]:
    policy = load_release_policy(ROOT)
    return set(policy["preflight"]["required_configuration_names"])


def test_two_clean_assemblies_are_byte_identical(tmp_path) -> None:
    first = build_test_release(tmp_path / "first")
    second = build_test_release(tmp_path / "second")
    assert first.archive_sha256 == second.archive_sha256
    assert first.archive_path.read_bytes() == second.archive_path.read_bytes()
    assert first.release_fingerprint == second.release_fingerprint


def test_preflight_accepts_exact_candidate_without_reading_secret_values(tmp_path) -> None:
    artifact, _ = load_test_release_files(tmp_path)
    report = preflight_release(
        artifact.archive_path,
        expected_code_commit=TEST_COMMIT,
        configured_names=_configuration_names(),
    )
    assert report["status"] == "PASS"
    assert report["configuration"]["secret_values_observed"] is False
    assert report["production_ready"] is False
    assert len(report["checks"]) == 7


@pytest.mark.parametrize(
    ("expected_code_commit", "runtime_version", "configured", "production", "code"),
    [
        ("f" * 40, "0.1.0", True, False, "VERSION_MISMATCH"),
        (TEST_COMMIT, "9.9.9", True, False, "VERSION_MISMATCH"),
        (TEST_COMMIT, "0.1.0", False, False, "CONFIGURATION_MISSING"),
        (TEST_COMMIT, "0.1.0", True, True, "PRODUCTION_AUTHORITY_UNAVAILABLE"),
    ],
)
def test_preflight_fails_closed_on_mismatch_missing_config_or_production(
    tmp_path,
    expected_code_commit: str,
    runtime_version: str,
    configured: bool,
    production: bool,
    code: str,
) -> None:
    artifact = build_test_release(tmp_path)
    names = _configuration_names() if configured else set()
    with pytest.raises(ReleaseContractError) as captured:
        preflight_release(
            artifact.archive_path,
            expected_code_commit=expected_code_commit,
            expected_runtime_version=runtime_version,
            configured_names=names,
            production_requested=production,
        )
    assert captured.value.code == code
