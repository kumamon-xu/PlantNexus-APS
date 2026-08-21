"""TASK-P2-09 formula-free mutations of Solver-produced candidates."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from app.planning.validation import validate_problem_schedule
from app.simulation.scenarios.p2_correctness import (
    CONSTRAINT_IDS,
    CorrectnessCase,
    CorrectnessReplay,
    execute_correctness_case,
    load_correctness_cases,
    materialize_constraint_mutation,
)

ROOT = Path(__file__).resolve().parents[3]
MUTATION_SOURCES = {
    "C-001": "P2-GOLDEN-JSSP",
    "C-002": "P2-GOLDEN-JSSP",
    "C-003": "P2-GOLDEN-JSSP",
    "C-004": "P2-GOLDEN-FJSP",
    "C-005": "P2-CALENDAR",
    "C-006": "P2-MATERIAL-DELAY",
    "C-007": "P2-RUNNING",
    "C-008": "P2-HARD-LOCK",
    "C-009": "P2-CROSS-WORKSHOP",
    "C-010": "P2-GOLDEN-FJSP",
    "C-011": "P2-MATERIAL-DELAY",
}


@lru_cache(maxsize=1)
def _cases() -> dict[str, CorrectnessCase]:
    return {case.scenario_id: case for case in load_correctness_cases(ROOT)}


@lru_cache(maxsize=7)
def _replay(scenario_id: str) -> CorrectnessReplay:
    return execute_correctness_case(_cases()[scenario_id], root=ROOT)


@pytest.mark.parametrize("constraint_id", CONSTRAINT_IDS)
def test_solver_candidate_mutation_fails_exactly_one_declared_constraint(
    constraint_id: str,
) -> None:
    replay = _replay(MUTATION_SOURCES[constraint_id])
    assert replay.validation_report["status"] == "PASS"
    problem, solution = materialize_constraint_mutation(replay, constraint_id)

    first = validate_problem_schedule(problem, solution)
    second = validate_problem_schedule(problem, solution)
    observed = tuple(
        cast(str, violation["constraint_id"])
        for violation in cast(list[dict[str, Any]], first["violations"])
    )

    assert first == second
    assert first["status"] == "FAIL"
    assert first["hard_violation_count"] == 1
    assert observed == (constraint_id,)

    schema = json.loads(
        (ROOT / "schemas/json/validation-report.v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(first)


def test_mutation_catalog_is_a_bijection_over_c001_through_c011() -> None:
    assert tuple(MUTATION_SOURCES) == CONSTRAINT_IDS
    assert set(MUTATION_SOURCES.values()).issubset(_cases())
