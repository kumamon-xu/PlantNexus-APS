"""TASK-P4-05 versioned freeze and effective-lock projection tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from app.planning.policy.freeze_window import (
    FREEZE_INTERVAL_SEMANTICS,
    SIMULATION_FREEZE_WINDOW_SECONDS,
    FreezePolicyError,
    FreezePolicyFailure,
    resolve_simulation_freeze_policy,
)
from app.planning.problem.freeze_projection import (
    FreezeProjectionError,
    FreezeProjectionFailure,
    project_effective_locks,
)
from app.planning.problem.freeze_window_check import (
    FreezeWindowFixture,
    build_freeze_window_fixture,
    move_base_assignment,
    omit_base_assignment,
    rehash_problem_v2,
)
from app.planning.validation.freeze_window_precheck import (
    validate_freeze_window_projection,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_FREEZE_ID = "TEST-FREEZE-WINDOW-001"
TEST_RUNNING_ID = "TEST-RUNNING"
TEST_LOCK_ID = "TEST-INF-LOCK"


@pytest.fixture(scope="module")
def primary() -> FreezeWindowFixture:
    return build_freeze_window_fixture(ROOT)


@pytest.fixture(scope="module")
def completed() -> FreezeWindowFixture:
    return build_freeze_window_fixture(ROOT, completed=True)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def test_versioned_policy_resolves_only_from_verified_snapshot_cutoff(
    primary: FreezeWindowFixture,
) -> None:
    """TEST-FREEZE-WINDOW-001 anchor/source/version contract."""

    resolved = resolve_simulation_freeze_policy(primary.policy, primary.snapshot)
    cutoff = cast(str, primary.snapshot.document["cutoff_at_utc"])

    assert resolved.window_seconds == SIMULATION_FREEZE_WINDOW_SECONDS == 900
    assert resolved.effective_from_utc == cutoff
    assert resolved.effective_until_utc == _format(
        _utc(cutoff) + timedelta(seconds=SIMULATION_FREEZE_WINDOW_SECONDS)
    )
    assert resolved.document()["interval_semantics"] == FREEZE_INTERVAL_SEMANTICS
    assert resolved.freeze_policy_fingerprint.startswith("sha256:")

    production = cast(dict[str, object], deepcopy(primary.policy))
    production["data_plane"] = "PRODUCTION"
    with pytest.raises(FreezePolicyError) as rejected:
        resolve_simulation_freeze_policy(production, primary.snapshot)
    assert rejected.value.reason is FreezePolicyFailure.PRODUCTION_NOT_AUTHORIZED


def test_projection_preserves_inputs_and_orders_effective_protections(
    primary: FreezeWindowFixture,
) -> None:
    """TEST-RUNNING / TEST-INF-LOCK authoritative priority evidence."""

    snapshot_bytes = primary.snapshot.canonical_bytes
    problem_bytes = primary.problem.canonical_bytes
    base_before = deepcopy(primary.base_schedule)
    first = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
    )
    replay = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=deepcopy(primary.policy),
    )
    document = first.document

    assert primary.snapshot.canonical_bytes == snapshot_bytes
    assert primary.problem.canonical_bytes == problem_bytes
    assert primary.base_schedule == base_before
    assert first.canonical_bytes == replay.canonical_bytes
    assert first.projection_fingerprint == replay.projection_fingerprint
    assert document["completed_protections"] == []
    running = cast(list[dict[str, object]], document["running_protections"])
    hard = cast(list[dict[str, object]], document["explicit_hard_locks"])
    derived = cast(list[dict[str, object]], document["freeze_derived_hard_locks"])
    soft = cast(list[dict[str, object]], document["soft_locks"])
    assert len(running) == 1
    assert running[0]["operation_id"] == primary.first_operation_id
    assert running[0]["protection_priority"] == 1
    assert cast(dict[str, object], running[0]["fact_evidence"])["status"] == "RUNNING"
    assert len(hard) == 2
    assert all(item["protection_priority"] == 2 for item in hard)
    assert len(derived) == 1
    assert derived[0]["operation_id"] == primary.second_operation_id
    assert len(soft) == 1
    assert soft[0]["protection_priority"] == 4
    assert document["added_operation_ids"] == []

    precheck = validate_freeze_window_projection(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
        projection=document,
    )
    assert precheck["status"] == "PASS"
    assert precheck["hard_violation_count"] == 0


def test_completed_fact_is_classified_and_never_freeze_derived(
    completed: FreezeWindowFixture,
) -> None:
    """TEST-RUNNING covers terminal C-007 preservation as well as RUNNING."""

    document = project_effective_locks(
        snapshot=completed.snapshot,
        problem=completed.problem,
        base_schedule=completed.base_schedule,
        policy=completed.policy,
    ).document

    assert document["completed_operation_ids"] == [completed.first_operation_id]
    protection = cast(list[dict[str, object]], document["completed_protections"])[0]
    assert protection["operation_id"] == completed.first_operation_id
    assert protection["protection_kind"] == "COMPLETED_EXECUTION_FACT"
    assert protection["protection_priority"] == 1
    assert cast(dict[str, object], protection["fact_evidence"])["status"] == "COMPLETED"
    assert completed.first_operation_id not in {
        item["operation_id"]
        for item in cast(
            list[dict[str, object]], document["freeze_derived_hard_locks"]
        )
    }


def test_half_open_freeze_end_is_outside_and_missing_base_is_added(
    primary: FreezeWindowFixture,
) -> None:
    """TEST-FREEZE-WINDOW-001 exact [start,end) and ADDED classification."""

    cutoff = _utc(cast(str, primary.snapshot.document["cutoff_at_utc"]))
    at_end = move_base_assignment(
        primary.base_schedule,
        operation_id=primary.second_operation_id,
        start_at_utc=_format(
            cutoff + timedelta(seconds=SIMULATION_FREEZE_WINDOW_SECONDS)
        ),
    )
    boundary = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=at_end,
        policy=primary.policy,
    ).document
    assert boundary["outside_freeze_operation_ids"] == [primary.second_operation_id]
    assert boundary["freeze_derived_hard_locks"] == []

    without_existing = omit_base_assignment(
        primary.base_schedule, operation_id=primary.second_operation_id
    )
    added = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=without_existing,
        policy=primary.policy,
    ).document
    assert added["added_operation_ids"] == [primary.second_operation_id]
    assert added["freeze_derived_hard_locks"] == []


def test_hard_freeze_conflict_stale_base_and_cross_plane_fail_closed(
    primary: FreezeWindowFixture,
    completed: FreezeWindowFixture,
) -> None:
    """TEST-INF-LOCK conflict precedence and stale authority rejection."""

    conflicting = move_base_assignment(
        primary.base_schedule,
        operation_id=primary.second_operation_id,
        start_at_utc="2026-08-19T00:08:00Z",
    )
    with pytest.raises(FreezeProjectionError) as freeze_conflict:
        project_effective_locks(
            snapshot=primary.snapshot,
            problem=primary.problem,
            base_schedule=conflicting,
            policy=primary.policy,
        )
    assert freeze_conflict.value.reason is FreezeProjectionFailure.FREEZE_LOCK_CONFLICT

    stale = move_base_assignment(
        completed.base_schedule,
        operation_id=completed.second_operation_id,
        start_at_utc="2026-08-19T00:00:00Z",
    )
    with pytest.raises(FreezeProjectionError) as stale_rejection:
        project_effective_locks(
            snapshot=completed.snapshot,
            problem=completed.problem,
            base_schedule=stale,
            policy=completed.policy,
        )
    assert stale_rejection.value.reason is FreezeProjectionFailure.STALE_BASE

    cross_plane = cast(dict[str, object], deepcopy(primary.base_schedule))
    cross_plane["data_plane"] = "PRODUCTION"
    with pytest.raises(FreezeProjectionError) as plane_rejection:
        project_effective_locks(
            snapshot=primary.snapshot,
            problem=primary.problem,
            base_schedule=cross_plane,
            policy=primary.policy,
        )
    assert plane_rejection.value.reason is FreezeProjectionFailure.PLANE_MISMATCH


def test_problem_lock_and_anchor_bytes_must_equal_the_snapshot_projection(
    primary: FreezeWindowFixture,
    completed: FreezeWindowFixture,
) -> None:
    """TEST-INF-LOCK rejects rehashed Problem facts not derived from Snapshot."""

    document = cast(dict[str, object], deepcopy(primary.problem.document))
    locks = cast(list[dict[str, object]], document["operation_locks"])
    locks[0]["end_at_utc"] = "2026-08-19T00:09:00Z"
    forged = rehash_problem_v2(document)
    with pytest.raises(FreezeProjectionError) as rejected:
        project_effective_locks(
            snapshot=primary.snapshot,
            problem=forged,
            base_schedule=primary.base_schedule,
            policy=primary.policy,
        )
    assert rejected.value.reason is FreezeProjectionFailure.LINEAGE_MISMATCH

    completed_document = cast(dict[str, object], deepcopy(completed.problem.document))
    anchors = cast(
        list[dict[str, object]],
        completed_document["historical_completion_anchors"],
    )
    assert anchors
    anchors[0]["source_record_id"] = "forged-but-schema-valid-source-record"
    forged_anchor = rehash_problem_v2(completed_document)
    with pytest.raises(FreezeProjectionError) as anchor_rejected:
        project_effective_locks(
            snapshot=completed.snapshot,
            problem=forged_anchor,
            base_schedule=completed.base_schedule,
            policy=completed.policy,
        )
    assert anchor_rejected.value.reason is FreezeProjectionFailure.LINEAGE_MISMATCH


def test_registered_ids_are_exact() -> None:
    assert TEST_FREEZE_ID == "TEST-FREEZE-WINDOW-001"
    assert TEST_RUNNING_ID == "TEST-RUNNING"
    assert TEST_LOCK_ID == "TEST-INF-LOCK"
