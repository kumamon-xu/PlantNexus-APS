"""Frozen P8 machine-contract parity for the durable ingress application."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.application.canonical_ingress import CanonicalIngressApplicationService
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    CanonicalIngressContractError,
    canonical_fingerprint,
    canonical_json_bytes,
    idempotency_key_reference,
    request_fingerprint,
)
from app.snapshots import import_package_id_for
from backend.tests.contract.p8_canonical_ingress_support import (
    InMemoryCanonicalIngressRepository,
    ROOT,
    SCHEMA_DIRECTORY,
    request_document,
    trusted_context,
)
from scripts.p8_machine_contract_check import (
    P8ContractError,
    apply_negative_vector,
    validate_planning_run,
    validate_request,
    validate_result,
)
from scripts.p6_duration_contract_check import run_contract_checks as run_p6_contract_checks


FROZEN_SCHEMA_HASHES = {
    "canonical-ingress-request.schema.json": (
        "bbd895cd742eb38e5ad534e1a4cdcc73d88ea95a6384d49d32eba3997cd182f9"
    ),
    "canonical-ingress-result.schema.json": (
        "047c440e6b1ceba7d52d2150b43ccc4a8f60cae50e13469628f3d45a8a294506"
    ),
    "planning-run.schema.json": (
        "3d5f4d21ccf3bf227a42530e59c4b4df456353a77801901bb9c5e695f206861a"
    ),
}


def _registry() -> Registry:
    registry = Registry()
    for path in sorted(SCHEMA_DIRECTORY.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and isinstance(document.get("$id"), str):
            registry = registry.with_resource(
                cast(str, document["$id"]), Resource.from_contents(document)
            )
    return registry


def _validate_official(schema_name: str, document: object) -> None:
    schema = json.loads((SCHEMA_DIRECTORY / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        schema, registry=_registry(), format_checker=FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(cast(Any, document)),
        key=lambda item: list(item.path),
    )
    assert errors == []


def _create_bundle() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    InMemoryCanonicalIngressRepository,
]:
    request = request_document()
    repository = InMemoryCanonicalIngressRepository()
    service = CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=repository,
    )
    outcome = service.submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )
    context = trusted_context(request)
    record = repository.get_by_idempotency(
        scope_fingerprint=context.idempotency_scope_fingerprint(),
        key_reference=idempotency_key_reference(request["idempotency_key"]),
    )
    assert record is not None
    record_document = record.document
    return (
        request,
        outcome.result,
        cast(dict[str, Any], outcome.planning_run),
        cast(dict[str, Any], record_document["audit_event"]),
        repository,
    )


def test_generated_bundle_passes_frozen_and_independent_contract_validators() -> None:
    request, result, planning_run, audit, _repository = _create_bundle()

    validate_request(ROOT, request)
    validate_planning_run(ROOT, planning_run, request=request)
    validate_result(ROOT, result, request=request, planning_run=planning_run)
    _validate_official("canonical-ingress-request.schema.json", request)
    _validate_official("canonical-ingress-result.schema.json", result)
    _validate_official("planning-run.schema.json", planning_run)
    _validate_official("audit-event.schema.json", audit)

    assert planning_run["state"] == "CREATED"
    assert planning_run["revision"] == 1
    assert all(value is None for value in planning_run["artifacts"].values())
    assert (
        result["accepted"]["runtime_resolution"] == planning_run["runtime_resolution"]
    )


def test_generated_replay_is_a_valid_result_with_exact_resource_references() -> None:
    request, created, planning_run, _audit, repository = _create_bundle()
    service = CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=repository,
    )
    replay = service.submit(
        canonical_json_bytes(request), context=trusted_context(request)
    ).result

    validate_result(ROOT, replay, request=request, planning_run=planning_run)
    _validate_official("canonical-ingress-result.schema.json", replay)
    assert replay["idempotency"]["outcome"] == "REPLAYED"
    assert replay["accepted"] == created["accepted"]
    assert replay["result_fingerprint"] != created["result_fingerprint"]


def test_production_consumer_matches_all_frozen_negative_vector_codes() -> None:
    contract = CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY)
    for path in sorted(
        (ROOT / "schemas" / "samples").glob("canonical-ingress.v1.invalid-*.json")
    ):
        vector = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        base = cast(
            dict[str, Any],
            json.loads(
                (ROOT / "schemas" / "samples" / vector["base_sample"]).read_text(
                    encoding="utf-8"
                )
            ),
        )
        mutated = apply_negative_vector(base, vector)
        if vector["mutation"]["operation"] == "IDEMPOTENCY_REUSE":
            assert vector["expected_rejection"] == "IDEMPOTENCY_CONFLICT"
            continue
        try:
            contract.validate_request(mutated)
        except CanonicalIngressContractError as error:
            observed = error.code.value
        else:
            observed = "UNEXPECTED_PASS"
        assert observed == vector["expected_rejection"], path.name
        try:
            validate_request(ROOT, mutated)
        except P8ContractError as error:
            assert error.code == observed
        else:
            raise AssertionError(f"reference checker accepted {path.name}")


def test_request_required_field_and_client_code_mutations_fail_closed() -> None:
    contract = CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY)
    base = request_document()
    for field in sorted(base):
        mutated = deepcopy(base)
        del mutated[field]
        if field != "request_fingerprint":
            mutated["request_fingerprint"] = request_fingerprint(mutated)
        try:
            contract.validate_request(mutated)
        except CanonicalIngressContractError:
            pass
        else:
            raise AssertionError(f"missing required field passed: {field}")

    for forbidden in ("plugin_id", "entry_point", "artifact_path", "module"):
        mutated = deepcopy(base)
        mutated[forbidden] = "client-owned-value"
        mutated["request_fingerprint"] = request_fingerprint(mutated)
        try:
            contract.validate_request(mutated)
        except CanonicalIngressContractError as error:
            assert error.code.value == "CONTRACT_VIOLATION"
        else:
            raise AssertionError(f"client code selector passed: {forbidden}")


def test_schema_integer_lexeme_reaches_data_validation_instead_of_contract_rejection() -> (
    None
):
    request = request_document()
    payload = cast(dict[str, Any], request["payload"])
    provenance = cast(dict[str, Any], payload["synthetic_provenance"])
    provenance["seed"] = float(provenance["seed"])
    payload["package_id"] = import_package_id_for(payload)
    request["payload_fingerprint"] = canonical_fingerprint(payload)
    request["request_fingerprint"] = request_fingerprint(request)

    _validate_official("canonical-ingress-request.schema.json", request)
    contract = CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY)
    contract.validate_request(request)

    repository = InMemoryCanonicalIngressRepository()
    result = CanonicalIngressApplicationService(
        contract=contract,
        repository=repository,
    ).submit(canonical_json_bytes(request), context=trusted_context(request))

    assert result.result["disposition"] == "REJECTED"
    assert result.result["rejection"]["code"] == "DATA_VALIDATION_FAILED"
    assert repository.count == 0


def test_p8_schema_bytes_remain_at_the_activated_hashes() -> None:
    observed = {
        name: sha256((SCHEMA_DIRECTORY / name).read_bytes()).hexdigest()
        for name in FROZEN_SCHEMA_HASHES
    }
    assert observed == FROZEN_SCHEMA_HASHES


def test_additive_p8_migration_preserves_the_frozen_p6_migration_prefix() -> None:
    report = run_p6_contract_checks(ROOT)
    repository = cast(dict[str, Any], report["boundaries"])["repository"]

    assert repository["migration_count"] == 5
    assert repository["migration_head"] == "0005_replan_event_persistence"
    assert (
        ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "0006_canonical_ingress_application.py"
    ).is_file()
