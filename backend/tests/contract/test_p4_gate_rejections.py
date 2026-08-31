"""TASK-P4-14 fail-closed P4 Gate and non-Exit contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application import p4_gate_report
from app.application.p4_gate_report import P4GateContractError, run_p4_vertical_slice_gate


ROOT = Path(__file__).resolve().parents[3]


def _replay_boundary_fixture() -> dict[str, object]:
    return {
        "raw_subreports": {
            "disruption_replay": {
                "counts": {"negative_vectors": 3},
                "boundaries": {"p5_plus": "UNSUPPORTED"},
            },
            "replanning_api": {
                "boundaries": {
                    "production_authority": "DEFAULT_DENY_OPEN_010_015"
                }
            },
            "replan_application": {
                "boundaries": {
                    "result_schedule_state": "DRAFT_ONLY",
                    "approval_publish_export": "NOT_INVOKED",
                }
            },
        }
    }


def test_four_fail_closed_rejection_boundaries_are_exact() -> None:
    rows = p4_gate_report._rejection_cases(_replay_boundary_fixture())
    assert [row["case_id"] for row in rows] == [
        "TAMPER_COVERAGE_AND_PLANE_FAIL_CLOSED",
        "PRODUCTION_AUTHORITY_DEFAULT_DENY",
        "P5_CAPABILITY_UNSUPPORTED",
        "PARTIAL_RESULT_CANNOT_ADVANCE_STATE",
    ]
    assert all(row["status"] == "PASS" for row in rows)


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("disruption_replay", "counts", "negative_vectors"), 2, "negative vectors"),
        (
            ("replanning_api", "boundaries", "production_authority"),
            "FORMED",
            "default deny",
        ),
        (("disruption_replay", "boundaries", "p5_plus"), "SUPPORTED", "P5"),
        (
            ("replan_application", "boundaries", "result_schedule_state"),
            "VALIDATED",
            "partial result",
        ),
    ],
)
def test_each_rejection_boundary_fails_closed(
    path: tuple[str, str, str], value: object, match: str
) -> None:
    replay = _replay_boundary_fixture()
    reports = replay["raw_subreports"]
    assert isinstance(reports, dict)
    report = reports[path[0]]
    assert isinstance(report, dict)
    section = report[path[1]]
    assert isinstance(section, dict)
    section[path[2]] = value
    with pytest.raises(P4GateContractError, match=match):
        p4_gate_report._rejection_cases(replay)


def test_gate_refuses_less_than_two_complete_replays() -> None:
    with pytest.raises(P4GateContractError, match="at least two complete replays"):
        run_p4_vertical_slice_gate(
            root=ROOT,
            frontend_report={},
            p2_report={},
            p3_report={},
            repeat=1,
        )


def test_cli_writes_blocking_gap_and_never_makes_an_exit_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = []
    for name in ("frontend", "p2", "p3"):
        path = tmp_path / f"{name}.json"
        path.write_text("{}\n", encoding="utf-8")
        inputs.append(path)
    report_path = tmp_path / "p4-failed.json"

    def fail_gate(**_: object) -> dict[str, object]:
        raise RuntimeError("bounded synthetic P4 Gate failure")

    monkeypatch.setattr(p4_gate_report, "run_p4_vertical_slice_gate", fail_gate)
    assert (
        p4_gate_report.main(
            [
                "--root",
                str(ROOT),
                "--repeat",
                "2",
                "--frontend-report",
                str(inputs[0]),
                "--p2-report",
                str(inputs[1]),
                "--p3-report",
                str(inputs[2]),
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
            "gap_id": "P4-VERTICAL-GATE-EXECUTION-001",
            "stage": "gate-orchestrator",
            "status": "BLOCKING",
            "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_COMMIT",
        }
    ]
    assert report["boundaries"]["exit_gate_audit"] == "NOT_PERFORMED"
    assert report["boundaries"]["p4_15"] == "NOT_STARTED"
    assert report["boundaries"]["p5_plus"] == "UNSUPPORTED"
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"
