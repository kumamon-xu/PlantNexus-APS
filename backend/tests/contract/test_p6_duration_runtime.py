from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from app.duration_prediction.runtime import (
    REGISTERED_FALLBACK_REASONS,
    DurationCandidate,
    DurationPredictionProvider,
    DurationProviderSignal,
    P6RuntimeError,
    load_duration_monitoring_policy,
    load_duration_runtime_policy,
    monitor_duration_runtime,
    validate_duration_prediction,
)
from backend.tests.p6_duration_runtime_support import (
    MODEL_ARTIFACT_PATH,
    MONITORING_POLICY_PATH,
    PREDICTION_SCHEMA_PATH,
    RUNTIME_POLICY_PATH,
    build_test_provider,
    load_json,
    load_monitoring_policy,
    monitoring_window,
    runtime_inputs,
    runtime_requests,
    sequence_clock,
)
from scripts.p6_duration_evaluation_check import main as evaluation_check_main
from scripts.p6_duration_runtime_check import (
    main as runtime_check_main,
    run_runtime_checks,
)


@pytest.fixture(scope="module")
def provider() -> DurationPredictionProvider:
    return build_test_provider()


def _schema_errors(prediction: dict[str, Any]) -> list[Any]:
    schema = load_json(PREDICTION_SCHEMA_PATH)
    return sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            prediction
        ),
        key=lambda error: list(error.absolute_path),
    )


def test_runtime_policy_is_exact_content_addressed_simulation_authority() -> None:
    policy = load_duration_runtime_policy(RUNTIME_POLICY_PATH)

    assert policy.document["policy_version"] == "SIM-P6-DURATION-RUNTIME-001@1.0.0"
    assert policy.document["runtime_environment"] == {
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "explicit_invocation_only": True,
        "in_process_only": True,
        "runtime_enabled": True,
    }
    assert policy.document["model_authorization"]["decision"] == (
        "SIMULATION_TEST_RUNTIME_ONLY"
    )
    assert policy.document["evaluation_gate"]["decision"] == (
        "READY_FOR_SIMULATION_RUNTIME"
    )
    assert policy.confidence_threshold == Fraction(9, 10)
    assert policy.prediction_timeout_ns == 50_000_000
    assert policy.document["governance_boundary"]["production_authorized"] is False


def test_exact_model_prediction_forms_valid_p6_02_carrier(
    provider: DurationPredictionProvider,
) -> None:
    request = runtime_requests()[0]
    original_feature = deepcopy(request.feature_record)
    original_standard = deepcopy(request.standard_duration)

    prediction = provider.predict(request)

    assert _schema_errors(prediction) == []
    validate_duration_prediction(prediction, provider.policy)
    assert prediction["fallback_reason"] == "NONE"
    assert prediction["selected_duration_source"] == "MODEL_CANDIDATE"
    assert prediction["selected_duration_seconds"] == prediction["p50_seconds"]
    assert prediction["p90_seconds"] >= prediction["p50_seconds"]
    assert prediction["confidence"] >= 0.9
    assert prediction["standard_duration"] == original_standard
    assert request.standard_duration == original_standard
    assert request.feature_record == original_feature
    assert prediction["model_reference"] == {
        "duration_model_manifest_version": "duration-model-manifest.v1",
        "model_manifest_id": (
            "duration-model-manifest-"
            "35f84b792028a1bf135fcc44d415423d47593f2843058d119fe288efd7195bf0"
        ),
        "model_manifest_fingerprint": (
            "sha256:35f84b792028a1bf135fcc44d415423d47593f2843058d119fe288efd7195bf0"
        ),
        "model_version": "1.0.0",
        "model_artifact_digest": (
            "sha256:472cc92ada06b488fceb8477ac5a3dfe06d6391dd5ada8b441d55b96e9640ddd"
        ),
    }
    assert prediction["evaluation_reference"]["evaluation_report_fingerprint"] == (
        "sha256:4c86069865003263c15e3a7e6d18a83b943a10a087d81ed34cdd3f353dfd799f"
    )
    assert prediction["prediction_policy_reference"] == {
        "document_version": "duration-runtime-policy.v1",
        "artifact_id": (
            "duration-runtime-policy-"
            "6acf154fe7ed2ed5b4b28060fd033896ad3ad1b66436c9edadeefe6245faebc7"
        ),
        "fingerprint": (
            "sha256:6acf154fe7ed2ed5b4b28060fd033896ad3ad1b66436c9edadeefe6245faebc7"
        ),
    }


@pytest.mark.parametrize("reason", REGISTERED_FALLBACK_REASONS)
def test_every_registered_runtime_reason_forms_exact_standard_fallback(
    provider: DurationPredictionProvider, reason: str
) -> None:
    request = runtime_requests()[0]

    def signal_candidate(*_args: object) -> None:
        raise DurationProviderSignal(reason)

    fallback_provider = replace(provider, candidate_predictor=signal_candidate)
    prediction = fallback_provider.predict(request)

    assert _schema_errors(prediction) == []
    assert prediction["fallback_reason"] == reason
    assert prediction["p50_seconds"] is None
    assert prediction["p90_seconds"] is None
    assert prediction["confidence"] is None
    assert prediction["selected_duration_source"] == "STANDARD_DURATION"
    assert (
        prediction["selected_duration_seconds"] == request.standard_duration["seconds"]
    )
    assert prediction["standard_duration"] == request.standard_duration


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (None, "PREDICTION_MISSING"),
        (DurationCandidate(10, 9), "INVALID_QUANTILES"),
        (
            DurationCandidate(100, 110, confidence=None, derive_confidence=False),
            "CONFIDENCE_MISSING",
        ),
        (
            DurationCandidate(100, 110, confidence=1.1, derive_confidence=False),
            "CONFIDENCE_INVALID",
        ),
        (
            DurationCandidate(
                100, 111, confidence=Fraction(89, 100), derive_confidence=False
            ),
            "LOW_CONFIDENCE",
        ),
    ],
)
def test_candidate_boundaries_use_stable_fallback_reason(
    provider: DurationPredictionProvider,
    candidate: DurationCandidate | None,
    reason: str,
) -> None:
    fallback_provider = replace(
        provider,
        candidate_predictor=lambda *_args: candidate,
    )

    prediction = fallback_provider.predict(runtime_requests()[0])

    assert prediction["fallback_reason"] == reason
    assert (
        prediction["selected_duration_seconds"]
        == prediction["standard_duration"]["seconds"]
    )


def test_confidence_exactly_at_threshold_selects_candidate(
    provider: DurationPredictionProvider,
) -> None:
    threshold_provider = replace(
        provider,
        candidate_predictor=lambda *_args: DurationCandidate(100, 110),
    )

    prediction = threshold_provider.predict(runtime_requests()[0])

    assert prediction["fallback_reason"] == "NONE"
    assert prediction["confidence"] == 0.9
    assert prediction["selected_duration_seconds"] == 100


def test_timeout_is_checked_without_partial_candidate(
    provider: DurationPredictionProvider,
) -> None:
    timeout_provider = replace(
        provider,
        monotonic_clock=sequence_clock([1, 50_000_002]),
    )

    prediction = timeout_provider.predict(runtime_requests()[0])

    assert prediction["fallback_reason"] == "PROVIDER_TIMEOUT"
    assert prediction["p50_seconds"] is None
    assert prediction["selected_duration_source"] == "STANDARD_DURATION"


def test_missing_artifact_disables_provider_and_preserves_fallback(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.pnmodel"
    unavailable = build_test_provider(model_artifact_path=missing)

    prediction = unavailable.predict(runtime_requests()[0])

    assert unavailable.startup_fallback_reason == "PROVIDER_UNAVAILABLE"
    assert prediction["fallback_reason"] == "PROVIDER_UNAVAILABLE"
    assert (
        prediction["selected_duration_seconds"]
        == prediction["standard_duration"]["seconds"]
    )


def test_not_ready_gate_disables_candidate_before_model_use() -> None:
    _, _, _, gate = runtime_inputs()
    gate["gate_decision"]["decision"] = "NOT_READY"
    gate["gate_decision"]["blocking_gaps"] = ["heldout-confidence-threshold"]
    disabled = build_test_provider(gate_report=gate)

    prediction = disabled.predict(runtime_requests()[0])

    assert disabled.startup_fallback_reason == "EVALUATION_GATE_NOT_PASSED"
    assert prediction["fallback_reason"] == "EVALUATION_GATE_NOT_PASSED"


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    [
        (("model_manifest", "model_version"), "2.0.0", "MODEL_VERSION_INCOMPATIBLE"),
        (
            ("model_manifest", "model_artifact", "artifact_digest"),
            "sha256:" + "0" * 64,
            "ARTIFACT_DIGEST_MISMATCH",
        ),
    ],
)
def test_model_identity_mismatch_disables_candidate(
    path: tuple[str, ...], value: object, reason: str
) -> None:
    _, model_bundle, _, _ = runtime_inputs()
    target: dict[str, Any] = model_bundle
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    disabled = build_test_provider(model_bundle=model_bundle)
    prediction = disabled.predict(runtime_requests()[0])

    assert disabled.startup_fallback_reason == reason
    assert prediction["fallback_reason"] == reason


def test_invalid_standard_duration_authority_fails_closed_without_carrier(
    provider: DurationPredictionProvider,
) -> None:
    request = runtime_requests()[0]
    invalid = replace(
        request,
        standard_duration={**request.standard_duration, "seconds": 0},
    )

    with pytest.raises(P6RuntimeError) as captured:
        provider.predict(invalid)

    assert captured.value.code == "INVALID_INTEGER"
    assert "0" not in captured.value.detail


def test_model_artifact_bytes_are_never_modified(
    provider: DurationPredictionProvider,
) -> None:
    before = MODEL_ARTIFACT_PATH.read_bytes()

    provider.predict(runtime_requests()[0])

    assert MODEL_ARTIFACT_PATH.read_bytes() == before


def test_machine_reporter_consumes_exact_p6_05_report_and_writes_safe_artifact(
    tmp_path: Path,
) -> None:
    offline_report = tmp_path / "offline.json"
    runtime_report = tmp_path / "runtime.json"
    assert (
        evaluation_check_main(
            [
                "--root",
                str(RUNTIME_POLICY_PATH.parents[3]),
                "--report",
                str(offline_report),
            ]
        )
        == 0
    )

    exit_code = runtime_check_main(
        [
            "--root",
            str(RUNTIME_POLICY_PATH.parents[3]),
            "--offline-gate-report",
            str(offline_report),
            "--report",
            str(runtime_report),
        ]
    )
    report = load_json(runtime_report)

    assert exit_code == 0
    assert report["result"] == "PASS"
    assert len(report["checks"]) == 12
    assert report["counts"] == {
        "candidate_carriers": 8,
        "feature_records": 8,
        "label_semantic_reads": 0,
        "registered_fallback_reasons": 19,
        "same_input_replays": 8,
        "schema_rejections": 0,
        "standard_authority_mutations": 0,
    }
    assert report["issues"] == []
    serialized = runtime_report.read_text(encoding="utf-8")
    for forbidden in (
        "actual_processing_seconds",
        '"feature_record"',
        '"label"',
        '"rows"',
        '"source_record_id"',
    ):
        assert forbidden not in serialized


def test_machine_reporter_fails_closed_on_non_p6_05_input(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid-offline.json"
    invalid.write_text(
        '{"schema_version":"wrong","task_id":"TASK-P6-05",'
        '"result":"PASS","issues":[]}\n',
        encoding="utf-8",
    )
    report = tmp_path / "runtime.json"

    exit_code = runtime_check_main(
        [
            "--root",
            str(RUNTIME_POLICY_PATH.parents[3]),
            "--offline-gate-report",
            str(invalid),
            "--report",
            str(report),
        ]
    )

    assert exit_code == 1
    assert load_json(report)["issues"] == ["OFFLINE_GATE_REPORT_REJECTED"]


def test_run_runtime_checks_is_replayable_from_same_offline_report(
    tmp_path: Path,
) -> None:
    offline_report = tmp_path / "offline.json"
    evaluation_check_main(
        ["--root", str(RUNTIME_POLICY_PATH.parents[3]), "--report", str(offline_report)]
    )

    first = run_runtime_checks(RUNTIME_POLICY_PATH.parents[3], offline_report)
    second = run_runtime_checks(RUNTIME_POLICY_PATH.parents[3], offline_report)

    assert first["result"] == second["result"] == "PASS"
    assert first["identities"] == second["identities"]
    assert first["fallback_summary"] == second["fallback_summary"]
    assert first["boundaries"] == second["boundaries"]


def test_monitoring_policy_is_exact_aggregate_only_authority() -> None:
    policy = load_duration_monitoring_policy(MONITORING_POLICY_PATH)

    assert policy.document["policy_version"] == ("SIM-P6-DURATION-MONITORING-001@1.0.0")
    assert policy.fallback_rate_max == Fraction(1, 4)
    assert policy.feature_total_variation_max == Fraction(1, 4)
    assert policy.quality_pass_ratio_min == Fraction(3, 4)
    assert policy.expected_observation_count == 8
    assert policy.late_observation_max_count == 0
    assert policy.document["privacy_retention"] == {
        "direct_identifiers_allowed": False,
        "persistence": "NONE",
        "provider_artifact": "AGGREGATE_REPORT_ONLY",
        "raw_feature_fields_allowed": False,
        "raw_label_fields_allowed": False,
        "retained_window_count": 1,
        "retention_policy_version": "run-scoped-aggregate-retention.v1",
        "source_record_references_allowed": False,
        "telemetry_granularity": "AGGREGATE_WINDOW_ONLY",
    }


def test_healthy_aggregate_window_has_no_disable_recommendation() -> None:
    report = monitor_duration_runtime(load_monitoring_policy(), monitoring_window())

    assert report["schema_version"] == "p6-duration-monitoring-report.v1"
    assert report["result"] == "PASS"
    assert report["monitoring_decision"] == {
        "automatic_actions": [],
        "external_side_effects": [],
        "human_review_required": False,
        "reason_codes": [],
        "recommendation": "NO_DISABLE_RECOMMENDATION",
        "runtime_fallback_reason": None,
        "standard_duration_fallback_required": False,
    }
    assert report["metrics"] == {
        "fallback_rate": {"denominator": 8, "numerator": 1},
        "feature_total_variation": {"denominator": 1, "numerator": 0},
        "quality_pass_ratio": {"denominator": 8, "numerator": 7},
    }


def test_exact_monitoring_threshold_boundaries_are_inclusive() -> None:
    boundary = monitoring_window(
        candidate_count=6,
        fallback_count=2,
        fallback_reason_counts={"LOW_CONFIDENCE": 2},
        feature_bucket_counts={"HIGH": 4, "LOW": 2, "MID_HIGH": 1, "MID_LOW": 1},
        quality_pass_count=6,
    )

    report = monitor_duration_runtime(load_monitoring_policy(), boundary)

    assert report["metrics"] == {
        "fallback_rate": {"denominator": 4, "numerator": 1},
        "feature_total_variation": {"denominator": 4, "numerator": 1},
        "quality_pass_ratio": {"denominator": 4, "numerator": 3},
    }
    assert report["monitoring_decision"]["reason_codes"] == []


@pytest.mark.parametrize(
    ("window_kwargs", "reason"),
    [
        (
            {
                "candidate_count": 5,
                "fallback_count": 3,
                "fallback_reason_counts": {"PROVIDER_TIMEOUT": 3},
            },
            "FALLBACK_RATE_BREACH",
        ),
        (
            {
                "feature_bucket_counts": {
                    "HIGH": 4,
                    "LOW": 4,
                    "MID_HIGH": 0,
                    "MID_LOW": 0,
                }
            },
            "FEATURE_DISTRIBUTION_DRIFT",
        ),
        ({"quality_pass_count": 5}, "QUALITY_DRIFT"),
        (
            {"model_version_counts": {"1.0.0": 7, "2.0.0": 1}},
            "MODEL_VERSION_DRIFT",
        ),
        (
            {
                "feature_schema_version_counts": {
                    "duration-features.v1": 7,
                    "duration-features.v2": 1,
                }
            },
            "FEATURE_VERSION_DRIFT",
        ),
        ({"late_observation_count": 1}, "LATE_TELEMETRY"),
    ],
)
def test_each_drift_signal_recommends_default_disable(
    window_kwargs: dict[str, Any], reason: str
) -> None:
    report = monitor_duration_runtime(
        load_monitoring_policy(), monitoring_window(**window_kwargs)
    )

    assert reason in report["monitoring_decision"]["reason_codes"]
    assert report["monitoring_decision"]["recommendation"] == "DEFAULT_DISABLE"
    assert report["monitoring_decision"]["runtime_fallback_reason"] == (
        "DRIFT_GATE_DISABLED"
    )
    assert report["monitoring_decision"]["automatic_actions"] == []


def test_short_monitoring_window_has_stable_insufficient_and_count_reasons() -> None:
    report = monitor_duration_runtime(
        load_monitoring_policy(),
        monitoring_window(
            observation_count=7,
            candidate_count=6,
            fallback_count=1,
            fallback_reason_counts={"LOW_CONFIDENCE": 1},
            model_version_counts={"1.0.0": 7},
            feature_schema_version_counts={"duration-features.v1": 7},
            feature_bucket_counts={"HIGH": 2, "LOW": 2, "MID_HIGH": 2, "MID_LOW": 1},
            quality_evaluated_count=7,
            quality_pass_count=7,
        ),
    )

    assert report["monitoring_decision"]["reason_codes"] == [
        "INSUFFICIENT_TELEMETRY",
        "WINDOW_COUNT_MISMATCH",
    ]
    assert report["monitoring_decision"]["recommendation"] == "DEFAULT_DISABLE"


def test_monitoring_report_is_byte_replayable_and_aggregate_only() -> None:
    policy = load_monitoring_policy()
    window = monitoring_window()

    first = monitor_duration_runtime(policy, window)
    second = monitor_duration_runtime(policy, window)

    assert first == second
    assert first["report_fingerprint"] == second["report_fingerprint"]
    serialized = str(first)
    for forbidden in (
        "actual_processing_seconds",
        "feature_record_id",
        "operation_id",
        "resource_option_id",
        "source_record_id",
    ):
        assert forbidden not in serialized
