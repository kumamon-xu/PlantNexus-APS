"""Contract tests for the independent TASK-P8-16 Gate carrier."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from app.data_validation.canonical_ingress import canonical_fingerprint
from scripts import p8_headless_extension_platform_gate as gate


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "benchmarks/p8/headless-extension-platform-gate-profile.v1.json"


def _seal(document: dict[str, Any]) -> dict[str, Any]:
    projection = dict(document)
    projection.pop("report_fingerprint", None)
    document["report_fingerprint"] = canonical_fingerprint(projection)
    return document


def _ready_report() -> dict[str, Any]:
    checks = [
        {"check_id": check_id, "status": "PASS", "evidence": {}}
        for check_id in gate._EXPECTED_CHECK_IDS
    ]
    return _seal(
        {
            "report_version": gate.REPORT_VERSION,
            "audit_status": "PASS",
            "verdict": "READY",
            "task_id": gate.TASK_ID,
            "test_id": gate.TEST_ID,
            "validation_profile": "PHASE_GATE",
            "diff_base": gate.DIFF_BASE,
            "code_commit": "1" * 40,
            "profile": {
                "profile_version": gate.PROFILE_VERSION,
                "profile_fingerprint": (
                    "sha256:da5ee7830e37f86569897a80685d25e59414f05153499b3effed37b483503043"
                ),
                "seed": 81620260909,
                "environment": "TEST",
                "data_plane": "SIMULATION",
                "frozen_p8_15_code_commit": gate.DIFF_BASE,
            },
            "inputs": {
                name: {
                    "report_version": version,
                    "status": "PASS",
                    "fingerprint": f"sha256:{index:064x}",
                }
                for index, (name, (version, _)) in enumerate(
                    gate._INPUT_REPORTS.items(), start=1
                )
            },
            "checks": checks,
            "check_summary": {
                "check_count": len(checks),
                "pass_count": len(checks),
                "blocked_count": 0,
                "error_count": 0,
            },
            "blocking_gaps": [],
            "issues": [],
            "scope": {
                "synthetic_engineering_gate": True,
                "real_data": False,
                "p7_reality_calibration": False,
                "production_ready": False,
                "capacity_or_sla": False,
                "demo_included": False,
                "third_party_connector": False,
            },
            "next": {
                "corrective_task": None,
                "requalification_task": None,
                "p8_exit_gate_authorized": False,
                "automatic_start": False,
            },
            "evidence": {
                name: {
                    "report_version": version,
                    "report_fingerprint": f"sha256:{index:064x}",
                }
                for index, (name, version) in enumerate(
                    {
                        "provenance": gate.PROVENANCE_VERSION,
                        "compatibility": gate.COMPATIBILITY_VERSION,
                        "security": gate.SECURITY_VERSION,
                        "recovery": gate.RECOVERY_VERSION,
                        "benchmark": gate.BENCHMARK_VERSION,
                    }.items(),
                    start=1,
                )
            },
        }
    )


def test_closed_profile_binds_p8_15_kit_and_two_extensions() -> None:
    document = json.loads(PROFILE.read_text(encoding="utf-8"))
    validated = gate.validate_profile(document)

    assert validated["profile_version"] == gate.PROFILE_VERSION
    assert validated["validation_profile"] == "PHASE_GATE"
    assert validated["frozen_p8_15"]["provider_run_id"] == 34320622291
    assert [item["extension_id"] for item in validated["extensions"]] == [
        "com.example.aps.alpha",
        "com.example.aps.beta",
    ]
    assert validated["boundaries"]["production_authorized"] is False
    assert validated["boundaries"]["demo_included"] is False


def test_gate_report_contract_accepts_binary_ready_and_not_ready() -> None:
    ready = _ready_report()
    gate.validate_gate_report(ready)

    not_ready = deepcopy(ready)
    check = not_ready["checks"][13]
    check["status"] = "BLOCKED"
    blocker_id = "P8-GATE-BLOCKER-EXTENSION-EXECUTION-001"
    not_ready["verdict"] = "NOT_READY"
    not_ready["blocking_gaps"] = [
        {
            "blocker_id": blocker_id,
            "category": gate._BLOCKER_DETAILS[blocker_id][0],
            "summary": gate._BLOCKER_DETAILS[blocker_id][1],
            "evidence": {},
            "corrective_owner": "TASK-P8-18",
            "requalification_owner": "TASK-P8-19",
            "production_waiver_allowed": False,
        }
    ]
    not_ready["check_summary"] = {
        "check_count": len(not_ready["checks"]),
        "pass_count": len(not_ready["checks"]) - 1,
        "blocked_count": 1,
        "error_count": 0,
    }
    not_ready["next"] = {
        "corrective_task": "TASK-P8-18",
        "requalification_task": "TASK-P8-19",
        "p8_exit_gate_authorized": False,
        "automatic_start": False,
    }
    _seal(not_ready)
    gate.validate_gate_report(not_ready)
