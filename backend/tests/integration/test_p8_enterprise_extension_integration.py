"""Clean-install and Runtime integration for two independent projects."""

from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from aps_extension_tooling.conformance import conform_extension_set

from backend.tests.p8_enterprise_extension_support import example_results


def test_two_projects_clean_install_test_package_and_load_as_one_runtime_set() -> None:
    alpha, beta = example_results(clean_install=True)
    assert alpha.project_test_count == 2
    assert beta.project_test_count == 3
    with TemporaryDirectory() as temporary:
        adapter, report = conform_extension_set(
            (alpha, beta), runtime_directory=Path(temporary)
        )
    assert report["status"] == "PASS"
    assert report["extension_count"] == 2
    assert report["contribution_count"] == 6
    assert adapter.document["mode"] == "LOADED"
    assert adapter.document["extension_count"] == 2
    assert adapter.safe_metrics()["payloads_recorded"] is False
