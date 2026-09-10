"""Contract and fail-closed tests for TASK-P8-19 requalification."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from app.data_validation.canonical_ingress import canonical_fingerprint
from scripts import p8_headless_extension_platform_requalification_gate as gate


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
        for check_id in gate._PLATFORM_CHECK_IDS
    ]
    closures = gate._closure_assertions(checks)
    return _seal(
        {
            "report_version": gate.REPORT_VERSION,
            "audit_status": "PASS",
            "verdict": "READY",
            "task_id": gate.TASK_ID,
            "test_id": gate.TEST_ID,
            "validation_profile": gate.VALIDATION_PROFILE,
            "diff_base": gate.DIFF_BASE,
            "code_commit": "1" * 40,
            "profile": {
                "profile_version": "p8-headless-extension-platform-gate-profile.v1",
                "profile_fingerprint": gate.PROFILE_FINGERPRINT,
                "seed": 81620260909,
                "environment": "TEST",
                "data_plane": "SIMULATION",
            },
            "historical_p8_16": {
                "final_sha": gate.P8_16_FINAL_SHA,
                "provider_run_id": gate.P8_16_PROVIDER_RUN_ID,
                "required_validate_job_id": gate.P8_16_REQUIRED_VALIDATE_JOB_ID,
                "verdict": "NOT_READY",
                "check_summary": {
                    "check_count": 18,
                    "pass_count": 14,
                    "blocked_count": 4,
                    "error_count": 0,
                },
                "blocking_gaps": list(gate._P8_16_BLOCKERS),
                "reports": {
                    name: {
                        "report_version": version,
                        "report_fingerprint": fingerprint,
                    }
                    for name, (version, fingerprint) in gate._P8_16_REPORTS.items()
                },
            },
            "direct_dependency_p8_18": {
                "runtime_implementation_sha": gate.P8_18_RUNTIME_IMPLEMENTATION_SHA,
                "closure_sha": gate.DIFF_BASE,
                "provider_run_id": gate.P8_18_PROVIDER_RUN_ID,
                "required_validate_job_id": gate.P8_18_REQUIRED_VALIDATE_JOB_ID,
                "reports": {
                    name: {
                        "report_version": version,
                        "report_fingerprint": fingerprint,
                    }
                    for name, (
                        version,
                        fingerprint,
                    ) in gate._P8_18_PROVIDER_REPORTS.items()
                },
            },
            "platform_checks": checks,
            "closure_assertions": closures,
            "check_summary": {
                "platform_check_count": 18,
                "platform_pass_count": 18,
                "platform_blocked_count": 0,
                "closure_assertion_count": 4,
                "closure_pass_count": 4,
                "closure_blocked_count": 0,
                "error_count": 0,
            },
            "blocking_gaps": [],
            "issues": [],
            "scope": {
                "synthetic_engineering_requalification": True,
                "canonical_json_only": True,
                "real_data": False,
                "p7_reality_calibration": False,
                "production_ready": False,
                "capacity_or_sla": False,
                "demo_included": False,
                "third_party_connector": False,
            },
            "next": {
                "p8_exit_gate_task": "TASK-P8-17",
                "eligible_to_request": True,
                "p8_exit_gate_authorized": False,
                "automatic_start": False,
                "production_ready": False,
            },
            "evidence": {
                name: {
                    "report_version": version,
                    "report_fingerprint": f"sha256:{index:064x}",
                }
                for index, (name, version) in enumerate(
                    gate._SUPPORT_VERSIONS.items(), start=1
                )
            },
        }
    )


def test_requalification_reuses_exact_p8_16_profile_and_history() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    validated = gate.validate_requalification_profile(profile)

    assert validated["profile_fingerprint"] == gate.PROFILE_FINGERPRINT
    assert validated["engineering_thresholds"] == {
        "maximum_gate_runtime_ms": 120000,
        "maximum_single_chain_ms": 30000,
        "minimum_targeted_p8_tests": 283,
    }
    assert gate._PLATFORM_CHECK_IDS == tuple(gate.frozen_gate._EXPECTED_CHECK_IDS)
    assert len(gate._P8_16_REPORTS) == 6
    assert len(gate._P8_18_PROVIDER_REPORTS) == 7


def test_report_requires_18_checks_four_closures_and_empty_ready_gaps() -> None:
    report = _ready_report()
    gate.validate_requalification_report(report)

    blocked = deepcopy(report)
    blocked["platform_checks"][13]["status"] = "BLOCKED"
    blocked["closure_assertions"] = gate._closure_assertions(blocked["platform_checks"])
    blocked["blocking_gaps"] = gate._blocking_gaps(
        blocked["platform_checks"], blocked["closure_assertions"]
    )
    blocked["verdict"] = "NOT_READY"
    blocked["check_summary"] = {
        "platform_check_count": 18,
        "platform_pass_count": 17,
        "platform_blocked_count": 1,
        "closure_assertion_count": 4,
        "closure_pass_count": 3,
        "closure_blocked_count": 1,
        "error_count": 0,
    }
    blocked["next"]["eligible_to_request"] = False
    _seal(blocked)
    gate.validate_requalification_report(blocked)


def test_report_rejects_history_closure_skip_and_unpaired_gap_mutations() -> None:
    for mutate in (
        lambda report: report["historical_p8_16"].update({"verdict": "READY"}),
        lambda report: report["closure_assertions"].pop(),
        lambda report: report["platform_checks"][0].update({"status": "SKIPPED"}),
        lambda report: report["blocking_gaps"].append({"gap_id": "P8-UNPAIRED"}),
    ):
        report = deepcopy(_ready_report())
        mutate(report)
        _seal(report)
        with pytest.raises(
            gate.RequalificationError, match="REQUALIFICATION_REPORT_INVALID"
        ):
            gate.validate_requalification_report(report)


def test_profile_rejects_refingerprinted_threshold_or_boundary_change() -> None:
    source = json.loads(PROFILE.read_text(encoding="utf-8"))
    for path, value in (
        (("engineering_thresholds", "minimum_targeted_p8_tests"), 1),
        (("boundaries", "production_authorized"), True),
    ):
        mutated = deepcopy(source)
        mutated[path[0]][path[1]] = value
        projection = dict(mutated)
        projection.pop("profile_fingerprint")
        mutated["profile_fingerprint"] = canonical_fingerprint(projection)
        with pytest.raises(
            gate.RequalificationError, match="REQUALIFICATION_PROFILE_INVALID"
        ):
            gate.validate_requalification_profile(mutated)


def test_cli_missing_input_failure_is_payload_and_path_free(tmp_path: Path) -> None:
    report_path = tmp_path / "failure.json"
    missing = tmp_path / "private-customer-input.json"
    arguments = [
        "--root",
        str(ROOT),
        "--profile",
        str(missing),
        "--junit",
        str(missing),
    ]
    for name in gate._CURRENT_REPORTS:
        arguments.extend(("--" + name.replace("_", "-"), str(missing)))
    for option, filename in (
        ("--report", report_path.name),
        ("--blocker-disposition-report", "disposition.json"),
        ("--provenance-report", "provenance.json"),
        ("--compatibility-report", "compatibility.json"),
        ("--security-report", "security.json"),
        ("--recovery-report", "recovery.json"),
        ("--benchmark-report", "benchmark.json"),
    ):
        arguments.extend((option, str(tmp_path / filename)))

    assert gate.main(arguments) == 1
    failure = json.loads(report_path.read_text(encoding="utf-8"))
    serialized = report_path.read_text(encoding="utf-8")
    assert failure["audit_status"] == "ERROR"
    assert failure["verdict"] == "NOT_READY"
    assert failure["payload_included"] is False
    assert failure["path_included"] is False
    assert "private-customer-input" not in serialized
