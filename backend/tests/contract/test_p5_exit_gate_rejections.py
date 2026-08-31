"""TASK-P5-22 fail-closed provider, topology and phase-boundary contracts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from app.application import p5_exit_gate_audit as audit
from app.application.p5_exit_gate_audit import (
    P5ExitGateAuditError,
    validate_provider_observation,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def observation() -> dict[str, Any]:
    return json.loads(
        (ROOT / "docs/p5-exit-gate-audit-observations.v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_exact_provider_observation_is_accepted(
    observation: dict[str, Any],
) -> None:
    validate_provider_observation(observation)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (
            lambda value: value["branch_protection"].update(
                {"expected_app_id": 0}
            ),
            "required provider",
        ),
        (
            lambda value: value["task_topology"].update(
                {"selected_owners": ["TASK-P5-04"], "selected_count": 1}
            ),
            "terminal or selected topology",
        ),
        (
            lambda value: value["predecessor_provider_audit"].update(
                {"expired_artifact_count": 1}
            ),
            "expired_artifact_count",
        ),
        (
            lambda value: value["predecessor_provider_audit"]["runs"][0][
                "artifacts"
            ][0].update({"digest": "sha256:" + "0" * 64}),
            "run/artifact inventory",
        ),
        (
            lambda value: value["historical_failure_corrective_chain"][0].update(
                {"corrective_sha": "0" * 40}
            ),
            "failure/corrective chain",
        ),
        (
            lambda value: value["contracts"].update(
                {"formed_strategy": "DECOMPOSED"}
            ),
            "contract boundary",
        ),
        (
            lambda value: value["registers"].update(
                {"prod_open_status": "ALL_CLOSED"}
            ),
            "OPEN/SIM/risk",
        ),
        (
            lambda value: value["boundaries"].update(
                {"production_readiness": "READY"}
            ),
            "P5/P6/Production",
        ),
    ],
)
def test_observation_tamper_fails_closed(
    observation: dict[str, Any], mutation: Any, match: str
) -> None:
    value = deepcopy(observation)
    mutation(value)
    with pytest.raises(P5ExitGateAuditError, match=match):
        validate_provider_observation(value)


def test_cli_emits_not_ready_and_never_transitions_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs: list[Path] = []
    for name in ("provider", "qualification", "p5", "p4", "p4-exit"):
        path = tmp_path / f"{name}.json"
        path.write_text("{}\n", encoding="utf-8")
        inputs.append(path)
    report_path = tmp_path / "p5-exit-failed.json"

    def fail_audit(**_: object) -> dict[str, object]:
        raise P5ExitGateAuditError("synthetic", "bounded negative")

    monkeypatch.setattr(audit, "run_p5_exit_gate_audit", fail_audit)
    assert (
        audit.main(
            [
                "--root",
                str(ROOT),
                "--provider-observation",
                str(inputs[0]),
                "--qualification-report",
                str(inputs[1]),
                "--p5-gate-report",
                str(inputs[2]),
                "--p4-gate-report",
                str(inputs[3]),
                "--p4-exit-observation",
                str(inputs[4]),
                "--report",
                str(report_path),
            ]
        )
        == 1
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["decision"] == "NOT_READY"
    assert report["blocking_gaps"] == [
        {
            "gap_id": "P5-EXIT-GATE-AUDIT-001",
            "field": "synthetic",
            "status": "BLOCKING",
            "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_SHA",
        }
    ]
    assert report["boundaries"]["current_phase"] == "P5"
    assert report["boundaries"]["p6_plus"] == "NOT_ENTERED"
    assert report["boundaries"]["automatic_phase_transition"] == "PROHIBITED"
    assert report["implementation_provider"] == "NOT_ELIGIBLE"
