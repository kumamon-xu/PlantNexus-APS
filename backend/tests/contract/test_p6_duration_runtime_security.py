"""Security, tamper, privacy, and isolation tests for the P6 local runtime."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from app.duration_prediction.runtime import (
    DurationPredictionProvider,
    P6RuntimeError,
    load_duration_monitoring_policy,
    load_duration_runtime_policy,
    monitor_duration_runtime,
)
from backend.tests.p6_duration_runtime_support import (
    MODEL_ARTIFACT_PATH,
    MONITORING_POLICY_PATH,
    ROOT,
    RUNTIME_POLICY_PATH,
    build_test_provider,
    load_monitoring_policy,
    monitoring_window,
    recompute_feature_identity,
    recompute_monitoring_window_identity,
    runtime_requests,
)


@pytest.fixture(scope="module")
def provider() -> DurationPredictionProvider:
    return build_test_provider()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_recomputed_policy_tamper_is_rejected_by_exact_authorization(
    tmp_path: Path,
) -> None:
    policy = json.loads(RUNTIME_POLICY_PATH.read_text(encoding="utf-8"))
    policy["resource_policy"]["prediction_timeout_ns"] += 1
    projection = {
        key: value
        for key, value in policy.items()
        if key not in {"policy_id", "policy_fingerprint"}
    }
    raw = json.dumps(
        projection,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = sha256(raw).hexdigest()
    policy["policy_id"] = f"duration-runtime-policy-{digest}"
    policy["policy_fingerprint"] = f"sha256:{digest}"
    target = tmp_path / "tampered-policy.json"
    _write_json(target, policy)

    with pytest.raises(P6RuntimeError) as captured:
        load_duration_runtime_policy(target)

    assert captured.value.code == "RUNTIME_POLICY_IDENTITY_MISMATCH"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (
            b'{"duration_runtime_policy_version":"duration-runtime-policy.v1",'
            b'"duration_runtime_policy_version":"duration-runtime-policy.v1"}',
            "DUPLICATE_JSON_KEY",
        ),
        (b'{"value":NaN}', "NON_FINITE_JSON"),
    ],
)
def test_policy_parser_rejects_duplicate_and_non_finite_json(
    tmp_path: Path, raw: bytes, code: str
) -> None:
    target = tmp_path / "invalid-policy.json"
    target.write_bytes(raw)

    with pytest.raises(P6RuntimeError) as captured:
        load_duration_runtime_policy(target)

    assert captured.value.code == code


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"token": "sensitive-value"}, "PRIVACY_GOVERNANCE_FAILED"),
        ({"unknown_runtime_field": "x"}, "CONTRACT_VERSION_INCOMPATIBLE"),
        ({"production_binding": True}, "PRIVACY_GOVERNANCE_FAILED"),
        ({"environment": "PRODUCTION"}, "AUTHORITY_NOT_ESTABLISHED"),
    ],
)
def test_feature_security_mutations_fallback_without_reflection(
    provider: DurationPredictionProvider,
    mutation: dict[str, object],
    reason: str,
) -> None:
    request = runtime_requests()[0]
    feature = deepcopy(dict(request.feature_record))
    feature.update(mutation)
    recompute_feature_identity(feature)

    prediction = provider.predict(replace(request, feature_record=feature))
    serialized = json.dumps(prediction, sort_keys=True)

    assert prediction["fallback_reason"] == reason
    assert (
        prediction["selected_duration_seconds"] == request.standard_duration["seconds"]
    )
    assert "sensitive-value" not in serialized
    assert "token" not in serialized


def test_oversized_feature_is_bounded_before_model_call(
    provider: DurationPredictionProvider,
) -> None:
    request = runtime_requests()[0]
    feature = deepcopy(dict(request.feature_record))
    for item in feature["features"]:
        if item["feature_name"] == "operation_family":
            item["value"] = "x" * 20_000
    recompute_feature_identity(feature)

    prediction = provider.predict(replace(request, feature_record=feature))

    assert prediction["fallback_reason"] == "FEATURE_VERSION_INCOMPATIBLE"
    assert prediction["selected_duration_source"] == "STANDARD_DURATION"


def test_feature_identity_tamper_returns_sanitized_provenance_fallback(
    provider: DurationPredictionProvider,
) -> None:
    request = runtime_requests()[0]
    feature = deepcopy(dict(request.feature_record))
    feature["features"][0]["value"] += 1

    prediction = provider.predict(replace(request, feature_record=feature))

    assert prediction["fallback_reason"] == "PROVENANCE_INCOMPLETE"
    assert "planned_quantity" not in json.dumps(prediction)


def test_unexpected_provider_exception_is_sanitized_and_has_no_partial_output(
    provider: DurationPredictionProvider,
) -> None:
    def broken(*_args: object) -> None:
        raise RuntimeError("secret-token=never-reflect")

    prediction = replace(provider, candidate_predictor=broken).predict(
        runtime_requests()[0]
    )
    serialized = json.dumps(prediction, sort_keys=True)

    assert prediction["fallback_reason"] == "PROVIDER_UNAVAILABLE"
    assert prediction["p50_seconds"] is None
    assert "secret-token" not in serialized
    assert "RuntimeError" not in serialized


def test_artifact_tamper_disables_model_without_executable_loading(
    tmp_path: Path,
) -> None:
    tampered = tmp_path / "tampered.pnmodel"
    tampered.write_bytes(b"{}\n")

    provider = build_test_provider(model_artifact_path=tampered)
    prediction = provider.predict(runtime_requests()[0])

    assert provider.startup_fallback_reason == "ARTIFACT_DIGEST_MISMATCH"
    assert prediction["fallback_reason"] == "ARTIFACT_DIGEST_MISMATCH"
    assert MODEL_ARTIFACT_PATH.read_bytes() != tampered.read_bytes()


def test_invalid_standard_authority_fingerprint_fails_closed(
    provider: DurationPredictionProvider,
) -> None:
    request = runtime_requests()[0]
    invalid = replace(
        request,
        standard_duration={
            **request.standard_duration,
            "source_record_fingerprint": "not-a-digest",
        },
    )

    with pytest.raises(P6RuntimeError) as captured:
        provider.predict(invalid)

    assert captured.value.code == "INVALID_FINGERPRINT"
    assert "not-a-digest" not in captured.value.detail


def test_runtime_module_has_no_network_planning_persistence_or_cache_imports() -> None:
    path = ROOT / "backend" / "app" / "duration_prediction" / "runtime.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden_prefixes = (
        "app.api",
        "app.application",
        "app.infrastructure",
        "app.planning",
        "app.simulation",
        "httpx",
        "requests",
        "socket",
        "sqlalchemy",
    )
    assert not any(
        imported == prefix or imported.startswith(prefix + ".")
        for imported in imports
        for prefix in forbidden_prefixes
    )


def test_recomputed_monitoring_policy_tamper_is_rejected(
    tmp_path: Path,
) -> None:
    policy = json.loads(MONITORING_POLICY_PATH.read_text(encoding="utf-8"))
    policy["thresholds"]["fallback_rate_max"] = {
        "denominator": 2,
        "numerator": 1,
    }
    projection = {
        key: value
        for key, value in policy.items()
        if key not in {"policy_id", "policy_fingerprint"}
    }
    digest = sha256(
        json.dumps(
            projection,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    policy["policy_id"] = f"duration-monitoring-policy-{digest}"
    policy["policy_fingerprint"] = f"sha256:{digest}"
    target = tmp_path / "tampered-monitor-policy.json"
    _write_json(target, policy)

    with pytest.raises(P6RuntimeError) as captured:
        load_duration_monitoring_policy(target)

    assert captured.value.code == "MONITORING_POLICY_IDENTITY_MISMATCH"


def test_raw_or_identifying_telemetry_defaults_disabled_without_reflection() -> None:
    window = monitoring_window()
    window["raw_payload"] = {
        "operation_id": "secret-operation",
        "actual_processing_seconds": 123,
    }
    recompute_monitoring_window_identity(window)

    report = monitor_duration_runtime(load_monitoring_policy(), window)
    serialized = json.dumps(report, sort_keys=True)

    assert report["monitoring_decision"]["reason_codes"] == [
        "TELEMETRY_PRIVACY_VIOLATION"
    ]
    assert report["monitoring_decision"]["recommendation"] == "DEFAULT_DISABLE"
    assert "secret-operation" not in serialized
    assert "actual_processing_seconds" not in serialized
    assert report["window_reference"] is None


@pytest.mark.parametrize(
    "identifier_key",
    [
        "feature_record_id",
        "operation_id",
        "resource_id",
        "resource_option_id",
        "row_id",
        "source_record_id",
        "user_id",
    ],
)
def test_direct_identifier_keys_are_classified_as_privacy_violations(
    identifier_key: str,
) -> None:
    window = monitoring_window()
    window[identifier_key] = "must-not-reflect"
    recompute_monitoring_window_identity(window)

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == [
        "TELEMETRY_PRIVACY_VIOLATION"
    ]
    assert "must-not-reflect" not in json.dumps(report, sort_keys=True)


def test_loaded_monitoring_policy_mutation_cannot_lower_thresholds() -> None:
    policy = load_monitoring_policy()
    policy.document["thresholds"]["fallback_rate_max"] = {
        "denominator": 2,
        "numerator": 1,
    }

    with pytest.raises(P6RuntimeError) as captured:
        monitor_duration_runtime(policy, monitoring_window())

    assert captured.value.code == "MONITORING_POLICY_IDENTITY_MISMATCH"


def test_privacy_flag_tamper_defaults_disabled_even_with_fresh_identity() -> None:
    window = monitoring_window()
    window["privacy"]["raw_label_fields_present"] = True
    recompute_monitoring_window_identity(window)

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == [
        "TELEMETRY_PRIVACY_VIOLATION"
    ]
    assert report["counts"]["observation_count"] == 0


def test_unapproved_threshold_reference_defaults_disabled() -> None:
    window = monitoring_window()
    window["policy_reference"]["threshold_policy_version"] = (
        "duration-drift-thresholds.v2"
    )
    recompute_monitoring_window_identity(window)

    report = monitor_duration_runtime(load_monitoring_policy(), window)

    assert report["monitoring_decision"]["reason_codes"] == [
        "TELEMETRY_LINEAGE_INVALID"
    ]
    assert report["monitoring_decision"]["automatic_actions"] == []
    assert report["boundaries"]["production_authorized"] is False
