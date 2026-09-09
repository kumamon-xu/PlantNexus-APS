"""Shared bounded fixtures for TEST-P8-ENTERPRISE-EXTENSION-KIT-001."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import shutil
from typing import Any, cast

from aps_extension_sdk import canonical_json_bytes, fingerprint_json
from aps_extension_tooling.conformance import ConformanceResult, conform_project


ROOT = Path(__file__).resolve().parents[2]
ALPHA = ROOT / "examples/enterprise-extensions/alpha-resource-tag"
BETA = ROOT / "examples/enterprise-extensions/beta-priority-policy"
TEMPLATE = ROOT / "templates/enterprise-extension"


def example_results(*, clean_install: bool = False) -> tuple[ConformanceResult, ...]:
    return tuple(
        conform_project(path, repository_root=ROOT, clean_install=clean_install)
        for path in (ALPHA, BETA)
    )


def copy_example(source: Path, target: Path) -> Path:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    return target


def mutate_manifest(
    project: Path,
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    path = project / "extension/extension-manifest.json"
    document = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    mutation(document)
    document.pop("manifest_fingerprint", None)
    document["manifest_fingerprint"] = fingerprint_json(document)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


__all__ = [
    "ALPHA",
    "BETA",
    "ROOT",
    "TEMPLATE",
    "copy_example",
    "example_results",
    "mutate_manifest",
]
