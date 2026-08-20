"""Emit machine-checkable TASK-P2-02 planning-machine contract evidence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tomllib
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app import SCHEMA_VERSION
from app.planning.contracts import (
    SolverStatus,
    contract_fingerprint,
    outcome_document_for_status,
    outcome_for_solver_status,
    statuses,
    validate_contract_bundle,
)


REPORT_VERSION = "planning-machine-contract-report.v1"
TASK_ID = "TASK-P2-02"
_ARTIFACT_SHA256 = {
    "schemas/json/planning-policy.schema.json": (
        "62624424115c3f6c9d45e920bcb0ac744ae9e1f2173af81072610298560a1bda"
    ),
    "schemas/json/solve-limits.schema.json": (
        "8caff522a1fef8e40671cdff3ca857084cbf908b5c7fdfb9fdd8468fc3811d95"
    ),
    "schemas/json/planning-solution.schema.json": (
        "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4"
    ),
    "schemas/json/solver-report.schema.json": (
        "64feacd0d1ec0ea1c9d3f62d8e38b473b61f42dab5bc672c5898c5e056257b2a"
    ),
    "schemas/samples/planning-policy.v1.synthetic.json": (
        "87f7b509d36220135358dbafef9b908725103e22ee69ff875b12861ebb410a26"
    ),
    "schemas/samples/solve-limits.v1.synthetic.json": (
        "68ebc4d134d945ce0cd73254166b6e299096a7f4cd0577187244c0dcfd38b492"
    ),
    "schemas/samples/planning-solution.v1.synthetic.json": (
        "054afe4525a115dc57ac88467bee36ef42f929c96e9741f5b418665cdce03afb"
    ),
    "schemas/samples/solver-report.v1.synthetic.json": (
        "df2348dc3cdb842b6bc87169ef111abb8cdf6394d6a39cafb67285be44e6528d"
    ),
}
_SCHEMA_SAMPLE_PAIRS = (
    ("planning-policy.schema.json", "planning-policy.v1.synthetic.json"),
    ("solve-limits.schema.json", "solve-limits.v1.synthetic.json"),
    ("planning-solution.schema.json", "planning-solution.v1.synthetic.json"),
    ("solver-report.schema.json", "solver-report.v1.synthetic.json"),
)
_EXPECTED_RUNTIME_DEPENDENCIES = {
    "alembic==1.16.5",
    "celery==5.5.3",
    "defusedxml==0.7.1",
    "fastapi==0.116.1",
    "openpyxl==3.1.5",
    "opentelemetry-api==1.36.0",
    "psycopg[binary]==3.2.9",
    "pydantic-settings==2.10.1",
    "redis==6.4.0",
    "sqlalchemy==2.0.43",
    "structlog==25.4.0",
    "uvicorn==0.35.0",
}
_EXPECTED_DEV_DEPENDENCIES = {
    "httpx==0.28.1",
    "hypothesis==6.165.10",
    "jsonschema==4.25.1",
    "pyright==1.1.411",
    "pytest==8.4.1",
    "PyYAML==6.0.2",
    "ruff==0.12.10",
}
_EXPECTED_UV_LOCK_SHA256 = (
    "7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd"
)


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _artifact(root: Path, relative_path: str) -> dict[str, object]:
    content = (root / relative_path).read_bytes()
    observed = sha256(content).hexdigest()
    if observed != _ARTIFACT_SHA256[relative_path]:
        raise ValueError(f"published artifact bytes changed: {relative_path}")
    return {"sha256": observed, "size_bytes": len(content)}


def _pass(name: str, details: object) -> dict[str, object]:
    return {"name": name, "status": "PASS", "details": details}


def _schema_registry(root: Path) -> Registry:
    registry = Registry()
    for schema_name, _ in _SCHEMA_SAMPLE_PAIRS:
        schema = _load_json(root / "schemas" / "json" / schema_name)
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema)
        )
    return registry


def _check_solver_free_boundary(root: Path) -> dict[str, object]:
    pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")
    lock_content = (root / "uv.lock").read_bytes()
    lock_sha256 = sha256(lock_content).hexdigest()
    project = cast(dict[str, Any], tomllib.loads(pyproject_text))
    runtime_dependencies = set(cast(list[str], project["project"]["dependencies"]))
    dev_dependencies = set(
        cast(list[str], project["dependency-groups"]["dev"])
    )
    if runtime_dependencies != _EXPECTED_RUNTIME_DEPENDENCIES:
        raise ValueError("TASK-P2-02 changed runtime dependencies")
    if dev_dependencies != _EXPECTED_DEV_DEPENDENCIES:
        raise ValueError("TASK-P2-02 changed development dependencies")
    if lock_sha256 != _EXPECTED_UV_LOCK_SHA256:
        raise ValueError("TASK-P2-02 changed uv.lock")
    source_paths = (
        root / "backend" / "app" / "planning" / "contracts.py",
        root / "backend" / "app" / "planning" / "policy" / "contracts.py",
    )
    sources = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    if "ortools" in pyproject_text.lower() or b"ortools" in lock_content.lower():
        raise ValueError("TASK-P2-02 added an OR-Tools dependency")
    for forbidden in (
        "CpModel",
        "cp_model",
        "IntervalVar",
        "from sqlalchemy",
        "from fastapi",
        "app.planning.backends",
        "app.planning.validation",
    ):
        if forbidden in sources:
            raise ValueError(f"implementation boundary crossed: {forbidden}")
    return {
        "runtime_dependency_change": "NONE",
        "development_dependency_change": "NONE",
        "runtime_dependency_count": len(runtime_dependencies),
        "development_dependency_count": len(dev_dependencies),
        "lockfile_change": "NONE",
        "uv_lock_sha256": lock_sha256,
        "ortools": "NOT_INSTALLED",
        "solver_backend_implementation": "NOT_IMPLEMENTED_BY_TASK",
        "constraint_implementation": "NOT_IMPLEMENTED_BY_TASK",
        "schedule_validator": "NOT_IMPLEMENTED_BY_TASK",
        "persistence_api_worker": "NOT_IMPLEMENTED_BY_TASK",
    }


def run_contract_checks(root: Path) -> dict[str, object]:
    """Validate fixed artifacts, pure invariants, status mapping, and scope."""

    schema_root = root / "schemas" / "json"
    sample_root = root / "schemas" / "samples"
    registry = _schema_registry(root)
    documents: dict[str, dict[str, Any]] = {}
    schema_ids: list[str] = []
    for schema_name, sample_name in _SCHEMA_SAMPLE_PAIRS:
        schema = _load_json(schema_root / schema_name)
        sample = _load_json(sample_root / sample_name)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        ).validate(sample)
        documents[sample_name] = sample
        schema_ids.append(cast(str, schema["$id"]))

    policy = documents["planning-policy.v1.synthetic.json"]
    limits = documents["solve-limits.v1.synthetic.json"]
    solution = documents["planning-solution.v1.synthetic.json"]
    report = documents["solver-report.v1.synthetic.json"]
    validate_contract_bundle(policy, limits, solution, report)

    artifacts = {
        path: _artifact(root, path) for path in sorted(_ARTIFACT_SHA256)
    }
    status_mapping = {}
    for status in statuses():
        outcome = outcome_for_solver_status(status)
        status_mapping[status.value] = {
            "planning_run_outcome": outcome_document_for_status(status),
            "candidate_available": outcome.candidate_available,
        }
    if set(status_mapping) != {status.value for status in SolverStatus}:
        raise ValueError("SolverStatus mapping is incomplete")

    sample_fingerprints = {
        name: contract_fingerprint(document)
        for name, document in sorted(documents.items())
    }
    checks = [
        _pass(
            "fixed-schema-and-sample-artifacts",
            {"artifacts": artifacts, "schema_ids": sorted(schema_ids)},
        ),
        _pass(
            "planning-policy-and-solve-limits",
            {
                "data_plane": policy["data_plane"],
                "hard_constraint_ids": policy["hard_constraint_ids"],
                "objective_stages": policy["objective_stages"],
                "explicit_limit_fields": [
                    "max_wall_time_seconds",
                    "max_workers",
                    "random_seed",
                ],
                "implicit_defaults": "FORBIDDEN",
            },
        ),
        _pass("seven-status-product-mapping", status_mapping),
        _pass(
            "cross-document-fingerprint-and-replay",
            {
                "sample_fingerprints": sample_fingerprints,
                "solution_policy_fingerprint": solution["policy"][
                    "policy_fingerprint"
                ],
                "solution_limits_fingerprint": solution["limits"][
                    "limits_fingerprint"
                ],
                "report_solution_fingerprint": report["solution"][
                    "solution_fingerprint"
                ],
            },
        ),
        _pass("task-boundary", _check_solver_free_boundary(root)),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "schema_set_version": SCHEMA_VERSION,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "check_count": len(checks),
        "checks": checks,
        "boundaries": {
            "sample_evidence_kind": "CONTRACT_SAMPLE",
            "sample_solver_execution": "NONE",
            "p2_objective_scope": "OBJ-001_ONLY",
            "obj_002_obj_003": "DEFERRED",
            "solver_backend": "NOT_IMPLEMENTED_BY_TASK",
            "schedule_validator": "NOT_IMPLEMENTED_BY_TASK",
            "production_authority": "BLOCKED_BY_OPEN_ITEMS",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_contract_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "main", "run_contract_checks"]
