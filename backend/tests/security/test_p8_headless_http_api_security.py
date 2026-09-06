"""Negative and authorization evidence for TEST-P8-HEADLESS-API-001."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.app import create_app
from app.data_validation.canonical_ingress import (
    canonical_json_bytes,
    request_fingerprint,
)
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from backend.tests.contract.p8_headless_http_support import (
    FailingAuthorizationProvider,
    StaticAuthorizationProvider,
    authorized_principal,
    canonical_request,
    compose_headless_api,
    create_headers,
    run_headers,
)


def _replace_request_fingerprint(document: dict[str, object]) -> None:
    document["request_fingerprint"] = request_fingerprint(document)


def _row_count(composition) -> int:
    with composition.database.engine.connect() as connection:
        return cast(
            int,
            connection.execute(text("SELECT count(*) FROM planning_runs")).scalar_one(),
        )


def test_transport_envelope_rejects_unsafe_bytes_before_side_effects(tmp_path) -> None:
    api, composition, _ = compose_headless_api(tmp_path)
    request = canonical_request()
    headers = create_headers(request)
    cases = (
        (
            {**headers, "Content-Type": "text/plain"},
            canonical_json_bytes(request),
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        ),
        (
            {**headers, "Content-Encoding": "gzip"},
            canonical_json_bytes(request),
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        ),
        ({**headers}, b'{"duplicate":1,"duplicate":2}', 400, "DUPLICATE_JSON_KEY"),
        ({**headers}, b'{"number":NaN}', 400, "NON_FINITE_NUMBER"),
        ({**headers}, b"{\xff}", 400, "MALFORMED_JSON"),
        (
            {**headers, "Content-Length": "8388609"},
            b"{}",
            413,
            "PAYLOAD_LIMIT_EXCEEDED",
        ),
    )
    with TestClient(api) as client:
        for case_headers, content, status_code, code in cases:
            response = client.post(
                "/api/v1/planning-runs", content=content, headers=case_headers
            )
            assert response.status_code == status_code
            assert response.json()["code"] == code
            assert response.headers["cache-control"] == "no-store"
        oversized = b'{"value":"' + (b"a" * 8_388_609) + b'"}'
        response = client.post(
            "/api/v1/planning-runs", content=oversized, headers=headers
        )
        assert response.status_code == 413
        assert response.json()["code"] == "PAYLOAD_LIMIT_EXCEEDED"
        missing_key_headers = dict(headers)
        missing_key_headers.pop("Idempotency-Key")
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=missing_key_headers,
        )
        assert response.status_code == 422
        assert response.json()["error_version"] == "headless-error.v1"
        assert response.json()["code"] == "CONTRACT_VIOLATION"
        unicode_correlation = deepcopy(request)
        unicode_correlation["correlation_id"] = "不可放入响应头"
        unicode_headers = create_headers(request)
        unicode_headers.pop("X-Correlation-Id")
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(unicode_correlation),
            headers=unicode_headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "CONTRACT_VIOLATION"
        assert response.headers["X-Correlation-Id"].isascii()
        assert response.json()["correlation_id"] == response.headers["X-Correlation-Id"]
        assert _row_count(composition) == 0


def test_depth_record_count_unknown_fields_and_versions_are_bounded(tmp_path) -> None:
    api, composition, _ = compose_headless_api(tmp_path)
    base = canonical_request()
    unknown = deepcopy(base)
    unknown["extension_id"] = "request-owned-extension-is-forbidden"
    _replace_request_fingerprint(unknown)
    version = deepcopy(base)
    version["canonical_ingress_request_version"] = "canonical-ingress-request.v2"
    _replace_request_fingerprint(version)
    deep = deepcopy(base)
    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(70):
        child: dict[str, object] = {}
        cursor["nested"] = child
        cursor = child
    deep["unexpected"] = nested
    records = deepcopy(base)
    payload = cast(dict[str, object], records["payload"])
    raw_records = cast(dict[str, object], payload["records"])
    raw_records["factories"] = [{} for _ in range(100_001)]
    cases = (
        (unknown, 422, "CONTRACT_VIOLATION"),
        (version, 400, "UNKNOWN_CONTRACT_VERSION"),
        (deep, 413, "PAYLOAD_LIMIT_EXCEEDED"),
        (records, 413, "PAYLOAD_LIMIT_EXCEEDED"),
    )
    with TestClient(api) as client:
        for document, status_code, code in cases:
            response = client.post(
                "/api/v1/planning-runs",
                content=canonical_json_bytes(document),
                headers=create_headers(base),
            )
            assert response.status_code == status_code
            assert response.json()["code"] == code
        assert _row_count(composition) == 0


def test_scope_authority_planning_input_and_idempotency_claims_fail_closed(
    tmp_path,
) -> None:
    api, composition, _ = compose_headless_api(tmp_path)
    base = canonical_request()
    scope = deepcopy(base)
    cast(dict[str, object], scope["requested_scope"])["tenant_id"] = "TENANT-OTHER"
    _replace_request_fingerprint(scope)
    malformed_scope = deepcopy(base)
    cast(dict[str, object], malformed_scope["requested_scope"])["tenant_id"] = (
        "x" * 257
    )
    _replace_request_fingerprint(malformed_scope)
    authority = deepcopy(base)
    authority_binding = cast(
        list[dict[str, object]],
        cast(dict[str, object], authority["source_authority"])["bindings"],
    )[0]
    authority_binding["authority_reference"] = "authority:not-configured"
    _replace_request_fingerprint(authority)
    inputs = deepcopy(base)
    planning_inputs = cast(dict[str, object], inputs["planning_inputs"])
    cast(dict[str, object], planning_inputs["planning_policy"])["artifact_id"] = (
        "POLICY-NOT-CONFIGURED"
    )
    _replace_request_fingerprint(inputs)
    with TestClient(api) as client:
        scope_response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(scope),
            headers=create_headers(scope),
        )
        assert scope_response.status_code == 403
        assert scope_response.json()["code"] == "SCOPE_MISMATCH"

        malformed_scope_response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(malformed_scope),
            headers=create_headers(malformed_scope),
        )
        assert malformed_scope_response.status_code == 422
        assert malformed_scope_response.json()["code"] == "CONTRACT_VIOLATION"

        authority_response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(authority),
            headers=create_headers(authority),
        )
        assert authority_response.status_code == 403
        assert authority_response.json()["rejection"]["code"] == "AUTHORITY_CONFLICT"
        assert authority_response.json()["side_effects"] == "NONE"

        inputs_response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(inputs),
            headers=create_headers(inputs),
        )
        assert inputs_response.status_code == 422
        assert inputs_response.json()["code"] == "INVALID_REFERENCE"

        mismatch_headers = create_headers(base)
        mismatch_headers["Idempotency-Key"] = "different-headless-key-0001"
        mismatch = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(base),
            headers=mismatch_headers,
        )
        assert mismatch.status_code == 422
        assert mismatch.json()["code"] == "CONTRACT_VIOLATION"
        assert _row_count(composition) == 0


def test_authentication_profiles_and_provider_failures_do_not_leak(tmp_path) -> None:
    request = canonical_request()
    disabled = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=False,
        ),
        probes={},
        authorization_provider=StaticAuthorizationProvider(),
    )
    with TestClient(disabled) as client:
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=create_headers(request),
        )
        assert response.status_code == 403
        assert response.json()["workspace_control_error"]["reason"] == (
            "AUTHORIZATION_DENIED"
        )

    api, _, _ = compose_headless_api(
        tmp_path, authorization_provider=FailingAuthorizationProvider()
    )
    with TestClient(api) as client:
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=create_headers(request),
        )
        assert response.status_code == 503
        assert "do-not-leak" not in response.text
        assert "secret" not in response.text.lower()

    bound_api, _, _ = compose_headless_api(
        tmp_path / "bound",
        authorization_provider=StaticAuthorizationProvider(
            authorized_principal(production_binding=True)
        ),
    )
    with TestClient(bound_api) as client:
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=create_headers(request),
        )
        assert response.status_code == 403

    clock_api, clock_composition, _ = compose_headless_api(tmp_path / "clock")
    clock_api.state.headless_clock = lambda: "not-a-utc-instant"
    with TestClient(clock_api) as client:
        response = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=create_headers(request),
        )
        assert response.status_code == 500
        assert response.json()["code"] == "SYSTEM_ERROR"
        assert _row_count(clock_composition) == 0


def test_action_unknown_fields_stale_preconditions_and_scope_are_side_effect_free(
    tmp_path,
) -> None:
    api, _, _ = compose_headless_api(tmp_path)
    request = canonical_request()
    with TestClient(api) as client:
        created = client.post(
            "/api/v1/planning-runs",
            content=canonical_json_bytes(request),
            headers=create_headers(request),
        )
        run_id = created.json()["accepted"]["planning_run"]["planning_run_id"]
        current = client.get(
            f"/api/v1/planning-runs/{run_id}/status", headers=run_headers()
        ).json()
        base_action = {
            "action_version": "planning-run-cancel-action.v1",
            "expected_revision": current["revision"],
            "expected_state": current["state"],
            "expected_run_fingerprint": current["run_fingerprint"],
            "reason": "Negative security test must not cancel.",
        }
        action_headers = {
            **run_headers(),
            "Content-Type": "application/json",
            "Idempotency-Key": "p8-security-cancel-key-0001",
        }
        unknown = {**base_action, "runtime_version": "request-owned"}
        response = client.post(
            f"/api/v1/planning-runs/{run_id}/cancel",
            content=canonical_json_bytes(unknown),
            headers=action_headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "CONTRACT_VIOLATION"

        credential_reason = {
            **base_action,
            "reason": "Authorization: Bearer must-not-enter-the-audit",
        }
        response = client.post(
            f"/api/v1/planning-runs/{run_id}/cancel",
            content=canonical_json_bytes(credential_reason),
            headers=action_headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "CONTRACT_VIOLATION"

        stale = {**base_action, "expected_revision": 999}
        response = client.post(
            f"/api/v1/planning-runs/{run_id}/cancel",
            content=canonical_json_bytes(stale),
            headers=action_headers,
        )
        assert response.status_code == 409
        assert response.json()["code"] == "INVALID_STATE_TRANSITION"

        wrong_scope = {**run_headers(), "X-APS-Tenant-Id": "TENANT-OTHER"}
        response = client.get(
            f"/api/v1/planning-runs/{run_id}/status", headers=wrong_scope
        )
        assert response.status_code == 403
        assert response.json()["code"] == "SCOPE_MISMATCH"
        malformed_headers = {**run_headers(), "X-APS-Tenant-Id": "x" * 257}
        response = client.get(
            f"/api/v1/planning-runs/{run_id}/status", headers=malformed_headers
        )
        assert response.status_code == 422
        assert response.json()["code"] == "CONTRACT_VIOLATION"
        final = client.get(
            f"/api/v1/planning-runs/{run_id}/status", headers=run_headers()
        )
        assert final.status_code == 200
        assert final.json()["state"] == "CREATED"
