"""TEST-PROBLEM-REPLAY-001 unit evidence for Problem construction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.data_validation import validate_import_package
from app.domain.types import duration_to_ticks
from app.normalization.order_expansion import expand_orders
from app.planning.problem import (
    PROBLEM_BUILDER_VERSION,
    PROBLEM_BUILDER_VERSION_V2,
    ImmutablePlanningProblem,
    PlanningProblemError,
    PlanningProblemErrorCode,
    build_planning_problem,
    build_planning_problem_v2,
    canonical_problem_bytes,
    canonical_problem_v2_bytes,
    problem_hash_for,
    problem_hash_projection,
    problem_v2_hash_for,
    problem_v2_hash_projection,
    verify_problem,
    verify_problem_v2,
)
from app.snapshots import (
    ImmutablePlanningSnapshot,
    build_planning_snapshot,
    import_package_id_for,
)

ROOT = Path(__file__).resolve().parents[3]
CUTOFF = "2026-08-20T00:00:00Z"
HORIZON_END = "2026-08-21T00:00:00Z"


def _snapshot(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> ImmutablePlanningSnapshot:
    document = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if mutate is not None:
        mutate(document)
    document["package_id"] = import_package_id_for(document)
    quality = cast(dict[str, object], validate_import_package(document).document)
    expansion = expand_orders(document, quality)  # type: ignore[arg-type]
    return build_planning_snapshot(
        document,
        quality,
        expansion,
        cutoff_at_utc=CUTOFF,
    )


def _problem(
    snapshot: ImmutablePlanningSnapshot | None = None,
    *,
    tick_seconds: int = 60,
    horizon_end_utc: str = HORIZON_END,
) -> ImmutablePlanningProblem:
    return build_planning_problem(
        snapshot or _snapshot(),
        problem_builder_version=PROBLEM_BUILDER_VERSION,
        tick_seconds=tick_seconds,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=horizon_end_utc,
    )


V2_PRIORITY_FACTS: dict[str, Mapping[str, object]] = {
    "DEMAND-001": {
        "priority_weight": 2,
        "source_system": "plantnexus-synthetic-policy",
        "source_version": "1.0.0",
        "source_record_id": "SIM-P2-DELIVERY-PRIORITY-001",
    }
}


def _prepare_v2_document(document: dict[str, Any]) -> None:
    fact = document["records"]["execution_facts"][0]
    fact["status"] = "COMPLETED"
    fact.pop("remaining_quantity")
    fact.pop("remaining_seconds")
    fact["actual_end_at_utc"] = "2026-08-19T00:05:00Z"
    fact["completed_quantity"] = 10

    lock = document["records"]["operation_locks"][0]
    lock["routing_operation_id"] = "ROUTING-OP-002"
    lock["start_at_utc"] = CUTOFF
    lock["end_at_utc"] = "2026-08-20T02:00:00Z"
    soft_lock = deepcopy(lock)
    soft_lock["lock_id"] = "LOCK-002"
    soft_lock["lock_type"] = "SOFT_LOCK"
    soft_lock["start_at_utc"] = "2026-08-20T03:00:00Z"
    soft_lock["end_at_utc"] = "2026-08-22T02:00:00Z"
    soft_lock["source"]["source_record_id"] = "SRC-LOCK-002"
    document["records"]["operation_locks"].append(soft_lock)


def _snapshot_v2(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> ImmutablePlanningSnapshot:
    def combined(document: dict[str, Any]) -> None:
        _prepare_v2_document(document)
        if mutate is not None:
            mutate(document)

    return _snapshot(combined)


def _problem_v2(
    *,
    mutate: Callable[[dict[str, Any]], None] | None = None,
    priority_facts: Mapping[str, Mapping[str, object]] = V2_PRIORITY_FACTS,
):  # type: ignore[no-untyped-def]
    return build_planning_problem_v2(
        _snapshot_v2(mutate),
        priority_facts=priority_facts,
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=60,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=HORIZON_END,
    )


def test_builder_projects_running_options_edges_and_platform_capabilities() -> None:
    problem = _problem()
    document = problem.document

    assert problem.problem_hash == (
        "sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72"
    )
    assert json.loads(problem.canonical_bytes) == document
    assert document["resource_ids"] == ["RESOURCE-001"]
    assert document["resource_unavailable_intervals"] == []
    assert document["required_capabilities"] == [
        "DAG_ROUTING",
        "RELEASE_AND_MATERIAL_GATE",
        "RUNNING_OPERATION",
    ]
    assert len(document["operation_instances"]) == 2
    running = next(
        operation
        for operation in document["operation_instances"]
        if operation["status"] == "RUNNING"
    )
    assert running.get("actual_start_at_utc") == "2026-08-18T23:55:00Z"
    assert running.get("assigned_resource_id") == "RESOURCE-001"
    assert running.get("remaining_seconds") == 180
    assert duration_to_ticks(cast(int, running.get("remaining_seconds")), 60) == 3
    assert running["resource_options"][0] == {
        "resource_id": "RESOURCE-001",
        "setup_seconds": 120,
        "cycle_seconds_per_unit": 30,
        "final_duration_seconds": 420,
        "duration_source": "schema_sample_explicit_duration",
        "source_version": "1.0.0",
    }
    assert len(document["precedence_edges"]) == 1
    assert document["precedence_edges"][0]["transport_lag_seconds"] == 60
    assert document["precedence_edges"][0].get("max_lag_seconds") == 3600
    verify_problem(problem)


def test_replay_order_self_hash_and_runtime_noise_are_deterministic() -> None:
    first = _problem()
    second = _problem()
    reordered = cast(dict[str, Any], deepcopy(first.document))
    reordered["resource_ids"].reverse()
    reordered["operation_instances"].reverse()
    reordered["precedence_edges"].reverse()
    reordered["resource_unavailable_intervals"].reverse()
    reordered["required_capabilities"].reverse()
    for operation in reordered["operation_instances"]:
        operation["resource_options"].reverse()
    noisy = cast(dict[str, object], deepcopy(reordered))
    noisy["problem_hash"] = "sha256:" + "0" * 64
    noisy["generated_at_utc"] = "2099-01-01T00:00:00Z"
    noisy["run_id"] = "ignored-runtime-noise"

    assert first == second
    assert canonical_problem_bytes(reordered) == first.canonical_bytes
    assert problem_hash_for(noisy) == first.problem_hash
    projection = problem_hash_projection(noisy)
    projected_problem = cast(Mapping[str, object], projection["problem"])
    assert "problem_hash" not in projected_problem
    assert "generated_at_utc" not in projected_problem
    assert projection["problem_hash_projection_version"] == (
        "planning-problem-hash-projection.v1"
    )


def test_snapshot_fact_tick_horizon_and_builder_version_are_hash_sensitive() -> None:
    baseline = _problem()
    changed_tick = _problem(tick_seconds=30)
    changed_horizon = _problem(horizon_end_utc="2026-08-22T00:00:00Z")

    def change_remaining(document: dict[str, Any]) -> None:
        document["records"]["execution_facts"][0]["remaining_seconds"] = 181

    changed_fact = _problem(_snapshot(change_remaining))
    changed_version = cast(dict[str, object], deepcopy(baseline.document))
    changed_version["problem_builder_version"] = "planning-problem-builder.v2"

    assert changed_tick.problem_hash != baseline.problem_hash
    assert changed_horizon.problem_hash != baseline.problem_hash
    assert changed_fact.problem_hash != baseline.problem_hash
    assert changed_fact.snapshot_id != baseline.snapshot_id
    assert problem_hash_for(changed_version) != baseline.problem_hash


def test_completed_operations_are_excluded_without_cross_boundary_edges() -> None:
    def complete_first_operation(document: dict[str, Any]) -> None:
        fact = document["records"]["execution_facts"][0]
        fact["status"] = "COMPLETED"
        fact.pop("remaining_quantity")
        fact.pop("remaining_seconds")
        fact["actual_end_at_utc"] = "2026-08-19T00:05:00Z"
        fact["completed_quantity"] = 10
        document["records"]["routing_precedence_edges"] = []

    problem = _problem(_snapshot(complete_first_operation))

    assert len(problem.document["operation_instances"]) == 1
    assert problem.document["operation_instances"][0]["status"] == "NOT_STARTED"
    assert problem.document["precedence_edges"] == []
    assert "RUNNING_OPERATION" not in problem.document["required_capabilities"]


def test_calendar_intervals_intersecting_horizon_are_projected_without_clipping() -> None:
    def move_calendar_into_horizon(document: dict[str, Any]) -> None:
        interval = document["records"]["calendars"][0]["unavailable_intervals"][0]
        interval["start_at_utc"] = "2026-08-20T08:00:00Z"
        interval["end_at_utc"] = "2026-08-20T09:00:00Z"

    problem = _problem(_snapshot(move_calendar_into_horizon))

    assert problem.document["resource_unavailable_intervals"] == [
        {
            "resource_id": "RESOURCE-001",
            "start_utc": "2026-08-20T08:00:00Z",
            "end_utc": "2026-08-20T09:00:00Z",
        }
    ]
    assert "MACHINE_CALENDAR" in problem.document["required_capabilities"]


def test_builder_rejects_invalid_version_tick_cutoff_and_truncating_horizon() -> None:
    snapshot = _snapshot()
    common = {
        "snapshot": snapshot,
        "problem_builder_version": PROBLEM_BUILDER_VERSION,
        "tick_seconds": 60,
        "horizon_start_utc": CUTOFF,
        "horizon_end_utc": HORIZON_END,
    }
    cases = (
        ({**common, "problem_builder_version": "planning-problem-builder.v2"}, PlanningProblemErrorCode.INVALID_BUILDER_VERSION),
        ({**common, "tick_seconds": 0}, PlanningProblemErrorCode.INVALID_BUILD_CONFIG),
        ({**common, "horizon_start_utc": "2026-08-20T00:00:01Z"}, PlanningProblemErrorCode.INVALID_BUILD_CONFIG),
        ({**common, "horizon_end_utc": "2026-08-20T00:02:00Z"}, PlanningProblemErrorCode.INVALID_BUILD_CONFIG),
    )
    for arguments, expected_code in cases:
        with pytest.raises(PlanningProblemError) as failure:
            build_planning_problem(**arguments)  # type: ignore[arg-type]
        assert failure.value.code is expected_code
        assert failure.value.category.value != "INFEASIBLE"


def test_builder_rejects_active_lock_and_completed_active_edge_without_hiding_facts() -> None:
    def active_lock(document: dict[str, Any]) -> None:
        lock = document["records"]["operation_locks"][0]
        lock["start_at_utc"] = "2026-08-20T00:00:00Z"
        lock["end_at_utc"] = "2026-08-20T00:03:00Z"

    with pytest.raises(PlanningProblemError) as lock_failure:
        _problem(_snapshot(active_lock))
    assert lock_failure.value.code is PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT
    assert lock_failure.value.category.value == "UNSUPPORTED_CAPABILITY"

    def completed_predecessor(document: dict[str, Any]) -> None:
        fact = document["records"]["execution_facts"][0]
        fact["status"] = "COMPLETED"
        fact.pop("remaining_quantity")
        fact.pop("remaining_seconds")
        fact["actual_end_at_utc"] = "2026-08-19T00:05:00Z"
        fact["completed_quantity"] = 10

    with pytest.raises(PlanningProblemError) as edge_failure:
        _problem(_snapshot(completed_predecessor))
    assert edge_failure.value.code is PlanningProblemErrorCode.UNSUPPORTED_PROBLEM_FACT


def test_verify_rejects_tampered_bytes_and_problem_is_immutable() -> None:
    problem = _problem()
    changed = cast(dict[str, object], deepcopy(problem.document))
    changed["tick_seconds"] = 61
    tampered = ImmutablePlanningProblem(
        canonical_bytes=canonical_problem_bytes(changed),
        problem_hash=problem.problem_hash,
        snapshot_id=problem.snapshot_id,
        problem_builder_version=problem.problem_builder_version,
    )
    with pytest.raises(PlanningProblemError) as failure:
        verify_problem(tampered)
    assert failure.value.code is PlanningProblemErrorCode.HASH_MISMATCH

    copy = problem.document
    copy["resource_ids"].append("MUTATED")
    assert problem.document["resource_ids"] == ["RESOURCE-001"]
    with pytest.raises(AttributeError):
        problem.problem_hash = "sha256:" + "0" * 64  # type: ignore[misc]


def test_verify_rejects_a_content_hashed_active_precedence_cycle() -> None:
    problem = _problem()
    cyclic = cast(dict[str, Any], deepcopy(problem.document))
    original = cyclic["precedence_edges"][0]
    cyclic["precedence_edges"].append(
        {
            "predecessor_operation_id": original["successor_operation_id"],
            "successor_operation_id": original["predecessor_operation_id"],
            "min_lag_seconds": 0,
            "transport_lag_seconds": 0,
        }
    )
    cyclic["problem_hash"] = problem_hash_for(cyclic)
    invalid = ImmutablePlanningProblem(
        canonical_bytes=canonical_problem_bytes(cyclic),
        problem_hash=cyclic["problem_hash"],
        snapshot_id=cyclic["snapshot_id"],
        problem_builder_version=cyclic["problem_builder_version"],
    )

    with pytest.raises(PlanningProblemError) as failure:
        verify_problem(invalid)
    assert failure.value.code is PlanningProblemErrorCode.MODEL_INVALID
    assert failure.value.field == "precedence_edges"


def test_v2_projects_sourced_demands_resources_locks_and_historical_edge() -> None:
    first = _problem_v2()
    second = _problem_v2()
    document = first.document
    published_sample = json.loads(
        (ROOT / "schemas/samples/planning-problem.v2.synthetic.json").read_text(
            encoding="utf-8"
        )
    )

    assert first == second
    assert first.problem_hash == (
        "sha256:9927418a446dd046ddd1d835643da03fbf5cdcf8ca246ba22c3700563a17e9e8"
    )
    assert document == published_sample
    assert document["delivery_demands"] == [
        {
            "demand_order_id": "DEMAND-001",
            "due_at_utc": "2026-08-20T00:00:00Z",
            "due_source_record_id": "SRC-DEMAND-001",
            "due_source_system": "schema_sample",
            "due_source_version": "1.0.0",
            "priority_source_record_id": "SIM-P2-DELIVERY-PRIORITY-001",
            "priority_source_system": "plantnexus-synthetic-policy",
            "priority_source_version": "1.0.0",
            "priority_weight": 2,
        }
    ]
    assert document["resources"][0] == {
        "calendar_id": "CALENDAR-001",
        "capabilities": ["CUTTING"],
        "capacity": 1,
        "factory_id": "FACTORY-001",
        "production_line_id": "LINE-001",
        "resource_code": "R001",
        "resource_group_id": "GROUP-001",
        "resource_id": "RESOURCE-001",
        "resource_type": "MACHINE",
        "status": "AVAILABLE",
        "workshop_id": "WORKSHOP-001",
    }
    assert len(document["operation_instances"]) == 1
    assert len(document["historical_completion_anchors"]) == 1
    anchor = document["historical_completion_anchors"][0]
    edge = document["precedence_edges"][0]
    assert edge["predecessor_operation_id"] == anchor["operation_id"]
    assert edge["successor_operation_id"] == document["operation_instances"][0][
        "operation_id"
    ]
    assert [lock["lock_type"] for lock in document["operation_locks"]] == [
        "HARD_LOCK",
        "SOFT_LOCK",
    ]
    assert document["operation_locks"][1]["end_at_utc"] > document[
        "horizon_end_utc"
    ]
    assert "HARD_SOFT_LOCK" in document["required_capabilities"]
    verify_problem_v2(first)


def test_v2_hash_is_order_independent_but_covers_every_new_fact_class() -> None:
    baseline = _problem_v2()
    reordered = cast(dict[str, Any], deepcopy(baseline.document))
    for collection in (
        "delivery_demands",
        "resources",
        "operation_instances",
        "historical_completion_anchors",
        "precedence_edges",
        "operation_locks",
        "resource_unavailable_intervals",
        "required_capabilities",
    ):
        reordered[collection].reverse()
    reordered["operation_instances"][0]["resource_options"].reverse()
    reordered["operation_instances"][0]["required_capabilities"].reverse()
    reordered["resources"][0]["capabilities"].reverse()
    reordered["problem_hash"] = "ignored-self-hash"
    reordered["runtime_nonce"] = "ignored-runtime-noise"

    assert problem_v2_hash_for(reordered) == baseline.problem_hash
    reordered["problem_hash"] = baseline.problem_hash
    assert canonical_problem_v2_bytes(reordered) == baseline.canonical_bytes
    projection = problem_v2_hash_projection(reordered)
    assert projection["problem_hash_projection_version"] == (
        "planning-problem-hash-projection.v2"
    )
    assert "problem_hash" not in cast(Mapping[str, object], projection["problem"])

    changed_priority = _problem_v2(
        priority_facts={
            "DEMAND-001": {**V2_PRIORITY_FACTS["DEMAND-001"], "priority_weight": 3}
        }
    )

    def change_due(document: dict[str, Any]) -> None:
        document["records"]["demand_orders"][0]["due_at_utc"] = (
            "2026-08-21T00:00:00Z"
        )

    def change_resource(document: dict[str, Any]) -> None:
        document["records"]["resources"][0]["status"] = "MAINTENANCE"

    def change_anchor(document: dict[str, Any]) -> None:
        document["records"]["execution_facts"][0]["actual_end_at_utc"] = (
            "2026-08-19T00:06:00Z"
        )

    def change_lock(document: dict[str, Any]) -> None:
        document["records"]["operation_locks"][0]["end_at_utc"] = (
            "2026-08-20T02:01:00Z"
        )

    changed_hashes = {
        changed_priority.problem_hash,
        _problem_v2(mutate=change_due).problem_hash,
        _problem_v2(mutate=change_resource).problem_hash,
        _problem_v2(mutate=change_anchor).problem_hash,
        _problem_v2(mutate=change_lock).problem_hash,
    }
    assert baseline.problem_hash not in changed_hashes
    assert len(changed_hashes) == 5


@pytest.mark.parametrize(
    "priority_facts",
    [
        {},
        {
            **V2_PRIORITY_FACTS,
            "DEMAND-EXTRA": {
                "priority_weight": 1,
                "source_system": "synthetic",
                "source_version": "1.0.0",
                "source_record_id": "EXTRA",
            },
        },
        {
            "DEMAND-001": {
                **V2_PRIORITY_FACTS["DEMAND-001"],
                "priority_weight": True,
            }
        },
        {
            "DEMAND-001": {
                "priority_weight": 1,
                "source_system": "synthetic",
                "source_version": "",
                "source_record_id": "MISSING-VERSION",
            }
        },
    ],
)
def test_v2_rejects_missing_extra_boolean_and_unversioned_priority(
    priority_facts: Mapping[str, Mapping[str, object]],
) -> None:
    with pytest.raises(PlanningProblemError) as failure:
        _problem_v2(priority_facts=priority_facts)
    assert failure.value.code is PlanningProblemErrorCode.INVALID_PRIORITY_FACT
    assert failure.value.category.value == "DATA_ERROR"


def test_v2_excludes_expired_locks_and_rejects_future_historical_anchor() -> None:
    def expire_hard_lock(document: dict[str, Any]) -> None:
        lock = document["records"]["operation_locks"][0]
        lock["start_at_utc"] = "2026-08-19T23:00:00Z"
        lock["end_at_utc"] = CUTOFF

    problem = _problem_v2(mutate=expire_hard_lock)
    assert [lock["lock_id"] for lock in problem.document["operation_locks"]] == [
        "LOCK-002"
    ]

    def future_completion(document: dict[str, Any]) -> None:
        document["records"]["execution_facts"][0]["actual_end_at_utc"] = (
            "2026-08-20T00:01:00Z"
        )

    with pytest.raises(PlanningProblemError) as failure:
        _problem_v2(mutate=future_completion)
    assert failure.value.code is PlanningProblemErrorCode.INVALID_HISTORICAL_FACT


def test_problem_package_has_no_solver_orm_api_or_persistence_dependency() -> None:
    source_root = ROOT / "backend/app/planning/problem"
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(source_root.glob("*.py"))
    ).lower()
    for forbidden in (
        "ortools",
        "cp_model",
        "intervalvar",
        "sqlalchemy",
        "fastapi",
        "app.infrastructure",
        "app.api",
    ):
        assert forbidden not in combined
