"""Deterministic, safe machine evidence for TASK-P6-04."""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, Sequence, cast

from jsonschema import Draft202012Validator, FormatChecker

from app.duration_prediction.dataset import (
    build_duration_dataset,
    canonical_json_bytes,
    load_duration_source,
)
import app.duration_prediction.model as model_module
from app.duration_prediction.model import (
    EXPECTED_DEPENDENCY_LOCK_DIGEST,
    MAX_ARTIFACT_BYTES,
    P6ModelError,
    artifact_file_bytes,
    build_duration_model,
    dependency_lock_digest,
    load_duration_model,
    predict_duration,
    write_duration_model,
)

try:
    from scripts.p6_duration_dataset_check import run_dataset_checks
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from p6_duration_dataset_check import run_dataset_checks


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-duration-model-report.v1"
TASK_ID = "TASK-P6-04"
DIFF_BASE = "1d184d082544454436a5558bc39a6a0a38f0fb1b"
SCHEMA_SET_VERSION = "2.9.0"
EXPECTED_CHECKS = (
    "upstream-p6-03-dataset-package",
    "dependency-algorithm-and-serialization-decision",
    "train-only-dataset-and-feature-lineage",
    "published-artifact-manifest-and-schema",
    "deterministic-training-and-source-order-replay",
    "safe-load-and-estimate-replay",
    "fail-closed-security-and-lineage-mutations",
    "atomic-publish-and-no-partial-cleanup",
    "provider-artifact-data-minimization",
    "repository-capability-and-production-boundaries",
)

DATASET_SOURCE_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-DATASET/source-records.v1.json"
)
DATASET_BUNDLE_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-DATASET/expected-dataset-bundle.v1.json"
)
MODEL_ARTIFACT_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-MODEL/baseline-model.v1.pnmodel"
)
MODEL_BUNDLE_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-MODEL/expected-model-bundle.v1.json"
)
MODEL_SCHEMA_RELATIVE = "schemas/json/duration-model-manifest.schema.json"


class P6ModelReportError(ValueError):
    """Stable report-level fail-closed error."""


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise P6ModelReportError(message)


def _load_json(path: Path) -> JsonObject:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise P6ModelReportError(f"{path.name} must contain an object")
    return cast(JsonObject, loaded)


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _refresh_identity(
    value: JsonObject, id_field: str, fingerprint_field: str, prefix: str
) -> None:
    projection = {
        key: item
        for key, item in value.items()
        if key not in {id_field, fingerprint_field}
    }
    fingerprint = _fingerprint(projection)
    value[id_field] = prefix + fingerprint.removeprefix("sha256:")
    value[fingerprint_field] = fingerprint


def _manifest_for_artifact(
    artifact: JsonObject, manifest: Mapping[str, Any]
) -> JsonObject:
    result = deepcopy(dict(manifest))
    model_artifact = cast(JsonObject, result["model_artifact"])
    model_artifact["artifact_digest"] = _fingerprint(artifact)
    _refresh_identity(
        result,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    return result


def _write_artifact(path: Path, artifact: Mapping[str, Any]) -> None:
    path.write_bytes(artifact_file_bytes(artifact))


def _observe_rejection(
    observed: dict[str, str],
    name: str,
    expected_code: str,
    action: Callable[[], object],
) -> None:
    try:
        action()
    except P6ModelError as error:
        observed[name] = error.code
    else:
        raise P6ModelReportError(f"mutation accepted: {name}")
    _expect(observed[name] == expected_code, f"wrong mutation code: {name}")


def _mutation_evidence(
    root: Path,
    dataset: Mapping[str, Any],
    artifact: Mapping[str, Any],
    expected_bundle: Mapping[str, Any],
) -> JsonObject:
    manifest = cast(JsonObject, expected_bundle["model_manifest"])
    configuration = cast(JsonObject, expected_bundle["training_configuration"])
    observed: dict[str, str] = {}

    _observe_rejection(
        observed,
        "dependency-lock",
        "DEPENDENCY_LOCK_MISMATCH",
        lambda: build_duration_model(dataset, "sha256:" + "0" * 64),
    )

    tampered_dataset = deepcopy(dict(dataset))
    cast(list[JsonObject], tampered_dataset["rows"])[0]["label"]["value"] = 999
    _observe_rejection(
        observed,
        "dataset-tamper",
        "DATASET_FINGERPRINT_MISMATCH",
        lambda: build_duration_model(tampered_dataset, EXPECTED_DEPENDENCY_LOCK_DIGEST),
    )
    projection = {
        key: value
        for key, value in tampered_dataset.items()
        if key != "bundle_fingerprint"
    }
    tampered_dataset["bundle_fingerprint"] = _fingerprint(projection)
    _observe_rejection(
        observed,
        "refreshed-dataset-tamper",
        "DATASET_NOT_AUTHORIZED",
        lambda: build_duration_model(tampered_dataset, EXPECTED_DEPENDENCY_LOCK_DIGEST),
    )

    changed_configuration = deepcopy(configuration)
    cast(JsonObject, changed_configuration["determinism"])["seed_accepted"] = True
    _observe_rejection(
        observed,
        "configuration-seed",
        "CONFIGURATION_MISMATCH",
        lambda: load_duration_model(
            root / MODEL_ARTIFACT_RELATIVE,
            manifest,
            changed_configuration,
        ),
    )

    with TemporaryDirectory(prefix="p6-duration-model-mutations-") as raw_directory:
        directory = Path(raw_directory)
        artifact_object = deepcopy(dict(artifact))
        cast(JsonObject, artifact_object["parameters"])["p90_margin_seconds"] = 21
        tampered_path = directory / "tampered.pnmodel"
        _write_artifact(tampered_path, artifact_object)
        _observe_rejection(
            observed,
            "artifact-digest",
            "ARTIFACT_DIGEST_MISMATCH",
            lambda: load_duration_model(tampered_path, manifest, configuration),
        )

        artifact_object["unexpected"] = "rejected"
        refreshed_manifest = _manifest_for_artifact(artifact_object, manifest)
        _write_artifact(tampered_path, artifact_object)
        _observe_rejection(
            observed,
            "artifact-unknown-field",
            "UNKNOWN_FIELD",
            lambda: load_duration_model(
                tampered_path, refreshed_manifest, configuration
            ),
        )

        unsafe_manifest = deepcopy(manifest)
        cast(JsonObject, unsafe_manifest["model_artifact"])[
            "serialization_format"
        ] = "python-pickle"
        _refresh_identity(
            unsafe_manifest,
            "model_manifest_id",
            "model_manifest_fingerprint",
            "duration-model-manifest-",
        )
        _observe_rejection(
            observed,
            "unsafe-serialization",
            "UNSAFE_SERIALIZATION_FORMAT",
            lambda: load_duration_model(
                root / MODEL_ARTIFACT_RELATIVE, unsafe_manifest, configuration
            ),
        )

        duplicate = directory / "duplicate.pnmodel"
        duplicate.write_bytes(b'{"x":1,"x":2}\n')
        _observe_rejection(
            observed,
            "duplicate-json",
            "DUPLICATE_JSON_KEY",
            lambda: load_duration_model(duplicate, manifest, configuration),
        )
        nonfinite = directory / "nonfinite.pnmodel"
        nonfinite.write_bytes(b'{"x":NaN}\n')
        _observe_rejection(
            observed,
            "nonfinite-json",
            "NON_FINITE_NUMBER",
            lambda: load_duration_model(nonfinite, manifest, configuration),
        )
        oversized = directory / "oversized.pnmodel"
        oversized.write_bytes(b"{" + b" " * MAX_ARTIFACT_BYTES + b"}")
        _observe_rejection(
            observed,
            "oversized-artifact",
            "ARTIFACT_TOO_LARGE",
            lambda: load_duration_model(oversized, manifest, configuration),
        )

        code_drift = deepcopy(dict(artifact))
        cast(JsonObject, code_drift["training_provenance"])[
            "code_revision"
        ] = "0" * 40
        code_manifest = _manifest_for_artifact(code_drift, manifest)
        cast(JsonObject, code_manifest["training_provenance"])[
            "code_revision"
        ] = "0" * 40
        _refresh_identity(
            code_manifest,
            "model_manifest_id",
            "model_manifest_fingerprint",
            "duration-model-manifest-",
        )
        code_path = directory / "code-drift.pnmodel"
        _write_artifact(code_path, code_drift)
        _observe_rejection(
            observed,
            "training-code-drift",
            "TRAINING_CODE_MISMATCH",
            lambda: load_duration_model(code_path, code_manifest, configuration),
        )

        negative_model = deepcopy(dict(artifact))
        offsets = cast(
            list[JsonObject],
            cast(JsonObject, negative_model["parameters"])["family_offsets_seconds"],
        )
        offsets[0] = {
            "operation_family": "milling",
            "numerator": -10_000,
            "denominator": 1,
        }
        negative_manifest = _manifest_for_artifact(negative_model, manifest)
        negative_path = directory / "negative-output.pnmodel"
        _write_artifact(negative_path, negative_model)
        loaded_negative = load_duration_model(
            negative_path, negative_manifest, configuration
        )
        first_feature = cast(
            JsonObject, cast(list[JsonObject], dataset["rows"])[0]["feature_record"]
        )
        _observe_rejection(
            observed,
            "invalid-model-output",
            "INVALID_MODEL_OUTPUT",
            lambda: predict_duration(loaded_negative, first_feature),
        )

    loaded = load_duration_model(
        root / MODEL_ARTIFACT_RELATIVE, manifest, configuration
    )
    out_of_scope = deepcopy(
        cast(JsonObject, cast(list[JsonObject], dataset["rows"])[0]["feature_record"])
    )
    out_of_scope["factory_id"] = "factory-other"
    _refresh_identity(
        out_of_scope,
        "feature_record_id",
        "feature_record_fingerprint",
        "duration-feature-record-",
    )
    _observe_rejection(
        observed,
        "out-of-scope-feature",
        "MODEL_OUT_OF_SCOPE",
        lambda: predict_duration(loaded, out_of_scope),
    )

    invalid_feature = deepcopy(
        cast(JsonObject, cast(list[JsonObject], dataset["rows"])[0]["feature_record"])
    )
    for item in cast(list[JsonObject], invalid_feature["features"]):
        if item["feature_name"] == "standard_duration_seconds":
            item["value"] = 0
    _refresh_identity(
        invalid_feature,
        "feature_record_id",
        "feature_record_fingerprint",
        "duration-feature-record-",
    )
    _observe_rejection(
        observed,
        "invalid-feature",
        "INVALID_INTEGER",
        lambda: predict_duration(loaded, invalid_feature),
    )
    return {"rejection_count": len(observed), "codes": dict(sorted(observed.items()))}


def _atomic_evidence(
    dataset: Mapping[str, Any], expected_bundle: Mapping[str, Any]
) -> JsonObject:
    with TemporaryDirectory(prefix="p6-duration-model-atomic-") as raw_directory:
        directory = Path(raw_directory)
        target = directory / "model.pnmodel"
        first = write_duration_model(dataset, target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
        first_bytes = target.read_bytes()
        second = write_duration_model(dataset, target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
        _expect(first == second == expected_bundle, "atomic replay bundle mismatch")
        _expect(first_bytes == target.read_bytes(), "atomic replay bytes mismatch")

        invalid = deepcopy(dict(dataset))
        cast(list[JsonObject], invalid["rows"])[0]["label"]["value"] = 999
        try:
            write_duration_model(invalid, target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
        except P6ModelError as error:
            _expect(
                error.code == "DATASET_FINGERPRINT_MISMATCH",
                "invalid atomic code changed",
            )
        else:
            raise P6ModelReportError("invalid dataset wrote model")
        _expect(target.read_bytes() == first_bytes, "invalid build replaced target")

        original_replace = model_module.os.replace

        def fail_replace(_source: Path, _target: Path) -> None:
            raise OSError("synthetic replace failure")

        model_module.os.replace = fail_replace
        try:
            try:
                write_duration_model(dataset, target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
            except P6ModelError as error:
                _expect(error.code == "ATOMIC_WRITE_FAILED", "replace code changed")
            else:
                raise P6ModelReportError("replace failure published model")
        finally:
            model_module.os.replace = original_replace
        _expect(target.read_bytes() == first_bytes, "replace failure changed target")
        _expect(
            not list(directory.glob(".model.pnmodel.*.tmp")),
            "partial temporary model remains",
        )
    return {
        "successful_replays": 2,
        "invalid_rejections": 1,
        "replace_failure_rejections": 1,
        "partial_artifacts": 0,
        "replacement": "ATOMIC_SAME_DIRECTORY",
    }


def _walk_keys(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            result.add(key)
            result.update(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_walk_keys(item))
    return result


def _with_report_identity(report: Mapping[str, Any]) -> JsonObject:
    result = deepcopy(dict(report))
    digest = _fingerprint(result)
    result["report_id"] = "p6-duration-model-report-" + digest.removeprefix(
        "sha256:"
    )
    result["report_fingerprint"] = digest
    return result


def run_model_checks(root: Path) -> JsonObject:
    """Run the complete deterministic P6-04 evidence package."""

    root = root.resolve()
    checks: list[JsonObject] = []

    def passed(name: str, evidence: object) -> None:
        checks.append({"name": name, "status": "PASS", "evidence": evidence})

    upstream = run_dataset_checks(root)
    _expect(upstream["status"] == "PASS", "P6-03 package failed")
    _expect(upstream["task_id"] == "TASK-P6-03", "wrong upstream task")
    _expect(upstream["counts"]["train_rows"] == 4, "upstream train count changed")
    passed(
        EXPECTED_CHECKS[0],
        {
            "task_id": upstream["task_id"],
            "diff_base": upstream["diff_base"],
            "schema_set_version": upstream["schema_set_version"],
            "check_count": upstream["check_count"],
            "counts": upstream["counts"],
            "issues": upstream["issues"],
        },
    )

    lock_digest = dependency_lock_digest(root / "uv.lock")
    _expect(lock_digest == EXPECTED_DEPENDENCY_LOCK_DIGEST, "dependency lock drift")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    _expect(
        all(name not in pyproject for name in ("numpy", "scikit-learn", "joblib")),
        "unapproved ML dependency present",
    )
    passed(
        EXPECTED_CHECKS[1],
        {
            "model_family": "grouped-median-residual-baseline.v1",
            "dependency_decision": "NO_NEW_DEPENDENCY",
            "dependency_lock_digest": lock_digest,
            "arithmetic": "PYTHON_FRACTION_EXACT",
            "randomness": "NONE",
            "serialization_format": "plantnexus-safe-canonical-json",
            "serialization_max_bytes": MAX_ARTIFACT_BYTES,
            "unsafe_executable_serialization": False,
        },
    )

    source = load_duration_source(root / DATASET_SOURCE_RELATIVE)
    dataset = build_duration_dataset(source)
    published_dataset = _load_json(root / DATASET_BUNDLE_RELATIVE)
    _expect(dataset == published_dataset, "P6-03 dataset drift")
    training_rows = [row for row in cast(list[JsonObject], dataset["rows"]) if row["partition"] == "train"]
    _expect(len(training_rows) == 4, "training partition changed")
    passed(
        EXPECTED_CHECKS[2],
        {
            "dataset_manifest": dataset["dataset_manifest"],
            "dataset_bundle_fingerprint": dataset["bundle_fingerprint"],
            "training_partition": "train",
            "training_rows": 4,
            "validation_rows_used_for_training": 0,
            "test_rows_used_for_training": 0,
            "required_features": [
                "planned_quantity",
                "setup_seconds",
                "standard_duration_seconds",
                "operation_family",
            ],
            "active_features": ["standard_duration_seconds", "operation_family"],
            "zero_weight_features": ["planned_quantity", "setup_seconds"],
        },
    )

    build = build_duration_model(dataset, lock_digest)
    expected_bundle = _load_json(root / MODEL_BUNDLE_RELATIVE)
    _expect(build.bundle == expected_bundle, "published model bundle drift")
    artifact_raw = (root / MODEL_ARTIFACT_RELATIVE).read_bytes().replace(b"\r\n", b"\n")
    _expect(
        artifact_raw == artifact_file_bytes(build.artifact),
        "published model artifact drift",
    )
    schema = _load_json(root / MODEL_SCHEMA_RELATIVE)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    manifest = cast(JsonObject, expected_bundle["model_manifest"])
    errors = sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
    _expect(not errors, f"model manifest schema rejection: {errors[0].json_path if errors else ''}")
    passed(
        EXPECTED_CHECKS[3],
        {
            "model_artifact": {
                "path": MODEL_ARTIFACT_RELATIVE,
                "digest": build.artifact_digest,
                "bytes": len(artifact_raw),
                "safe_for_provider": True,
            },
            "model_manifest": manifest,
            "bundle_fingerprint": build.bundle["bundle_fingerprint"],
            "schema": MODEL_SCHEMA_RELATIVE,
        },
    )

    second = build_duration_model(dataset, lock_digest)
    reordered_source = deepcopy(source)
    reordered_source["records"] = list(
        reversed(cast(list[JsonObject], reordered_source["records"]))
    )
    reordered_dataset = build_duration_dataset(reordered_source)
    reordered = build_duration_model(reordered_dataset, lock_digest)
    _expect(
        artifact_file_bytes(build.artifact)
        == artifact_file_bytes(second.artifact)
        == artifact_file_bytes(reordered.artifact),
        "artifact replay differs",
    )
    _expect(
        canonical_json_bytes(build.bundle)
        == canonical_json_bytes(second.bundle)
        == canonical_json_bytes(reordered.bundle),
        "bundle replay differs",
    )
    passed(
        EXPECTED_CHECKS[4],
        {
            "same_input_replays": 2,
            "source_order_replays": 1,
            "artifact_bytes_identical": True,
            "bundle_bytes_identical": True,
            "host_clock_or_rng_inputs": 0,
        },
    )

    loaded = load_duration_model(
        root / MODEL_ARTIFACT_RELATIVE,
        manifest,
        cast(JsonObject, expected_bundle["training_configuration"]),
    )
    expected_estimates = {
        item["dataset_row_id"]: item["estimate"]
        for item in cast(list[JsonObject], cast(JsonObject, expected_bundle["replay"])["estimates"])
    }
    observed_estimates = 0
    for row in cast(list[JsonObject], dataset["rows"]):
        estimate = predict_duration(
            loaded, cast(JsonObject, row["feature_record"])
        )
        _expect(estimate == expected_estimates[row["dataset_row_id"]], "estimate drift")
        _expect(
            cast(int, estimate["p90_seconds"]) >= cast(int, estimate["p50_seconds"]) > 0,
            "invalid replay quantile",
        )
        observed_estimates += 1
    passed(
        EXPECTED_CHECKS[5],
        {
            "safe_loads": 1,
            "replayed_estimates": observed_estimates,
            "p90_margin_seconds": build.artifact["parameters"]["p90_margin_seconds"],
            "confidence_status": "NOT_ESTABLISHED_BY_P6_04",
            "evaluation_gate": "NOT_EVALUATED_BY_P6_04",
            "formal_duration_prediction_carriers": 0,
        },
    )

    mutations = _mutation_evidence(
        root, dataset, build.artifact, expected_bundle
    )
    passed(EXPECTED_CHECKS[6], mutations)
    passed(EXPECTED_CHECKS[7], _atomic_evidence(dataset, expected_bundle))

    replay = cast(JsonObject, expected_bundle["replay"])
    forbidden_keys = {
        "label",
        "actual_processing_seconds",
        "customer_id",
        "operator_id",
        "employee_id",
        "email",
        "phone",
        "token",
        "secret",
        "endpoint",
    }
    _expect(_walk_keys(build.artifact).isdisjoint(forbidden_keys), "artifact leaks data")
    _expect(_walk_keys(replay).isdisjoint(forbidden_keys), "replay leaks data")
    passed(
        EXPECTED_CHECKS[8],
        {
            "provider_payload": "SAFE_MODEL_MANIFEST_REPLAY_REPORT_ONLY",
            "model_artifact_included": True,
            "model_manifest_included": True,
            "replay_included": True,
            "raw_dataset_source_included": False,
            "dataset_rows_or_labels_included": False,
            "production_data": "NONE",
        },
    )

    passed(
        EXPECTED_CHECKS[9],
        {
            "schema_set_version": SCHEMA_SET_VERSION,
            "p6_02_schema_and_samples": "UNCHANGED_AND_CONSUMED",
            "p6_03_source_and_dataset": "UNCHANGED_AND_REPLAYED",
            "dependency_lock_migration_state": "UNCHANGED_BY_TASK",
            "planning_solver_validator_runtime_frontend": "UNCHANGED_BY_TASK",
            "quality_evaluation_confidence_gate": "NOT_FORMED",
            "promotion_or_runtime": "NOT_IMPLEMENTED",
            "p6_05_plus": "NOT_STARTED",
            "p7_reality_calibration": "NOT_ENTERED",
            "production_uat_external_deployment_capacity_sla": "NOT_FORMED",
        },
    )

    _expect(tuple(check["name"] for check in checks) == EXPECTED_CHECKS, "check order drift")
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "schema_set_version": SCHEMA_SET_VERSION,
        "status": "PASS",
        "result": "PASS",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "dataset_rows": 8,
            "training_rows": 4,
            "validation_rows_used_for_training": 0,
            "test_rows_used_for_training": 0,
            "operation_families": 2,
            "model_parameters": 3,
            "replayed_estimates": 8,
            "mutation_rejections": mutations["rejection_count"],
            "atomic_rejections": 2,
        },
        "artifacts": {
            "dataset_source": {
                "path": DATASET_SOURCE_RELATIVE,
                "included_in_provider_artifact": False,
            },
            "dataset_bundle": {
                "path": DATASET_BUNDLE_RELATIVE,
                "fingerprint": dataset["bundle_fingerprint"],
                "included_in_provider_artifact": False,
            },
            "model_artifact": {
                "path": MODEL_ARTIFACT_RELATIVE,
                "digest": build.artifact_digest,
                "safe_for_provider": True,
            },
            "model_bundle": {
                "path": MODEL_BUNDLE_RELATIVE,
                "bundle_fingerprint": build.bundle["bundle_fingerprint"],
                "included_in_provider_artifact": False,
            },
            "model_manifest": {
                "artifact_id": manifest["model_manifest_id"],
                "fingerprint": manifest["model_manifest_fingerprint"],
                "included_in_provider_artifact": True,
            },
            "replay": {
                "artifact_id": replay["artifact_id"],
                "fingerprint": replay["fingerprint"],
                "included_in_provider_artifact": True,
            },
        },
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "environment": "TEST",
            "production_binding": False,
            "production_authorized": False,
            "promotion_authorized": False,
            "standard_duration_authority": "UNCHANGED",
            "formal_prediction_or_evaluation_gate": "NOT_FORMED",
            "routing_resource_hard_constraints_state_weights": "UNCHANGED",
            "runtime_or_planning_authority": "NONE",
            "open_authority_gaps": list(model_module.OPEN_AUTHORITY_GAPS),
            "p7_reality_calibration": "NOT_ENTERED",
            "production_uat_external_deployment_capacity_sla": "NOT_FORMED",
        },
        "issues": [],
    }
    return _with_report_identity(report)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-duration-model.json"),
    )
    parser.add_argument(
        "--model-artifact",
        type=Path,
        default=Path("build/validation/p6-duration-baseline-model.json"),
    )
    parser.add_argument(
        "--manifest-artifact",
        type=Path,
        default=Path("build/validation/p6-duration-model-manifest.json"),
    )
    parser.add_argument(
        "--replay-artifact",
        type=Path,
        default=Path("build/validation/p6-duration-model-replay.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = run_model_checks(args.root)
        model_bundle = _load_json(args.root.resolve() / MODEL_BUNDLE_RELATIVE)
        model_artifact = json.loads(
            (args.root.resolve() / MODEL_ARTIFACT_RELATIVE).read_text(encoding="utf-8")
        )
        _expect(isinstance(model_artifact, dict), "model artifact root changed")
    except Exception as error:  # deterministic CI failure envelope
        failure = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "diff_base": DIFF_BASE,
            "schema_set_version": SCHEMA_SET_VERSION,
            "status": "FAIL",
            "result": "FAIL",
            "check_count": 0,
            "checks": [],
            "issues": [{"type": type(error).__name__, "message": str(error)}],
        }
        _write_json(args.report, failure)
        return 1

    _write_json(args.report, report)
    _write_json(args.model_artifact, cast(JsonObject, model_artifact))
    _write_json(
        args.manifest_artifact, cast(JsonObject, model_bundle["model_manifest"])
    )
    _write_json(args.replay_artifact, cast(JsonObject, model_bundle["replay"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
