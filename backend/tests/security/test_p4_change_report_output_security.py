"""TEST-SIM-ISOLATION: P4 read/export authorization and Production denial."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.application.change_report_queries import (
    ChangeReportQuery,
    ChangeReportQueryService,
    ChangeReportReadContext,
    ChangeReportReadError,
    ChangeReportReadFailure,
)
from app.application.export_downloads import ExportPackageDownloadService
from app.application.export_jobs import ExportJobService
from app.domain.export_job import (
    ExportJobContext,
    ExportJobError,
    ExportJobFailure,
    ExportJobRequest,
)


ROOT = Path(__file__).resolve().parents[3]
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


class NeverCalled:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self) -> Any:
        self.calls.append("transaction")
        raise AssertionError("authorization must precede transaction creation")

    def __getattr__(self, name: str) -> Any:
        def called(*_args: object, **_kwargs: object) -> Any:
            self.calls.append(name)
            raise AssertionError("authorization must precede repository/package lookup")

        return called


def _query() -> ChangeReportQuery:
    return ChangeReportQuery(
        attempt_id="replan-attempt-sensitive",
        expected_result_fingerprint=SHA_A,
        expected_schedule_version_id="schedule-version-sensitive",
        expected_schedule_content_fingerprint=SHA_B,
        expected_report_id="change-report-" + "c" * 64,
        expected_report_fingerprint=SHA_C,
    )


def _read_context(*, production: bool = False) -> ChangeReportReadContext:
    return ChangeReportReadContext(
        actor_ref="actor:security-reader",
        authenticated=production,
        resolved_capabilities=frozenset({"view"}) if production else frozenset(),
        attempt_scope=frozenset({_query().attempt_id}) if production else frozenset(),
        schedule_version_scope=(
            frozenset({_query().expected_schedule_version_id})
            if production
            else frozenset()
        ),
        data_plane="PRODUCTION" if production else "SIMULATION",
        environment="PRODUCTION" if production else "TEST",
        production_binding=production,
    )


def _job_context(*, allowed: bool, production_binding: bool = False) -> ExportJobContext:
    return ExportJobContext(
        actor_ref="actor:p4-output-security",
        authenticated=allowed,
        resolved_capabilities=frozenset({"export"}) if allowed else frozenset(),
        schedule_version_scope=(
            frozenset({"schedule-version-sensitive"}) if allowed else frozenset()
        ),
        export_job_scope=frozenset({"export-job-" + "d" * 64}) if allowed else frozenset(),
        auth_policy_version="p4-output-security-policy.v1",
        production_binding=production_binding,
        occurred_at_utc="2026-08-28T12:00:00Z",
        code_commit="uncommitted",
    )


def _p4_request(*, production: bool) -> ExportJobRequest:
    provenance = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/schedule-version.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        )["synthetic_provenance"],
    )
    return ExportJobRequest(
        schedule_version_id="schedule-version-sensitive",
        expected_content_fingerprint=SHA_B,
        raw_idempotency_key="p4-output-security-key",
        reason="Verify P4 output security boundary.",
        correlation_id="correlation-p4-output-security",
        environment="PRODUCTION" if production else "TEST",
        synthetic_provenance=provenance,
        data_plane="PRODUCTION" if production else "SIMULATION",
        change_report_reference={
            "change_report_version": "change-report.v1",
            "report_id": "change-report-" + "c" * 64,
            "report_fingerprint": SHA_C,
        },
    )


def test_read_denial_and_production_guard_precede_all_lookups() -> None:
    boundary = NeverCalled()
    service = ChangeReportQueryService(
        lineage_repository=cast(Any, boundary),
        schedule_repository=cast(Any, boundary),
    )
    with pytest.raises(ChangeReportReadError) as denied:
        service.query(
            _query(),
            _read_context(),
            generated_at_utc="2026-08-28T12:00:00Z",
        )
    assert denied.value.reason is ChangeReportReadFailure.AUTHORIZATION_DENIED
    assert boundary.calls == []

    with pytest.raises(ChangeReportReadError) as production:
        service.query(
            _query(),
            _read_context(production=True),
            generated_at_utc="2026-08-28T12:00:00Z",
        )
    assert (
        production.value.reason
        is ChangeReportReadFailure.PRODUCTION_AUTHORITY_UNAVAILABLE
    )
    assert boundary.calls == []


def test_p4_export_create_production_guard_precedes_lookup_and_transaction() -> None:
    boundary = NeverCalled()
    service = ExportJobService(
        transaction_factory=cast(Any, boundary),
        schedule_repository=cast(Any, boundary),
        export_job_repository=cast(Any, boundary),
        audit_repository=cast(Any, boundary),
    )
    with pytest.raises(ExportJobError) as captured:
        service.create(
            _p4_request(production=True),
            _job_context(allowed=True),
            publication_result={},
        )
    assert captured.value.reason is ExportJobFailure.PRODUCTION_AUTHORITY_UNAVAILABLE
    assert boundary.calls == []


@pytest.mark.parametrize(
    "context",
    [
        _job_context(allowed=False),
        _job_context(allowed=True, production_binding=True),
    ],
)
def test_download_denial_precedes_job_and_package_lookup(
    context: ExportJobContext,
) -> None:
    boundary = NeverCalled()
    service = ExportPackageDownloadService(
        export_job_repository=cast(Any, boundary),
        package_store=cast(Any, boundary),
    )
    with pytest.raises(ExportJobError) as captured:
        service.download(
            "export-job-" + "d" * 64,
            context,
            correlation_id="correlation-p4-output-download-security",
        )
    assert captured.value.reason is ExportJobFailure.AUTHORIZATION_DENIED
    assert boundary.calls == []
