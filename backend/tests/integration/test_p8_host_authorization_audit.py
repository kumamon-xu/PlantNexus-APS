"""Durable Runtime and audit evidence for TEST-P8-HOST-AUTHORIZATION-001."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import cast

from alembic import command
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.api.app import create_runtime_app
from app.application.host_authorization import (
    HEADLESS_OPERATION_CAPABILITIES,
    HostAuthorizationAdapter,
    HostAuthorizationRequest,
    VerifiedHostIdentity,
)
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.domain.types import format_utc_instant
from app.infrastructure.host_authorization_audit_repository import (
    HostAuthorizationAuditPersistenceError,
    SqlAlchemyHostAuthorizationAuditRepository,
)
from backend.tests.contract.p8_headless_http_support import (
    StaticAuthorizationProvider,
    authorization_policy,
    canonical_request,
    compose_headless_api,
    create_headers,
    run_headers,
)
from backend.tests.p8_runtime_support import runtime_settings
from backend.tests.p8_solver_worker_support import migrated_engine


def _cancel_document(run: dict[str, object]) -> dict[str, object]:
    return {
        "action_version": "planning-run-cancel-action.v1",
        "expected_revision": run["revision"],
        "expected_state": run["state"],
        "expected_run_fingerprint": run["run_fingerprint"],
        "reason": "P8-08 audit coverage cancellation.",
    }


def _retry_document(run: dict[str, object]) -> dict[str, object]:
    return {
        "action_version": "planning-run-retry-action.v1",
        "expected_revision": run["revision"],
        "expected_state": run["state"],
        "expected_run_fingerprint": run["run_fingerprint"],
        "failed_attempt_id": "planning-run-attempt-not-found",
        "failed_attempt_number": 1,
        "reason": "P8-08 authorization-before-application evidence.",
    }


def _authorization_request() -> HostAuthorizationRequest:
    return HostAuthorizationRequest.create(
        operation_id="getHeadlessPlanningRunStatus",
        tenant_id="TENANT-P8-APPLICATION",
        factory_id="FACTORY-001",
        planning_scope_id="PLANNING-P8-APPLICATION",
        resource_type="PLANNING_RUN",
        resource_id="planning-run-audit-repository-001",
        correlation_id="CORRELATION-P8-HOST-AUDIT-REPOSITORY",
        occurred_at_utc="2026-09-06T01:00:00Z",
    )


def test_every_headless_operation_persists_one_complete_sanitized_decision(
    tmp_path: Path,
) -> None:
    api, composition, _ = compose_headless_api(tmp_path)
    document = canonical_request()
    correlations = {
        "createHeadlessPlanningRun": cast(str, document["correlation_id"]),
        "getHeadlessPlanningRunStatus": "CORRELATION-P8-HOST-AUTH-STATUS",
        "retryHeadlessPlanningRun": "CORRELATION-P8-HOST-AUTH-RETRY",
        "cancelHeadlessPlanningRun": "CORRELATION-P8-HOST-AUTH-CANCEL",
        "getHeadlessPlanningRunResult": "CORRELATION-P8-HOST-AUTH-RESULT",
    }
    with TestClient(api) as client:
        created = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(document),
            headers=create_headers(document),
        )
        assert created.status_code == 202
        planning_run_id = cast(
            str, created.json()["accepted"]["planning_run"]["planning_run_id"]
        )

        status = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/status",
            headers=run_headers(correlation_id=correlations["getHeadlessPlanningRunStatus"]),
        )
        assert status.status_code == 200
        current = cast(dict[str, object], status.json())

        retry_headers = {
            **run_headers(correlation_id=correlations["retryHeadlessPlanningRun"]),
            "Content-Type": "application/json",
            "Idempotency-Key": "p8-host-authorization-retry-key-0001",
        }
        retry = client.post(
            f"/api/v1/planning-runs/{planning_run_id}/retry",
            content=canonical_json_bytes(_retry_document(current)),
            headers=retry_headers,
        )
        assert retry.status_code in {404, 409}

        cancel_headers = {
            **run_headers(correlation_id=correlations["cancelHeadlessPlanningRun"]),
            "Content-Type": "application/json",
            "Idempotency-Key": "p8-host-authorization-cancel-key-0001",
        }
        cancelled = client.post(
            f"/api/v1/planning-runs/{planning_run_id}/cancel",
            content=canonical_json_bytes(_cancel_document(current)),
            headers=cancel_headers,
        )
        assert cancelled.status_code == 200

        result = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/result",
            headers=run_headers(correlation_id=correlations["getHeadlessPlanningRunResult"]),
        )
        assert result.status_code == 200

    repository = SqlAlchemyHostAuthorizationAuditRepository(
        composition.database.engine, data_plane="SIMULATION"
    )
    assert repository.count() == len(HEADLESS_OPERATION_CAPABILITIES)
    records = []
    for operation_id, correlation_id in correlations.items():
        selected = repository.list_for_correlation(correlation_id)
        assert len(selected) == 1
        assert selected[0]["operation_id"] == operation_id
        records.append(selected[0])

    expected_assertion = f"sha256:{sha256(b'p8-headless-token').hexdigest()}"
    expected_scope = {
        "tenant_id": "TENANT-P8-APPLICATION",
        "factory_id": "FACTORY-001",
        "planning_scope_id": "PLANNING-P8-APPLICATION",
    }
    assert {record["outcome"] for record in records} == {"ALLOWED"}
    assert {record["reason"] for record in records} == {"AUTHORIZED"}
    assert {record["assertion_reference"] for record in records} == {
        expected_assertion
    }
    assert {record["required_capability"] for record in records} == {
        "view",
        "edit",
    }
    assert all(record["requested_scope"] == expected_scope for record in records)
    rendered = json.dumps(records, sort_keys=True)
    assert "p8-headless-token" not in rendered
    assert planning_run_id not in rendered
    assert "password" not in rendered.lower()


def test_audit_repository_is_append_only_integrity_checked_and_migration_reversible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "host-authorization-audit.db"
    engine, configuration = migrated_engine(database_path)
    repository = SqlAlchemyHostAuthorizationAuditRepository(
        engine, data_plane="SIMULATION"
    )
    adapter = HostAuthorizationAdapter(
        provider=StaticAuthorizationProvider(),
        policy=authorization_policy(),
        audit_sink=repository,
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
        audit_id_factory=lambda: f"host-authz-event-{'1' * 32}",
    )
    request = _authorization_request()
    adapter.authorize("Bearer p8-headless-token", request)
    adapter.authorize("Bearer p8-headless-token", request)
    assert repository.count() == 1
    event_id = f"host-authz-event-{'1' * 32}"
    assert repository.get(event_id) is not None
    with pytest.raises(HostAuthorizationAuditPersistenceError):
        repository.update(event_id)
    with pytest.raises(HostAuthorizationAuditPersistenceError):
        repository.delete(event_id)

    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE headless_authorization_audit_records "
                "SET outcome = 'DENIED' WHERE audit_event_id = :audit_event_id"
            ),
            {"audit_event_id": event_id},
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM headless_authorization_audit_records "
                "WHERE audit_event_id = :audit_event_id"
            ),
            {"audit_event_id": event_id},
        )

    before = set(inspect(engine).get_table_names())
    assert "headless_authorization_audit_records" in before
    engine.dispose()
    try:
        command.downgrade(configuration, "0008_planning_run_solver_worker")
        downgraded = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            after = set(inspect(downgraded).get_table_names())
            assert "headless_authorization_audit_records" not in after
            assert before - {"headless_authorization_audit_records"} <= after
        finally:
            downgraded.dispose()

        command.upgrade(configuration, "head")
        upgraded = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            replay = SqlAlchemyHostAuthorizationAuditRepository(
                upgraded, data_plane="SIMULATION"
            )
            assert replay.count() == 0
        finally:
            upgraded.dispose()
    finally:
        command.downgrade(configuration, "base")


class _CurrentIdentityProvider:
    def verify(self, bearer_token: str) -> VerifiedHostIdentity | None:
        if bearer_token != "p8-headless-token":
            return None
        now = datetime.now(UTC).replace(microsecond=0)
        return VerifiedHostIdentity.create(
            subject_ref="subject:p8-headless-http-test",
            identity_provider_reference="identity-provider:p8-test-host",
            issuer="https://identity.test.invalid/plantnexus",
            audience="plantnexus-aps-test",
            issued_at_utc=format_utc_instant(now - timedelta(minutes=5)),
            expires_at_utc=format_utc_instant(now + timedelta(minutes=5)),
        )


def test_deployable_runtime_loads_injected_test_provider_and_defaults_closed(
    tmp_path: Path,
) -> None:
    authorized_path = tmp_path / "authorized-runtime.db"
    seed, configuration = migrated_engine(authorized_path)
    seed.dispose()
    settings = runtime_settings(
        tmp_path,
        database_url=f"sqlite:///{authorized_path.as_posix()}",
    )
    application = create_runtime_app(
        settings,
        host_identity_provider=_CurrentIdentityProvider(),
        host_authorization_policy=authorization_policy(),
    )
    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/v1/planning-runs/planning-run-not-found/status",
                headers=run_headers(correlation_id="CORRELATION-P8-RUNTIME-INJECTED"),
            )
            assert response.status_code == 404
        engine = create_engine(f"sqlite:///{authorized_path.as_posix()}")
        try:
            repository = SqlAlchemyHostAuthorizationAuditRepository(
                engine, data_plane="SIMULATION"
            )
            assert repository.count() == 1
            assert repository.list_for_correlation(
                "CORRELATION-P8-RUNTIME-INJECTED"
            )[0]["outcome"] == "ALLOWED"
        finally:
            engine.dispose()
    finally:
        command.downgrade(configuration, "base")

    unavailable_path = tmp_path / "unavailable-runtime.db"
    seed, unavailable_configuration = migrated_engine(unavailable_path)
    seed.dispose()
    unavailable_root = tmp_path / "unavailable"
    unavailable_root.mkdir()
    unavailable_settings = runtime_settings(
        unavailable_root,
        database_url=f"sqlite:///{unavailable_path.as_posix()}",
    )
    unavailable = create_runtime_app(unavailable_settings)
    try:
        with TestClient(unavailable) as client:
            denied = client.get(
                "/api/v1/planning-runs/planning-run-not-found/status",
                headers=run_headers(correlation_id="CORRELATION-P8-RUNTIME-UNAVAILABLE"),
            )
            assert denied.status_code == 503
            assert denied.json()["details"]["reason"] == "AUTHORIZATION_DENIED"
        engine = create_engine(f"sqlite:///{unavailable_path.as_posix()}")
        try:
            repository = SqlAlchemyHostAuthorizationAuditRepository(
                engine, data_plane="SIMULATION"
            )
            record = repository.list_for_correlation(
                "CORRELATION-P8-RUNTIME-UNAVAILABLE"
            )[0]
            assert record["outcome"] == "DENIED"
            assert record["reason"] == "IDENTITY_CONFIGURATION_UNAVAILABLE"
        finally:
            engine.dispose()
    finally:
        command.downgrade(unavailable_configuration, "base")
