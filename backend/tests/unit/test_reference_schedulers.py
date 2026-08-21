"""Unit coverage for TASK-P2-10 deterministic reference schedulers."""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import cast

import pytest

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.validation.problem_schedule_validator import (
    ProblemScheduleValidator,
)
from app.simulation.baselines.contracts import (
    ALGORITHM_IDENTITIES,
    REFERENCE_SCHEDULER_CONTRACT_VERSION,
    REFERENCE_SCHEDULER_POLICY_VERSION,
    ReferenceAlgorithm,
    ReferenceSchedulerStatus,
)
from app.simulation.baselines.reference_schedulers import (
    schedule_all_references,
    schedule_reference,
)
from app.simulation.scenarios.p2_correctness import (
    execute_correctness_case,
    load_correctness_cases,
)


ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _problems() -> dict[str, PlanningProblemDocumentV2]:
    return {
        case.scenario_id: cast(
            PlanningProblemDocumentV2,
            execute_correctness_case(case, root=ROOT).problem,
        )
        for case in load_correctness_cases(ROOT)
    }


def _assignment_at_zero(result: object) -> str:
    document = cast(dict[str, object], result)
    candidate = cast(dict[str, object], document["candidate"])
    assignments = cast(list[dict[str, object]], candidate["assignments"])
    return str(next(value["operation_id"] for value in assignments if value["start_tick"] == 0))


def _two_operation_problem(
    *,
    release_ticks: tuple[int, int],
    due_ticks: tuple[int, int],
    durations: tuple[int, int],
    priorities: tuple[int, int],
) -> PlanningProblemDocumentV2:
    problem = deepcopy(_problems()["P2-CALENDAR"])
    start = parse_utc_instant(problem["horizon_start_utc"])
    problem["horizon_end_utc"] = format_utc_instant(start + timedelta(minutes=10))
    problem["resource_unavailable_intervals"] = []
    demand_template = problem["delivery_demands"][0]
    operation_template = problem["operation_instances"][0]
    demands = []
    operations = []
    for index, label in enumerate(("A", "B")):
        demand = deepcopy(demand_template)
        demand_id = f"DEMAND-{label}"
        demand.update(
            {
                "demand_order_id": demand_id,
                "due_at_utc": format_utc_instant(
                    start + timedelta(minutes=due_ticks[index])
                ),
                "due_source_record_id": f"DUE-{label}",
                "priority_weight": priorities[index],
                "priority_source_record_id": f"PRIORITY-{label}",
            }
        )
        operation = deepcopy(operation_template)
        operation.update(
            {
                "operation_id": f"OP-{label}",
                "demand_order_id": demand_id,
                "release_at_utc": format_utc_instant(
                    start + timedelta(minutes=release_ticks[index])
                ),
                "material_ready_at_utc": format_utc_instant(start),
            }
        )
        option = operation["resource_options"][0]
        option["cycle_seconds_per_unit"] = durations[index]
        option["final_duration_seconds"] = durations[index]
        demands.append(demand)
        operations.append(operation)
    problem["delivery_demands"] = sorted(
        demands, key=lambda value: value["demand_order_id"]
    )
    problem["operation_instances"] = sorted(
        operations, key=lambda value: value["operation_id"]
    )
    problem["problem_hash"] = problem_v2_hash_for(problem)
    return problem


def test_algorithm_identities_and_tie_breaks_are_exact_and_versioned() -> None:
    assert REFERENCE_SCHEDULER_CONTRACT_VERSION == "reference-scheduler-contracts.v1"
    assert REFERENCE_SCHEDULER_POLICY_VERSION == "reference-scheduler-policy.v1"
    assert [identity.algorithm_id for identity in ALGORITHM_IDENTITIES.values()] == [
        "reference-fcfs.v1",
        "reference-edd.v1",
        "reference-spt.v1",
        "reference-priority-edd.v1",
        "reference-greedy-earliest-available-machine.v1",
    ]
    assert ALGORITHM_IDENTITIES[ReferenceAlgorithm.FCFS].operation_selection == (
        "release_at_utc",
        "demand_order_id",
        "operation_id",
    )
    assert ALGORITHM_IDENTITIES[ReferenceAlgorithm.EDD].operation_selection == (
        "due_at_utc",
        "release_at_utc",
        "demand_order_id",
        "operation_id",
    )
    assert ALGORITHM_IDENTITIES[ReferenceAlgorithm.SPT].operation_selection == (
        "minimum_duration_seconds",
        "due_at_utc",
        "operation_id",
    )
    assert ALGORITHM_IDENTITIES[
        ReferenceAlgorithm.PRIORITY_EDD
    ].operation_selection[0] == "negative_priority_weight"


@pytest.mark.parametrize(
    ("algorithm", "problem", "expected_first"),
    (
        (
            ReferenceAlgorithm.FCFS,
            _two_operation_problem(
                release_ticks=(1, 0),
                due_ticks=(5, 5),
                durations=(60, 60),
                priorities=(1, 1),
            ),
            "OP-B",
        ),
        (
            ReferenceAlgorithm.EDD,
            _two_operation_problem(
                release_ticks=(0, 0),
                due_ticks=(2, 5),
                durations=(60, 60),
                priorities=(1, 1),
            ),
            "OP-A",
        ),
        (
            ReferenceAlgorithm.SPT,
            _two_operation_problem(
                release_ticks=(0, 0),
                due_ticks=(5, 5),
                durations=(120, 60),
                priorities=(1, 1),
            ),
            "OP-B",
        ),
        (
            ReferenceAlgorithm.PRIORITY_EDD,
            _two_operation_problem(
                release_ticks=(0, 0),
                due_ticks=(1, 5),
                durations=(60, 60),
                priorities=(1, 3),
            ),
            "OP-B",
        ),
        (
            ReferenceAlgorithm.GREEDY_EARLIEST_AVAILABLE_MACHINE,
            _two_operation_problem(
                release_ticks=(0, 0),
                due_ticks=(5, 5),
                durations=(120, 60),
                priorities=(1, 1),
            ),
            "OP-B",
        ),
    ),
)
def test_each_algorithm_executes_its_frozen_primary_ordering(
    algorithm: ReferenceAlgorithm,
    problem: PlanningProblemDocumentV2,
    expected_first: str,
) -> None:
    result = schedule_reference(problem, algorithm)

    assert result["status"] is ReferenceSchedulerStatus.FEASIBLE
    assert _assignment_at_zero(result) == expected_first


def test_all_five_algorithms_produce_complete_deterministic_valid_candidates() -> None:
    candidate_count = 0
    for problem in _problems().values():
        for algorithm in ReferenceAlgorithm:
            first = schedule_reference(problem, algorithm)
            second = schedule_reference(problem, algorithm)
            assert first["status"] is ReferenceSchedulerStatus.FEASIBLE
            assert first["candidate"] == second["candidate"]
            assert first["validation_report"] == second["validation_report"]
            assert first["metrics"]["weighted_tardiness_seconds"] == second["metrics"][
                "weighted_tardiness_seconds"
            ]
            assert first["metrics"]["makespan_seconds"] == second["metrics"][
                "makespan_seconds"
            ]
            candidate = first["candidate"]
            assert candidate is not None
            assert len(candidate["assignments"]) == len(problem["operation_instances"])
            assert first["metrics"]["unscheduled_operation_count"] == 0
            report = ProblemScheduleValidator().validate(problem, candidate)
            assert report["status"] == "PASS"
            assert report["hard_violation_count"] == 0
            assert first["non_production"] is True
            assert first["optimality_claim"] == "NONE"
            candidate_count += 1
    assert candidate_count == 35


def test_calendar_transport_running_and_hard_lock_facts_are_preserved() -> None:
    calendar = schedule_reference(_problems()["P2-CALENDAR"], ReferenceAlgorithm.FCFS)
    assert calendar["candidate"] is not None
    assert calendar["candidate"]["assignments"][0]["start_tick"] == 2

    cross_problem = _problems()["P2-CROSS-WORKSHOP"]
    cross = schedule_reference(cross_problem, ReferenceAlgorithm.FCFS)
    assert cross["candidate"] is not None
    assignments = {
        value["operation_id"]: value for value in cross["candidate"]["assignments"]
    }
    edge = cross_problem["precedence_edges"][0]
    assert assignments[edge["successor_operation_id"]]["start_tick"] == (
        assignments[edge["predecessor_operation_id"]]["end_tick"] + 2
    )

    running_problem = _problems()["P2-RUNNING"]
    running = schedule_reference(running_problem, ReferenceAlgorithm.EDD)
    assert running["candidate"] is not None
    running_operation = next(
        value
        for value in running_problem["operation_instances"]
        if value["status"] == "RUNNING"
    )
    running_assignment = next(
        value
        for value in running["candidate"]["assignments"]
        if value["operation_id"] == running_operation["operation_id"]
    )
    assert running_assignment["resource_id"] == cast(
        str, running_operation.get("assigned_resource_id")
    )
    assert (running_assignment["start_tick"], running_assignment["end_tick"]) == (0, 2)

    locked_problem = _problems()["P2-HARD-LOCK"]
    locked = schedule_reference(locked_problem, ReferenceAlgorithm.SPT)
    assert locked["candidate"] is not None
    lock = locked_problem["operation_locks"][0]
    locked_assignment = locked["candidate"]["assignments"][0]
    assert locked_assignment["resource_id"] == lock["resource_id"]
    assert (locked_assignment["start_tick"], locked_assignment["end_tick"]) == (1, 3)
    assert locked_assignment["lock_ids"] == [lock["lock_id"]]


def test_blocked_horizon_returns_failure_without_partial_or_false_certificate() -> None:
    problem = deepcopy(_problems()["P2-CALENDAR"])
    resource = problem["resources"][0]
    problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": resource["calendar_id"],
            "resource_id": resource["resource_id"],
            "start_utc": problem["horizon_start_utc"],
            "end_utc": problem["horizon_end_utc"],
        }
    ]
    problem["problem_hash"] = problem_v2_hash_for(problem)

    results = schedule_all_references(problem)

    assert len(results) == 5
    for result in results:
        assert result["status"] is ReferenceSchedulerStatus.HEURISTIC_FAILURE
        assert result["candidate"] is None
        assert result["validation_report"] is None
        assert result["metrics"]["scheduled_operation_count"] == 0
        assert result["metrics"]["unscheduled_operation_count"] == 1
        assert result["failure"] is not None


def test_invalid_problem_hash_is_rejected_before_scheduling() -> None:
    problem = deepcopy(_problems()["P2-CALENDAR"])
    problem["problem_hash"] = "sha256:" + "0" * 64

    result = schedule_reference(problem, ReferenceAlgorithm.FCFS)

    assert result["status"] is ReferenceSchedulerStatus.INVALID_PROBLEM
    assert result["candidate"] is None
    assert result["failure"] is not None
    assert result["failure"]["code"] == "INVALID_PROBLEM"


def test_baseline_modules_have_no_direct_solver_backend_dependency() -> None:
    baseline_root = ROOT / "backend" / "app" / "simulation" / "baselines"
    for path in sorted(baseline_root.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        assert not any(value.startswith("app.planning.backends") for value in imported)
        assert "or" + "tools" not in source.lower()
        assert "cp_" + "model" not in source.lower()
