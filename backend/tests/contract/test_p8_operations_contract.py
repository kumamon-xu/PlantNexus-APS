"""Contract evidence for TEST-P8-OPERATIONS-001."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import json
from pathlib import Path
from typing import cast

import pytest

from scripts.p8_operations_check import (
    OBSERVABILITY_PATH,
    TARGET_PATH,
    OperationsEvidenceError,
    validate_observability_contract,
    validate_runbooks,
    validate_target_contract,
)

ROOT = Path(__file__).resolve().parents[3]


def _document(path: Path) -> dict[str, object]:
    return cast(
        dict[str, object], json.loads((ROOT / path).read_text(encoding="utf-8"))
    )


def test_observability_contract_has_four_signals_ten_alerts_and_runbooks() -> None:
    summary = validate_observability_contract(_document(OBSERVABILITY_PATH), ROOT)
    assert summary["golden_signal_count"] == 4
    assert summary["alert_count"] == 10
    assert summary["dashboard_count"] == 1
    assert summary["payload_logging"] is False
    assert str(summary["policy_fingerprint"]).startswith("sha256:")
    runbooks = validate_runbooks(ROOT)
    assert len(runbooks) == 6
    assert all(item["required_sections"] == 8 for item in runbooks)
    assert all(item["status"] == "PASS" for item in runbooks)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value.update({"unknown": True}), "CONTRACT_INVALID"),
        (
            lambda value: cast(dict[str, object], value["isolation"]).update(
                {"data_plane": "PRODUCTION"}
            ),
            "ISOLATION_INVALID",
        ),
        (
            lambda value: cast(dict[str, object], value["extensions"]).update(
                {"allowed_extension_ids": ["enterprise.unverified"]}
            ),
            "EXTENSION_BOUNDARY_INVALID",
        ),
        (
            lambda value: cast(dict[str, object], value["production_boundary"]).update(
                {"production_ready": True}
            ),
            "PRODUCTION_CLAIM_INVALID",
        ),
    ],
)
def test_target_contract_rejects_scope_and_authority_mutations(
    mutation: Callable[[dict[str, object]], None], code: str
) -> None:
    target = deepcopy(_document(TARGET_PATH))
    mutation(target)
    with pytest.raises(OperationsEvidenceError) as error:
        validate_target_contract(target)
    assert error.value.code == code


def test_alert_contract_rejects_missing_or_unroutable_rule() -> None:
    policy = deepcopy(_document(OBSERVABILITY_PATH))
    alerts = cast(list[dict[str, object]], policy["alerts"])
    alerts.pop()
    with pytest.raises(OperationsEvidenceError) as missing:
        validate_observability_contract(policy, ROOT)
    assert missing.value.code == "OBSERVABILITY_INVALID"

    policy = deepcopy(_document(OBSERVABILITY_PATH))
    cast(list[dict[str, object]], policy["alerts"])[0]["runbook"] = (
        "docs/runbooks/not-present.md"
    )
    with pytest.raises(OperationsEvidenceError) as unroutable:
        validate_observability_contract(policy, ROOT)
    assert unroutable.value.code == "RUNBOOK_MISSING"
