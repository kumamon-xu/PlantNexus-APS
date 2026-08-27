"""TEST-PROPERTY fixed-seed OBJ-002 integer and replay properties."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import cast

from hypothesis import given, seed, settings
from hypothesis import strategies as st

from app.planning.reporting.stability import calculate_stability


TEST_ID = "TEST-PROPERTY"
ORIGIN = datetime(2026, 8, 28, tzinfo=UTC)


def _utc(seconds: int) -> str:
    return (ORIGIN + timedelta(seconds=seconds)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _assignment(resource: str, start_tick: int) -> dict[str, object]:
    return {
        "operation_id": "operation-property-001",
        "resource_id": resource,
        "start_tick": start_tick,
        "end_tick": start_tick + 2,
        "duration_ticks": 2,
        "start_at_utc": _utc(start_tick * 60),
        "end_at_utc": _utc((start_tick + 2) * 60),
        "duration_seconds": 120,
        "lock_ids": [],
        "execution_fact_ids": [],
    }


@seed(2026082806)
@settings(max_examples=64, deadline=None)
@given(
    shift_ticks=st.integers(min_value=-20, max_value=20),
    resource_changed=st.booleans(),
)
def test_obj_002_is_exact_for_signed_shifts_and_resource_changes(
    shift_ticks: int,
    resource_changed: bool,
) -> None:
    base = _assignment("resource-property-a", 20)
    new = _assignment(
        "resource-property-b" if resource_changed else "resource-property-a",
        20 + shift_ticks,
    )
    first = calculate_stability(
        base_assignments=(base,),
        new_assignments=(new,),
        active_operation_ids=("operation-property-001",),
        active_soft_locks=(),
    )
    replay = calculate_stability(
        base_assignments=(deepcopy(base),),
        new_assignments=(deepcopy(new),),
        active_operation_ids=("operation-property-001",),
        active_soft_locks=(),
    )
    changed = int(resource_changed or shift_ticks != 0)
    assert first == replay
    assert first.score == (
        0,
        changed,
        int(resource_changed and changed == 1),
        abs(shift_ticks * 60) if changed else 0,
    )
    assert first.unchanged_existing == 1 - changed


@seed(2026082807)
@settings(max_examples=32, deadline=None)
@given(
    lock_count=st.integers(min_value=0, max_value=8),
    fact_count=st.integers(min_value=0, max_value=8),
)
def test_metadata_cardinality_never_changes_the_stability_tuple(
    lock_count: int,
    fact_count: int,
) -> None:
    base = _assignment("resource-property-a", 20)
    new = cast(dict[str, object], deepcopy(base))
    new["lock_ids"] = [f"lock-property-{index}" for index in range(lock_count)]
    new["execution_fact_ids"] = [
        f"fact-property-{index}" for index in range(fact_count)
    ]
    result = calculate_stability(
        base_assignments=(base,),
        new_assignments=(new,),
        active_operation_ids=("operation-property-001",),
        active_soft_locks=(),
    )
    assert result.score == (0, 0, 0, 0)
    assert result.unchanged_existing == 1
    assert TEST_ID == "TEST-PROPERTY"
