"""Mutation and sanitized failure checks for TASK-P8-16."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.data_validation.canonical_ingress import canonical_fingerprint
from scripts import p8_headless_extension_platform_gate as gate
from tests.p8.test_p8_headless_extension_platform_gate import _ready_report, _seal


ROOT = Path(__file__).resolve().parents[2]


def test_report_rejects_dropped_check_and_unpaired_blocker() -> None:
    dropped = deepcopy(_ready_report())
    dropped["checks"].pop()
    dropped["check_summary"] = {
        "check_count": len(dropped["checks"]),
        "pass_count": len(dropped["checks"]),
        "blocked_count": 0,
        "error_count": 0,
    }
    _seal(dropped)
    with pytest.raises(gate.GateInputError, match="GATE_REPORT_INVALID"):
        gate.validate_gate_report(dropped)

    unpaired = deepcopy(_ready_report())
    unpaired["verdict"] = "NOT_READY"
    unpaired["blocking_gaps"] = [
        {
            "blocker_id": "P8-GATE-BLOCKER-HEADLESS-OUTPUT-003",
        }
    ]
    _seal(unpaired)
    with pytest.raises(gate.GateInputError, match="GATE_REPORT_INVALID"):
        gate.validate_gate_report(unpaired)

    unknown = deepcopy(_ready_report())
    unknown["unexpected"] = True
    _seal(unknown)
    with pytest.raises(gate.GateInputError, match="GATE_REPORT_INVALID"):
        gate.validate_gate_report(unknown)

    invalid_status = deepcopy(_ready_report())
    invalid_status["checks"][0]["status"] = "SKIPPED"
    _seal(invalid_status)
    with pytest.raises(gate.GateInputError, match="GATE_REPORT_INVALID"):
        gate.validate_gate_report(invalid_status)


def test_profile_rejects_mutation_even_if_refingerprinted() -> None:
    profile_path = (
        ROOT / "benchmarks/p8/headless-extension-platform-gate-profile.v1.json"
    )
    document = json.loads(profile_path.read_text(encoding="utf-8"))
    mutated = deepcopy(document)
    mutated["boundaries"]["production_authorized"] = True
    projection = dict(mutated)
    projection.pop("profile_fingerprint")
    mutated["profile_fingerprint"] = canonical_fingerprint(projection)

    with pytest.raises(gate.GateInputError, match="GATE_PROFILE_INVALID"):
        gate.validate_profile(mutated)

    for field, value in (
        ("developer_kit_archive_sha256", "sha256:" + "0" * 64),
        ("provider_run_id", 1),
    ):
        mutated = deepcopy(document)
        mutated["frozen_p8_15"][field] = value
        projection = dict(mutated)
        projection.pop("profile_fingerprint")
        mutated["profile_fingerprint"] = canonical_fingerprint(projection)
        with pytest.raises(gate.GateInputError, match="GATE_PROFILE_INVALID"):
            gate.validate_profile(mutated)

    mutated = deepcopy(document)
    mutated["engineering_thresholds"]["minimum_targeted_p8_tests"] = 1
    projection = dict(mutated)
    projection.pop("profile_fingerprint")
    mutated["profile_fingerprint"] = canonical_fingerprint(projection)
    with pytest.raises(gate.GateInputError, match="GATE_PROFILE_INVALID"):
        gate.validate_profile(mutated)


def test_cli_missing_input_failure_is_payload_and_path_free(tmp_path: Path) -> None:
    report_path = tmp_path / "failure.json"
    missing = tmp_path / "private-input-name.json"
    arguments = [
        "--root",
        str(ROOT),
        "--profile",
        str(missing),
        "--junit",
        str(missing),
    ]
    for name in gate._INPUT_REPORTS:
        arguments.extend(("--" + name.replace("_", "-"), str(missing)))
    arguments.extend(
        (
            "--report",
            str(report_path),
            "--provenance-report",
            str(tmp_path / "provenance.json"),
            "--compatibility-report",
            str(tmp_path / "compatibility.json"),
            "--security-report",
            str(tmp_path / "security.json"),
            "--recovery-report",
            str(tmp_path / "recovery.json"),
            "--benchmark-report",
            str(tmp_path / "benchmark.json"),
        )
    )

    assert gate.main(arguments) == 1
    failure = json.loads(report_path.read_text(encoding="utf-8"))
    serialized = report_path.read_text(encoding="utf-8")
    assert failure["audit_status"] != "PASS"
    assert failure["verdict"] == "NOT_READY"
    assert failure["payload_included"] is False
    assert failure["path_included"] is False
    assert "private-input-name" not in serialized
