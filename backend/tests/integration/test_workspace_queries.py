"""TASK-P3-05 actual SQLite repository/query integration evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from app.application.workspace_read_model_check import (
    main as workspace_read_model_main,
    run_workspace_read_model_checks,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_OBS_ID = "TEST-OBS-001"
TEST_SIM_ISOLATION_ID = "TEST-SIM-ISOLATION"


def test_versioned_repository_reads_are_complete_and_side_effect_free() -> None:
    report = run_workspace_read_model_checks(ROOT)
    assert report["status"] == "PASS"
    assert report["check_count"] == 8
    counts = cast(dict[str, object], report["counts"])
    assert counts["workspace_views"] == 14
    assert counts["product_service_solver_invocations"] == 0
    boundary = cast(dict[str, object], report["boundaries"])
    assert boundary["repository_writes_from_queries"] == "FORBIDDEN_AND_ABSENT"
    assert boundary["change_report_replan"] == "NOT_IMPLEMENTED"
    assert TEST_OBS_ID == "TEST-OBS-001"
    assert TEST_SIM_ISOLATION_ID == "TEST-SIM-ISOLATION"


def test_read_model_cli_emits_required_machine_report(tmp_path: Path) -> None:
    report_path = tmp_path / "p3-workspace-read-models.json"
    assert (
        workspace_read_model_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-workspace-read-model-report.v1"
    assert report["task_id"] == "TASK-P3-05"
    assert report["status"] == "PASS"
    assert report["check_count"] == 8
    assert report["issues"] == []
