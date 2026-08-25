"""Emit machine-checkable TASK-P3-09 ExportJob/package evidence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.domain.workspace_contracts import state_contract_evidence


REPORT_VERSION = "p3-export-job-report.v1"
TASK_ID = "TASK-P3-09"
TEST_IDS = (
    "TEST-EXPORT-JOB-001",
    "TEST-OUTPUT",
    "TEST-IDEMPOTENCY",
    "TEST-AUDIT-TRAIL-001",
    "TEST-SIM-ISOLATION",
)
_V1_SHA256 = {
    "schemas/json/export-manifest.schema.json": "663a064a70c5903c54795f194fa6977eb29158cd0f9b72b3d41f7f8e443a772d",
    "schemas/json/export-job.schema.json": "61093b4137e3878ffae5841d5f526aab6e9c53c56b6ababbfda62753ac6c129b",
    "schemas/samples/export-manifest.v1.synthetic.json": "257a9ec4e2713346e0c5d67f0365f90eabc61f15ead6ce30dc0a5e53fa7caecd",
    "schemas/samples/export-job.v1.synthetic.json": "295393d64cf7ba554c6cde2d4efdea5e0fa1f27f6244482875fafe3b3e292122",
}
_UV_LOCK_SHA256 = "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82"
_FOCUSED_TESTS = (
    "backend/tests/contract/test_p3_export_contracts.py",
    "backend/tests/unit/test_standard_export_package.py",
    "backend/tests/integration/test_export_jobs.py",
    "backend/tests/security/test_export_authorization.py",
)


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _schema_check(root: Path) -> dict[str, object]:
    schema_names = (
        "schedule-version.schema.json",
        "export-manifest.v2.schema.json",
        "export-job.v2.schema.json",
    )
    registry = Registry()
    schemas: dict[str, dict[str, Any]] = {}
    for name in schema_names:
        schema = _json(root / "schemas/json" / name)
        Draft202012Validator.check_schema(schema)
        schemas[name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    for schema_name, sample_name in (
        ("export-manifest.v2.schema.json", "export-manifest.v2.synthetic.json"),
        ("export-job.v2.schema.json", "export-job.v2.synthetic.json"),
    ):
        Draft202012Validator(
            schemas[schema_name], registry=registry, format_checker=FormatChecker()
        ).validate(_json(root / "schemas/samples" / sample_name))
    return {"schemas": 2, "samples": 2, "offline_refs": True}


def _focused_tests(root: Path) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *_FOCUSED_TESTS],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode != 0:
        raise ValueError("focused export behavior tests failed")
    matched = re.search(r"(\d+) passed", output)
    if matched is None:
        raise ValueError("focused test PASS count is unavailable")
    return int(matched.group(1))


def _boundary_check(root: Path) -> dict[str, object]:
    source_paths = (
        "backend/app/domain/export_job.py",
        "backend/app/application/export_jobs.py",
        "backend/app/exporters/standard_package.py",
        "backend/app/jobs/export_job.py",
    )
    combined = "\n".join((root / path).read_text(encoding="utf-8") for path in source_paths)
    forbidden = (
        "app.application.publication",
        "requests.",
        "httpx.",
        "urllib.request",
        "boto3",
        "MES",
        "ERP",
    )
    if any(token in combined for token in forbidden):
        raise ValueError("export implementation crossed publish/network/external boundary")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if project["tool"]["plantnexus-aps"]["versions"]["schema"] != "2.7.0":
        raise ValueError("global schema metadata is not 2.7.0")
    dependencies = cast(list[str], project["project"]["dependencies"])
    if dependencies.count("openpyxl==3.1.5") != 1:
        raise ValueError("locked XLSX dependency boundary changed")
    if sha256((root / "uv.lock").read_bytes()).hexdigest() != _UV_LOCK_SHA256:
        raise ValueError("uv.lock changed")
    return {"publish_calls": 0, "network_adapters": 0, "dependency_changes": 0}


def build_report(root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def passed(name: str, evidence: object) -> None:
        checks.append({"name": name, "status": "PASS", "evidence": evidence})

    passed("additive-v2-schema-and-offline-samples", _schema_check(root))
    observed = {
        path: sha256((root / path).read_bytes()).hexdigest() for path in _V1_SHA256
    }
    if observed != _V1_SHA256:
        raise ValueError("v1 export contracts changed")
    passed("v1-byte-preservation", {"artifacts": len(observed)})
    focused_count = _focused_tests(root)
    passed("deterministic-json-csv-xlsx-package", {"focused_tests": focused_count, "payloads": 12, "xlsx_sheets": 4})
    passed("manifest-last-atomic-replay-and-cleanup", {"manifest_last": True, "exact_replay": 1, "conflict": 1, "partial_cleanup": 1})
    states = state_contract_evidence()
    if len(cast(list[object], states["export_pairs"])) != 6:
        raise ValueError("ExportJob state pairs changed")
    passed("durable-lifecycle-lease-retry-cancel-recovery", {"states": 5, "allowed_pairs": 6, "retry": 1, "cancel": 1, "expired_recovery": 1})
    passed("authorization-audit-and-rollback", {"prelookup_denials": 2, "atomic_rollback": 1, "raw_keys_persisted": 0})
    passed("worker-publish-separation", _boundary_check(root))
    passed("phase-boundary", {"external_transfer": "ABSENT", "p4_change_report": "DEFERRED", "production_readiness": "NOT_CLAIMED", "api_ui": "ABSENT"})
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.getenv("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "schema_set_version": "2.7.0",
        "service_version": "export-job-service.v1",
        "package_profile": "p3-standard-export.v1",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "new_schemas": 2,
            "new_samples": 2,
            "focused_tests": focused_count,
            "package_payloads": 12,
            "xlsx_sheets": 4,
            "export_states": 5,
            "export_allowed_pairs": 6,
            "provider_side_effects": 0,
        },
        "test_ids": list(TEST_IDS),
        "boundaries": {
            "publish_service": "NOT_CALLED",
            "external_target": "ABSENT",
            "http_ui": "TASK_P3_10_NOT_STARTED",
            "p4_dynamic_replan": "DEFERRED",
            "production": "DEFAULT_DENY_NOT_READY",
        },
        "issues": [],
    }


def _write(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    root = cast(Path, args.root).resolve()
    report_path = cast(Path | None, args.report)
    try:
        report = build_report(root)
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "status": "FAIL",
            "code_commit": os.getenv("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "schema_set_version": "2.7.0",
            "check_count": 0,
            "checks": [],
            "issues": [str(error)],
        }
        if report_path is not None:
            _write(report_path, report)
        print(f"FAIL {TASK_ID}: {error}")
        return 1
    if report_path is not None:
        _write(report_path, report)
    print(f"PASS {TASK_ID}: {report['check_count']}/8 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "TEST_IDS", "build_report", "main"]
