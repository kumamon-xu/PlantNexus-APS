"""TEST-P8-CANONICAL-INGRESS-001 application and strict-parser evidence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest

from app.application.canonical_ingress import (
    CanonicalIngressApplicationService,
    CanonicalIngressBuildPlan,
    CanonicalIngressPersistenceCode,
    CanonicalIngressPersistenceError,
    CanonicalIngressRecord,
)
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    CanonicalIngressContractCode,
    CanonicalIngressContractError,
    canonical_fingerprint,
    canonical_json_bytes,
    request_fingerprint,
)
from app.snapshots import import_package_id_for
from backend.tests.contract.p8_canonical_ingress_support import (
    InMemoryCanonicalIngressRepository,
    SCHEMA_DIRECTORY,
    request_document,
    runtime_resolution,
    trusted_context,
)


@pytest.fixture
def contract() -> CanonicalIngressContract:
    return CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY)


def _service(
    contract: CanonicalIngressContract,
    repository: object | None = None,
) -> CanonicalIngressApplicationService:
    return CanonicalIngressApplicationService(
        contract=contract,
        repository=cast(object, repository or InMemoryCanonicalIngressRepository()),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"a":1,"a":2}', CanonicalIngressContractCode.DUPLICATE_JSON_KEY),
        (b'{"a":NaN}', CanonicalIngressContractCode.NON_FINITE_NUMBER),
        (b'{"a":Infinity}', CanonicalIngressContractCode.NON_FINITE_NUMBER),
        (b"\xff", CanonicalIngressContractCode.MALFORMED_JSON),
        (b"[]", CanonicalIngressContractCode.CONTRACT_VIOLATION),
    ],
)
def test_strict_parser_rejects_ambiguous_or_non_json_input(
    contract: CanonicalIngressContract,
    raw: bytes,
    code: CanonicalIngressContractCode,
) -> None:
    with pytest.raises(CanonicalIngressContractError) as caught:
        contract.parse_request(raw)
    assert caught.value.code is code
    assert "NaN" not in str(caught.value)
    assert "Infinity" not in str(caught.value)


def test_create_and_exact_replay_keep_one_resource_set(
    contract: CanonicalIngressContract,
) -> None:
    request = request_document()
    repository = InMemoryCanonicalIngressRepository()
    service = _service(contract, repository)

    created = service.submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )
    replayed = service.submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )

    assert created.result["disposition"] == "ACCEPTED"
    assert created.result["idempotency"]["outcome"] == "CREATED"
    assert replayed.result["idempotency"]["outcome"] == "REPLAYED"
    assert replayed.replayed is True
    assert repository.count == 1
    assert created.snapshot == replayed.snapshot
    assert created.problem == replayed.problem
    assert created.planning_run == replayed.planning_run
    assert (
        created.result["accepted"]["planning_run"]
        == replayed.result["accepted"]["planning_run"]
    )
    assert created.quality_report_bytes == replayed.quality_report_bytes
    assert "idempotency_key" not in str(created.observability)


def test_same_key_and_scope_with_changed_request_is_conflict(
    contract: CanonicalIngressContract,
) -> None:
    first = request_document()
    changed = request_document(
        request_id="REQUEST-P8-APPLICATION-002",
        correlation_id="CORRELATION-P8-APPLICATION-002",
    )
    changed["planning_inputs"]["planning_policy"]["artifact_id"] = (
        "POLICY-P8-APPLICATION-CHANGED"
    )
    changed["request_fingerprint"] = request_fingerprint(changed)
    repository = InMemoryCanonicalIngressRepository()
    service = _service(contract, repository)

    service.submit(canonical_json_bytes(first), context=trusted_context(first))
    conflict = service.submit(
        canonical_json_bytes(changed), context=trusted_context(changed)
    )

    assert conflict.result["disposition"] == "REJECTED"
    assert conflict.result["idempotency"]["outcome"] == "CONFLICT"
    assert conflict.result["rejection"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert repository.count == 1


@pytest.mark.parametrize(
    ("context_change", "expected_code"),
    [
        ({"tenant_id": "TENANT-NOT-AUTHORIZED"}, "SCOPE_MISMATCH"),
        (
            {"authorized_authority_references": ("authority:not-authorized",)},
            "AUTHORITY_CONFLICT",
        ),
    ],
)
def test_scope_and_authority_are_server_owned_zero_effect_rejections(
    contract: CanonicalIngressContract,
    context_change: dict[str, object],
    expected_code: str,
) -> None:
    request = request_document()
    repository = InMemoryCanonicalIngressRepository()
    context = replace(trusted_context(request), **context_change)

    outcome = _service(contract, repository).submit(
        canonical_json_bytes(request), context=context
    )

    assert outcome.result["rejection"]["code"] == expected_code
    assert outcome.result["side_effects"] == "NONE"
    assert repository.count == 0


def test_production_requires_an_explicit_runtime_binding(
    contract: CanonicalIngressContract,
) -> None:
    request = request_document(data_plane="PRODUCTION", environment="PRODUCTION")
    repository = InMemoryCanonicalIngressRepository()

    outcome = _service(contract, repository).submit(
        canonical_json_bytes(request),
        context=trusted_context(request, production_binding=False),
    )

    assert outcome.result["rejection"]["code"] == "DATA_PLANE_MISMATCH"
    assert repository.count == 0


def test_runtime_and_planning_references_fail_closed(
    contract: CanonicalIngressContract,
) -> None:
    request = request_document()
    invalid_runtime = runtime_resolution()
    invalid_runtime["resolution_fingerprint"] = f"sha256:{'0' * 64}"
    context = trusted_context(request)
    invalid_context = replace(
        context, runtime_resolution_bytes=canonical_json_bytes(invalid_runtime)
    )
    runtime_outcome = _service(contract).submit(
        canonical_json_bytes(request), context=invalid_context
    )

    other_inputs = {
        **request["planning_inputs"],
        "planning_policy": {
            **request["planning_inputs"]["planning_policy"],
            "artifact_id": "POLICY-NOT-REQUESTED",
        },
    }
    wrong_plan = CanonicalIngressBuildPlan.create(
        planning_inputs=other_inputs,
        cutoff_at_utc="2026-08-20T00:00:00Z",
        tick_seconds=60,
        horizon_start_utc="2026-08-20T00:00:00Z",
        horizon_end_utc="2026-08-21T00:00:00Z",
        priority_facts={},
    )
    reference_outcome = _service(contract).submit(
        canonical_json_bytes(request), context=replace(context, build_plan=wrong_plan)
    )

    assert runtime_outcome.result["rejection"]["code"] == ("RUNTIME_RESOLUTION_FAILED")
    assert reference_outcome.result["rejection"]["code"] == "INVALID_REFERENCE"


def test_data_validation_and_problem_build_failures_are_distinct(
    contract: CanonicalIngressContract,
) -> None:
    invalid_data = request_document()
    duplicate = deepcopy(invalid_data["payload"]["records"]["resources"][0])
    duplicate["resource_code"] = "R001-DUPLICATE-ID"
    duplicate["source"]["source_record_id"] = "SRC-RESOURCE-DUPLICATE-ID"
    invalid_data["payload"]["records"]["resources"].append(duplicate)
    invalid_data["payload"]["package_id"] = import_package_id_for(
        invalid_data["payload"]
    )
    invalid_data["payload_fingerprint"] = canonical_fingerprint(invalid_data["payload"])
    invalid_data["request_fingerprint"] = request_fingerprint(invalid_data)
    repository = InMemoryCanonicalIngressRepository()
    data_outcome = _service(contract, repository).submit(
        canonical_json_bytes(invalid_data), context=trusted_context(invalid_data)
    )

    valid = request_document()
    empty_priority_plan = CanonicalIngressBuildPlan.create(
        planning_inputs=valid["planning_inputs"],
        cutoff_at_utc="2026-08-20T00:00:00Z",
        tick_seconds=60,
        horizon_start_utc="2026-08-20T00:00:00Z",
        horizon_end_utc="2026-08-21T00:00:00Z",
        priority_facts={},
    )
    model_outcome = _service(contract).submit(
        canonical_json_bytes(valid),
        context=replace(trusted_context(valid), build_plan=empty_priority_plan),
    )

    assert data_outcome.result["rejection"]["code"] == "DATA_VALIDATION_FAILED"
    assert data_outcome.quality_report_bytes is not None
    assert model_outcome.result["rejection"]["code"] == "MODEL_INVALID"
    assert repository.count == 0


class _FailingRepository:
    def __init__(self, *, fail_lookup: bool) -> None:
        self.fail_lookup = fail_lookup

    def get_by_idempotency(
        self, *, scope_fingerprint: str, key_reference: str
    ) -> CanonicalIngressRecord | None:
        del scope_fingerprint, key_reference
        if self.fail_lookup:
            raise CanonicalIngressPersistenceError(
                CanonicalIngressPersistenceCode.PERSISTENCE_FAILED,
                field="lookup",
                message="sanitized failure",
            )
        return None

    def commit(self, record: CanonicalIngressRecord) -> object:
        del record
        raise CanonicalIngressPersistenceError(
            CanonicalIngressPersistenceCode.PERSISTENCE_FAILED,
            field="commit",
            message="sanitized failure",
        )


@pytest.mark.parametrize("fail_lookup", [True, False])
def test_persistence_failures_return_retryable_system_result(
    contract: CanonicalIngressContract, fail_lookup: bool
) -> None:
    request = request_document()
    outcome = _service(contract, _FailingRepository(fail_lookup=fail_lookup)).submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )

    assert outcome.result["rejection"]["code"] == "SYSTEM_ERROR"
    assert outcome.result["rejection"]["retryability"] == "RETRY_SAME_REQUEST"
    assert outcome.result["side_effects"] == "NONE"


def test_build_plan_bytes_are_self_verifying() -> None:
    request = request_document()
    plan = trusted_context(request).build_plan
    damaged = CanonicalIngressBuildPlan(
        canonical_bytes=plan.canonical_bytes.replace(
            b'"tick_seconds":60', b'"tick_seconds":61'
        )
    )
    with pytest.raises(ValueError, match="fingerprint"):
        damaged.verify()
