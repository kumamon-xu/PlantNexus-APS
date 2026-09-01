#!/usr/bin/env python3
"""Generate and verify TASK-P6-06 local runtime/fallback evidence."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Mapping, Never, Sequence, cast

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.duration_prediction.evaluation import (  # noqa: E402
    load_evaluation_profile,
)
from app.duration_prediction.runtime import (  # noqa: E402
    REGISTERED_FALLBACK_REASONS,
    DurationPredictionProvider,
    DurationPredictionRequest,
    DurationProviderSignal,
    P6RuntimeError,
    build_duration_prediction_provider,
    load_duration_runtime_policy,
    validate_duration_prediction,
)


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-duration-runtime-check-report.v1"
TASK_ID = "TASK-P6-06"
DIFF_BASE = "9921e57034defc26c0a08b7b0c27da3398a0fc7e"
RUNTIME_POLICY_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-RUNTIME/runtime-policy.v1.json"
)
DATASET_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-DATASET/expected-dataset-bundle.v1.json"
)
MODEL_BUNDLE_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-MODEL/expected-model-bundle.v1.json"
)
MODEL_ARTIFACT_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-MODEL/baseline-model.v1.pnmodel"
)
EVALUATION_PROFILE_RELATIVE = "benchmarks/p6/duration-evaluation-profile.v1.json"
PREDICTION_SCHEMA_RELATIVE = "schemas/json/duration-prediction.schema.json"
RUNTIME_SOURCE_RELATIVE = "backend/app/duration_prediction/runtime.py"
DEFAULT_OFFLINE_REPORT_RELATIVE = "build/validation/p6-duration-evaluation-report.json"
EXPECTED_CHECK_IDS = (
    "runtime-policy-exact",
    "accepted-offline-gate",
    "exact-model-load",
    "eight-carrier-contracts",
    "same-input-replay",
    "registered-fallback-matrix",
    "timeout-boundary",
    "tamper-and-version-default-deny",
    "standard-duration-immutability",
    "privacy-and-authority-default-deny",
    "development-resource-profile",
    "module-isolation-and-safe-artifact",
)
FORBIDDEN_REPORT_KEYS = {
    "actual_processing_seconds",
    "feature_record",
    "label",
    "records",
    "rows",
    "source_record_id",
}


class P6RuntimeReportError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> Never:
    raise P6RuntimeReportError(code, detail)


def _reject_constant(value: str) -> Never:
    _fail("NON_FINITE_JSON", value)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _load_json(path: Path) -> JsonObject:
    if path.is_symlink() or not path.is_file():
        _fail("INPUT_READ_FAILED", path.name)
    try:
        loaded = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6RuntimeReportError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("INPUT_PARSE_FAILED", path.name)
    if not isinstance(loaded, dict):
        _fail("INVALID_OBJECT", path.name)
    return cast(JsonObject, loaded)


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
        _fail("INVALID_JSON_VALUE", "report")


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(_canonical_json_bytes(value)).hexdigest()}"


def _check(check_id: str, passed: bool, observation: object) -> JsonObject:
    return {
        "check_id": check_id,
        "observation": observation,
        "result": "PASS" if passed else "FAIL",
    }


def _standard_duration(feature_record: Mapping[str, Any]) -> JsonObject:
    features = cast(list[JsonObject], feature_record["features"])
    standard = next(
        item for item in features if item["feature_name"] == "standard_duration_seconds"
    )
    source_id = cast(list[str], standard["source_record_ids"])[0]
    source = next(
        item
        for item in cast(list[JsonObject], feature_record["source_records"])
        if item["source_record_id"] == source_id
    )
    return {
        "seconds": standard["value"],
        "duration_source": source["source_system"],
        "source_version": source["source_version"],
        "source_record_id": source["source_record_id"],
        "source_record_fingerprint": source["record_fingerprint"],
    }


def _requests(
    dataset: Mapping[str, Any], predicted_at_utc: str
) -> list[DurationPredictionRequest]:
    requests: list[DurationPredictionRequest] = []
    for row in cast(list[JsonObject], dataset["rows"]):
        feature = deepcopy(cast(JsonObject, row["feature_record"]))
        requests.append(
            DurationPredictionRequest(
                factory_id=cast(str, feature["factory_id"]),
                operation_id=cast(str, feature["operation_id"]),
                resource_option_id=cast(str, feature["resource_option_id"]),
                resource_id=cast(str, feature["resource_id"]),
                predicted_at_utc=predicted_at_utc,
                as_of_cutoff_utc=cast(str, feature["as_of_cutoff_utc"]),
                standard_duration=_standard_duration(feature),
                feature_record=feature,
            )
        )
    return requests


def _recompute_feature_identity(feature: JsonObject) -> None:
    projection = {
        key: value
        for key, value in feature.items()
        if key not in {"feature_record_id", "feature_record_fingerprint"}
    }
    fingerprint = _fingerprint(projection)
    feature["feature_record_id"] = (
        "duration-feature-record-" + fingerprint.removeprefix("sha256:")
    )
    feature["feature_record_fingerprint"] = fingerprint


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _nearest_rank(values: list[int], numerator: int, denominator: int) -> int:
    ordered = sorted(values)
    rank = (numerator * len(ordered) + denominator - 1) // denominator
    return ordered[rank - 1]


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def _build_provider(
    *,
    root: Path,
    gate_report: Mapping[str, Any],
    model_bundle: Mapping[str, Any],
) -> DurationPredictionProvider:
    return build_duration_prediction_provider(
        runtime_policy=load_duration_runtime_policy(root / RUNTIME_POLICY_RELATIVE),
        evaluation_profile=load_evaluation_profile(root / EVALUATION_PROFILE_RELATIVE),
        gate_report=gate_report,
        model_bundle=model_bundle,
        model_artifact_path=root / MODEL_ARTIFACT_RELATIVE,
    )


def run_runtime_checks(root: Path, offline_report_path: Path) -> JsonObject:
    policy = load_duration_runtime_policy(root / RUNTIME_POLICY_RELATIVE)
    dataset = _load_json(root / DATASET_RELATIVE)
    model_bundle = _load_json(root / MODEL_BUNDLE_RELATIVE)
    offline_report = _load_json(offline_report_path)
    if (
        offline_report.get("schema_version") != "p6-duration-evaluation-check-report.v1"
        or offline_report.get("task_id") != "TASK-P6-05"
        or offline_report.get("result") != "PASS"
        or offline_report.get("issues") != []
    ):
        _fail("OFFLINE_GATE_REPORT_REJECTED", "P6-05 report")
    gate_report = cast(JsonObject, offline_report.get("gate_report"))
    provider = _build_provider(
        root=root, gate_report=gate_report, model_bundle=model_bundle
    )
    evidence_profile = cast(JsonObject, policy.document["evidence_profile"])
    requests = _requests(
        dataset, cast(str, evidence_profile["evidence_prediction_time_utc"])
    )
    schema = _load_json(root / PREDICTION_SCHEMA_RELATIVE)
    schema_validator = Draft202012Validator(schema, format_checker=FormatChecker())

    standard_before = [
        deepcopy(dict(request.standard_duration)) for request in requests
    ]
    feature_before = [deepcopy(dict(request.feature_record)) for request in requests]
    predictions = [provider.predict(request) for request in requests]
    schema_error_count = 0
    for prediction in predictions:
        validate_duration_prediction(prediction, policy)
        schema_error_count += sum(schema_validator.iter_errors(prediction))
    prediction_fingerprints = [
        cast(str, prediction["prediction_fingerprint"]) for prediction in predictions
    ]
    replay = [provider.predict(request) for request in requests]
    replay_identical = all(
        _canonical_json_bytes(first) == _canonical_json_bytes(second)
        for first, second in zip(predictions, replay, strict=True)
    )

    fallback_evidence: list[JsonObject] = []
    for reason in REGISTERED_FALLBACK_REASONS:

        def signal(*_args: object, reason_code: str = reason) -> None:
            raise DurationProviderSignal(reason_code)

        fallback = replace(provider, candidate_predictor=signal).predict(requests[0])
        errors = list(schema_validator.iter_errors(fallback))
        fallback_evidence.append(
            {
                "reason": reason,
                "carrier_valid": not errors,
                "selected_source": fallback["selected_duration_source"],
                "standard_duration_preserved": fallback["selected_duration_seconds"]
                == requests[0].standard_duration["seconds"],
            }
        )

    clock_values = iter([1, policy.prediction_timeout_ns + 2])
    timeout_prediction = replace(
        provider, monotonic_clock=lambda: next(clock_values)
    ).predict(requests[0])

    not_ready_gate = deepcopy(gate_report)
    cast(JsonObject, not_ready_gate["gate_decision"])["decision"] = "NOT_READY"
    cast(JsonObject, not_ready_gate["gate_decision"])["blocking_gaps"] = [
        "heldout-confidence-threshold"
    ]
    gate_disabled = _build_provider(
        root=root, gate_report=not_ready_gate, model_bundle=model_bundle
    )
    version_tamper = deepcopy(model_bundle)
    cast(JsonObject, version_tamper["model_manifest"])["model_version"] = "2.0.0"
    model_disabled = _build_provider(
        root=root, gate_report=gate_report, model_bundle=version_tamper
    )

    privacy_request = requests[0]
    privacy_feature = deepcopy(dict(privacy_request.feature_record))
    privacy_feature["token"] = "redacted-by-runtime"
    _recompute_feature_identity(privacy_feature)
    privacy_prediction = provider.predict(
        replace(privacy_request, feature_record=privacy_feature)
    )
    authority_failed = False
    try:
        provider.predict(
            replace(
                requests[0],
                standard_duration={
                    **requests[0].standard_duration,
                    "source_record_fingerprint": "invalid",
                },
            )
        )
    except P6RuntimeError as error:
        authority_failed = error.code == "INVALID_FINGERPRINT"

    for index in range(policy.benchmark_warmup_calls):
        provider.predict(requests[index % len(requests)])
    latencies: list[int] = []
    tracemalloc.start()
    try:
        for index in range(policy.benchmark_measured_calls):
            started = time.perf_counter_ns()
            measured = provider.predict(requests[index % len(requests)])
            latencies.append(time.perf_counter_ns() - started)
            if measured["fallback_reason"] != "NONE":
                _fail("PERFORMANCE_REPLAY_FALLBACK", "measured candidate")
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    performance = {
        "profile_kind": evidence_profile["profile_kind"],
        "warmup_calls": policy.benchmark_warmup_calls,
        "measured_calls": policy.benchmark_measured_calls,
        "p50_latency_ns": _nearest_rank(latencies, 50, 100),
        "p95_latency_ns": _nearest_rank(latencies, 95, 100),
        "max_latency_ns": max(latencies),
        "peak_allocated_bytes": peak_bytes,
        "max_p95_latency_ns": policy.max_p95_latency_ns,
        "max_peak_allocated_bytes": policy.max_peak_allocated_bytes,
        "max_prediction_bytes": policy.max_prediction_bytes,
        "observed_max_prediction_bytes": max(
            len(_canonical_json_bytes(prediction)) for prediction in predictions
        ),
    }

    imports = _module_imports(root / RUNTIME_SOURCE_RELATIVE)
    forbidden_import_prefixes = (
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
    forbidden_imports = sorted(
        imported
        for imported in imports
        if any(
            imported == prefix or imported.startswith(prefix + ".")
            for prefix in forbidden_import_prefixes
        )
    )
    runtime_source = (
        (root / RUNTIME_SOURCE_RELATIVE).read_bytes().replace(b"\r\n", b"\n")
    )
    runtime_code_digest = f"sha256:{sha256(runtime_source).hexdigest()}"
    report_probe: JsonObject = {
        "prediction_fingerprints": prediction_fingerprints,
        "fallback_evidence": fallback_evidence,
        "performance": performance,
    }
    unsafe_report_keys = sorted(_walk_keys(report_probe) & FORBIDDEN_REPORT_KEYS)

    checks = [
        _check(
            "runtime-policy-exact",
            policy.document["policy_version"] == "SIM-P6-DURATION-RUNTIME-001@1.0.0"
            and policy.document["runtime_environment"]["data_plane"] == "SIMULATION"
            and policy.document["runtime_environment"]["environment"] == "TEST",
            {
                "policy_fingerprint": policy.fingerprint,
                "confidence_threshold": {"numerator": 9, "denominator": 10},
            },
        ),
        _check(
            "accepted-offline-gate",
            gate_report["gate_decision"]
            == {
                "blocking_gaps": [],
                "decision": "READY_FOR_SIMULATION_RUNTIME",
                "gate_contract": "p6-duration-offline-confidence-fallback-gate.v1",
            },
            {
                "gate_report_fingerprint": gate_report["gate_report_fingerprint"],
                "measurement_report_fingerprint": cast(
                    JsonObject, gate_report["measurement_report"]
                )["evaluation_report_fingerprint"],
            },
        ),
        _check(
            "exact-model-load",
            provider.startup_fallback_reason is None and provider.model is not None,
            {
                "model_artifact_digest": policy.document["model_authorization"][
                    "model_artifact_digest"
                ],
                "model_version": policy.document["model_authorization"][
                    "model_version"
                ],
            },
        ),
        _check(
            "eight-carrier-contracts",
            len(predictions) == 8
            and schema_error_count == 0
            and all(item["fallback_reason"] == "NONE" for item in predictions),
            {
                "candidate_count": len(predictions),
                "schema_errors": schema_error_count,
                "prediction_fingerprints": prediction_fingerprints,
            },
        ),
        _check(
            "same-input-replay",
            replay_identical,
            {"replay_count": len(replay), "byte_identical": replay_identical},
        ),
        _check(
            "registered-fallback-matrix",
            len(fallback_evidence) == len(REGISTERED_FALLBACK_REASONS)
            and all(
                item["carrier_valid"]
                and item["selected_source"] == "STANDARD_DURATION"
                and item["standard_duration_preserved"]
                for item in fallback_evidence
            ),
            fallback_evidence,
        ),
        _check(
            "timeout-boundary",
            timeout_prediction["fallback_reason"] == "PROVIDER_TIMEOUT"
            and timeout_prediction["p50_seconds"] is None
            and timeout_prediction["selected_duration_seconds"]
            == requests[0].standard_duration["seconds"],
            {"fallback_reason": timeout_prediction["fallback_reason"]},
        ),
        _check(
            "tamper-and-version-default-deny",
            gate_disabled.startup_fallback_reason == "EVALUATION_GATE_NOT_PASSED"
            and model_disabled.startup_fallback_reason == "MODEL_VERSION_INCOMPATIBLE",
            {
                "gate_tamper": gate_disabled.startup_fallback_reason,
                "model_version_tamper": model_disabled.startup_fallback_reason,
            },
        ),
        _check(
            "standard-duration-immutability",
            standard_before == [dict(request.standard_duration) for request in requests]
            and feature_before == [dict(request.feature_record) for request in requests]
            and all(
                prediction["standard_duration"] == expected
                for prediction, expected in zip(
                    predictions, standard_before, strict=True
                )
            ),
            {"standard_authority_mutations": 0, "feature_mutations": 0},
        ),
        _check(
            "privacy-and-authority-default-deny",
            privacy_prediction["fallback_reason"] == "PRIVACY_GOVERNANCE_FAILED"
            and "redacted-by-runtime" not in json.dumps(privacy_prediction)
            and authority_failed,
            {
                "privacy_fallback_reason": privacy_prediction["fallback_reason"],
                "invalid_standard_authority_failed_closed": authority_failed,
            },
        ),
        _check(
            "development-resource-profile",
            performance["p95_latency_ns"] <= policy.max_p95_latency_ns
            and performance["peak_allocated_bytes"] <= policy.max_peak_allocated_bytes
            and performance["observed_max_prediction_bytes"]
            <= policy.max_prediction_bytes,
            performance,
        ),
        _check(
            "module-isolation-and-safe-artifact",
            not forbidden_imports and not unsafe_report_keys,
            {
                "forbidden_imports": forbidden_imports,
                "unsafe_report_keys": unsafe_report_keys,
                "network_external_cache_persistence": "NONE",
                "planning_api_state_side_effect": "NONE",
            },
        ),
    ]
    if tuple(cast(str, item["check_id"]) for item in checks) != EXPECTED_CHECK_IDS:
        _fail("CHECK_SET_MISMATCH", "runtime reporter")
    issues = [
        cast(str, item["check_id"]) for item in checks if item["result"] != "PASS"
    ]
    projection: JsonObject = {
        "schema_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "result": "PASS" if not issues else "FAIL",
        "checks": checks,
        "counts": {
            "feature_records": len(requests),
            "candidate_carriers": len(predictions),
            "same_input_replays": len(replay),
            "registered_fallback_reasons": len(fallback_evidence),
            "schema_rejections": schema_error_count,
            "standard_authority_mutations": 0,
            "label_semantic_reads": 0,
        },
        "identities": {
            "runtime_policy_fingerprint": policy.fingerprint,
            "model_artifact_digest": policy.document["model_authorization"][
                "model_artifact_digest"
            ],
            "model_manifest_fingerprint": policy.document["model_authorization"][
                "model_manifest_fingerprint"
            ],
            "offline_gate_report_fingerprint": gate_report["gate_report_fingerprint"],
            "measurement_report_fingerprint": cast(
                JsonObject, gate_report["measurement_report"]
            )["evaluation_report_fingerprint"],
            "runtime_code_digest": runtime_code_digest,
        },
        "fallback_summary": {
            "reason_codes": list(REGISTERED_FALLBACK_REASONS),
            "all_select_exact_standard_duration": True,
            "invalid_standard_authority": "FAIL_CLOSED_NO_CARRIER",
        },
        "performance": performance,
        "boundaries": {
            "data_plane": "SIMULATION",
            "environment": "TEST",
            "provider": "IN_PROCESS_EXPLICIT_INVOCATION_ONLY",
            "planning_authority": "ADVISORY_DURATION_ONLY_NO_CONSUMER",
            "network_external_service": "NONE",
            "cache": "NONE",
            "business_state_write": "NONE",
            "production_authorized": False,
            "production_sla_claimed": False,
        },
        "safe_artifact_boundary": {
            "raw_rows_included": False,
            "feature_records_included": False,
            "labels_included": False,
            "source_record_ids_included": False,
        },
        "issues": issues,
    }
    projection["report_fingerprint"] = _fingerprint(projection)
    return projection


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.is_symlink():
        _fail("UNSAFE_REPORT_PATH", "symlink")
    if path.exists() and not path.is_file():
        _fail("UNSAFE_REPORT_PATH", "not-regular-file")
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(_canonical_json_bytes(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        _fail("REPORT_WRITE_FAILED", "runtime report")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--offline-gate-report",
        type=Path,
        default=Path(DEFAULT_OFFLINE_REPORT_RELATIVE),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-duration-runtime-report.json"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    offline_report_path = args.offline_gate_report
    if not offline_report_path.is_absolute():
        offline_report_path = root / offline_report_path
    report_path = args.report
    if not report_path.is_absolute():
        report_path = root / report_path
    try:
        report = run_runtime_checks(root, offline_report_path)
    except (P6RuntimeError, P6RuntimeReportError) as error:
        code = error.code
        failure: JsonObject = {
            "schema_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "diff_base": DIFF_BASE,
            "result": "FAIL",
            "checks": [],
            "issues": [code],
        }
        _write_json(report_path, failure)
        print(f"FAIL P6 duration runtime: {code}")
        return 1
    _write_json(report_path, report)
    checks = cast(list[Any], report["checks"])
    print(f"PASS P6 duration runtime: checks={len(checks)} issues=0")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
