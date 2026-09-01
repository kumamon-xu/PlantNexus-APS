"""Contract, mutation, property, and cleanup tests for TASK-P6-03."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st
from jsonschema import Draft202012Validator, FormatChecker
import pytest

import app.duration_prediction.dataset as dataset_module
from app.duration_prediction.dataset import (
    P6DatasetError,
    build_duration_dataset,
    canonical_json_bytes,
    load_duration_source,
    recompute_source_identity,
    source_dataset_fingerprint,
    write_duration_dataset,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = (
    ROOT / "fixtures" / "synthetic" / "P6-DURATION-DATASET" / "source-records.v1.json"
)
EXPECTED_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-DATASET"
    / "expected-dataset-bundle.v1.json"
)
FEATURE_SCHEMA_PATH = ROOT / "schemas" / "json" / "duration-feature-record.schema.json"


def _source() -> dict[str, Any]:
    return load_duration_source(SOURCE_PATH)


def _expected() -> dict[str, Any]:
    loaded = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _mutated_source(case: str) -> dict[str, Any]:
    source = _source()
    records = source["records"]
    assert isinstance(records, list)
    first = records[0]
    fifth = records[4]
    assert isinstance(first, dict)
    assert isinstance(fifth, dict)
    if case == "unauthorized-plane":
        source["data_plane"] = "PRODUCTION"
    elif case == "mixed-schema-version":
        source["schema_set_version"] = "2.8.0"
    elif case == "future-feature":
        first["feature_available_at_utc"] = "2026-07-04T08:01:00Z"
    elif case == "invalid-normal-label":
        first["actual_processing_seconds"] = None
    elif case == "pii-flag":
        first["pii_fields_present"] = True
    elif case == "target-flag":
        first["target_fields_present"] = True
    elif case == "group-crossing":
        fifth["lineage_group_id"] = "lineage-train-a"
    elif case == "label-policy-drift":
        policy = source["label_policy"]
        assert isinstance(policy, dict)
        policy["derive_from_start_end"] = True
    elif case == "missing-lineage":
        del first["lineage_group_id"]
    elif case == "sensitive-key":
        first["operator_id"] = "forbidden"
    elif case == "unknown-completion":
        first["status"] = "CANCELLED"
    else:  # pragma: no cover - keeps the case table closed
        raise AssertionError(case)
    return recompute_source_identity(source)


def test_builds_published_bundle_and_existing_feature_contract() -> None:
    source = _source()
    source_before = deepcopy(source)
    bundle = build_duration_dataset(source)
    assert source == source_before
    assert recompute_source_identity(source) == source
    assert bundle == _expected()
    assert bundle["duration_dataset_bundle_version"] == "duration-dataset-bundle.v1"
    assert bundle["schema_set_version"] == "2.9.0"

    manifest = bundle["dataset_manifest"]
    assert manifest["document_version"] == "duration-dataset-manifest.v1"
    assert manifest["dataset_version"] == "SIM-P6-FEATURE-DATASET-001@1.0.0"
    assert manifest["counts"] == {
        "source_records": 10,
        "eligible_rows": 8,
        "excluded_records": 2,
    }
    assert [item["row_count"] for item in manifest["partitions"]] == [4, 2, 2]
    assert manifest["production_binding"] is False
    assert manifest["governance_boundary"]["production_authorized"] is False

    schema = json.loads(FEATURE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in bundle["rows"]:
        assert list(validator.iter_errors(row["feature_record"])) == []
        assert (
            row["label"]["source_record_id"] + "-feature-context"
            == row["feature_record"]["source_records"][0]["source_record_id"]
        )
        assert row["feature_record"]["target_fields_present"] is False
        assert row["feature_record"]["pii_fields_present"] is False


@settings(max_examples=16, deadline=None)
@given(st.permutations(tuple(range(10))))
def test_input_record_order_is_non_semantic(order: tuple[int, ...]) -> None:
    source = _source()
    baseline = build_duration_dataset(source)
    records = source["records"]
    assert isinstance(records, list)
    source["records"] = [records[index] for index in order]
    replay = build_duration_dataset(source)
    assert canonical_json_bytes(replay) == canonical_json_bytes(baseline)


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("unauthorized-plane", "UNAUTHORIZED_SOURCE"),
        ("mixed-schema-version", "UNAUTHORIZED_SOURCE"),
        ("future-feature", "FUTURE_FEATURE_LEAKAGE"),
        ("invalid-normal-label", "INVALID_POSITIVE_INTEGER"),
        ("pii-flag", "PII_POLICY_VIOLATION"),
        ("target-flag", "TARGET_LEAKAGE"),
        ("group-crossing", "LINEAGE_GROUP_SPLIT_CROSSING"),
        ("label-policy-drift", "POLICY_MISMATCH"),
        ("missing-lineage", "MISSING_FIELD"),
        ("sensitive-key", "PII_OR_TARGET_FIELD_FORBIDDEN"),
        ("unknown-completion", "UNKNOWN_COMPLETION_SEMANTICS"),
    ],
)
def test_semantic_mutations_fail_closed(case: str, error_code: str) -> None:
    with pytest.raises(P6DatasetError, match=f"^{error_code}:"):
        build_duration_dataset(_mutated_source(case))


def test_source_and_record_tampering_are_independently_rejected() -> None:
    source = _source()
    records = source["records"]
    assert isinstance(records, list) and isinstance(records[0], dict)
    records[0]["planned_quantity"] = 99
    with pytest.raises(P6DatasetError, match="^SOURCE_FINGERPRINT_MISMATCH:"):
        build_duration_dataset(source)

    source = _source()
    records = source["records"]
    assert isinstance(records, list) and isinstance(records[0], dict)
    records[0]["source_record_fingerprint"] = "sha256:" + "f" * 64
    digest = source_dataset_fingerprint(source)
    source["source_dataset_fingerprint"] = digest
    source["source_dataset_id"] = "duration-dataset-source-" + digest.removeprefix(
        "sha256:"
    )
    with pytest.raises(P6DatasetError, match="^RECORD_FINGERPRINT_MISMATCH:"):
        build_duration_dataset(source)


def test_exclusions_are_stable_and_do_not_become_labels() -> None:
    bundle = build_duration_dataset(_source())
    assert bundle["exclusions"] == sorted(
        bundle["exclusions"], key=lambda item: item["source_record_id"]
    )
    assert {item["reason"] for item in bundle["exclusions"]} == {
        "RUNNING_NOT_LABEL_ELIGIBLE",
        "INTERRUPTED_NOT_LABEL_ELIGIBLE",
    }
    output_ids = {row["label"]["source_record_id"] for row in bundle["rows"]}
    excluded_ids = {item["source_record_id"] for item in bundle["exclusions"]}
    assert output_ids.isdisjoint(excluded_ids)


def test_atomic_writer_is_exact_and_cleans_temporary_files(tmp_path: Path) -> None:
    target = tmp_path / "dataset.json"
    first = write_duration_dataset(_source(), target)
    first_bytes = target.read_bytes()
    second = write_duration_dataset(_source(), target)
    assert first == second == _expected()
    assert first_bytes == target.read_bytes() == canonical_json_bytes(first) + b"\n"
    assert list(tmp_path.glob(".dataset.json.*.tmp")) == []


def test_invalid_input_leaves_existing_target_and_parent_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "existing.json"
    target.write_bytes(b"sentinel\n")
    invalid = _mutated_source("future-feature")
    with pytest.raises(P6DatasetError, match="^FUTURE_FEATURE_LEAKAGE:"):
        write_duration_dataset(invalid, target)
    assert target.read_bytes() == b"sentinel\n"
    assert list(tmp_path.glob(".existing.json.*.tmp")) == []

    missing_parent_target = tmp_path / "not-created" / "dataset.json"
    with pytest.raises(P6DatasetError, match="^FUTURE_FEATURE_LEAKAGE:"):
        write_duration_dataset(invalid, missing_parent_target)
    assert not missing_parent_target.parent.exists()


def test_atomic_replace_failure_preserves_target_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "dataset.json"
    target.write_bytes(b"previous\n")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(dataset_module.os, "replace", fail_replace)
    with pytest.raises(P6DatasetError, match="^ATOMIC_WRITE_FAILED: OSError$"):
        write_duration_dataset(_source(), target)
    assert target.read_bytes() == b"previous\n"
    assert list(tmp_path.glob(".dataset.json.*.tmp")) == []


def test_loader_rejects_duplicate_keys_and_non_finite_numbers(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"records": [], "records": []}\n', encoding="utf-8")
    with pytest.raises(P6DatasetError, match="^DUPLICATE_JSON_KEY: records$"):
        load_duration_source(duplicate)

    non_finite = tmp_path / "non-finite.json"
    non_finite.write_text('{"value": NaN}\n', encoding="utf-8")
    with pytest.raises(P6DatasetError, match="^NON_FINITE_NUMBER: NaN$"):
        load_duration_source(non_finite)


def test_dataset_manifest_matches_p6_02_model_reference_shape() -> None:
    manifest = build_duration_dataset(_source())["dataset_manifest"]
    reference = {
        "document_version": manifest["document_version"],
        "artifact_id": manifest["artifact_id"],
        "fingerprint": manifest["fingerprint"],
    }
    assert reference["document_version"] == "duration-dataset-manifest.v1"
    assert reference["artifact_id"].startswith("duration-dataset-manifest-")
    assert reference["fingerprint"].startswith("sha256:")
