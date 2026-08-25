"""TASK-P3-10 HTTP delegation, error, and correlation integration evidence."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.planning_workspace_check import run_http_api_checks
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


ROOT = Path(__file__).resolve().parents[3]


def test_planning_workspace_http_machine_contract_is_complete() -> None:
    report = run_http_api_checks(ROOT)
    assert report["report_version"] == "p3-planning-workspace-api-report.v1"
    assert report["task_id"] == "TASK-P3-10"
    assert report["status"] == "PASS"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "api_paths": 17,
        "http_operations": 17,
        "successful_delegations": 17,
        "mapped_error_reasons": 8,
        "production_provider_lookups": 0,
        "production_application_calls": 0,
        "router_business_state_transitions": 0,
        "solver_validator_invocations": 0,
    }
    assert report["issues"] == []


def test_unconfigured_api_is_fail_closed_and_validation_is_sanitized() -> None:
    application = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
    )
    with TestClient(application) as client:
        unauthenticated = client.get(
            "/api/v1/schedule-versions/schedule-version-sim-001"
        )
        invalid_body = client.post(
            "/api/v1/schedule-versions/schedule-version-sim-001/approve",
            content="not-json",
            headers={
                "Authorization": "Bearer do-not-reflect",
                "Content-Type": "application/json",
                "Idempotency-Key": "p3-http-invalid-0001",
            },
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["WWW-Authenticate"] == "Bearer"
    assert invalid_body.status_code == 422
    assert invalid_body.json()["error_version"] == "planning-workspace-error.v1"
    assert "not-json" not in invalid_body.text
    assert "do-not-reflect" not in invalid_body.text
