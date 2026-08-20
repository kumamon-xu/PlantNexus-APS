"""Formal PlanningProblem v2 / PlanningSolution validator evidence."""

from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
import pytest

from app.planning.contracts import validate_planning_solution
from app.planning.validation.problem_schedule_validator import (
    FORMAL_RULE_METADATA,
    ProblemScheduleValidationInputError,
    ProblemScheduleValidator,
    validate_problem_schedule,
    validation_error_from_problem_report,
)
from app.planning.validation.problem_validator_check import (
    formal_validation_vector,
    materialize_formal_mutation,
    run_formal_validator_checks,
)


ROOT = Path(__file__).resolve().parents[3]
type JsonObject = dict[str, Any]

FORMAL_MUTATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("missing_operation", ("C-001",)),
    ("duplicate_operation", ("C-001", "C-003")),
    ("wrong_resource", ("C-003",)),
    ("machine_overlap", ("C-004",)),
    ("calendar_overlap", ("C-005",)),
    ("material_early", ("C-006",)),
    ("completed_rescheduled", ("C-007",)),
    ("running_moved", ("C-007",)),
    ("hard_lock_moved", ("C-008",)),
    ("precedence_lag", ("C-002",)),
    ("cross_workshop_lag", ("C-009",)),
    ("wrong_duration", ("C-010",)),
    ("horizon_overflow", ("C-011",)),
)


def _load_json(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(JsonObject, value)


def test_formal_positive_candidate_passes_both_entry_points_and_schemas() -> None:
    problem, candidate = formal_validation_vector()
    validate_planning_solution(candidate)

    report = validate_problem_schedule(problem, candidate)
    replay = ProblemScheduleValidator().validate(problem, candidate)

    assert report == replay
    assert report == {
        "validation_report_version": "validation-report.v2",
        "problem_hash": problem["problem_hash"],
        "status": "PASS",
        "hard_violation_count": 0,
        "violations": [],
    }
    assert validation_error_from_problem_report(report) is None
    Draft202012Validator(
        _load_json(ROOT / "schemas/json/validation-report.v2.schema.json")
    ).validate(report)


def test_declared_solve_outcome_is_not_a_validation_input() -> None:
    problem, candidate = formal_validation_vector()
    expected = validate_problem_schedule(problem, candidate)
    contradictory = deepcopy(candidate)
    contradictory["solver_status"] = "FAILED"
    contradictory.pop("planning_run_outcome")
    contradictory.pop("objective_stage_results")
    contradictory.pop("diagnostics")

    assert validate_problem_schedule(problem, contradictory) == expected


@pytest.mark.parametrize(("mutation_class", "expected"), FORMAL_MUTATIONS)
def test_declarative_formal_mutations_fail_exact_constraints(
    mutation_class: str, expected: tuple[str, ...]
) -> None:
    problem, candidate = formal_validation_vector()
    changed_problem, changed_candidate = materialize_formal_mutation(
        problem, candidate, mutation_class
    )

    first = validate_problem_schedule(changed_problem, changed_candidate)
    second = validate_problem_schedule(changed_problem, changed_candidate)
    observed = tuple(
        str(violation["constraint_id"]) for violation in first["violations"]
    )

    assert first == second
    assert first["status"] == "FAIL"
    assert observed == expected
    assert first["hard_violation_count"] == len(expected)
    error = validation_error_from_problem_report(first)
    assert error is not None
    assert error["category"] == "VALIDATION_FAILED"
    assert error["code"] == "SCHEDULE_VALIDATION_FAILED"
    assert len(error["details"]) == len(expected)
    Draft202012Validator(
        _load_json(ROOT / "schemas/json/validation-report.v2.schema.json")
    ).validate(first)
    Draft202012Validator(
        _load_json(ROOT / "schemas/json/error.v2.schema.json")
    ).validate(error)


def test_malformed_candidate_and_wrong_problem_reference_fail_stably() -> None:
    problem, candidate = formal_validation_vector()
    malformed = deepcopy(candidate)
    malformed["assignments"] = "not-an-array"
    report = validate_problem_schedule(problem, malformed)
    assert report["status"] == "FAIL"
    assert tuple(violation["constraint_id"] for violation in report["violations"]) == (
        "C-001",
        "C-001",
        "C-001",
        "C-001",
        "C-001",
        "C-001",
        "C-007",
        "C-008",
    )

    wrong_reference = deepcopy(candidate)
    cast(JsonObject, wrong_reference["problem"])["problem_hash"] = "sha256:" + "f" * 64
    reference_report = validate_problem_schedule(problem, wrong_reference)
    assert reference_report["status"] == "FAIL"
    assert tuple(
        violation["constraint_id"] for violation in reference_report["violations"]
    ) == ("C-001",)
    assert (
        cast(JsonObject, reference_report["violations"][0]["observed_value"])["reason"]
        == "candidate references a different PlanningProblem"
    )


def test_invalid_authoritative_problem_is_rejected_before_candidate_rules() -> None:
    problem, candidate = formal_validation_vector()
    problem["problem_hash"] = "sha256:" + "0" * 64

    with pytest.raises(
        ProblemScheduleValidationInputError,
        match="authoritative Problem hash does not match its facts",
    ):
        validate_problem_schedule(problem, candidate)


def test_running_remainder_overrides_full_option_duration_without_losing_c010() -> None:
    problem, candidate = formal_validation_vector()
    operation = next(
        value
        for value in cast(list[JsonObject], problem["operation_instances"])
        if value["operation_id"] == "OP-C"
    )
    option = cast(list[JsonObject], operation["resource_options"])[0]

    assert option["final_duration_seconds"] == 600
    assert operation["remaining_seconds"] == 120
    assert validate_problem_schedule(problem, candidate)["status"] == "PASS"


def test_formal_rule_metadata_and_source_boundary_are_independent() -> None:
    assert tuple(FORMAL_RULE_METADATA) == tuple(
        f"C-{number:03d}" for number in range(1, 12)
    )
    source_path = ROOT / "backend/app/planning/validation/problem_schedule_validator.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        module
        for node in ast.walk(tree)
        for module in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
            if isinstance(node, ast.ImportFrom) and node.module
            else []
        )
    }
    assert not any(module.startswith("app.planning.backends") for module in imports)
    assert not any(module.startswith("ortools") for module in imports)
    assert "app.planning.validation.schedule_validator" not in imports
    assert "app.planning.validation.mutation_check" not in imports
    assert "solver_status" not in source
    assert "expected-outcomes" not in source


def test_formal_validator_machine_report_is_complete() -> None:
    report = run_formal_validator_checks(ROOT)

    assert report["report_version"] == "formal-schedule-validator-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-04"
    assert report["check_count"] == 6
    assert cast(JsonObject, report["counts"]) == {
        "positive_cases": 1,
        "mutation_cases": 13,
        "constraints_covered": 11,
        "required_mutation_classes": 13,
        "hard_violations": 14,
        "property_examples": 6,
    }
    assert {check["name"] for check in cast(list[JsonObject], report["checks"])} == {
        "fixed-contract-and-fixture-fingerprints",
        "formal-positive-and-status-independence",
        "c001-c011-declarative-mutations",
        "report-error-schema-and-determinism",
        "duration-and-ordering-properties",
        "independent-source-boundary",
    }
    boundaries = cast(JsonObject, report["boundaries"])
    assert boundaries["backend_constraint_reuse"] == "NONE"
    assert boundaries["solver_status_trusted"] is False
    assert boundaries["p0_fixture_and_mutation_bytes"] == "PRESERVED"
