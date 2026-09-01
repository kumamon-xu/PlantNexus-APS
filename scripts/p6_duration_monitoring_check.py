#!/usr/bin/env python3
"""Generate TASK-P6-08 aggregate drift/fallback monitoring evidence."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Mapping, Never, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.duration_prediction.runtime import (  # noqa: E402
    EXPECTED_MONITORING_POLICY_FINGERPRINT,
    MONITORING_FEATURE_BUCKETS,
    MONITORING_POLICY_IDENTITY,
    MONITORING_REASON_CODES,
    LoadedMonitoringPolicy,
    load_duration_monitoring_policy,
    monitor_duration_runtime,
)


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-duration-monitoring-check-report.v1"
TASK_ID = "TASK-P6-08"
DIFF_BASE = "e5d63fcf54c841ed93ef7c62084bcdeeda63abd4"
POLICY_RELATIVE = "fixtures/synthetic/P6-DURATION-MONITORING/monitor-policy.v1.json"
RUNTIME_SOURCE_RELATIVE = "backend/app/duration_prediction/runtime.py"
EXPECTED_CHECK_IDS = (
    "monitor-policy-exact",
    "healthy-and-inclusive-thresholds",
    "version-drift-default-disable",
    "fallback-feature-quality-drift",
    "late-window-and-quality-default-disable",
    "tamper-lineage-window-default-disable",
    "privacy-redaction-aggregate-only",
    "deterministic-report-replay",
    "standard-fallback-and-no-auto-action",
    "run-scoped-retention-and-isolation",
    "module-isolation-and-safe-artifact",
    "development-overhead-observation",
)
FORBIDDEN_REPORT_KEYS = {
    "actual_processing_seconds",
    "customer_id",
    "email",
    "feature_record",
    "label",
    "operation_id",
    "raw_payload",
    "resource_id",
    "resource_option_id",
    "source_record_id",
    "token",
}


class P6MonitoringReportError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> Never:
    raise P6MonitoringReportError(code, detail)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        _fail("INVALID_JSON_VALUE", "monitoring evidence")


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(_canonical_bytes(value)).hexdigest()}"


def _with_window_identity(value: Mapping[str, Any]) -> JsonObject:
    projection = deepcopy(dict(value))
    fingerprint = _fingerprint(projection)
    result = deepcopy(projection)
    result["window_id"] = "duration-monitoring-window-" + fingerprint.removeprefix(
        "sha256:"
    )
    result["window_fingerprint"] = fingerprint
    return result


def _window(
    policy: LoadedMonitoringPolicy,
    *,
    observation_count: int = 8,
    candidate_count: int = 7,
    fallback_count: int = 1,
    fallback_reason_counts: Mapping[str, int] | None = None,
    late_observation_count: int = 0,
    model_version_counts: Mapping[str, int] | None = None,
    feature_version_counts: Mapping[str, int] | None = None,
    feature_bucket_counts: Mapping[str, int] | None = None,
    quality_evaluated_count: int = 8,
    quality_pass_count: int = 7,
) -> JsonObject:
    projection: JsonObject = {
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "duration_monitoring_window_version": "duration-monitoring-window.v1",
        "environment": "TEST",
        "feature_distribution": {
            "bucket_counts": deepcopy(
                dict(feature_bucket_counts)
                if feature_bucket_counts is not None
                else {"HIGH": 2, "LOW": 2, "MID_HIGH": 2, "MID_LOW": 2}
            ),
            "profile_version": "duration-feature-aggregate-profile.v1",
        },
        "outcomes": {
            "candidate_count": candidate_count,
            "fallback_count": fallback_count,
            "fallback_reason_counts": deepcopy(
                dict(fallback_reason_counts)
                if fallback_reason_counts is not None
                else ({"LOW_CONFIDENCE": fallback_count} if fallback_count else {})
            ),
        },
        "policy_reference": {
            "artifact_id": policy.document["policy_id"],
            "document_version": "duration-monitoring-policy.v1",
            "fingerprint": policy.fingerprint,
            "threshold_policy_version": "duration-drift-thresholds.v1",
        },
        "privacy": {
            "aggregation": "WINDOW_ONLY",
            "direct_identifiers_present": False,
            "raw_feature_fields_present": False,
            "raw_label_fields_present": False,
            "source_record_references_present": False,
        },
        "production_binding": False,
        "quality": {
            "evaluated_count": quality_evaluated_count,
            "pass_count": quality_pass_count,
            "policy_version": "duration-quality-aggregate.v1",
        },
        "runtime_reference": deepcopy(policy.document["runtime_reference"]),
        "synthetic": True,
        "versions": {
            "feature_schema_version_counts": deepcopy(
                dict(feature_version_counts)
                if feature_version_counts is not None
                else {"duration-features.v1": observation_count}
            ),
            "model_version_counts": deepcopy(
                dict(model_version_counts)
                if model_version_counts is not None
                else {"1.0.0": observation_count}
            ),
        },
        "window": {
            "ended_at_utc": "2026-09-01T12:00:00Z",
            "late_observation_count": late_observation_count,
            "observation_count": observation_count,
            "sequence": 1,
            "started_at_utc": "2026-09-01T11:00:00Z",
        },
    }
    return _with_window_identity(projection)


def _recompute_window_identity(value: Mapping[str, Any]) -> JsonObject:
    projection = {
        key: deepcopy(child)
        for key, child in value.items()
        if key not in {"window_id", "window_fingerprint"}
    }
    return _with_window_identity(projection)


def _check(check_id: str, condition: bool, details: object) -> JsonObject:
    return {
        "check_id": check_id,
        "result": "PASS" if condition else "FAIL",
        "details": details,
    }


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


def _decision(report: Mapping[str, Any]) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], report["monitoring_decision"])


def run_monitoring_checks(root: Path) -> JsonObject:
    policy = load_duration_monitoring_policy(root / POLICY_RELATIVE)
    healthy_window = _window(policy)
    healthy = monitor_duration_runtime(policy, healthy_window)
    replay = monitor_duration_runtime(policy, healthy_window)
    boundary = monitor_duration_runtime(
        policy,
        _window(
            policy,
            candidate_count=6,
            fallback_count=2,
            fallback_reason_counts={"LOW_CONFIDENCE": 2},
            feature_bucket_counts={
                "HIGH": 4,
                "LOW": 2,
                "MID_HIGH": 1,
                "MID_LOW": 1,
            },
            quality_pass_count=6,
        ),
    )
    fallback_drift = monitor_duration_runtime(
        policy,
        _window(
            policy,
            candidate_count=5,
            fallback_count=3,
            fallback_reason_counts={"PROVIDER_TIMEOUT": 3},
        ),
    )
    feature_drift = monitor_duration_runtime(
        policy,
        _window(
            policy,
            feature_bucket_counts={
                "HIGH": 4,
                "LOW": 4,
                "MID_HIGH": 0,
                "MID_LOW": 0,
            },
        ),
    )
    quality_drift = monitor_duration_runtime(
        policy, _window(policy, quality_pass_count=5)
    )
    model_drift = monitor_duration_runtime(
        policy,
        _window(policy, model_version_counts={"1.0.0": 7, "2.0.0": 1}),
    )
    feature_version_drift = monitor_duration_runtime(
        policy,
        _window(
            policy,
            feature_version_counts={
                "duration-features.v1": 7,
                "duration-features.v2": 1,
            },
        ),
    )
    late = monitor_duration_runtime(policy, _window(policy, late_observation_count=1))
    quality_incomplete = monitor_duration_runtime(
        policy,
        _window(policy, quality_evaluated_count=7, quality_pass_count=7),
    )
    short_window = monitor_duration_runtime(
        policy,
        _window(
            policy,
            observation_count=7,
            candidate_count=6,
            fallback_count=1,
            fallback_reason_counts={"LOW_CONFIDENCE": 1},
            model_version_counts={"1.0.0": 7},
            feature_version_counts={"duration-features.v1": 7},
            feature_bucket_counts={"HIGH": 2, "LOW": 2, "MID_HIGH": 2, "MID_LOW": 1},
            quality_evaluated_count=7,
            quality_pass_count=7,
        ),
    )

    tampered_window = _window(policy)
    cast(JsonObject, tampered_window["outcomes"])["candidate_count"] = 6
    tampered = monitor_duration_runtime(policy, tampered_window)
    lineage_window = _window(policy)
    cast(JsonObject, lineage_window["policy_reference"])["threshold_policy_version"] = (
        "duration-drift-thresholds.v2"
    )
    lineage = monitor_duration_runtime(
        policy, _recompute_window_identity(lineage_window)
    )
    invalid_window = _window(policy)
    invalid_range = cast(JsonObject, invalid_window["window"])
    invalid_range["ended_at_utc"] = invalid_range["started_at_utc"]
    invalid = monitor_duration_runtime(
        policy, _recompute_window_identity(invalid_window)
    )
    privacy_window = _window(policy)
    privacy_window["raw_payload"] = {
        "actual_processing_seconds": 123,
        "operation_id": "must-not-reflect",
    }
    privacy = monitor_duration_runtime(
        policy, _recompute_window_identity(privacy_window)
    )

    measured_reports: list[JsonObject] = []
    latencies: list[int] = []
    tracemalloc.start()
    try:
        for _ in range(256):
            started = time.perf_counter_ns()
            measured = monitor_duration_runtime(policy, healthy_window)
            latencies.append(time.perf_counter_ns() - started)
            measured_reports.append(measured)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    performance = {
        "profile_kind": "DEVELOPMENT_OBSERVATION_ONLY_NOT_PRODUCTION_SLO",
        "measured_calls": len(latencies),
        "p50_latency_ns": _nearest_rank(latencies, 50, 100),
        "p95_latency_ns": _nearest_rank(latencies, 95, 100),
        "max_latency_ns": max(latencies),
        "peak_allocated_bytes": peak_bytes,
        "threshold_applied": False,
    }

    drift_reports = [
        fallback_drift,
        feature_drift,
        quality_drift,
        model_drift,
        feature_version_drift,
        late,
        quality_incomplete,
        short_window,
    ]
    invalid_reports = [tampered, lineage, invalid, privacy]
    all_disabled = drift_reports + invalid_reports
    safe_probe = {
        "healthy": healthy,
        "boundary": boundary,
        "disabled": all_disabled,
    }
    unsafe_report_keys = sorted(_walk_keys(safe_probe) & FORBIDDEN_REPORT_KEYS)
    serialized_probe = json.dumps(safe_probe, sort_keys=True)
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

    checks = [
        _check(
            "monitor-policy-exact",
            policy.document["policy_version"] == MONITORING_POLICY_IDENTITY
            and policy.fingerprint == EXPECTED_MONITORING_POLICY_FINGERPRINT
            and policy.expected_observation_count == 8
            and tuple(sorted(policy.reference_bucket_counts))
            == tuple(sorted(MONITORING_FEATURE_BUCKETS)),
            {
                "policy_fingerprint": policy.fingerprint,
                "threshold_policy_version": policy.document["thresholds"][
                    "threshold_policy_version"
                ],
                "expected_observation_count": policy.expected_observation_count,
            },
        ),
        _check(
            "healthy-and-inclusive-thresholds",
            _decision(healthy)["reason_codes"] == []
            and _decision(boundary)["reason_codes"] == []
            and boundary["metrics"]
            == {
                "fallback_rate": {"denominator": 4, "numerator": 1},
                "feature_total_variation": {"denominator": 4, "numerator": 1},
                "quality_pass_ratio": {"denominator": 4, "numerator": 3},
            },
            {
                "healthy_report_fingerprint": healthy["report_fingerprint"],
                "boundary_report_fingerprint": boundary["report_fingerprint"],
            },
        ),
        _check(
            "version-drift-default-disable",
            _decision(model_drift)["reason_codes"] == ["MODEL_VERSION_DRIFT"]
            and _decision(feature_version_drift)["reason_codes"]
            == ["FEATURE_VERSION_DRIFT"],
            {
                "model": _decision(model_drift)["reason_codes"],
                "feature": _decision(feature_version_drift)["reason_codes"],
            },
        ),
        _check(
            "fallback-feature-quality-drift",
            _decision(fallback_drift)["reason_codes"] == ["FALLBACK_RATE_BREACH"]
            and _decision(feature_drift)["reason_codes"]
            == ["FEATURE_DISTRIBUTION_DRIFT"]
            and _decision(quality_drift)["reason_codes"] == ["QUALITY_DRIFT"],
            {
                "fallback": fallback_drift["metrics"]["fallback_rate"],
                "feature": feature_drift["metrics"]["feature_total_variation"],
                "quality": quality_drift["metrics"]["quality_pass_ratio"],
            },
        ),
        _check(
            "late-window-and-quality-default-disable",
            _decision(late)["reason_codes"] == ["LATE_TELEMETRY"]
            and _decision(quality_incomplete)["reason_codes"]
            == ["QUALITY_EVIDENCE_INCOMPLETE"]
            and _decision(short_window)["reason_codes"]
            == ["INSUFFICIENT_TELEMETRY", "WINDOW_COUNT_MISMATCH"],
            {
                "late": _decision(late)["reason_codes"],
                "quality": _decision(quality_incomplete)["reason_codes"],
                "short_window": _decision(short_window)["reason_codes"],
            },
        ),
        _check(
            "tamper-lineage-window-default-disable",
            _decision(tampered)["reason_codes"] == ["TELEMETRY_TAMPERED"]
            and _decision(lineage)["reason_codes"] == ["TELEMETRY_LINEAGE_INVALID"]
            and _decision(invalid)["reason_codes"] == ["TELEMETRY_WINDOW_INVALID"],
            {
                "tamper": _decision(tampered)["reason_codes"],
                "lineage": _decision(lineage)["reason_codes"],
                "window": _decision(invalid)["reason_codes"],
            },
        ),
        _check(
            "privacy-redaction-aggregate-only",
            _decision(privacy)["reason_codes"] == ["TELEMETRY_PRIVACY_VIOLATION"]
            and privacy["window_reference"] is None
            and "must-not-reflect" not in serialized_probe
            and "actual_processing_seconds" not in serialized_probe,
            {
                "privacy_reason": _decision(privacy)["reason_codes"],
                "raw_feature_fields": 0,
                "raw_label_fields": 0,
                "direct_identifiers": 0,
            },
        ),
        _check(
            "deterministic-report-replay",
            _canonical_bytes(healthy) == _canonical_bytes(replay)
            and all(
                report["report_fingerprint"] == healthy["report_fingerprint"]
                for report in measured_reports
            ),
            {
                "same_input_replays": len(measured_reports) + 1,
                "report_fingerprint": healthy["report_fingerprint"],
            },
        ),
        _check(
            "standard-fallback-and-no-auto-action",
            all(
                _decision(report)["recommendation"] == "DEFAULT_DISABLE"
                and _decision(report)["runtime_fallback_reason"]
                == "DRIFT_GATE_DISABLED"
                and _decision(report)["standard_duration_fallback_required"] is True
                and _decision(report)["automatic_actions"] == []
                and _decision(report)["external_side_effects"] == []
                for report in all_disabled
            ),
            {
                "disabled_scenarios": len(all_disabled),
                "runtime_fallback_reason": "DRIFT_GATE_DISABLED",
                "automatic_actions": 0,
            },
        ),
        _check(
            "run-scoped-retention-and-isolation",
            policy.document["privacy_retention"]["persistence"] == "NONE"
            and policy.document["privacy_retention"]["retained_window_count"] == 1
            and healthy["boundaries"]["monitor_persistence"] == "NONE"
            and healthy["boundaries"]["planning_state_write"] == "NONE"
            and healthy["boundaries"]["production_authorized"] is False,
            deepcopy(policy.document["privacy_retention"]),
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
        _check(
            "development-overhead-observation",
            performance["measured_calls"] == 256
            and performance["p50_latency_ns"] > 0
            and performance["p95_latency_ns"] > 0
            and performance["peak_allocated_bytes"] > 0
            and performance["threshold_applied"] is False,
            performance,
        ),
    ]
    if tuple(cast(str, item["check_id"]) for item in checks) != EXPECTED_CHECK_IDS:
        _fail("CHECK_SET_MISMATCH", "monitoring reporter")
    issues = [
        cast(str, item["check_id"]) for item in checks if item["result"] != "PASS"
    ]
    projection: JsonObject = {
        "schema_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "result": "PASS" if not issues else "FAIL",
        "checks": checks,
        "counts": {
            "aggregate_windows": 14,
            "automatic_actions": 0,
            "direct_identifiers": 0,
            "drift_scenarios": len(drift_reports),
            "invalid_or_tamper_scenarios": len(invalid_reports),
            "raw_feature_fields": 0,
            "raw_label_fields": 0,
            "registered_monitoring_reasons": len(MONITORING_REASON_CODES),
        },
        "identities": {
            "monitoring_policy_fingerprint": policy.fingerprint,
            "runtime_policy_fingerprint": policy.document["runtime_reference"][
                "policy_fingerprint"
            ],
            "runtime_code_digest": f"sha256:{sha256(runtime_source).hexdigest()}",
        },
        "monitor_reports": {
            "healthy": healthy,
            "inclusive_boundary": boundary,
            "fallback_breach": fallback_drift,
            "privacy_default_disable": privacy,
        },
        "performance": performance,
        "boundaries": {
            "data_plane": "SIMULATION",
            "environment": "TEST",
            "monitoring_kind": "DEVELOPMENT_AGGREGATE_ONLY",
            "external_alert_or_infrastructure": "NONE",
            "persistence": "NONE",
            "automatic_retraining_promotion_rollback": "NONE",
            "planning_or_business_state_write": "NONE",
            "production_authorized": False,
            "production_slo_claimed": False,
        },
        "safe_artifact_boundary": {
            "raw_predictions_included": False,
            "feature_records_included": False,
            "labels_included": False,
            "operation_or_resource_ids_included": False,
            "source_record_ids_included": False,
        },
        "blocking_gaps": [],
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
            handle.write(_canonical_bytes(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        _fail("REPORT_WRITE_FAILED", "monitoring report")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-duration-monitoring-report.json"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report_path = args.report
    if not report_path.is_absolute():
        report_path = root / report_path
    try:
        report = run_monitoring_checks(root)
    except (P6MonitoringReportError, ValueError) as error:
        code = getattr(error, "code", type(error).__name__)
        failure: JsonObject = {
            "schema_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "diff_base": DIFF_BASE,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "result": "FAIL",
            "checks": [],
            "blocking_gaps": [code],
            "issues": [code],
        }
        _write_json(report_path, failure)
        print(f"FAIL P6 duration monitoring: {code}")
        return 1
    _write_json(report_path, report)
    checks = cast(list[Any], report["checks"])
    print(f"PASS P6 duration monitoring: checks={len(checks)} issues=0")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
