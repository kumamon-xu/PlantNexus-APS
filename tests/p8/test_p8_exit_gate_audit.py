"""Positive contract coverage for the independent TASK-P8-17 Exit audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import p8_exit_gate_audit as gate


ROOT = Path(__file__).resolve().parents[2]
OBSERVATION = ROOT / "docs/p8-exit-gate-audit-observations.v1.json"


def _observation() -> dict[str, Any]:
    return json.loads(OBSERVATION.read_text(encoding="utf-8"))


def _fresh_ready_report() -> dict[str, Any]:
    return {
        "report_version": "p8-headless-extension-platform-requalification-report.v1",
        "report_fingerprint": "sha256:" + "1" * 64,
        "task_id": "TASK-P8-19",
        "code_commit": "1" * 40,
        "audit_status": "PASS",
        "verdict": "READY",
        "check_summary": {
            "platform_check_count": 18,
            "platform_pass_count": 18,
            "platform_blocked_count": 0,
            "closure_assertion_count": 4,
            "closure_pass_count": 4,
            "closure_blocked_count": 0,
            "error_count": 0,
        },
        "issues": [],
        "blocking_gaps": [],
    }


def test_provider_observation_is_frozen_complete_and_on_current_lineage() -> None:
    observation = _observation()

    gate.validate_provider_observation(observation, ROOT)

    assert observation["observation_fingerprint"] == gate.OBSERVATION_FINGERPRINT
    assert observation["summary"] == {
        "provider_input_count": 20,
        "provider_task_count": 19,
        "artifact_count": 83,
        "entry_count": 1869,
        "retained_history_count": 9,
        "expired_artifact_count": 0,
        "digest_mismatch_count": 0,
        "unsafe_archive_count": 0,
        "issue_count": 0,
    }
    assert observation["task_topology"]["terminal_done_count"] == 19
    assert observation["task_topology"]["active_task"] == gate.TASK_ID


def test_exit_audit_requires_fresh_ready_replay_and_builds_bound_manifest(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    fresh = _fresh_ready_report()
    monkeypatch.setattr(
        gate, "run_p8_requalification_gate", lambda *args, **kwargs: fresh
    )
    monkeypatch.setattr(gate, "validate_requalification_report", lambda report: None)
    monkeypatch.setattr(
        gate,
        "_scope_evidence",
        lambda root: {
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
        },
    )
    input_paths = {name: tmp_path / f"{name}.json" for name in gate._INPUT_REPORTS}

    report = gate.run_exit_audit(
        root=ROOT,
        provider_observation=_observation(),
        profile_path=tmp_path / "profile.json",
        junit_path=tmp_path / "tests.xml",
        input_paths=input_paths,
        subreport_dir=tmp_path / "subreports",
    )
    manifest = gate.build_exit_manifest(report)

    gate.validate_exit_report(report)
    gate.validate_exit_manifest(manifest, report)
    assert report["decision"] == "READY"
    assert report["check_count"] == 20
    assert report["fresh_p8_19"]["platform_pass_count"] == 18
    assert report["fresh_p8_19"]["closure_pass_count"] == 4
    assert manifest["provider_binding"]["fresh_phase_gate_replay"] is True
    assert manifest["boundaries"]["production_ready"] is False


def test_public_product_owner_snapshot_preserves_headless_extension_boundaries() -> (
    None
):
    evidence = gate._public_owner_evidence(ROOT)

    assert evidence["accepted_adrs"] == ["ADR-0017", "ADR-0018"]
    assert evidence["schema_set_version"] == "2.10.0"
    assert evidence["migration_head"] == "0009_host_authorization_audit"
    assert evidence["extension_points"] == [
        "Constraint",
        "Objective",
        "Planning Rule",
        "Validation Rule",
        "Replan Policy",
        "Plugin Registry",
    ]


def test_task_scope_uses_working_tree_while_auditor_has_uncommitted_changes(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        gate,
        "_git",
        lambda root, *args, **kwargs: (
            " M scripts/p8_exit_gate_audit.py"
            if args[0] == "status"
            else "1" * 40
        ),
    )
    monkeypatch.setattr(
        gate, "_working_tree_paths", lambda root: sorted(gate._ALLOWED_TRACKED_PATHS)
    )

    paths, source, implementation_commit = gate._task_scope_paths(ROOT)

    assert paths == sorted(gate._ALLOWED_TRACKED_PATHS)
    assert source == "WORKING_TREE"
    assert implementation_commit == "1" * 40


def test_task_scope_binds_latest_committed_auditor_revision(monkeypatch: Any) -> None:
    latest = "2" * 40

    def fake_git(root: Path, *args: str, **kwargs: Any) -> str:
        if args[0] == "status":
            return ""
        if args[0] == "log":
            return latest
        if args[0] == "diff":
            assert args[-1] == f"{gate.DIFF_BASE}..{latest}"
            return "\n".join(sorted(gate._ALLOWED_TRACKED_PATHS))
        raise AssertionError(args)

    monkeypatch.setattr(gate, "_git", fake_git)

    paths, source, implementation_commit = gate._task_scope_paths(ROOT)

    assert paths == sorted(gate._ALLOWED_TRACKED_PATHS)
    assert source == "LATEST_EXIT_AUDIT_COMMIT"
    assert implementation_commit == latest
