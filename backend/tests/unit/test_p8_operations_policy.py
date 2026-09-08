"""Unit evidence for TASK-P8-10 target and Extension readiness policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from scripts.p8_operations_check import (
    TARGET_PATH,
    contract_only_reports,
    extension_readiness,
    validate_target_contract,
)

ROOT = Path(__file__).resolve().parents[3]


def _target() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ROOT / TARGET_PATH).read_text(encoding="utf-8")),
    )


def test_target_is_exact_p8_13_test_simulation_runtime() -> None:
    summary = validate_target_contract(_target())
    assert summary == {
        "target_id": "p8-operations-compose-v1",
        "runtime_environment": "test",
        "data_plane": "SIMULATION",
        "runtime_version": "0.1.0",
        "runtime_implementation_sha": "9818d0b6686ff005d0ea48ae81f3a306a5b36172",
        "release_archive_sha256": (
            "sha256:ee48bdd3245d83f7f87e1205c77aa69639b693120d13b6f80364a7dbecb1013f"
        ),
        "release_fingerprint": (
            "sha256:1a06018df48a7a22cd434d8076c02768b09da4ef3dfed35dd45d1b34474c70cc"
        ),
        "extension_loading": "DISABLED_UNTIL_COMPATIBILITY_VERIFIED",
        "migration_version_table_bootstrap": (
            "CREATE_IF_ABSENT_VARCHAR_128_PRIMARY_KEY"
        ),
        "production_ready": False,
    }


def test_extension_configuration_is_default_empty_and_fail_closed() -> None:
    target = _target()
    accepted = extension_readiness(target, [])
    rejected = extension_readiness(target, ["enterprise.unverified"])
    assert accepted == {
        "status": "UP",
        "code": None,
        "promotion_allowed": True,
        "configured_extension_count": 0,
    }
    assert rejected == {
        "status": "DOWN",
        "code": "EXTENSION_CONFIGURATION_REJECTED",
        "promotion_allowed": False,
        "configured_extension_count": 1,
    }


def test_contract_only_reports_keep_unexecuted_recovery_explicit() -> None:
    deployment, observability, recovery, runbook = contract_only_reports(ROOT)
    assert {
        report["status"] for report in (deployment, observability, recovery, runbook)
    } == {"PASS"}
    assert deployment["execution"] == "CONTRACT_ONLY"
    assert observability["alert_ids"]
    assert recovery["backup_restore_executed"] is False
    assert recovery["rollback_executed"] is False
    assert runbook["runbook_count"] == 6
    assert deployment["production_ready"] is False
    assert recovery["production_recovery_claimed"] is False
