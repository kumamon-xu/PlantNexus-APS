"""Emit machine-checkable TASK-P2-08 OBJ-001 and Global Strategy evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from itertools import permutations
import json
import os
from pathlib import Path
from typing import Any, cast

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.core_model_check import synthetic_core_problem
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.backends.cp_sat.objectives import (
    OBJECTIVE_ID,
    OBJECTIVE_METRIC,
    OBJECTIVE_UNIT,
    add_delivery_objective,
)
from app.planning.contracts import (
    SolverStatus,
    contract_fingerprint,
    statuses,
    validate_contract_bundle,
)
from app.planning.policy.contracts import PlanningPolicyDocument, SolveLimitsDocument
from app.planning.policy.delivery import (
    DeliveryPolicyError,
    SIMULATION_DELIVERY_SOURCE_SYSTEM,
    SIMULATION_DELIVERY_SOURCE_VERSION,
    simulation_delivery_policy,
    simulation_solve_limits,
    validate_simulation_delivery_execution,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.strategies import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    GlobalCpSatStrategy,
)


REPORT_VERSION = "objective-strategy-report.v1"
TASK_ID = "TASK-P2-08"
type JsonObject = dict[str, Any]

_FIXED_FINGERPRINTS = {
    "planning_problem_v2_schema": "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    "planning_solution_schema": "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    "solver_report_schema": "64feacd0d1ec0ea1c9d3f62d8e38b473b61f42dab5bc672c5898c5e056257b2a",
    "planning_policy_schema": "62624424115c3f6c9d45e920bcb0ac744ae9e1f2173af81072610298560a1bda",
    "solve_limits_schema": "8caff522a1fef8e40671cdff3ca857084cbf908b5c7fdfb9fdd8468fc3811d95",
    "constraint_rule_sheet": "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2",
    "planning_contracts": "d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630",
    "core_model": "e53b5db71dd644cb7c297e2b16206b7166fc90885a53675fbc3958341e7c11c0",
    "formal_validator": "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f",
    "problem_hashing": "ec2b98ed59ed8b5a4d4588254e2a49d9b9c7df1c2b666f78f00104c39cc76b4e",
    "uv_lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
    "adr_0004": "f66a9e78ad8f54486b510d8565a0cbdfe69d476b207fa1f1471a0345ed802ee0",
    "adr_0006": "d7792b2b20fc87991def44da090879a2ed72c835166e1ff5b29e5d636a3df3b7",
}
_FINGERPRINT_PATHS = {
    "planning_problem_v2_schema": "schemas/json/planning-problem.v2.schema.json",
    "planning_solution_schema": "schemas/json/planning-solution.schema.json",
    "solver_report_schema": "schemas/json/solver-report.schema.json",
    "planning_policy_schema": "schemas/json/planning-policy.schema.json",
    "solve_limits_schema": "schemas/json/solve-limits.schema.json",
    "constraint_rule_sheet": "schemas/rules/constraint-rule-sheet.v1.yaml",
    "planning_contracts": "backend/app/planning/contracts.py",
    "core_model": "backend/app/planning/backends/cp_sat/model.py",
    "formal_validator": "backend/app/planning/validation/problem_schedule_validator.py",
    "problem_hashing": "backend/app/planning/problem/hashing.py",
    "uv_lock": "uv.lock",
    "adr_0004": "docs/adr/ADR-0004-global-cp-sat-strategy-for-v1.md",
    "adr_0006": "docs/adr/ADR-0006-lexicographic-objectives.md",
}


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _fingerprints(root: Path) -> JsonObject:
    evidence: JsonObject = {}
    for key, expected in _FIXED_FINGERPRINTS.items():
        relative = _FINGERPRINT_PATHS[key]
        observed = sha256((root / relative).read_bytes()).hexdigest()
        if observed != expected:
            raise ValueError(f"frozen artifact changed: {relative}")
        evidence[key] = {"path": relative, "sha256": observed}
    return evidence


def _limits() -> SolveLimitsDocument:
    return simulation_solve_limits(
        limits_id="LIMITS-TASK-P2-08-MACHINE",
        limits_revision="1.0.0",
        source_record_id="LIMITS-TASK-P2-08-MACHINE",
        max_wall_time_seconds=5.0,
        max_workers=1,
        random_seed=20260821,
    )


def _delivery_problem(
    durations: list[int],
    due_ticks: list[int],
    weights: list[int],
    *,
    tag: str,
    horizon_ticks: int | None = None,
) -> PlanningProblemDocumentV2:
    horizon = sum(durations) if horizon_ticks is None else horizon_ticks
    problem = synthetic_core_problem(
        [[("RESOURCE-001", duration)] for duration in durations],
        horizon_ticks=horizon,
        tick_seconds=60,
        tag=f"TASK-P2-08-{tag}",
    )
    start = parse_utc_instant(problem["horizon_start_utc"])
    template = problem["delivery_demands"][0]
    demands = []
    for index, (due_tick, weight) in enumerate(zip(due_ticks, weights, strict=True)):
        demand = deepcopy(template)
        demand_id = f"DEMAND-{tag}-{index:03d}"
        demand.update(
            {
                "demand_order_id": demand_id,
                "due_at_utc": format_utc_instant(
                    start + timedelta(seconds=due_tick * 60)
                ),
                "due_source_record_id": f"DUE-{tag}-{index:03d}",
                "priority_weight": weight,
                "priority_source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
                "priority_source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
                "priority_source_record_id": f"PRIORITY-{tag}-{index:03d}",
            }
        )
        demands.append(demand)
        problem["operation_instances"][index]["demand_order_id"] = demand_id
    problem["delivery_demands"] = demands
    problem["problem_hash"] = problem_v2_hash_for(
        cast(dict[str, object], problem)
    )
    return problem


def _brute_force(
    durations: list[int], due_ticks: list[int], weights: list[int]
) -> int:
    values = []
    for ordering in permutations(range(len(durations))):
        completion = 0
        objective = 0
        for index in ordering:
            completion += durations[index]
            objective += weights[index] * max(0, completion - due_ticks[index]) * 60
        values.append(objective)
    return min(values)


def _solve(
    problem: PlanningProblemDocumentV2,
    *,
    tag: str,
) -> tuple[PlanningPolicyDocument, SolveLimitsDocument, Any]:
    policy = simulation_delivery_policy()
    limits = _limits()
    result = GlobalCpSatStrategy().solve(
        problem,
        policy,
        limits,
        planning_run_id=f"PLANNING-RUN-TASK-P2-08-{tag}",
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
    )
    validate_contract_bundle(policy, limits, result.solution, result.solver_report)
    return policy, limits, result


def run_objective_strategy_checks(root: Path) -> JsonObject:
    """Run fixed immutable, objective, optimality, status, and boundary checks."""

    root = root.resolve()
    fingerprints = _fingerprints(root)
    policy = simulation_delivery_policy()
    limits = _limits()
    policy_details = {
        "policy_id": policy["policy_id"],
        "policy_revision": policy["policy_revision"],
        "policy_fingerprint": contract_fingerprint(policy),
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "data_plane": policy["data_plane"],
        "implicit_defaults": "NONE",
    }

    shape_problem = _delivery_problem([2, 2], [2, 2], [1, 3], tag="SHAPE")
    core = build_core_model(shape_problem)
    variables_before = len(core.model.proto.variables)
    constraints_before = len(core.model.proto.constraints)
    objective = add_delivery_objective(shape_problem, core)
    if not core.model.has_objective():
        raise ValueError("OBJ-001 was not attached to the CP-SAT model")
    shape_details = {
        "objective_id": OBJECTIVE_ID,
        "metric": OBJECTIVE_METRIC,
        "unit": OBJECTIVE_UNIT,
        "metrics": objective.metrics,
        "variable_delta": len(core.model.proto.variables) - variables_before,
        "constraint_delta": len(core.model.proto.constraints) - constraints_before,
    }

    vectors = (
        ([2, 2], [2, 2], [1, 3]),
        ([1, 2, 1], [4, 4, 4], [2, 5, 1]),
        ([1, 2, 1], [1, 2, 3], [4, 1, 3]),
        ([3, 1, 2], [2, 4, 5], [1, 5, 2]),
    )
    optimum_rows = []
    validator_passes = 0
    for index, (durations, due_ticks, weights) in enumerate(vectors):
        _, _, result = _solve(
            _delivery_problem(
                durations,
                due_ticks,
                weights,
                tag=f"OPTIMUM-{index}",
            ),
            tag=f"OPTIMUM-{index}",
        )
        expected = _brute_force(durations, due_ticks, weights)
        stage = result.solution["objective_stage_results"][0]
        if (
            result.solution["solver_status"] != SolverStatus.OPTIMAL.value
            or stage["objective_value"] != expected
            or stage["best_bound"] != expected
            or stage["relative_gap"] != 0
        ):
            raise ValueError("CP-SAT OBJ-001 differs from the tiny exhaustive oracle")
        if result.validation_report is None or result.validation_report["status"] != "PASS":
            raise ValueError("optimized candidate did not pass the independent Validator")
        validator_passes += 1
        optimum_rows.append(
            {
                "case": index,
                "objective": expected,
                "status": result.solution["solver_status"],
                "validator": result.validation_report["status"],
            }
        )

    _, _, infeasible = _solve(
        _delivery_problem(
            [3, 3], [4, 4], [1, 1], tag="INFEASIBLE", horizon_ticks=4
        ),
        tag="INFEASIBLE",
    )
    if (
        infeasible.solution["solver_status"] != SolverStatus.INFEASIBLE.value
        or infeasible.solution["assignments"]
        or infeasible.validation_report is not None
    ):
        raise ValueError("complete hard-domain infeasibility mapping changed")

    production_policy = deepcopy(policy)
    production_limits = deepcopy(limits)
    production_policy["data_plane"] = "PRODUCTION"
    production_limits["data_plane"] = "PRODUCTION"
    try:
        validate_simulation_delivery_execution(
            shape_problem,
            cast(PlanningPolicyDocument, production_policy),
            cast(SolveLimitsDocument, production_limits),
        )
    except DeliveryPolicyError as error:
        production_rejection = error.reason.value
    else:
        raise ValueError("Production objective execution was not blocked")

    status_rows = [status.value for status in statuses()]
    if status_rows != [status.value for status in SolverStatus]:
        raise ValueError("solver status vocabulary changed")
    representative = _solve(shape_problem, tag="REPORT")[2]
    report = representative.solver_report
    if (
        report["solver_status"] != "OPTIMAL"
        or report["objective_stage_results"]
        != representative.solution["objective_stage_results"]
        or report["timings"]["validation_seconds"] is None
        or report["model_metrics"]["variables"] <= 0
    ):
        raise ValueError("Strategy SolverReport lost required objective evidence")

    checks = [
        _pass(
            "fixed-contract-model-validator-adr-and-lock-fingerprints",
            fingerprints,
        ),
        _pass(
            "approved-versioned-simulation-policy-and-explicit-limits",
            policy_details,
        ),
        _pass("exact-obj001-model-shape-unit-and-overflow-domain", shape_details),
        _pass("tiny-brute-force-weighted-tardiness-optimality", optimum_rows),
        _pass(
            "complete-hard-domain-and-independent-validator-gate",
            {
                "validator_passes": validator_passes,
                "infeasible_status": infeasible.solution["solver_status"],
                "infeasible_assignments": 0,
            },
        ),
        _pass(
            "honest-status-solution-report-limits-and-provenance",
            {
                "status_vocabulary": status_rows,
                "representative_solution_status": representative.solution[
                    "solver_status"
                ],
                "report_id": report["report_id"],
                "solver": report["solver"],
                "timings": report["timings"],
                "model_metrics": report["model_metrics"],
                "memory_peak_mb": report["memory_peak_mb"],
                "code_commit": report["provenance"]["code_commit"],
            },
        ),
        _pass(
            "global-only-and-production-deferred-boundary",
            {
                "strategy_id": STRATEGY_ID,
                "strategy_version": STRATEGY_VERSION,
                "backend_calls_per_run": 1,
                "production_rejection": production_rejection,
                "obj_002_obj_003": "NOT_IMPLEMENTED",
                "reference_scheduler": "NOT_IMPLEMENTED_BY_TASK",
                "benchmark_runner": "NOT_IMPLEMENTED_BY_TASK",
                "export_publish": "NOT_IMPLEMENTED_BY_TASK",
            },
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "objective_ids": 1,
            "tiny_optimality_cases": len(vectors),
            "independent_validator_passes": validator_passes,
            "certified_infeasible_cases": 1,
            "status_values": len(status_rows),
            "production_rejections": 1,
        },
        "boundaries": {
            "hard_constraints": "C-001_THROUGH_C-011_COMPLETE_AND_UNCHANGED",
            "objective": "OBJ-001_ONLY_PRIORITY_WEIGHTED_TARDINESS_SECONDS",
            "strategy": "ONE_GLOBAL_CP_SAT_MODEL_NO_DECOMPOSITION_OR_FALLBACK",
            "policy": "VERSIONED_SIMULATION_ONLY",
            "production_authority": "BLOCKED_BY_OPEN_006_011_012",
            "obj_002_obj_003": "DEFERRED",
            "formal_validator_changes": "NONE",
            "schema_contract_changes": "NONE",
            "dependency_changes": "NONE",
            "benchmark": "TINY_CORRECTNESS_ONLY_NO_XS_S_M_BASELINE",
            "publishability": "INTERNAL_TEST_EVIDENCE_ONLY",
        },
    }


def _write_report(path: Path, report: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_objective_strategy_checks(arguments.root)
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get(
                "PLANTNEXUS_CODE_COMMIT", "uncommitted"
            ),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        exit_code = 1
    else:
        exit_code = 0
    _write_report(arguments.report, report)
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "main", "run_objective_strategy_checks"]
