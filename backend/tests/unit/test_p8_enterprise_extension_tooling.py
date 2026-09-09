"""Unit tests for project parsing, scaffolding, and the public CLI."""

from __future__ import annotations

import json
from pathlib import Path

from aps_extension_tooling.conformance import scaffold_project
from aps_extension_tooling.packaging import project_archive, sdk_wheel
from aps_extension_tooling.project import load_project

from backend.tests.p8_enterprise_extension_support import ALPHA, ROOT, TEMPLATE
from scripts.aps_extension_conformance import main as conformance_main


def _scaffold(target: Path) -> Path:
    return scaffold_project(
        template_root=TEMPLATE,
        output_root=target,
        repository_root=ROOT,
        extension_id="com.example.aps.unit",
        distribution_name="example-unit-aps-extension",
        package_name="example_unit_extension",
        owner="Example Enterprise Unit Engineering",
        repository_url="https://example.invalid/enterprise/unit-extension",
        license_expression="LicenseRef-Example-Enterprise",
        source_commit="b" * 40,
    )


def test_project_parser_requires_exact_sdk_wheel_and_sdk_only_imports() -> None:
    _, sdk_bytes = sdk_wheel(ROOT)
    from aps_extension_tooling.packaging import digest_bytes

    project, scan = load_project(
        ALPHA,
        repository_root=ROOT,
        expected_sdk_wheel_digest=digest_bytes(sdk_bytes),
    )
    assert project.project_id == "com.example.aps.alpha"
    assert scan.import_roots == (
        "__future__",
        "aps_extension_sdk",
        "collections",
        "example_alpha_extension",
        "json",
        "pathlib",
        "unittest",
    )
    assert scan.core_copy_count == 0


def test_scaffold_is_reproducible_local_and_does_not_create_git(tmp_path: Path) -> None:
    first = _scaffold(tmp_path / "first")
    second = _scaffold(tmp_path / "second")
    assert project_archive(first) == project_archive(second)
    assert not (first / ".git").exists()
    project, _ = load_project(first, repository_root=ROOT)
    assert project.project_id == "com.example.aps.unit"
    assert project.owner == "Example Enterprise Unit Engineering"


def test_public_cli_checks_one_project_and_writes_safe_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    output = tmp_path / "artifacts"
    assert (
        conformance_main(
            [
                "--root",
                str(ROOT),
                "check",
                "--project",
                str(ALPHA),
                "--output",
                str(output),
                "--report",
                str(report_path),
                "--skip-clean-install",
            ]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["project_id"] == "com.example.aps.alpha"
    assert str(ROOT) not in report_path.read_text(encoding="utf-8")
    assert len(tuple(output.glob("*.whl"))) == 2
