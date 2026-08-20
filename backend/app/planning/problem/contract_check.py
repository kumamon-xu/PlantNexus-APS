"""Emit machine-checkable PlanningProblem v1/v2 contract evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from app import SCHEMA_VERSION
from app.data_validation import validate_import_package
from app.normalization.order_expansion import expand_orders
from app.snapshots import build_planning_snapshot, import_package_id_for

from .builder import build_planning_problem, build_planning_problem_v2
from .contracts import ImmutablePlanningProblem, ImmutablePlanningProblemV2
from .hashing import (
    PLANNING_PROBLEM_VERSION,
    PLANNING_PROBLEM_VERSION_V2,
    PROBLEM_BUILDER_VERSION,
    PROBLEM_BUILDER_VERSION_V2,
    PROBLEM_HASH_PROJECTION_VERSION,
    PROBLEM_HASH_PROJECTION_VERSION_V2,
    problem_hash_projection,
    problem_v2_hash_projection,
    verify_problem,
    verify_problem_v2,
)

REPORT_VERSION = "planning-problem-contract-report.v1"
TASK_ID = "TASK-P2-01"
_EXPECTED_V1_SCHEMA_SHA256 = (
    "41b01bfbcdfdb0a6dc52da1121383f630ac3f08ca7db4d21c0b66dea3a96e943"
)
_EXPECTED_V1_SAMPLE_SHA256 = (
    "aa31fbb20b862b7ef51a0e1ed781cddca07c00a0d2724d9ea34e6a75d08a4093"
)
_EXPECTED_V1_PROBLEM_HASH = (
    "sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72"
)
_EXPECTED_V1_CANONICAL_SHA256 = (
    "1f00ad7a856395328e9eb2c70afe8fe5878d69c3d8618ae7ef45bca34ef08645"
)
_EXPECTED_V2_PROBLEM_HASH = (
    "sha256:9927418a446dd046ddd1d835643da03fbf5cdcf8ca246ba22c3700563a17e9e8"
)
_EXPECTED_V2_CANONICAL_SHA256 = (
    "2dbe06907952d6aba303977d67a7f5d7a6ef89c4be5ac5a6ac8d74e3f95d720a"
)


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _fingerprint(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {"sha256": sha256(content).hexdigest(), "size_bytes": len(content)}


def _pass(name: str, details: object) -> dict[str, object]:
    return {"name": name, "status": "PASS", "details": details}


def _replay_v1(root: Path) -> ImmutablePlanningProblem:
    import_document = _load_json(
        root / "schemas" / "samples" / "import-package.v2.synthetic.json"
    )
    import_document["package_id"] = import_package_id_for(import_document)
    quality = cast(
        dict[str, object], validate_import_package(import_document).document
    )
    expansion = expand_orders(import_document, quality)  # type: ignore[arg-type]
    snapshot = build_planning_snapshot(
        import_document,
        quality,
        expansion,
        cutoff_at_utc="2026-08-20T00:00:00Z",
    )
    return build_planning_problem(
        snapshot,
        problem_builder_version=PROBLEM_BUILDER_VERSION,
        tick_seconds=60,
        horizon_start_utc="2026-08-20T00:00:00Z",
        horizon_end_utc="2026-08-21T00:00:00Z",
    )


def _replay_v2(root: Path) -> ImmutablePlanningProblemV2:
    import_document = _load_json(
        root / "schemas" / "samples" / "import-package.v2.synthetic.json"
    )
    fact = import_document["records"]["execution_facts"][0]
    fact["status"] = "COMPLETED"
    fact.pop("remaining_quantity")
    fact.pop("remaining_seconds")
    fact["actual_end_at_utc"] = "2026-08-19T00:05:00Z"
    fact["completed_quantity"] = 10
    lock = import_document["records"]["operation_locks"][0]
    lock["routing_operation_id"] = "ROUTING-OP-002"
    lock["start_at_utc"] = "2026-08-20T00:00:00Z"
    lock["end_at_utc"] = "2026-08-20T02:00:00Z"
    soft_lock = deepcopy(lock)
    soft_lock["lock_id"] = "LOCK-002"
    soft_lock["lock_type"] = "SOFT_LOCK"
    soft_lock["start_at_utc"] = "2026-08-20T03:00:00Z"
    soft_lock["end_at_utc"] = "2026-08-22T02:00:00Z"
    soft_lock["source"]["source_record_id"] = "SRC-LOCK-002"
    import_document["records"]["operation_locks"].append(soft_lock)
    import_document["package_id"] = import_package_id_for(import_document)
    quality = cast(
        dict[str, object], validate_import_package(import_document).document
    )
    expansion = expand_orders(import_document, quality)  # type: ignore[arg-type]
    snapshot = build_planning_snapshot(
        import_document,
        quality,
        expansion,
        cutoff_at_utc="2026-08-20T00:00:00Z",
    )
    return build_planning_problem_v2(
        snapshot,
        priority_facts={
            "DEMAND-001": {
                "priority_weight": 2,
                "source_system": "plantnexus-synthetic-policy",
                "source_version": "1.0.0",
                "source_record_id": "SIM-P2-DELIVERY-PRIORITY-001",
            }
        },
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=60,
        horizon_start_utc="2026-08-20T00:00:00Z",
        horizon_end_utc="2026-08-21T00:00:00Z",
    )


def run_contract_checks(root: Path) -> dict[str, object]:
    """Verify published schemas, samples, immutable v1 bytes, and replay vectors."""

    schema_root = root / "schemas" / "json"
    sample_root = root / "schemas" / "samples"
    v1_schema_path = schema_root / "planning-problem.schema.json"
    v1_sample_path = sample_root / "planning-problem.synthetic.json"
    v2_schema_path = schema_root / "planning-problem.v2.schema.json"
    v2_sample_path = sample_root / "planning-problem.v2.synthetic.json"

    v1_schema_fingerprint = _fingerprint(v1_schema_path)
    v1_sample_fingerprint = _fingerprint(v1_sample_path)
    if v1_schema_fingerprint["sha256"] != _EXPECTED_V1_SCHEMA_SHA256:
        raise ValueError("PlanningProblem v1 Schema bytes changed")
    if v1_sample_fingerprint["sha256"] != _EXPECTED_V1_SAMPLE_SHA256:
        raise ValueError("PlanningProblem v1 sample bytes changed")

    v1_schema = _load_json(v1_schema_path)
    v1_document = _load_json(v1_sample_path)
    Draft202012Validator.check_schema(v1_schema)
    Draft202012Validator(
        v1_schema, format_checker=FormatChecker()
    ).validate(v1_document)
    v1_problem = _replay_v1(root)
    v1_bytes = v1_problem.canonical_bytes
    verify_problem(v1_problem)
    if (
        v1_problem.problem_hash != _EXPECTED_V1_PROBLEM_HASH
        or sha256(v1_bytes).hexdigest() != _EXPECTED_V1_CANONICAL_SHA256
    ):
        raise ValueError("PlanningProblem v1 replay vector changed")

    v2_schema = _load_json(v2_schema_path)
    v2_document = _load_json(v2_sample_path)
    Draft202012Validator.check_schema(v2_schema)
    Draft202012Validator(
        v2_schema, format_checker=FormatChecker()
    ).validate(v2_document)
    v2_problem = _replay_v2(root)
    v2_bytes = v2_problem.canonical_bytes
    verify_problem_v2(v2_problem)
    if (
        v2_problem.problem_hash != _EXPECTED_V2_PROBLEM_HASH
        or sha256(v2_bytes).hexdigest() != _EXPECTED_V2_CANONICAL_SHA256
        or v2_problem.document != v2_document
    ):
        raise ValueError("PlanningProblem v2 builder replay differs from fixed sample")

    v1_projection = problem_hash_projection(
        cast(dict[str, object], v1_document)
    )
    v2_projection = problem_v2_hash_projection(
        cast(dict[str, object], v2_document)
    )
    checks = [
        _pass(
            "v1-byte-preservation",
            {
                "schema": v1_schema_fingerprint,
                "sample": v1_sample_fingerprint,
            },
        ),
        _pass(
            "v1-schema-sample-replay",
            {
                "problem_version": PLANNING_PROBLEM_VERSION,
                "builder_version": PROBLEM_BUILDER_VERSION,
                "hash_projection_version": PROBLEM_HASH_PROJECTION_VERSION,
                "problem_hash": v1_problem.problem_hash,
                "canonical_bytes_sha256": sha256(v1_bytes).hexdigest(),
                "canonical_bytes_size": len(v1_bytes),
                "projection_version": v1_projection[
                    "problem_hash_projection_version"
                ],
            },
        ),
        _pass(
            "v2-schema-sample-replay",
            {
                "schema": _fingerprint(v2_schema_path),
                "sample": _fingerprint(v2_sample_path),
                "problem_version": PLANNING_PROBLEM_VERSION_V2,
                "builder_version": PROBLEM_BUILDER_VERSION_V2,
                "hash_projection_version": PROBLEM_HASH_PROJECTION_VERSION_V2,
                "problem_hash": v2_problem.problem_hash,
                "canonical_bytes_sha256": sha256(v2_bytes).hexdigest(),
                "canonical_bytes_size": len(v2_bytes),
                "projection_version": v2_projection[
                    "problem_hash_projection_version"
                ],
            },
        ),
        _pass(
            "v2-gap-closure-fields",
            {
                "delivery_demand_count": len(v2_document["delivery_demands"]),
                "resource_count": len(v2_document["resources"]),
                "historical_anchor_count": len(
                    v2_document["historical_completion_anchors"]
                ),
                "hard_lock_count": sum(
                    lock["lock_type"] == "HARD_LOCK"
                    for lock in v2_document["operation_locks"]
                ),
                "soft_lock_count": sum(
                    lock["lock_type"] == "SOFT_LOCK"
                    for lock in v2_document["operation_locks"]
                ),
            },
        ),
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
            "v1_default_api": "PRESERVED",
            "v2_api": "OPT_IN",
            "solver": "NOT_IMPLEMENTED_BY_TASK",
            "validator": "NOT_IMPLEMENTED_BY_TASK",
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
