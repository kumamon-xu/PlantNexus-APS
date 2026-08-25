"""TASK-P3-10 pre-lookup authorization and redaction evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.contracts import PlanningWorkspaceApplicationRequest
from app.api.dependencies.authorization import (
    AuthorizationAuditRecord,
    PrincipalContext,
)
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


@dataclass(slots=True)
class RecordingApplication:
    calls: int = 0
    error: BaseException | None = None

    def execute(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> Mapping[str, object]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"correlation_id": request.context.correlation_id}


@dataclass(slots=True)
class RecordingProvider:
    principal: PrincipalContext | None
    error: BaseException | None = None
    calls: int = 0

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.principal if bearer_token == "known-token" else None


@dataclass(slots=True)
class RecordingAuditSink:
    events: list[AuthorizationAuditRecord] = field(default_factory=list)
    error: BaseException | None = None

    def record(self, event: AuthorizationAuditRecord) -> None:
        if self.error is not None:
            raise self.error
        self.events.append(event)


def _principal(*, scope: str) -> PrincipalContext:
    return PrincipalContext(
        actor_ref="actor:p3-security-test",
        resolved_capabilities=frozenset({"view"}),
        planning_run_scope=frozenset(),
        schedule_version_scope=frozenset({scope}),
        export_job_scope=frozenset(),
        auth_policy_version="simulation-security-test.v1",
    )


def test_missing_and_out_of_scope_auth_never_reach_application() -> None:
    application = RecordingApplication()
    provider = RecordingProvider(_principal(scope="different-schedule"))
    sink = RecordingAuditSink()
    api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
        planning_workspace_application=application,
        authorization_provider=provider,
        authorization_audit_sink=sink,
    )
    with TestClient(api) as client:
        missing = client.get("/api/v1/schedule-versions/schedule-version-sim-001")
        denied = client.get(
            "/api/v1/schedule-versions/schedule-version-sim-001",
            headers={"Authorization": "Bearer known-token"},
        )

    assert missing.status_code == 401
    assert missing.headers["Cache-Control"] == "no-store"
    assert denied.status_code == 403
    assert denied.headers["Cache-Control"] == "no-store"
    assert application.calls == 0
    assert provider.calls == 1
    assert [event.reason for event in sink.events] == [
        "AUTHENTICATION_REQUIRED",
        "RESOURCE_SCOPE_DENIED",
    ]
    assert "known-token" not in repr(sink.events)


def test_production_denies_before_provider_or_application_lookup() -> None:
    application = RecordingApplication()
    provider = RecordingProvider(_principal(scope="schedule-version-sim-001"))
    sink = RecordingAuditSink()
    api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.PRODUCTION,
            data_plane=DataPlane.PRODUCTION,
            code_commit="d" * 40,
        ),
        probes={},
        planning_workspace_application=application,
        authorization_provider=provider,
        authorization_audit_sink=sink,
    )
    with TestClient(api) as client:
        response = client.get(
            "/api/v1/schedule-versions/schedule-version-sim-001",
            headers={"Authorization": "Bearer known-token"},
        )

    assert response.status_code == 403
    assert response.json()["workspace_control_error"]["reason"] == (
        "AUTHORIZATION_DENIED"
    )
    assert provider.calls == 0
    assert application.calls == 0
    assert len(sink.events) == 1
    assert sink.events[0].reason == "PRODUCTION_AUTHORITY_UNAVAILABLE"


def test_unknown_application_error_is_sanitized() -> None:
    application = RecordingApplication(
        error=RuntimeError(
            "postgresql://operator:secret@database/private token=never-return"
        )
    )
    provider = RecordingProvider(_principal(scope="schedule-version-sim-001"))
    api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
        planning_workspace_application=application,
        authorization_provider=provider,
    )
    with TestClient(api) as client:
        response = client.get(
            "/api/v1/schedule-versions/schedule-version-sim-001",
            headers={"Authorization": "Bearer known-token"},
        )

    assert response.status_code == 500
    assert response.json()["product_error"] == {
        "category": "SYSTEM_ERROR",
        "code": "SYSTEM_ERROR",
    }
    for secret in ("operator", "secret", "private", "token", "RuntimeError"):
        assert secret not in response.text


def test_provider_and_denial_audit_failures_are_sanitized_and_fail_closed() -> None:
    application = RecordingApplication()
    provider_sink = RecordingAuditSink()
    provider_api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
        planning_workspace_application=application,
        authorization_provider=RecordingProvider(
            None,
            error=RuntimeError("oidc-client-secret=never-return"),
        ),
        authorization_audit_sink=provider_sink,
    )
    with TestClient(provider_api) as client:
        provider_failure = client.get(
            "/api/v1/schedule-versions/schedule-version-sim-001",
            headers={"Authorization": "Bearer known-token"},
        )

    audit_api = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
        planning_workspace_application=application,
        authorization_provider=RecordingProvider(None),
        authorization_audit_sink=RecordingAuditSink(
            error=RuntimeError("audit-dsn=never-return")
        ),
    )
    with TestClient(audit_api) as client:
        audit_failure = client.get(
            "/api/v1/schedule-versions/schedule-version-sim-001"
        )

    assert provider_failure.status_code == 503
    assert provider_failure.headers["Cache-Control"] == "no-store"
    assert provider_sink.events[0].reason == "AUTHORIZATION_PROVIDER_UNAVAILABLE"
    assert audit_failure.status_code == 500
    assert audit_failure.headers["Cache-Control"] == "no-store"
    assert application.calls == 0
    for secret in ("oidc", "client-secret", "audit-dsn", "never-return"):
        assert secret not in provider_failure.text
        assert secret not in audit_failure.text
