"""TASK-P5-21 fail-closed portfolio and non-Exit contracts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.application import p5_portfolio_gate_report as gate
from app.application.p5_portfolio_gate_report import (
    P5PortfolioGateContractError,
    load_portfolio_manifest,
    run_p5_portfolio_gate,
    validate_portfolio_manifest,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def manifest() -> dict[str, object]:
    value, _ = load_portfolio_manifest(
        ROOT / "docs/core/p5-portfolio-amendment-manifest.md"
    )
    return value


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (
            lambda value: value["portfolio"].update(  # type: ignore[union-attr]
                {"selected": ["P5-CANDIDATE-BATCH"], "selected_count": 1}
            ),
            "empty selected",
        ),
        (
            lambda value: value["dispositions"][0].update(  # type: ignore[index,union-attr]
                {"decision_fingerprint": "sha256:" + "0" * 64}
            ),
            "decision identities",
        ),
        (
            lambda value: value["resolved_dag"].update(  # type: ignore[union-attr]
                {"p5_21_direct_dependencies": ["TASK-P5-04"]}
            ),
            "dependency topology",
        ),
        (
            lambda value: value["preserved_boundaries"].update(  # type: ignore[union-attr]
                {"formed_strategy": "DECOMPOSED"}
            ),
            "phase boundary",
        ),
    ],
)
def test_portfolio_tamper_fails_closed(
    manifest: dict[str, object], mutation: object, match: str
) -> None:
    value = deepcopy(manifest)
    mutation(value)  # type: ignore[operator]
    with pytest.raises(P5PortfolioGateContractError, match=match):
        validate_portfolio_manifest(value)


def test_public_manifest_requires_exactly_one_json_payload(tmp_path: Path) -> None:
    path = tmp_path / "manifest.md"
    path.write_text("~~~json\n{}\n~~~\n~~~json\n{}\n~~~\n", encoding="utf-8")
    with pytest.raises(P5PortfolioGateContractError, match="exactly one"):
        load_portfolio_manifest(path)


def test_gate_refuses_less_than_two_independent_p4_replays(
    manifest: dict[str, object],
) -> None:
    with pytest.raises(P5PortfolioGateContractError, match="at least two"):
        run_p5_portfolio_gate(
            root=ROOT,
            portfolio_manifest=manifest,
            portfolio_document_sha256="sha256:" + "0" * 64,
            frontend_report={},
            p2_report={},
            p3_report={},
            repeat=1,
        )


def test_unselected_capability_acceptance_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "require_v1_capability_contract", lambda _: ())
    with pytest.raises(P5PortfolioGateContractError, match="was accepted"):
        gate._unsupported_rejections()


def test_cli_preserves_blocking_gap_and_never_starts_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs: list[Path] = []
    for name in ("frontend", "p2", "p3"):
        path = tmp_path / f"{name}.json"
        path.write_text("{}\n", encoding="utf-8")
        inputs.append(path)
    report_path = tmp_path / "p5-failed.json"

    def fail_gate(**_: object) -> dict[str, object]:
        raise RuntimeError("bounded synthetic P5 Gate failure")

    monkeypatch.setattr(gate, "run_p5_portfolio_gate", fail_gate)
    assert (
        gate.main(
            [
                "--root",
                str(ROOT),
                "--portfolio-manifest",
                str(ROOT / "docs/core/p5-portfolio-amendment-manifest.md"),
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
            "gap_id": "P5-PORTFOLIO-GATE-EXECUTION-001",
            "stage": "gate-orchestrator",
            "status": "BLOCKING",
            "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_COMMIT",
        }
    ]
    assert report["boundaries"]["p5_22_exit_gate_audit"] == "NOT_STARTED"
    assert report["boundaries"]["p6_plus"] == "NOT_ENTERED"
    assert report["boundaries"]["production_identity_and_approval_authority"] == (
        "NOT_FORMED"
    )
