"""Contract evidence for TEST-P8-ENTERPRISE-EXTENSION-KIT-001."""

from __future__ import annotations

import json
from pathlib import Path

from aps_extension_sdk import ExtensionPoint
from aps_extension_tooling.project import DEVELOPER_KIT_VERSION, RUNTIME_VERSION

from backend.tests.p8_enterprise_extension_support import ROOT, example_results
from scripts.p8_enterprise_extension_kit_check import main as kit_check_main


def test_two_standalone_projects_cover_the_six_public_spi_without_core_copy() -> None:
    results = example_results()
    assert len(results) == 2
    assert len({result.project.project_id for result in results}) == 2
    assert len({result.project.package_name for result in results}) == 2
    assert {
        contribution.extension_point
        for result in results
        for contribution in result.project.manifest.contributions
    } == set(ExtensionPoint)
    for result in results:
        assert result.project.sdk_api_version == "1.0.0"
        assert result.project.runtime_version == RUNTIME_VERSION
        assert result.project.developer_kit_version == DEVELOPER_KIT_VERSION
        assert result.report["source_scan"]["core_copy_count"] == 0
        assert result.report["source_scan"]["forbidden_import_count"] == 0


def test_machine_evidence_binds_template_examples_negatives_and_boundaries(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.json"
    template_path = tmp_path / "template.json"
    dependency_path = tmp_path / "dependency.json"
    benchmark_path = tmp_path / "benchmark.json"
    assert (
        kit_check_main(
            [
                "--root",
                str(ROOT),
                "--report",
                str(report_path),
                "--template-manifest",
                str(template_path),
                "--dependency-report",
                str(dependency_path),
                "--benchmark-report",
                str(benchmark_path),
                "--artifact-directory",
                str(tmp_path / "artifacts"),
            ]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    dependencies = json.loads(dependency_path.read_text(encoding="utf-8"))
    assert report["task_id"] == "TASK-P8-14"
    assert report["test_id"] == "TEST-P8-ENTERPRISE-EXTENSION-KIT-001"
    assert report["diff_base"] == "2682a2235f33d37cc909a1ad8ca3c52a6dffab05"
    assert report["check_count"] == 12
    assert report["negative_count"] == 8
    assert report["issues"] == []
    assert report["status"] == "PASS"
    assert dependencies["third_party_extension_runtime_dependency_count"] == 0
    assert dependencies["floating_dependency_count"] == 0
    assert dependencies["sdk_distribution_license_status"] == (
        "BLOCKED_UNTIL_DEVELOPER_KIT_P8_15"
    )
