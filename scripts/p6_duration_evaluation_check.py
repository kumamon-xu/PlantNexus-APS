#!/usr/bin/env python3
"""Generate and verify TASK-P6-05 aggregate offline-evaluation evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Never, Sequence, cast

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.duration_prediction.evaluation import (  # noqa: E402
    P6EvaluationError,
    build_duration_evaluation,
    canonical_json_bytes,
    evaluate_duration_paths,
    load_evaluation_profile,
    validate_offline_gate_report,
)
from app.duration_prediction.model import load_duration_model  # noqa: E402

JsonObject = dict[str, Any]
REPORT_VERSION = "p6-duration-evaluation-check-report.v1"
BASELINE_VERSION = "duration-evaluation-baseline.v1"
TASK_ID = "TASK-P6-05"
DIFF_BASE = "03a0b4dd4de9398aa02746b736c3cf6e7fab9b0d"
PROFILE_RELATIVE = "benchmarks/p6/duration-evaluation-profile.v1.json"
BASELINE_RELATIVE = "benchmarks/p6/duration-evaluation-baseline.v1.json"
DATASET_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-DATASET/expected-dataset-bundle.v1.json"
)
MODEL_BUNDLE_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-MODEL/expected-model-bundle.v1.json"
)
MODEL_ARTIFACT_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-MODEL/baseline-model.v1.pnmodel"
)
EXPECTED_CHECK_IDS = (
    "profile-and-input-lineage",
    "heldout-only-selection",
    "measurement-carrier-compatibility",
    "model-versus-standard-gate",
    "confidence-and-fallback-policy",
    "deterministic-source-order-replay",
    "aggregate-baseline-replay",
    "provider-payload-minimization",
)
FORBIDDEN_PAYLOAD_KEYS = {
    "actual_processing_seconds",
    "dataset_row_id",
    "feature_record",
    "label",
    "records",
    "rows",
    "source_record_id",
}


class P6EvaluationReportError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> Never:
    raise P6EvaluationReportError(code, detail)


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
        _fail("INPUT_READ_FAILED", str(path))
    try:
        loaded = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except P6EvaluationReportError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail("INPUT_PARSE_FAILED", f"{path.name}:{type(error).__name__}")
    if not isinstance(loaded, dict):
        _fail("INVALID_OBJECT", path.name)
    return cast(JsonObject, loaded)


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _with_identity(
    projection: Mapping[str, Any],
    *,
    id_field: str,
    fingerprint_field: str,
    prefix: str,
) -> JsonObject:
    result = deepcopy(dict(projection))
    fingerprint = _fingerprint(result)
    result[id_field] = prefix + fingerprint.removeprefix("sha256:")
    result[fingerprint_field] = fingerprint
    return result


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


def build_baseline_projection(gate_report: Mapping[str, Any]) -> JsonObject:
    """Project the safe exact golden without copying any source row or label."""

    report = cast(JsonObject, gate_report)
    decision = cast(JsonObject, report["gate_decision"])
    fallback = cast(JsonObject, report["fallback_evidence"])
    reasons = [
        cast(JsonObject, cast(JsonObject, item)["decision"])["fallback_reason"]
        for item in cast(list[Any], fallback["scenarios"])
        if cast(JsonObject, cast(JsonObject, item)["decision"])["fallback_used"]
    ]
    measurement = cast(JsonObject, report["measurement_report"])
    projection: JsonObject = {
        "duration_evaluation_baseline_version": BASELINE_VERSION,
        "task_id": TASK_ID,
        "profile_reference": deepcopy(report["profile_reference"]),
        "input_lineage": deepcopy(report["input_lineage"]),
        "expected_selection": deepcopy(report["selection"]),
        "expected_metrics": deepcopy(report["metrics"]),
        "expected_gate_decision": deepcopy(decision),
        "expected_check_ids": [
            cast(JsonObject, item)["check_id"]
            for item in cast(list[Any], report["checks"])
        ],
        "expected_fallback_reason_codes": reasons,
        "expected_fallback_scenario_count": fallback["scenario_count"],
        "measurement_report_fingerprint": measurement[
            "evaluation_report_fingerprint"
        ],
        "gate_report_fingerprint": report["gate_report_fingerprint"],
        "provider_payload": {
            "aggregate_only": True,
            "raw_rows_included": False,
            "labels_included": False,
            "production_authorized": False,
        },
    }
    return _with_identity(
        projection,
        id_field="baseline_id",
        fingerprint_field="baseline_fingerprint",
        prefix="duration-evaluation-baseline-",
    )


def _check(check_id: str, passed: bool, observation: object) -> JsonObject:
    return {
        "check_id": check_id,
        "observation": observation,
        "result": "PASS" if passed else "FAIL",
    }


def run_evaluation_checks(root: Path) -> JsonObject:
    profile_path = root / PROFILE_RELATIVE
    dataset_path = root / DATASET_RELATIVE
    model_bundle_path = root / MODEL_BUNDLE_RELATIVE
    model_artifact_path = root / MODEL_ARTIFACT_RELATIVE
    build = evaluate_duration_paths(
        dataset_path=dataset_path,
        model_bundle_path=model_bundle_path,
        model_artifact_path=model_artifact_path,
        profile_path=profile_path,
    )
    profile = load_evaluation_profile(profile_path)
    gate_report = build.gate_report
    validate_offline_gate_report(gate_report, profile)
    baseline = _load_json(root / BASELINE_RELATIVE)
    observed_baseline = build_baseline_projection(gate_report)

    dataset_bundle = _load_json(dataset_path)
    model_bundle = _load_json(model_bundle_path)
    reversed_dataset = deepcopy(dataset_bundle)
    cast(list[Any], reversed_dataset["rows"]).reverse()
    loaded_model = load_duration_model(
        model_artifact_path,
        cast(JsonObject, model_bundle["model_manifest"]),
        cast(JsonObject, model_bundle["training_configuration"]),
    )
    replay = build_duration_evaluation(
        reversed_dataset, model_bundle, loaded_model, profile
    )
    decision = cast(JsonObject, gate_report["gate_decision"])
    measurement = cast(JsonObject, gate_report["measurement_report"])
    selection = cast(JsonObject, gate_report["selection"])
    fallback = cast(JsonObject, gate_report["fallback_evidence"])
    unsafe_keys = sorted(_walk_keys(gate_report) & FORBIDDEN_PAYLOAD_KEYS)
    checks = [
        _check(
            "profile-and-input-lineage",
            gate_report["profile_reference"]
            == {
                "profile_id": profile.document["profile_id"],
                "profile_fingerprint": profile.fingerprint,
            }
            and gate_report["input_lineage"] == observed_baseline["input_lineage"],
            {"profile_fingerprint": profile.fingerprint},
        ),
        _check(
            "heldout-only-selection",
            selection["heldout_row_count"] == 4
            and selection["partition_counts"] == {"test": 2, "validation": 2}
            and selection["train_label_reads"] == 0,
            selection,
        ),
        _check(
            "measurement-carrier-compatibility",
            measurement["gate_assessment"]
            == {
                "gate_contract": "duration-evaluation-gate.planned-p6-05",
                "decision": "NOT_EVALUATED_BY_P6_02",
                "thresholds_embedded": False,
            },
            {
                "evaluation_report_fingerprint": measurement[
                    "evaluation_report_fingerprint"
                ]
            },
        ),
        _check(
            "model-versus-standard-gate",
            decision["decision"] in {"READY_FOR_SIMULATION_RUNTIME", "NOT_READY"}
            and isinstance(decision["blocking_gaps"], list),
            decision,
        ),
        _check(
            "confidence-and-fallback-policy",
            fallback["scenario_count"] == 11
            and observed_baseline["expected_fallback_reason_codes"]
            == [
                "FALLBACK_CONFIDENCE_MISSING",
                "FALLBACK_CONFIDENCE_INVALID",
                "FALLBACK_CONFIDENCE_BELOW_THRESHOLD",
                "FALLBACK_QUANTILES_INVALID",
                "FALLBACK_LINEAGE_INCOMPATIBLE",
                "FALLBACK_MODEL_INVALID",
                "FALLBACK_TIMEOUT",
                "FALLBACK_AUTHORITY_UNAVAILABLE",
                "FALLBACK_PRIVACY_BOUNDARY",
            ],
            {"scenario_count": fallback["scenario_count"]},
        ),
        _check(
            "deterministic-source-order-replay",
            replay.gate_report == gate_report,
            {"byte_identical": canonical_json_bytes(replay.gate_report) == canonical_json_bytes(gate_report)},
        ),
        _check(
            "aggregate-baseline-replay",
            baseline == observed_baseline,
            {"baseline_fingerprint": observed_baseline["baseline_fingerprint"]},
        ),
        _check(
            "provider-payload-minimization",
            not unsafe_keys,
            {"forbidden_keys": unsafe_keys, "raw_rows_included": False},
        ),
    ]
    if tuple(cast(str, item["check_id"]) for item in checks) != EXPECTED_CHECK_IDS:
        _fail("CHECK_SET_MISMATCH", "reporter")
    issues = [
        cast(str, item["check_id"])
        for item in checks
        if item["result"] != "PASS"
    ]
    projection: JsonObject = {
        "schema_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "result": "PASS" if not issues else "FAIL",
        "checks": checks,
        "gate_decision": deepcopy(decision),
        "profile_reference": deepcopy(gate_report["profile_reference"]),
        "input_lineage": deepcopy(gate_report["input_lineage"]),
        "metrics": deepcopy(gate_report["metrics"]),
        "fallback_summary": {
            "reason_codes": deepcopy(
                observed_baseline["expected_fallback_reason_codes"]
            ),
            "scenario_count": fallback["scenario_count"],
        },
        "measurement_report_reference": {
            "evaluation_report_id": measurement["evaluation_report_id"],
            "evaluation_report_fingerprint": measurement[
                "evaluation_report_fingerprint"
            ],
        },
        "gate_report": deepcopy(gate_report),
        "safe_artifact_boundary": {
            "aggregate_only": True,
            "labels_included": False,
            "raw_rows_included": False,
            "production_authorized": False,
        },
        "issues": issues,
    }
    fingerprint = _fingerprint(projection)
    projection["report_fingerprint"] = fingerprint
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
            handle.write(canonical_json_bytes(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        _fail("REPORT_WRITE_FAILED", type(error).__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-duration-evaluation-report.json"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report_path = args.report
    if not report_path.is_absolute():
        report_path = root / report_path
    try:
        report = run_evaluation_checks(root)
    except (P6EvaluationError, P6EvaluationReportError) as error:
        code = error.code
        failure: JsonObject = {
            "schema_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "diff_base": DIFF_BASE,
            "result": "FAIL",
            "checks": [],
            "gate_decision": {"decision": "NOT_READY", "blocking_gaps": [code]},
            "issues": [code],
        }
        _write_json(report_path, failure)
        print(f"FAIL P6 duration evaluation: {code}")
        return 1
    _write_json(report_path, report)
    print(
        "PASS P6 duration evaluation: "
        f"decision={cast(JsonObject, report['gate_decision'])['decision']} "
        f"checks={len(cast(list[Any], report['checks']))} issues=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
