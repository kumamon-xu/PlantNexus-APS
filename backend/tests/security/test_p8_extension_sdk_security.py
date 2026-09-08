"""Closed-boundary and fail-closed security cases for Extension SDK v1."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aps_extension_sdk import (
    ExtensionContractError,
    ExtensionErrorCode,
    assert_immutable_json,
    parse_extension_manifest,
)


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "backend/aps_extension_sdk"
SAMPLE = PACKAGE / "contracts/samples/extension-manifest.v1.synthetic.json"


def _manifest() -> dict[str, Any]:
    value = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_sdk_package_has_no_core_runtime_solver_database_or_dynamic_import_edge() -> None:
    forbidden_roots = {
        "app",
        "backend",
        "celery",
        "fastapi",
        "importlib",
        "ortools",
        "psycopg",
        "redis",
        "sqlalchemy",
    }
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"__import__", "eval", "exec", "open"}
        assert imported.isdisjoint(forbidden_roots)


def test_manifest_cannot_request_privileged_runtime_services() -> None:
    document = _manifest()
    document["requested_services"] = ["sdk.service.database.v1"]
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_code_selection", True),
        ("network_install", True),
        ("external_api", True),
        ("database_access", True),
        ("sandboxed", True),
    ],
)
def test_manifest_cannot_expand_the_closed_execution_boundary(
    field: str,
    value: bool,
) -> None:
    document = _manifest()
    document["execution_boundary"][field] = value
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS


def test_mutable_or_nonfinite_extension_return_is_rejected() -> None:
    for value in ({"mutable": []}, [1, 2], {"set"}, float("nan")):
        with pytest.raises(ExtensionContractError) as captured:
            assert_immutable_json(value)
        assert captured.value.code is ExtensionErrorCode.MUTABLE_VALUE


def test_unsafe_entrypoint_and_fingerprint_fail_before_execution() -> None:
    for entrypoint in (
        "../../payload:Extension",
        "enterprise_extension;os.system:Extension",
        "https://example.invalid/plugin:Extension",
    ):
        document = copy.deepcopy(_manifest())
        document["contributions"][0]["implementation"] = entrypoint
        with pytest.raises(ExtensionContractError) as captured:
            parse_extension_manifest(document)
        assert captured.value.code is ExtensionErrorCode.INVALID_MANIFEST


def test_manifest_errors_do_not_echo_unknown_secret_fields() -> None:
    secret = "credential-super-secret-value"
    document = _manifest()
    document[secret] = True
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.INVALID_MANIFEST
    assert secret not in str(captured.value)
