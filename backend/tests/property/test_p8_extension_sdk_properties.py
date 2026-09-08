"""Property evidence for SDK canonicalization, immutability, and strict parsing."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from hypothesis import given, strategies as st
import pytest

from aps_extension_sdk import (
    ExtensionContractError,
    ExtensionErrorCode,
    SemanticVersion,
    fingerprint_json,
    freeze_json,
    parse_extension_manifest,
    thaw_json,
)


ROOT = Path(__file__).resolve().parents[3]
SAMPLE = (
    ROOT
    / "backend/aps_extension_sdk/contracts/samples/extension-manifest.v1.synthetic.json"
)


def _manifest() -> dict[str, Any]:
    value = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@given(st.dictionaries(st.text(min_size=1, max_size=12), st.integers(), max_size=20))
def test_frozen_json_fingerprint_is_independent_of_mapping_insertion_order(
    values: dict[str, int],
) -> None:
    reverse = dict(reversed(list(values.items())))
    assert fingerprint_json(values) == fingerprint_json(reverse)
    assert thaw_json(freeze_json(values)) == values


@given(
    major=st.integers(min_value=0, max_value=1000),
    minor=st.integers(min_value=0, max_value=1000),
    patch=st.integers(min_value=0, max_value=1000),
)
def test_release_semver_round_trips_canonically(major: int, minor: int, patch: int) -> None:
    text = f"{major}.{minor}.{patch}"
    assert str(SemanticVersion.parse(text)) == text


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20))
def test_unknown_manifest_fields_fail_closed(suffix: str) -> None:
    document = _manifest()
    document[f"unknown_{suffix}"] = True
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.INVALID_MANIFEST


@given(st.permutations([0, 1, 2, 3, 4, 5, 6]))
def test_noncanonical_contribution_order_is_rejected(permutation: list[int]) -> None:
    if permutation == list(range(7)):
        return
    document = _manifest()
    original = copy.deepcopy(document["contributions"])
    document["contributions"] = [original[index] for index in permutation]
    with pytest.raises(ExtensionContractError) as captured:
        parse_extension_manifest(document)
    assert captured.value.code is ExtensionErrorCode.REGISTRY_CONFLICT
