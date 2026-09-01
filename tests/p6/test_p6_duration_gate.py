"""Non-skippable fresh vertical-slice evidence for TASK-P6-09."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.p6.p6_duration_gate_report import (
    DIFF_BASE,
    EXPECTED_CHECK_IDS,
    REPORT_VERSION,
    STAGE_ORDER,
    TASK_ID,
    build_p6_duration_gate_manifest,
    run_p6_duration_vertical_slice_gate,
    validate_p6_duration_gate_manifest,
    validate_p6_duration_vertical_slice_report,
)


ROOT = Path(__file__).resolve().parents[2]


def test_p6_duration_vertical_slice_fresh_two_run_gate(
    tmp_path: Path,
    record_testsuite_property: Any,
) -> None:
    report = run_p6_duration_vertical_slice_gate(
        root=ROOT,
        repeat=2,
        subreport_dir=tmp_path / "raw-safe-subreports",
    )
    manifest = build_p6_duration_gate_manifest(report)
    validate_p6_duration_vertical_slice_report(report)
    validate_p6_duration_gate_manifest(manifest, report)

    assert report["report_version"] == REPORT_VERSION
    assert report["task_id"] == TASK_ID
    assert report["diff_base"] == DIFF_BASE
    assert report["status"] == "PASS"
    assert report["repeat_count"] == 2
    assert report["stage_order"] == list(STAGE_ORDER)
    assert report["check_count"] == len(EXPECTED_CHECK_IDS)
    assert report["issues"] == []
    assert report["blocking_gaps"] == []
    assert report["boundaries"]["default_enabled"] is False
    assert report["boundaries"]["production_authorized"] is False
    assert report["scope_evidence"]["forbidden_owner_changes"] == 0

    semantic = report["semantic_consistency"]["combined_fingerprints"][0]
    properties = {
        "p6_gate_report_version": REPORT_VERSION,
        "p6_gate_task_id": TASK_ID,
        "p6_gate_diff_base": DIFF_BASE,
        "p6_gate_code_commit": report["code_commit"],
        "p6_gate_validation_profile": report["validation_profile"],
        "p6_gate_status": report["status"],
        "p6_gate_repeat_count": report["repeat_count"],
        "p6_gate_stage_count": len(STAGE_ORDER),
        "p6_gate_check_count": report["check_count"],
        "p6_gate_issues": json.dumps(report["issues"], separators=(",", ":")),
        "p6_gate_blocking_gaps": json.dumps(
            report["blocking_gaps"], separators=(",", ":")
        ),
        "p6_gate_semantic_fingerprint": semantic,
        "p6_gate_report_fingerprint": report["report_fingerprint"],
        "p6_gate_manifest_fingerprint": manifest["manifest_fingerprint"],
        "p6_gate_provider_binding": manifest["provider_binding"][
            "gate_execution_evidence"
        ],
    }
    for name, value in properties.items():
        record_testsuite_property(name, str(value))
