"""Valid-carrier negative replay against formal Runtime and durable repositories."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect, text

from app.api.app import create_app
from app.infrastructure.config import Settings
from app.domain.workspace_contracts import workspace_command_fingerprint
from backend.tests.integration import test_p9_manual as manual
from backend.tests.integration import test_p9_readmodel as reads
from backend.tests.integration import test_p9_replan as replan
from backend.tests.integration.test_p8_headless_http_api_integration import (
    _cancel_document,
    _retry_document,
)
from backend.tests.contract.p8_headless_http_support import (
    compose_headless_api,
    canonical_request,
    create_headers,
    run_headers,
)
from backend.tests.p8_runtime_support import RecordingCelery

runtime = manual.runtime
export_configuration = reads.export_configuration
events = replan.events
replans = replan.replans


def business_state(engine: Any) -> dict[str, list[str]]:
    """Compare all business rows, not merely counts; denial audit may append."""
    with engine.connect() as connection:
        return {
            table: sorted(
                repr(tuple(row))
                for row in connection.execute(text('SELECT * FROM "' + table + '"'))
            )
            for table in inspect(engine).get_table_names()
            if "audit" not in table
        }


def denied(response: Any) -> None:
    assert response.status_code == 403, response.text
    assert "AUTHORIZATION_DENIED" in response.text


def test_readiness_failure_is_declared_in_current_openapi() -> None:
    assert (
        "503"
        in create_app(
            Settings(
                runtime_schema_directory=Path(__file__).resolve().parents[3]
                / "schemas/json"
            ),
            probes={},
        ).openapi()["paths"]["/health/ready"]["get"]["responses"]
    )


@pytest.mark.parametrize(
    "view", ["DATA_HEALTH", "IMPORT_RUNS", "PLANNING_RUNS", "AUDIT"]
)
def test_workspace_query_valid_carrier_denied(runtime: Any, view: str) -> None:  # noqa: F811
    runtime.identity.principal = replace(
        runtime.identity.principal, resolved_capabilities=frozenset()
    )
    before = business_state(runtime.db)
    denied(reads.query(runtime, view))
    assert business_state(runtime.db) == before


@pytest.mark.parametrize(
    "resource", ["schedule-versions", "planning-runs", "export-jobs"]
)
def test_existing_resource_scope_denied_and_missing_resource(
    runtime: Any, resource: str
) -> None:  # noqa: F811
    if resource == "export-jobs":
        published = reads.publish(runtime)
        response = reads.create_export(runtime, published)
        assert response.status_code == 202, response.text
        identity = response.json()["export_job_id"]
        field = "export_job_scope"
    elif resource == "planning-runs":
        identity = runtime.source["lineage"]["planning_run_id"]
        field = "planning_run_scope"
    else:
        identity = runtime.source["schedule_version_id"]
        field = "schedule_version_scope"
    principal = runtime.identity.principal
    runtime.identity.principal = replace(principal, **{field: frozenset()})
    before = business_state(runtime.db)
    headers = {
        "Authorization": "Bearer p9-test-token",
        "X-Correlation-Id": "corrective-resource-read",
    }
    denied(runtime.client.get(f"/api/v1/{resource}/{identity}", headers=headers))
    assert business_state(runtime.db) == before
    runtime.identity.principal = principal
    missing = runtime.client.get(
        f"/api/v1/{resource}/missing-corrective-resource", headers=headers
    )
    assert missing.status_code == (422 if resource == "planning-runs" else 404), (
        missing.text
    )
    if resource == "planning-runs":
        assert missing.json()["product_error"]["code"] == "INVALID_REFERENCE"
        assert missing.json()["details"]["reason"] == "MIXED_LINEAGE"
    assert business_state(runtime.db) == before


@pytest.mark.parametrize("action", ["APPROVE", "REJECT"])
def test_decision_denial_stale_and_key_conflict(runtime: Any, action: str) -> None:  # noqa: F811
    value = manual.command(runtime.source, action, key="corrective-decision-key-001")
    principal = runtime.identity.principal
    runtime.identity.principal = replace(
        principal, resolved_capabilities=frozenset({"view"})
    )
    before = business_state(runtime.db)
    denied(manual.post(runtime, value))
    assert business_state(runtime.db) == before
    runtime.identity.principal = principal
    stale = deepcopy(value)
    stale["expected_content_fingerprint"] = "sha256:" + "a" * 64
    stale["request_fingerprint"] = workspace_command_fingerprint(stale)
    response = manual.post(runtime, stale)
    assert response.status_code == 409, response.text
    assert business_state(runtime.db) == before
    accepted = manual.post(runtime, value)
    assert accepted.status_code == 200, accepted.text
    after = business_state(runtime.db)
    conflict = deepcopy(value)
    conflict["reason"] = "Different explicit reason with the same command key."
    conflict["request_fingerprint"] = workspace_command_fingerprint(conflict)
    response = manual.post(runtime, conflict)
    assert response.status_code == 409, response.text
    assert "IDEMPOTENCY_CONFLICT" in response.text
    assert business_state(runtime.db) == after


def test_export_valid_command_denied_without_job(runtime: Any) -> None:  # noqa: F811
    published = reads.publish(runtime)
    runtime.identity.principal = replace(
        runtime.identity.principal, resolved_capabilities=frozenset({"view"})
    )
    before = business_state(runtime.db)
    denied(reads.create_export(runtime, published))
    assert business_state(runtime.db) == before


@pytest.mark.parametrize("kind", ["REPLAN_REQUEST", "REPLAN_RESULT", "CHANGE_REPORT"])
def test_replan_valid_query_denied_and_missing(replans: Any, kind: str) -> None:  # noqa: F811
    accepted = replan.create(replans)
    assert accepted.status_code == 202, accepted.text
    attempt = accepted.json()["result"]["attempt"]
    # A nonexistent report is still a well-formed query, denied before lookup.
    report = (
        {
            "report_id": "change-report-" + "a" * 64,
            "report_fingerprint": "sha256:" + "a" * 64,
        }
        if kind == "CHANGE_REPORT"
        else None
    )
    principal = replans.runtime.identity.principal
    replans.runtime.identity.principal = replace(
        principal, resolved_capabilities=frozenset()
    )
    before = business_state(replans.runtime.db)
    denied(replan.query(replans, kind, attempt, report))
    assert business_state(replans.runtime.db) == before
    replans.runtime.identity.principal = principal
    if kind == "CHANGE_REPORT":
        missing = replan.query(replans, kind, attempt, report)
        assert missing.status_code == 422, missing.text
        assert missing.json()["product_error"]["code"] == "INVALID_REFERENCE"
        assert missing.json()["details"]["reason"] == "MIXED_LINEAGE"
        assert business_state(replans.runtime.db) == before


@pytest.mark.parametrize("action", ["CANCEL", "RETRY"])
def test_replan_control_denial_and_stale_attempt(replans: Any, action: str) -> None:  # noqa: F811
    attempt = replan.create(replans).json()["result"]["attempt"]
    if action == "RETRY":
        cancelled = replan.control(
            replans, attempt, "CANCEL", "corrective-setup-cancel"
        )
        assert cancelled.status_code == 202, cancelled.text
        attempt = cancelled.json()["result"]["attempt"]
    principal = replans.runtime.identity.principal
    replans.runtime.identity.principal = replace(
        principal, resolved_capabilities=frozenset({"replan_view"})
    )
    before = business_state(replans.runtime.db)
    denied(replan.control(replans, attempt, action, "corrective-control-key-001"))
    assert business_state(replans.runtime.db) == before
    replans.runtime.identity.principal = principal
    stale = {**attempt, "attempt_number": attempt["attempt_number"] + 1}
    response = replan.control(replans, stale, action, "corrective-stale-key-001")
    assert response.status_code == 409, response.text
    assert business_state(replans.runtime.db) == before


@pytest.mark.parametrize("action", ["status", "cancel", "retry"])
def test_headless_scope_denied_missing_and_stale(tmp_path: Path, action: str) -> None:
    publisher = RecordingCelery(fail=action == "retry")
    api, composition, _ = compose_headless_api(tmp_path, publisher=publisher)
    with TestClient(api) as client:
        request = canonical_request()
        created = client.post(
            "/api/v1/planning-runs", json=request, headers=create_headers(request)
        )
        assert created.status_code == (503 if action == "retry" else 202), created.text
        engine = composition.database.engine
        with engine.connect() as connection:
            identity = connection.scalar(
                text("SELECT planning_run_id FROM planning_runs")
            )
            attempt = json.loads(
                connection.scalar(
                    text("SELECT attempt_json FROM planning_run_attempts")
                )
            )
        current = client.get(
            f"/api/v1/planning-runs/{identity}/status", headers=run_headers()
        ).json()
        body = (
            _retry_document(current, attempt)
            if action == "retry"
            else _cancel_document(current)
        )
        headers = {**run_headers(), "Idempotency-Key": "corrective-headless-key-001"}
        url = f"/api/v1/planning-runs/{identity}/{action}"
        before = business_state(engine)
        bad_scope = {**headers, "X-APS-Planning-Scope-Id": "corrective-other-scope"}
        response = (
            client.get(url, headers=bad_scope)
            if action == "status"
            else client.post(url, json=body, headers=bad_scope)
        )
        assert response.status_code == 403, response.text
        assert business_state(engine) == before
        if action == "status":
            missing = client.get(
                "/api/v1/planning-runs/corrective-missing/status", headers=headers
            )
            assert missing.status_code == 404, missing.text
        else:
            stale = {**body, "expected_revision": current["revision"] + 1}
            response = client.post(url, json=stale, headers=headers)
            assert response.status_code == 409, response.text
        assert business_state(engine) == before
        assert len(publisher.messages) == (0 if action == "retry" else 1)
