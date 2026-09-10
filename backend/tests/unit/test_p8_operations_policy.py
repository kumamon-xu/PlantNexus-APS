"""Unit evidence for the P8-18-corrected operations target policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from scripts.p8_operations_check import (
    EXPECTED_DEVELOPER_KIT_FINGERPRINT,
    EXPECTED_EXTENSION_IDS,
    RUNTIME_INPUTS,
    TARGET_PATH,
    contract_only_reports,
    extension_readiness,
    validate_target_contract,
)

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_input_guard_names_only_runtime_release_policies() -> None:
    release_inputs = {
        path for path in RUNTIME_INPUTS if path.startswith("infra/release")
    }
    assert release_inputs == {
        "infra/release/runtime-release-policy.v1.json",
        "infra/release/runtime-vulnerability-policy.v1.json",
    }
    assert "infra/release" not in RUNTIME_INPUTS


def _target() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((ROOT / TARGET_PATH).read_text(encoding="utf-8")),
    )


def test_target_is_exact_p8_18_test_simulation_runtime() -> None:
    target = _target()
    release = cast(dict[str, object], target["release"])
    summary = validate_target_contract(_target())
    assert summary == {
        "target_id": "p8-operations-compose-v1",
        "runtime_environment": "test",
        "data_plane": "SIMULATION",
        "runtime_version": "0.1.0",
        "runtime_implementation_sha": release["implementation_sha"],
        "release_archive_sha256": release["release_archive_sha256"],
        "release_fingerprint": release["release_fingerprint"],
        "extension_loading": "VERIFIED_BUILD_DEPLOY_STARTUP_ALLOW_LIST",
        "extension_ids": list(EXPECTED_EXTENSION_IDS),
        "developer_kit_version": "1.0.0",
        "developer_kit_fingerprint": EXPECTED_DEVELOPER_KIT_FINGERPRINT,
        "migration_version_table_bootstrap": (
            "CREATE_IF_ABSENT_VARCHAR_128_PRIMARY_KEY"
        ),
        "production_ready": False,
    }


def test_extension_configuration_is_exact_allow_list_and_fail_closed() -> None:
    target = _target()
    accepted = extension_readiness(target, EXPECTED_EXTENSION_IDS)
    rejected = extension_readiness(target, ["enterprise.unverified"])
    assert accepted == {
        "status": "UP",
        "code": None,
        "promotion_allowed": True,
        "configured_extension_count": 1,
        "configured_extension_ids": list(EXPECTED_EXTENSION_IDS),
    }
    assert rejected == {
        "status": "DOWN",
        "code": "EXTENSION_CONFIGURATION_REJECTED",
        "promotion_allowed": False,
        "configured_extension_count": 1,
        "configured_extension_ids": ["enterprise.unverified"],
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
