from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

import pytest

from app.duration_prediction.evaluation import (
    P6EvaluationError,
    build_duration_evaluation,
    canonical_json_bytes,
    evaluate_duration_paths,
    load_evaluation_profile,
    validate_offline_gate_report,
)
from app.duration_prediction.model import load_duration_model

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "benchmarks" / "p6" / "duration-evaluation-profile.v1.json"
DATASET_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-DATASET"
    / "expected-dataset-bundle.v1.json"
)
MODEL_BUNDLE_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MODEL"
    / "expected-model-bundle.v1.json"
)
MODEL_ARTIFACT_PATH = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "P6-DURATION-MODEL"
    / "baseline-model.v1.pnmodel"
)


def _load(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _inputs():  # type: ignore[no-untyped-def]
    dataset = _load(DATASET_PATH)
    model_bundle = _load(MODEL_BUNDLE_PATH)
    profile = load_evaluation_profile(PROFILE_PATH)
    loaded_model = load_duration_model(
        MODEL_ARTIFACT_PATH,
        model_bundle["model_manifest"],
        model_bundle["training_configuration"],
    )
    return dataset, model_bundle, profile, loaded_model


def _refresh_identity(
    value: dict[str, Any], id_field: str, fingerprint_field: str, prefix: str
) -> None:
    value.pop(id_field, None)
    value.pop(fingerprint_field, None)
    fingerprint = f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"
    value[id_field] = prefix + fingerprint.removeprefix("sha256:")
    value[fingerprint_field] = fingerprint


def _set_threshold(profile: dict[str, Any]) -> None:
    profile["confidence_policy"]["threshold"]["numerator"] = 8


def _set_partitions(profile: dict[str, Any]) -> None:
    profile["evaluation_selection"]["included_partitions"] = ["test"]


def _set_fallback_reason(profile: dict[str, Any]) -> None:
    profile["fallback_policy"]["reason_codes"][0] = "UNKNOWN"


def _set_production(profile: dict[str, Any]) -> None:
    profile["governance_boundary"]["production_authorized"] = True


def _set_dataset_identity(profile: dict[str, Any]) -> None:
    profile["input_contract"]["dataset"]["bundle_fingerprint"] = "sha256:" + "0" * 64


def _add_unknown(profile: dict[str, Any]) -> None:
    profile["unknown"] = True


@pytest.mark.parametrize(
    "mutation",
    [
        _set_threshold,
        _set_partitions,
        _set_fallback_reason,
        _set_production,
        _set_dataset_identity,
        _add_unknown,
    ],
)
def test_profile_policy_mutations_fail_closed(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    profile = _load(PROFILE_PATH)
    mutation(profile)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(P6EvaluationError) as captured:
        load_evaluation_profile(path)

    assert captured.value.code in {
        "NON_CANONICAL_FRACTION",
        "OBJECT_SHAPE_MISMATCH",
        "PROFILE_POLICY_MISMATCH",
    }


@pytest.mark.parametrize(
    ("raw", "expected_code"),
    [
        (b'{"profile_id":"a","profile_id":"b"}', "DUPLICATE_JSON_KEY"),
        (b'{"profile_id":NaN}', "NON_FINITE_JSON"),
    ],
)
def test_duplicate_and_nonfinite_profile_json_are_rejected(
    tmp_path: Path, raw: bytes, expected_code: str
) -> None:
    path = tmp_path / "profile.json"
    path.write_bytes(raw)

    with pytest.raises(P6EvaluationError) as captured:
        load_evaluation_profile(path)

    assert captured.value.code == expected_code


def test_heldout_label_tamper_is_rejected_before_aggregation() -> None:
    dataset, model_bundle, profile, loaded_model = _inputs()
    mutated = deepcopy(dataset)
    heldout = next(row for row in mutated["rows"] if row["partition"] == "validation")
    heldout["label"]["value"] += 1

    with pytest.raises(P6EvaluationError) as captured:
        build_duration_evaluation(mutated, model_bundle, loaded_model, profile)

    assert captured.value.code == "DATASET_ROW_TAMPERED"


def test_sparse_heldout_partition_and_family_fail_closed() -> None:
    dataset, model_bundle, profile, loaded_model = _inputs()
    mutated = deepcopy(dataset)
    index = next(
        index
        for index, row in enumerate(mutated["rows"])
        if row["partition"] == "test"
    )
    mutated["rows"].pop(index)

    with pytest.raises(P6EvaluationError) as captured:
        build_duration_evaluation(mutated, model_bundle, loaded_model, profile)

    assert captured.value.code == "DATASET_PARTITION_MISMATCH"


def test_exact_dataset_file_digest_rejects_refreshed_in_memory_tamper(
    tmp_path: Path,
) -> None:
    dataset = _load(DATASET_PATH)
    heldout = next(row for row in dataset["rows"] if row["partition"] == "validation")
    heldout["label"]["value"] += 1
    projection = {
        key: deepcopy(value)
        for key, value in heldout.items()
        if key not in {"dataset_row_id", "dataset_row_fingerprint"}
    }
    fingerprint = f"sha256:{sha256(canonical_json_bytes(projection)).hexdigest()}"
    heldout["dataset_row_fingerprint"] = fingerprint
    heldout["dataset_row_id"] = "duration-dataset-row-" + fingerprint.removeprefix(
        "sha256:"
    )
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")

    with pytest.raises(P6EvaluationError) as captured:
        evaluate_duration_paths(
            dataset_path=path,
            model_bundle_path=MODEL_BUNDLE_PATH,
            model_artifact_path=MODEL_ARTIFACT_PATH,
            profile_path=PROFILE_PATH,
        )

    assert captured.value.code == "DATASET_FILE_DIGEST_MISMATCH"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("decision", "REPORT_DECISION_MISMATCH"),
        ("check", "REPORT_DECISION_MISMATCH"),
        ("measurement", "MEASUREMENT_CONTRACT_MISMATCH"),
        ("train-label-read", "TRAIN_LABEL_READ"),
        ("unsafe-payload", "UNSAFE_EVIDENCE_PAYLOAD"),
    ],
)
def test_report_mutations_fail_even_with_refreshed_fingerprints(
    mutation: str, expected_code: str
) -> None:
    dataset, model_bundle, profile, loaded_model = _inputs()
    report = deepcopy(
        build_duration_evaluation(
            dataset, model_bundle, loaded_model, profile
        ).gate_report
    )
    if mutation == "decision":
        report["gate_decision"]["decision"] = "NOT_READY"
    elif mutation == "check":
        report["checks"][0]["result"] = "FAIL"
    elif mutation == "measurement":
        measurement = report["measurement_report"]
        measurement["gate_assessment"]["thresholds_embedded"] = True
        _refresh_identity(
            measurement,
            "evaluation_report_id",
            "evaluation_report_fingerprint",
            "duration-evaluation-report-",
        )
    elif mutation == "train-label-read":
        report["selection"]["train_label_reads"] = 1
    else:
        report["metrics"]["overall"]["label"] = {"value": 1}
    _refresh_identity(
        report,
        "gate_report_id",
        "gate_report_fingerprint",
        "p6-duration-offline-gate-report-",
    )

    with pytest.raises(P6EvaluationError) as captured:
        validate_offline_gate_report(report, profile)

    assert captured.value.code == expected_code
