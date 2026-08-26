"""TASK-P3-14 fail-closed P3 exit and non-Exit contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application import p3_gate_report
from app.application.p3_gate_report import (
    P3GateContractError,
    run_exit_rejection_checks,
    run_p3_vertical_slice_gate,
)


ROOT = Path(__file__).resolve().parents[3]


def test_four_exit_rejections_preserve_exact_stage_category_and_code() -> None:
    rows = run_exit_rejection_checks(ROOT)
    assert [row["case_id"] for row in rows] == [
        "DRAFT_CANNOT_PUBLISH",
        "REJECTED_CANNOT_PUBLISH",
        "PUBLISHED_CONTENT_CANNOT_MUTATE",
        "UNPUBLISHED_VERSION_CANNOT_EXPORT",
    ]
    assert [(row["stage"], row["category"], row["code"]) for row in rows] == [
        (
            "schedule_version.publication_precondition",
            "DATA_ERROR",
            "INVALID_STATE_TRANSITION",
        ),
        (
            "schedule_version.publication_precondition",
            "DATA_ERROR",
            "INVALID_STATE_TRANSITION",
        ),
        (
            "workspace_persistence.transition",
            "WORKSPACE_CONTROL",
            "STATE_CONFLICT",
        ),
        (
            "export_job.source_precondition",
            "WORKSPACE_CONTROL",
            "STALE_SOURCE",
        ),
    ]
    assert all(row["status"] == "PASS" for row in rows)
    assert all("REJECTED_BEFORE" in row["behavior"] for row in rows)


def test_gate_refuses_less_than_two_complete_replays() -> None:
    with pytest.raises(P3GateContractError, match="at least two complete replays"):
        run_p3_vertical_slice_gate(
            root=ROOT,
            frontend_report={},
            p2_report={},
            repeat=1,
        )


def test_cli_writes_fail_report_and_never_makes_an_exit_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frontend_path = tmp_path / "frontend.json"
    p2_path = tmp_path / "p2.json"
    report_path = tmp_path / "p3-failed.json"
    frontend_path.write_text("{}\n", encoding="utf-8")
    p2_path.write_text("{}\n", encoding="utf-8")

    def fail_gate(**_: object) -> dict[str, object]:
        raise RuntimeError("bounded synthetic P3 Gate failure")

    monkeypatch.setattr(p3_gate_report, "run_p3_vertical_slice_gate", fail_gate)
    assert (
        p3_gate_report.main(
            [
                "--root",
                str(ROOT),
                "--repeat",
                "2",
                "--frontend-report",
                str(frontend_path),
                "--p2-report",
                str(p2_path),
                "--report",
                str(report_path),
            ]
        )
        == 1
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["blocking_gaps"] == [
        {
            "gap_id": "P3-GATE-EXECUTION-001",
            "stage": "orchestrator",
            "status": "BLOCKING",
            "remediation": "REQUIRES_SEPARATE_BOUNDED_TASK",
        }
    ]
    assert report["boundaries"]["exit_gate_audit"] == "NOT_PERFORMED"
    assert report["boundaries"]["p3_15"] == "NOT_STARTED"
    assert report["boundaries"]["p4"] == "NOT_STARTED"
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"
