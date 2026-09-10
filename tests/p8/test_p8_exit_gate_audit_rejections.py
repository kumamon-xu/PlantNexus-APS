"""Fail-closed mutation coverage for TASK-P8-17 evidence carriers."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import p8_exit_gate_audit as gate


ROOT = Path(__file__).resolve().parents[2]
OBSERVATION = ROOT / "docs/p8-exit-gate-audit-observations.v1.json"


def _observation() -> dict[str, Any]:
    return json.loads(OBSERVATION.read_text(encoding="utf-8"))


def _seal(document: dict[str, Any], field: str) -> dict[str, Any]:
    gate._with_fingerprint(document, field)
    return document


def _ready_report() -> dict[str, Any]:
    observation = _observation()
    provider = deepcopy(observation["summary"])
    provider.update(
        {
            "observation_version": gate.OBSERVATION_VERSION,
            "observation_fingerprint": gate.OBSERVATION_FINGERPRINT,
            "required_context": "validate",
            "required_app_id": 15368,
        }
    )
    scope = {
        "status": "PASS",
        "diff_base": gate.DIFF_BASE,
        "scope_source": "WORKING_TREE",
        "implementation_commit": "1" * 40,
        "changed_paths": sorted(gate._ALLOWED_TRACKED_PATHS),
        "changed_path_count": len(gate._ALLOWED_TRACKED_PATHS),
        "exact_allow_list": sorted(gate._ALLOWED_TRACKED_PATHS),
        "unexpected_paths": [],
        "missing_paths": [],
        "impact_rules": list(gate.IMPACT_RULES),
        "product_source_changes": 0,
        "forbidden_owner_changes": 0,
    }
    fresh = {
        "report_version": "p8-headless-extension-platform-requalification-report.v1",
        "report_fingerprint": "sha256:" + "1" * 64,
        "report_sha256": "sha256:" + "2" * 64,
        "task_id": "TASK-P8-19",
        "code_commit": "1" * 40,
        "profile_fingerprint": gate.PROFILE_FINGERPRINT,
        "audit_status": "PASS",
        "verdict": "READY",
        "platform_check_count": 18,
        "platform_pass_count": 18,
        "platform_blocked_count": 0,
        "closure_assertion_count": 4,
        "closure_pass_count": 4,
        "closure_blocked_count": 0,
        "error_count": 0,
        "issues": [],
        "blocking_gaps": [],
    }
    return _seal(
        {
            "report_version": gate.REPORT_VERSION,
            "audit_task": gate.TASK_ID,
            "test_id": gate.TEST_ID,
            "task_status": "in_progress_ready_for_exact_provider",
            "code_commit": "1" * 40,
            "diff_base": gate.DIFF_BASE,
            "generated_at_utc": "2026-09-10T01:00:00+00:00",
            "duration_ms": 1.0,
            "validation_profile": gate.VALIDATION_PROFILE,
            "decision": "READY",
            "impact_rules": list(gate.IMPACT_RULES),
            "provider_evidence": provider,
            "task_topology": deepcopy(observation["task_topology"]),
            "public_owner_evidence": {},
            "fresh_p8_19": fresh,
            "registers": deepcopy(observation["registers"]),
            "scope_evidence": scope,
            "checks": [
                {"check_id": check_id, "status": "PASS", "evidence": {}}
                for check_id in gate.EXPECTED_CHECK_IDS
            ],
            "check_count": len(gate.EXPECTED_CHECK_IDS),
            "issues": [],
            "blocking_gaps": [],
            "boundaries": dict(gate._BOUNDARIES),
            "implementation_provider": "PENDING_EXACT_SHA",
        },
        "report_fingerprint",
    )


def test_observation_rejects_refingerprinted_run_app_and_inventory_mutations() -> None:
    for mutate in (
        lambda value: value["provider_inputs"][0].update({"run_id": 1}),
        lambda value: value["provider_inputs"][0].update({"required_app_id": 1}),
        lambda value: value["provider_inputs"].pop(),
    ):
        observation = deepcopy(_observation())
        mutate(observation)
        _seal(observation, "observation_fingerprint")
        with pytest.raises(gate.P8ExitGateAuditError):
            gate.validate_provider_observation(
                observation,
                ROOT,
                enforce_frozen_fingerprint=False,
            )


def test_observation_rejects_a_self_consistent_but_unfrozen_snapshot() -> None:
    observation = deepcopy(_observation())
    observation["collected_at_utc"] = "2026-09-10T02:00:00+00:00"
    _seal(observation, "observation_fingerprint")

    with pytest.raises(gate.P8ExitGateAuditError, match="PROVIDER_OBSERVATION_DRIFT"):
        gate.validate_provider_observation(observation, ROOT)


def test_exit_report_rejects_skips_gaps_and_production_claims() -> None:
    for mutate in (
        lambda value: value["checks"][0].update({"status": "SKIPPED"}),
        lambda value: value["blocking_gaps"].append({"gap_id": "P8-UNPAIRED"}),
        lambda value: value["boundaries"].update({"production_ready": True}),
        lambda value: value["fresh_p8_19"].update({"platform_pass_count": 17}),
    ):
        report = deepcopy(_ready_report())
        mutate(report)
        _seal(report, "report_fingerprint")
        with pytest.raises(gate.P8ExitGateAuditError):
            gate.validate_exit_report(report)


def test_manifest_rejects_report_and_provider_binding_drift() -> None:
    report = _ready_report()
    manifest = gate.build_exit_manifest(report)
    for mutate in (
        lambda value: value.update({"report_sha256": "sha256:" + "0" * 64}),
        lambda value: value["provider_binding"].update({"required_app_id": 0}),
    ):
        candidate = deepcopy(manifest)
        mutate(candidate)
        _seal(candidate, "manifest_fingerprint")
        with pytest.raises(gate.P8ExitGateAuditError):
            gate.validate_exit_manifest(candidate, report)


def test_cli_failure_is_payload_and_path_free(tmp_path: Path) -> None:
    report_path = tmp_path / "failure.json"
    manifest_path = tmp_path / "manifest.json"

    assert (
        gate.main(
            [
                "--root",
                str(ROOT),
                "--report",
                str(report_path),
                "--manifest",
                str(manifest_path),
            ]
        )
        == 1
    )
    serialized = report_path.read_text(encoding="utf-8")
    failure = json.loads(serialized)
    assert failure["decision"] == "NOT_READY"
    assert failure["issues"][0]["payload_included"] is False
    assert failure["issues"][0]["path_included"] is False
    assert str(ROOT) not in serialized
