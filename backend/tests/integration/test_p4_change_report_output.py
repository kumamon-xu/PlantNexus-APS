"""TASK-P4-11 end-to-end read, ExportJob, package, and download evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from app.exporters.change_report_output_check import main


ROOT = Path(__file__).resolve().parents[3]


def test_machine_evidence_runs_real_durable_read_export_and_verified_download(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    implementation_sha = "1" * 40
    monkeypatch.setenv("PLANTNEXUS_CODE_COMMIT", implementation_sha)
    report_path = tmp_path / "p4-change-report-output.json"
    assert main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = cast(
        dict[str, object], json.loads(report_path.read_text(encoding="utf-8"))
    )

    assert report["report_version"] == "p4-change-report-output-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-11"
    assert report["code_commit"] == implementation_sha
    assert report["diff_base"] == "45b12d9a67ce5ef1680a47fecdc68705355af226"
    assert report["check_count"] == 8
    assert report["issues"] == []
    checks = {
        cast(str, check["name"]): cast(dict[str, object], check["evidence"])
        for check in cast(list[dict[str, object]], report["checks"])
    }
    assert set(checks) == {
        "durable-versioned-change-report-read-model",
        "stable-filter-cursor-exact-replay-and-zero-solver-side-effect",
        "complete-change-report-replan-schedule-artifact-lineage",
        "v3-export-job-existing-state-idempotency-and-audit",
        "deterministic-canonical-json-csv-five-sheet-xlsx-manifest-binding",
        "manifest-last-replay-tamper-conflict-and-partial-cleanup",
        "verified-exported-only-download-and-default-deny-boundary",
        "p4-p5-production-and-frozen-history-boundary",
    }
    assert checks["durable-versioned-change-report-read-model"][
        "solver_invocations"
    ] == 0
    lifecycle = checks["v3-export-job-existing-state-idempotency-and-audit"]
    assert lifecycle["state"] == "EXPORTED"
    assert lifecycle["attempt"] == 1
    assert lifecycle["create_exact_replay"] is True
    assert lifecycle["download_verified"] is True
    package = checks[
        "deterministic-canonical-json-csv-five-sheet-xlsx-manifest-binding"
    ]
    assert package["file_count"] == 13
    assert package["sheet_count"] == 5
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "publishable": False,
        "target": "SIMULATION_INTERNAL",
        "automatic_publish_export": "NOT_INVOKED",
        "schedule_version_state_pairs": "UNCHANGED",
        "export_job_state_pairs": "UNCHANGED",
        "p3_v1_v2_bytes": "FROZEN",
        "schema_migration_dependency": "UNCHANGED",
        "http_ui_p4_12_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
