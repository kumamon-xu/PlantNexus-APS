"""TEST-SIM-ISOLATION: export authorization precedes resource and replay lookup."""

from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.application.export_jobs import ExportJobService
from app.domain.export_job import (
    ExportJobContext,
    ExportJobError,
    ExportJobFailure,
    ExportJobRequest,
    export_job_identity,
)
from app.domain.workspace_contracts import require_workspace_document


ROOT = Path(__file__).resolve().parents[3]


class ForbiddenLookup:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, _value: str):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("authorization must precede ExportJob lookup")

    def get_record(self, _value: str):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("authorization must precede ScheduleVersion lookup")


class CapturingAudit:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def append(self, document):  # type: ignore[no-untyped-def]
        copied = dict(document)
        require_workspace_document(copied)
        self.documents.append(copied)
        return object()

    def append_in_transaction(self, _connection, _document):  # type: ignore[no-untyped-def]
        raise AssertionError("business transaction must not start")

    def get(self, _value: str):  # type: ignore[no-untyped-def]
        raise AssertionError("authorization must precede audit replay lookup")


def _request(*, production: bool = False) -> ExportJobRequest:
    provenance = json.loads((ROOT / "schemas/samples/schedule-version.v1.synthetic.json").read_text(encoding="utf-8"))["synthetic_provenance"]
    return ExportJobRequest(
        schedule_version_id="schedule-version-sensitive",
        expected_content_fingerprint="sha256:" + "1" * 64,
        raw_idempotency_key="security-export-key-0001",
        reason="Security boundary export request.",
        correlation_id="correlation-security-export",
        environment="PRODUCTION" if production else "TEST",
        synthetic_provenance=provenance,
        data_plane="PRODUCTION" if production else "SIMULATION",
        target="SIMULATION_INTERNAL",
    )


def _context(*, allowed: bool) -> ExportJobContext:
    return ExportJobContext(
        actor_ref="actor:security-test", authenticated=allowed,
        resolved_capabilities=frozenset({"export"}) if allowed else frozenset(),
        schedule_version_scope=frozenset({"schedule-version-sensitive"}) if allowed else frozenset(),
        export_job_scope=frozenset(), auth_policy_version="security-policy.v1",
        production_binding=False, occurred_at_utc="2026-08-25T03:00:00Z", code_commit="uncommitted",
    )


def test_denied_create_writes_sanitized_audit_without_resource_lookup() -> None:
    lookups = ForbiddenLookup()
    audits = CapturingAudit()
    service = ExportJobService(
        transaction_factory=lambda: nullcontext(object()),
        schedule_repository=cast(Any, lookups), export_job_repository=cast(Any, lookups), audit_repository=cast(Any, audits),
    )
    with pytest.raises(ExportJobError) as captured:
        service.create(_request(), _context(allowed=False), publication_result={})
    assert captured.value.reason is ExportJobFailure.AUTHORIZATION_DENIED
    assert lookups.calls == 0
    assert len(audits.documents) == 1
    denial = audits.documents[0]
    assert denial["result"] == {
        "outcome": "DENIED", "replayed": False, "retryable": False,
        "error": {"error_namespace": "WORKSPACE_CONTROL", "reason": "AUTHORIZATION_DENIED", "message": "Export authorization was denied."},
    }
    rendered = json.dumps(denial).lower()
    assert "security-export-key-0001" not in rendered
    assert "password" not in rendered and "token" not in rendered


def test_production_is_default_denied_before_any_lookup_or_audit_write() -> None:
    lookups = ForbiddenLookup()
    audits = CapturingAudit()
    service = ExportJobService(
        transaction_factory=lambda: nullcontext(object()),
        schedule_repository=cast(Any, lookups), export_job_repository=cast(Any, lookups), audit_repository=cast(Any, audits),
    )
    with pytest.raises(ExportJobError) as captured:
        service.create(_request(production=True), _context(allowed=True), publication_result={})
    assert captured.value.reason is ExportJobFailure.PRODUCTION_AUTHORITY_UNAVAILABLE
    assert lookups.calls == 0
    assert audits.documents == []


def test_denied_job_action_precedes_job_lookup() -> None:
    lookups = ForbiddenLookup()
    audits = CapturingAudit()
    service = ExportJobService(
        transaction_factory=lambda: nullcontext(object()),
        schedule_repository=cast(Any, lookups), export_job_repository=cast(Any, lookups), audit_repository=cast(Any, audits),
    )
    job_id = export_job_identity(_request()).export_job_id
    with pytest.raises(ExportJobError) as captured:
        service.cancel(job_id, _context(allowed=False))
    assert captured.value.reason is ExportJobFailure.AUTHORIZATION_DENIED
    assert lookups.calls == 0
