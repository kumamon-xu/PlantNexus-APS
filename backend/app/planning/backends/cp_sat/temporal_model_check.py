"""Emit machine-checkable TASK-P2-06 temporal model correctness evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any, cast

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.backend import CpSatBackend
from app.planning.backends.cp_sat.core_constraints import (
    CoreModelInputError,
    CoreModelReason,
)
from app.planning.backends.cp_sat.core_model_check import (
    synthetic_core_limits,
    synthetic_core_policy,
    synthetic_core_problem,
)
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.backends.cp_sat.temporal_constraints import (
    TEMPORAL_CONSTRAINT_IDS,
    calendar_tick_blocks,
    ceil_seconds_to_ticks,
    floor_seconds_to_ticks,
)
from app.planning.contracts import PlanningSolutionDocument
from app.planning.policy.contracts import PlanningPolicyDocument, SolveLimitsDocument
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import validate_problem_schedule


REPORT_VERSION = "cp-sat-temporal-model-report.v1"
TASK_ID = "TASK-P2-06"
type JsonObject = dict[str, Any]

_FIXED_FINGERPRINTS = {
    "planning_problem_v2_schema": "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    "planning_solution_schema": "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    "planning_policy_schema": "62624424115c3f6c9d45e920bcb0ac744ae9e1f2173af81072610298560a1bda",
    "solve_limits_schema": "8caff522a1fef8e40671cdff3ca857084cbf908b5c7fdfb9fdd8468fc3811d95",
    "constraint_rule_sheet": "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2",
    "formal_validator": "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f",
    "planning_contracts": "d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630",
    "problem_builder": "c96a55a8d59da785a0109d83a75fbd2df2e2bfcccf234c07581019033af0f291",
    "problem_hashing": "ec2b98ed59ed8b5a4d4588254e2a49d9b9c7df1c2b666f78f00104c39cc76b4e",
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
    "problem_builder": "backend/app/planning/problem/builder.py",
    "problem_hashing": "backend/app/planning/problem/hashing.py",
    "uv_lock": "uv.lock",
}


def _at(problem: PlanningProblemDocumentV2, seconds: int) -> str:
    return format_utc_instant(
        parse_utc_instant(problem["horizon_start_utc"])
        + timedelta(seconds=seconds)
    )


def _rehash(problem: PlanningProblemDocumentV2) -> PlanningProblemDocumentV2:
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    return problem


def _edge(
    *,
    predecessor: str = "OP-000",
    successor: str = "OP-001",
    minimum: int = 0,
    transport: int = 0,
    maximum: int | None = None,
) -> JsonObject:
    value: JsonObject = {
        "precedence_edge_id": "EDGE-TEMPORAL-001",
        "predecessor_operation_id": predecessor,
        "successor_operation_id": successor,
        "min_lag_seconds": minimum,
        "transport_lag_seconds": transport,
    }
    if maximum is not None:
        value["max_lag_seconds"] = maximum
    return value


def _two_resource_problem(
    *,
    tag: str,
    horizon_ticks: int = 8,
    tick_seconds: int = 60,
) -> PlanningProblemDocumentV2:
    return synthetic_core_problem(
        [[("RESOURCE-001", 1)], [("RESOURCE-002", 1)]],
        horizon_ticks=horizon_ticks,
        tick_seconds=tick_seconds,
        tag=tag,
    )


def _precedence_problem() -> PlanningProblemDocumentV2:
    problem = _two_resource_problem(tag="REPORT-PRECEDENCE")
    problem["precedence_edges"] = [
        cast(Any, _edge(minimum=61, maximum=120))
    ]
    return _rehash(problem)


def _gate_problem(*, calendar: bool) -> PlanningProblemDocumentV2:
    problem = synthetic_core_problem(
        [[("RESOURCE-001", 1)]],
        horizon_ticks=6,
        tag="REPORT-GATE-CALENDAR" if calendar else "REPORT-GATE",
    )
    operation = problem["operation_instances"][0]
    operation["release_at_utc"] = _at(problem, 61)
    operation["material_ready_at_utc"] = _at(problem, 119)
    if calendar:
        problem["resource_unavailable_intervals"] = [
            {
                "calendar_id": "CAL-RESOURCE-001",
                "resource_id": "RESOURCE-001",
                "start_utc": _at(problem, 120),
                "end_utc": _at(problem, 180),
            }
        ]
    return _rehash(problem)


def _transport_problem() -> PlanningProblemDocumentV2:
    problem = _two_resource_problem(tag="REPORT-TRANSPORT", horizon_ticks=5)
    problem["resources"][0]["workshop_id"] = "WORKSHOP-A"
    problem["resources"][1]["workshop_id"] = "WORKSHOP-B"
    problem["precedence_edges"] = [
        cast(Any, _edge(minimum=0, transport=121, maximum=180))
    ]
    return _rehash(problem)


def _anchor_problem() -> PlanningProblemDocumentV2:
    problem = synthetic_core_problem(
        [[("RESOURCE-002", 1)]], horizon_ticks=4, tag="REPORT-ANCHOR"
    )
    problem["resources"].append(
        {
            "resource_id": "RESOURCE-001",
            "resource_code": "RESOURCE-001",
            "resource_type": "MACHINE",
            "status": "AVAILABLE",
            "factory_id": "FACTORY-CORE",
            "workshop_id": "WORKSHOP-A",
            "production_line_id": "LINE-CORE",
            "resource_group_id": "GROUP-CORE",
            "calendar_id": "CAL-RESOURCE-001",
            "capabilities": ["CORE"],
            "capacity": 1,
        }
    )
    problem["resources"][0]["workshop_id"] = "WORKSHOP-B"
    problem["resources"].sort(key=lambda item: item["resource_id"])
    problem["historical_completion_anchors"] = [
        {
            "operation_id": "OP-HISTORICAL",
            "execution_fact_id": "FACT-HISTORICAL",
            "resource_id": "RESOURCE-001",
            "actual_start_at_utc": _at(problem, -90),
            "actual_end_at_utc": _at(problem, -30),
            "source_system": "TASK-P2-06-MACHINE",
            "source_version": "1.0.0",
            "source_record_id": "FACT-HISTORICAL",
        }
    ]
    problem["precedence_edges"] = [
        cast(
            Any,
            _edge(
                predecessor="OP-HISTORICAL",
                successor="OP-000",
                minimum=31,
                transport=61,
                maximum=90,
            ),
        )
    ]
    return _rehash(problem)


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _fingerprints(root: Path) -> JsonObject:
    observed = {
        name: sha256((root / relative).read_bytes()).hexdigest()
        for name, relative in _FINGERPRINT_PATHS.items()
    }
    if observed != _FIXED_FINGERPRINTS:
        raise ValueError("A frozen P2-06 contract, builder, validator, rule, or lock drifted")
    return observed


def _accepted_result(
    backend: CpSatBackend,
    problem: PlanningProblemDocumentV2,
    policy: PlanningPolicyDocument,
    limits: SolveLimitsDocument,
):
    result = backend.solve_with_evidence(problem, policy, limits)
    if (
        result.solution["solver_status"] != "FEASIBLE"
        or result.validation_report is None
        or result.validation_report["status"] != "PASS"
        or result.telemetry["objective_optimized"]
    ):
        raise ValueError("Temporal candidate was not honestly mapped and validated")
    return result


def _assignment_by_id(solution: PlanningSolutionDocument) -> dict[str, JsonObject]:
    return {
        assignment["operation_id"]: cast(JsonObject, assignment)
        for assignment in solution["assignments"]
    }


def _move_assignment(
    solution: PlanningSolutionDocument,
    problem: PlanningProblemDocumentV2,
    operation_id: str,
    start_tick: int,
) -> None:
    assignment = _assignment_by_id(solution)[operation_id]
    duration_ticks = cast(int, assignment["duration_ticks"])
    end_tick = start_tick + duration_ticks
    assignment["start_tick"] = start_tick
    assignment["end_tick"] = end_tick
    assignment["start_at_utc"] = _at(
        problem, start_tick * problem["tick_seconds"]
    )
    assignment["end_at_utc"] = _at(problem, end_tick * problem["tick_seconds"])


def _validator_mutations(
    cases: Mapping[str, tuple[PlanningProblemDocumentV2, PlanningSolutionDocument]],
) -> JsonObject:
    observed: JsonObject = {}

    precedence_problem, precedence_solution = cases["precedence"]
    mutated_precedence = deepcopy(precedence_solution)
    precedence_assignments = _assignment_by_id(mutated_precedence)
    predecessor_end = cast(int, precedence_assignments["OP-000"]["end_tick"])
    _move_assignment(mutated_precedence, precedence_problem, "OP-001", predecessor_end + 1)
    observed["C-002"] = sorted(
        {
            item["constraint_id"]
            for item in validate_problem_schedule(
                precedence_problem, mutated_precedence
            )["violations"]
        }
    )

    calendar_problem, calendar_solution = cases["calendar"]
    mutated_calendar = deepcopy(calendar_solution)
    _move_assignment(mutated_calendar, calendar_problem, "OP-000", 2)
    observed["C-005"] = sorted(
        {
            item["constraint_id"]
            for item in validate_problem_schedule(
                calendar_problem, mutated_calendar
            )["violations"]
        }
    )

    gate_problem, gate_solution = cases["gate"]
    mutated_gate = deepcopy(gate_solution)
    _move_assignment(mutated_gate, gate_problem, "OP-000", 1)
    observed["C-006"] = sorted(
        {
            item["constraint_id"]
            for item in validate_problem_schedule(gate_problem, mutated_gate)[
                "violations"
            ]
        }
    )

    transport_problem, transport_solution = cases["transport"]
    mutated_transport = deepcopy(transport_solution)
    transport_assignments = _assignment_by_id(mutated_transport)
    predecessor_end = cast(int, transport_assignments["OP-000"]["end_tick"])
    _move_assignment(mutated_transport, transport_problem, "OP-001", predecessor_end + 1)
    observed["C-009"] = sorted(
        {
            item["constraint_id"]
            for item in validate_problem_schedule(
                transport_problem, mutated_transport
            )["violations"]
        }
    )

    for constraint_id in TEMPORAL_CONSTRAINT_IDS:
        if constraint_id not in cast(list[str], observed[constraint_id]):
            raise ValueError(f"Validator mutation did not expose {constraint_id}")
    return observed


def _infeasible_cases(
    backend: CpSatBackend,
    policy: PlanningPolicyDocument,
    limits: SolveLimitsDocument,
) -> JsonObject:
    impossible_window = _two_resource_problem(tag="REPORT-MAX-INFEASIBLE")
    impossible_window["precedence_edges"] = [
        cast(Any, _edge(minimum=61, maximum=119))
    ]
    _rehash(impossible_window)

    full_calendar = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=3, tag="REPORT-CALENDAR-INFEASIBLE"
    )
    full_calendar["resource_unavailable_intervals"] = [
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(full_calendar, 0),
            "end_utc": _at(full_calendar, 61),
        },
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(full_calendar, 60),
            "end_utc": _at(full_calendar, 180),
        },
    ]
    _rehash(full_calendar)

    late_gate = synthetic_core_problem(
        [[("RESOURCE-001", 1)]], horizon_ticks=3, tag="REPORT-GATE-INFEASIBLE"
    )
    late_gate["operation_instances"][0]["release_at_utc"] = _at(late_gate, 181)
    _rehash(late_gate)

    results = {
        "max_lag_tick_window": backend.solve(
            impossible_window, policy, limits
        )["solver_status"],
        "fragmented_calendar": backend.solve(full_calendar, policy, limits)[
            "solver_status"
        ],
        "release_after_horizon": backend.solve(late_gate, policy, limits)[
            "solver_status"
        ],
    }
    if set(results.values()) != {"INFEASIBLE"}:
        raise ValueError("A certified temporal infeasible case changed status")
    return results


def _precheck_rejections() -> JsonObject:
    fractional = _two_resource_problem(tag="REPORT-FRACTIONAL")
    fractional["operation_instances"][0]["release_at_utc"] = (
        "2026-08-20T00:00:00.500000Z"
    )
    _rehash(fractional)
    try:
        build_core_model(fractional)
    except CoreModelInputError as error:
        if error.reason is not CoreModelReason.TEMPORAL_INSTANT_NOT_SECOND_PRECISION:
            raise
        precision_reason = error.reason.value
    else:
        raise ValueError("Sub-second temporal fact was rounded silently")

    overflow = _two_resource_problem(tag="REPORT-TICK-OVERFLOW")
    overflow["precedence_edges"] = [
        cast(Any, _edge(minimum=((1 << 63) + 1) * 60))
    ]
    _rehash(overflow)
    try:
        build_core_model(overflow)
    except CoreModelInputError as error:
        if error.reason is not CoreModelReason.TICK_VALUE_OUT_OF_RANGE:
            raise
        overflow_reason = error.reason.value
    else:
        raise ValueError("Overflowing temporal tick reached CP-SAT construction")
    return {"precision": precision_reason, "overflow": overflow_reason}


def _tiny_window_oracle(
    backend: CpSatBackend,
    policy: PlanningPolicyDocument,
    limits: SolveLimitsDocument,
) -> list[JsonObject]:
    cases = (
        (60, 0, 0),
        (60, 1, 59),
        (60, 61, 119),
        (60, 61, 120),
        (30, 31, 59),
        (30, 31, 60),
        (7, 8, 13),
        (7, 8, 14),
    )
    rows: list[JsonObject] = []
    for index, (tick_seconds, minimum, maximum) in enumerate(cases):
        lower = ceil_seconds_to_ticks(minimum, tick_seconds)
        upper = floor_seconds_to_ticks(maximum, tick_seconds)
        expected = lower <= upper
        problem = _two_resource_problem(
            tag=f"REPORT-ORACLE-{index}",
            tick_seconds=tick_seconds,
            horizon_ticks=max(3, upper + 3),
        )
        problem["precedence_edges"] = [
            cast(Any, _edge(minimum=minimum, maximum=maximum))
        ]
        _rehash(problem)
        result = backend.solve_with_evidence(problem, policy, limits)
        observed = result.solution["solver_status"] == "FEASIBLE"
        if observed != expected:
            raise ValueError("CP-SAT max-lag window differs from the exact tiny oracle")
        if observed and (
            result.validation_report is None
            or result.validation_report["status"] != "PASS"
        ):
            raise ValueError("Tiny oracle candidate failed independent validation")
        rows.append(
            {
                "tick_seconds": tick_seconds,
                "min_lag_seconds": minimum,
                "max_lag_seconds": maximum,
                "min_tick": lower,
                "max_tick": upper,
                "expected_feasible": expected,
            }
        )
    return rows


def _stripped_temporal_problem(
    problem: PlanningProblemDocumentV2,
) -> PlanningProblemDocumentV2:
    stripped = deepcopy(problem)
    stripped["historical_completion_anchors"] = []
    stripped["precedence_edges"] = []
    stripped["resource_unavailable_intervals"] = []
    for operation in stripped["operation_instances"]:
        operation["release_at_utc"] = stripped["horizon_start_utc"]
        operation["material_ready_at_utc"] = stripped["horizon_start_utc"]
    return _rehash(stripped)


def _model_deltas(
    problems: Mapping[str, PlanningProblemDocumentV2],
) -> JsonObject:
    rows: JsonObject = {}
    for name, problem in sorted(problems.items()):
        baseline = build_core_model(_stripped_temporal_problem(problem))
        temporal = build_core_model(problem)
        if temporal.model.has_objective():
            raise ValueError("TASK-P2-06 model unexpectedly contains an objective")
        rows[name] = {
            "baseline": baseline.metrics,
            "temporal": temporal.metrics,
            "delta": {
                key: temporal.metrics[key] - baseline.metrics[key]
                for key in baseline.metrics
            },
            "temporal_constraints": temporal.temporal_metrics,
        }
    return rows


def run_temporal_model_checks(root: Path) -> JsonObject:
    """Run exact rounding, model, Validator, oracle, and telemetry checks."""

    root = root.resolve()
    policy = synthetic_core_policy()
    limits = synthetic_core_limits()
    backend = CpSatBackend()
    problems = {
        "precedence": _precedence_problem(),
        "calendar": _gate_problem(calendar=True),
        "gate": _gate_problem(calendar=False),
        "transport": _transport_problem(),
        "anchor": _anchor_problem(),
    }
    results = {
        name: _accepted_result(backend, problem, policy, limits)
        for name, problem in problems.items()
    }
    candidates = {
        name: (problems[name], results[name].solution)
        for name in ("precedence", "calendar", "gate", "transport")
    }
    mutations = _validator_mutations(candidates)
    infeasible = _infeasible_cases(backend, policy, limits)
    prechecks = _precheck_rejections()
    oracle_rows = _tiny_window_oracle(backend, policy, limits)
    model_deltas = _model_deltas(problems)

    projection_problem = deepcopy(problems["calendar"])
    projection_problem["resource_unavailable_intervals"].append(
        {
            "calendar_id": "CAL-RESOURCE-001",
            "resource_id": "RESOURCE-001",
            "start_utc": _at(projection_problem, 179),
            "end_utc": _at(projection_problem, 241),
        }
    )
    _rehash(projection_problem)
    projection = calendar_tick_blocks(projection_problem, horizon_ticks=6)
    if projection["RESOURCE-001"] != ((2, 5),):
        raise ValueError("Non-integral or fragmented calendar projection changed")

    telemetry = {name: result.telemetry for name, result in results.items()}
    for value in telemetry.values():
        if (
            value["model_build_seconds"] < 0
            or value["solve_seconds"] < 0
            or value["first_feasible_seconds"] is None
            or value["python_memory_peak_mb"] < 0
            or value["validator_status"] != "PASS"
        ):
            raise ValueError("Temporal telemetry is incomplete or invalid")

    checks = [
        _pass("fixed-contract-builder-validator-rule-and-lock-fingerprints", _fingerprints(root)),
        _pass(
            "exact-signed-rounding-and-half-open-calendar-projection",
            {
                "ceil_61_by_60": ceil_seconds_to_ticks(61, 60),
                "floor_119_by_60": floor_seconds_to_ticks(119, 60),
                "ceil_negative_61_by_60": ceil_seconds_to_ticks(-61, 60),
                "projection": projection,
            },
        ),
        _pass(
            "c002-c005-c006-c009-positive-candidates",
            {
                "constraint_ids": list(TEMPORAL_CONSTRAINT_IDS),
                "statuses": {
                    name: result.solution["solver_status"]
                    for name, result in results.items()
                },
                "validator_statuses": {
                    name: cast(JsonObject, result.validation_report)["status"]
                    for name, result in results.items()
                },
            },
        ),
        _pass(
            "max-lag-calendar-gate-infeasible-and-precheck-boundaries",
            {"infeasible": infeasible, "prechecks": prechecks},
        ),
        _pass("independent-validator-temporal-mutations", mutations),
        _pass("tiny-exact-window-oracle", oracle_rows),
        _pass(
            "model-delta-and-real-telemetry",
            {"models": model_deltas, "telemetry": telemetry},
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
            "temporal_constraint_ids": len(TEMPORAL_CONSTRAINT_IDS),
            "candidate_cases": len(results),
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
            "implemented_constraints": [
                "C-001",
                "C-002",
                "C-003",
                "C-004",
                "C-005",
                "C-006",
                "C-009",
                "C-010",
                "C-011",
            ],
            "deferred_constraints": ["C-007", "C-008"],
            "objective": "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED",
            "strategy": "NOT_IMPLEMENTED",
            "benchmark": "MODEL_DELTA_ONLY_NO_XS_S_M_BASELINE",
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
        report = run_temporal_model_checks(cast(Path, args.root))
    except Exception as error:  # CLI boundary emits sanitized failure evidence
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "error_type": type(error).__name__,
        }
        _write_report(cast(Path, args.report), report)
        print(f"FAIL CP-SAT temporal model: {type(error).__name__}", file=sys.stderr)
        return 1
    _write_report(cast(Path, args.report), report)
    counts = cast(JsonObject, report["counts"])
    print(
        "PASS CP-SAT temporal model: "
        f"checks={report['check_count']} constraints={counts['temporal_constraint_ids']} "
        f"oracle_cases={counts['tiny_oracle_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_temporal_model_checks"]
