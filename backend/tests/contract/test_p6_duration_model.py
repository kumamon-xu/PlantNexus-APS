"""Training, replay, security, and cleanup tests for TASK-P6-04."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st
from jsonschema import Draft202012Validator, FormatChecker
import pytest

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
    build_training_configuration,
    dependency_lock_digest,
    load_duration_model,
    predict_duration,
    write_duration_model,
)


ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-DATASET"
    / "expected-dataset-bundle.v1.json"
)
SOURCE_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-DATASET"
    / "source-records.v1.json"
)
ARTIFACT_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MODEL"
    / "baseline-model.v1.pnmodel"
)
EXPECTED_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MODEL"
    / "expected-model-bundle.v1.json"
)
MANIFEST_SCHEMA_PATH = ROOT / "schemas" / "json" / "duration-model-manifest.schema.json"


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _dataset() -> dict[str, Any]:
    return _load_json(DATASET_PATH)


def _expected() -> dict[str, Any]:
    return _load_json(EXPECTED_PATH)


def _digest(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _refresh_identity(
    value: dict[str, Any], id_field: str, fingerprint_field: str, prefix: str
) -> None:
    projection = {
        key: item
        for key, item in value.items()
        if key not in {id_field, fingerprint_field}
    }
    fingerprint = _digest(projection)
    value[id_field] = prefix + fingerprint.removeprefix("sha256:")
    value[fingerprint_field] = fingerprint


def _refresh_manifest_for_artifact(
    artifact: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    result = deepcopy(manifest)
    result["model_artifact"]["artifact_digest"] = _digest(artifact)
    _refresh_identity(
        result,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    return result


def _refresh_feature(feature_record: dict[str, Any]) -> None:
    _refresh_identity(
        feature_record,
        "feature_record_id",
        "feature_record_fingerprint",
        "duration-feature-record-",
    )


def _write_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.write_bytes(artifact_file_bytes(artifact))


def _published_model() -> model_module.LoadedDurationModel:
    expected = _expected()
    return load_duration_model(
        ARTIFACT_PATH,
        expected["model_manifest"],
        expected["training_configuration"],
    )


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key)
            keys.update(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_walk_keys(item))
    return keys


def test_published_artifact_bundle_and_existing_manifest_schema_are_exact() -> None:
    build = build_duration_model(_dataset(), dependency_lock_digest(ROOT / "uv.lock"))
    expected = _expected()
    assert build.bundle == expected
    assert ARTIFACT_PATH.read_bytes().replace(b"\r\n", b"\n") == artifact_file_bytes(
        build.artifact
    )
    assert build.artifact_digest == expected["model_manifest"]["model_artifact"][
        "artifact_digest"
    ]
    assert build.artifact["parameters"]["family_offsets_seconds"] == [
        {"operation_family": "milling", "numerator": -40, "denominator": 1},
        {"operation_family": "turning", "numerator": -45, "denominator": 2},
    ]
    assert build.artifact["parameters"]["p90_margin_seconds"] == 20
    assert len(build.artifact["training_provenance"]["training_row_ids"]) == 4
    assert build.artifact["training_provenance"]["partition"] == "train"
    assert build.artifact["training_provenance"]["dependency_lock_digest"] == (
        EXPECTED_DEPENDENCY_LOCK_DIGEST
    )

    schema = _load_json(MANIFEST_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert list(validator.iter_errors(expected["model_manifest"])) == []
    assert expected["model_manifest"]["use_authorization"]["decision"] == (
        "SIMULATION_EVALUATION_ONLY"
    )
    assert expected["model_manifest"]["production_binding"] is False
    assert expected["use_authorization_decision"]["promotion_authorized"] is False


def test_artifact_and_provider_replay_are_data_minimized() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    replay = _expected()["replay"]
    forbidden = {
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
    assert _walk_keys(artifact).isdisjoint(forbidden)
    assert _walk_keys(replay).isdisjoint(forbidden)
    assert replay["boundaries"]["labels_in_replay_artifact"] is False
    assert replay["boundaries"]["quality_metrics"] == "NOT_COMPUTED"
    assert replay["boundaries"]["confidence_threshold"] == "NOT_FORMED"
    raw = ARTIFACT_PATH.read_bytes().lower()
    assert all(
        token not in raw
        for token in (b"pickle", b"joblib", b"cloudpickle", b"__reduce__", b"importlib")
    )


def test_same_input_training_and_estimates_are_byte_identical() -> None:
    first = build_duration_model(_dataset(), EXPECTED_DEPENDENCY_LOCK_DIGEST)
    second = build_duration_model(_dataset(), EXPECTED_DEPENDENCY_LOCK_DIGEST)
    assert artifact_file_bytes(first.artifact) == artifact_file_bytes(second.artifact)
    assert canonical_json_bytes(first.bundle) == canonical_json_bytes(second.bundle)
    assert first.artifact_digest == second.artifact_digest


@settings(max_examples=8, deadline=None)
@given(st.permutations(tuple(range(10))))
def test_source_order_cannot_change_training_output(order: tuple[int, ...]) -> None:
    source = load_duration_source(SOURCE_PATH)
    records = source["records"]
    assert isinstance(records, list)
    source["records"] = [records[index] for index in order]
    rebuilt_dataset = build_duration_dataset(source)
    trained = build_duration_model(rebuilt_dataset, EXPECTED_DEPENDENCY_LOCK_DIGEST)
    assert trained.bundle == _expected()


def test_safe_loader_replays_all_partitions_without_evaluation() -> None:
    model = _published_model()
    dataset = _dataset()
    replay_by_row = {
        item["dataset_row_id"]: item["estimate"] for item in _expected()["replay"]["estimates"]
    }
    observed_partitions: set[str] = set()
    for row in dataset["rows"]:
        estimate = predict_duration(model, row["feature_record"])
        assert estimate == replay_by_row[row["dataset_row_id"]]
        assert estimate["p90_seconds"] >= estimate["p50_seconds"] > 0
        assert estimate["confidence_status"] == "NOT_ESTABLISHED_BY_P6_04"
        assert estimate["evaluation_gate"] == "NOT_EVALUATED_BY_P6_04"
        assert estimate["planning_authority"] == "NONE"
        observed_partitions.add(row["partition"])
    assert observed_partitions == {"train", "validation", "test"}


@settings(max_examples=20, deadline=None)
@given(
    planned_quantity=st.integers(min_value=1, max_value=10_000),
    setup_seconds=st.integers(min_value=0, max_value=100_000),
)
def test_zero_weight_features_do_not_change_estimate(
    planned_quantity: int, setup_seconds: int
) -> None:
    model = _published_model()
    feature = deepcopy(_dataset()["rows"][0]["feature_record"])
    baseline = predict_duration(model, feature)
    for item in feature["features"]:
        if item["feature_name"] == "planned_quantity":
            item["value"] = planned_quantity
        if item["feature_name"] == "setup_seconds":
            item["value"] = setup_seconds
    _refresh_feature(feature)
    changed = predict_duration(model, feature)
    assert (changed["p50_seconds"], changed["p90_seconds"]) == (
        baseline["p50_seconds"],
        baseline["p90_seconds"],
    )


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("payload-tamper", "DATASET_FINGERPRINT_MISMATCH"),
        ("refreshed-tamper", "DATASET_NOT_AUTHORIZED"),
        ("mixed-schema", "SCHEMA_VERSION_INCOMPATIBLE"),
    ],
)
def test_dataset_tampering_and_mixed_versions_fail_closed(
    mutation: str, error_code: str
) -> None:
    dataset = _dataset()
    if mutation == "mixed-schema":
        dataset["schema_set_version"] = "2.8.0"
    else:
        dataset["rows"][0]["label"]["value"] = 999
        if mutation == "refreshed-tamper":
            projection = {
                key: value
                for key, value in dataset.items()
                if key != "bundle_fingerprint"
            }
            dataset["bundle_fingerprint"] = _digest(projection)
    with pytest.raises(P6ModelError, match=f"^{error_code}:"):
        build_duration_model(dataset, EXPECTED_DEPENDENCY_LOCK_DIGEST)


def test_dependency_lock_and_configuration_are_exact() -> None:
    with pytest.raises(P6ModelError, match="^DEPENDENCY_LOCK_MISMATCH:"):
        build_duration_model(_dataset(), "sha256:" + "0" * 64)

    expected = _expected()
    configuration = deepcopy(expected["training_configuration"])
    configuration["determinism"]["seed_accepted"] = True
    with pytest.raises(P6ModelError, match="^CONFIGURATION_MISMATCH:"):
        load_duration_model(ARTIFACT_PATH, expected["model_manifest"], configuration)
    assert build_training_configuration()["determinism"] == {
        "randomness": "NONE",
        "seed_accepted": False,
        "host_clock_in_identity": False,
        "training_timestamp_utc": "2026-09-01T09:00:00Z",
    }


def test_tampered_artifact_and_unknown_fields_fail_even_with_refreshed_manifest(
    tmp_path: Path,
) -> None:
    expected = _expected()
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    artifact["parameters"]["p90_margin_seconds"] = 21
    path = tmp_path / "tampered.pnmodel"
    _write_artifact(path, artifact)
    with pytest.raises(P6ModelError, match="^ARTIFACT_DIGEST_MISMATCH:"):
        load_duration_model(
            path, expected["model_manifest"], expected["training_configuration"]
        )

    artifact["unexpected"] = "rejected"
    refreshed_manifest = _refresh_manifest_for_artifact(
        artifact, expected["model_manifest"]
    )
    _write_artifact(path, artifact)
    with pytest.raises(P6ModelError, match="^UNKNOWN_FIELD:"):
        load_duration_model(path, refreshed_manifest, expected["training_configuration"])


def test_training_code_and_manifest_lineage_fail_closed(tmp_path: Path) -> None:
    expected = _expected()
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    artifact["training_provenance"]["code_revision"] = "0" * 40
    manifest = _refresh_manifest_for_artifact(artifact, expected["model_manifest"])
    manifest["training_provenance"]["code_revision"] = "0" * 40
    _refresh_identity(
        manifest,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    path = tmp_path / "code-drift.pnmodel"
    _write_artifact(path, artifact)
    with pytest.raises(P6ModelError, match="^TRAINING_CODE_MISMATCH:"):
        load_duration_model(path, manifest, expected["training_configuration"])

    manifest = deepcopy(expected["model_manifest"])
    manifest["dataset_manifest"]["fingerprint"] = "sha256:" + "0" * 64
    _refresh_identity(
        manifest,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    with pytest.raises(P6ModelError, match="^DATASET_VERSION_INCOMPATIBLE:"):
        load_duration_model(
            ARTIFACT_PATH, manifest, expected["training_configuration"]
        )

    unknown_manifest = deepcopy(expected["model_manifest"])
    unknown_manifest["unexpected_runtime_endpoint"] = "https://invalid.example"
    _refresh_identity(
        unknown_manifest,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    with pytest.raises(P6ModelError, match="^UNKNOWN_FIELD:"):
        load_duration_model(
            ARTIFACT_PATH, unknown_manifest, expected["training_configuration"]
        )

    changed_scope = deepcopy(expected["model_manifest"])
    changed_scope["scope"]["resource_ids"].append("resource-sim-p6-unapproved")
    _refresh_identity(
        changed_scope,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    with pytest.raises(P6ModelError, match="^MODEL_MANIFEST_MISMATCH:"):
        load_duration_model(
            ARTIFACT_PATH, changed_scope, expected["training_configuration"]
        )


def test_unsafe_serialization_duplicate_nonfinite_and_oversize_are_rejected(
    tmp_path: Path,
) -> None:
    expected = _expected()
    manifest = deepcopy(expected["model_manifest"])
    manifest["model_artifact"]["serialization_format"] = "python-pickle"
    _refresh_identity(
        manifest,
        "model_manifest_id",
        "model_manifest_fingerprint",
        "duration-model-manifest-",
    )
    with pytest.raises(P6ModelError, match="^UNSAFE_SERIALIZATION_FORMAT:"):
        load_duration_model(
            ARTIFACT_PATH, manifest, expected["training_configuration"]
        )

    duplicate = tmp_path / "duplicate.pnmodel"
    duplicate.write_bytes(b'{"x":1,"x":2}\n')
    with pytest.raises(P6ModelError, match="^DUPLICATE_JSON_KEY:"):
        load_duration_model(
            duplicate, expected["model_manifest"], expected["training_configuration"]
        )

    non_finite = tmp_path / "nan.pnmodel"
    non_finite.write_bytes(b'{"x":NaN}\n')
    with pytest.raises(P6ModelError, match="^NON_FINITE_NUMBER:"):
        load_duration_model(
            non_finite, expected["model_manifest"], expected["training_configuration"]
        )

    oversize = tmp_path / "oversize.pnmodel"
    oversize.write_bytes(b"{" + b" " * MAX_ARTIFACT_BYTES + b"}")
    with pytest.raises(P6ModelError, match="^ARTIFACT_TOO_LARGE:"):
        load_duration_model(
            oversize, expected["model_manifest"], expected["training_configuration"]
        )


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("factory", "MODEL_OUT_OF_SCOPE"),
        ("resource", "MODEL_OUT_OF_SCOPE"),
        ("family", "MODEL_OUT_OF_SCOPE"),
        ("standard", "INVALID_INTEGER"),
        ("future", "FUTURE_FEATURE_LEAKAGE"),
    ],
)
def test_feature_scope_and_invalid_inputs_fail_closed(
    mutation: str, error_code: str
) -> None:
    model = _published_model()
    feature = deepcopy(_dataset()["rows"][0]["feature_record"])
    if mutation == "factory":
        feature["factory_id"] = "factory-other"
    elif mutation == "resource":
        feature["resource_id"] = "resource-other"
    else:
        for item in feature["features"]:
            if mutation == "family" and item["feature_name"] == "operation_family":
                item["value"] = "drilling"
            if mutation == "standard" and item["feature_name"] == "standard_duration_seconds":
                item["value"] = 0
            if mutation == "future":
                item["available_at_utc"] = "2026-07-04T08:00:01Z"
    _refresh_feature(feature)
    with pytest.raises(P6ModelError, match=f"^{error_code}:"):
        predict_duration(model, feature)


def test_invalid_model_output_is_rejected_after_safe_load(tmp_path: Path) -> None:
    expected = _expected()
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    artifact["parameters"]["family_offsets_seconds"][0] = {
        "operation_family": "milling",
        "numerator": -10_000,
        "denominator": 1,
    }
    manifest = _refresh_manifest_for_artifact(artifact, expected["model_manifest"])
    path = tmp_path / "invalid-output.pnmodel"
    _write_artifact(path, artifact)
    loaded = load_duration_model(path, manifest, expected["training_configuration"])
    feature = _dataset()["rows"][0]["feature_record"]
    with pytest.raises(P6ModelError, match="^INVALID_MODEL_OUTPUT:"):
        predict_duration(loaded, feature)


def test_atomic_writer_replays_and_preserves_target_on_invalid_input(
    tmp_path: Path,
) -> None:
    target = tmp_path / "model.pnmodel"
    first = write_duration_model(_dataset(), target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
    first_bytes = target.read_bytes()
    second = write_duration_model(_dataset(), target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
    assert first == second == _expected()
    assert first_bytes == target.read_bytes() == ARTIFACT_PATH.read_bytes().replace(
        b"\r\n", b"\n"
    )
    assert list(tmp_path.glob(".model.pnmodel.*.tmp")) == []

    invalid = _dataset()
    invalid["rows"][0]["label"]["value"] = 999
    with pytest.raises(P6ModelError, match="^DATASET_FINGERPRINT_MISMATCH:"):
        write_duration_model(invalid, target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
    assert target.read_bytes() == first_bytes
    assert list(tmp_path.glob(".model.pnmodel.*.tmp")) == []


def test_atomic_replace_failure_preserves_target_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "model.pnmodel"
    target.write_bytes(b"previous\n")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(model_module.os, "replace", fail_replace)
    with pytest.raises(P6ModelError, match="^ATOMIC_WRITE_FAILED: OSError$"):
        write_duration_model(_dataset(), target, EXPECTED_DEPENDENCY_LOCK_DIGEST)
    assert target.read_bytes() == b"previous\n"
    assert list(tmp_path.glob(".model.pnmodel.*.tmp")) == []


def test_loader_and_writer_reject_symlink_targets(tmp_path: Path) -> None:
    expected = _expected()
    actual = tmp_path / "actual.pnmodel"
    actual.write_bytes(ARTIFACT_PATH.read_bytes())
    link = tmp_path / "link.pnmodel"
    try:
        os.symlink(actual, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(P6ModelError, match="^UNSAFE_ARTIFACT_PATH:"):
        load_duration_model(
            link, expected["model_manifest"], expected["training_configuration"]
        )
    with pytest.raises(P6ModelError, match="^UNSAFE_ARTIFACT_PATH:"):
        write_duration_model(_dataset(), link, EXPECTED_DEPENDENCY_LOCK_DIGEST)
