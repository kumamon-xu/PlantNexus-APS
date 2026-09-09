"""Fail-closed source, dependency, ownership, and path boundary tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aps_extension_sdk import canonical_json_bytes
from aps_extension_tooling.project import (
    ConformanceError,
    ExtensionToolingErrorCode,
    load_project,
)

from backend.tests.p8_enterprise_extension_support import ALPHA, ROOT, copy_example


def _descriptor(project: Path) -> dict[str, object]:
    return json.loads(
        (project / "enterprise-extension-project.v1.json").read_text(encoding="utf-8")
    )


def _write_descriptor(project: Path, document: dict[str, object]) -> None:
    (project / "enterprise-extension-project.v1.json").write_bytes(
        canonical_json_bytes(document) + b"\n"
    )


def test_core_internal_import_is_rejected_before_packaging(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    (project / "src/example_alpha_extension/forbidden.py").write_text(
        "from app.planning import contracts\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN


def test_floating_sdk_dependency_is_rejected(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    (project / "requirements.lock").write_text(
        "aps-extension-sdk>=1.0\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID


def test_missing_owner_and_license_are_rejected(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    document = _descriptor(project)
    document["owner"] = "unknown"
    _write_descriptor(project, document)
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == ExtensionToolingErrorCode.OWNER_UNDECLARED


def test_project_relative_path_cannot_escape_repository(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    document = _descriptor(project)
    document["manifest_path"] = "../extension-manifest.json"
    _write_descriptor(project, document)
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == ExtensionToolingErrorCode.PROJECT_INVALID
    assert str(tmp_path) not in captured.value.safe_message


def test_core_copy_is_rejected_even_when_renamed_outside_source(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    copied = ROOT / "backend/app/api/routers/__init__.py"
    (project / "copied-core.txt").write_bytes(copied.read_bytes())
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == ExtensionToolingErrorCode.CORE_COPY_DETECTED


def test_undeclared_source_package_is_rejected(tmp_path: Path) -> None:
    project = copy_example(ALPHA, tmp_path / "project")
    hidden = project / "src/hidden_package"
    hidden.mkdir()
    (hidden / "extra.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ConformanceError) as captured:
        load_project(project, repository_root=ROOT)
    assert captured.value.code == ExtensionToolingErrorCode.SOURCE_INVALID
