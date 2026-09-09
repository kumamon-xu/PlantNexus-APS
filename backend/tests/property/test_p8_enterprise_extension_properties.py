"""Determinism and order properties for independent Extension projects."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from aps_extension_tooling.conformance import conform_extension_set, scaffold_project
from aps_extension_tooling.packaging import extension_wheel, project_archive

from backend.tests.p8_enterprise_extension_support import (
    ROOT,
    TEMPLATE,
    example_results,
)


def test_repeated_packages_are_byte_identical_for_both_projects() -> None:
    for result in example_results():
        first_name, first = extension_wheel(result.project)
        second_name, second = extension_wheel(result.project)
        assert first_name == second_name
        assert first == second == result.extension_wheel_bytes


def test_runtime_set_resolution_is_independent_of_project_input_order() -> None:
    first, second = example_results()
    with TemporaryDirectory() as forward_dir, TemporaryDirectory() as reverse_dir:
        _, forward = conform_extension_set(
            (first, second), runtime_directory=Path(forward_dir)
        )
        _, reverse = conform_extension_set(
            (second, first), runtime_directory=Path(reverse_dir)
        )
    assert forward["extension_set_fingerprint"] == reverse["extension_set_fingerprint"]


def test_scaffold_archive_is_stable_for_same_identity(tmp_path: Path) -> None:
    archives = []
    for index in range(3):
        target = tmp_path / str(index)
        scaffold_project(
            template_root=TEMPLATE,
            output_root=target,
            repository_root=ROOT,
            extension_id="com.example.aps.property",
            distribution_name="example-property-aps-extension",
            package_name="example_property_extension",
            owner="Example Enterprise Property Engineering",
            repository_url="https://example.invalid/enterprise/property-extension",
            license_expression="LicenseRef-Example-Enterprise",
            source_commit="c" * 40,
        )
        archives.append(project_archive(target))
    assert archives[0] == archives[1] == archives[2]
