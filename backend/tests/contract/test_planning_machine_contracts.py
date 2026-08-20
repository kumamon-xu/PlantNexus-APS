"""TASK-P2-02: solver-neutral planning-machine contract evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from app.planning.contracts import (
    PlanningContractError,
    SolverStatus,
    canonical_contract_bytes,
    contract_fingerprint,
    outcome_document_for_status,
    outcome_for_solver_status,
    statuses,
    validate_contract_bundle,
    validate_planning_solution,
    validate_solver_report,
)
from app.planning.policy.contracts import (
    validate_planning_policy,
    validate_solve_limits,
)


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
SAMPLE_ROOT = ROOT / "schemas" / "samples"
SCHEMA_FILES = (
    "planning-policy.schema.json",
    "solve-limits.schema.json",
    "planning-solution.schema.json",
    "solver-report.schema.json",
)
SAMPLE_PAIRS = (
    ("planning-policy.schema.json", "planning-policy.v1.synthetic.json"),
    ("solve-limits.schema.json", "solve-limits.v1.synthetic.json"),
    ("planning-solution.schema.json", "planning-solution.v1.synthetic.json"),
    ("solver-report.schema.json", "solver-report.v1.synthetic.json"),
)
EXPECTED_SAMPLE_FINGERPRINTS = {
    "planning-policy.v1.synthetic.json": (
        "sha256:32a46b97989910c7ab9b0b6f1fbfff2cdb958492d329fb4c71b06f0c7e38de7a"
    ),
    "solve-limits.v1.synthetic.json": (
        "sha256:76091493ee0b96a761c9df6e9881d03d9b8cca1c4b09103602661dcbf5d4a27b"
    ),
    "planning-solution.v1.synthetic.json": (
        "sha256:4713507110b47c8f61d16149580abe393a75bf9237f92e09ec81b5ac6ff336f5"
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def schema_validator(name: str) -> Draft202012Validator:
    registry = Registry()
    for filename in SCHEMA_FILES:
        schema = load_json(SCHEMA_ROOT / filename)
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema)
        )
    return Draft202012Validator(
        load_json(SCHEMA_ROOT / name),
        registry=registry,
        format_checker=FormatChecker(),
    )


def sample_bundle() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    return (
        load_json(SAMPLE_ROOT / "planning-policy.v1.synthetic.json"),
        load_json(SAMPLE_ROOT / "solve-limits.v1.synthetic.json"),
        load_json(SAMPLE_ROOT / "planning-solution.v1.synthetic.json"),
        load_json(SAMPLE_ROOT / "solver-report.v1.synthetic.json"),
    )


def walk_json(value: Any):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def candidate_solution(status: SolverStatus) -> dict[str, Any]:
    solution = load_json(SAMPLE_ROOT / "planning-solution.v1.synthetic.json")
    solution["evidence_kind"] = "SOLVER_RUN"
    solution["solver_status"] = status.value
    solution["planning_run_outcome"] = outcome_document_for_status(status)
    solution["diagnostics"] = []
    solution["assignments"] = [
        {
            "operation_id": "OPERATION-001",
            "resource_id": "RESOURCE-001",
            "start_tick": 0,
            "end_tick": 5,
            "duration_ticks": 5,
            "start_at_utc": "2026-08-20T00:00:00Z",
            "end_at_utc": "2026-08-20T00:05:00Z",
            "duration_seconds": 260,
            "lock_ids": [],
            "execution_fact_ids": [],
        }
    ]
    stage = cast(dict[str, Any], solution["objective_stage_results"][0])
    stage.update(
        {
            "status": status.value,
            "objective_value": 10,
            "best_bound": 10 if status is SolverStatus.OPTIMAL else 8,
            "relative_gap": 0 if status is SolverStatus.OPTIMAL else 0.2,
            "solve_seconds": 2,
            "stop_reason": status.value,
        }
    )
    return solution


def non_candidate_solution(status: SolverStatus) -> dict[str, Any]:
    solution = load_json(SAMPLE_ROOT / "planning-solution.v1.synthetic.json")
    solution["solver_status"] = status.value
    solution["planning_run_outcome"] = outcome_document_for_status(status)
    stage = cast(dict[str, Any], solution["objective_stage_results"][0])
    stage.update(
        {
            "status": status.value,
            "objective_value": None,
            "best_bound": None,
            "relative_gap": None,
            "stop_reason": status.value,
        }
    )
    return solution


def report_for_solution(solution: dict[str, Any]) -> dict[str, Any]:
    report = load_json(SAMPLE_ROOT / "solver-report.v1.synthetic.json")
    for field in (
        "evidence_kind",
        "problem",
        "policy",
        "limits",
        "solver_status",
        "planning_run_outcome",
        "objective_stage_results",
        "diagnostics",
    ):
        report[field] = copy.deepcopy(solution[field])
    report["solution"] = {
        "planning_solution_version": solution["planning_solution_version"],
        "solution_id": solution["solution_id"],
        "solution_fingerprint": contract_fingerprint(solution),
        "solver_status": solution["solver_status"],
    }
    if outcome_for_solver_status(solution["solver_status"]).candidate_available:
        report["finished_at_utc"] = "2026-08-20T00:00:02Z"
        report["timings"] = {
            "model_build_seconds": 0,
            "first_feasible_seconds": 1,
            "solve_seconds": 2,
            "validation_seconds": None,
            "total_seconds": 2,
        }
        report["model_metrics"] = {
            "variables": 1,
            "constraints": 1,
            "optional_intervals": 1,
        }
        report["memory_peak_mb"] = 1
    return report


def test_four_schemas_and_samples_validate_with_offline_urn_registry() -> None:
    for filename in SCHEMA_FILES:
        schema = load_json(SCHEMA_ROOT / filename)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert all("default" not in node for node in walk_json(schema))

    for schema_name, sample_name in SAMPLE_PAIRS:
        sample = load_json(SAMPLE_ROOT / sample_name)
        schema_validator(schema_name).validate(sample)
        assert json.loads(canonical_contract_bytes(sample)) == sample


def test_published_samples_are_explicit_simulation_contract_evidence() -> None:
    policy, limits, solution, report = sample_bundle()
    assert policy["data_plane"] == limits["data_plane"] == "SIMULATION"
    assert solution["evidence_kind"] == report["evidence_kind"] == "CONTRACT_SAMPLE"
    assert solution["solver_status"] == report["solver_status"] == "UNKNOWN"
    assert solution["assignments"] == []
    assert report["solver"]["solver_name"] == "contract-sample-no-solver"
    assert report["solver"]["solver_version"] == "not-installed"
    assert report["model_metrics"] == {
        "variables": 0,
        "constraints": 0,
        "optional_intervals": 0,
    }
    validate_contract_bundle(policy, limits, solution, report)


def test_policy_and_limits_have_no_implicit_objective_or_budget() -> None:
    policy, limits, _, _ = sample_bundle()
    validate_planning_policy(policy)
    validate_solve_limits(limits)

    missing_objective = copy.deepcopy(policy)
    del missing_objective["objective_stages"]
    with pytest.raises(PlanningContractError, match="INVALID_SHAPE"):
        validate_planning_policy(missing_objective)

    stability_stage = copy.deepcopy(policy)
    stability_stage["objective_stages"][0]["objective_id"] = "OBJ-002"
    with pytest.raises(PlanningContractError, match="INVALID_REFERENCE"):
        validate_planning_policy(stability_stage)

    missing_limit = copy.deepcopy(limits)
    del missing_limit["max_wall_time_seconds"]
    with pytest.raises(PlanningContractError, match="INVALID_SHAPE"):
        validate_solve_limits(missing_limit)

    boolean_limit = copy.deepcopy(limits)
    boolean_limit["max_workers"] = True
    with pytest.raises(PlanningContractError, match="INVALID_METRIC"):
        validate_solve_limits(boolean_limit)


def test_solver_status_vocabulary_and_product_mapping_are_total() -> None:
    expected = {
        "OPTIMAL": ("SOLVED", None, True),
        "FEASIBLE": ("SOLVED", None, True),
        "INFEASIBLE": ("INFEASIBLE", "INFEASIBLE", False),
        "UNKNOWN": (
            "NO_SOLUTION_WITHIN_LIMIT",
            "NO_SOLUTION_WITHIN_LIMIT",
            False,
        ),
        "MODEL_INVALID": ("MODEL_INVALID", "MODEL_INVALID", False),
        "CANCELLED": ("CANCELLED", None, False),
        "FAILED": ("FAILED", "SYSTEM_ERROR", False),
    }
    assert tuple(item.value for item in statuses()) == tuple(expected)
    for status in statuses():
        outcome = outcome_for_solver_status(status)
        state, category, candidate_available = expected[status.value]
        assert outcome.planning_run_state.value == state
        assert (
            None
            if outcome.product_error_category is None
            else outcome.product_error_category.value
        ) == category
        assert outcome.candidate_available is candidate_available
        document = outcome_document_for_status(status)
        assert document["state"] == state
        assert (
            None
            if document["product_error"] is None
            else document["product_error"]["category"]
        ) == category


@pytest.mark.parametrize("status", [SolverStatus.OPTIMAL, SolverStatus.FEASIBLE])
def test_candidate_solution_restores_ticks_utc_and_duration(
    status: SolverStatus,
) -> None:
    solution = candidate_solution(status)
    validate_planning_solution(solution)
    schema_validator("planning-solution.schema.json").validate(solution)


@pytest.mark.parametrize(
    "status",
    [
        SolverStatus.INFEASIBLE,
        SolverStatus.UNKNOWN,
        SolverStatus.MODEL_INVALID,
        SolverStatus.CANCELLED,
        SolverStatus.FAILED,
    ],
)
def test_non_candidate_statuses_cannot_carry_assignments(status: SolverStatus) -> None:
    solution = non_candidate_solution(status)
    validate_planning_solution(solution)
    schema_validator("planning-solution.schema.json").validate(solution)

    solution["assignments"] = candidate_solution(SolverStatus.FEASIBLE)["assignments"]
    with pytest.raises(PlanningContractError, match="INVALID_STATUS_COMBINATION"):
        validate_planning_solution(solution)


@pytest.mark.parametrize("status", list(SolverStatus))
def test_every_status_round_trips_through_solution_report_and_bundle(
    status: SolverStatus,
) -> None:
    if outcome_for_solver_status(status).candidate_available:
        solution = candidate_solution(status)
    else:
        solution = non_candidate_solution(status)
    report = report_for_solution(solution)
    policy, limits, _, _ = sample_bundle()

    validate_contract_bundle(policy, limits, solution, report)
    schema_validator("planning-solution.schema.json").validate(solution)
    schema_validator("solver-report.schema.json").validate(report)


def test_solution_rejects_false_status_and_time_evidence() -> None:
    optimal = candidate_solution(SolverStatus.OPTIMAL)
    optimal["objective_stage_results"][0]["best_bound"] = 9
    optimal["objective_stage_results"][0]["relative_gap"] = 0.1
    with pytest.raises(PlanningContractError, match="optimality fields"):
        validate_planning_solution(optimal)

    wrong_gap = candidate_solution(SolverStatus.FEASIBLE)
    wrong_gap["objective_stage_results"][0]["relative_gap"] = 0.3
    with pytest.raises(PlanningContractError, match="relative gap"):
        validate_planning_solution(wrong_gap)

    over_budget = candidate_solution(SolverStatus.FEASIBLE)
    over_budget["objective_stage_results"][0]["solve_seconds"] = 31
    with pytest.raises(PlanningContractError, match="explicit budget"):
        validate_planning_solution(over_budget)

    bad_time = candidate_solution(SolverStatus.FEASIBLE)
    bad_time["assignments"][0]["end_at_utc"] = "2026-08-20T00:06:00Z"
    with pytest.raises(PlanningContractError, match="UTC/tick projection"):
        validate_planning_solution(bad_time)

    bad_duration = candidate_solution(SolverStatus.FEASIBLE)
    bad_duration["assignments"][0]["duration_seconds"] = 301
    with pytest.raises(PlanningContractError, match="seconds and solver ticks"):
        validate_planning_solution(bad_duration)


def test_solver_report_rejects_limit_timing_and_provenance_drift() -> None:
    _, _, _, report = sample_bundle()
    validate_solver_report(report)

    wrong_limit = copy.deepcopy(report)
    wrong_limit["solver"]["parameters"][0]["value"] = 31
    with pytest.raises(PlanningContractError, match="explicit limit parameter"):
        validate_solver_report(wrong_limit)

    negative_timing = copy.deepcopy(report)
    negative_timing["timings"]["solve_seconds"] = -1
    with pytest.raises(PlanningContractError, match="INVALID_METRIC"):
        validate_solver_report(negative_timing)

    stage_timing_drift = copy.deepcopy(report)
    stage_timing_drift["timings"]["solve_seconds"] = 1
    stage_timing_drift["timings"]["total_seconds"] = 1
    with pytest.raises(PlanningContractError, match="objective-stage timing"):
        validate_solver_report(stage_timing_drift)

    missing_validation_total = copy.deepcopy(report)
    missing_validation_total["timings"]["validation_seconds"] = 1
    with pytest.raises(PlanningContractError, match="total timing"):
        validate_solver_report(missing_validation_total)

    wrong_commit = copy.deepcopy(report)
    wrong_commit["provenance"]["code_commit"] = "main"
    with pytest.raises(PlanningContractError, match="code commit"):
        validate_solver_report(wrong_commit)


def test_bundle_rejects_fingerprint_and_cross_document_drift() -> None:
    policy, limits, solution, report = sample_bundle()

    drifted_policy = copy.deepcopy(policy)
    drifted_policy["policy_revision"] = "1.0.1"
    with pytest.raises(PlanningContractError, match="policy reference"):
        validate_contract_bundle(drifted_policy, limits, solution, report)

    drifted_report = copy.deepcopy(report)
    drifted_report["solution"]["solution_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(PlanningContractError, match="solution reference"):
        validate_contract_bundle(policy, limits, solution, drifted_report)

    wrong_plane = copy.deepcopy(limits)
    wrong_plane["data_plane"] = "PRODUCTION"
    with pytest.raises(PlanningContractError, match="different data planes"):
        validate_contract_bundle(policy, wrong_plane, solution, report)

    wrong_evidence_kind = copy.deepcopy(report)
    wrong_evidence_kind["evidence_kind"] = "SOLVER_RUN"
    with pytest.raises(PlanningContractError, match="outcome evidence diverge"):
        validate_contract_bundle(
            policy, limits, solution, wrong_evidence_kind
        )


def test_canonical_fingerprints_are_key_order_independent_and_fixed() -> None:
    for filename, expected in EXPECTED_SAMPLE_FINGERPRINTS.items():
        document = load_json(SAMPLE_ROOT / filename)
        reversed_document = dict(reversed(tuple(document.items())))
        assert canonical_contract_bytes(document) == canonical_contract_bytes(
            reversed_document
        )
        assert contract_fingerprint(document) == expected


def test_machine_contract_scope_remains_solver_and_infrastructure_free() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8").lower()
    sources = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (
            ROOT / "backend" / "app" / "planning" / "contracts.py",
            ROOT / "backend" / "app" / "planning" / "policy" / "contracts.py",
        )
    )
    assert "ortools" not in pyproject
    assert 'name = "ortools"' not in lock
    for forbidden in (
        "cpmodel",
        "cp_model",
        "intervalvar",
        "from sqlalchemy",
        "from fastapi",
        "app.planning.backends",
        "app.planning.validation",
    ):
        assert forbidden not in sources


def test_json_schema_rejects_unknown_fields_and_wrong_status_mapping() -> None:
    _, _, solution, report = sample_bundle()
    solution["implicit_default"] = True
    with pytest.raises(ValidationError):
        schema_validator("planning-solution.schema.json").validate(solution)

    report["planning_run_outcome"]["state"] = "INFEASIBLE"
    with pytest.raises(ValidationError):
        schema_validator("solver-report.schema.json").validate(report)

    _, _, solution, report = sample_bundle()
    solution["planning_run_outcome"]["product_error"] = None
    with pytest.raises(ValidationError):
        schema_validator("planning-solution.schema.json").validate(solution)

    report["planning_run_outcome"]["product_error"] = None
    with pytest.raises(ValidationError):
        schema_validator("solver-report.schema.json").validate(report)
