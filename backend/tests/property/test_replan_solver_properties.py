"""TEST-PROPERTY tiny exhaustive/oracle checks for P4 replan objectives."""

from __future__ import annotations

from typing import cast

from hypothesis import given, settings, strategies as st

from app.domain.execution_contracts import contract_fingerprint
from app.planning.backends.cp_sat.core_model_check import synthetic_core_problem
from app.planning.backends.cp_sat.replan_backend import LexicographicReplanBackend
from app.planning.policy.delivery import simulation_solve_limits
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import problem_v2_hash_for


TEST_PROPERTY_ID = "TEST-PROPERTY"


def _projection(problem: PlanningProblemDocumentV2) -> dict[str, object]:
    active = sorted(operation["operation_id"] for operation in problem["operation_instances"])
    document: dict[str, object] = {
        "effective_lock_projection_version": "effective-lock-projection.v1",
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "base_schedule_version": {
            "schedule_version_version": "schedule-version.v1",
            "schedule_version_id": "schedule-version-p4-07-property-base",
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
            + problem["problem_hash"].removeprefix("sha256:"),
            "fingerprint": problem["problem_hash"],
        },
        "planning_policy": {
            "planning_policy_version": "planning-policy.v2",
            "policy_id": "POLICY-P4-07-PROPERTY",
            "policy_revision": "1.0.0",
            "policy_fingerprint": "sha256:" + "3" * 64,
        },
        "freeze_resolution": {},
        "base_assignment_operation_ids": [],
        "new_active_operation_ids": active,
        "completed_operation_ids": [],
        "completed_protections": [],
        "added_operation_ids": active,
        "outside_freeze_operation_ids": active,
        "running_protections": [],
        "explicit_hard_locks": [],
        "freeze_derived_hard_locks": [],
        "soft_locks": [],
    }
    document["projection_fingerprint"] = contract_fingerprint(document)
    return document


def _limits():  # type: ignore[no-untyped-def]
    return simulation_solve_limits(
        limits_id="LIMITS-TASK-P4-07-PROPERTY",
        limits_revision="1.0.0",
        source_record_id="LIMITS-TASK-P4-07-PROPERTY",
        max_wall_time_seconds=3.0,
        max_workers=1,
        random_seed=20260828,
    )


@settings(max_examples=12, deadline=None)
@given(
    st.tuples(st.integers(min_value=1, max_value=4), st.integers(min_value=1, max_value=4)).filter(
        lambda values: values[0] != values[1]
    )
)
def test_added_operation_makespan_matches_tiny_exhaustive_resource_oracle(
    durations: tuple[int, int],
) -> None:
    problem = synthetic_core_problem(
        [[("RESOURCE-A", durations[0]), ("RESOURCE-B", durations[1])]],
        horizon_ticks=max(durations),
        tag=f"P4-07-PROPERTY-{durations[0]}-{durations[1]}",
    )
    problem["delivery_demands"][0][
        "priority_source_system"
    ] = "plantnexus-synthetic-policy"
    problem["delivery_demands"][0]["priority_source_version"] = "1.0.0"
    problem["problem_hash"] = problem_v2_hash_for(cast(dict[str, object], problem))
    projection = _projection(problem)

    first = LexicographicReplanBackend().solve_with_evidence(
        problem,
        base_assignments=[],
        effective_locks=projection,
        limits=_limits(),
    )
    replay = LexicographicReplanBackend().solve_with_evidence(
        problem,
        base_assignments=[],
        effective_locks=projection,
        limits=_limits(),
    )
    candidate = cast(dict[str, object], first.candidate)
    assignment = cast(list[dict[str, object]], candidate["assignments"])[0]

    assert first.solver_status.value == "OPTIMAL"
    assert cast(dict[str, object], first.objective_values)["makespan"] == min(
        durations
    ) * problem["tick_seconds"]
    assert assignment["duration_ticks"] == min(durations)
    assert cast(dict[str, object], first.objective_values) == replay.objective_values
    assert candidate["candidate_fingerprint"] == cast(
        dict[str, object], replay.candidate
    )["candidate_fingerprint"]
    assert all(report["status"] == "PASS" for report in first.validation_reports)


def test_registered_id_is_exact() -> None:
    assert TEST_PROPERTY_ID == "TEST-PROPERTY"
