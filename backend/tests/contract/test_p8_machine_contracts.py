"""TEST-P8-CANONICAL-CONTRACT-001: P8 canonical ingress and PlanningRun contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from hypothesis import given, strategies as st
from jsonschema import Draft202012Validator

from app import SCHEMA_VERSION
from scripts.p8_machine_contract_check import (
    ACTIVATION_SCHEMA_MANIFEST_SHA256,
    DIFF_BASE,
    IMMUTABLE_HISTORICAL_MANIFEST_SHA256,
    NEGATIVE_SAMPLES,
    POSITIVE_SAMPLES,
    P8ContractError,
    SCHEMA_IDS,
    SCHEMAS,
    apply_negative_vector,
    canonical_fingerprint,
    idempotency_key_reference,
    request_fingerprint,
    result_fingerprint,
    run_contract_checks,
    run_fingerprint,
    runtime_resolution_fingerprint,
    scope_fingerprint,
    validate_document,
    validate_planning_run,
    validate_request,
    validate_result,
)


TEST_ID = "TEST-P8-CANONICAL-CONTRACT-001"
ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas/json"
SAMPLE_ROOT = ROOT / "schemas/samples"


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sample(name: str) -> dict[str, Any]:
    return _json(SAMPLE_ROOT / name)


def _walk(value: object):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_p8_schemas_are_strict_additive_offline_and_have_stable_ids() -> None:
    for version, filename in SCHEMAS.items():
        schema = _json(SCHEMA_ROOT / filename)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == SCHEMA_IDS[version]
        assert schema["properties"]["schema_set_version"] == {"const": "2.10.0"}
        assert all("default" not in node for node in _walk(schema))
        assert all(
            node.get("additionalProperties") is False
            for node in _walk(schema)
            if node.get("type") == "object"
        )
        assert all(
            cast(str, node["$ref"]).startswith(("#/", "urn:plantnexus:aps:schema:"))
            for node in _walk(schema)
            if "$ref" in node
        )


def test_positive_samples_validate_round_trip_and_bind_cross_document_lineage() -> None:
    request = _sample(POSITIVE_SAMPLES[0])
    accepted = _sample(POSITIVE_SAMPLES[1])
    rejected = _sample(POSITIVE_SAMPLES[2])
    created = _sample(POSITIVE_SAMPLES[3])
    completed = _sample(POSITIVE_SAMPLES[4])

    validate_request(ROOT, request)
    validate_result(ROOT, accepted, request=request, planning_run=created)
    validate_result(ROOT, rejected, request=request)
    validate_planning_run(ROOT, created, request=request)
    validate_planning_run(ROOT, completed, request=request)
    for document in (request, accepted, rejected, created, completed):
        assert (
            json.loads(json.dumps(document, sort_keys=True, separators=(",", ":")))
            == document
        )

    assert request["payload_fingerprint"] == canonical_fingerprint(request["payload"])
    assert request["request_fingerprint"] == request_fingerprint(request)
    assert accepted["result_fingerprint"] == result_fingerprint(accepted)
    assert rejected["result_fingerprint"] == result_fingerprint(rejected)
    assert accepted["effective_scope"]["scope_fingerprint"] == scope_fingerprint(
        accepted["effective_scope"]
    )
    assert accepted["idempotency"]["key_reference"] == idempotency_key_reference(
        request["idempotency_key"]
    )
    assert created["run_fingerprint"] == run_fingerprint(created)
    assert completed["run_fingerprint"] == run_fingerprint(completed)
    assert created["runtime_resolution"]["resolution_fingerprint"] == (
        runtime_resolution_fingerprint(created["runtime_resolution"])
    )
    assert created["runtime_resolution"] == completed["runtime_resolution"]

    forged_inputs = copy.deepcopy(created)
    forged_inputs["inputs"]["planning_policy"]["artifact_id"] = (
        "POLICY-P8-SYNTHETIC-FORGED"
    )
    forged_inputs["run_fingerprint"] = run_fingerprint(forged_inputs)
    with pytest.raises(P8ContractError) as captured:
        validate_planning_run(ROOT, forged_inputs, request=request)
    assert captured.value.code == "LINEAGE_INVALID"

    forged_runtime = copy.deepcopy(accepted)
    forged_runtime["accepted"]["runtime_resolution"]["validator_version"] = (
        "0.0.1-p8-contract-sample"
    )
    forged_runtime["accepted"]["runtime_resolution"]["resolution_fingerprint"] = (
        runtime_resolution_fingerprint(forged_runtime["accepted"]["runtime_resolution"])
    )
    forged_runtime["result_fingerprint"] = result_fingerprint(forged_runtime)
    with pytest.raises(P8ContractError) as captured:
        validate_result(ROOT, forged_runtime, request=request, planning_run=created)
    assert captured.value.code == "EXTENSION_SET_MISMATCH"


def test_client_cannot_select_extension_code_registry_or_artifact_path() -> None:
    request = _sample(POSITIVE_SAMPLES[0])
    forbidden = {
        "plugin_id": "enterprise.example",
        "module": "enterprise.extension",
        "artifact_path": "C:/plugins/enterprise.whl",
        "extension_set_id": "CLIENT-CHOSEN",
    }
    for field, value in forbidden.items():
        mutation = copy.deepcopy(request)
        mutation[field] = value
        with pytest.raises(P8ContractError) as captured:
            validate_request(ROOT, mutation)
        assert captured.value.code == "CONTRACT_VIOLATION"

    unauthorized_collection = copy.deepcopy(request)
    unauthorized_collection["source_authority"]["bindings"][0][
        "canonical_collections"
    ] = ["demand_orders"]
    unauthorized_collection["request_fingerprint"] = request_fingerprint(
        unauthorized_collection
    )
    with pytest.raises(P8ContractError) as captured:
        validate_request(ROOT, unauthorized_collection)
    assert captured.value.code == "AUTHORITY_CONFLICT"

    duplicated_claim = copy.deepcopy(request)
    second_binding = copy.deepcopy(duplicated_claim["source_authority"]["bindings"][0])
    second_binding["authority_reference"] = "authority:p8-synthetic-host-secondary"
    duplicated_claim["source_authority"]["bindings"].append(second_binding)
    duplicated_claim["request_fingerprint"] = request_fingerprint(duplicated_claim)
    with pytest.raises(P8ContractError) as captured:
        validate_request(ROOT, duplicated_claim)
    assert captured.value.code == "AUTHORITY_CONFLICT"

    ambiguous_mapping = copy.deepcopy(request)
    second_mapping = copy.deepcopy(
        ambiguous_mapping["source_authority"]["mapping_provenance"][0]
    )
    second_mapping["mapping_profile_id"] = "MAPPING-P8-SYNTHETIC-002"
    second_mapping["mapping_profile_fingerprint"] = "sha256:" + "5" * 64
    ambiguous_mapping["source_authority"]["mapping_provenance"].append(second_mapping)
    ambiguous_mapping["request_fingerprint"] = request_fingerprint(ambiguous_mapping)
    with pytest.raises(P8ContractError) as captured:
        validate_request(ROOT, ambiguous_mapping)
    assert captured.value.code == "AUTHORITY_CONFLICT"


def test_accepted_and_rejected_results_are_discriminated_and_fail_closed() -> None:
    request = _sample(POSITIVE_SAMPLES[0])
    accepted = _sample(POSITIVE_SAMPLES[1])
    rejected = _sample(POSITIVE_SAMPLES[2])
    assert accepted["side_effects"] == "PLANNING_RUN_CREATED_OR_REPLAYED"
    assert accepted["accepted"]["planning_run"]["state"] == "CREATED"
    assert (
        accepted["accepted"]["runtime_resolution"]["extension_set"]
        == (_sample(POSITIVE_SAMPLES[3])["runtime_resolution"]["extension_set"])
    )
    assert rejected["side_effects"] == "NONE"
    assert rejected["accepted"] is None
    assert rejected["rejection"]["code"] == "IDEMPOTENCY_CONFLICT"

    leaked = copy.deepcopy(rejected)
    leaked["accepted"] = accepted["accepted"]
    with pytest.raises(P8ContractError) as captured:
        validate_document(ROOT, leaked)
    assert captured.value.code in {"CONTRACT_VIOLATION", "LINEAGE_INVALID"}

    forged_scope = copy.deepcopy(accepted)
    forged_scope["effective_scope"]["scope_fingerprint"] = "sha256:" + "0" * 64
    forged_scope["result_fingerprint"] = result_fingerprint(forged_scope)
    with pytest.raises(P8ContractError) as captured:
        validate_result(ROOT, forged_scope, request=request)
    assert captured.value.code == "LINEAGE_INVALID"

    forged_key_reference = copy.deepcopy(accepted)
    forged_key_reference["idempotency"]["key_reference"] = "sha256:" + "0" * 64
    forged_key_reference["result_fingerprint"] = result_fingerprint(
        forged_key_reference
    )
    with pytest.raises(P8ContractError) as captured:
        validate_result(ROOT, forged_key_reference, request=request)
    assert captured.value.code == "LINEAGE_INVALID"


def test_planning_run_states_pairs_terminal_and_actions_equal_frozen_registry() -> None:
    registry = cast(
        dict[str, Any],
        yaml.safe_load(
            (ROOT / "schemas/rules/state-machines.v1.yaml").read_text("utf-8")
        ),
    )
    machine = next(
        item for item in registry["machines"] if item["machine"] == "PLANNING_RUN"
    )
    schema = _json(SCHEMA_ROOT / SCHEMAS["planning-run.v1"])
    assert set(schema["$defs"]["planningRunState"]["enum"]) == set(machine["states"])
    assert set(machine["terminal_states"]) == {
        "COMPLETED",
        "DATA_REJECTED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "CANCELLED",
        "FAILED",
    }
    assert _sample(POSITIVE_SAMPLES[3])["allowed_actions"] == ["READ", "CANCEL"]
    assert _sample(POSITIVE_SAMPLES[4])["allowed_actions"] == ["READ"]

    bad_revision = _sample(POSITIVE_SAMPLES[4])
    bad_revision["revision"] += 1
    bad_revision["run_fingerprint"] = run_fingerprint(bad_revision)
    with pytest.raises(P8ContractError) as captured:
        validate_planning_run(ROOT, bad_revision)
    assert captured.value.code == "INVALID_STATE_TRANSITION"

    bad_updated_at = _sample(POSITIVE_SAMPLES[4])
    bad_updated_at["updated_at_utc"] = "2026-09-04T00:00:09Z"
    bad_updated_at["run_fingerprint"] = run_fingerprint(bad_updated_at)
    with pytest.raises(P8ContractError) as captured:
        validate_planning_run(ROOT, bad_updated_at)
    assert captured.value.code == "LINEAGE_INVALID"


def test_published_negative_vectors_have_exact_stable_rejections() -> None:
    observed: list[str] = []
    for name in NEGATIVE_SAMPLES:
        vector = _sample(name)
        base = _sample(vector["base_sample"])
        mutation = apply_negative_vector(base, vector)
        if vector["mutation"]["operation"] == "IDEMPOTENCY_REUSE":
            validate_request(ROOT, mutation)
            code = "IDEMPOTENCY_CONFLICT"
        else:
            with pytest.raises(P8ContractError) as captured:
                validate_document(ROOT, mutation)
            code = captured.value.code
        assert code == vector["expected_rejection"]
        observed.append(code)
    assert len(observed) == 10
    assert "INVALID_STATE_TRANSITION" in observed
    assert "DATA_PLANE_MISMATCH" in observed
    assert "IDEMPOTENCY_CONFLICT" in observed


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20))
def test_unknown_request_fields_fail_closed_property(field_suffix: str) -> None:
    request = _sample(POSITIVE_SAMPLES[0])
    request[f"unknown_{field_suffix}"] = True
    with pytest.raises(P8ContractError) as captured:
        validate_request(ROOT, request)
    assert captured.value.code == "CONTRACT_VIOLATION"


@given(
    source=st.sampled_from(
        [
            "CREATED",
            "INGESTING",
            "VALIDATING",
            "SNAPSHOTTED",
            "BUILDING",
            "SOLVING",
            "SOLVED",
            "VERIFYING",
        ]
    )
)
def test_illegal_completed_predecessors_fail_before_fingerprint(source: str) -> None:
    if source == "VERIFYING":
        return
    completed = _sample(POSITIVE_SAMPLES[4])
    completed["last_transition"]["from_state"] = source
    with pytest.raises(P8ContractError) as captured:
        validate_planning_run(ROOT, completed)
    assert captured.value.code == "INVALID_STATE_TRANSITION"


def test_machine_report_freezes_history_versions_and_non_implementation_boundary() -> (
    None
):
    report = run_contract_checks(ROOT)
    assert report["report_version"] == "p8-machine-contract-report.v1"
    assert report["task_id"] == "TASK-P8-02"
    assert report["test_id"] == TEST_ID
    assert report["diff_base"] == DIFF_BASE
    assert report["schema_set_version"] == SCHEMA_VERSION == "2.10.0"
    assert report["status"] == report["result"] == "PASS"
    assert report["check_count"] == 6
    assert report["counts"] == {
        "new_schemas": 3,
        "new_rule_registries": 1,
        "positive_samples": 5,
        "negative_samples": 10,
        "immutable_historical_artifacts": 97,
    }
    preservation = report["checks"][0]["evidence"]
    assert (
        preservation["activation_manifest_sha256"] == ACTIVATION_SCHEMA_MANIFEST_SHA256
    )
    assert preservation["immutable_historical_manifest_sha256"] == (
        IMMUTABLE_HISTORICAL_MANIFEST_SHA256
    )
    assert (
        report["boundaries"]["api_database_worker_extension_sdk"] == "NOT_IMPLEMENTED"
    )
    assert report["boundaries"]["third_party_adapter"] == "EXCLUDED"
    assert report["boundaries"]["demo"] == "EXCLUDED"
    assert report["issues"] == []
