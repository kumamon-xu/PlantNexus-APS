"""Strict contracts for TEST-P8-HOST-AUTHORIZATION-001."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from app.application.host_authorization import (
    HEADLESS_OPERATION_CAPABILITIES,
    HOST_AUTHORIZATION_POLICY_VERSION,
    VERIFIED_HOST_IDENTITY_VERSION,
    HostAuthorizationAuditRecord,
    HostAuthorizationPolicyCatalog,
    HostAuthorizationRequest,
    HostPlanningScope,
    VerifiedHostIdentity,
)
from backend.tests.contract.p8_headless_http_support import (
    RecordingHostAuthorizationAuditSink,
    authorization_policy,
    host_authorization_adapter,
    verified_identity,
)


def _request(operation_id: str) -> HostAuthorizationRequest:
    return HostAuthorizationRequest.create(
        operation_id=operation_id,
        tenant_id="TENANT-P8-APPLICATION",
        factory_id="FACTORY-001",
        planning_scope_id="PLANNING-P8-APPLICATION",
        resource_type="PLANNING_RUN",
        resource_id="planning-run-contract-001",
        correlation_id=f"CORRELATION-{operation_id}",
        occurred_at_utc="2026-09-06T01:00:00Z",
    )


def test_policy_is_canonical_order_independent_and_exposes_only_safe_metadata() -> None:
    scopes = (
        ("TENANT-P8-APPLICATION", "FACTORY-002", "PLANNING-P8-SECONDARY"),
        ("TENANT-P8-APPLICATION", "FACTORY-001", "PLANNING-P8-APPLICATION"),
    )
    first = authorization_policy(
        operations=tuple(reversed(tuple(HEADLESS_OPERATION_CAPABILITIES))),
        scopes=scopes,
    )
    second = authorization_policy(
        operations=tuple(HEADLESS_OPERATION_CAPABILITIES),
        scopes=tuple(reversed(scopes)),
    )

    assert first.canonical_bytes == second.canonical_bytes
    assert first.fingerprint == second.fingerprint
    assert first.safe_reference == {
        "policy_version": HOST_AUTHORIZATION_POLICY_VERSION,
        "policy_id": "p8-host-authorization-test.v1",
        "policy_fingerprint": first.fingerprint,
        "identity_provider_reference": "identity-provider:p8-test-host",
        "principal_count": 1,
        "scope_count": 2,
    }
    safe = json.dumps(first.safe_reference, sort_keys=True)
    assert "subject:p8-headless-http-test" not in safe
    assert "actor:p8-headless-http-test" not in safe


def test_policy_rejects_unknown_authority_wildcards_duplicates_and_production() -> None:
    base = json.loads(authorization_policy().canonical_bytes)
    mutations: list[dict[str, object]] = []

    unknown = deepcopy(base)
    unknown["request_owned_scope"] = "forbidden"
    mutations.append(unknown)

    production = deepcopy(base)
    production["environment"] = "PRODUCTION"
    production["data_plane"] = "PRODUCTION"
    production["production_binding"] = True
    mutations.append(production)

    wildcard = deepcopy(base)
    wildcard["principals"][0]["scopes"][0]["factory_id"] = "*"
    mutations.append(wildcard)

    duplicate_operation = deepcopy(base)
    duplicate_operation["principals"][0]["operations"].append(
        "createHeadlessPlanningRun"
    )
    mutations.append(duplicate_operation)

    unknown_operation = deepcopy(base)
    unknown_operation["principals"][0]["operations"] = ["installArbitraryPlugin"]
    mutations.append(unknown_operation)

    duplicate_scope = deepcopy(base)
    duplicate_scope["principals"][0]["scopes"].append(
        deepcopy(duplicate_scope["principals"][0]["scopes"][0])
    )
    mutations.append(duplicate_scope)

    duplicate_subject = deepcopy(base)
    duplicate_subject["principals"].append(
        deepcopy(duplicate_subject["principals"][0])
    )
    mutations.append(duplicate_subject)

    boolean_lifetime = deepcopy(base)
    boolean_lifetime["max_assertion_lifetime_seconds"] = True
    mutations.append(boolean_lifetime)

    raw_revocation = deepcopy(base)
    raw_revocation["revoked_assertion_references"] = ["raw-bearer-is-forbidden"]
    mutations.append(raw_revocation)

    for document in mutations:
        with pytest.raises(ValueError):
            HostAuthorizationPolicyCatalog.create(document)


def test_identity_scope_and_request_factories_are_strict() -> None:
    identity = verified_identity()
    assert identity.identity_version == VERIFIED_HOST_IDENTITY_VERSION
    assert identity.expires_at_utc > identity.issued_at_utc

    with pytest.raises(ValueError):
        VerifiedHostIdentity.create(
            subject_ref="raw-user@example.test",
            identity_provider_reference="identity-provider:p8-test-host",
            issuer="https://identity.test.invalid/plantnexus",
            audience="plantnexus-aps-test",
            issued_at_utc="2026-09-06T00:30:00Z",
            expires_at_utc="2026-09-06T01:30:00Z",
        )
    with pytest.raises(ValueError):
        HostPlanningScope.create(
            tenant_id="TENANT-P8-APPLICATION",
            factory_id="*",
            planning_scope_id="PLANNING-P8-APPLICATION",
        )
    with pytest.raises(ValueError):
        HostAuthorizationRequest.create(
            operation_id="unknownHeadlessOperation",
            tenant_id="TENANT-P8-APPLICATION",
            factory_id="FACTORY-001",
            planning_scope_id="PLANNING-P8-APPLICATION",
            resource_type="PLANNING_RUN",
            resource_id="planning-run-contract-001",
            correlation_id="CORRELATION-P8-HOST-AUTH",
            occurred_at_utc="2026-09-06T01:00:00Z",
        )


def test_all_five_operations_derive_only_the_registered_application_capability() -> None:
    sink = RecordingHostAuthorizationAuditSink()
    adapter = host_authorization_adapter(audit_sink=sink)

    for operation_id, capability in HEADLESS_OPERATION_CAPABILITIES.items():
        principal = adapter.authorize("Bearer p8-headless-token", _request(operation_id))
        assert principal.application_capability == capability
        assert principal.actor_reference == "actor:p8-headless-http-test"
        assert principal.subject_reference == "subject:p8-headless-http-test"
        assert principal.production_binding is False
        assert principal.requested_scope == _request(operation_id).requested_scope

    assert [record.document["operation_id"] for record in sink.records] == list(
        HEADLESS_OPERATION_CAPABILITIES
    )
    assert {record.document["outcome"] for record in sink.records} == {"ALLOWED"}
    assert {record.document["reason"] for record in sink.records} == {"AUTHORIZED"}


def test_audit_carrier_rejects_incomplete_conflicting_or_unscoped_evidence() -> None:
    sink = RecordingHostAuthorizationAuditSink()
    adapter = host_authorization_adapter(audit_sink=sink)
    adapter.authorize(
        "Bearer p8-headless-token", _request("getHeadlessPlanningRunStatus")
    )
    base = sink.records[0].document

    missing = deepcopy(base)
    del missing["assertion_reference"]
    conflict = deepcopy(base)
    conflict["reason"] = "OPERATION_DENIED"
    wildcard = deepcopy(base)
    wildcard["requested_scope"]["factory_id"] = "*"
    partial_policy = deepcopy(base)
    partial_policy["auth_policy_fingerprint"] = None

    for document in (missing, conflict, wildcard, partial_policy):
        with pytest.raises(ValueError):
            HostAuthorizationAuditRecord.create(document)
