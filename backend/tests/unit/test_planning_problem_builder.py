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
    ImmutablePlanningProblem,
    PlanningProblemError,
    PlanningProblemErrorCode,
    build_planning_problem,
    canonical_problem_bytes,
    problem_hash_for,
    problem_hash_projection,
    verify_problem,
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
