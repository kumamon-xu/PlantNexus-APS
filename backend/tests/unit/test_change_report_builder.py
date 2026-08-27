"""TEST-CHANGE-REPORT-001 immutable complete ChangeReport builder evidence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from app.domain.change_report import ChangeReportError, ChangeReportFailure
from app.domain.execution_contracts import require_p4_document
from app.planning.reporting.change_report import build_change_report
from app.planning.reporting.stability_change_report_check import (
    StabilityChangeReportFixture,
    build_fixture_change_report,
    build_stability_change_report_fixture,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_ID = "TEST-CHANGE-REPORT-001"


@pytest.fixture(scope="module")
def fixture() -> StabilityChangeReportFixture:
    return build_stability_change_report_fixture(ROOT)


def test_builder_emits_complete_sorted_content_addressed_evidence(
    fixture: StabilityChangeReportFixture,
) -> None:
    immutable = build_fixture_change_report(fixture)
    document = immutable.document
    require_p4_document(document)
    assert document["report_id"] == immutable.report_id
    assert document["report_fingerprint"] == immutable.report_fingerprint
    operations = cast(list[dict[str, object]], document["operations"])
    operation_ids = [cast(str, item["operation_id"]) for item in operations]
    assert operation_ids == sorted(operation_ids)
    assert [item["classification"] for item in operations] == [
        "ADDED",
        "CHANGED",
        "REMOVED_BY_FACT",
        "UNCHANGED",
    ]
    changed = next(item for item in operations if item["classification"] == "CHANGED")
    assert cast(list[dict[str, object]], changed["reasons"])[0]["reason_code"] == (
        "UNATTRIBUTED_SOLVER_CHANGE"
    )
    assert document["stability"] == {
        "soft_lock_violations": 1,
        "changed_existing_operations": 1,
        "resource_changes": 1,
        "absolute_start_shift_seconds": 300,
        "unchanged_existing": 1,
        "comparable_existing": 2,
        "unchanged_ratio": {
            "status": "APPLICABLE",
            "numerator": 1,
            "denominator": 2,
        },
    }
    assert TEST_ID == "TEST-CHANGE-REPORT-001"


def test_builder_is_byte_exact_and_does_not_mutate_inputs(
    fixture: StabilityChangeReportFixture,
) -> None:
    before = deepcopy(fixture)
    first = build_fixture_change_report(fixture)
    second = build_fixture_change_report(fixture)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.report_id == second.report_id
    assert fixture == before


def test_removed_operation_requires_the_exact_completion_fact(
    fixture: StabilityChangeReportFixture,
) -> None:
    with pytest.raises(ChangeReportError) as rejected:
        build_change_report(
            context=fixture.context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact={},
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    assert rejected.value.reason is ChangeReportFailure.MISSING_FACT_EVIDENCE

    context = cast(dict[str, object], deepcopy(fixture.context))
    cast(dict[str, object], context["freeze_evidence"])["effective_lock_ids"] = [
        "soft-lock-stable-001"
    ]
    with pytest.raises(ChangeReportError) as missing_lock:
        build_change_report(
            context=context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    assert missing_lock.value.reason is ChangeReportFailure.LINEAGE_MISMATCH


def test_reason_outside_classification_is_rejected(
    fixture: StabilityChangeReportFixture,
) -> None:
    reasons = cast(dict[str, object], deepcopy(fixture.reasons_by_operation))
    stable_reason = cast(
        list[dict[str, object]], reasons["operation-stable-001"]
    )[0]
    stable_reason["reason_code"] = "URGENT_DEMAND"
    with pytest.raises(ChangeReportError) as rejected:
        build_change_report(
            context=fixture.context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=reasons,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    assert rejected.value.reason is ChangeReportFailure.INVALID_REASON_EVIDENCE


def test_production_context_is_default_denied(
    fixture: StabilityChangeReportFixture,
) -> None:
    context = cast(dict[str, object], deepcopy(fixture.context))
    context["environment"] = "PRODUCTION"
    with pytest.raises(ChangeReportError) as rejected:
        build_change_report(
            context=context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    assert rejected.value.reason is ChangeReportFailure.PLANE_MISMATCH

    forged_kpi = cast(dict[str, object], deepcopy(fixture.before_kpi))
    cast(dict[str, object], forged_kpi["delivery"])[
        "priority_weighted_tardiness_seconds"
    ] = 601
    with pytest.raises(ChangeReportError) as kpi_rejected:
        build_change_report(
            context=fixture.context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=forged_kpi,
            after_kpi=fixture.after_kpi,
        )
    assert kpi_rejected.value.reason is ChangeReportFailure.KPI_EVIDENCE_MISMATCH
