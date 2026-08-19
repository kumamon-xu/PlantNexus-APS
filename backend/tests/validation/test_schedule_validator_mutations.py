"""Independent evidence for TASK-P0-07 fixture-local validation rules."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator

from app.planning.validation.mutation_check import (
    CONSTRAINT_IDS,
    materialize_case,
    run_mutation_checks,
)
from app.planning.validation.schedule_validator import (
    RULE_METADATA,
    ValidationInputError,
    fixture_problem_hash,
    validate_fixture_schedule,
    validation_error_from_report,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN_ROOT = ROOT / "fixtures" / "deterministic" / "SIM-MINIMAL-001"
MUTATION_ROOT = ROOT / "fixtures" / "infeasible" / "SIM-MINIMAL-001-MUTATIONS"
SCHEMA_ROOT = ROOT / "schemas" / "json"
RULE_SHEET_PATH = ROOT / "schemas" / "rules" / "constraint-rule-sheet.v1.yaml"

type JsonObject = dict[str, Any]

EXPECTED_CONSTRAINTS: dict[str, tuple[str, ...]] = {
    "MUT-C001-MISSING-OPERATION": ("C-001",),
    "MUT-C001-DUPLICATE-OPERATION": ("C-001", "C-003", "C-004"),
    "MUT-C003-WRONG-RESOURCE": ("C-003",),
    "MUT-C004-MACHINE-OVERLAP": ("C-004",),
    "MUT-C005-CALENDAR-OVERLAP": ("C-005",),
    "MUT-C006-MATERIAL-EARLY": ("C-006",),
    "MUT-C007-COMPLETED-RESCHEDULED": ("C-007",),
    "MUT-C007-RUNNING-MOVED": ("C-007",),
    "MUT-C008-HARD-LOCK-MOVED": ("C-008",),
    "MUT-C002-MAX-LAG": ("C-002",),
    "MUT-C009-TRANSPORT-LAG": ("C-009",),
    "MUT-C010-WRONG-DURATION": ("C-010",),
    "MUT-C011-HORIZON-OVERFLOW": ("C-011",),
}


def load_json(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(JsonObject, value)


def base_documents() -> tuple[JsonObject, JsonObject]:
    return (
        load_json(GOLDEN_ROOT / "import-package.json"),
        load_json(GOLDEN_ROOT / "golden-schedule.json"),
    )


def mutation_cases() -> dict[str, JsonObject]:
    suite = load_json(MUTATION_ROOT / "mutation-suite.json")
    cases = cast(list[JsonObject], suite["cases"])
    return {str(case["case_id"]): case for case in cases}


def expected_cases() -> dict[str, JsonObject]:
    outcomes = load_json(MUTATION_ROOT / "expected-outcomes.json")
    cases = cast(list[JsonObject], outcomes["cases"])
    return {str(case["case_id"]): case for case in cases}


def materialized_report(case_id: str) -> JsonObject:
    package, schedule = base_documents()
    mutated_package, mutated_schedule = materialize_case(
        package, schedule, mutation_cases()[case_id]
    )
    return cast(JsonObject, validate_fixture_schedule(mutated_package, mutated_schedule))


def test_positive_golden_passes_without_expected_outcome_as_input() -> None:
    package, schedule = base_documents()
    report = validate_fixture_schedule(package, schedule)

    assert report == {
        "validation_report_version": "validation-report.v2",
        "problem_hash": (
            "fixture-problem:sha256:"
            "fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10"
        ),
        "status": "PASS",
        "hard_violation_count": 0,
        "violations": [],
    }
    assert fixture_problem_hash(package) == report["problem_hash"]
    assert validation_error_from_report(report) is None

    source = (
        ROOT / "backend" / "app" / "planning" / "validation" / "schedule_validator.py"
    ).read_text(encoding="utf-8")
    assert "expected-outcomes" not in source
    assert "mutation-suite" not in source
    assert "yaml" not in source


@pytest.mark.parametrize("case_id", tuple(EXPECTED_CONSTRAINTS))
def test_each_mutation_fails_exact_constraints_and_committed_outcome(
    case_id: str,
) -> None:
    report = materialized_report(case_id)
    expected = expected_cases()[case_id]
    constraint_ids = tuple(
        str(value["constraint_id"])
        for value in cast(list[JsonObject], report["violations"])
    )

    assert report["status"] == "FAIL"
    assert constraint_ids == EXPECTED_CONSTRAINTS[case_id]
    assert report["hard_violation_count"] == len(EXPECTED_CONSTRAINTS[case_id])
    assert report == expected["validation_report"]
    assert validation_error_from_report(
        cast(Any, report)
    ) == expected["error"]

    report_schema = load_json(SCHEMA_ROOT / "validation-report.v2.schema.json")
    error_schema = load_json(SCHEMA_ROOT / "error.v2.schema.json")
    Draft202012Validator(report_schema).validate(report)
    Draft202012Validator(error_schema).validate(expected["error"])


def test_manual_mutation_observations_match_rule_arithmetic() -> None:
    max_lag = cast(
        list[JsonObject], materialized_report("MUT-C002-MAX-LAG")["violations"]
    )[0]
    assert max_lag["observed_value"] == {
        "predecessor_end_tick": 6,
        "successor_start_tick": 9,
        "lag_seconds": 2700,
        "min_lag_seconds": 0,
        "max_lag_seconds": 1800,
    }

    calendar = cast(
        list[JsonObject],
        materialized_report("MUT-C005-CALENDAR-OVERLAP")["violations"],
    )[0]
    assert calendar["observed_value"] == {
        "assignment_start_utc": "2026-08-20T09:45:00Z",
        "assignment_end_utc": "2026-08-20T10:45:00Z",
        "unavailable_start_utc": "2026-08-20T09:00:00Z",
        "unavailable_end_utc": "2026-08-20T10:00:00Z",
    }

    running = cast(
        list[JsonObject], materialized_report("MUT-C007-RUNNING-MOVED")["violations"]
    )[0]
    running_observed = cast(JsonObject, running["observed_value"])
    assert running_observed["remaining_seconds"] == 5400
    assert running_observed["expected_end_tick"] == 6

    transport = cast(
        list[JsonObject], materialized_report("MUT-C009-TRANSPORT-LAG")["violations"]
    )[0]
    transport_observed = cast(JsonObject, transport["observed_value"])
    assert transport_observed["transport_seconds_observed"] == 1800
    assert transport_observed["transport_lag_seconds"] == 2700

    duration = cast(
        list[JsonObject], materialized_report("MUT-C010-WRONG-DURATION")["violations"]
    )[0]
    assert duration["observed_value"] == {
        "resource_id": "RES-HEAT-001",
        "interval_ticks": 5,
        "duration_seconds": 3600,
        "expected_duration_ticks": 4,
    }

    horizon = cast(
        list[JsonObject], materialized_report("MUT-C011-HORIZON-OVERFLOW")["violations"]
    )[0]
    assert horizon["observed_value"] == {
        "start_tick": 8,
        "end_tick": 12,
        "horizon_start_tick": 0,
        "horizon_end_tick": 11,
    }


def test_mutation_materializer_is_formula_free_and_does_not_modify_golden() -> None:
    package, schedule = base_documents()
    package_before = copy.deepcopy(package)
    schedule_before = copy.deepcopy(schedule)
    materialize_case(
        package,
        schedule,
        mutation_cases()["MUT-C004-MACHINE-OVERLAP"],
    )
    assert package == package_before
    assert schedule == schedule_before

    materializer_source = (
        ROOT / "backend" / "app" / "planning" / "validation" / "mutation_check.py"
    ).read_text(encoding="utf-8")
    apply_body = materializer_source.split("def _apply_operation", 1)[1].split(
        "def materialize_case", 1
    )[0]
    assert "constraint_id" not in apply_body
    assert "RULE_METADATA" not in apply_body
    assert "duration_to_ticks" not in apply_body


def test_rule_metadata_coverage_and_machine_check_are_complete() -> None:
    rule_sheet = cast(
        JsonObject, yaml.safe_load(RULE_SHEET_PATH.read_text(encoding="utf-8"))
    )
    rules = cast(list[JsonObject], rule_sheet["active_rules"])
    metadata = {
        str(rule["constraint_id"]): (
            str(cast(JsonObject, rule["violation"])["expected_rule"]),
            str(cast(JsonObject, rule["violation"])["message"]),
        )
        for rule in rules
    }
    assert metadata == RULE_METADATA
    assert tuple(metadata) == CONSTRAINT_IDS
    assert set().union(*map(set, EXPECTED_CONSTRAINTS.values())) == set(CONSTRAINT_IDS)

    report = run_mutation_checks(ROOT)
    assert report["result"] == "PASS"
    assert report["counts"] == {
        "cases": 13,
        "constraints_covered": 11,
        "required_mutation_classes": 13,
        "hard_violations": 15,
    }
    assert report["issues"] == []


def test_validation_boundary_rejects_mismatched_envelope_and_solver_imports() -> None:
    package, schedule = base_documents()
    mismatched = copy.deepcopy(schedule)
    mismatched["horizon_end_utc"] = "2026-08-20T10:45:00Z"
    with pytest.raises(ValidationInputError, match="candidate horizon differs"):
        validate_fixture_schedule(package, mismatched)

    validation_root = ROOT / "backend" / "app" / "planning" / "validation"
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(validation_root.glob("*.py"))
    )
    assert "from app.planning.backends" not in combined
    assert "import app.planning.backends" not in combined
    assert "from ortools" not in combined
    assert "import ortools" not in combined
    assert "cpmodel" not in combined
    assert "intervalvar" not in combined
