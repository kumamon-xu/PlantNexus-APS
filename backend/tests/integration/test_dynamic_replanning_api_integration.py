"""TASK-P4-12 machine report and fail-closed composition tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.replanning_check import (
    RecordingProvider,
    build_replanning_query,
    compact_query,
    load_replanning_api_fixture,
    run_replanning_api_checks,
)
from app.api.dependencies.authorization import PrincipalContext
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


ROOT = Path(__file__).resolve().parents[3]


def test_replanning_http_machine_contract_is_complete() -> None:
    report = run_replanning_api_checks(ROOT)
    assert report["report_version"] == "p4-replanning-api-report.v1"
    assert report["task_id"] == "TASK-P4-12"
    assert report["status"] == "PASS"
    assert report["diff_base"] == "f4a54d3bb065b5cc8b51c450ffdc435bcc77d384"
    assert report["impact_rules"] == [
        "IMPACT-API",
        "IMPACT-DOCS",
        "IMPACT-FRONTEND",
        "IMPACT-INFRA",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["counts"] == {
        "api_paths": 8,
        "http_operations": 9,
        "successful_delegations": 9,
        "p3_frozen_operations": 18,
        "production_provider_lookups": 0,
        "production_application_calls": 0,
        "router_business_state_transitions": 0,
        "solver_validator_projection_invocations": 0,
    }
    assert report["issues"] == []


def test_unconfigured_p4_application_fails_closed_after_authorization() -> None:
    fixture = load_replanning_api_fixture(ROOT)
    event = fixture["event"]
    event_id = str(event["event_id"])
    scope = str(event["planning_scope_id"])
    query = build_replanning_query(
        query_kind="EXECUTION_EVENT",
        resource_id=event_id,
        planning_scope_id=scope,
        correlation_id="correlation-p4-unavailable-001",
    )
    principal = PrincipalContext(
        actor_ref="actor:p4-unavailable-test",
        resolved_capabilities=frozenset({"event_view"}),
        planning_run_scope=frozenset(),
        schedule_version_scope=frozenset(),
        export_job_scope=frozenset(),
        auth_policy_version="simulation-p4-unavailable.v1",
        planning_scope_scope=frozenset({scope}),
    )
    api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
        authorization_provider=RecordingProvider(principal),
    )
    with TestClient(api) as client:
        response = client.get(
            f"/api/v1/execution-events/{event_id}",
            params={"query": compact_query(query)},
            headers={
                "Authorization": "Bearer p4-machine-token",
                "X-Correlation-Id": "correlation-p4-unavailable-001",
            },
        )

    assert response.status_code == 503
    assert response.json()["product_error"] == {
        "category": "SYSTEM_ERROR",
        "code": "SYSTEM_ERROR",
    }
    assert response.headers["Cache-Control"] == "no-store"
