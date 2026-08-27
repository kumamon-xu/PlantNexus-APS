"""TEST-STABILITY-OBJECTIVE-001 pure integer OBJ-002 evidence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from app.domain.change_report import ChangeReportError, ChangeReportFailure
from app.planning.reporting.stability import (
    STABILITY_COMPONENTS,
    calculate_operation_delta,
    calculate_stability,
    canonical_assignment,
)
from app.planning.reporting.stability_change_report_check import (
    build_stability_change_report_fixture,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_ID = "TEST-STABILITY-OBJECTIVE-001"


def test_obj_002_uses_the_accepted_integer_lexicographic_vector() -> None:
    fixture = build_stability_change_report_fixture(ROOT)
    result = calculate_stability(
        base_assignments=fixture.base_assignments,
        new_assignments=fixture.new_assignments,
        active_operation_ids=fixture.active_operation_ids,
        active_soft_locks=fixture.active_soft_locks,
    )
    assert STABILITY_COMPONENTS == (
        "SOFT_LOCK_VIOLATIONS",
        "CHANGED_EXISTING_OPERATIONS",
        "RESOURCE_CHANGES",
        "ABSOLUTE_START_SHIFT_SECONDS",
    )
    assert result.score == (1, 1, 1, 300)
    assert result.document["unchanged_ratio"] == {
        "status": "APPLICABLE",
        "numerator": 1,
        "denominator": 2,
    }
    assert all(isinstance(value, int) for value in result.score)
    assert TEST_ID == "TEST-STABILITY-OBJECTIVE-001"


def test_assignment_metadata_does_not_invent_a_schedule_movement() -> None:
    fixture = build_stability_change_report_fixture(ROOT)
    base = next(
        item
        for item in fixture.base_assignments
        if item["operation_id"] == "operation-stable-001"
    )
    new = next(
        item
        for item in fixture.new_assignments
        if item["operation_id"] == "operation-stable-001"
    )
    assert base["lock_ids"] != new["lock_ids"]
    delta = calculate_operation_delta(base, new)
    assert delta.changed is False
    assert delta.document == {
        "resource_changed": False,
        "start_shift_seconds": 0,
        "absolute_start_shift_seconds": 0,
        "end_shift_seconds": 0,
        "duration_delta_seconds": 0,
    }


def test_no_comparable_operation_has_an_exact_not_applicable_ratio() -> None:
    fixture = build_stability_change_report_fixture(ROOT)
    added = fixture.new_assignments[0]
    result = calculate_stability(
        base_assignments=(),
        new_assignments=(added,),
        active_operation_ids=(cast(str, added["operation_id"]),),
        active_soft_locks=(),
    )
    assert result.score == (0, 0, 0, 0)
    assert result.document["unchanged_ratio"] == {
        "status": "NOT_APPLICABLE_NO_COMPARABLE_OPERATION",
        "numerator": 0,
        "denominator": 0,
    }


def test_signed_shift_and_absolute_component_are_both_exact() -> None:
    fixture = build_stability_change_report_fixture(ROOT)
    base = next(
        item
        for item in fixture.base_assignments
        if item["operation_id"] == "operation-changed-001"
    )
    earlier = cast(dict[str, object], deepcopy(base))
    earlier.update(
        {
            "start_tick": 2,
            "end_tick": 4,
            "start_at_utc": "2026-08-28T00:02:00Z",
            "end_at_utc": "2026-08-28T00:04:00Z",
        }
    )
    delta = calculate_operation_delta(
        canonical_assignment(base, field="base"),
        canonical_assignment(earlier, field="new"),
    )
    assert delta.start_shift_seconds == -180
    assert delta.absolute_start_shift_seconds == 180
    assert delta.end_shift_seconds == -180


def test_duplicate_or_incomplete_active_universe_fails_closed() -> None:
    fixture = build_stability_change_report_fixture(ROOT)
    with pytest.raises(ChangeReportError) as rejected:
        calculate_stability(
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=(
                fixture.active_operation_ids[0],
                fixture.active_operation_ids[0],
            ),
            active_soft_locks=fixture.active_soft_locks,
        )
    assert rejected.value.reason is ChangeReportFailure.DUPLICATE_OPERATION
