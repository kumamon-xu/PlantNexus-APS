"""Integrated public-client, browser-evidence, and backend-only P8-11 tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.release.builder import build_release, build_wheel
from scripts.p8_frontend_distribution_check import (
    REQUIRED_BROWSER_TITLES,
    check_backend_only,
    check_browser_security,
    check_generated_client,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_COMMIT = "b" * 40
TEST_EPOCH = 315_532_800


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_generated_client_is_bound_to_the_five_p8_07_operations() -> None:
    result = check_generated_client(ROOT, expected_commit=TEST_COMMIT)
    assert result["api_contract"] == "headless-http.v1"
    assert result["compatibility_policy"] == "V1_ADDITIVE_ONLY"
    assert result["operation_count"] == 5
    assert result["total_openapi_operation_count"] == 34
    assert result["schema_digest_count"] == 7
    assert result["auth"] == "OPAQUE_IN_MEMORY_PROVIDER_ONLY"


def test_browser_security_evidence_and_dependency_baseline_are_exact(
    tmp_path: Path,
) -> None:
    specs = [
        {
            "title": title,
            "ok": True,
            "tests": [
                {"projectName": "chromium-p8-headless-distribution", "status": "expected"}
            ],
        }
        for title in sorted(REQUIRED_BROWSER_TITLES)
    ]
    browser = tmp_path / "browser.json"
    sca = tmp_path / "sca.json"
    licenses = tmp_path / "licenses.json"
    _write(
        browser,
        {
            "stats": {
                "expected": 8,
                "skipped": 0,
                "unexpected": 0,
                "flaky": 0,
            },
            "errors": [],
            "suites": [{"specs": specs}],
        },
    )
    _write(sca, {"report_version": "p3-frontend-sca-report.v1", "status": "PASS", "issues": []})
    _write(
        licenses,
        {"report_version": "p3-frontend-license-report.v1", "status": "PASS", "issues": []},
    )
    result = check_browser_security(
        ROOT,
        browser,
        sca,
        licenses,
        expected_commit=TEST_COMMIT,
    )
    assert result["scenario_count"] == 8
    assert result["accessibility"] == "AXE_AND_KEYBOARD_PASS"
    assert result["authentication_storage"] == "NO_CREDENTIAL_PERSISTENCE"


def test_runtime_release_starts_from_its_wheel_without_frontend(
    tmp_path: Path,
) -> None:
    wheel = build_wheel(ROOT, tmp_path / "wheel", epoch=TEST_EPOCH)
    artifact = build_release(
        ROOT,
        wheel,
        tmp_path / "release",
        code_commit=TEST_COMMIT,
        epoch=TEST_EPOCH,
    )
    report = tmp_path / "runtime-report.json"
    _write(
        report,
        {
            "report_version": "p8-runtime-release-report.v1",
            "task_id": "TASK-P8-09",
            "code_commit": TEST_COMMIT,
            "status": "PASS",
            "issues": [],
            "release": {
                "runtime_version": artifact.runtime_version,
                "archive_name": artifact.archive_path.name,
                "archive_sha256": artifact.archive_sha256,
            },
        },
    )
    result = check_backend_only(
        ROOT,
        report,
        tmp_path / "release",
        expected_commit=TEST_COMMIT,
    )
    assert result["frontend_payload_count"] == 0
    assert result["smoke"] == {
        "frontend_routes": [],
        "liveness": True,
        "module_from_release": True,
        "openapi": True,
        "p8_headless_routes": 5,
        "readiness": True,
    }
