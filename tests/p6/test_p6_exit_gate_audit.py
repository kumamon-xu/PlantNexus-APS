"""Non-skippable independent P6 Exit evidence for TASK-P6-10."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.p6.p6_exit_gate_audit import (
    DIFF_BASE,
    EXPECTED_CHECK_IDS,
    MANIFEST_VERSION,
    OBSERVATION_VERSION,
    REPORT_VERSION,
    TASK_ID,
    build_p6_exit_gate_manifest,
    run_p6_exit_gate_audit,
    validate_p6_exit_gate_manifest,
    validate_p6_exit_gate_report,
    validate_provider_observation,
)


type JsonObject = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]
OBSERVATION_PATH = ROOT / "docs/p6-exit-gate-audit-observations.v1.json"


def _load_observation() -> JsonObject:
    value = json.loads(OBSERVATION_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_p6_exit_gate_fresh_independent_audit(
    tmp_path: Path,
    record_testsuite_property: Any,
) -> None:
    observation = _load_observation()
    validate_provider_observation(observation, ROOT)
    report = run_p6_exit_gate_audit(
        root=ROOT,
        provider_observation=observation,
        subreport_dir=tmp_path / "fresh-exit-subreports",
    )
    manifest = build_p6_exit_gate_manifest(report)
    validate_p6_exit_gate_report(report)
    validate_p6_exit_gate_manifest(manifest, report)

    assert observation["report_version"] == OBSERVATION_VERSION
    assert report["report_version"] == REPORT_VERSION
    assert manifest["schema_version"] == MANIFEST_VERSION
    assert report["audit_task"] == TASK_ID
    assert report["diff_base"] == DIFF_BASE
    assert report["validation_profile"] == "PHASE_GATE"
    assert report["decision"] == "READY"
    assert report["check_count"] == len(EXPECTED_CHECK_IDS)
    assert report["issues"] == []
    assert report["blocking_gaps"] == []

    provider = report["provider_evidence"]
    assert provider["run_count"] == 18
    assert provider["successful_run_count"] == 17
    assert provider["retained_failed_run_count"] == 1
    assert provider["artifact_count"] == 48
    assert provider["successful_artifact_count"] == 46
    assert provider["expired_artifact_count"] == 0
    assert provider["digest_mismatch_count"] == 0
    assert provider["successful_zip_issue_count"] == 0

    fresh_gate = report["fresh_p6_gate"]
    assert fresh_gate["status"] == "PASS"
    assert fresh_gate["repeat_count"] == 2
    assert fresh_gate["check_count"] == 13
    assert fresh_gate["owner_stage_executions"] == 18
    assert fresh_gate["negative_rejections"] == 10
    assert fresh_gate["issues"] == []
    assert fresh_gate["blocking_gaps"] == []

    boundaries = report["boundaries"]
    assert boundaries["current_phase"] == "P6"
    assert boundaries["p6_milestone"] == "ACTIVE_AWAITING_USER_TRANSITION"
    assert boundaries["p7_reality_calibration"] == "NOT_ENTERED"
    assert boundaries["production_readiness"] == "NOT_CLAIMED"
    assert boundaries["default_enabled"] is False
    assert boundaries["automatic_phase_transition"] == "PROHIBITED"

    properties = {
        "p6_exit_report_version": REPORT_VERSION,
        "p6_exit_task_id": TASK_ID,
        "p6_exit_diff_base": DIFF_BASE,
        "p6_exit_code_commit": report["code_commit"],
        "p6_exit_validation_profile": report["validation_profile"],
        "p6_exit_decision": report["decision"],
        "p6_exit_check_count": report["check_count"],
        "p6_exit_issues": json.dumps(report["issues"], separators=(",", ":")),
        "p6_exit_blocking_gaps": json.dumps(
            report["blocking_gaps"], separators=(",", ":")
        ),
        "p6_exit_provider_inventory_fingerprint": provider[
            "provider_inventory_fingerprint"
        ],
        "p6_exit_fresh_gate_semantic_fingerprint": fresh_gate[
            "semantic_fingerprint"
        ],
        "p6_exit_report_fingerprint": report["report_fingerprint"],
        "p6_exit_manifest_fingerprint": manifest["manifest_fingerprint"],
        "p6_exit_provider_binding": manifest["provider_binding"][
            "exit_execution_evidence"
        ],
    }
    for name, value in properties.items():
        record_testsuite_property(name, str(value))
