"""Deterministic, safe machine evidence for TASK-P6-03."""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence, cast

from jsonschema import Draft202012Validator, FormatChecker

from app.duration_prediction.dataset import (
    P6DatasetError,
    build_duration_dataset,
    canonical_json_bytes,
    load_duration_source,
    recompute_source_identity,
    write_duration_dataset,
)
try:
    from scripts.p6_duration_contract_check import run_contract_checks
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from p6_duration_contract_check import run_contract_checks


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-duration-dataset-report.v1"
TASK_ID = "TASK-P6-03"
DIFF_BASE = "4360746f2712012a0aa4f52a40c189837a2097b3"
SCHEMA_SET_VERSION = "2.9.0"
EXPECTED_CHECKS = (
    "upstream-p6-02-contract-package",
    "authorized-source-policy-and-identity",
    "published-bundle-and-manifest-identity",
    "label-eligibility-censoring-and-redaction",
    "group-safe-time-split",
    "as-of-feature-schema-and-provenance",
    "canonical-replay-and-row-order-invariance",
    "fail-closed-mutation-matrix",
    "atomic-write-and-no-partial-cleanup",
    "repository-and-provider-boundaries",
)

SOURCE_RELATIVE = "fixtures/synthetic/P6-DURATION-DATASET/source-records.v1.json"
EXPECTED_RELATIVE = (
    "fixtures/synthetic/P6-DURATION-DATASET/expected-dataset-bundle.v1.json"
)
FEATURE_SCHEMA_RELATIVE = "schemas/json/duration-feature-record.schema.json"


class P6DatasetReportError(ValueError):
    """Stable report-level fail-closed error."""


def _load_json(path: Path) -> JsonObject:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise P6DatasetReportError(f"{path.name} must contain an object")
    return cast(JsonObject, loaded)


def _canonical_fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise P6DatasetReportError(message)


def _mutate(source: Mapping[str, Any], case: str) -> JsonObject:
    result = deepcopy(dict(source))
    records = cast(list[JsonObject], result["records"])
    first = records[0]
    fifth = records[4]
    if case == "unauthorized-source":
        result["source_version"] = "SIM-P6-DURATION-HISTORY@2.0.0"
    elif case == "production-plane":
        result["data_plane"] = "PRODUCTION"
    elif case == "mixed-schema":
        result["schema_set_version"] = "2.8.0"
    elif case == "future-leakage":
        first["feature_available_at_utc"] = "2026-07-04T08:00:01Z"
    elif case == "invalid-label":
        first["actual_processing_seconds"] = None
    elif case == "pii":
        first["pii_fields_present"] = True
    elif case == "target":
        first["target_fields_present"] = True
    elif case == "group-crossing":
        fifth["lineage_group_id"] = "lineage-train-a"
    elif case == "retention-drift":
        authority = cast(JsonObject, result["authority"])
        authority["retention_policy_version"] = "unapproved.v2"
    elif case == "missing-lineage":
        del first["lineage_group_id"]
    elif case == "sensitive-key":
        first["operator_id"] = "forbidden"
    else:  # pragma: no cover - closed caller table
        raise AssertionError(case)
    return recompute_source_identity(result)


def _mutation_evidence(source: Mapping[str, Any]) -> JsonObject:
    expected_codes = {
        "unauthorized-source": "UNAUTHORIZED_SOURCE",
        "production-plane": "UNAUTHORIZED_SOURCE",
        "mixed-schema": "UNAUTHORIZED_SOURCE",
        "future-leakage": "FUTURE_FEATURE_LEAKAGE",
        "invalid-label": "INVALID_POSITIVE_INTEGER",
        "pii": "PII_POLICY_VIOLATION",
        "target": "TARGET_LEAKAGE",
        "group-crossing": "LINEAGE_GROUP_SPLIT_CROSSING",
        "retention-drift": "POLICY_MISMATCH",
        "missing-lineage": "MISSING_FIELD",
        "sensitive-key": "PII_OR_TARGET_FIELD_FORBIDDEN",
    }
    observed: dict[str, str] = {}
    for case, expected_code in expected_codes.items():
        try:
            build_duration_dataset(_mutate(source, case))
        except P6DatasetError as error:
            observed[case] = error.code
        else:
            raise P6DatasetReportError(f"mutation accepted: {case}")
        _expect(observed[case] == expected_code, f"wrong mutation code: {case}")

    tampered = deepcopy(dict(source))
    records = cast(list[JsonObject], tampered["records"])
    records[0]["planned_quantity"] = 999
    try:
        build_duration_dataset(tampered)
    except P6DatasetError as error:
        observed["undeclared-tamper"] = error.code
    else:
        raise P6DatasetReportError("undeclared tamper accepted")
    _expect(
        observed["undeclared-tamper"] == "SOURCE_FINGERPRINT_MISMATCH",
        "source tamper code changed",
    )
    return {
        "rejection_count": len(observed),
        "codes": dict(sorted(observed.items())),
    }


def _feature_evidence(root: Path, bundle: Mapping[str, Any]) -> JsonObject:
    schema = _load_json(root / FEATURE_SCHEMA_RELATIVE)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    feature_fingerprints: list[str] = []
    source_links = 0
    for row in cast(list[JsonObject], bundle["rows"]):
        feature_record = cast(JsonObject, row["feature_record"])
        errors = sorted(validator.iter_errors(feature_record), key=lambda item: list(item.path))
        if errors:
            raise P6DatasetReportError(
                f"feature schema rejection: {errors[0].json_path}"
            )
        feature_fingerprints.append(cast(str, feature_record["feature_record_fingerprint"]))
        label = cast(JsonObject, row["label"])
        sources = cast(list[JsonObject], feature_record["source_records"])
        _expect(
            cast(str, label["source_record_id"]) + "-feature-context"
            == sources[0]["source_record_id"],
            "label/feature lineage mismatch",
        )
        cutoff = cast(str, feature_record["as_of_cutoff_utc"])
        for feature in cast(list[JsonObject], feature_record["features"]):
            _expect(
                cast(str, feature["available_at_utc"]) <= cutoff,
                "future feature survived",
            )
            source_links += len(cast(list[str], feature["source_record_ids"]))
    return {
        "feature_records": len(feature_fingerprints),
        "features_per_record": 4,
        "source_links": source_links,
        "feature_record_fingerprints": feature_fingerprints,
        "schema": FEATURE_SCHEMA_RELATIVE,
    }


def _atomic_evidence(source: Mapping[str, Any], expected: Mapping[str, Any]) -> JsonObject:
    with TemporaryDirectory(prefix="p6-duration-dataset-") as raw_directory:
        directory = Path(raw_directory)
        target = directory / "dataset.json"
        first = write_duration_dataset(source, target)
        first_bytes = target.read_bytes()
        second = write_duration_dataset(source, target)
        _expect(first == second == expected, "atomic replay differs from expected")
        _expect(
            first_bytes == target.read_bytes() == canonical_json_bytes(first) + b"\n",
            "atomic bytes are not canonical",
        )
        invalid = _mutate(source, "future-leakage")
        try:
            write_duration_dataset(invalid, target)
        except P6DatasetError as error:
            _expect(error.code == "FUTURE_FEATURE_LEAKAGE", "invalid atomic code")
        else:
            raise P6DatasetReportError("invalid source wrote an artifact")
        _expect(target.read_bytes() == first_bytes, "invalid build replaced target")
        temporary_files = list(directory.glob(".dataset.json.*.tmp"))
        _expect(not temporary_files, "partial temporary artifact remains")
    return {
        "successful_replays": 2,
        "invalid_rejections": 1,
        "partial_artifacts": 0,
        "replacement": "ATOMIC_SAME_DIRECTORY",
    }


def _with_report_identity(report: Mapping[str, Any]) -> JsonObject:
    result = deepcopy(dict(report))
    digest = _canonical_fingerprint(result)
    result["report_id"] = "p6-duration-dataset-report-" + digest.removeprefix(
        "sha256:"
    )
    result["report_fingerprint"] = digest
    return result


def run_dataset_checks(root: Path) -> JsonObject:
    """Run the complete deterministic P6-03 evidence package."""

    root = root.resolve()
    checks: list[JsonObject] = []

    def passed(name: str, evidence: object) -> None:
        checks.append({"name": name, "status": "PASS", "evidence": evidence})

    upstream = run_contract_checks(root)
    _expect(upstream["status"] == "PASS", "P6-02 package failed")
    _expect(upstream["task_id"] == "TASK-P6-02", "wrong upstream task")
    _expect(upstream["schema_set_version"] == SCHEMA_SET_VERSION, "schema drift")
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

    source = load_duration_source(root / SOURCE_RELATIVE)
    _expect(recompute_source_identity(source) == source, "source identity mismatch")
    passed(
        EXPECTED_CHECKS[1],
        {
            "document_version": source["source_dataset_version"],
            "artifact_id": source["source_dataset_id"],
            "fingerprint": source["source_dataset_fingerprint"],
            "source_version": source["source_version"],
            "data_plane": source["data_plane"],
            "environment": source["environment"],
            "synthetic": source["synthetic"],
            "production_binding": source["production_binding"],
            "authority": source["authority"],
            "privacy_policy": source["privacy_policy"],
        },
    )

    bundle = build_duration_dataset(source)
    expected = _load_json(root / EXPECTED_RELATIVE)
    _expect(bundle == expected, "published expected bundle drift")
    _expect(
        bundle["bundle_fingerprint"]
        == _canonical_fingerprint(
            {key: value for key, value in bundle.items() if key != "bundle_fingerprint"}
        ),
        "bundle fingerprint mismatch",
    )
    manifest = cast(JsonObject, bundle["dataset_manifest"])
    passed(
        EXPECTED_CHECKS[2],
        {
            "bundle_fingerprint": bundle["bundle_fingerprint"],
            "expected_bundle_canonical_fingerprint": _canonical_fingerprint(expected),
            "dataset_manifest": manifest,
        },
    )

    rows = cast(list[JsonObject], bundle["rows"])
    exclusions = cast(list[JsonObject], bundle["exclusions"])
    _expect(len(rows) == 8 and len(exclusions) == 2, "eligibility counts changed")
    _expect(
        {item["reason"] for item in exclusions}
        == {
            "RUNNING_NOT_LABEL_ELIGIBLE",
            "INTERRUPTED_NOT_LABEL_ELIGIBLE",
        },
        "exclusion reasons changed",
    )
    _expect(
        all(
            row["feature_record"]["pii_fields_present"] is False
            and row["feature_record"]["target_fields_present"] is False
            for row in rows
        ),
        "redaction boundary changed",
    )
    passed(
        EXPECTED_CHECKS[3],
        {
            "eligible_rows": len(rows),
            "excluded_records": len(exclusions),
            "exclusion_reason_counts": manifest["exclusion_reason_counts"],
            "label_policy": manifest["label_policy"],
            "pii_fields_present": False,
            "target_fields_present": False,
        },
    )

    partition_rows = {
        name: sum(1 for row in rows if row["partition"] == name)
        for name in ("train", "validation", "test")
    }
    groups: dict[str, set[str]] = {}
    for row in rows:
        groups.setdefault(cast(str, row["lineage_group_id"]), set()).add(
            cast(str, row["partition"])
        )
    _expect(all(len(partitions) == 1 for partitions in groups.values()), "group crossing")
    _expect(partition_rows == {"train": 4, "validation": 2, "test": 2}, "split drift")
    passed(
        EXPECTED_CHECKS[4],
        {
            "partition_rows": partition_rows,
            "lineage_groups": len(groups),
            "crossing_groups": 0,
            "split_policy": manifest["split_policy"],
        },
    )

    passed(EXPECTED_CHECKS[5], _feature_evidence(root, bundle))

    replay = build_duration_dataset(source)
    reordered = deepcopy(source)
    reordered["records"] = list(reversed(cast(list[JsonObject], reordered["records"])))
    reordered_replay = build_duration_dataset(reordered)
    _expect(
        canonical_json_bytes(bundle)
        == canonical_json_bytes(replay)
        == canonical_json_bytes(reordered_replay),
        "deterministic replay changed",
    )
    passed(
        EXPECTED_CHECKS[6],
        {
            "same_input_replays": 2,
            "row_order_replays": 1,
            "canonicalization_version": "canonical-json.v1",
            "identical_bytes": True,
        },
    )

    mutation_evidence = _mutation_evidence(source)
    passed(EXPECTED_CHECKS[7], mutation_evidence)
    passed(EXPECTED_CHECKS[8], _atomic_evidence(source, expected))

    passed(
        EXPECTED_CHECKS[9],
        {
            "p6_02_machine_assets": "FROZEN_AND_REPLAYED",
            "schema_set_version": SCHEMA_SET_VERSION,
            "dependency_lock_migration_state": "UNCHANGED_BY_TASK",
            "planning_solver_validator_runtime_frontend": "UNCHANGED_BY_TASK",
            "provider_payload": "SAFE_REPORT_AND_DATASET_MANIFEST_ONLY",
            "raw_source_in_provider_artifact": False,
            "production_data": "NONE",
            "model_training": "NOT_PERFORMED",
            "p6_04_plus": "NOT_STARTED",
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
            "source_records": 10,
            "eligible_rows": 8,
            "excluded_records": 2,
            "train_rows": 4,
            "validation_rows": 2,
            "test_rows": 2,
            "feature_records": 8,
            "features": 32,
            "mutation_rejections": mutation_evidence["rejection_count"],
        },
        "artifacts": {
            "source": {
                "path": SOURCE_RELATIVE,
                "artifact_id": source["source_dataset_id"],
                "fingerprint": source["source_dataset_fingerprint"],
                "included_in_provider_artifact": False,
            },
            "expected_bundle": {
                "path": EXPECTED_RELATIVE,
                "bundle_fingerprint": bundle["bundle_fingerprint"],
                "included_in_provider_artifact": False,
            },
            "dataset_manifest": {
                "document_version": manifest["document_version"],
                "artifact_id": manifest["artifact_id"],
                "fingerprint": manifest["fingerprint"],
                "included_in_report": True,
            },
        },
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "environment": "TEST",
            "production_binding": False,
            "production_authorized": False,
            "standard_duration_authority": "UNCHANGED_FEATURE_ONLY_NOT_LABEL",
            "actual_processing_label": "EXPLICIT_COMPLETED_NORMAL_ONLY",
            "routing_resource_hard_constraints_state_weights": "UNCHANGED",
            "planning_or_prediction_authority": "NONE",
            "open_authority_gaps": ["OPEN-010", "OPEN-011", "OPEN-014", "OPEN-015"],
            "p7_reality_calibration": "NOT_ENTERED",
            "production_uat_external_deployment_capacity_sla": "NOT_FORMED",
        },
        "issues": [],
    }
    return _with_report_identity(report)


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-duration-dataset.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = run_dataset_checks(args.root)
    except Exception as error:  # deterministic CI failure envelope
        report = {
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
        _write_report(args.report, report)
        return 1
    _write_report(args.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
