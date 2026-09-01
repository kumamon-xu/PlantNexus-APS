"""Authority and formal-Validator mutations for TASK-P6-07."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

from app.duration_prediction.planning_ingress import (
    evaluate_planning_authority_invariants,
)

from backend.tests.p6_planning_integration_support import (
    build_integration_problem,
    integration_inputs,
    provider_for_tests,
)


ROOT = Path(__file__).resolve().parents[3]


def _routing(document: dict[str, Any]) -> None:
    document["operation_instances"][0]["resource_options"] = []


def _resource(document: dict[str, Any]) -> None:
    document["resources"][0]["capabilities"].append("P6-MUTATION")


def _constraint(document: dict[str, Any]) -> None:
    document["operation_instances"][0]["release_at_utc"] = (
        "2026-08-20T00:01:00Z"
    )


def _state(document: dict[str, Any]) -> None:
    document["operation_instances"][0]["status"] = "RUNNING"


def _weight(document: dict[str, Any]) -> None:
    document["delivery_demands"][0]["priority_weight"] += 1


def _identity(document: dict[str, Any]) -> None:
    document["snapshot_id"] = "planning-snapshot-v2-tampered"


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        ("routing", _routing),
        ("resource_compatibility", _resource),
        ("hard_constraints", _constraint),
        ("operation_state", _state),
        ("business_weights", _weight),
        ("problem_identity", _identity),
    ],
)
def test_independent_invariant_comparator_rejects_authority_mutations(
    field: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    snapshot, _, features = integration_inputs()
    result = build_integration_problem(
        snapshot,
        provider=provider_for_tests(),
        feature_records=features,
    )
    selected = dict(deepcopy(result.problem.document))
    mutate(selected)

    invariants = evaluate_planning_authority_invariants(
        result.standard_problem.document, selected
    )

    assert invariants.as_document()[field] is False
    assert not invariants.all_passed


def test_planning_ingress_module_has_no_solver_validator_state_or_io_dependency() -> None:
    source_path = (
        ROOT / "backend/app/duration_prediction/planning_ingress.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    forbidden = (
        "app.api",
        "app.application",
        "app.infrastructure",
        "app.planning.backends",
        "app.planning.validation",
        "sqlalchemy",
        "ortools",
    )
    assert not any(
        module == prefix or module.startswith(prefix + ".")
        for module in imports
        for prefix in forbidden
    )
