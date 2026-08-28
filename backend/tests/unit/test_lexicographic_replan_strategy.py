"""TEST-REPLAN P4 lexicographic strategy and honest report evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from typing import cast

from app.domain.execution_contracts import (
    contract_fingerprint,
    replan_request_fingerprint,
    require_p4_document,
    solver_report_fingerprint,
)
from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat.core_model_check import synthetic_core_problem
from app.planning.backends.cp_sat.replan_backend import LexicographicReplanBackend
from app.planning.policy.contracts import SolveLimitsDocument
from app.planning.policy.delivery import simulation_solve_limits
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import (
    FreezeWindowFixture,
    build_freeze_window_fixture,
)
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanStrategy,
)
from app.planning.problem.hashing import problem_v2_hash_for


ROOT = Path(__file__).resolve().parents[3]
TEST_REPLAN_ID = "TEST-REPLAN"


def _limits(*, wall_time: float = 6.0) -> SolveLimitsDocument:
    return simulation_solve_limits(
        limits_id="LIMITS-TASK-P4-07-UNIT",
        limits_revision="1.0.0",
        source_record_id="LIMITS-TASK-P4-07-UNIT",
        max_wall_time_seconds=wall_time,
        max_workers=1,
        random_seed=20260828,
    )


def _limits_reference(limits: SolveLimitsDocument) -> dict[str, object]:
    return {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }


def _request(
    fixture: FreezeWindowFixture,
    projection: dict[str, object],
    limits: SolveLimitsDocument,
) -> dict[str, object]:
    document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/replan-request.v1.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["base_schedule_version"] = deepcopy(
        projection["base_schedule_version"]
    )
    document["new_snapshot"] = deepcopy(projection["new_snapshot"])
    document["new_snapshot_cutoff_at_utc"] = fixture.snapshot.document[
        "cutoff_at_utc"
    ]
    document["new_problem"] = deepcopy(projection["new_problem"])
    document["freeze_resolution"] = deepcopy(projection["freeze_resolution"])
    document["planning_policy"] = deepcopy(projection["planning_policy"])
    document["solve_limits"] = _limits_reference(limits)
    fingerprint = replan_request_fingerprint(document)
    document["request_fingerprint"] = fingerprint
    document["request_id"] = "replan-request-" + fingerprint.removeprefix("sha256:")
    require_p4_document(document)
    return document


def _assignment(
    problem: dict[str, object],
    *,
    operation_id: str,
    resource_id: str,
    start_tick: int,
    duration_ticks: int,
) -> dict[str, object]:
    horizon_start = parse_utc_instant(cast(str, problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    end_tick = start_tick + duration_ticks
    return {
        "operation_id": operation_id,
        "resource_id": resource_id,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "duration_ticks": duration_ticks,
        "start_at_utc": format_utc_instant(
            horizon_start + timedelta(seconds=start_tick * tick_seconds)
        ),
        "end_at_utc": format_utc_instant(
            horizon_start + timedelta(seconds=end_tick * tick_seconds)
        ),
        "duration_seconds": duration_ticks * tick_seconds,
        "lock_ids": [],
        "execution_fact_ids": [],
    }


def _projection(
    problem: dict[str, object],
    base: list[dict[str, object]],
    *,
    soft_locks: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    active = sorted(
        cast(str, operation["operation_id"])
        for operation in cast(list[dict[str, object]], problem["operation_instances"])
    )
    base_ids = sorted(cast(str, item["operation_id"]) for item in base)
    document: dict[str, object] = {
        "effective_lock_projection_version": "effective-lock-projection.v1",
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "base_schedule_version": {
            "schedule_version_version": "schedule-version.v1",
            "schedule_version_id": "schedule-version-p4-07-unit-base",
            "state": "PUBLISHED",
            "content_fingerprint": "sha256:" + "1" * 64,
        },
        "new_snapshot": {
            "document_version": "planning-snapshot.v2",
            "artifact_id": problem["snapshot_id"],
            "fingerprint": "sha256:" + "2" * 64,
        },
        "new_problem": {
            "document_version": "planning-problem.v2",
            "artifact_id": "planning-problem-v2-"
            + cast(str, problem["problem_hash"]).removeprefix("sha256:"),
            "fingerprint": problem["problem_hash"],
        },
        "planning_policy": {
            "planning_policy_version": "planning-policy.v2",
            "policy_id": "POLICY-P4-07-UNIT",
            "policy_revision": "1.0.0",
            "policy_fingerprint": "sha256:" + "3" * 64,
        },
        "freeze_resolution": {
            "freeze_policy_version": "freeze-policy.v1",
            "freeze_policy_id": "FREEZE-P4-07-UNIT",
            "freeze_policy_revision": "1.0.0",
            "freeze_policy_fingerprint": "sha256:" + "4" * 64,
            "source": {
                "source_system": "unit",
                "source_version": "1.0.0",
                "source_record_id": "unit",
            },
            "window_seconds": 1,
            "effective_from_utc": problem["horizon_start_utc"],
            "effective_until_utc": format_utc_instant(
                parse_utc_instant(cast(str, problem["horizon_start_utc"]))
                + timedelta(seconds=1)
            ),
            "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
            "effective_lock_ids": [],
        },
        "base_assignment_operation_ids": base_ids,
        "new_active_operation_ids": active,
        "completed_operation_ids": sorted(set(base_ids) - set(active)),
        "completed_protections": [],
        "added_operation_ids": sorted(set(active) - set(base_ids)),
        "outside_freeze_operation_ids": active,
        "running_protections": [],
        "explicit_hard_locks": [],
        "freeze_derived_hard_locks": [],
        "soft_locks": [] if soft_locks is None else soft_locks,
    }
    document["projection_fingerprint"] = contract_fingerprint(document)
    return document


def _two_demand_problem() -> dict[str, object]:
    problem = cast(
        dict[str, object],
        synthetic_core_problem(
            [[("RESOURCE-001", 2)], [("RESOURCE-001", 2)]],
            horizon_ticks=4,
            tag="P4-07-DELIVERY-STABILITY",
        ),
    )
    operations = cast(list[dict[str, object]], problem["operation_instances"])
    horizon_start = parse_utc_instant(cast(str, problem["horizon_start_utc"]))
    template = cast(list[dict[str, object]], problem["delivery_demands"])[0]
    demands: list[dict[str, object]] = []
    for index, (due_tick, weight) in enumerate(((4, 1), (2, 10))):
        demand = deepcopy(template)
        demand_id = f"DEMAND-P4-07-{index}"
        demand.update(
            {
                "demand_order_id": demand_id,
                "due_at_utc": format_utc_instant(
                    horizon_start + timedelta(seconds=due_tick * 60)
                ),
                "due_source_record_id": f"DUE-P4-07-{index}",
                "priority_weight": weight,
                "priority_source_system": "plantnexus-synthetic-policy",
                "priority_source_version": "1.0.0",
                "priority_source_record_id": f"PRIORITY-P4-07-{index}",
            }
        )
        operations[index]["demand_order_id"] = demand_id
        demands.append(demand)
    problem["delivery_demands"] = demands
    problem["problem_hash"] = problem_v2_hash_for(problem)
    return problem


def test_frozen_fact_and_lock_problem_runs_all_lexicographic_rounds() -> None:
    fixture = build_freeze_window_fixture(ROOT)
    limits = _limits()
    projection = project_effective_locks(
        snapshot=fixture.snapshot,
        problem=fixture.problem,
        base_schedule=fixture.base_schedule,
        policy=fixture.policy,
    ).document
    request = _request(fixture, projection, limits)

    result = LexicographicReplanStrategy().solve(
        fixture.problem.document,
        fixture.policy,
        limits,
        base_schedule=fixture.base_schedule,
        effective_locks=projection,
        replan_request=request,
        planning_run_id="PLANNING-RUN-TASK-P4-07-UNIT",
        code_commit="uncommitted",
    )

    report = result.solver_report
    assert report["solver_status"] == "OPTIMAL"
    assert report["candidate"] is not None
    assert len(result.round_reports) == 6
    assert len(result.validation_reports) == 6
    assert all(item["status"] == "PASS" for item in result.validation_reports)
    assert [
        item["objective_id"]
        for item in cast(list[dict[str, object]], report["objective_stage_results"])
    ] == ["OBJ-001", "OBJ-002", "OBJ-003"]
    assert report["report_fingerprint"] == solver_report_fingerprint(report)
    require_p4_document(report)


def test_delivery_precedes_stability_and_obj002_uses_exact_component_order() -> None:
    problem = _two_demand_problem()
    base = [
        _assignment(
            problem,
            operation_id="OP-000",
            resource_id="RESOURCE-001",
            start_tick=0,
            duration_ticks=2,
        ),
        _assignment(
            problem,
            operation_id="OP-001",
            resource_id="RESOURCE-001",
            start_tick=2,
            duration_ticks=2,
        ),
    ]
    soft = [
        {
            "protection_kind": "SOFT_LOCK",
            "protection_priority": 4,
            "reference_id": "LOCK-P4-07-SOFT-001",
            "operation_id": "OP-000",
            "resource_id": "RESOURCE-001",
            "start_at_utc": base[0]["start_at_utc"],
            "end_at_utc": base[0]["end_at_utc"],
            "source": {
                "source_system": "unit",
                "source_version": "1.0.0",
                "source_record_id": "unit",
            },
        }
    ]
    projection = _projection(problem, base, soft_locks=soft)

    result = LexicographicReplanBackend().solve_with_evidence(
        cast(object, problem),  # type: ignore[arg-type]
        base_assignments=base,
        effective_locks=projection,
        limits=_limits(),
    )
    candidate = cast(dict[str, object], result.candidate)
    assignments = {
        item["operation_id"]: item
        for item in cast(list[dict[str, object]], candidate["assignments"])
    }

    assert result.solver_status.value == "OPTIMAL"
    assert result.objective_values == {
        "delivery": 0,
        "stability": {
            "soft_lock_violations": 1,
            "changed_existing_operations": 2,
            "resource_changes": 0,
            "absolute_start_shift_seconds": 240,
        },
        "makespan": 240,
    }
    assert assignments["OP-001"]["start_tick"] == 0
    assert assignments["OP-000"]["start_tick"] == 2
    assert [item["component"] for item in result.round_reports[1:5]] == [
        "soft_lock_violations",
        "changed_existing_operations",
        "resource_changes",
        "absolute_start_shift_seconds",
    ]


def test_added_operation_has_zero_stability_cost_and_makespan_breaks_tie() -> None:
    problem = cast(
        dict[str, object],
        synthetic_core_problem(
            [[("RESOURCE-SLOW", 3), ("RESOURCE-FAST", 1)]],
            horizon_ticks=3,
            tag="P4-07-MAKESPAN",
        ),
    )
    demand = cast(list[dict[str, object]], problem["delivery_demands"])[0]
    demand["priority_source_system"] = "plantnexus-synthetic-policy"
    demand["priority_source_version"] = "1.0.0"
    problem["problem_hash"] = problem_v2_hash_for(problem)
    projection = _projection(problem, [])

    result = LexicographicReplanBackend().solve_with_evidence(
        cast(object, problem),  # type: ignore[arg-type]
        base_assignments=[],
        effective_locks=projection,
        limits=_limits(),
    )
    candidate = cast(dict[str, object], result.candidate)
    assignment = cast(list[dict[str, object]], candidate["assignments"])[0]

    assert result.objective_values == {
        "delivery": 0,
        "stability": {
            "soft_lock_violations": 0,
            "changed_existing_operations": 0,
            "resource_changes": 0,
            "absolute_start_shift_seconds": 0,
        },
        "makespan": 60,
    }
    assert assignment["resource_id"] == "RESOURCE-FAST"


def test_registered_id_is_exact() -> None:
    assert TEST_REPLAN_ID == "TEST-REPLAN"
