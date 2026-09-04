"""TASK-P3-09 additive export contracts and frozen-v1 compatibility."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from app import SCHEMA_VERSION
from app.domain.workspace_contracts import (
    WorkspaceContractError,
    export_job_fingerprint,
    require_workspace_document,
)


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
SAMPLE_ROOT = ROOT / "schemas" / "samples"
V1_SHA256 = {
    "schemas/json/export-manifest.schema.json": "663a064a70c5903c54795f194fa6977eb29158cd0f9b72b3d41f7f8e443a772d",
    "schemas/json/export-job.schema.json": "61093b4137e3878ffae5841d5f526aab6e9c53c56b6ababbfda62753ac6c129b",
    "schemas/samples/export-manifest.v1.synthetic.json": "257a9ec4e2713346e0c5d67f0365f90eabc61f15ead6ce30dc0a5e53fa7caecd",
    "schemas/samples/export-job.v1.synthetic.json": "295393d64cf7ba554c6cde2d4efdea5e0fa1f27f6244482875fafe3b3e292122",
}


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _validator(schema_name: str) -> Draft202012Validator:
    names = (
        "schedule-version.schema.json",
        "export-manifest.v2.schema.json",
        "export-job.v2.schema.json",
    )
    registry = Registry()
    for name in names:
        schema = _json(SCHEMA_ROOT / name)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return Draft202012Validator(
        _json(SCHEMA_ROOT / schema_name),
        registry=registry,
        format_checker=FormatChecker(),
    )


@pytest.mark.parametrize(
    ("schema_name", "sample_name"),
    (
        ("export-manifest.v2.schema.json", "export-manifest.v2.synthetic.json"),
        ("export-job.v2.schema.json", "export-job.v2.synthetic.json"),
    ),
)
def test_additive_v2_schema_and_sample_validate_offline(
    schema_name: str, sample_name: str
) -> None:
    schema = _json(SCHEMA_ROOT / schema_name)
    Draft202012Validator.check_schema(schema)
    assert "default" not in json.dumps(schema)
    _validator(schema_name).validate(_json(SAMPLE_ROOT / sample_name))


def test_export_job_v2_pure_precheck_and_versions_fail_closed() -> None:
    job = _json(SAMPLE_ROOT / "export-job.v2.synthetic.json")
    assert require_workspace_document(job) == "export-job.v2"
    assert job["job_fingerprint"] == export_job_fingerprint(job)

    wrong_set = deepcopy(job)
    wrong_set["schema_set_version"] = "2.6.0"
    with pytest.raises(WorkspaceContractError):
        require_workspace_document(wrong_set)

    wrong_manifest = deepcopy(job)
    wrong_manifest["state"] = "EXPORTED"
    wrong_manifest["attempt"] = 1
    wrong_manifest["started_at_utc"] = "2026-08-25T00:01:00Z"
    wrong_manifest["finished_at_utc"] = "2026-08-25T00:02:00Z"
    wrong_manifest["artifact_manifest"] = {
        "export_manifest_version": "export-manifest.v1",
        "package_id": "export-package-" + "1" * 64,
        "manifest_fingerprint": "sha256:" + "2" * 64,
        "storage_reference": "sha256:" + "3" * 64,
    }
    wrong_manifest["job_fingerprint"] = export_job_fingerprint(wrong_manifest)
    with pytest.raises(ValidationError):
        _validator("export-job.v2.schema.json").validate(wrong_manifest)


def test_global_metadata_dictionary_and_v1_bytes_are_preserved() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dictionary = yaml.safe_load((ROOT / "schemas/data_dictionary.yaml").read_text(encoding="utf-8"))
    assert SCHEMA_VERSION == "2.10.0"
    assert project["tool"]["plantnexus-aps"]["versions"]["schema"] == "2.10.0"
    assert dictionary["schema_set_version"] == "2.10.0"
    assert {"export-manifest.v1", "export-job.v1", "export-manifest.v2", "export-job.v2"}.issubset(dictionary["schemas"])
    for relative, expected in V1_SHA256.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_manifest_v2_rejects_p4_or_active_content() -> None:
    manifest = _json(SAMPLE_ROOT / "export-manifest.v2.synthetic.json")
    injected = deepcopy(manifest)
    injected["files"][0]["path"] = "change_report.json"
    with pytest.raises(ValidationError):
        _validator("export-manifest.v2.schema.json").validate(injected)
    assert manifest["state_boundary"]["external_transfer"] == "NOT_STARTED"
    assert manifest["state_boundary"]["production"] == "NOT_AUTHORIZED"
