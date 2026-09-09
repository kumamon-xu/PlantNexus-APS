"""Compatibility and explicit-upgrade properties for TASK-P8-15."""

from __future__ import annotations

from hypothesis import given, strategies as st
import pytest

from aps_developer_kit.builder import load_policy
from aps_developer_kit.contracts import (
    DeveloperKitContractError,
    plan_upgrade,
    require_compatible,
)
from backend.tests.p8_developer_kit_support import ROOT


TARGET = {
    "developer_kit": "1.0.0",
    "runtime": "0.1.0",
    "extension_sdk": "1.0.0",
    "extension_tooling": "1.0.0",
    "enterprise_template": "1.0.0",
}


@given(
    field=st.sampled_from(sorted(TARGET)),
    unsupported=st.sampled_from(["0.0.1", "0.2.0", "1.0.1", "latest"]),
)
def test_any_single_version_drift_is_rejected(field: str, unsupported: str) -> None:
    matrix = load_policy(ROOT)["compatibility"]
    combination = dict(TARGET)
    if unsupported == combination[field]:
        unsupported = "9.9.9"
    combination[field] = unsupported
    with pytest.raises(DeveloperKitContractError) as raised:
        require_compatible(matrix, combination)
    assert raised.value.code == "KIT_COMBINATION_UNSUPPORTED"


def test_upgrade_is_pure_and_requires_explicit_opt_in() -> None:
    matrix = load_policy(ROOT)["compatibility"]
    predecessor = {
        "developer_kit": "0.0.0-not-published",
        "runtime": "0.1.0",
        "extension_sdk": "1.0.0",
    }
    original = dict(predecessor)
    with pytest.raises(DeveloperKitContractError) as raised:
        plan_upgrade(matrix, predecessor, TARGET, explicit_opt_in=False)
    assert raised.value.code == "KIT_IMPLICIT_UPGRADE_FORBIDDEN"
    plan = plan_upgrade(matrix, predecessor, TARGET, explicit_opt_in=True)
    assert predecessor == original
    assert plan["project_mutated"] is False
    assert plan["conformance_required"] is True
