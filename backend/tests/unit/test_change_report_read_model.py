"""TEST-CHANGE-REPORT-001: immutable P4 ChangeReport read projection."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import pytest

from app.application.change_report_queries import (
    CHANGE_REPORT_READ_MODEL_VERSION,
    ChangeReportQuery,
    ChangeReportQueryService,
    ChangeReportReadContext,
    ChangeReportReadError,
    ChangeReportReadFailure,
)
from app.domain.execution_contracts import canonical_contract_bytes
from app.exporters.change_report_output_check import (
    ChangeReportOutputFixture,
    build_change_report_output_fixture,
)


ROOT = Path(__file__).resolve().parents[3]
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


@dataclass(frozen=True, slots=True)
class StoredResult:
    result: dict[str, object]
    solver_report: dict[str, object]
    validation_report: dict[str, object]
    kpi: dict[str, object]
    change_report: dict[str, object]


class LineageRepository:
    def __init__(self, stored: StoredResult | None) -> None:
        self.stored = stored
        self.calls = 0

    def get_applied_result_for_attempt(self, attempt_id: str) -> StoredResult | None:
        del attempt_id
        self.calls += 1
        return self.stored


class ScheduleRepository:
    def __init__(self, schedule: dict[str, object] | None) -> None:
        self.schedule = schedule
        self.calls = 0

    def get(self, schedule_version_id: str) -> dict[str, object] | None:
        del schedule_version_id
        self.calls += 1
        return deepcopy(self.schedule)


@pytest.fixture(scope="module")
def fixture() -> ChangeReportOutputFixture:
    return build_change_report_output_fixture(ROOT)


def _stored(fixture: ChangeReportOutputFixture) -> StoredResult:
    report = fixture.change_report
    lineage = cast(dict[str, object], report["lineage"])
    return StoredResult(
        result={
            "record_version": "replan-result-reference.v1",
            "result_id": "replan-result-read-model-001",
            "result_fingerprint": SHA_A,
            "attempt_id": "replan-attempt-read-model-001",
            "request_id": "replan-request-read-model-001",
            "request_fingerprint": SHA_B,
            "planning_run_id": lineage["planning_run_id"],
            "planning_run_terminal_state": "COMPLETED",
            "solver_report": deepcopy(lineage["solver_report"]),
            "validation_report": deepcopy(lineage["validation_report"]),
            "new_schedule_version": {
                "document_version": "schedule-version.v2",
                "artifact_id": fixture.schedule_version["schedule_version_id"],
                "fingerprint": fixture.schedule_version["content_fingerprint"],
            },
            "change_report": {
                "document_version": "change-report.v1",
                "artifact_id": report["report_id"],
                "fingerprint": report["report_fingerprint"],
            },
            "correlation_id": report["correlation_id"],
            "finished_at_utc": "2026-08-28T10:06:00Z",
        },
        solver_report=deepcopy(fixture.solver_report),
        validation_report=deepcopy(fixture.validation_report),
        kpi=deepcopy(fixture.kpi),
        change_report=deepcopy(report),
    )


def _query(fixture: ChangeReportOutputFixture, *, limit: int = 2) -> ChangeReportQuery:
    report = fixture.change_report
    return ChangeReportQuery(
        attempt_id="replan-attempt-read-model-001",
        expected_result_fingerprint=SHA_A,
        expected_schedule_version_id=cast(
            str, fixture.schedule_version["schedule_version_id"]
        ),
        expected_schedule_content_fingerprint=cast(
            str, fixture.schedule_version["content_fingerprint"]
        ),
        expected_report_id=cast(str, report["report_id"]),
        expected_report_fingerprint=cast(str, report["report_fingerprint"]),
        classifications=("UNCHANGED",),
        limit=limit,
    )


def _context(fixture: ChangeReportOutputFixture) -> ChangeReportReadContext:
    return ChangeReportReadContext(
        actor_ref="actor:p4-change-report-reader",
        authenticated=True,
        resolved_capabilities=frozenset({"view"}),
        attempt_scope=frozenset({"replan-attempt-read-model-001"}),
        schedule_version_scope=frozenset(
            {cast(str, fixture.schedule_version["schedule_version_id"])}
        ),
        data_plane="SIMULATION",
        environment="TEST",
        production_binding=False,
    )


def test_read_projection_is_stable_filtered_complete_and_side_effect_free(
    fixture: ChangeReportOutputFixture,
) -> None:
    lineage = LineageRepository(_stored(fixture))
    schedules = ScheduleRepository(fixture.schedule_version)
    service = ChangeReportQueryService(
        lineage_repository=lineage,
        schedule_repository=schedules,
    )
    before = canonical_contract_bytes(fixture.change_report)
    first = service.query(
        _query(fixture),
        _context(fixture),
        generated_at_utc="2026-08-28T11:00:00Z",
    )
    replay = service.query(
        _query(fixture),
        _context(fixture),
        generated_at_utc="2026-08-28T11:00:00Z",
    )

    assert first.document == replay.document
    assert first.document["read_model_version"] == CHANGE_REPORT_READ_MODEL_VERSION
    result = cast(dict[str, object], first.document["result"])
    operations = cast(list[dict[str, object]], result["operations"])
    assert [row["operation_id"] for row in operations] == sorted(
        cast(str, row["operation_id"]) for row in operations
    )
    assert len(operations) == 2
    assert result["filtered_operation_count"] == 4
    assert result["operation_universe_count"] == 4
    assert result["next_cursor"] == operations[-1]["operation_id"]
    assert result["export_eligible"] is True
    assert result["publishable"] is False
    assert service.solver_invocations == 0
    assert canonical_contract_bytes(fixture.change_report) == before
    assert lineage.calls == 2 and schedules.calls == 2

    next_page = service.query(
        replace(
            _query(fixture),
            after_operation_id=cast(str, result["next_cursor"]),
        ),
        _context(fixture),
        generated_at_utc="2026-08-28T11:00:00Z",
    )
    next_operations = cast(
        list[dict[str, object]],
        cast(dict[str, object], next_page.document["result"])["operations"],
    )
    assert len(next_operations) == 2
    assert set(row["operation_id"] for row in operations).isdisjoint(
        row["operation_id"] for row in next_operations
    )


@pytest.mark.parametrize(
    ("context_changes", "failure"),
    [
        ({"authenticated": False}, ChangeReportReadFailure.AUTHORIZATION_DENIED),
        ({"actor_ref": ""}, ChangeReportReadFailure.AUTHORIZATION_DENIED),
        ({"resolved_capabilities": frozenset()}, ChangeReportReadFailure.AUTHORIZATION_DENIED),
        ({"data_plane": "PRODUCTION"}, ChangeReportReadFailure.PRODUCTION_AUTHORITY_UNAVAILABLE),
        ({"environment": "PRODUCTION"}, ChangeReportReadFailure.PRODUCTION_AUTHORITY_UNAVAILABLE),
    ],
)
def test_authorization_and_production_denial_precede_repository_lookup(
    fixture: ChangeReportOutputFixture,
    context_changes: dict[str, object],
    failure: ChangeReportReadFailure,
) -> None:
    lineage = LineageRepository(None)
    schedules = ScheduleRepository(None)
    service = ChangeReportQueryService(
        lineage_repository=lineage,
        schedule_repository=schedules,
    )
    with pytest.raises(ChangeReportReadError) as captured:
        service.query(
            _query(fixture),
            replace(_context(fixture), **context_changes),
            generated_at_utc="2026-08-28T11:00:00Z",
        )
    assert captured.value.reason is failure
    assert lineage.calls == 0 and schedules.calls == 0


def test_mixed_kpi_lineage_and_unstable_filter_are_rejected(
    fixture: ChangeReportOutputFixture,
) -> None:
    stored = _stored(fixture)
    stored.kpi["kpi_id"] = "kpi-cross-lineage"
    service = ChangeReportQueryService(
        lineage_repository=LineageRepository(stored),
        schedule_repository=ScheduleRepository(fixture.schedule_version),
    )
    with pytest.raises(ChangeReportReadError) as captured:
        service.query(
            _query(fixture),
            _context(fixture),
            generated_at_utc="2026-08-28T11:00:00Z",
        )
    assert captured.value.reason is ChangeReportReadFailure.LINEAGE_MISMATCH

    with pytest.raises(ChangeReportReadError) as invalid:
        service.query(
            replace(_query(fixture), classifications=("UNCHANGED", "UNCHANGED")),
            _context(fixture),
            generated_at_utc="2026-08-28T11:00:00Z",
        )
    assert invalid.value.reason is ChangeReportReadFailure.INVALID_QUERY
