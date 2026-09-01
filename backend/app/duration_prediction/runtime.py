"""Fail-closed P6 duration runtime and aggregate monitoring.

The provider consumes one exact Simulation/Test model and the independently
accepted P6-05 offline Gate.  It returns the immutable P6-02 prediction
carrier, never mutates standard duration, and has no Planning, persistence,
network, cache, promotion, or Production authority.  The P6-08 monitor accepts
only one explicit aggregate window and can recommend default-disable without
executing an action or retaining telemetry.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import time
from typing import Any, Never, cast

from app.duration_prediction.evaluation import (
    LoadedEvaluationProfile,
    P6EvaluationError,
    interval_tightness_confidence,
    validate_offline_gate_report,
)
from app.duration_prediction.model import (
    LoadedDurationModel,
    P6ModelError,
    load_duration_model,
    predict_duration,
)


type JsonObject = dict[str, Any]
type CandidatePredictor = Callable[
    [LoadedDurationModel, Mapping[str, Any]], "DurationCandidate | None"
]
type MonotonicClock = Callable[[], int]

RUNTIME_POLICY_VERSION = "duration-runtime-policy.v1"
RUNTIME_POLICY_IDENTITY = "SIM-P6-DURATION-RUNTIME-001@1.0.0"
EXPECTED_POLICY_FINGERPRINT = (
    "sha256:6acf154fe7ed2ed5b4b28060fd033896ad3ad1b66436c9edadeefe6245faebc7"
)
EXPECTED_POLICY_ID = (
    "duration-runtime-policy-"
    "6acf154fe7ed2ed5b4b28060fd033896ad3ad1b66436c9edadeefe6245faebc7"
)
PREDICTION_VERSION = "duration-prediction.v1"
FEATURE_RECORD_VERSION = "duration-feature-record.v1"
MODEL_MANIFEST_VERSION = "duration-model-manifest.v1"
EVALUATION_REPORT_VERSION = "duration-evaluation-report.v1"
SCHEMA_SET_VERSION = "2.9.0"
CANONICALIZATION_VERSION = "canonical-json.v1"
FEATURE_SCHEMA_VERSION = "duration-features.v1"
MODEL_VERSION = "1.0.0"
DATA_PLANE = "SIMULATION"
ENVIRONMENT = "TEST"
MAX_POLICY_BYTES = 65_536
MAX_MONITORING_POLICY_BYTES = 65_536
OPEN_AUTHORITY_GAPS = ("OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015")
MONITORING_POLICY_VERSION = "duration-monitoring-policy.v1"
MONITORING_POLICY_IDENTITY = "SIM-P6-DURATION-MONITORING-001@1.0.0"
EXPECTED_MONITORING_POLICY_FINGERPRINT = (
    "sha256:83df8f3f9ea8574f919734f2593b287cd80524e7bc3197795da07d1f90bfdf7b"
)
EXPECTED_MONITORING_POLICY_ID = (
    "duration-monitoring-policy-"
    "83df8f3f9ea8574f919734f2593b287cd80524e7bc3197795da07d1f90bfdf7b"
)
MONITORING_WINDOW_VERSION = "duration-monitoring-window.v1"
MONITORING_REPORT_VERSION = "p6-duration-monitoring-report.v1"
MONITORING_THRESHOLD_VERSION = "duration-drift-thresholds.v1"
MONITORING_FEATURE_PROFILE_VERSION = "duration-feature-aggregate-profile.v1"
MONITORING_QUALITY_POLICY_VERSION = "duration-quality-aggregate.v1"
MONITORING_FEATURE_BUCKETS = ("HIGH", "LOW", "MID_HIGH", "MID_LOW")
MONITORING_REASON_CODES = (
    "TELEMETRY_PRIVACY_VIOLATION",
    "TELEMETRY_TAMPERED",
    "TELEMETRY_LINEAGE_INVALID",
    "TELEMETRY_WINDOW_INVALID",
    "INSUFFICIENT_TELEMETRY",
    "WINDOW_COUNT_MISMATCH",
    "LATE_TELEMETRY",
    "MODEL_VERSION_DRIFT",
    "FEATURE_VERSION_DRIFT",
    "FALLBACK_RATE_BREACH",
    "FEATURE_DISTRIBUTION_DRIFT",
    "QUALITY_EVIDENCE_INCOMPLETE",
    "QUALITY_DRIFT",
)
EXPECTED_FEATURE_NAMES = (
    "operation_family",
    "planned_quantity",
    "setup_seconds",
    "standard_duration_seconds",
)
REGISTERED_FALLBACK_REASONS = (
    "PREDICTION_MISSING",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_TIMEOUT",
    "INVALID_QUANTILES",
    "CONFIDENCE_MISSING",
    "CONFIDENCE_INVALID",
    "LOW_CONFIDENCE",
    "MODEL_NOT_APPROVED",
    "MODEL_OUT_OF_SCOPE",
    "MODEL_VERSION_INCOMPATIBLE",
    "FEATURE_VERSION_INCOMPATIBLE",
    "DATASET_VERSION_INCOMPATIBLE",
    "CONTRACT_VERSION_INCOMPATIBLE",
    "ARTIFACT_DIGEST_MISMATCH",
    "PROVENANCE_INCOMPLETE",
    "EVALUATION_GATE_NOT_PASSED",
    "DRIFT_GATE_DISABLED",
    "AUTHORITY_NOT_ESTABLISHED",
    "PRIVACY_GOVERNANCE_FAILED",
)
_STANDARD_DURATION_KEYS = {
    "seconds",
    "duration_source",
    "source_version",
    "source_record_id",
    "source_record_fingerprint",
}
_FEATURE_ROOT_KEYS = {
    "as_of_cutoff_utc",
    "canonicalization_version",
    "data_plane",
    "duration_feature_record_version",
    "environment",
    "factory_id",
    "feature_record_fingerprint",
    "feature_record_id",
    "feature_schema_version",
    "features",
    "governance_boundary",
    "operation_id",
    "pii_fields_present",
    "production_binding",
    "resource_id",
    "resource_option_id",
    "schema_set_version",
    "source_records",
    "synthetic",
    "synthetic_provenance",
    "target_fields_present",
}
_SOURCE_RECORD_KEYS = {
    "available_at_utc",
    "observed_at_utc",
    "record_fingerprint",
    "source_record_id",
    "source_system",
    "source_version",
}
_FEATURE_KEYS = {
    "available_at_utc",
    "feature_name",
    "source_record_ids",
    "transform_version",
    "unit",
    "value",
    "value_type",
}
_PREDICTION_KEYS = {
    "duration_prediction_version",
    "schema_set_version",
    "canonicalization_version",
    "prediction_id",
    "data_plane",
    "environment",
    "factory_id",
    "operation_id",
    "resource_option_id",
    "resource_id",
    "predicted_at_utc",
    "as_of_cutoff_utc",
    "unit",
    "p50_seconds",
    "p90_seconds",
    "confidence",
    "model_version",
    "feature_schema_version",
    "fallback_reason",
    "selected_duration_source",
    "selected_duration_seconds",
    "standard_duration",
    "feature_record_reference",
    "model_reference",
    "evaluation_reference",
    "prediction_policy_reference",
    "synthetic",
    "synthetic_provenance",
    "production_binding",
    "governance_boundary",
    "prediction_fingerprint",
}
_SENSITIVE_KEYS = {
    "actual_processing_seconds",
    "credential",
    "credentials",
    "email",
    "free_text",
    "label",
    "password",
    "phone",
    "raw_payload",
    "secret",
    "token",
}
_MONITORING_DIRECT_IDENTIFIER_KEYS = {
    "actor_id",
    "correlation_id",
    "customer_id",
    "employee_id",
    "factory_id",
    "feature_record_id",
    "label_id",
    "operation_id",
    "person_id",
    "prediction_id",
    "record_id",
    "request_id",
    "resource_id",
    "resource_option_id",
    "row_id",
    "run_id",
    "source_record_id",
    "source_record_ids",
    "user_id",
}


class P6RuntimeError(ValueError):
    """Stable, sanitized failure when no trustworthy carrier can be formed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class DurationProviderSignal(RuntimeError):
    """Sanitized provider outcome used by an in-process candidate adapter."""

    def __init__(self, fallback_reason: str) -> None:
        self.fallback_reason = fallback_reason
        super().__init__(fallback_reason)


def _fail(code: str, detail: str) -> Never:
    raise P6RuntimeError(code, detail)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        _fail("INVALID_JSON_VALUE", "runtime payload")


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(_canonical_json_bytes(value)).hexdigest()}"


def _reject_constant(value: str) -> Never:
    _fail("NON_FINITE_JSON", value)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _expect_object(value: object, path: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail("INVALID_OBJECT", path)
    return cast(JsonObject, value)


def _expect_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        _fail("OBJECT_SHAPE_MISMATCH", path)


def _expect_int(value: object, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("INVALID_INTEGER", path)
    return value


def _expect_identifier(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in value
        )
    ):
        _fail("INVALID_IDENTIFIER", path)
    return value


def _expect_fingerprint(value: object, path: str) -> str:
    fingerprint = _expect_identifier(value, path)
    if (
        len(fingerprint) != 71
        or not fingerprint.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in fingerprint[7:])
    ):
        _fail("INVALID_FINGERPRINT", path)
    return fingerprint


def _utc_instant(value: object, path: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        _fail("INVALID_UTC_INSTANT", path)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _fail("INVALID_UTC_INSTANT", path)
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        _fail("INVALID_UTC_INSTANT", path)
    return value, parsed


def _with_identity(value: Mapping[str, Any]) -> JsonObject:
    projection = deepcopy(dict(value))
    fingerprint = _fingerprint(projection)
    result = deepcopy(projection)
    result["prediction_id"] = "duration-prediction-" + fingerprint.removeprefix(
        "sha256:"
    )
    result["prediction_fingerprint"] = fingerprint
    return result


@dataclass(frozen=True)
class LoadedRuntimePolicy:
    """Exact, content-addressed Simulation/Test runtime authorization."""

    document: JsonObject
    fingerprint: str
    confidence_threshold: Fraction
    prediction_timeout_ns: int
    max_feature_record_bytes: int
    max_prediction_bytes: int
    max_features: int
    max_source_records: int
    benchmark_warmup_calls: int
    benchmark_measured_calls: int
    max_p95_latency_ns: int
    max_peak_allocated_bytes: int


@dataclass(frozen=True)
class DurationCandidate:
    """Sanitized result from the in-process model adapter."""

    p50_seconds: object
    p90_seconds: object
    confidence: object | None = None
    derive_confidence: bool = True


@dataclass(frozen=True)
class DurationPredictionRequest:
    """Caller-owned authority and immutable feature snapshot for one option."""

    factory_id: str
    operation_id: str
    resource_option_id: str
    resource_id: str
    predicted_at_utc: str
    as_of_cutoff_utc: str
    standard_duration: Mapping[str, Any]
    feature_record: Mapping[str, Any]


def _validate_runtime_policy(document: Mapping[str, Any]) -> LoadedRuntimePolicy:
    candidate = deepcopy(dict(document))
    _expect_keys(
        candidate,
        {
            "canonicalization_version",
            "confidence_policy",
            "contract",
            "determinism",
            "drift_policy",
            "duration_runtime_policy_version",
            "evaluation_gate",
            "evidence_profile",
            "fallback_policy",
            "governance_boundary",
            "model_authorization",
            "policy_fingerprint",
            "policy_id",
            "policy_version",
            "resource_policy",
            "runtime_environment",
            "standard_duration_policy",
            "synthetic",
            "synthetic_provenance",
            "task_id",
        },
        "runtime-policy",
    )
    projection = deepcopy(candidate)
    identifier = projection.pop("policy_id")
    fingerprint = projection.pop("policy_fingerprint")
    expected_fingerprint = _fingerprint(projection)
    if (
        fingerprint != expected_fingerprint
        or fingerprint != EXPECTED_POLICY_FINGERPRINT
        or identifier != EXPECTED_POLICY_ID
    ):
        _fail("RUNTIME_POLICY_IDENTITY_MISMATCH", "runtime-policy")
    if (
        candidate["duration_runtime_policy_version"] != RUNTIME_POLICY_VERSION
        or candidate["policy_version"] != RUNTIME_POLICY_IDENTITY
        or candidate["task_id"] != "TASK-P6-06"
        or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
        or candidate["synthetic"] is not True
    ):
        _fail("RUNTIME_POLICY_VERSION_MISMATCH", "runtime-policy")

    contract = _expect_object(candidate["contract"], "runtime-policy.contract")
    if contract != {
        "duration_prediction_version": PREDICTION_VERSION,
        "fallback_contract_version": "standard-duration-fallback.v1",
        "feature_record_version": FEATURE_RECORD_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
    }:
        _fail("RUNTIME_POLICY_CONTRACT_MISMATCH", "runtime-policy.contract")
    environment = _expect_object(
        candidate["runtime_environment"], "runtime-policy.environment"
    )
    if environment != {
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "explicit_invocation_only": True,
        "in_process_only": True,
        "runtime_enabled": True,
    }:
        _fail("RUNTIME_POLICY_ENVIRONMENT_MISMATCH", "runtime-policy.environment")
    drift = _expect_object(candidate["drift_policy"], "runtime-policy.drift")
    if drift != {
        "decision": "NOT_APPLICABLE_TO_FIXED_SIMULATION_TEST_REPLAY",
        "monitoring_formed": False,
        "production_use": False,
    }:
        _fail("RUNTIME_POLICY_DRIFT_MISMATCH", "runtime-policy.drift")
    confidence = _expect_object(
        candidate["confidence_policy"], "runtime-policy.confidence"
    )
    if (
        confidence.get("formula") != "max(0,1-(p90_seconds-p50_seconds)/p50_seconds)"
        or confidence.get("policy_version") != "interval-tightness-confidence.v1"
    ):
        _fail("RUNTIME_POLICY_CONFIDENCE_MISMATCH", "runtime-policy.confidence")
    threshold = _expect_object(
        confidence.get("threshold"), "runtime-policy.confidence.threshold"
    )
    confidence_threshold = Fraction(
        _expect_int(threshold.get("numerator"), "threshold.numerator", minimum=1),
        _expect_int(threshold.get("denominator"), "threshold.denominator", minimum=1),
    )
    if confidence_threshold != Fraction(9, 10):
        _fail("RUNTIME_POLICY_CONFIDENCE_MISMATCH", "runtime-policy.threshold")
    fallback = _expect_object(candidate["fallback_policy"], "runtime-policy.fallback")
    if (
        fallback.get("invalid_standard_duration_decision") != "FAIL_CLOSED"
        or fallback.get("selected_duration_source")
        != "STANDARD_DURATION_RESOURCE_OPTION"
        or tuple(cast(list[str], fallback.get("registered_reasons")))
        != REGISTERED_FALLBACK_REASONS
    ):
        _fail("RUNTIME_POLICY_FALLBACK_MISMATCH", "runtime-policy.fallback")
    governance = _expect_object(
        candidate["governance_boundary"], "runtime-policy.governance"
    )
    if governance != {
        "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        "planning_authority": "ADVISORY_DURATION_ONLY",
        "production_authorized": False,
        "promotion_authorized": False,
    }:
        _fail("RUNTIME_POLICY_AUTHORITY_MISMATCH", "runtime-policy.governance")
    resource = _expect_object(candidate["resource_policy"], "runtime-policy.resource")
    evidence = _expect_object(candidate["evidence_profile"], "runtime-policy.evidence")
    return LoadedRuntimePolicy(
        document=candidate,
        fingerprint=cast(str, fingerprint),
        confidence_threshold=confidence_threshold,
        prediction_timeout_ns=_expect_int(
            resource.get("prediction_timeout_ns"), "resource.timeout", minimum=1
        ),
        max_feature_record_bytes=_expect_int(
            resource.get("max_feature_record_bytes"),
            "resource.feature-bytes",
            minimum=1,
        ),
        max_prediction_bytes=_expect_int(
            resource.get("max_prediction_bytes"), "resource.prediction-bytes", minimum=1
        ),
        max_features=_expect_int(
            resource.get("max_features"), "resource.features", minimum=1
        ),
        max_source_records=_expect_int(
            resource.get("max_source_records"), "resource.sources", minimum=1
        ),
        benchmark_warmup_calls=_expect_int(
            evidence.get("benchmark_warmup_calls"), "evidence.warmup", minimum=1
        ),
        benchmark_measured_calls=_expect_int(
            evidence.get("benchmark_measured_calls"), "evidence.measured", minimum=1
        ),
        max_p95_latency_ns=_expect_int(
            evidence.get("max_p95_latency_ns"), "evidence.p95", minimum=1
        ),
        max_peak_allocated_bytes=_expect_int(
            evidence.get("max_peak_allocated_bytes"), "evidence.memory", minimum=1
        ),
    )


def load_duration_runtime_policy(path: Path) -> LoadedRuntimePolicy:
    """Load the one approved content-addressed policy with strict JSON parsing."""

    if path.is_symlink():
        _fail("UNSAFE_RUNTIME_POLICY_PATH", "symlink")
    try:
        if not path.is_file():
            _fail("RUNTIME_POLICY_READ_FAILED", "not-regular-file")
        raw = path.read_bytes()
    except P6RuntimeError:
        raise
    except OSError:
        _fail("RUNTIME_POLICY_READ_FAILED", "read")
    if len(raw) > MAX_POLICY_BYTES:
        _fail("RUNTIME_POLICY_TOO_LARGE", "runtime-policy")
    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6RuntimeError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        _fail("RUNTIME_POLICY_PARSE_FAILED", "runtime-policy")
    return _validate_runtime_policy(_expect_object(loaded, "runtime-policy"))


def _model_fallback_reason(error: P6ModelError) -> str:
    if error.code in {"ARTIFACT_READ_FAILED", "DEPENDENCY_LOCK_READ_FAILED"}:
        return "PROVIDER_UNAVAILABLE"
    if error.code in {"ARTIFACT_DIGEST_MISMATCH", "FINGERPRINT_MISMATCH"}:
        return "ARTIFACT_DIGEST_MISMATCH"
    if "MODEL_VERSION" in error.code or error.code in {
        "ALGORITHM_INCOMPATIBLE",
        "SERIALIZATION_VERSION_INCOMPATIBLE",
    }:
        return "MODEL_VERSION_INCOMPATIBLE"
    if "FEATURE_VERSION" in error.code or error.code == "FEATURE_CONTRACT_MISMATCH":
        return "FEATURE_VERSION_INCOMPATIBLE"
    if "DATASET" in error.code:
        return "DATASET_VERSION_INCOMPATIBLE"
    if error.code in {"MODEL_OUT_OF_SCOPE", "MODEL_SCOPE_MISMATCH"}:
        return "MODEL_OUT_OF_SCOPE"
    if error.code in {
        "GOVERNANCE_BOUNDARY_MISMATCH",
        "UNSAFE_SERIALIZATION_FORMAT",
        "UNSAFE_ARTIFACT_PATH",
    }:
        return "MODEL_NOT_APPROVED"
    if error.code in {"INVALID_MODEL_OUTPUT", "INVALID_MODEL_PARAMETERS"}:
        return "INVALID_QUANTILES"
    return "PROVENANCE_INCOMPLETE"


def _gate_fallback_reason(
    policy: LoadedRuntimePolicy,
    profile: LoadedEvaluationProfile,
    gate_report: Mapping[str, Any],
) -> str | None:
    expected = _expect_object(
        policy.document["evaluation_gate"], "runtime-policy.evaluation-gate"
    )
    if profile.document.get("profile_id") != expected.get(
        "profile_id"
    ) or profile.fingerprint != expected.get("profile_fingerprint"):
        return "PROVENANCE_INCOMPLETE"
    decision = gate_report.get("gate_decision")
    if (
        not isinstance(decision, dict)
        or decision.get("decision") != ("READY_FOR_SIMULATION_RUNTIME")
        or decision.get("blocking_gaps") != []
    ):
        return "EVALUATION_GATE_NOT_PASSED"
    try:
        validate_offline_gate_report(gate_report, profile)
    except P6EvaluationError:
        return "PROVENANCE_INCOMPLETE"
    if (
        gate_report.get("gate_report_id") != expected.get("gate_report_id")
        or gate_report.get("gate_report_fingerprint")
        != expected.get("gate_report_fingerprint")
        or decision.get("gate_contract") != expected.get("gate_contract")
    ):
        return "PROVENANCE_INCOMPLETE"
    measurement = gate_report.get("measurement_report")
    if not isinstance(measurement, dict) or {
        "duration_evaluation_report_version": measurement.get(
            "duration_evaluation_report_version"
        ),
        "evaluation_report_id": measurement.get("evaluation_report_id"),
        "evaluation_report_fingerprint": measurement.get(
            "evaluation_report_fingerprint"
        ),
        "gate_decision": cast(
            dict[str, Any], measurement.get("gate_assessment", {})
        ).get("decision"),
    } != expected.get("measurement_reference"):
        return "PROVENANCE_INCOMPLETE"
    return None


def _baseline_candidate(
    model: LoadedDurationModel, feature_record: Mapping[str, Any]
) -> DurationCandidate:
    estimate = predict_duration(model, feature_record)
    return DurationCandidate(
        p50_seconds=estimate.get("p50_seconds"),
        p90_seconds=estimate.get("p90_seconds"),
    )


@dataclass(frozen=True)
class DurationPredictionProvider:
    """Immutable provider; each call builds a fresh carrier and stores no state."""

    policy: LoadedRuntimePolicy
    model: LoadedDurationModel | None
    startup_fallback_reason: str | None
    candidate_predictor: CandidatePredictor
    monotonic_clock: MonotonicClock

    def predict(self, request: DurationPredictionRequest) -> JsonObject:
        """Return a model candidate or an exact standard-duration fallback."""

        return _predict(self, request)


def build_duration_prediction_provider(
    *,
    runtime_policy: LoadedRuntimePolicy,
    evaluation_profile: LoadedEvaluationProfile,
    gate_report: Mapping[str, Any],
    model_bundle: Mapping[str, Any],
    model_artifact_path: Path,
    candidate_predictor: CandidatePredictor = _baseline_candidate,
    monotonic_clock: MonotonicClock = time.monotonic_ns,
) -> DurationPredictionProvider:
    """Validate exact Gate/model inputs and build a default-deny provider."""

    startup_reason = _gate_fallback_reason(
        runtime_policy, evaluation_profile, deepcopy(dict(gate_report))
    )
    loaded_model: LoadedDurationModel | None = None
    if startup_reason is None:
        try:
            bundle = _expect_object(deepcopy(dict(model_bundle)), "model-bundle")
            manifest = _expect_object(bundle.get("model_manifest"), "model-manifest")
            configuration = _expect_object(
                bundle.get("training_configuration"), "training-configuration"
            )
            authorization = _expect_object(
                runtime_policy.document["model_authorization"],
                "runtime-policy.model",
            )
            if manifest.get("model_version") != authorization.get("model_version"):
                startup_reason = "MODEL_VERSION_INCOMPATIBLE"
            elif manifest.get("model_artifact", {}).get("artifact_digest") != (
                authorization.get("model_artifact_digest")
            ):
                startup_reason = "ARTIFACT_DIGEST_MISMATCH"
            elif manifest.get("model_manifest_id") != authorization.get(
                "model_manifest_id"
            ) or manifest.get("model_manifest_fingerprint") != authorization.get(
                "model_manifest_fingerprint"
            ):
                startup_reason = "PROVENANCE_INCOMPLETE"
            else:
                loaded_model = load_duration_model(
                    model_artifact_path, manifest, configuration
                )
        except P6ModelError as error:
            startup_reason = _model_fallback_reason(error)
        except P6RuntimeError:
            startup_reason = "PROVENANCE_INCOMPLETE"
        except (AttributeError, KeyError, TypeError):
            startup_reason = "PROVENANCE_INCOMPLETE"
    return DurationPredictionProvider(
        policy=runtime_policy,
        model=loaded_model,
        startup_fallback_reason=startup_reason,
        candidate_predictor=candidate_predictor,
        monotonic_clock=monotonic_clock,
    )


def _validate_standard_duration(value: Mapping[str, Any]) -> JsonObject:
    authority = _expect_object(deepcopy(dict(value)), "standard-duration")
    _expect_keys(authority, _STANDARD_DURATION_KEYS, "standard-duration")
    _expect_int(authority["seconds"], "standard-duration.seconds", minimum=1)
    for key in ("duration_source", "source_version", "source_record_id"):
        _expect_identifier(authority[key], f"standard-duration.{key}")
    _expect_fingerprint(
        authority["source_record_fingerprint"],
        "standard-duration.source_record_fingerprint",
    )
    return authority


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            lowered = key.lower()
            if (
                lowered in _SENSITIVE_KEYS
                or lowered.endswith("_password")
                or lowered.endswith("_secret")
                or lowered.endswith("_token")
                or lowered.endswith("_credential")
            ):
                return True
            if _contains_sensitive_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _contains_monitoring_direct_identifier(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                isinstance(key, str)
                and key.lower() in _MONITORING_DIRECT_IDENTIFIER_KEYS
            ):
                return True
            if _contains_monitoring_direct_identifier(child):
                return True
    elif isinstance(value, list):
        return any(_contains_monitoring_direct_identifier(item) for item in value)
    return False


def _feature_reference(feature_record: Mapping[str, Any]) -> JsonObject:
    return {
        "duration_feature_record_version": FEATURE_RECORD_VERSION,
        "feature_record_id": _expect_identifier(
            feature_record.get("feature_record_id"), "feature-record.id"
        ),
        "feature_record_fingerprint": _expect_fingerprint(
            feature_record.get("feature_record_fingerprint"),
            "feature-record.fingerprint",
        ),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
    }


def _feature_fallback_reason(
    *,
    policy: LoadedRuntimePolicy,
    request: DurationPredictionRequest,
    feature_record: JsonObject,
    standard_duration: Mapping[str, Any],
) -> str | None:
    try:
        feature_bytes = _canonical_json_bytes(feature_record)
    except P6RuntimeError:
        return "FEATURE_VERSION_INCOMPATIBLE"
    if len(feature_bytes) > policy.max_feature_record_bytes:
        return "FEATURE_VERSION_INCOMPATIBLE"
    if _contains_sensitive_key(feature_record):
        return "PRIVACY_GOVERNANCE_FAILED"
    if set(feature_record) != _FEATURE_ROOT_KEYS:
        return "CONTRACT_VERSION_INCOMPATIBLE"
    if (
        feature_record.get("duration_feature_record_version") != FEATURE_RECORD_VERSION
        or feature_record.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
    ):
        return "FEATURE_VERSION_INCOMPATIBLE"
    if (
        feature_record.get("schema_set_version") != SCHEMA_SET_VERSION
        or feature_record.get("canonicalization_version") != CANONICALIZATION_VERSION
    ):
        return "CONTRACT_VERSION_INCOMPATIBLE"
    if (
        feature_record.get("data_plane") != DATA_PLANE
        or feature_record.get("environment") != ENVIRONMENT
    ):
        return "AUTHORITY_NOT_ESTABLISHED"
    if (
        feature_record.get("pii_fields_present") is not False
        or feature_record.get("target_fields_present") is not False
        or feature_record.get("synthetic") is not True
        or feature_record.get("production_binding") is not False
        or feature_record.get("governance_boundary")
        != {
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
            "production_authorized": False,
        }
    ):
        return "PRIVACY_GOVERNANCE_FAILED"
    projection = {
        key: value
        for key, value in feature_record.items()
        if key not in {"feature_record_id", "feature_record_fingerprint"}
    }
    expected_fingerprint = _fingerprint(projection)
    if feature_record.get(
        "feature_record_fingerprint"
    ) != expected_fingerprint or feature_record.get(
        "feature_record_id"
    ) != "duration-feature-record-" + expected_fingerprint.removeprefix("sha256:"):
        return "PROVENANCE_INCOMPLETE"
    if (
        feature_record.get("factory_id") != request.factory_id
        or feature_record.get("operation_id") != request.operation_id
        or feature_record.get("resource_option_id") != request.resource_option_id
        or feature_record.get("resource_id") != request.resource_id
        or feature_record.get("as_of_cutoff_utc") != request.as_of_cutoff_utc
    ):
        return "PROVENANCE_INCOMPLETE"
    sources = feature_record.get("source_records")
    features = feature_record.get("features")
    if (
        not isinstance(sources, list)
        or len(sources) != policy.max_source_records
        or not isinstance(features, list)
        or len(features) != policy.max_features
    ):
        return "FEATURE_VERSION_INCOMPATIBLE"
    source_by_id: dict[str, JsonObject] = {}
    for raw_source in sources:
        if not isinstance(raw_source, dict) or set(raw_source) != _SOURCE_RECORD_KEYS:
            return "FEATURE_VERSION_INCOMPATIBLE"
        source = cast(JsonObject, raw_source)
        source_id = source.get("source_record_id")
        if not isinstance(source_id, str) or source_id in source_by_id:
            return "PROVENANCE_INCOMPLETE"
        try:
            _expect_fingerprint(source.get("record_fingerprint"), "source.fingerprint")
            _, observed = _utc_instant(source.get("observed_at_utc"), "source.observed")
            _, available = _utc_instant(
                source.get("available_at_utc"), "source.available"
            )
            _, cutoff = _utc_instant(request.as_of_cutoff_utc, "request.cutoff")
        except P6RuntimeError:
            return "FEATURE_VERSION_INCOMPATIBLE"
        if observed > available or available > cutoff:
            return "PROVENANCE_INCOMPLETE"
        source_by_id[source_id] = source
    feature_by_name: dict[str, JsonObject] = {}
    for raw_feature in features:
        if not isinstance(raw_feature, dict) or set(raw_feature) != _FEATURE_KEYS:
            return "FEATURE_VERSION_INCOMPATIBLE"
        feature = cast(JsonObject, raw_feature)
        name = feature.get("feature_name")
        if not isinstance(name, str) or name in feature_by_name:
            return "FEATURE_VERSION_INCOMPATIBLE"
        source_ids = feature.get("source_record_ids")
        if (
            not isinstance(source_ids, list)
            or len(source_ids) != 1
            or source_ids[0] not in source_by_id
        ):
            return "PROVENANCE_INCOMPLETE"
        feature_by_name[name] = feature
    if tuple(sorted(feature_by_name)) != EXPECTED_FEATURE_NAMES:
        return "FEATURE_VERSION_INCOMPATIBLE"
    standard_feature = feature_by_name["standard_duration_seconds"]
    source = source_by_id[cast(list[str], standard_feature["source_record_ids"])[0]]
    if (
        standard_feature.get("value") != standard_duration.get("seconds")
        or source.get("source_system") != standard_duration.get("duration_source")
        or source.get("source_version") != standard_duration.get("source_version")
        or source.get("source_record_id") != standard_duration.get("source_record_id")
        or source.get("record_fingerprint")
        != standard_duration.get("source_record_fingerprint")
    ):
        return "PROVENANCE_INCOMPLETE"
    return None


def _candidate_decision(
    provider: DurationPredictionProvider,
    feature_record: Mapping[str, Any],
) -> tuple[str, int | None, int | None, float | None]:
    if provider.startup_fallback_reason is not None:
        return provider.startup_fallback_reason, None, None, None
    if provider.model is None:
        return "PROVIDER_UNAVAILABLE", None, None, None
    started = provider.monotonic_clock()
    try:
        candidate = provider.candidate_predictor(provider.model, feature_record)
    except DurationProviderSignal as signal:
        reason = signal.fallback_reason
        if reason not in REGISTERED_FALLBACK_REASONS:
            reason = "PROVIDER_UNAVAILABLE"
        return reason, None, None, None
    except P6ModelError as error:
        return _model_fallback_reason(error), None, None, None
    except Exception:
        return "PROVIDER_UNAVAILABLE", None, None, None
    finished = provider.monotonic_clock()
    elapsed = finished - started
    if elapsed < 0 or elapsed > provider.policy.prediction_timeout_ns:
        return "PROVIDER_TIMEOUT", None, None, None
    if candidate is None:
        return "PREDICTION_MISSING", None, None, None
    p50 = candidate.p50_seconds
    p90 = candidate.p90_seconds
    if (
        isinstance(p50, bool)
        or not isinstance(p50, int)
        or isinstance(p90, bool)
        or not isinstance(p90, int)
        or p50 <= 0
        or p90 <= 0
        or p90 < p50
    ):
        return "INVALID_QUANTILES", None, None, None
    if candidate.derive_confidence:
        try:
            confidence = interval_tightness_confidence(p50, p90)
        except P6EvaluationError:
            return "INVALID_QUANTILES", None, None, None
    else:
        raw_confidence = candidate.confidence
        if raw_confidence is None:
            return "CONFIDENCE_MISSING", None, None, None
        if isinstance(raw_confidence, bool) or not isinstance(
            raw_confidence, (int, float, Fraction)
        ):
            return "CONFIDENCE_INVALID", None, None, None
        if isinstance(raw_confidence, float) and not math.isfinite(raw_confidence):
            return "CONFIDENCE_INVALID", None, None, None
        confidence = Fraction(raw_confidence)
        if confidence < 0 or confidence > 1:
            return "CONFIDENCE_INVALID", None, None, None
    if confidence < provider.policy.confidence_threshold:
        return "LOW_CONFIDENCE", None, None, None
    return "NONE", p50, p90, confidence.numerator / confidence.denominator


def _predict(
    provider: DurationPredictionProvider, request: DurationPredictionRequest
) -> JsonObject:
    factory_id = _expect_identifier(request.factory_id, "request.factory-id")
    operation_id = _expect_identifier(request.operation_id, "request.operation-id")
    resource_option_id = _expect_identifier(
        request.resource_option_id, "request.resource-option-id"
    )
    resource_id = _expect_identifier(request.resource_id, "request.resource-id")
    predicted_at_utc, predicted_at = _utc_instant(
        request.predicted_at_utc, "request.predicted-at"
    )
    as_of_cutoff_utc, as_of_cutoff = _utc_instant(
        request.as_of_cutoff_utc, "request.as-of-cutoff"
    )
    if predicted_at < as_of_cutoff:
        _fail("INVALID_PREDICTION_TIME", "predicted-at-before-cutoff")
    standard_duration = _validate_standard_duration(request.standard_duration)
    feature_record = _expect_object(
        deepcopy(dict(request.feature_record)), "request.feature-record"
    )
    feature_reference = _feature_reference(feature_record)
    fallback_reason = _feature_fallback_reason(
        policy=provider.policy,
        request=request,
        feature_record=feature_record,
        standard_duration=standard_duration,
    )
    p50_seconds: int | None = None
    p90_seconds: int | None = None
    confidence: float | None = None
    if fallback_reason is None:
        fallback_reason, p50_seconds, p90_seconds, confidence = _candidate_decision(
            provider, feature_record
        )
    if fallback_reason == "NONE":
        assert p50_seconds is not None
        selected_source = "MODEL_CANDIDATE"
        selected_seconds = p50_seconds
    else:
        p50_seconds = None
        p90_seconds = None
        confidence = None
        selected_source = "STANDARD_DURATION"
        selected_seconds = cast(int, standard_duration["seconds"])
    policy_document = provider.policy.document
    model_authorization = _expect_object(
        policy_document["model_authorization"], "runtime-policy.model"
    )
    gate = _expect_object(policy_document["evaluation_gate"], "runtime-policy.gate")
    projection: JsonObject = {
        "duration_prediction_version": PREDICTION_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "factory_id": factory_id,
        "operation_id": operation_id,
        "resource_option_id": resource_option_id,
        "resource_id": resource_id,
        "predicted_at_utc": predicted_at_utc,
        "as_of_cutoff_utc": as_of_cutoff_utc,
        "unit": "SECONDS",
        "p50_seconds": p50_seconds,
        "p90_seconds": p90_seconds,
        "confidence": confidence,
        "model_version": MODEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "fallback_reason": fallback_reason,
        "selected_duration_source": selected_source,
        "selected_duration_seconds": selected_seconds,
        "standard_duration": standard_duration,
        "feature_record_reference": feature_reference,
        "model_reference": {
            "duration_model_manifest_version": MODEL_MANIFEST_VERSION,
            "model_manifest_id": model_authorization["model_manifest_id"],
            "model_manifest_fingerprint": model_authorization[
                "model_manifest_fingerprint"
            ],
            "model_version": model_authorization["model_version"],
            "model_artifact_digest": model_authorization["model_artifact_digest"],
        },
        "evaluation_reference": deepcopy(gate["measurement_reference"]),
        "prediction_policy_reference": {
            "document_version": RUNTIME_POLICY_VERSION,
            "artifact_id": policy_document["policy_id"],
            "fingerprint": policy_document["policy_fingerprint"],
        },
        "synthetic": True,
        "synthetic_provenance": deepcopy(policy_document["synthetic_provenance"]),
        "production_binding": False,
        "governance_boundary": {
            "production_authorized": False,
            "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
            "planning_authority": "ADVISORY_DURATION_ONLY",
        },
    }
    prediction = _with_identity(projection)
    validate_duration_prediction(prediction, provider.policy)
    if len(_canonical_json_bytes(prediction)) > provider.policy.max_prediction_bytes:
        _fail("PREDICTION_RESOURCE_LIMIT", "prediction-bytes")
    return prediction


def validate_duration_prediction(
    prediction: Mapping[str, Any], policy: LoadedRuntimePolicy
) -> None:
    """Freshly verify identity and the P6-02 candidate/fallback invariants."""

    candidate = _expect_object(deepcopy(dict(prediction)), "prediction")
    _expect_keys(candidate, _PREDICTION_KEYS, "prediction")
    projection = deepcopy(candidate)
    identifier = projection.pop("prediction_id")
    fingerprint = projection.pop("prediction_fingerprint")
    expected = _fingerprint(projection)
    if (
        fingerprint != expected
        or identifier != "duration-prediction-" + expected.removeprefix("sha256:")
    ):
        _fail("PREDICTION_IDENTITY_MISMATCH", "prediction")
    if (
        candidate["duration_prediction_version"] != PREDICTION_VERSION
        or candidate["schema_set_version"] != SCHEMA_SET_VERSION
        or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
        or candidate["data_plane"] != DATA_PLANE
        or candidate["environment"] != ENVIRONMENT
        or candidate["unit"] != "SECONDS"
        or candidate["model_version"] != MODEL_VERSION
        or candidate["feature_schema_version"] != FEATURE_SCHEMA_VERSION
        or candidate["synthetic"] is not True
        or candidate["production_binding"] is not False
    ):
        _fail("PREDICTION_CONTRACT_MISMATCH", "prediction.header")
    reason = candidate["fallback_reason"]
    if reason != "NONE" and reason not in REGISTERED_FALLBACK_REASONS:
        _fail("PREDICTION_FALLBACK_MISMATCH", "prediction.reason")
    standard = _validate_standard_duration(
        cast(Mapping[str, Any], candidate["standard_duration"])
    )
    if reason == "NONE":
        p50 = _expect_int(candidate["p50_seconds"], "prediction.p50", minimum=1)
        p90 = _expect_int(candidate["p90_seconds"], "prediction.p90", minimum=1)
        confidence = candidate["confidence"]
        if (
            p90 < p50
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0 <= confidence <= 1
            or candidate["selected_duration_source"] != "MODEL_CANDIDATE"
            or candidate["selected_duration_seconds"] != p50
        ):
            _fail("PREDICTION_CANDIDATE_MISMATCH", "prediction.candidate")
    elif (
        candidate["p50_seconds"] is not None
        or candidate["p90_seconds"] is not None
        or candidate["confidence"] is not None
        or candidate["selected_duration_source"] != "STANDARD_DURATION"
        or candidate["selected_duration_seconds"] != standard["seconds"]
    ):
        _fail("PREDICTION_FALLBACK_MISMATCH", "prediction.fallback")
    expected_policy_reference = {
        "document_version": RUNTIME_POLICY_VERSION,
        "artifact_id": policy.document["policy_id"],
        "fingerprint": policy.document["policy_fingerprint"],
    }
    if candidate["prediction_policy_reference"] != expected_policy_reference:
        _fail("PREDICTION_POLICY_MISMATCH", "prediction.policy")
    if candidate["governance_boundary"] != {
        "production_authorized": False,
        "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        "planning_authority": "ADVISORY_DURATION_ONLY",
    }:
        _fail("PREDICTION_AUTHORITY_MISMATCH", "prediction.governance")


@dataclass(frozen=True)
class LoadedMonitoringPolicy:
    """Exact aggregate-only Simulation/Test monitoring authorization."""

    document: JsonObject
    fingerprint: str
    fallback_rate_max: Fraction
    feature_total_variation_max: Fraction
    quality_pass_ratio_min: Fraction
    expected_observation_count: int
    minimum_observation_count: int
    late_observation_max_count: int
    reference_bucket_counts: Mapping[str, int]


@dataclass(frozen=True)
class ValidatedMonitoringWindow:
    """Strict aggregate projection; it contains no record-level telemetry."""

    document: JsonObject
    fingerprint: str
    observation_count: int
    candidate_count: int
    fallback_count: int
    fallback_reason_counts: Mapping[str, int]
    late_observation_count: int
    model_version_matches: bool
    feature_version_matches: bool
    feature_bucket_counts: Mapping[str, int]
    quality_evaluated_count: int
    quality_pass_count: int


def _expect_ratio(
    value: object,
    path: str,
    *,
    minimum: Fraction = Fraction(0),
    maximum: Fraction = Fraction(1),
) -> Fraction:
    ratio = _expect_object(value, path)
    _expect_keys(ratio, {"denominator", "numerator"}, path)
    numerator = _expect_int(ratio["numerator"], f"{path}.numerator")
    denominator = _expect_int(ratio["denominator"], f"{path}.denominator", minimum=1)
    result = Fraction(numerator, denominator)
    if result < minimum or result > maximum:
        _fail("INVALID_RATIO", path)
    return result


def _validate_monitoring_policy(
    document: Mapping[str, Any],
) -> LoadedMonitoringPolicy:
    candidate = deepcopy(dict(document))
    _expect_keys(
        candidate,
        {
            "canonicalization_version",
            "decision_policy",
            "duration_monitoring_policy_version",
            "governance_boundary",
            "policy_fingerprint",
            "policy_id",
            "policy_version",
            "privacy_retention",
            "reference_distribution",
            "runtime_environment",
            "runtime_reference",
            "synthetic_provenance",
            "task_id",
            "thresholds",
            "window_policy",
        },
        "monitoring-policy",
    )
    projection = deepcopy(candidate)
    identifier = projection.pop("policy_id")
    fingerprint = projection.pop("policy_fingerprint")
    expected_fingerprint = _fingerprint(projection)
    if (
        fingerprint != expected_fingerprint
        or fingerprint != EXPECTED_MONITORING_POLICY_FINGERPRINT
        or identifier != EXPECTED_MONITORING_POLICY_ID
    ):
        _fail("MONITORING_POLICY_IDENTITY_MISMATCH", "monitoring-policy")
    if (
        candidate["duration_monitoring_policy_version"] != MONITORING_POLICY_VERSION
        or candidate["policy_version"] != MONITORING_POLICY_IDENTITY
        or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
        or candidate["task_id"] != "TASK-P6-08"
    ):
        _fail("MONITORING_POLICY_VERSION_MISMATCH", "monitoring-policy")

    runtime_reference = _expect_object(
        candidate["runtime_reference"], "monitoring-policy.runtime-reference"
    )
    if runtime_reference != {
        "duration_runtime_policy_version": RUNTIME_POLICY_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "policy_fingerprint": EXPECTED_POLICY_FINGERPRINT,
        "policy_id": EXPECTED_POLICY_ID,
    }:
        _fail("MONITORING_POLICY_LINEAGE_MISMATCH", "runtime-reference")
    environment = _expect_object(
        candidate["runtime_environment"], "monitoring-policy.environment"
    )
    if environment != {
        "data_plane": DATA_PLANE,
        "environment": ENVIRONMENT,
        "explicit_aggregate_input_only": True,
        "production_binding": False,
        "synthetic": True,
    }:
        _fail("MONITORING_POLICY_ENVIRONMENT_MISMATCH", "environment")

    window = _expect_object(candidate["window_policy"], "monitoring-policy.window")
    if set(window) != {
        "expected_observation_count",
        "late_observation_max_count",
        "minimum_observation_count",
        "window_mode",
        "window_version",
    }:
        _fail("MONITORING_POLICY_WINDOW_MISMATCH", "window")
    expected_observation_count = _expect_int(
        window["expected_observation_count"], "window.expected-count", minimum=1
    )
    minimum_observation_count = _expect_int(
        window["minimum_observation_count"], "window.minimum-count", minimum=1
    )
    late_observation_max_count = _expect_int(
        window["late_observation_max_count"], "window.late-count"
    )
    if (
        window["window_mode"] != "FIXED_COUNT_EXPLICIT_HALF_OPEN_UTC"
        or window["window_version"] != MONITORING_WINDOW_VERSION
        or expected_observation_count != 8
        or minimum_observation_count != 8
        or late_observation_max_count != 0
    ):
        _fail("MONITORING_POLICY_WINDOW_MISMATCH", "window")

    thresholds = _expect_object(candidate["thresholds"], "monitoring-policy.thresholds")
    _expect_keys(
        thresholds,
        {
            "fallback_rate_max",
            "feature_total_variation_max",
            "quality_pass_ratio_min",
            "threshold_policy_version",
        },
        "monitoring-policy.thresholds",
    )
    fallback_rate_max = _expect_ratio(
        thresholds["fallback_rate_max"], "thresholds.fallback-rate"
    )
    feature_total_variation_max = _expect_ratio(
        thresholds["feature_total_variation_max"], "thresholds.feature-drift"
    )
    quality_pass_ratio_min = _expect_ratio(
        thresholds["quality_pass_ratio_min"], "thresholds.quality"
    )
    if (
        thresholds["threshold_policy_version"] != MONITORING_THRESHOLD_VERSION
        or fallback_rate_max != Fraction(1, 4)
        or feature_total_variation_max != Fraction(1, 4)
        or quality_pass_ratio_min != Fraction(3, 4)
    ):
        _fail("MONITORING_POLICY_THRESHOLD_MISMATCH", "thresholds")

    reference = _expect_object(
        candidate["reference_distribution"], "monitoring-policy.reference"
    )
    _expect_keys(
        reference,
        {"bucket_counts", "profile_version", "total_count"},
        "monitoring-policy.reference",
    )
    reference_counts_raw = _expect_object(
        reference["bucket_counts"], "monitoring-policy.reference.bucket-counts"
    )
    if set(reference_counts_raw) != set(MONITORING_FEATURE_BUCKETS):
        _fail("MONITORING_POLICY_REFERENCE_MISMATCH", "reference.bucket-counts")
    reference_counts = {
        bucket: _expect_int(
            reference_counts_raw[bucket], f"reference.bucket-counts.{bucket}"
        )
        for bucket in MONITORING_FEATURE_BUCKETS
    }
    reference_total = _expect_int(
        reference["total_count"], "reference.total-count", minimum=1
    )
    if (
        reference["profile_version"] != MONITORING_FEATURE_PROFILE_VERSION
        or reference_total != 8
        or sum(reference_counts.values()) != reference_total
        or any(count != 2 for count in reference_counts.values())
    ):
        _fail("MONITORING_POLICY_REFERENCE_MISMATCH", "reference")

    privacy = _expect_object(
        candidate["privacy_retention"], "monitoring-policy.privacy"
    )
    if privacy != {
        "direct_identifiers_allowed": False,
        "persistence": "NONE",
        "provider_artifact": "AGGREGATE_REPORT_ONLY",
        "raw_feature_fields_allowed": False,
        "raw_label_fields_allowed": False,
        "retained_window_count": 1,
        "retention_policy_version": "run-scoped-aggregate-retention.v1",
        "source_record_references_allowed": False,
        "telemetry_granularity": "AGGREGATE_WINDOW_ONLY",
    }:
        _fail("MONITORING_POLICY_PRIVACY_MISMATCH", "privacy")
    decision = _expect_object(
        candidate["decision_policy"], "monitoring-policy.decision"
    )
    if decision != {
        "automatic_actions": [],
        "external_side_effects": False,
        "on_breach": "DEFAULT_DISABLE_AND_STANDARD_DURATION_FALLBACK",
        "on_invalid_input": "DEFAULT_DISABLE_AND_STANDARD_DURATION_FALLBACK",
    }:
        _fail("MONITORING_POLICY_DECISION_MISMATCH", "decision")
    governance = _expect_object(
        candidate["governance_boundary"], "monitoring-policy.governance"
    )
    if governance != {
        "automatic_promotion_authorized": False,
        "automatic_retraining_authorized": False,
        "automatic_rollback_authorized": False,
        "open_authority_gaps": list(OPEN_AUTHORITY_GAPS),
        "planning_authority": "ADVISORY_DURATION_ONLY",
        "production_authorized": False,
    }:
        _fail("MONITORING_POLICY_AUTHORITY_MISMATCH", "governance")
    provenance = _expect_object(
        candidate["synthetic_provenance"], "monitoring-policy.provenance"
    )
    if provenance != {
        "assumption_profile": MONITORING_POLICY_IDENTITY,
        "assumption_refs": [
            "SIM-ASSUMPTION-021",
            "SIM-ASSUMPTION-022",
            "SIM-ASSUMPTION-023",
            "SIM-ASSUMPTION-024",
            "SIM-ASSUMPTION-025",
            "SIM-ASSUMPTION-026",
        ],
    }:
        _fail("MONITORING_POLICY_PROVENANCE_MISMATCH", "provenance")
    return LoadedMonitoringPolicy(
        document=candidate,
        fingerprint=cast(str, fingerprint),
        fallback_rate_max=fallback_rate_max,
        feature_total_variation_max=feature_total_variation_max,
        quality_pass_ratio_min=quality_pass_ratio_min,
        expected_observation_count=expected_observation_count,
        minimum_observation_count=minimum_observation_count,
        late_observation_max_count=late_observation_max_count,
        reference_bucket_counts=reference_counts,
    )


def load_duration_monitoring_policy(path: Path) -> LoadedMonitoringPolicy:
    """Load the exact monitoring policy without accepting ambient defaults."""

    if path.is_symlink():
        _fail("UNSAFE_MONITORING_POLICY_PATH", "symlink")
    try:
        if not path.is_file():
            _fail("MONITORING_POLICY_READ_FAILED", "not-regular-file")
        raw = path.read_bytes()
    except P6RuntimeError:
        raise
    except OSError:
        _fail("MONITORING_POLICY_READ_FAILED", "read")
    if len(raw) > MAX_MONITORING_POLICY_BYTES:
        _fail("MONITORING_POLICY_TOO_LARGE", "monitoring-policy")
    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6RuntimeError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        _fail("MONITORING_POLICY_PARSE_FAILED", "monitoring-policy")
    return _validate_monitoring_policy(_expect_object(loaded, "monitoring-policy"))


def _expect_count_mapping(
    value: object,
    path: str,
    *,
    allowed_keys: set[str] | None = None,
    maximum_keys: int = 32,
    positive_only: bool = False,
) -> dict[str, int]:
    mapping = _expect_object(value, path)
    if len(mapping) > maximum_keys:
        _fail("TELEMETRY_WINDOW_INVALID", path)
    counts: dict[str, int] = {}
    for raw_key, raw_count in mapping.items():
        key = _expect_identifier(raw_key, f"{path}.key")
        if allowed_keys is not None and key not in allowed_keys:
            _fail("TELEMETRY_WINDOW_INVALID", path)
        counts[key] = _expect_int(
            raw_count, f"{path}.{key}", minimum=1 if positive_only else 0
        )
    return counts


def _validate_monitoring_window(
    policy: LoadedMonitoringPolicy,
    window: object,
) -> ValidatedMonitoringWindow:
    if not isinstance(window, Mapping) or any(
        not isinstance(key, str) for key in window
    ):
        _fail("TELEMETRY_WINDOW_INVALID", "aggregate-window")
    candidate = deepcopy(dict(window))
    if _contains_sensitive_key(candidate) or _contains_monitoring_direct_identifier(
        candidate
    ):
        _fail("TELEMETRY_PRIVACY_VIOLATION", "aggregate-window")
    try:
        _expect_keys(
            candidate,
            {
                "canonicalization_version",
                "data_plane",
                "duration_monitoring_window_version",
                "environment",
                "feature_distribution",
                "outcomes",
                "policy_reference",
                "privacy",
                "production_binding",
                "quality",
                "runtime_reference",
                "synthetic",
                "versions",
                "window",
                "window_fingerprint",
                "window_id",
            },
            "aggregate-window",
        )
        if (
            candidate["duration_monitoring_window_version"] != MONITORING_WINDOW_VERSION
            or candidate["canonicalization_version"] != CANONICALIZATION_VERSION
            or candidate["data_plane"] != DATA_PLANE
            or candidate["environment"] != ENVIRONMENT
            or candidate["synthetic"] is not True
            or candidate["production_binding"] is not False
        ):
            _fail("TELEMETRY_LINEAGE_INVALID", "aggregate-window.header")
        expected_policy_reference = {
            "artifact_id": policy.document["policy_id"],
            "document_version": MONITORING_POLICY_VERSION,
            "fingerprint": policy.fingerprint,
            "threshold_policy_version": MONITORING_THRESHOLD_VERSION,
        }
        if candidate["policy_reference"] != expected_policy_reference:
            _fail("TELEMETRY_LINEAGE_INVALID", "aggregate-window.policy")
        if candidate["runtime_reference"] != policy.document["runtime_reference"]:
            _fail("TELEMETRY_LINEAGE_INVALID", "aggregate-window.runtime")
        if candidate["privacy"] != {
            "aggregation": "WINDOW_ONLY",
            "direct_identifiers_present": False,
            "raw_feature_fields_present": False,
            "raw_label_fields_present": False,
            "source_record_references_present": False,
        }:
            _fail("TELEMETRY_PRIVACY_VIOLATION", "aggregate-window.privacy")

        projection = deepcopy(candidate)
        identifier = projection.pop("window_id")
        fingerprint = projection.pop("window_fingerprint")
        expected_fingerprint = _fingerprint(projection)
        if (
            fingerprint != expected_fingerprint
            or identifier
            != "duration-monitoring-window-"
            + expected_fingerprint.removeprefix("sha256:")
        ):
            _fail("TELEMETRY_TAMPERED", "aggregate-window")

        window_data = _expect_object(candidate["window"], "aggregate-window.window")
        _expect_keys(
            window_data,
            {
                "ended_at_utc",
                "late_observation_count",
                "observation_count",
                "sequence",
                "started_at_utc",
            },
            "aggregate-window.window",
        )
        _expect_int(window_data["sequence"], "window.sequence")
        _, started_at = _utc_instant(window_data["started_at_utc"], "window.started-at")
        _, ended_at = _utc_instant(window_data["ended_at_utc"], "window.ended-at")
        if ended_at <= started_at:
            _fail("TELEMETRY_WINDOW_INVALID", "window.half-open-range")
        observation_count = _expect_int(
            window_data["observation_count"], "window.observation-count"
        )
        late_observation_count = _expect_int(
            window_data["late_observation_count"], "window.late-count"
        )
        if late_observation_count > observation_count:
            _fail("TELEMETRY_WINDOW_INVALID", "window.late-count")

        outcomes = _expect_object(candidate["outcomes"], "aggregate-window.outcomes")
        _expect_keys(
            outcomes,
            {"candidate_count", "fallback_count", "fallback_reason_counts"},
            "aggregate-window.outcomes",
        )
        candidate_count = _expect_int(
            outcomes["candidate_count"], "outcomes.candidate-count"
        )
        fallback_count = _expect_int(
            outcomes["fallback_count"], "outcomes.fallback-count"
        )
        fallback_reason_counts = _expect_count_mapping(
            outcomes["fallback_reason_counts"],
            "outcomes.fallback-reasons",
            allowed_keys=set(REGISTERED_FALLBACK_REASONS),
            maximum_keys=len(REGISTERED_FALLBACK_REASONS),
            positive_only=True,
        )
        if (
            candidate_count + fallback_count != observation_count
            or sum(fallback_reason_counts.values()) != fallback_count
        ):
            _fail("TELEMETRY_WINDOW_INVALID", "outcomes.counts")

        versions = _expect_object(candidate["versions"], "aggregate-window.versions")
        _expect_keys(
            versions,
            {"feature_schema_version_counts", "model_version_counts"},
            "aggregate-window.versions",
        )
        model_counts = _expect_count_mapping(
            versions["model_version_counts"],
            "versions.models",
            maximum_keys=4,
            positive_only=True,
        )
        feature_version_counts = _expect_count_mapping(
            versions["feature_schema_version_counts"],
            "versions.features",
            maximum_keys=4,
            positive_only=True,
        )
        if (
            sum(model_counts.values()) != observation_count
            or sum(feature_version_counts.values()) != observation_count
        ):
            _fail("TELEMETRY_WINDOW_INVALID", "versions.counts")

        distribution = _expect_object(
            candidate["feature_distribution"], "aggregate-window.distribution"
        )
        _expect_keys(
            distribution,
            {"bucket_counts", "profile_version"},
            "aggregate-window.distribution",
        )
        if distribution["profile_version"] != MONITORING_FEATURE_PROFILE_VERSION:
            _fail("TELEMETRY_LINEAGE_INVALID", "distribution.profile")
        bucket_counts = _expect_count_mapping(
            distribution["bucket_counts"],
            "distribution.bucket-counts",
            allowed_keys=set(MONITORING_FEATURE_BUCKETS),
            maximum_keys=len(MONITORING_FEATURE_BUCKETS),
        )
        if (
            set(bucket_counts) != set(MONITORING_FEATURE_BUCKETS)
            or sum(bucket_counts.values()) != observation_count
        ):
            _fail("TELEMETRY_WINDOW_INVALID", "distribution.counts")

        quality = _expect_object(candidate["quality"], "aggregate-window.quality")
        _expect_keys(
            quality,
            {"evaluated_count", "pass_count", "policy_version"},
            "aggregate-window.quality",
        )
        if quality["policy_version"] != MONITORING_QUALITY_POLICY_VERSION:
            _fail("TELEMETRY_LINEAGE_INVALID", "quality.policy")
        evaluated_count = _expect_int(
            quality["evaluated_count"], "quality.evaluated-count"
        )
        pass_count = _expect_int(quality["pass_count"], "quality.pass-count")
        if pass_count > evaluated_count or evaluated_count > observation_count:
            _fail("TELEMETRY_WINDOW_INVALID", "quality.counts")
    except P6RuntimeError as error:
        if error.code in {
            "TELEMETRY_LINEAGE_INVALID",
            "TELEMETRY_PRIVACY_VIOLATION",
            "TELEMETRY_TAMPERED",
            "TELEMETRY_WINDOW_INVALID",
        }:
            raise
        _fail("TELEMETRY_WINDOW_INVALID", "aggregate-window")
    return ValidatedMonitoringWindow(
        document=candidate,
        fingerprint=cast(str, fingerprint),
        observation_count=observation_count,
        candidate_count=candidate_count,
        fallback_count=fallback_count,
        fallback_reason_counts=fallback_reason_counts,
        late_observation_count=late_observation_count,
        model_version_matches=model_counts == {MODEL_VERSION: observation_count},
        feature_version_matches=feature_version_counts
        == {FEATURE_SCHEMA_VERSION: observation_count},
        feature_bucket_counts=bucket_counts,
        quality_evaluated_count=evaluated_count,
        quality_pass_count=pass_count,
    )


def _fraction_document(value: Fraction) -> JsonObject:
    return {"denominator": value.denominator, "numerator": value.numerator}


def _feature_total_variation(
    observed: Mapping[str, int], reference: Mapping[str, int]
) -> Fraction:
    observed_total = sum(observed.values())
    reference_total = sum(reference.values())
    if observed_total <= 0 or reference_total <= 0:
        return Fraction(0)
    difference = sum(
        abs(observed[bucket] * reference_total - reference[bucket] * observed_total)
        for bucket in MONITORING_FEATURE_BUCKETS
    )
    return Fraction(difference, 2 * observed_total * reference_total)


def _build_monitoring_report(
    policy: LoadedMonitoringPolicy,
    window: ValidatedMonitoringWindow | None,
    reason_codes: list[str],
) -> JsonObject:
    ordered_reasons = [
        reason for reason in MONITORING_REASON_CODES if reason in set(reason_codes)
    ]
    if window is None:
        counts = {
            "candidate_count": 0,
            "fallback_count": 0,
            "late_observation_count": 0,
            "observation_count": 0,
            "quality_evaluated_count": 0,
            "quality_pass_count": 0,
        }
        fallback_reason_counts: JsonObject = {}
        window_reference: JsonObject | None = None
        metrics: JsonObject = {
            "fallback_rate": None,
            "feature_total_variation": None,
            "quality_pass_ratio": None,
        }
        version_checks = {
            "feature_schema_version_matches": False,
            "model_version_matches": False,
        }
    else:
        counts = {
            "candidate_count": window.candidate_count,
            "fallback_count": window.fallback_count,
            "late_observation_count": window.late_observation_count,
            "observation_count": window.observation_count,
            "quality_evaluated_count": window.quality_evaluated_count,
            "quality_pass_count": window.quality_pass_count,
        }
        fallback_reason_counts = deepcopy(dict(window.fallback_reason_counts))
        window_reference = {
            "fingerprint": window.fingerprint,
            "window_id": window.document["window_id"],
            "window_version": MONITORING_WINDOW_VERSION,
        }
        fallback_rate = (
            Fraction(window.fallback_count, window.observation_count)
            if window.observation_count
            else Fraction(0)
        )
        feature_drift = _feature_total_variation(
            window.feature_bucket_counts, policy.reference_bucket_counts
        )
        quality_ratio = (
            Fraction(window.quality_pass_count, window.quality_evaluated_count)
            if window.quality_evaluated_count
            else Fraction(0)
        )
        metrics = {
            "fallback_rate": _fraction_document(fallback_rate),
            "feature_total_variation": _fraction_document(feature_drift),
            "quality_pass_ratio": _fraction_document(quality_ratio),
        }
        version_checks = {
            "feature_schema_version_matches": window.feature_version_matches,
            "model_version_matches": window.model_version_matches,
        }
    disable = bool(ordered_reasons)
    projection: JsonObject = {
        "schema_version": MONITORING_REPORT_VERSION,
        "task_id": "TASK-P6-08",
        "result": "PASS",
        "policy_reference": {
            "artifact_id": policy.document["policy_id"],
            "document_version": MONITORING_POLICY_VERSION,
            "fingerprint": policy.fingerprint,
            "threshold_policy_version": MONITORING_THRESHOLD_VERSION,
        },
        "window_reference": window_reference,
        "counts": counts,
        "fallback_reason_counts": fallback_reason_counts,
        "metrics": metrics,
        "thresholds": {
            "fallback_rate_max": _fraction_document(policy.fallback_rate_max),
            "feature_total_variation_max": _fraction_document(
                policy.feature_total_variation_max
            ),
            "quality_pass_ratio_min": _fraction_document(policy.quality_pass_ratio_min),
        },
        "version_checks": version_checks,
        "monitoring_decision": {
            "automatic_actions": [],
            "external_side_effects": [],
            "human_review_required": disable,
            "reason_codes": ordered_reasons,
            "recommendation": "DEFAULT_DISABLE"
            if disable
            else "NO_DISABLE_RECOMMENDATION",
            "runtime_fallback_reason": "DRIFT_GATE_DISABLED" if disable else None,
            "standard_duration_fallback_required": disable,
        },
        "privacy_retention": deepcopy(policy.document["privacy_retention"]),
        "boundaries": {
            "data_plane": DATA_PLANE,
            "environment": ENVIRONMENT,
            "input_granularity": "AGGREGATE_WINDOW_ONLY",
            "monitor_persistence": "NONE",
            "planning_state_write": "NONE",
            "production_authorized": False,
            "production_slo_claimed": False,
            "raw_feature_or_label_included": False,
            "retraining_promotion_rollback": "NONE",
        },
        "issues": [],
    }
    projection["report_fingerprint"] = _fingerprint(projection)
    return projection


def monitor_duration_runtime(
    policy: LoadedMonitoringPolicy,
    aggregate_window: object,
) -> JsonObject:
    """Evaluate one immutable aggregate window and recommend default-disable."""

    trusted_policy = _validate_monitoring_policy(policy.document)

    try:
        window = _validate_monitoring_window(trusted_policy, aggregate_window)
    except P6RuntimeError as error:
        reason = (
            error.code
            if error.code
            in {
                "TELEMETRY_LINEAGE_INVALID",
                "TELEMETRY_PRIVACY_VIOLATION",
                "TELEMETRY_TAMPERED",
                "TELEMETRY_WINDOW_INVALID",
            }
            else "TELEMETRY_WINDOW_INVALID"
        )
        return _build_monitoring_report(trusted_policy, None, [reason])

    reasons: list[str] = []
    if window.observation_count < trusted_policy.minimum_observation_count:
        reasons.append("INSUFFICIENT_TELEMETRY")
    if window.observation_count != trusted_policy.expected_observation_count:
        reasons.append("WINDOW_COUNT_MISMATCH")
    if window.late_observation_count > trusted_policy.late_observation_max_count:
        reasons.append("LATE_TELEMETRY")
    if not window.model_version_matches:
        reasons.append("MODEL_VERSION_DRIFT")
    if not window.feature_version_matches:
        reasons.append("FEATURE_VERSION_DRIFT")

    if window.observation_count:
        fallback_rate = Fraction(window.fallback_count, window.observation_count)
        if fallback_rate > trusted_policy.fallback_rate_max:
            reasons.append("FALLBACK_RATE_BREACH")
        feature_drift = _feature_total_variation(
            window.feature_bucket_counts, trusted_policy.reference_bucket_counts
        )
        if feature_drift > trusted_policy.feature_total_variation_max:
            reasons.append("FEATURE_DISTRIBUTION_DRIFT")
    if window.quality_evaluated_count != window.observation_count:
        reasons.append("QUALITY_EVIDENCE_INCOMPLETE")
    if window.quality_evaluated_count:
        quality_ratio = Fraction(
            window.quality_pass_count, window.quality_evaluated_count
        )
        if quality_ratio < trusted_policy.quality_pass_ratio_min:
            reasons.append("QUALITY_DRIFT")
    return _build_monitoring_report(trusted_policy, window, reasons)
