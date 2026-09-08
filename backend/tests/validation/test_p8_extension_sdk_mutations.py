"""Independent mutations for pairing, objective stage, versions, and conflicts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aps_extension_sdk import (
    ExtensionContractError,
    ExtensionErrorCode,
    fingerprint_json,
    parse_compatibility_policy,
    parse_extension_manifest,
    resolve_manifest_set,
)


ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "backend/aps_extension_sdk/contracts/samples"


def _json(name: str) -> dict[str, Any]:
    value = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _contribution(document: dict[str, Any], contribution_id: str) -> dict[str, Any]:
    return next(
        item
        for item in document["contributions"]
        if item["contribution_id"] == contribution_id
    )


def test_constraint_without_present_validator_is_rejected() -> None:
    document = _json("extension-manifest.v1.synthetic.json")
    constraint = _contribution(document, "com.example.capacity.constraint")
    constraint["validation_rule_ids"] = ["com.example.absent.validator"]
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.MISSING_VALIDATION_PAIR


def test_asymmetric_or_same_entrypoint_validator_pair_is_rejected() -> None:
    for mutation in ("asymmetric", "same-entrypoint"):
        document = _json("extension-manifest.v1.synthetic.json")
        constraint = _contribution(document, "com.example.capacity.constraint")
        validator = _contribution(document, "com.example.capacity.validator")
        if mutation == "asymmetric":
            validator["validates_contribution_ids"] = ["com.example.sequence.rule"]
        else:
            validator["implementation"] = constraint["implementation"]
        with pytest.raises(ExtensionContractError) as captured:
            parse_extension_manifest(document)
        assert captured.value.code is ExtensionErrorCode.INVALID_VALIDATION_PAIR


def test_objective_cannot_move_before_existing_core_stages() -> None:
    document = _json("extension-manifest.v1.synthetic.json")
    objective = _contribution(document, "com.example.cost.objective")
    objective["objective_stage"] = "BEFORE_DELIVERY"
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.INVALID_OBJECTIVE_STAGE


def test_duplicate_ids_and_mixed_sdk_sets_fail_closed() -> None:
    original = _json("extension-manifest.v1.synthetic.json")
    duplicate = copy.deepcopy(original)
    duplicate["contributions"].insert(1, copy.deepcopy(duplicate["contributions"][0]))
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(duplicate)
    assert captured.value.code is ExtensionErrorCode.DUPLICATE_CONTRIBUTION_ID

    second = copy.deepcopy(original)
    second["extension_id"] = "com.example.second_extension"
    second["sdk_api_version"] = "1.1.0"
    second.pop("manifest_fingerprint")
    second["manifest_fingerprint"] = fingerprint_json(second)
    first_manifest = parse_extension_manifest(original)
    second_manifest = parse_extension_manifest(second)
    policy = parse_compatibility_policy(
        _json("extension-compatibility.v1.synthetic.json")
    )
    with pytest.raises(ExtensionContractError) as captured:
        resolve_manifest_set((first_manifest, second_manifest), policy)
    assert captured.value.code is ExtensionErrorCode.MIXED_SDK_VERSION
