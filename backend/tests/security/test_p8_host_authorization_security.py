"""Fail-closed security evidence for TEST-P8-HOST-AUTHORIZATION-001."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.application.host_authorization import (
    HostAuthorizationAdapter,
    HostAuthorizationAuditRecord,
    HostAuthorizationError,
    HostAuthorizationReason,
    HostAuthorizationRequest,
    UnavailableHostAuthorizationAdapter,
    VerifiedHostIdentity,
)
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.infrastructure.host_authorization_audit_repository import (
    SqlAlchemyHostAuthorizationAuditRepository,
)
from backend.tests.contract.p8_headless_http_support import (
    FailingAuthorizationProvider,
    RecordingHostAuthorizationAuditSink,
    StaticAuthorizationProvider,
    authorization_policy,
    canonical_request,
    compose_headless_api,
    create_headers,
    host_authorization_adapter,
    run_headers,
    verified_identity,
)


def _request(
    *,
    operation_id: str = "getHeadlessPlanningRunStatus",
    tenant_id: str = "TENANT-P8-APPLICATION",
    factory_id: str = "FACTORY-001",
    planning_scope_id: str = "PLANNING-P8-APPLICATION",
    resource_id: str = "planning-run-security-001",
) -> HostAuthorizationRequest:
    return HostAuthorizationRequest.create(
        operation_id=operation_id,
        tenant_id=tenant_id,
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        resource_type="PLANNING_RUN",
        resource_id=resource_id,
        correlation_id="CORRELATION-P8-HOST-AUTH-SECURITY",
        occurred_at_utc="2026-09-06T01:00:00Z",
    )


def _assert_denied(
    adapter: HostAuthorizationAdapter | UnavailableHostAuthorizationAdapter,
    sink: RecordingHostAuthorizationAuditSink,
    *,
    header: str | None,
    expected_reason: HostAuthorizationReason,
    request: HostAuthorizationRequest | None = None,
) -> None:
    with pytest.raises(HostAuthorizationError) as captured:
        adapter.authorize(header, request or _request())
    assert captured.value.reason is expected_reason
    assert captured.value.status_code in {401, 403, 500, 503}
    assert len(sink.records) == 1
    assert sink.records[0].document["outcome"] == "DENIED"
    assert sink.records[0].document["reason"] == expected_reason.value


def test_missing_malformed_forged_and_unavailable_identity_fail_closed() -> None:
    cases = (
        (
            StaticAuthorizationProvider(),
            None,
            HostAuthorizationReason.AUTHENTICATION_REQUIRED,
        ),
        (
            StaticAuthorizationProvider(),
            "Basic p8-headless-token",
            HostAuthorizationReason.INVALID_AUTHENTICATION,
        ),
        (
            StaticAuthorizationProvider(),
            "Bearer token with whitespace",
            HostAuthorizationReason.INVALID_AUTHENTICATION,
        ),
        (
            StaticAuthorizationProvider(),
            f"Bearer {'x' * 4_097}",
            HostAuthorizationReason.INVALID_AUTHENTICATION,
        ),
        (
            StaticAuthorizationProvider(),
            "Bearer forged-host-token",
            HostAuthorizationReason.INVALID_AUTHENTICATION,
        ),
        (
            FailingAuthorizationProvider(),
            "Bearer p8-headless-token",
            HostAuthorizationReason.IDENTITY_PROVIDER_UNAVAILABLE,
        ),
    )
    for provider, header, reason in cases:
        sink = RecordingHostAuthorizationAuditSink()
        adapter = host_authorization_adapter(provider=provider, audit_sink=sink)
        _assert_denied(adapter, sink, header=header, expected_reason=reason)
        rendered = json.dumps(sink.records[0].document, sort_keys=True)
        assert "p8-headless-token" not in rendered
        assert "forged-host-token" not in rendered
        assert "secret-do-not-leak" not in rendered
        assert "RuntimeError" not in rendered


def test_provider_projection_time_revocation_and_subject_mapping_are_revalidated() -> None:
    token_reference = f"sha256:{sha256(b'p8-headless-token').hexdigest()}"
    invalid_version = VerifiedHostIdentity(
        subject_ref="subject:p8-headless-http-test",
        identity_provider_reference="identity-provider:p8-test-host",
        issuer="https://identity.test.invalid/plantnexus",
        audience="plantnexus-aps-test",
        issued_at_utc="2026-09-06T00:30:00Z",
        expires_at_utc="2026-09-06T01:30:00Z",
        identity_version="verified-host-identity.v999",
    )
    cases = (
        (
            invalid_version,
            authorization_policy(),
            HostAuthorizationReason.INVALID_PROVIDER_CONTEXT,
        ),
        (
            verified_identity(identity_provider_reference="identity-provider:other"),
            authorization_policy(),
            HostAuthorizationReason.INVALID_PROVIDER_CONTEXT,
        ),
        (
            verified_identity(issuer="https://issuer.invalid/untrusted"),
            authorization_policy(),
            HostAuthorizationReason.ISSUER_MISMATCH,
        ),
        (
            verified_identity(audience="another-service"),
            authorization_policy(),
            HostAuthorizationReason.AUDIENCE_MISMATCH,
        ),
        (
            verified_identity(
                issued_at_utc="2026-09-06T01:01:00Z",
                expires_at_utc="2026-09-06T01:30:00Z",
            ),
            authorization_policy(),
            HostAuthorizationReason.ASSERTION_NOT_YET_VALID,
        ),
        (
            verified_identity(
                issued_at_utc="2026-09-06T00:01:00Z",
                expires_at_utc="2026-09-06T01:00:00Z",
            ),
            authorization_policy(),
            HostAuthorizationReason.ASSERTION_EXPIRED,
        ),
        (
            verified_identity(
                issued_at_utc="2026-09-06T00:00:00Z",
                expires_at_utc="2026-09-06T02:00:00Z",
            ),
            authorization_policy(),
            HostAuthorizationReason.ASSERTION_LIFETIME_EXCEEDED,
        ),
        (
            verified_identity(),
            authorization_policy(revoked_assertions=(token_reference,)),
            HostAuthorizationReason.ASSERTION_REVOKED,
        ),
        (
            verified_identity(),
            authorization_policy(
                revoked_subjects=("subject:p8-headless-http-test",)
            ),
            HostAuthorizationReason.SUBJECT_REVOKED,
        ),
        (
            verified_identity(subject_ref="subject:unmapped-host-user"),
            authorization_policy(),
            HostAuthorizationReason.SUBJECT_UNMAPPED,
        ),
    )
    for identity, policy, reason in cases:
        sink = RecordingHostAuthorizationAuditSink()
        adapter = host_authorization_adapter(
            provider=StaticAuthorizationProvider(identity),
            policy=policy,
            audit_sink=sink,
        )
        _assert_denied(
            adapter,
            sink,
            header="Bearer p8-headless-token",
            expected_reason=reason,
        )


def test_operation_and_each_composite_scope_dimension_are_server_owned() -> None:
    operation_sink = RecordingHostAuthorizationAuditSink()
    operation_adapter = host_authorization_adapter(
        policy=authorization_policy(operations=("createHeadlessPlanningRun",)),
        audit_sink=operation_sink,
    )
    _assert_denied(
        operation_adapter,
        operation_sink,
        header="Bearer p8-headless-token",
        expected_reason=HostAuthorizationReason.OPERATION_DENIED,
    )

    requests = (
        _request(tenant_id="TENANT-OTHER"),
        _request(factory_id="FACTORY-OTHER"),
        _request(planning_scope_id="PLANNING-OTHER"),
    )
    for request in requests:
        sink = RecordingHostAuthorizationAuditSink()
        adapter = host_authorization_adapter(audit_sink=sink)
        _assert_denied(
            adapter,
            sink,
            header="Bearer p8-headless-token",
            expected_reason=HostAuthorizationReason.FACTORY_SCOPE_DENIED,
            request=request,
        )


def test_cross_scope_existing_and_unknown_resources_are_not_enumerable(
    tmp_path: Path,
) -> None:
    api, composition, _ = compose_headless_api(tmp_path)
    document = canonical_request()
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
        denied_headers = {
            **run_headers(correlation_id="CORRELATION-P8-NO-ENUMERATION"),
            "X-APS-Tenant-Id": "TENANT-OTHER",
        }
        existing = client.get(
            f"/api/v1/planning-runs/{planning_run_id}/status",
            headers=denied_headers,
        )
        unknown_id = "planning-run-does-not-exist"
        unknown = client.get(
            f"/api/v1/planning-runs/{unknown_id}/status",
            headers=denied_headers,
        )
        assert existing.status_code == unknown.status_code == 403
        assert existing.content == unknown.content
        assert planning_run_id not in existing.text
        assert unknown_id not in unknown.text
        with composition.database.engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM planning_runs")) == 1

    repository = SqlAlchemyHostAuthorizationAuditRepository(
        composition.database.engine, data_plane="SIMULATION"
    )
    records = repository.list_for_correlation("CORRELATION-P8-NO-ENUMERATION")
    assert len(records) == 2
    assert {record["reason"] for record in records} == {"FACTORY_SCOPE_DENIED"}
    assert records[0]["resource_reference"] != records[1]["resource_reference"]
    rendered = json.dumps(records, sort_keys=True)
    assert planning_run_id not in rendered
    assert unknown_id not in rendered


class _FailingAuditSink:
    def append(self, record: HostAuthorizationAuditRecord) -> None:
        del record
        raise RuntimeError("database secret-do-not-leak from audit sink")


def test_audit_failure_denies_before_business_side_effect_and_is_sanitized(
    tmp_path: Path,
) -> None:
    api, composition, publisher = compose_headless_api(tmp_path)
    api.state.host_authorization_adapter = HostAuthorizationAdapter(
        provider=StaticAuthorizationProvider(),
        policy=authorization_policy(),
        audit_sink=_FailingAuditSink(),
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
    )
    document = canonical_request()
    with TestClient(api) as client:
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(document),
            headers=create_headers(document),
        )
        assert response.status_code == 500
        assert response.json()["namespace"] == "PRODUCT"
        assert response.json()["product_error"]["code"] == "SYSTEM_ERROR"
        assert "secret-do-not-leak" not in response.text
        assert "database" not in response.text.lower()
        with composition.database.engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM planning_runs")) == 0
    assert publisher.messages == []


def test_unavailable_and_production_authority_are_explicitly_default_deny() -> None:
    simulation_sink = RecordingHostAuthorizationAuditSink()
    simulation = UnavailableHostAuthorizationAdapter(
        audit_sink=simulation_sink,
        environment="TEST",
        data_plane="SIMULATION",
    )
    _assert_denied(
        simulation,
        simulation_sink,
        header="Bearer p8-headless-token",
        expected_reason=HostAuthorizationReason.IDENTITY_CONFIGURATION_UNAVAILABLE,
    )

    production_sink = RecordingHostAuthorizationAuditSink()
    production = UnavailableHostAuthorizationAdapter(
        audit_sink=production_sink,
        environment="PRODUCTION",
        data_plane="PRODUCTION",
    )
    _assert_denied(
        production,
        production_sink,
        header="Bearer p8-headless-token",
        expected_reason=HostAuthorizationReason.PRODUCTION_AUTHORITY_UNAVAILABLE,
    )
