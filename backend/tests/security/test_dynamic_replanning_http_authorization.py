"""TASK-P4-12 pre-lookup authorization and redaction evidence."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.dependencies.authorization import PrincipalContext
from app.api.replanning_check import (
    RecordingAuditSink,
    RecordingDynamicReplanningApplication,
    RecordingProvider,
    build_replanning_query,
    compact_query,
    load_replanning_api_fixture,
)
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


ROOT = Path(__file__).resolve().parents[3]


def _principal(
    scope: str, *, capabilities: frozenset[str] = frozenset({"event_view"})
) -> PrincipalContext:
    return PrincipalContext(
        actor_ref="actor:p4-http-security",
        resolved_capabilities=capabilities,
        planning_run_scope=frozenset(),
        schedule_version_scope=frozenset(),
        export_job_scope=frozenset(),
        auth_policy_version="simulation-p4-http-security.v1",
        planning_scope_scope=frozenset({scope}),
    )


def _event_query() -> tuple[str, str, str]:
    event = load_replanning_api_fixture(ROOT)["event"]
    event_id = str(event["event_id"])
    scope = str(event["planning_scope_id"])
    query = build_replanning_query(
        query_kind="EXECUTION_EVENT",
        resource_id=event_id,
        planning_scope_id=scope,
        correlation_id="correlation-p4-security-001",
    )
    return event_id, scope, compact_query(query)


def test_missing_capability_and_scope_denials_never_reach_application() -> None:
    event_id, scope, query = _event_query()
    for principal, reason in (
        (_principal(scope, capabilities=frozenset()), "CAPABILITY_DENIED"),
        (_principal("different-planning-scope"), "RESOURCE_SCOPE_DENIED"),
    ):
        application = RecordingDynamicReplanningApplication()
        sink = RecordingAuditSink()
        api = create_app(
            Settings(
                runtime_environment=RuntimeEnvironment.TEST,
                data_plane=DataPlane.SIMULATION,
                simulation_api_enabled=True,
            ),
            probes={},
            dynamic_replanning_application=application,
            authorization_provider=RecordingProvider(principal),
            authorization_audit_sink=sink,
        )
        with TestClient(api) as client:
            response = client.get(
                f"/api/v1/execution-events/{event_id}",
                params={"query": query},
                headers={
                    "Authorization": "Bearer p4-machine-token",
                    "X-Correlation-Id": "correlation-p4-security-001",
                },
            )

        assert response.status_code == 403
        assert application.requests == []
        assert sink.events[-1].reason == reason
        assert sink.events[-1].resource_type == "PLANNING_SCOPE"


def test_production_denies_before_provider_or_application_lookup() -> None:
    event_id, scope, query = _event_query()
    application = RecordingDynamicReplanningApplication()
    provider = RecordingProvider(_principal(scope))
    sink = RecordingAuditSink()
    api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.PRODUCTION,
            data_plane=DataPlane.PRODUCTION,
            simulation_api_enabled=False,
            code_commit="d" * 40,
        ),
        probes={},
        dynamic_replanning_application=application,
        authorization_provider=provider,
        authorization_audit_sink=sink,
    )
    with TestClient(api) as client:
        response = client.get(
            f"/api/v1/execution-events/{event_id}",
            params={"query": query},
            headers={
                "Authorization": "Bearer p4-machine-token",
                "X-Correlation-Id": "correlation-p4-security-001",
            },
        )

    assert response.status_code == 403
    assert provider.calls == 0
    assert application.requests == []
    assert [event.reason for event in sink.events] == [
        "PRODUCTION_AUTHORITY_UNAVAILABLE"
    ]


def test_unknown_exception_is_sanitized_and_raw_token_is_not_audited() -> None:
    event_id, scope, query = _event_query()
    application = RecordingDynamicReplanningApplication(
        failure=RuntimeError(
            "postgresql://operator:secret@database/private token=never-return"
        )
    )
    sink = RecordingAuditSink()
    api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
        dynamic_replanning_application=application,
        authorization_provider=RecordingProvider(_principal(scope)),
        authorization_audit_sink=sink,
    )
    with TestClient(api) as client:
        response = client.get(
            f"/api/v1/execution-events/{event_id}",
            params={"query": query},
            headers={
                "Authorization": "Bearer p4-machine-token",
                "X-Correlation-Id": "correlation-p4-security-001",
            },
        )

    assert response.status_code == 500
    for secret in (
        "operator",
        "secret",
        "private",
        "RuntimeError",
        "p4-machine-token",
    ):
        assert secret not in response.text
        assert secret not in repr(sink.events)
