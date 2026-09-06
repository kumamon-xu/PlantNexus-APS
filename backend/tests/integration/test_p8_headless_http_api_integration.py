"""End-to-end Simulation evidence for TEST-P8-HEADLESS-API-001."""

from __future__ import annotations

import json
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.data_validation.canonical_ingress import canonical_json_bytes
from backend.tests.contract.p8_headless_http_support import (
    canonical_request,
    compose_headless_api,
    create_headers,
    run_headers,
)
from backend.tests.p8_runtime_support import RecordingCelery


def _cancel_document(run: dict[str, object]) -> dict[str, object]:
    return {
        "action_version": "planning-run-cancel-action.v1",
        "expected_revision": run["revision"],
        "expected_state": run["state"],
        "expected_run_fingerprint": run["run_fingerprint"],
        "reason": "Cancel the synthetic P8-07 HTTP integration run.",
    }


def _retry_document(
    run: dict[str, object], attempt: dict[str, object]
) -> dict[str, object]:
    return {
        "action_version": "planning-run-retry-action.v1",
        "expected_revision": run["revision"],
        "expected_state": run["state"],
        "expected_run_fingerprint": run["run_fingerprint"],
        "failed_attempt_id": attempt["attempt_id"],
        "failed_attempt_number": attempt["attempt_number"],
        "reason": "Retry the synthetic dispatch-failed attempt.",
    }


def test_create_status_cancel_result_and_replay_are_one_runtime_chain(
    tmp_path,
) -> None:
    api, _, publisher = compose_headless_api(tmp_path)
    request = canonical_request()
    request_bytes = canonical_json_bytes(request)
    with TestClient(api) as client:
        created = client.post(
            "/api/v1/planning-runs",
            content=request_bytes,
            headers=create_headers(request),
        )
        assert created.status_code == 202
        assert created.json()["disposition"] == "ACCEPTED"
        run_reference = created.json()["accepted"]["planning_run"]
        planning_run_id = run_reference["planning_run_id"]
        assert created.headers["location"] == (
            f"/api/v1/planning-runs/{planning_run_id}/status"
        )
        assert created.headers["x-aps-api-version"] == "headless-http.v1"
        assert created.headers["cache-control"] == "no-store"
        assert len(publisher.messages) == 1

        api.state.headless_clock = lambda: "2026-09-06T01:00:01Z"
        replayed = client.post(
            "/api/v1/planning-runs",
            content=request_bytes,
            headers=create_headers(request),
        )
        assert replayed.status_code == 202
        assert replayed.json()["idempotency"]["outcome"] == "REPLAYED"
        assert len(publisher.messages) == 1

        headers = run_headers()
        status = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/status", headers=headers
        )
        assert status.status_code == 200
        current = cast(dict[str, object], status.json())
        assert current["state"] == "CREATED"
        assert current["terminal"] is False
        assert status.headers["etag"] == f'"{current["run_fingerprint"]}"'

        premature = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/result", headers=headers
        )
        assert premature.status_code == 409
        assert premature.json()["code"] == "INVALID_STATE_TRANSITION"

        cancel_headers = {
            **headers,
            "Content-Type": "application/json",
            "Idempotency-Key": "p8-headless-cancel-key-0001",
        }
        cancel_bytes = canonical_json_bytes(_cancel_document(current))
        cancelled = client.post(
            f"/api/v1/planning-runs/{planning_run_id}/cancel",
            content=cancel_bytes,
            headers=cancel_headers,
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "CANCELLED"
        assert cancelled.json()["terminal"] is True

        cancel_replay = client.post(
            f"/api/v1/planning-runs/{planning_run_id}/cancel",
            content=cancel_bytes,
            headers=cancel_headers,
        )
        assert cancel_replay.status_code == 200
        assert cancel_replay.content == cancelled.content

        result = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/result", headers=headers
        )
        assert result.status_code == 200
        assert result.content == cancelled.content


def test_dispatch_failure_is_sanitized_and_retry_dispatches_once(tmp_path) -> None:
    publisher = RecordingCelery(fail=True)
    api, composition, _ = compose_headless_api(tmp_path, publisher=publisher)
    request = canonical_request()
    with TestClient(api) as client:
        failed_create = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=create_headers(request),
        )
        assert failed_create.status_code == 503
        assert failed_create.json()["code"] == "SYSTEM_ERROR"
        assert "redis://" not in failed_create.text
        assert "do-not-leak" not in failed_create.text

        with composition.database.engine.connect() as connection:
            planning_run_id = connection.execute(
                text("SELECT planning_run_id FROM planning_runs")
            ).scalar_one()
        status = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/status",
            headers=run_headers(),
        )
        assert status.status_code == 200
        current = cast(dict[str, object], status.json())
        assert current["state"] == "CREATED"
        with composition.database.engine.connect() as connection:
            attempt_json = connection.execute(
                text(
                    "SELECT attempt_json FROM planning_run_attempts "
                    "WHERE planning_run_id = :planning_run_id "
                    "ORDER BY attempt_number DESC LIMIT 1"
                ),
                {"planning_run_id": planning_run_id},
            ).scalar_one()
        attempt = cast(dict[str, object], json.loads(attempt_json))
        assert attempt["status"] == "DISPATCH_FAILED"

        publisher.fail = False
        retry_headers = {
            **run_headers(correlation_id="CORRELATION-P8-HEADLESS-RETRY"),
            "Content-Type": "application/json",
            "Idempotency-Key": "p8-headless-retry-key-0001",
        }
        retry_bytes = canonical_json_bytes(_retry_document(current, attempt))
        retried = client.post(
            f"/api/v1/planning-runs/{planning_run_id}/retry",
            content=retry_bytes,
            headers=retry_headers,
        )
        assert retried.status_code == 202
        assert len(publisher.messages) == 1

        api.state.headless_clock = lambda: "2026-09-06T01:00:01Z"
        retry_replay = client.post(
            f"/api/v1/planning-runs/{planning_run_id}/retry",
            content=retry_bytes,
            headers=retry_headers,
        )
        assert retry_replay.status_code == 202
        assert retry_replay.content == retried.content
        assert len(publisher.messages) == 1
