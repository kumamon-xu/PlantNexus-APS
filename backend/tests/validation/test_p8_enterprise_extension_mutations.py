"""Manifest and Runtime-set mutations must fail with stable codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aps_extension_sdk import canonical_json_bytes, fingerprint_json
from aps_extension_tooling.conformance import conform_extension_set
from aps_extension_tooling.project import (
    ConformanceError,
    ExtensionToolingErrorCode,
    load_project,
)

from backend.tests.p8_enterprise_extension_support import (
    ALPHA,
    BETA,
    ROOT,
    copy_example,
    example_results,
    mutate_manifest,
)


def test_missing_validation_pair_is_rejected(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")

    def mutation(document: dict[str, object]) -> None:
        contributions = document["contributions"]
        assert isinstance(contributions, list)
        document["contributions"] = contributions[:1]

    mutate_manifest(project, mutation)
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == "MISSING_VALIDATION_PAIR"


def test_objective_outside_enterprise_tie_break_is_rejected(tmp_path: Path) -> None:
    project = copy_example(BETA, tmp_path / "project")

    def mutation(document: dict[str, object]) -> None:
        contributions = document["contributions"]
        assert isinstance(contributions, list)
        objective = contributions[1]
        assert isinstance(objective, dict)
        objective["objective_stage"] = "CORE_DELIVERY"

    mutate_manifest(project, mutation)
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == "INVALID_OBJECTIVE_STAGE"


def test_privileged_requested_service_is_rejected(tmp_path: Path) -> None:
    project = copy_example(BETA, tmp_path / "project")

    def mutation(document: dict[str, object]) -> None:
        document["requested_services"] = ["database"]

    mutate_manifest(project, mutation)
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == "FORBIDDEN_BOUNDARY_ACCESS"


def test_duplicate_extension_set_is_rejected_before_runtime_side_effect(
    tmp_path: Path,
) -> None:
    alpha = example_results()[0]
    with pytest.raises(ConformanceError) as captured:
        conform_extension_set((alpha, alpha), runtime_directory=tmp_path / "runtime")
    assert captured.value.code == ExtensionToolingErrorCode.SET_CONFLICT
    assert not (tmp_path / "runtime").exists()


def test_configuration_values_must_satisfy_declared_schema(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    path = project / "extension/extension-configuration.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["values"] = {"required_tag": ""}
    document.pop("configuration_fingerprint")
    document["configuration_fingerprint"] = fingerprint_json(document)
    path.write_bytes(canonical_json_bytes(document) + b"\n")
    with pytest.raises(ConformanceError) as captured:
        from aps_extension_tooling.conformance import conform_project

        conform_project(project, repository_root=ROOT, clean_install=False)
    assert captured.value.code == ExtensionToolingErrorCode.PROJECT_INVALID
    assert captured.value.field == "configuration_path.values"
