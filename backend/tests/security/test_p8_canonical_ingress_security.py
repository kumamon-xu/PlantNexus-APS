"""Security and isolation evidence for TEST-P8-CANONICAL-INGRESS-001."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from app.application.canonical_ingress import CanonicalIngressApplicationService
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    CanonicalIngressContractCode,
    CanonicalIngressContractError,
    canonical_json_bytes,
    idempotency_key_reference,
    request_fingerprint,
)
from backend.tests.contract.p8_canonical_ingress_support import (
    InMemoryCanonicalIngressRepository,
    SCHEMA_DIRECTORY,
    request_document,
    trusted_context,
)


def _service(
    repository: InMemoryCanonicalIngressRepository,
) -> CanonicalIngressApplicationService:
    return CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=repository,
    )


def test_raw_idempotency_secret_never_reaches_result_record_audit_or_observability() -> (
    None
):
    secret = "P8-SUPER-SECRET-IDEMPOTENCY-0001"
    request = request_document(idempotency_key=secret)
    context = trusted_context(request)
    repository = InMemoryCanonicalIngressRepository()
    outcome = _service(repository).submit(
        canonical_json_bytes(request), context=context
    )
    record = repository.get_by_idempotency(
        scope_fingerprint=context.idempotency_scope_fingerprint(),
        key_reference=idempotency_key_reference(secret),
    )

    assert record is not None
    for evidence in (
        outcome.canonical_result_bytes,
        outcome.planning_run_bytes,
        record.canonical_bytes,
        canonical_json_bytes(outcome.observability),
    ):
        assert evidence is not None
        assert secret.encode() not in evidence
    assert b'"idempotency_key"' not in record.canonical_bytes


@pytest.mark.parametrize(
    ("pointer", "field"),
    [
        ("root", "plugin_id"),
        ("root", "entry_point"),
        ("root", "artifact_path"),
        ("payload", "extension_set_id"),
        ("payload", "module"),
    ],
)
def test_client_code_extension_and_path_selectors_are_rejected_before_persistence(
    pointer: str, field: str
) -> None:
    request = request_document()
    target = request if pointer == "root" else request["payload"]
    target[field] = "../../client-controlled-code.py"
    request["request_fingerprint"] = request_fingerprint(request)
    repository = InMemoryCanonicalIngressRepository()

    with pytest.raises(CanonicalIngressContractError) as caught:
        _service(repository).submit(
            canonical_json_bytes(request), context=trusted_context(request)
        )

    assert caught.value.code is CanonicalIngressContractCode.CONTRACT_VIOLATION
    assert repository.count == 0
    assert "client-controlled-code" not in str(caught.value)


def test_runtime_scope_cannot_be_widened_by_request_fields() -> None:
    request = request_document()
    repository = InMemoryCanonicalIngressRepository()
    context = replace(
        trusted_context(request),
        tenant_id="TENANT-OTHER",
        factory_id="FACTORY-OTHER",
        planning_scope_id="PLANNING-OTHER",
        data_plane="PRODUCTION",
        environment="PRODUCTION",
        production_binding=True,
    )

    outcome = _service(repository).submit(
        canonical_json_bytes(request), context=context
    )

    assert outcome.result["disposition"] == "REJECTED"
    assert outcome.result["rejection"]["code"] == "DATA_PLANE_MISMATCH"
    assert outcome.result["effective_scope"] is None
    assert repository.count == 0


def test_production_is_mechanically_available_only_with_trusted_binding() -> None:
    request = request_document(data_plane="PRODUCTION", environment="PRODUCTION")
    repository = InMemoryCanonicalIngressRepository()
    denied = _service(repository).submit(
        canonical_json_bytes(request),
        context=trusted_context(request, production_binding=False),
    )
    accepted = _service(repository).submit(
        canonical_json_bytes(request),
        context=trusted_context(request, production_binding=True),
    )

    assert denied.result["rejection"]["code"] == "DATA_PLANE_MISMATCH"
    assert accepted.result["disposition"] == "ACCEPTED"
    assert accepted.result["effective_scope"]["data_plane"] == "PRODUCTION"
    assert accepted.snapshot is not None
    assert accepted.snapshot.data_plane.value == "production"
    assert repository.count == 1


def test_sanitized_authority_rejection_does_not_echo_untrusted_reference() -> None:
    request = request_document()
    untrusted = "authority:TOP-SECRET-CUSTOMER-SYSTEM"
    request["source_authority"]["bindings"][0]["authority_reference"] = untrusted
    request["request_fingerprint"] = request_fingerprint(request)
    repository = InMemoryCanonicalIngressRepository()
    outcome = _service(repository).submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )

    serialized = canonical_json_bytes(cast(dict[str, Any], outcome.result))
    assert outcome.result["rejection"]["code"] == "AUTHORITY_CONFLICT"
    assert untrusted.encode() not in serialized
    assert repository.count == 0
