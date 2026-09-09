"""Packaged SDK/tooling/template/Extension integration for TASK-P8-15."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from aps_extension_tooling.conformance import conform_extension_set, conform_project
from aps_developer_kit.contracts import read_kit_archive, strict_json_document
from backend.tests.p8_developer_kit_support import ROOT, build_test_kit


def _extract(files: dict[str, bytes], root: Path) -> None:
    for relative, raw in files.items():
        path = root.joinpath(*Path(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def test_packaged_two_extension_set_loads_with_exact_kit_inputs(tmp_path) -> None:
    artifact = build_test_kit(tmp_path)
    _, files = read_kit_archive(artifact.archive_path)
    extracted = tmp_path / "extracted"
    _extract(files, extracted)
    lock = strict_json_document(files["metadata/developer-kit-lock.json"])
    sdk_entry = cast(dict[str, object], cast(dict[str, object], lock["artifacts"])["sdk"])
    inventory = json.loads(files["metadata/core-source-hashes.json"])
    core_digests = frozenset(
        entry["sha256"].removeprefix("sha256:") for entry in inventory["entries"]
    )
    results = tuple(
        conform_project(
            extracted / f"examples/{name}",
            repository_root=ROOT,
            clean_install=False,
            sdk_wheel_path=extracted / cast(str, sdk_entry["path"]),
            expected_runtime_version="0.1.0",
            expected_developer_kit_version="1.0.0",
            forbidden_core_digests=core_digests,
        )
        for name in ("alpha-resource-tag", "beta-priority-policy")
    )
    with TemporaryDirectory(prefix="p8-kit-test-runtime-") as runtime_directory:
        _, report = conform_extension_set(
            results, runtime_directory=Path(runtime_directory)
        )
    assert report["status"] == "PASS"
    assert report["developer_kit_version"] == "1.0.0"
    assert report["extension_count"] == 2


def test_build_does_not_relock_or_mutate_predecessor_projects(tmp_path) -> None:
    paths = (
        ROOT
        / "examples/enterprise-extensions/alpha-resource-tag/enterprise-extension-project.v1.json",
        ROOT
        / "examples/enterprise-extensions/beta-priority-policy/enterprise-extension-project.v1.json",
    )
    before = tuple(path.read_bytes() for path in paths)
    artifact = build_test_kit(tmp_path)
    after = tuple(path.read_bytes() for path in paths)
    _, files = read_kit_archive(artifact.archive_path)
    assert before == after
    assert all(b'"developer_kit_version": "0.0.0-not-published"' in raw for raw in after)
    assert (
        b'"developer_kit_version": "1.0.0"'
        in files["examples/alpha-resource-tag/enterprise-extension-project.v1.json"]
    )
