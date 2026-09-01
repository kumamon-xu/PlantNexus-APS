"""Fail-closed, in-process P6 duration prediction runtime.

The provider consumes one exact Simulation/Test model and the independently
accepted P6-05 offline Gate.  It returns the immutable P6-02 prediction
carrier, never mutates standard duration, and has no Planning, persistence,
network, cache, promotion, or Production authority.
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
OPEN_AUTHORITY_GAPS = ("OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015")
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
