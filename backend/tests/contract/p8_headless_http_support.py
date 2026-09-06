"""Shared explicit Simulation composition for P8-07 HTTP tests."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from celery import Celery
from fastapi import FastAPI

from app.api.app import create_app
from app.application.host_authorization import (
    HEADLESS_OPERATION_CAPABILITIES,
    HostAuthorizationAdapter,
    HostAuthorizationAuditRecord,
    HostAuthorizationPolicyCatalog,
    HostIdentityProvider,
    VerifiedHostIdentity,
)
from app.infrastructure.host_authorization_audit_repository import (
    SqlAlchemyHostAuthorizationAuditRepository,
)
from app.runtime_composition import RuntimeComposition, RuntimeProcess, compose_runtime
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    RecordingCelery,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


HEADLESS_NOW = "2026-09-06T01:00:00Z"


class StaticAuthorizationProvider:
    def __init__(self, identity: VerifiedHostIdentity | None = None) -> None:
        self.identity = identity or verified_identity()

    def verify(self, bearer_token: str) -> VerifiedHostIdentity | None:
        return self.identity if bearer_token == "p8-headless-token" else None


class FailingAuthorizationProvider:
    def verify(self, bearer_token: str) -> VerifiedHostIdentity | None:
        del bearer_token
        raise RuntimeError("Bearer secret-do-not-leak from identity provider")


def verified_identity(
    *,
    subject_ref: str = "subject:p8-headless-http-test",
    identity_provider_reference: str = "identity-provider:p8-test-host",
    issuer: str = "https://identity.test.invalid/plantnexus",
    audience: str = "plantnexus-aps-test",
    issued_at_utc: str = "2026-09-06T00:30:00Z",
    expires_at_utc: str = "2026-09-06T01:30:00Z",
) -> VerifiedHostIdentity:
    return VerifiedHostIdentity.create(
        subject_ref=subject_ref,
        identity_provider_reference=identity_provider_reference,
        issuer=issuer,
        audience=audience,
        issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc,
    )


def authorization_policy(
    *,
    operations: tuple[str, ...] = tuple(HEADLESS_OPERATION_CAPABILITIES),
    scopes: tuple[tuple[str, str, str], ...] = (
        (
            "TENANT-P8-APPLICATION",
            "FACTORY-001",
            "PLANNING-P8-APPLICATION",
        ),
    ),
    subject_ref: str = "subject:p8-headless-http-test",
    revoked_subjects: tuple[str, ...] = (),
    revoked_assertions: tuple[str, ...] = (),
) -> HostAuthorizationPolicyCatalog:
    return HostAuthorizationPolicyCatalog.create(
        {
            "host_authorization_policy_version": "host-authorization-policy.v1",
            "policy_id": "p8-host-authorization-test.v1",
            "identity_provider_reference": "identity-provider:p8-test-host",
            "issuer": "https://identity.test.invalid/plantnexus",
            "audience": "plantnexus-aps-test",
            "environment": "TEST",
            "data_plane": "SIMULATION",
            "production_binding": False,
            "max_assertion_lifetime_seconds": 3_600,
            "revoked_subject_references": list(revoked_subjects),
            "revoked_assertion_references": list(revoked_assertions),
            "principals": [
                {
                    "subject_ref": subject_ref,
                    "actor_ref": "actor:p8-headless-http-test",
                    "operations": list(operations),
                    "scopes": [
                        {
                            "tenant_id": tenant_id,
                            "factory_id": factory_id,
                            "planning_scope_id": planning_scope_id,
                        }
                        for tenant_id, factory_id, planning_scope_id in scopes
                    ],
                }
            ],
        }
    )


class RecordingHostAuthorizationAuditSink:
    def __init__(self) -> None:
        self.records: list[HostAuthorizationAuditRecord] = []

    def append(self, record: HostAuthorizationAuditRecord) -> None:
        self.records.append(record)


def host_authorization_adapter(
    *,
    provider: HostIdentityProvider | None = None,
    policy: HostAuthorizationPolicyCatalog | None = None,
    audit_sink: RecordingHostAuthorizationAuditSink | None = None,
    simulation_api_enabled: bool = True,
) -> HostAuthorizationAdapter:
    return HostAuthorizationAdapter(
        provider=provider or StaticAuthorizationProvider(),
        policy=policy or authorization_policy(),
        audit_sink=audit_sink or RecordingHostAuthorizationAuditSink(),
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=simulation_api_enabled,
    )


def canonical_request() -> dict[str, object]:
    return cast(dict[str, object], worker_request())


def create_headers(document: dict[str, object]) -> dict[str, str]:
    return {
        "Authorization": "Bearer p8-headless-token",
        "Content-Type": "application/json; charset=utf-8",
        "Idempotency-Key": cast(str, document["idempotency_key"]),
        "X-Correlation-Id": cast(str, document["correlation_id"]),
    }


def run_headers(
    *, correlation_id: str = "CORRELATION-P8-HEADLESS-RUN"
) -> dict[str, str]:
    return {
        "Authorization": "Bearer p8-headless-token",
        "X-APS-Tenant-Id": "TENANT-P8-APPLICATION",
        "X-APS-Factory-Id": "FACTORY-001",
        "X-APS-Planning-Scope-Id": "PLANNING-P8-APPLICATION",
        "X-Correlation-Id": correlation_id,
    }


def compose_headless_api(
    tmp_path: Path,
    *,
    publisher: RecordingCelery | None = None,
    authorization_provider: HostIdentityProvider | None = None,
    authorization_policy_catalog: HostAuthorizationPolicyCatalog | None = None,
    identities: tuple[str, ...] = (
        "headless-dispatch-001",
        "headless-dispatch-002",
        "headless-dispatch-003",
    ),
) -> tuple[FastAPI, RuntimeComposition, RecordingCelery]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database_path = tmp_path / "headless-http.db"
    seed, _ = migrated_engine(database_path)
    seed.dispose()
    settings = runtime_settings(
        tmp_path, database_url=f"sqlite:///{database_path.as_posix()}"
    )
    resolved_publisher = publisher or RecordingCelery()
    composition = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, resolved_publisher),
        identity_factory=FixedIdentityFactory(*identities),
    )
    application = create_app(
        settings,
        probes=composition.probes,
        runtime_application=composition.application,
        runtime_descriptor=composition.descriptor,
        runtime_http_context=composition.http_context_adapter,
        host_authorization_adapter=HostAuthorizationAdapter(
            provider=authorization_provider or StaticAuthorizationProvider(),
            policy=authorization_policy_catalog or authorization_policy(),
            audit_sink=SqlAlchemyHostAuthorizationAuditRepository(
                composition.database.engine, data_plane="SIMULATION"
            ),
            environment="TEST",
            data_plane="SIMULATION",
            simulation_api_enabled=True,
        ),
        headless_clock=lambda: HEADLESS_NOW,
        runtime_closers=(composition.close,),
    )
    return application, composition, resolved_publisher


__all__ = [
    "FailingAuthorizationProvider",
    "HEADLESS_NOW",
    "StaticAuthorizationProvider",
    "RecordingHostAuthorizationAuditSink",
    "authorization_policy",
    "canonical_request",
    "compose_headless_api",
    "create_headers",
    "host_authorization_adapter",
    "run_headers",
    "verified_identity",
]
