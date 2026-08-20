"""Emit machine-checkable TASK-P2-05 core model correctness evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence, cast

from app.domain.types import format_utc_instant
from app.planning.backends.cp_sat.backend import CpSatBackend
from app.planning.backends.cp_sat.core_constraints import (
    CORE_CONSTRAINT_IDS,
    CoreModelInputError,
    CoreModelReason,
    precheck_core_problem,
)
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.policy.contracts import PlanningPolicyDocument, SolveLimitsDocument
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


REPORT_VERSION = "cp-sat-core-model-report.v1"
TASK_ID = "TASK-P2-05"
type JsonObject = dict[str, Any]
type OptionTicks = tuple[str, int]

_FIXED_FINGERPRINTS = {
    "planning_problem_v2_schema": "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    "planning_solution_schema": "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    "planning_policy_schema": "62624424115c3f6c9d45e920bcb0ac744ae9e1f2173af81072610298560a1bda",
    "solve_limits_schema": "8caff522a1fef8e40671cdff3ca857084cbf908b5c7fdfb9fdd8468fc3811d95",
    "constraint_rule_sheet": "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2",
    "formal_validator": "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f",
    "planning_contracts": "d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630",
    "uv_lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}
_FINGERPRINT_PATHS = {
    "planning_problem_v2_schema": "schemas/json/planning-problem.v2.schema.json",
    "planning_solution_schema": "schemas/json/planning-solution.schema.json",
    "planning_policy_schema": "schemas/json/planning-policy.schema.json",
    "solve_limits_schema": "schemas/json/solve-limits.schema.json",
    "constraint_rule_sheet": "schemas/rules/constraint-rule-sheet.v1.yaml",
    "formal_validator": "backend/app/planning/validation/problem_schedule_validator.py",
    "planning_contracts": "backend/app/planning/contracts.py",
    "uv_lock": "uv.lock",
}


def synthetic_core_problem(
    operation_options: Sequence[Sequence[OptionTicks]],
    *,
    horizon_ticks: int,
    tick_seconds: int = 60,
    tag: str = "CORE",
) -> PlanningProblemDocumentV2:
    """Build a versioned in-memory synthetic Problem for bounded core evidence."""

    horizon_start = datetime(2026, 8, 20, tzinfo=UTC)
    horizon_end = horizon_start + timedelta(seconds=horizon_ticks * tick_seconds)
    resource_ids = sorted(
        {resource_id for options in operation_options for resource_id, _ in options}
    )
    resources = [
        {
            "resource_id": resource_id,
            "resource_code": resource_id,
            "resource_type": "MACHINE",
            "status": "AVAILABLE",
            "factory_id": "FACTORY-CORE",
            "workshop_id": "WORKSHOP-CORE",
            "production_line_id": "LINE-CORE",
            "resource_group_id": "GROUP-CORE",
            "calendar_id": f"CAL-{resource_id}",
            "capabilities": ["CORE"],
            "capacity": 1,
        }
        for resource_id in resource_ids
    ]
    operations = []
    for operation_index, options in enumerate(operation_options):
        operations.append(
            {
                "operation_id": f"OP-{operation_index:03d}",
                "demand_order_id": "DEMAND-CORE",
                "status": "NOT_STARTED",
                "release_at_utc": format_utc_instant(horizon_start),
                "material_ready_at_utc": format_utc_instant(horizon_start),
                "required_capabilities": ["CORE"],
                "resource_options": [
                    {
                        "resource_id": resource_id,
                        "setup_seconds": 0,
                        "cycle_seconds_per_unit": duration_ticks * tick_seconds,
                        "final_duration_seconds": duration_ticks * tick_seconds,
                        "duration_source": "TASK-P2-05-SYNTHETIC-CORE",
                        "source_version": "1.0.0",
                    }
                    for resource_id, duration_ticks in options
                ],
            }
        )
    identity_payload = json.dumps(
        {
            "tag": tag,
            "horizon_ticks": horizon_ticks,
            "tick_seconds": tick_seconds,
            "operation_options": operation_options,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    snapshot_suffix = sha256(identity_payload).hexdigest()
    document = cast(
        PlanningProblemDocumentV2,
        {
            "problem_version": "planning-problem.v2",
            "schema_set_version": "2.3.0",
            "snapshot_id": f"snapshot-core-{snapshot_suffix}",
            "problem_builder_version": "planning-problem-builder.v2",
            "problem_hash": "sha256:" + "0" * 64,
            "canonicalization_version": "canonical-json.v1",
            "problem_hash_projection_version": "planning-problem-hash-projection.v2",
            "tick_seconds": tick_seconds,
            "horizon_start_utc": format_utc_instant(horizon_start),
            "horizon_end_utc": format_utc_instant(horizon_end),
            "delivery_demands": [
                {
                    "demand_order_id": "DEMAND-CORE",
                    "due_at_utc": format_utc_instant(horizon_end),
                    "due_source_system": "TASK-P2-05-SYNTHETIC-CORE",
                    "due_source_version": "1.0.0",
                    "due_source_record_id": f"DUE-{tag}",
                    "priority_weight": 1,
                    "priority_source_system": "TASK-P2-05-SYNTHETIC-CORE",
                    "priority_source_version": "1.0.0",
                    "priority_source_record_id": f"PRIORITY-{tag}",
                }
            ],
            "resources": resources,
            "operation_instances": operations,
            "historical_completion_anchors": [],
            "precedence_edges": [],
            "operation_locks": [],
            "resource_unavailable_intervals": [],
            "required_capabilities": (
                ["ALTERNATIVE_RESOURCE"]
                if any(len(options) > 1 for options in operation_options)
                else []
            ),
        },
    )
    document["problem_hash"] = problem_v2_hash_for(
        cast(dict[str, object], document)
    )
    return document


def synthetic_core_policy() -> PlanningPolicyDocument:
    return {
        "planning_policy_version": "planning-policy.v1",
        "schema_set_version": "2.4.0",
        "policy_id": "POLICY-TASK-P2-05-CORE",
        "policy_revision": "1.0.0",
        "data_plane": "SIMULATION",
        "policy_source": {
            "source_system": "TASK-P2-05-SYNTHETIC-CORE",
            "source_version": "1.0.0",
            "source_record_id": "POLICY-TASK-P2-05-CORE",
        },
        "canonicalization_version": "canonical-json.v1",
        "constraint_contract_version": "constraint-rule-sheet.v1",
        "objective_policy_version": "objective-policy.v1",
        "hard_constraint_ids": [f"C-{index:03d}" for index in range(1, 12)],
        "objective_stages": [
            {
                "stage_index": 1,
                "objective_id": "OBJ-001",
                "metric": "WEIGHTED_TARDINESS",
                "sense": "MINIMIZE",
            }
        ],
    }


def synthetic_core_limits() -> SolveLimitsDocument:
    return {
        "solve_limits_version": "solve-limits.v1",
        "schema_set_version": "2.4.0",
        "limits_id": "LIMITS-TASK-P2-05-CORE",
        "limits_revision": "1.0.0",
        "data_plane": "SIMULATION",
        "limits_source": {
            "source_system": "TASK-P2-05-SYNTHETIC-CORE",
            "source_version": "1.0.0",
            "source_record_id": "LIMITS-TASK-P2-05-CORE",
        },
        "canonicalization_version": "canonical-json.v1",
        "max_wall_time_seconds": 5.0,
        "max_workers": 1,
        "random_seed": 20260820,
    }


def brute_force_core_feasible(
    operation_options: Sequence[Sequence[OptionTicks]], horizon_ticks: int
) -> bool:
    """Independent tiny feasibility oracle: enumerate choices and unary loads."""

    if any(not options for options in operation_options):
        return False
    for choices in product(*operation_options):
        load_by_resource: dict[str, int] = {}
        for resource_id, duration_ticks in choices:
            load_by_resource[resource_id] = (
                load_by_resource.get(resource_id, 0) + duration_ticks
            )
        if all(load <= horizon_ticks for load in load_by_resource.values()):
            return True
    return not operation_options


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _fingerprints(root: Path) -> JsonObject:
    observed = {
        name: sha256((root / relative).read_bytes()).hexdigest()
        for name, relative in _FINGERPRINT_PATHS.items()
    }
    if observed != _FIXED_FINGERPRINTS:
        raise ValueError("A frozen P2-05 contract, validator, rule, or lock drifted")
    return observed


def _precheck_evidence() -> JsonObject:
    overflow = synthetic_core_problem(
        [[("RESOURCE-001", 7)]], horizon_ticks=6, tag="OVERFLOW"
    )
    try:
        precheck_core_problem(cast(dict[str, object], overflow))
    except CoreModelInputError as error:
        if error.reason is not CoreModelReason.DURATION_EXCEEDS_HORIZON:
            raise
        overflow_reason = error.reason.value
    else:
        raise ValueError("overflow Problem unexpectedly reached CP-SAT construction")

    zero = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=2, tag="ZERO"
    )
    zero["operation_instances"][0]["resource_options"] = []
    try:
        precheck_core_problem(cast(dict[str, object], zero))
    except CoreModelInputError as error:
        if error.reason is not CoreModelReason.ZERO_RESOURCE_OPTIONS:
            raise
        zero_reason = error.reason.value
    else:
        raise ValueError("zero-candidate Problem unexpectedly reached CP-SAT construction")
    return {"overflow": overflow_reason, "zero_candidate": zero_reason}


def run_core_model_checks(root: Path) -> JsonObject:
    """Run core construction, solve, oracle, Validator, mutation, and telemetry checks."""

    root = root.resolve()
    policy = synthetic_core_policy()
    limits = synthetic_core_limits()
    backend = CpSatBackend()
    jssp_options: tuple[tuple[OptionTicks, ...], ...] = (
        (("RESOURCE-001", 2),),
        (("RESOURCE-001", 3),),
        (("RESOURCE-001", 1),),
    )
    fjsp_options: tuple[tuple[OptionTicks, ...], ...] = (
        (("RESOURCE-001", 2), ("RESOURCE-002", 3)),
        (("RESOURCE-001", 3), ("RESOURCE-002", 1)),
    )
    infeasible_options: tuple[tuple[OptionTicks, ...], ...] = (
        (("RESOURCE-001", 4),),
        (("RESOURCE-001", 4),),
    )
    jssp = synthetic_core_problem(jssp_options, horizon_ticks=6, tag="JSSP")
    fjsp = synthetic_core_problem(fjsp_options, horizon_ticks=6, tag="FJSP")
    infeasible = synthetic_core_problem(
        infeasible_options, horizon_ticks=6, tag="INFEASIBLE"
    )

    jssp_model = build_core_model(jssp)
    fjsp_model = build_core_model(fjsp)
    if jssp_model.model.has_objective() or fjsp_model.model.has_objective():
        raise ValueError("TASK-P2-05 core model unexpectedly contains an objective")
    jssp_result = backend.solve_with_evidence(jssp, policy, limits)
    fjsp_result = backend.solve_with_evidence(fjsp, policy, limits)
    infeasible_result = backend.solve_with_evidence(infeasible, policy, limits)
    for result in (jssp_result, fjsp_result):
        if (
            result.solution["solver_status"] != "FEASIBLE"
            or result.validation_report is None
            or result.validation_report["status"] != "PASS"
            or result.telemetry["objective_optimized"]
        ):
            raise ValueError("Core candidate status, validation, or objective boundary failed")
    assert jssp_result.validation_report is not None
    assert fjsp_result.validation_report is not None
    if (
        infeasible_result.solution["solver_status"] != "INFEASIBLE"
        or infeasible_result.solution["assignments"]
        or infeasible_result.validation_report is not None
    ):
        raise ValueError("Unary overload did not produce a certified non-candidate")

    ordered = sorted(
        jssp_result.solution["assignments"], key=lambda item: item["start_tick"]
    )
    if any(left["end_tick"] != right["start_tick"] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Tight JSSP did not demonstrate half-open back-to-back intervals")

    missing = deepcopy(jssp_result.solution)
    missing["assignments"].pop()
    missing_report = validate_problem_schedule(jssp, missing)
    duration = deepcopy(jssp_result.solution)
    duration["assignments"][0]["duration_seconds"] += 1
    duration_report = validate_problem_schedule(jssp, duration)
    if tuple(item["constraint_id"] for item in missing_report["violations"]) != (
        "C-001",
    ) or tuple(item["constraint_id"] for item in duration_report["violations"]) != (
        "C-010",
    ):
        raise ValueError("Independent Validator mutations did not isolate C-001/C-010")

    oracle_cases = (
        (jssp_options, 6),
        (fjsp_options, 6),
        (infeasible_options, 6),
        (
            (
                (("RESOURCE-001", 2), ("RESOURCE-002", 2)),
                (("RESOURCE-001", 5),),
            ),
            5,
        ),
    )
    oracle_rows = []
    for index, case in enumerate(oracle_cases):
        options, horizon = case
        expected = brute_force_core_feasible(options, horizon)
        problem = synthetic_core_problem(options, horizon_ticks=horizon, tag=f"ORACLE-{index}")
        observed = backend.solve(problem, policy, limits)["solver_status"] == "FEASIBLE"
        if observed != expected:
            raise ValueError("CP-SAT result differs from the independent tiny oracle")
        oracle_rows.append({"case": index, "expected_feasible": expected})

    telemetry_rows = [jssp_result.telemetry, fjsp_result.telemetry]
    for telemetry in telemetry_rows:
        if (
            telemetry["model_build_seconds"] < 0
            or telemetry["solve_seconds"] < 0
            or telemetry["first_feasible_seconds"] is None
            or telemetry["python_memory_peak_mb"] < 0
            or telemetry["validator_status"] != "PASS"
        ):
            raise ValueError("Core telemetry is incomplete or invalid")

    checks = [
        _pass("fixed-contract-validator-rule-and-lock-fingerprints", _fingerprints(root)),
        _pass(
            "c001-c003-c004-c010-c011-model-shape",
            {
                "constraint_ids": list(CORE_CONSTRAINT_IDS),
                "jssp": jssp_model.metrics,
                "fjsp": fjsp_model.metrics,
                "objective_present": False,
            },
        ),
        _pass(
            "tiny-golden-jssp-fjsp-candidates",
            {
                "jssp_problem_hash": jssp["problem_hash"],
                "fjsp_problem_hash": fjsp["problem_hash"],
                "candidate_statuses": [
                    jssp_result.solution["solver_status"],
                    fjsp_result.solution["solver_status"],
                ],
                "validator_statuses": [
                    jssp_result.validation_report["status"],
                    fjsp_result.validation_report["status"],
                ],
            },
        ),
        _pass(
            "infeasible-and-build-prechecks",
            {
                "unary_overload_status": infeasible_result.solution["solver_status"],
                "prechecks": _precheck_evidence(),
            },
        ),
        _pass(
            "independent-validator-positive-and-mutations",
            {
                "positive": "PASS",
                "missing_assignment": ["C-001"],
                "duration_mutation": ["C-010"],
            },
        ),
        _pass(
            "brute-force-oracle-and-real-telemetry",
            {"oracle_cases": oracle_rows, "telemetry": telemetry_rows},
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "check_count": len(checks),
        "counts": {
            "core_constraint_ids": len(CORE_CONSTRAINT_IDS),
            "candidate_cases": 2,
            "infeasible_cases": 1,
            "precheck_rejections": 2,
            "validator_mutations": 2,
            "brute_force_cases": len(oracle_rows),
        },
        "checks": checks,
        "boundaries": {
            "problem_policy_solution_schema_changes": "NONE",
            "constraint_rule_changes": "NONE",
            "formal_validator_changes": "NONE",
            "dependency_changes": "NONE",
            "implemented_constraints": list(CORE_CONSTRAINT_IDS),
            "deferred_constraints": [
                "C-002",
                "C-005",
                "C-006",
                "C-007",
                "C-008",
                "C-009",
            ],
            "objective": "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED",
            "strategy": "NOT_IMPLEMENTED",
            "benchmark": "TINY_CORRECTNESS_ONLY_NO_XS_S_M_BASELINE",
            "candidate_publishability": "TEST_ARTIFACT_ONLY",
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
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_core_model_checks(cast(Path, args.root))
    except Exception as error:  # CLI boundary emits sanitized failure evidence
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "error_type": type(error).__name__,
        }
        _write_report(cast(Path, args.report), report)
        print(f"FAIL CP-SAT core model: {type(error).__name__}", file=sys.stderr)
        return 1
    _write_report(cast(Path, args.report), report)
    counts = cast(JsonObject, report["counts"])
    print(
        "PASS CP-SAT core model: "
        f"checks={report['check_count']} constraints={counts['core_constraint_ids']} "
        f"oracle_cases={counts['brute_force_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "REPORT_VERSION",
    "TASK_ID",
    "brute_force_core_feasible",
    "main",
    "run_core_model_checks",
    "synthetic_core_limits",
    "synthetic_core_policy",
    "synthetic_core_problem",
]
