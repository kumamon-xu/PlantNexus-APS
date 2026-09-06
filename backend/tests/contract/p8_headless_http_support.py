"""Shared explicit Simulation composition for P8-07 HTTP tests."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from celery import Celery
from fastapi import FastAPI

from app.api.app import create_app
from app.api.dependencies.authorization import AuthorizationProvider, PrincipalContext
from app.runtime_composition import RuntimeComposition, RuntimeProcess, compose_runtime
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    RecordingCelery,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


HEADLESS_NOW = "2026-09-06T01:00:00Z"


class StaticAuthorizationProvider:
    def __init__(self, principal: PrincipalContext | None = None) -> None:
        self.principal = principal or authorized_principal()

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        return self.principal if bearer_token == "p8-headless-token" else None


class FailingAuthorizationProvider:
    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        del bearer_token
        raise RuntimeError("Bearer secret-do-not-leak from identity provider")


def authorized_principal(
    *,
    capabilities: frozenset[str] = frozenset({"view", "edit"}),
    planning_run_scope: frozenset[str] = frozenset({"*"}),
    planning_scope_scope: frozenset[str] = frozenset({"PLANNING-P8-APPLICATION"}),
    production_binding: bool = False,
) -> PrincipalContext:
    return PrincipalContext(
        actor_ref="actor:p8-headless-http-test",
        resolved_capabilities=capabilities,
        planning_run_scope=planning_run_scope,
        schedule_version_scope=frozenset(),
        export_job_scope=frozenset(),
        auth_policy_version="headless-http-auth-policy.v1",
        production_binding=production_binding,
        planning_scope_scope=planning_scope_scope,
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
    authorization_provider: AuthorizationProvider | None = None,
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
        authorization_provider=authorization_provider or StaticAuthorizationProvider(),
        runtime_application=composition.application,
        runtime_descriptor=composition.descriptor,
        runtime_http_context=composition.http_context_adapter,
        headless_clock=lambda: HEADLESS_NOW,
        runtime_closers=(composition.close,),
    )
    return application, composition, resolved_publisher


__all__ = [
    "FailingAuthorizationProvider",
    "HEADLESS_NOW",
    "StaticAuthorizationProvider",
    "authorized_principal",
    "canonical_request",
    "compose_headless_api",
    "create_headers",
    "run_headers",
]
