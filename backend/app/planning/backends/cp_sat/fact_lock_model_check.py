"""Emit machine-checkable TASK-P2-07 execution-fact and lock evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, cast

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.backend import CoreSolveResult, CpSatBackend
from app.planning.backends.cp_sat.core_constraints import (
    CoreModelInputError,
    CoreModelReason,
)
from app.planning.backends.cp_sat.core_model_check import (
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.backends.cp_sat.fact_lock_constraints import (
    FACT_LOCK_CONSTRAINT_IDS,
)
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)


REPORT_VERSION = "cp-sat-fact-lock-model-report.v1"
TASK_ID = "TASK-P2-07"
type JsonObject = dict[str, Any]

_FIXED_FINGERPRINTS = {
    "planning_problem_v2_schema": "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    "planning_solution_schema": "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    "constraint_rule_sheet": "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2",
    "formal_validator": "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f",
    "problem_builder": "c96a55a8d59da785a0109d83a75fbd2df2e2bfcccf234c07581019033af0f291",
    "problem_hashing": "ec2b98ed59ed8b5a4d4588254e2a49d9b9c7df1c2b666f78f00104c39cc76b4e",
    "adr_0007": "646a586cd54c94567e72ecb9219920b15565aaac8431feb83b11de77cd00d2ba",
    "uv_lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}
_FINGERPRINT_PATHS = {
    "planning_problem_v2_schema": "schemas/json/planning-problem.v2.schema.json",
    "planning_solution_schema": "schemas/json/planning-solution.schema.json",
    "constraint_rule_sheet": "schemas/rules/constraint-rule-sheet.v1.yaml",
    "formal_validator": "backend/app/planning/validation/problem_schedule_validator.py",
    "problem_builder": "backend/app/planning/problem/builder.py",
    "problem_hashing": "backend/app/planning/problem/hashing.py",
    "adr_0007": "docs/adr/ADR-0007-immutable-snapshot-and-schedule-version.md",
    "uv_lock": "uv.lock",
}


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _fingerprints(root: Path) -> JsonObject:
    observed = {
        name: sha256((root / relative).read_bytes()).hexdigest()
        for name, relative in _FINGERPRINT_PATHS.items()
    }
    if observed != _FIXED_FINGERPRINTS:
        raise ValueError(
            "A frozen P2-07 contract, builder, validator, rule, ADR, or lock drifted"
        )
    return observed


def _at(problem: PlanningProblemDocumentV2, seconds: int) -> str:
    return format_utc_instant(
        parse_utc_instant(problem["horizon_start_utc"])
        + timedelta(seconds=seconds)
    )


def _enable(problem: PlanningProblemDocumentV2, *capabilities: str) -> None:
    problem["required_capabilities"] = sorted(
        set(problem["required_capabilities"]) | set(capabilities)
    )


def _rehash(problem: PlanningProblemDocumentV2) -> PlanningProblemDocumentV2:
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    return problem


def _make_running(
    problem: PlanningProblemDocumentV2,
    *,
    resource_id: str,
    remaining_seconds: int,
    operation_index: int = 0,
) -> None:
    operation = cast(dict[str, Any], problem["operation_instances"][operation_index])
    operation.update(
        {
            "status": "RUNNING",
            "actual_start_at_utc": _at(problem, -120),
            "assigned_resource_id": resource_id,
            "remaining_seconds": remaining_seconds,
        }
    )
    _enable(problem, "RUNNING_OPERATION")


def _lock(
    problem: PlanningProblemDocumentV2,
    *,
    lock_id: str,
    operation_id: str = "OP-000",
    lock_type: str = "HARD_LOCK",
    resource_id: str = "RESOURCE-001",
    start_tick: int = 0,
    end_tick: int = 1,
) -> JsonObject:
    tick_seconds = problem["tick_seconds"]
    return {
        "lock_id": lock_id,
        "operation_id": operation_id,
        "lock_type": lock_type,
        "resource_id": resource_id,
        "start_at_utc": _at(problem, start_tick * tick_seconds),
        "end_at_utc": _at(problem, end_tick * tick_seconds),
        "source_system": "TASK-P2-07-MACHINE",
        "source_version": "1.0.0",
        "source_record_id": lock_id,
    }


def _solve(problem: PlanningProblemDocumentV2) -> CoreSolveResult:
    return CpSatBackend().solve_with_evidence(
        _rehash(problem), synthetic_core_policy(), synthetic_core_limits()
    )


def _running_anchor_case() -> tuple[PlanningProblemDocumentV2, CoreSolveResult]:
    problem = synthetic_core_problem(
        [
            [("RESOURCE-001", 4), ("RESOURCE-002", 1)],
            [("RESOURCE-002", 1)],
        ],
        horizon_ticks=6,
        tag="MACHINE-RUNNING-ANCHOR",
    )
    _make_running(problem, resource_id="RESOURCE-001", remaining_seconds=61)
    problem["historical_completion_anchors"] = [
        {
            "operation_id": "OP-COMPLETED",
            "execution_fact_id": "FACT-COMPLETED",
            "resource_id": "RESOURCE-001",
            "actual_start_at_utc": _at(problem, -90),
            "actual_end_at_utc": _at(problem, -30),
            "source_system": "TASK-P2-07-MACHINE",
            "source_version": "1.0.0",
            "source_record_id": "FACT-COMPLETED",
        }
    ]
    problem["precedence_edges"] = [
        {
            "precedence_edge_id": "EDGE-COMPLETED-ACTIVE",
            "predecessor_operation_id": "OP-COMPLETED",
            "successor_operation_id": "OP-001",
            "min_lag_seconds": 90,
            "transport_lag_seconds": 0,
        }
    ]
    _enable(problem, "DAG_ROUTING")
    result = _solve(problem)
    by_id = {
        assignment["operation_id"]: assignment
        for assignment in result.solution["assignments"]
    }
    if (
        result.solution["solver_status"] != "FEASIBLE"
        or result.validation_report is None
        or result.validation_report["status"] != "PASS"
        or set(by_id) != {"OP-000", "OP-001"}
        or by_id["OP-000"]["resource_id"] != "RESOURCE-001"
        or by_id["OP-000"]["start_tick"] != 0
        or by_id["OP-000"]["end_tick"] != 2
        or by_id["OP-000"]["duration_seconds"] != 61
        or by_id["OP-001"]["start_tick"] < 1
    ):
        raise ValueError("C-007 RUNNING/COMPLETED anchor candidate is invalid")
    return problem, result


def _hard_soft_cases() -> tuple[
    PlanningProblemDocumentV2,
    CoreSolveResult,
    PlanningProblemDocumentV2,
    CoreSolveResult,
]:
    hard_problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=6,
        tag="MACHINE-HARD-SOFT",
    )
    hard_problem["operation_locks"] = cast(
        Any,
        [
            _lock(
                hard_problem,
                lock_id="LOCK-HARD",
                resource_id="RESOURCE-002",
                start_tick=2,
                end_tick=3,
            ),
            _lock(
                hard_problem,
                lock_id="LOCK-SOFT",
                lock_type="SOFT_LOCK",
                resource_id="RESOURCE-001",
                start_tick=4,
                end_tick=5,
            ),
        ],
    )
    _enable(hard_problem, "HARD_SOFT_LOCK")
    hard_result = _solve(hard_problem)
    hard_assignment = hard_result.solution["assignments"][0]
    if (
        hard_result.validation_report is None
        or hard_result.validation_report["status"] != "PASS"
        or (
            hard_assignment["resource_id"],
            hard_assignment["start_tick"],
            hard_assignment["end_tick"],
        )
        != ("RESOURCE-002", 2, 3)
        or hard_assignment["lock_ids"] != ["LOCK-HARD", "LOCK-SOFT"]
    ):
        raise ValueError("C-008 exact HARD lock candidate is invalid")

    soft_problem = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=4,
        tag="MACHINE-SOFT-NON-HARD",
    )
    soft_problem["operation_locks"] = cast(
        Any,
        [
            _lock(
                soft_problem,
                lock_id="LOCK-SOFT-ONLY",
                lock_type="SOFT_LOCK",
                resource_id="RESOURCE-002",
                start_tick=2,
                end_tick=3,
            )
        ],
    )
    soft_problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-002",
            "resource_id": "RESOURCE-002",
            "start_utc": _at(soft_problem, 0),
            "end_utc": _at(soft_problem, 240),
        }
    ]
    _enable(soft_problem, "HARD_SOFT_LOCK", "MACHINE_CALENDAR")
    soft_result = _solve(soft_problem)
    soft_assignment = soft_result.solution["assignments"][0]
    if (
        soft_result.validation_report is None
        or soft_result.validation_report["status"] != "PASS"
        or soft_assignment["resource_id"] != "RESOURCE-001"
        or soft_assignment["lock_ids"] != ["LOCK-SOFT-ONLY"]
    ):
        raise ValueError("SOFT lock was hardened or its metadata was discarded")
    return hard_problem, hard_result, soft_problem, soft_result


def _infeasible_evidence() -> JsonObject:
    statuses: dict[str, str] = {}

    calendar = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=4, tag="MACHINE-INF-CALENDAR"
    )
    calendar["operation_locks"] = cast(
        Any, [_lock(calendar, lock_id="LOCK-CALENDAR")]
    )
    calendar["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(calendar, 0),
            "end_utc": _at(calendar, 60),
        }
    ]
    _enable(calendar, "HARD_SOFT_LOCK", "MACHINE_CALENDAR")
    statuses["calendar"] = _solve(calendar).solution["solver_status"]

    overlap = synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-001", 1)]],
        horizon_ticks=4,
        tag="MACHINE-INF-OVERLAP",
    )
    overlap["operation_locks"] = cast(
        Any,
        [
            _lock(overlap, lock_id="LOCK-A", operation_id="OP-000"),
            _lock(overlap, lock_id="LOCK-B", operation_id="OP-001"),
        ],
    )
    _enable(overlap, "HARD_SOFT_LOCK")
    statuses["resource_overlap"] = _solve(overlap).solution["solver_status"]

    horizon = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=4, tag="MACHINE-INF-HORIZON"
    )
    horizon["operation_locks"] = cast(
        Any,
        [
            _lock(
                horizon,
                lock_id="LOCK-HORIZON",
                start_tick=4,
                end_tick=5,
            )
        ],
    )
    _enable(horizon, "HARD_SOFT_LOCK")
    statuses["horizon"] = _solve(horizon).solution["solver_status"]

    if set(statuses.values()) != {"INFEASIBLE"}:
        raise ValueError("A valid fact/lock conflict was not certified INFEASIBLE")
    return statuses


def _precheck_evidence() -> JsonObject:
    observed: dict[str, str] = {}

    grid = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=4, tag="MACHINE-PRECHECK-GRID"
    )
    grid_lock = _lock(grid, lock_id="LOCK-GRID")
    grid_lock["start_at_utc"] = _at(grid, 1)
    grid_lock["end_at_utc"] = _at(grid, 61)
    grid["operation_locks"] = cast(Any, [grid_lock])
    _enable(grid, "HARD_SOFT_LOCK")

    duration = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=4, tag="MACHINE-PRECHECK-DURATION"
    )
    duration["operation_locks"] = cast(
        Any,
        [_lock(duration, lock_id="LOCK-DURATION", start_tick=0, end_tick=2)],
    )
    _enable(duration, "HARD_SOFT_LOCK")

    running_lock = synthetic_core_problem(
        [[("RESOURCE-001", 1), ("RESOURCE-002", 1)]],
        horizon_ticks=4,
        tag="MACHINE-PRECHECK-RUNNING-LOCK",
    )
    _make_running(running_lock, resource_id="RESOURCE-001", remaining_seconds=60)
    running_lock["operation_locks"] = cast(
        Any,
        [
            _lock(
                running_lock,
                lock_id="LOCK-RUNNING-CONFLICT",
                resource_id="RESOURCE-002",
            )
        ],
    )
    _enable(running_lock, "HARD_SOFT_LOCK")

    overflow = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=2, tag="MACHINE-PRECHECK-OVERFLOW"
    )
    _make_running(overflow, resource_id="RESOURCE-001", remaining_seconds=121)

    cases = {
        "hard_lock_grid": (grid, CoreModelReason.HARD_LOCK_NOT_TICK_ALIGNED),
        "hard_lock_duration": (duration, CoreModelReason.FACT_LOCK_SELF_CONFLICT),
        "running_hard_lock": (
            running_lock,
            CoreModelReason.FACT_LOCK_SELF_CONFLICT,
        ),
        "running_remainder_overflow": (
            overflow,
            CoreModelReason.DURATION_EXCEEDS_HORIZON,
        ),
    }
    for name, (problem, expected_reason) in cases.items():
        try:
            build_core_model(_rehash(problem))
        except CoreModelInputError as error:
            if error.reason is not expected_reason:
                raise
            observed[name] = error.reason.value
        else:
            raise ValueError(f"Fact/lock precheck case unexpectedly built: {name}")
    return observed


def _validator_mutations(
    running_problem: PlanningProblemDocumentV2,
    running_result: CoreSolveResult,
    hard_problem: PlanningProblemDocumentV2,
    hard_result: CoreSolveResult,
) -> JsonObject:
    running = deepcopy(running_result.solution)
    running_assignment = running["assignments"][0]
    running_assignment["start_tick"] += 1
    running_assignment["end_tick"] += 1
    running_tick_seconds = running_problem["tick_seconds"]
    running_assignment["start_at_utc"] = _at(
        running_problem, running_assignment["start_tick"] * running_tick_seconds
    )
    running_assignment["end_at_utc"] = _at(
        running_problem, running_assignment["end_tick"] * running_tick_seconds
    )
    running_ids = tuple(
        item["constraint_id"]
        for item in validate_problem_schedule(running_problem, running)["violations"]
    )

    hard = deepcopy(hard_result.solution)
    assignment = hard["assignments"][0]
    assignment["start_tick"] += 1
    assignment["end_tick"] += 1
    assignment["start_at_utc"] = _at(hard_problem, assignment["start_tick"] * 60)
    assignment["end_at_utc"] = _at(hard_problem, assignment["end_tick"] * 60)
    hard_ids = tuple(
        item["constraint_id"]
        for item in validate_problem_schedule(hard_problem, hard)["violations"]
    )
    if running_ids != ("C-007",) or hard_ids != ("C-008",):
        raise ValueError("Independent Validator mutations did not isolate C-007/C-008")
    return {"running_moved": list(running_ids), "hard_lock_moved": list(hard_ids)}


def _tiny_oracle() -> list[JsonObject]:
    cases = (
        (0, 1, 3, None, True),
        (2, 1, 3, None, True),
        (3, 1, 3, None, False),
        (0, 1, 3, (0, 1), False),
        (0, 1, 3, (1, 2), True),
        (1, 2, 4, (2, 3), False),
    )
    rows: list[JsonObject] = []
    for index, (start, duration, horizon, unavailable, expected) in enumerate(cases):
        problem = synthetic_core_problem(
            [[("RESOURCE-001", duration)]],
            horizon_ticks=horizon,
            tag=f"MACHINE-ORACLE-{index}",
        )
        problem["operation_locks"] = cast(
            Any,
            [
                _lock(
                    problem,
                    lock_id=f"LOCK-ORACLE-{index}",
                    start_tick=start,
                    end_tick=start + duration,
                )
            ],
        )
        _enable(problem, "HARD_SOFT_LOCK")
        if unavailable is not None:
            unavailable_start, unavailable_end = unavailable
            problem["resource_unavailable_intervals"] = [
                {
                    "calendar_id": "CAL-RESOURCE-001",
                    "resource_id": "RESOURCE-001",
                    "start_utc": _at(problem, unavailable_start * 60),
                    "end_utc": _at(problem, unavailable_end * 60),
                }
            ]
            _enable(problem, "MACHINE_CALENDAR")
        result = _solve(problem)
        observed = result.solution["solver_status"] == "FEASIBLE"
        if observed is not expected:
            raise ValueError("CP-SAT fact/lock result differs from tiny exact oracle")
        rows.append(
            {
                "case": index,
                "expected_feasible": expected,
                "observed_status": result.solution["solver_status"],
            }
        )
    return rows


def _model_delta_and_telemetry() -> JsonObject:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-002", 1)]],
        horizon_ticks=4,
        tag="MACHINE-MODEL-DELTA",
    )
    _make_running(problem, resource_id="RESOURCE-001", remaining_seconds=60)
    problem["operation_locks"] = cast(
        Any,
        [
            _lock(
                problem,
                lock_id="LOCK-DELTA-HARD",
                operation_id="OP-001",
                resource_id="RESOURCE-002",
                start_tick=1,
                end_tick=2,
            ),
            _lock(
                problem,
                lock_id="LOCK-DELTA-SOFT",
                operation_id="OP-001",
                lock_type="SOFT_LOCK",
                resource_id="RESOURCE-002",
                start_tick=2,
                end_tick=3,
            ),
        ],
    )
    _enable(problem, "HARD_SOFT_LOCK")
    model = build_core_model(_rehash(problem))

    baseline = synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-002", 1)]],
        horizon_ticks=4,
        tag="MACHINE-MODEL-DELTA-BASE",
    )
    baseline_model = build_core_model(baseline)
    result = _solve(problem)
    constraint_delta = (
        model.metrics["constraints"] - baseline_model.metrics["constraints"]
    )
    if (
        model.fact_lock_metrics["fixed_operation_intervals"] != 2
        or model.fact_lock_metrics["resource_fix_constraints"] != 2
        or model.fact_lock_metrics["start_fix_constraints"] != 2
        or model.fact_lock_metrics["end_fix_constraints"] != 2
        or constraint_delta != 6
        or result.validation_report is None
        or result.validation_report["status"] != "PASS"
        or result.telemetry["model_build_seconds"] < 0
        or result.telemetry["solve_seconds"] < 0
        or result.telemetry["first_feasible_seconds"] is None
        or result.telemetry["python_memory_peak_mb"] < 0
    ):
        raise ValueError("Fact/lock model delta or runtime telemetry is invalid")
    return {
        "fact_lock_metrics": model.fact_lock_metrics,
        "constraint_delta": constraint_delta,
        "telemetry": result.telemetry,
    }


def run_fact_lock_model_checks(root: Path) -> JsonObject:
    """Run C-007/C-008 candidates, conflicts, mutations, oracle, and telemetry."""

    root = root.resolve()
    running_problem, running_result = _running_anchor_case()
    hard_problem, hard_result, soft_problem, soft_result = _hard_soft_cases()
    infeasible = _infeasible_evidence()
    prechecks = _precheck_evidence()
    mutations = _validator_mutations(
        running_problem, running_result, hard_problem, hard_result
    )
    oracle_rows = _tiny_oracle()
    model_delta = _model_delta_and_telemetry()
    checks = [
        _pass(
            "fixed-contract-builder-validator-rule-adr-and-lock-fingerprints",
            _fingerprints(root),
        ),
        _pass(
            "c007-running-remainder-resource-and-completed-anchor",
            {
                "problem_hash": running_problem["problem_hash"],
                "assignments": running_result.solution["assignments"],
                "completed_assignment_absent": True,
                "validator_status": running_result.validation_report["status"]
                if running_result.validation_report is not None
                else None,
            },
        ),
        _pass(
            "c008-hard-exact-and-soft-metadata-only",
            {
                "hard_problem_hash": hard_problem["problem_hash"],
                "hard_assignment": hard_result.solution["assignments"][0],
                "soft_problem_hash": soft_problem["problem_hash"],
                "soft_assignment": soft_result.solution["assignments"][0],
            },
        ),
        _pass(
            "calendar-resource-overlap-and-horizon-certified-infeasible",
            infeasible,
        ),
        _pass("fact-lock-self-conflict-and-grid-prechecks", prechecks),
        _pass("independent-validator-c007-c008-mutations", mutations),
        _pass(
            "tiny-exact-oracle-model-delta-and-real-telemetry",
            {"oracle_cases": oracle_rows, "model_delta": model_delta},
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
            "fact_lock_constraint_ids": len(FACT_LOCK_CONSTRAINT_IDS),
            "candidate_cases": 4,
            "infeasible_cases": len(infeasible),
            "precheck_rejections": len(prechecks),
            "validator_mutations": len(mutations),
            "tiny_oracle_cases": len(oracle_rows),
        },
        "checks": checks,
        "boundaries": {
            "problem_policy_solution_schema_changes": "NONE",
            "constraint_rule_changes": "NONE",
            "formal_validator_changes": "NONE",
            "problem_builder_hashing_changes": "NONE",
            "dependency_changes": "NONE",
            "implemented_constraints": [f"C-{index:03d}" for index in range(1, 12)],
            "deferred_constraints": [],
            "soft_lock": "METADATA_REFERENCE_ONLY_STABILITY_OBJECTIVE_NOT_EXECUTED",
            "objective": "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED",
            "strategy": "NOT_IMPLEMENTED",
            "dynamic_replan": "NOT_IMPLEMENTED",
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
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_fact_lock_model_checks(arguments.root)
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
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


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_fact_lock_model_checks"]
