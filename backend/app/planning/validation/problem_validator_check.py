"""Emit machine-checkable TASK-P2-04 formal validator evidence."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any, cast

from jsonschema import Draft202012Validator
import yaml

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.contracts import validate_planning_solution
from app.planning.problem.hashing import (
    problem_v2_hash_for,
    validate_built_problem_v2,
)
from app.planning.validation.problem_schedule_validator import (
    FORMAL_RULE_METADATA,
    validate_problem_schedule,
    validation_error_from_problem_report,
)


REPORT_VERSION = "formal-schedule-validator-report.v1"
TASK_ID = "TASK-P2-04"
CONSTRAINT_IDS = tuple(f"C-{number:03d}" for number in range(1, 12))

_FIXED_FINGERPRINTS = {
    "fixtures/deterministic/SIM-MINIMAL-001/import-package.json": (
        "6299921cb58866fba8c66a7f8c6adfb47c3de50122d49fde4c20014e7bf0c112"
    ),
    "fixtures/deterministic/SIM-MINIMAL-001/golden-schedule.json": (
        "44885e64f477167e08f3146e02546d43780ce5c0fa5db26d82b8b268a2005d5a"
    ),
    "fixtures/deterministic/SIM-MINIMAL-001/expected-validation.json": (
        "28ecb8cf41fd376f04e916e3c3bea6a026ecb393202257fce8eff2a38a012f9b"
    ),
    "fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/mutation-suite.json": (
        "27914614496f2784f9d3a339a58814b2c0344b864592569b33949e8e22f8c51a"
    ),
    "fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/expected-outcomes.json": (
        "d3a9a16236c39aed55badd0aff46e85d48d78fc5d01be9ffd7c7af8c55069086"
    ),
    "fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/coverage-matrix.json": (
        "a00138aeb672bd18f06d413a84a9e65193536ff4a6767a29df8f0fc52fc46327"
    ),
    "schemas/json/planning-problem.v2.schema.json": (
        "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8"
    ),
    "schemas/json/planning-solution.schema.json": (
        "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4"
    ),
    "schemas/json/validation-report.v2.schema.json": (
        "1da63e931e7ddd90134eb652c857f13eb862787de855165cd230c2d8071fd353"
    ),
    "schemas/rules/constraint-rule-sheet.v1.yaml": (
        "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2"
    ),
    "backend/app/planning/validation/schedule_validator.py": (
        "2b7369d97ca6ac758c05e006041579dafb8c0accf5f4417e33fca3c646be8cd2"
    ),
    "backend/app/planning/validation/mutation_check.py": (
        "9843bbdd692358830430581d324606e3c3ca860a040f0c3e730ebcd7066ba7dd"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}

type JsonObject = dict[str, Any]


def _resource(resource_id: str, workshop_id: str) -> JsonObject:
    return {
        "resource_id": resource_id,
        "resource_code": resource_id,
        "resource_type": "MACHINE",
        "status": "AVAILABLE",
        "factory_id": "FACTORY-001",
        "workshop_id": workshop_id,
        "production_line_id": f"LINE-{workshop_id}",
        "resource_group_id": f"GROUP-{workshop_id}",
        "calendar_id": f"CALENDAR-{resource_id}",
        "capabilities": ["PROCESSING"],
        "capacity": 1,
    }


def _option(resource_id: str, duration_seconds: int) -> JsonObject:
    return {
        "resource_id": resource_id,
        "setup_seconds": 0,
        "cycle_seconds_per_unit": duration_seconds,
        "final_duration_seconds": duration_seconds,
        "duration_source": "task-p2-04-explicit-vector",
        "source_version": "1.0.0",
    }


def _operation(
    operation_id: str,
    resource_id: str,
    duration_seconds: int,
    *,
    status: str = "NOT_STARTED",
) -> JsonObject:
    operation: JsonObject = {
        "operation_id": operation_id,
        "demand_order_id": "DEMAND-VALIDATOR-001",
        "status": status,
        "release_at_utc": "2026-08-20T00:00:00Z",
        "material_ready_at_utc": "2026-08-20T00:00:00Z",
        "required_capabilities": ["PROCESSING"],
        "resource_options": [_option(resource_id, duration_seconds)],
    }
    if status == "RUNNING":
        operation.update(
            {
                "actual_start_at_utc": "2026-08-19T23:50:00Z",
                "assigned_resource_id": resource_id,
                "remaining_seconds": 120,
            }
        )
    return operation


def _base_problem() -> JsonObject:
    problem: JsonObject = {
        "problem_version": "planning-problem.v2",
        "schema_set_version": "2.3.0",
        "snapshot_id": "SNAPSHOT-TASK-P2-04-001",
        "problem_builder_version": "planning-problem-builder.v2",
        "problem_hash": "",
        "canonicalization_version": "canonical-json.v1",
        "problem_hash_projection_version": "planning-problem-hash-projection.v2",
        "tick_seconds": 60,
        "horizon_start_utc": "2026-08-20T00:00:00Z",
        "horizon_end_utc": "2026-08-20T06:00:00Z",
        "delivery_demands": [
            {
                "demand_order_id": "DEMAND-VALIDATOR-001",
                "due_at_utc": "2026-08-20T06:00:00Z",
                "due_source_system": "task-p2-04-vector",
                "due_source_version": "1.0.0",
                "due_source_record_id": "DUE-001",
                "priority_weight": 1,
                "priority_source_system": "task-p2-04-vector",
                "priority_source_version": "1.0.0",
                "priority_source_record_id": "PRIORITY-001",
            }
        ],
        "resources": [
            _resource("RESOURCE-A", "WORKSHOP-A"),
            _resource("RESOURCE-B", "WORKSHOP-B"),
            _resource("RESOURCE-C", "WORKSHOP-C"),
            _resource("RESOURCE-H", "WORKSHOP-A"),
        ],
        "operation_instances": [
            _operation("OP-A", "RESOURCE-A", 120),
            _operation("OP-B", "RESOURCE-A", 180),
            _operation("OP-C", "RESOURCE-C", 600, status="RUNNING"),
            _operation("OP-D", "RESOURCE-B", 120),
            _operation("OP-E", "RESOURCE-A", 60),
        ],
        "historical_completion_anchors": [
            {
                "operation_id": "OP-H",
                "execution_fact_id": "FACT-H",
                "resource_id": "RESOURCE-H",
                "actual_start_at_utc": "2026-08-19T23:50:00Z",
                "actual_end_at_utc": "2026-08-19T23:59:00Z",
                "source_system": "task-p2-04-vector",
                "source_version": "1.0.0",
                "source_record_id": "HISTORY-001",
            }
        ],
        "precedence_edges": [
            {
                "precedence_edge_id": "EDGE-A-B",
                "predecessor_operation_id": "OP-A",
                "successor_operation_id": "OP-B",
                "min_lag_seconds": 0,
                "max_lag_seconds": 60,
                "transport_lag_seconds": 0,
            },
            {
                "precedence_edge_id": "EDGE-H-D",
                "predecessor_operation_id": "OP-H",
                "successor_operation_id": "OP-D",
                "min_lag_seconds": 0,
                "max_lag_seconds": 120,
                "transport_lag_seconds": 60,
            },
        ],
        "operation_locks": [
            {
                "lock_id": "LOCK-A",
                "operation_id": "OP-A",
                "lock_type": "HARD_LOCK",
                "resource_id": "RESOURCE-A",
                "start_at_utc": "2026-08-20T00:00:00Z",
                "end_at_utc": "2026-08-20T00:02:00Z",
                "source_system": "task-p2-04-vector",
                "source_version": "1.0.0",
                "source_record_id": "LOCK-SOURCE-A",
            },
            {
                "lock_id": "LOCK-E",
                "operation_id": "OP-E",
                "lock_type": "SOFT_LOCK",
                "resource_id": "RESOURCE-A",
                "start_at_utc": "2026-08-20T00:06:00Z",
                "end_at_utc": "2026-08-20T00:07:00Z",
                "source_system": "task-p2-04-vector",
                "source_version": "1.0.0",
                "source_record_id": "LOCK-SOURCE-E",
            },
        ],
        "resource_unavailable_intervals": [
            {
                "calendar_id": "CALENDAR-RESOURCE-A",
                "resource_id": "RESOURCE-A",
                "start_utc": "2026-08-20T00:05:00Z",
                "end_utc": "2026-08-20T00:06:00Z",
            }
        ],
        "required_capabilities": [
            "DAG_ROUTING",
            "HARD_SOFT_LOCK",
            "MACHINE_CALENDAR",
            "RELEASE_AND_MATERIAL_GATE",
            "RUNNING_OPERATION",
            "SINGLE_FACTORY_MULTI_WORKSHOP",
        ],
    }
    problem["problem_hash"] = problem_v2_hash_for(problem)
    validate_built_problem_v2(problem)
    return problem


def _assignment(
    operation_id: str,
    resource_id: str,
    start_tick: int,
    end_tick: int,
    duration_seconds: int,
    *,
    lock_ids: list[str] | None = None,
) -> JsonObject:
    horizon_start = parse_utc_instant("2026-08-20T00:00:00Z")
    return {
        "operation_id": operation_id,
        "resource_id": resource_id,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "duration_ticks": end_tick - start_tick,
        "start_at_utc": format_utc_instant(
            horizon_start + timedelta(seconds=start_tick * 60)
        ),
        "end_at_utc": format_utc_instant(
            horizon_start + timedelta(seconds=end_tick * 60)
        ),
        "duration_seconds": duration_seconds,
        "lock_ids": sorted(lock_ids or []),
        "execution_fact_ids": [],
    }


def _problem_reference(problem: JsonObject) -> JsonObject:
    fields = (
        "problem_version",
        "problem_builder_version",
        "problem_hash_projection_version",
        "problem_hash",
        "snapshot_id",
        "tick_seconds",
        "horizon_start_utc",
        "horizon_end_utc",
    )
    return {field: problem[field] for field in fields}


def _base_candidate(problem: JsonObject) -> JsonObject:
    candidate: JsonObject = {
        "planning_solution_version": "planning-solution.v1",
        "schema_set_version": "2.4.0",
        "solution_id": "SOLUTION-SAMPLE-TASK-P2-04-001",
        "evidence_kind": "CONTRACT_SAMPLE",
        "canonicalization_version": "canonical-json.v1",
        "problem": _problem_reference(problem),
        "policy": {
            "planning_policy_version": "planning-policy.v1",
            "policy_id": "POLICY-TASK-P2-04-001",
            "policy_revision": "1.0.0",
            "policy_fingerprint": "sha256:" + "0" * 64,
        },
        "limits": {
            "solve_limits_version": "solve-limits.v1",
            "limits_id": "LIMITS-TASK-P2-04-001",
            "limits_revision": "1.0.0",
            "limits_fingerprint": "sha256:" + "1" * 64,
            "max_wall_time_seconds": 1,
            "max_workers": 1,
            "random_seed": 20260820,
        },
        "solver_status": "FEASIBLE",
        "planning_run_outcome": {"state": "SOLVED", "product_error": None},
        "assignments": [
            _assignment("OP-A", "RESOURCE-A", 0, 2, 120, lock_ids=["LOCK-A"]),
            _assignment("OP-B", "RESOURCE-A", 2, 5, 180),
            _assignment("OP-C", "RESOURCE-C", 0, 2, 120),
            _assignment("OP-D", "RESOURCE-B", 0, 2, 120),
            _assignment("OP-E", "RESOURCE-A", 6, 7, 60, lock_ids=["LOCK-E"]),
        ],
        "objective_stage_results": [
            {
                "stage_index": 1,
                "objective_id": "OBJ-001",
                "metric": "WEIGHTED_TARDINESS",
                "sense": "MINIMIZE",
                "status": "FEASIBLE",
                "objective_value": 0,
                "best_bound": 0,
                "relative_gap": 0.0,
                "allocated_wall_time_seconds": 1,
                "solve_seconds": 0,
                "stop_reason": "CONTRACT_SAMPLE_NO_SOLVER",
            }
        ],
        "diagnostics": [],
    }
    validate_planning_solution(candidate)
    return candidate


def formal_validation_vector() -> tuple[JsonObject, JsonObject]:
    """Return a fresh, valid synthetic Problem/Solution correctness vector."""

    problem = _base_problem()
    return problem, _base_candidate(problem)


def _assignment_for(candidate: JsonObject, operation_id: str) -> JsonObject:
    values = [
        cast(JsonObject, value)
        for value in cast(list[JsonObject], candidate["assignments"])
        if value["operation_id"] == operation_id
    ]
    if len(values) != 1:
        raise ValueError(f"expected one assignment for {operation_id}")
    return values[0]


def _operation_for(problem: JsonObject, operation_id: str) -> JsonObject:
    values = [
        cast(JsonObject, value)
        for value in cast(list[JsonObject], problem["operation_instances"])
        if value["operation_id"] == operation_id
    ]
    if len(values) != 1:
        raise ValueError(f"expected one operation for {operation_id}")
    return values[0]


def _edge_for(problem: JsonObject, edge_id: str) -> JsonObject:
    values = [
        cast(JsonObject, value)
        for value in cast(list[JsonObject], problem["precedence_edges"])
        if value["precedence_edge_id"] == edge_id
    ]
    if len(values) != 1:
        raise ValueError(f"expected one edge for {edge_id}")
    return values[0]


def _refresh_identity(problem: JsonObject, candidate: JsonObject) -> None:
    problem["problem_hash"] = problem_v2_hash_for(problem)
    candidate["problem"] = _problem_reference(problem)
    validate_built_problem_v2(problem)


def _set_interval(
    assignment: JsonObject,
    *,
    start_tick: int,
    end_tick: int,
    duration_seconds: int,
) -> None:
    replacement = _assignment(
        str(assignment["operation_id"]),
        str(assignment["resource_id"]),
        start_tick,
        end_tick,
        duration_seconds,
        lock_ids=cast(list[str], assignment["lock_ids"]),
    )
    assignment.update(replacement)


_CASES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("FORMAL-MUT-C001-MISSING", "missing_operation", ("C-001",)),
    (
        "FORMAL-MUT-C001-DUPLICATE",
        "duplicate_operation",
        ("C-001", "C-003"),
    ),
    ("FORMAL-MUT-C003-WRONG-RESOURCE", "wrong_resource", ("C-003",)),
    ("FORMAL-MUT-C004-OVERLAP", "machine_overlap", ("C-004",)),
    ("FORMAL-MUT-C005-CALENDAR", "calendar_overlap", ("C-005",)),
    ("FORMAL-MUT-C006-MATERIAL", "material_early", ("C-006",)),
    ("FORMAL-MUT-C007-COMPLETED", "completed_rescheduled", ("C-007",)),
    ("FORMAL-MUT-C007-RUNNING", "running_moved", ("C-007",)),
    ("FORMAL-MUT-C008-LOCK", "hard_lock_moved", ("C-008",)),
    ("FORMAL-MUT-C002-MAX-LAG", "precedence_lag", ("C-002",)),
    ("FORMAL-MUT-C009-TRANSPORT", "cross_workshop_lag", ("C-009",)),
    ("FORMAL-MUT-C010-DURATION", "wrong_duration", ("C-010",)),
    ("FORMAL-MUT-C011-HORIZON", "horizon_overflow", ("C-011",)),
)


def materialize_formal_mutation(
    problem: JsonObject, candidate: JsonObject, mutation_class: str
) -> tuple[JsonObject, JsonObject]:
    """Apply one explicit mutation without consulting evaluator metadata."""

    changed_problem = deepcopy(problem)
    changed_candidate = deepcopy(candidate)
    assignments = cast(list[JsonObject], changed_candidate["assignments"])
    if mutation_class == "missing_operation":
        changed_candidate["assignments"] = [
            value for value in assignments if value["operation_id"] != "OP-E"
        ]
    elif mutation_class == "duplicate_operation":
        assignments.append(_assignment("OP-E", "RESOURCE-A", 8, 9, 60))
    elif mutation_class == "wrong_resource":
        _assignment_for(changed_candidate, "OP-E")["resource_id"] = "RESOURCE-UNKNOWN"
    elif mutation_class == "machine_overlap":
        _set_interval(
            _assignment_for(changed_candidate, "OP-E"),
            start_tick=4,
            end_tick=5,
            duration_seconds=60,
        )
    elif mutation_class == "calendar_overlap":
        _set_interval(
            _assignment_for(changed_candidate, "OP-E"),
            start_tick=5,
            end_tick=6,
            duration_seconds=60,
        )
    elif mutation_class == "material_early":
        _operation_for(changed_problem, "OP-E")["material_ready_at_utc"] = (
            "2026-08-20T00:07:00Z"
        )
        _refresh_identity(changed_problem, changed_candidate)
    elif mutation_class == "completed_rescheduled":
        assignments.append(_assignment("OP-H", "RESOURCE-H", 8, 9, 60))
    elif mutation_class == "running_moved":
        _set_interval(
            _assignment_for(changed_candidate, "OP-C"),
            start_tick=1,
            end_tick=3,
            duration_seconds=120,
        )
    elif mutation_class == "hard_lock_moved":
        cast(list[JsonObject], changed_problem["operation_locks"])[0]["end_at_utc"] = (
            "2026-08-20T00:03:00Z"
        )
        _refresh_identity(changed_problem, changed_candidate)
    elif mutation_class == "precedence_lag":
        _edge_for(changed_problem, "EDGE-A-B")["min_lag_seconds"] = 60
        _refresh_identity(changed_problem, changed_candidate)
    elif mutation_class == "cross_workshop_lag":
        _edge_for(changed_problem, "EDGE-H-D")["transport_lag_seconds"] = 120
        _refresh_identity(changed_problem, changed_candidate)
    elif mutation_class == "wrong_duration":
        _set_interval(
            _assignment_for(changed_candidate, "OP-E"),
            start_tick=6,
            end_tick=8,
            duration_seconds=120,
        )
    elif mutation_class == "horizon_overflow":
        _set_interval(
            _assignment_for(changed_candidate, "OP-E"),
            start_tick=360,
            end_tick=361,
            duration_seconds=60,
        )
    else:
        raise ValueError(f"unsupported formal mutation class {mutation_class}")
    assignments = cast(list[JsonObject], changed_candidate["assignments"])
    assignments.sort(key=lambda value: (str(value.get("operation_id")), str(value)))
    return changed_problem, changed_candidate


def _fingerprint_evidence(root: Path) -> dict[str, object]:
    evidence: dict[str, object] = {}
    for relative, expected in _FIXED_FINGERPRINTS.items():
        path = root / relative
        content = path.read_bytes()
        observed = sha256(content).hexdigest()
        if observed != expected:
            raise ValueError(f"immutable validator input changed: {relative}")
        evidence[relative] = {"sha256": observed, "size_bytes": len(content)}
    return evidence


def _rule_metadata_evidence(root: Path) -> dict[str, object]:
    sheet = cast(
        JsonObject,
        yaml.safe_load(
            (root / "schemas/rules/constraint-rule-sheet.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    rules = cast(list[JsonObject], sheet["active_rules"])
    metadata = {
        str(rule["constraint_id"]): (
            str(cast(JsonObject, rule["violation"])["expected_rule"]),
            str(cast(JsonObject, rule["violation"])["message"]),
        )
        for rule in rules
    }
    if metadata != FORMAL_RULE_METADATA or tuple(metadata) != CONSTRAINT_IDS:
        raise ValueError("formal rule metadata differs from the rule sheet")
    return {
        "rule_sheet_version": sheet["rule_sheet_version"],
        "constraints": list(metadata),
    }


def _schema_validators(root: Path) -> tuple[Draft202012Validator, Draft202012Validator]:
    report_schema = cast(
        JsonObject,
        json.loads(
            (root / "schemas/json/validation-report.v2.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    error_schema = cast(
        JsonObject,
        json.loads(
            (root / "schemas/json/error.v2.schema.json").read_text(encoding="utf-8")
        ),
    )
    Draft202012Validator.check_schema(report_schema)
    Draft202012Validator.check_schema(error_schema)
    return Draft202012Validator(report_schema), Draft202012Validator(error_schema)


def _mutation_evidence(root: Path) -> tuple[list[JsonObject], int]:
    problem, candidate = formal_validation_vector()
    report_validator, error_validator = _schema_validators(root)
    evidence: list[JsonObject] = []
    hard_violations = 0
    covered: set[str] = set()
    for case_id, mutation_class, expected_constraints in _CASES:
        changed_problem, changed_candidate = materialize_formal_mutation(
            problem, candidate, mutation_class
        )
        first = validate_problem_schedule(changed_problem, changed_candidate)
        second = validate_problem_schedule(changed_problem, changed_candidate)
        if first != second:
            raise ValueError(f"formal mutation is not deterministic: {case_id}")
        observed = tuple(
            str(violation["constraint_id"]) for violation in first["violations"]
        )
        if first["status"] != "FAIL" or observed != expected_constraints:
            raise ValueError(
                f"formal mutation {case_id} expected {expected_constraints}, got {observed}"
            )
        error = validation_error_from_problem_report(first)
        if error is None:
            raise ValueError(f"formal mutation has no Error v2 mapping: {case_id}")
        report_validator.validate(first)
        error_validator.validate(error)
        hard_violations += first["hard_violation_count"]
        covered.update(observed)
        evidence.append(
            {
                "case_id": case_id,
                "mutation_class": mutation_class,
                "status": first["status"],
                "constraint_ids": list(observed),
                "hard_violation_count": first["hard_violation_count"],
            }
        )
    if covered != set(CONSTRAINT_IDS):
        raise ValueError("formal mutation set does not cover C-001 through C-011")
    return evidence, hard_violations


def _property_evidence() -> list[JsonObject]:
    explicit_ceiling_examples = ((1, 1), (59, 1), (60, 1), (61, 2), (119, 2), (120, 2))
    evidence: list[JsonObject] = []
    for seconds, expected_ticks in explicit_ceiling_examples:
        problem, candidate = formal_validation_vector()
        option = cast(
            JsonObject,
            cast(list[JsonObject], _operation_for(problem, "OP-E")["resource_options"])[
                0
            ],
        )
        option["cycle_seconds_per_unit"] = seconds
        option["final_duration_seconds"] = seconds
        assignment = _assignment_for(candidate, "OP-E")
        _set_interval(
            assignment,
            start_tick=6,
            end_tick=6 + expected_ticks,
            duration_seconds=seconds,
        )
        _refresh_identity(problem, candidate)
        report = validate_problem_schedule(problem, candidate)
        if report["status"] != "PASS":
            raise ValueError(f"explicit duration property failed for {seconds} seconds")
        reversed_problem = deepcopy(problem)
        reversed_candidate = deepcopy(candidate)
        for collection in (
            "resources",
            "operation_instances",
            "precedence_edges",
            "operation_locks",
        ):
            cast(list[object], reversed_problem[collection]).reverse()
        cast(list[object], reversed_candidate["assignments"]).reverse()
        if validate_problem_schedule(reversed_problem, reversed_candidate) != report:
            raise ValueError("collection ordering changed formal validation output")
        evidence.append(
            {
                "duration_seconds": seconds,
                "duration_ticks": expected_ticks,
                "status": report["status"],
                "reordered_replay": "IDENTICAL",
            }
        )
    return evidence


def _independence_evidence(root: Path) -> dict[str, object]:
    path = root / "backend/app/planning/validation/problem_schedule_validator.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.as_posix())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden_prefixes = (
        "app.planning.backends",
        "ortools",
        "app.planning.validation.schedule_validator",
        "app.planning.validation.mutation_check",
    )
    forbidden_imports = sorted(
        module
        for module in imports
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in forbidden_prefixes
        )
    )
    forbidden_tokens = sorted(
        token for token in ("expected-outcomes", "solver_status") if token in source
    )
    if forbidden_imports or forbidden_tokens:
        raise ValueError(
            "formal validator independence boundary failed: "
            f"imports={forbidden_imports} tokens={forbidden_tokens}"
        )
    return {
        "source_path": path.relative_to(root).as_posix(),
        "source_sha256": sha256(source.encode("utf-8")).hexdigest(),
        "imports": sorted(imports),
        "forbidden_imports": [],
        "forbidden_decision_tokens": [],
    }


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def run_formal_validator_checks(root: Path) -> JsonObject:
    """Run fixed, mutation, schema, property, and independence evidence."""

    root = root.resolve()
    problem, candidate = formal_validation_vector()
    positive = validate_problem_schedule(problem, candidate)
    replay = validate_problem_schedule(problem, candidate)
    if positive != replay or positive["status"] != "PASS":
        raise ValueError("formal positive vector is not a deterministic PASS")
    status_changed = deepcopy(candidate)
    status_changed["solver_status"] = "FAILED"
    status_changed.pop("planning_run_outcome")
    status_changed.pop("objective_stage_results")
    if validate_problem_schedule(problem, status_changed) != positive:
        raise ValueError("declared solve outcome influenced schedule validation")

    report_validator, _ = _schema_validators(root)
    report_validator.validate(positive)
    if validation_error_from_problem_report(positive) is not None:
        raise ValueError("positive formal report unexpectedly mapped to an error")

    mutations, hard_violations = _mutation_evidence(root)
    properties = _property_evidence()
    fixed = _fingerprint_evidence(root)
    rules = _rule_metadata_evidence(root)
    independence = _independence_evidence(root)
    checks = [
        _pass("fixed-contract-and-fixture-fingerprints", fixed),
        _pass(
            "formal-positive-and-status-independence",
            {
                "problem_hash": problem["problem_hash"],
                "solution_id": candidate["solution_id"],
                "status": positive["status"],
                "hard_violation_count": positive["hard_violation_count"],
                "declared_outcome_mutation": "IDENTICAL_REPORT",
                "solver_executed": False,
            },
        ),
        _pass(
            "c001-c011-declarative-mutations",
            {"rules": rules, "cases": mutations},
        ),
        _pass(
            "report-error-schema-and-determinism",
            {
                "validation_report_contract": "validation-report.v2",
                "error_contract": "error.v2",
                "positive_replay": "IDENTICAL",
                "negative_replays": len(mutations),
            },
        ),
        _pass("duration-and-ordering-properties", properties),
        _pass("independent-source-boundary", independence),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "check_count": len(checks),
        "counts": {
            "positive_cases": 1,
            "mutation_cases": len(mutations),
            "constraints_covered": len(CONSTRAINT_IDS),
            "required_mutation_classes": len(_CASES),
            "hard_violations": hard_violations,
            "property_examples": len(properties),
        },
        "checks": checks,
        "boundaries": {
            "backend_constraint_reuse": "NONE",
            "solver_status_trusted": False,
            "expected_artifact_decision_input": "NONE",
            "p0_fixture_and_mutation_bytes": "PRESERVED",
            "problem_solution_schema_changes": "NONE",
            "dependency_changes": "NONE",
            "cp_sat_business_model": "NOT_MODIFIED_BY_TASK",
            "objective": "NOT_IMPLEMENTED_BY_TASK",
            "benchmark": "NOT_APPLICABLE_CORRECTNESS_ONLY",
            "production_readiness": "NOT_CLAIMED",
        },
    }


def _write_report(path: Path, report: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    root = cast(Path, args.root)
    report_path = cast(Path | None, args.report)
    try:
        report = run_formal_validator_checks(root)
    except Exception as error:  # CLI boundary emits sanitized failure evidence
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "error_type": type(error).__name__,
        }
        if report_path is not None:
            _write_report(report_path, report)
        print(
            f"FAIL formal schedule validator: {type(error).__name__}", file=sys.stderr
        )
        return 1
    if report_path is not None:
        _write_report(report_path, report)
    counts = cast(JsonObject, report["counts"])
    print(
        "PASS formal schedule validator: "
        f"checks={report['check_count']} mutations={counts['mutation_cases']} "
        f"constraints={counts['constraints_covered']} "
        f"properties={counts['property_examples']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONSTRAINT_IDS",
    "REPORT_VERSION",
    "formal_validation_vector",
    "main",
    "materialize_formal_mutation",
    "run_formal_validator_checks",
]
