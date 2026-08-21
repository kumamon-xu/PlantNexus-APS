"""TASK-P2-13 fail-closed public-boundary and non-Exit contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.p2_gate_report import (
    P2GateContractError,
    main,
    run_exit_rejection_checks,
    run_p2_vertical_slice_gate,
)


ROOT = Path(__file__).resolve().parents[3]


def test_four_unsupported_invalid_and_limit_cases_are_exact() -> None:
    rows = run_exit_rejection_checks()
    assert [row["case_id"] for row in rows] == [
        "UNSUPPORTED_CAPABILITY",
        "INVALID_PLANNING_PROBLEM",
        "INVALID_SOLVE_LIMITS",
        "NO_SOLUTION_WITHIN_LIMIT",
    ]
    assert all(row["status"] == "PASS" for row in rows)
    assert [(row["category"], row["code"]) for row in rows] == [
        ("UNSUPPORTED_CAPABILITY", "UNSUPPORTED_CAPABILITY"),
        ("MODEL_INVALID", "MODEL_INVALID"),
        ("MODEL_INVALID", "MODEL_INVALID"),
        ("NO_SOLUTION_WITHIN_LIMIT", "NO_SOLUTION_WITHIN_LIMIT"),
    ]
    assert rows[0]["behavior"] == "REJECTED_BEFORE_PLANNING"
    assert rows[0]["details"]["capabilities"] == ["SECONDARY_CAPACITY"]
    assert rows[1]["behavior"] == "REJECTED_BEFORE_SOLVER"
    assert rows[2]["details"] == {
        "reason": "INVALID_METRIC",
        "field": "max_wall_time_seconds",
        "expected_contract": "finite number > 0",
    }
    assert rows[3]["behavior"] == "NO_CANDIDATE_AND_NOT_INFEASIBLE"
    assert rows[3]["details"] == {
        "solver_status": "UNKNOWN",
        "planning_run_state": "NO_SOLUTION_WITHIN_LIMIT",
        "candidate_available": False,
    }


def test_gate_refuses_less_than_two_complete_replays() -> None:
    with pytest.raises(P2GateContractError, match="at least two complete replays"):
        run_p2_vertical_slice_gate(root=ROOT, repeat=1)


def test_cli_repeat_rejection_is_nonzero_and_never_an_exit_decision(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "repeat-rejected.json"
    assert (
        main(
            [
                "--root",
                str(ROOT),
                "--repeat",
                "1",
                "--report",
                str(report_path),
            ]
        )
        == 1
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["error"]["error_type"] == "P2GateContractError"
    assert report["blocking_gaps"][0]["status"] == "BLOCKING"
    assert report["boundaries"]["exit_gate_decision"] == "NOT_PERFORMED"
    assert report["boundaries"]["p2_14"] == "NOT_STARTED"
    assert report["boundaries"]["p3"] == "NOT_STARTED"
