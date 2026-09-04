"""Property and mutation evidence for TEST-P8-CANONICAL-INGRESS-001."""

from __future__ import annotations

from copy import deepcopy

from hypothesis import given, settings, strategies as st

from app.application.canonical_ingress import CanonicalIngressApplicationService
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    canonical_fingerprint,
    canonical_json_bytes,
    request_fingerprint,
)
from backend.tests.contract.p8_canonical_ingress_support import (
    InMemoryCanonicalIngressRepository,
    SCHEMA_DIRECTORY,
    request_document,
    trusted_context,
)


SAFE_ID = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-",
    min_size=1,
    max_size=24,
)


def _service(
    repository: InMemoryCanonicalIngressRepository,
) -> CanonicalIngressApplicationService:
    return CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=repository,
    )


@settings(max_examples=12, deadline=None)
@given(request_id=SAFE_ID, correlation_id=SAFE_ID)
def test_replay_identity_ignores_transport_ids_but_echoes_current_request(
    request_id: str, correlation_id: str
) -> None:
    original = request_document()
    replay_request = request_document(
        request_id=request_id,
        correlation_id=correlation_id,
    )
    repository = InMemoryCanonicalIngressRepository()
    service = _service(repository)

    created = service.submit(
        canonical_json_bytes(original), context=trusted_context(original)
    )
    replayed = service.submit(
        canonical_json_bytes(replay_request),
        context=trusted_context(replay_request),
    )

    assert replay_request["request_fingerprint"] == original["request_fingerprint"]
    assert replayed.result["idempotency"]["outcome"] == "REPLAYED"
    assert replayed.result["request_id"] == request_id
    assert replayed.result["correlation_id"] == correlation_id
    assert replayed.result["accepted"] == created.result["accepted"]
    assert repository.count == 1


@settings(max_examples=12, deadline=None)
@given(
    changed_artifact_id=SAFE_ID.filter(
        lambda value: value != "POLICY-P8-APPLICATION-001"
    )
)
def test_any_planning_input_mutation_under_the_same_key_conflicts(
    changed_artifact_id: str,
) -> None:
    original = request_document()
    changed = request_document(
        request_id="REQUEST-P8-MUTATION",
        correlation_id="CORRELATION-P8-MUTATION",
    )
    changed["planning_inputs"]["planning_policy"]["artifact_id"] = changed_artifact_id
    changed["request_fingerprint"] = request_fingerprint(changed)
    repository = InMemoryCanonicalIngressRepository()
    service = _service(repository)

    service.submit(canonical_json_bytes(original), context=trusted_context(original))
    outcome = service.submit(
        canonical_json_bytes(changed), context=trusted_context(changed)
    )

    assert outcome.result["rejection"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert outcome.result["side_effects"] == "NONE"
    assert repository.count == 1


@settings(max_examples=12, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_canonical_request_bytes_and_fingerprint_are_mapping_order_independent(
    seed: int,
) -> None:
    request = request_document()
    request["payload"]["synthetic_provenance"]["seed"] = seed
    request["payload_fingerprint"] = canonical_fingerprint(request["payload"])
    request["request_fingerprint"] = request_fingerprint(request)
    reversed_request = deepcopy(request)
    reversed_request = dict(reversed(list(reversed_request.items())))

    assert canonical_json_bytes(request) == canonical_json_bytes(reversed_request)
    assert request_fingerprint(request) == request_fingerprint(reversed_request)
