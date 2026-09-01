"""TEST-P6-PREDICTION-CONTRACT-001: P6 duration carrier contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given, strategies as st
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from scripts.p6_duration_contract_check import (
    FALLBACK_REASONS,
    HISTORICAL_MANIFEST_SHA256,
    NEGATIVE_SAMPLES,
    POSITIVE_SAMPLES,
    P6ContractError,
    SCHEMA_IDS,
    SCHEMAS,
    apply_negative_vector,
    contract_fingerprint,
    load_positive_samples,
    recompute_identity,
    run_contract_checks,
    validate_document,
    validate_p6_bundle,
)

TEST_ID = "TEST-P6-PREDICTION-CONTRACT-001"
TEST_CONTRACT_ID = "TEST-CONTRACT-001"
ROOT = Path(__file__).resolve().parents[3]


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((ROOT / "schemas" / "json" / name).read_text(encoding="utf-8")),
    )


def _negative(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((ROOT / "schemas" / "samples" / name).read_text(encoding="utf-8")),
    )


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(name), format_checker=FormatChecker())


def _walk(value: object):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_p6_schemas_are_strict_offline_additive_and_samples_round_trip() -> None:
    documents = load_positive_samples(ROOT)
    assert len(SCHEMAS) == 4
    assert len(documents) == 5
    for kind, filename in SCHEMAS.items():
        schema = _schema(filename)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == SCHEMA_IDS[kind]
        assert all("default" not in node for node in _walk(schema))
        assert all(
            node.get("additionalProperties") is False
            for node in _walk(schema)
            if node.get("type") == "object"
        )
        assert all(
            cast(str, node["$ref"]).startswith("#/")
            for node in _walk(schema)
            if "$ref" in node
        )
    for document in documents.values():
        validate_document(ROOT, document)
        assert json.loads(
            json.dumps(document, sort_keys=True, separators=(",", ":"))
        ) == document
    assert TEST_CONTRACT_ID == "TEST-CONTRACT-001"


def test_canonical_fingerprints_and_cross_document_lineage_are_exact() -> None:
    documents = load_positive_samples(ROOT)
    validate_p6_bundle(ROOT, documents)
    for document in documents.values():
        assert contract_fingerprint(document) in document.values()

    prediction = deepcopy(documents[POSITIVE_SAMPLES[3]])
    prediction["feature_record_reference"]["feature_record_fingerprint"] = (
        "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    )
    documents[POSITIVE_SAMPLES[3]] = recompute_identity(prediction)
    with pytest.raises(P6ContractError, match="LINEAGE_MISMATCH"):
        validate_p6_bundle(ROOT, documents)


def test_candidate_is_advisory_and_fallback_selects_authoritative_standard() -> None:
    documents = load_positive_samples(ROOT)
    candidate = documents[POSITIVE_SAMPLES[3]]
    fallback = documents[POSITIVE_SAMPLES[4]]
    assert candidate["fallback_reason"] == "NONE"
    assert candidate["selected_duration_source"] == "MODEL_CANDIDATE"
    assert candidate["selected_duration_seconds"] == candidate["p50_seconds"]
    assert fallback["fallback_reason"] == "PROVIDER_TIMEOUT"
    assert fallback["selected_duration_source"] == "STANDARD_DURATION"
    assert fallback["selected_duration_seconds"] == fallback["standard_duration"]["seconds"]
    for prediction in (candidate, fallback):
        assert prediction["governance_boundary"]["planning_authority"] == (
            "ADVISORY_DURATION_ONLY"
        )
        assert prediction["production_binding"] is False


def test_published_negative_vectors_fail_with_exact_stable_codes() -> None:
    documents = load_positive_samples(ROOT)
    observed: set[str] = set()
    for name in NEGATIVE_SAMPLES:
        vector = _negative(name)
        mutated = apply_negative_vector(documents[vector["base_sample"]], vector)
        with pytest.raises(P6ContractError) as captured:
            validate_document(ROOT, mutated)
        assert captured.value.code == vector["expected_rejection"]
        observed.add(captured.value.code)
    assert observed == {
        "AS_OF_LEAKAGE",
        "MISSING_DATASET_LINEAGE",
        "INVALID_QUANTILE_ORDER",
        "INCOMPATIBLE_SCHEMA_SET",
        "UNKNOWN_FALLBACK_REASON",
    }


@given(
    p50=st.integers(min_value=1, max_value=1_000_000),
    spread=st.integers(min_value=0, max_value=1_000_000),
    confidence=st.floats(
        min_value=0,
        max_value=1,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_ordered_quantile_and_confidence_property(
    p50: int, spread: int, confidence: float
) -> None:
    prediction = load_positive_samples(ROOT)[POSITIVE_SAMPLES[3]]
    prediction["p50_seconds"] = p50
    prediction["p90_seconds"] = p50 + spread
    prediction["confidence"] = confidence
    prediction["selected_duration_seconds"] = p50
    validate_document(ROOT, recompute_identity(prediction))


@given(
    lower=st.integers(min_value=1, max_value=999_999),
    gap=st.integers(min_value=1, max_value=999_999),
)
def test_reversed_quantile_property_fails_closed(lower: int, gap: int) -> None:
    prediction = load_positive_samples(ROOT)[POSITIVE_SAMPLES[3]]
    prediction["p50_seconds"] = lower + gap
    prediction["p90_seconds"] = lower
    prediction["selected_duration_seconds"] = lower + gap
    with pytest.raises(P6ContractError, match="INVALID_QUANTILE_ORDER"):
        validate_document(ROOT, recompute_identity(prediction))


@pytest.mark.parametrize("reason", FALLBACK_REASONS[1:])
def test_every_registered_fallback_reason_selects_exact_standard_duration(
    reason: str,
) -> None:
    prediction = load_positive_samples(ROOT)[POSITIVE_SAMPLES[4]]
    prediction["fallback_reason"] = reason
    validate_document(ROOT, recompute_identity(prediction))


def test_unknown_fallback_confidence_unit_and_production_are_schema_rejected() -> None:
    prediction = load_positive_samples(ROOT)[POSITIVE_SAMPLES[3]]
    validator = _validator(SCHEMAS["prediction"])
    for field, value in (
        ("fallback_reason", "UNKNOWN"),
        ("confidence", 1.1),
        ("unit", "MINUTES"),
        ("data_plane", "PRODUCTION"),
        ("schema_set_version", "2.8.0"),
    ):
        mutation = deepcopy(prediction)
        mutation[field] = value
        with pytest.raises(ValidationError):
            validator.validate(mutation)


def test_model_and_evaluation_carriers_create_no_lifecycle_or_gate_decision() -> None:
    documents = load_positive_samples(ROOT)
    model = documents[POSITIVE_SAMPLES[1]]
    evaluation = documents[POSITIVE_SAMPLES[2]]
    forbidden = {"state", "promotion_status", "deployment_status", "runtime_endpoint"}
    assert all(not forbidden.intersection(node) for node in _walk(model))
    assert evaluation["gate_assessment"] == {
        "gate_contract": "duration-evaluation-gate.planned-p6-05",
        "decision": "NOT_EVALUATED_BY_P6_02",
        "thresholds_embedded": False,
    }


def test_machine_report_freezes_history_dependencies_and_boundaries() -> None:
    report = run_contract_checks(ROOT)
    assert report["report_version"] == "p6-duration-contract-report.v1"
    assert report["task_id"] == "TASK-P6-02"
    assert report["diff_base"] == "e74099ca24ed59140f6490c84025b7299b5f201d"
    assert report["schema_set_version"] == "2.9.0"
    assert report["status"] == report["result"] == "PASS"
    assert report["check_count"] == 10
    assert report["counts"] == {
        "new_schemas": 4,
        "positive_samples": 5,
        "negative_samples": 5,
        "frozen_historical_artifacts": 70,
        "schema_rejections": 20,
        "semantic_rejections": 7,
        "tamper_rejections": 5,
    }
    assert report["checks"][0]["evidence"]["manifest_sha256"] == (
        HISTORICAL_MANIFEST_SHA256
    )
    assert report["boundaries"]["dataset_training_runtime_planning_integration"] == (
        "NOT_IMPLEMENTED"
    )
    assert report["boundaries"]["standard_duration_authority"] == "UNCHANGED"
    assert report["issues"] == []
    assert TEST_ID == "TEST-P6-PREDICTION-CONTRACT-001"
