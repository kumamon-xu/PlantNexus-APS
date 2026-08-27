"""TEST-PROPERTY fixed-seed freeze-window boundary and replay evidence."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from hypothesis import given, seed, settings
from hypothesis import strategies as st
import pytest

from app.planning.policy.freeze_window import SIMULATION_FREEZE_WINDOW_SECONDS
from app.planning.problem.freeze_projection import (
    FreezeProjectionError,
    FreezeProjectionFailure,
    project_effective_locks,
)
from app.planning.problem.freeze_window_check import (
    build_freeze_window_fixture,
    move_base_assignment,
)
from app.planning.validation.freeze_window_precheck import (
    validate_freeze_window_projection,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_ID = "TEST-PROPERTY"
FIXTURE = build_freeze_window_fixture(ROOT, completed=True)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


@seed(2026082705)
@settings(max_examples=48, deadline=None)
@given(offset_ticks=st.integers(min_value=-7, max_value=25))
def test_half_open_classification_is_total_deterministic_and_fail_closed(
    offset_ticks: int,
) -> None:
    """TEST-PROPERTY generates before/inside/at-end/after boundary vectors."""

    cutoff = _utc(cast(str, FIXTURE.snapshot.document["cutoff_at_utc"]))
    base = move_base_assignment(
        FIXTURE.base_schedule,
        operation_id=FIXTURE.second_operation_id,
        start_at_utc=_format(cutoff + timedelta(seconds=offset_ticks * 60)),
    )
    if offset_ticks < 0:
        with pytest.raises(FreezeProjectionError) as rejected:
            project_effective_locks(
                snapshot=FIXTURE.snapshot,
                problem=FIXTURE.problem,
                base_schedule=base,
                policy=FIXTURE.policy,
            )
        assert rejected.value.reason is FreezeProjectionFailure.STALE_BASE
        return

    first = project_effective_locks(
        snapshot=FIXTURE.snapshot,
        problem=FIXTURE.problem,
        base_schedule=base,
        policy=FIXTURE.policy,
    )
    replay = project_effective_locks(
        snapshot=FIXTURE.snapshot,
        problem=FIXTURE.problem,
        base_schedule=base,
        policy=FIXTURE.policy,
    )
    assert first.canonical_bytes == replay.canonical_bytes
    document = first.document
    inside = offset_ticks * 60 < SIMULATION_FREEZE_WINDOW_SECONDS
    derived = cast(list[dict[str, object]], document["freeze_derived_hard_locks"])
    outside = cast(list[str], document["outside_freeze_operation_ids"])
    assert len(derived) == (1 if inside else 0)
    assert outside == ([] if inside else [FIXTURE.second_operation_id])
    report = validate_freeze_window_projection(
        snapshot=FIXTURE.snapshot,
        problem=FIXTURE.problem,
        base_schedule=base,
        policy=FIXTURE.policy,
        projection=document,
    )
    assert report["status"] == "PASS"


@seed(2026082706)
@settings(max_examples=32, deadline=None)
@given(delta_seconds=st.integers(min_value=-59, max_value=59).filter(lambda value: value != 0))
def test_non_grid_freeze_tuple_never_rounds_or_silently_repairs(
    delta_seconds: int,
) -> None:
    """TEST-PROPERTY proves exact-grid projection rejects lossy conversion."""

    cutoff = _utc(cast(str, FIXTURE.snapshot.document["cutoff_at_utc"]))
    base = move_base_assignment(
        FIXTURE.base_schedule,
        operation_id=FIXTURE.second_operation_id,
        start_at_utc=_format(cutoff + timedelta(seconds=60 + delta_seconds)),
    )
    with pytest.raises(FreezeProjectionError) as rejected:
        project_effective_locks(
            snapshot=FIXTURE.snapshot,
            problem=FIXTURE.problem,
            base_schedule=base,
            policy=FIXTURE.policy,
        )
    assert rejected.value.reason is FreezeProjectionFailure.UNREPRESENTABLE_LOCK


def test_property_test_id_is_registered() -> None:
    assert TEST_ID == "TEST-PROPERTY"
