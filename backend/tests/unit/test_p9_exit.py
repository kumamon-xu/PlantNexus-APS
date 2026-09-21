"""Exit cannot accept another candidate, missing coverage or repaired history."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts.p9_exit_gate_audit import (
    BLOCKED_CAPABILITIES,
    EXIT_CANDIDATE,
    exit_report,
    frozen_inputs,
    installed_boundaries,
)
from scripts.p9_runtime_vertical_gate import verdict


def inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ids = ["candidate", "fresh-contracts", "sealed-holdout", "readiness-contract"]
    ids += [f"B{i:02}" for i in range(1, 11)] + [f"op{i}" for i in range(34)]
    vertical = verdict(
        [{"check_id": i, "status": "PASS", "summary": i} for i in ids], "a" * 40
    )
    vertical.update(
        candidate={k: v for k, v in EXIT_CANDIDATE.items() if k != "contract"},
        audit_working_tree_dirty=False,
        fresh={"operation_rows": [{"operation_id": f"op{i}"} for i in range(34)]},
    )
    caps = {
        "checks": [
            {
                "capability": i,
                "error": "UNSUPPORTED_CAPABILITY",
                "registry_status": "UNSUPPORTED",
            }
            for i in BLOCKED_CAPABILITIES
        ]
    }
    return vertical, caps, {"status": "PASS"}


@pytest.mark.parametrize(
    "mutation",
    [
        "candidate",
        "audit_sha",
        "dirty",
        "missing_check",
        "duplicate_check",
        "missing_operation",
        "counts",
        "missing_capability",
        "issues",
    ],
)
def test_exit_rejects_invalid_identity_or_incomplete_coverage(mutation: str) -> None:
    vertical, caps, frozen = deepcopy(inputs())
    if mutation == "candidate":
        vertical["candidate"]["runtime_sha256"] = "0" * 64
    elif mutation == "audit_sha":
        vertical["code_commit"] = EXIT_CANDIDATE["source_revision"]
    elif mutation == "dirty":
        vertical["audit_working_tree_dirty"] = True
    elif mutation == "missing_check":
        vertical["checks"].pop()
    elif mutation == "duplicate_check":
        vertical["checks"][-1] = vertical["checks"][0]
    elif mutation == "missing_operation":
        vertical["fresh"]["operation_rows"].pop()
    elif mutation == "counts":
        vertical["check_summary"]["pass_count"] += 1
    elif mutation == "missing_capability":
        caps["checks"].pop()
    elif mutation == "issues":
        vertical["issues"] = ["unresolved"]
    with pytest.raises(ValueError, match="P9_EXIT"):
        exit_report(vertical, caps, frozen, "a" * 40)


@pytest.mark.parametrize("failure", ["none", "vertical", "capability", "frozen"])
def test_readiness_is_recomputed_and_never_advances_phase(failure: str) -> None:
    vertical, caps, frozen = inputs()
    if failure == "vertical":
        vertical["checks"][0]["status"] = "BLOCKED"
        vertical["check_summary"] = verdict(vertical["checks"], "a" * 40)[
            "check_summary"
        ]
    elif failure == "capability":
        caps["checks"][0]["error"] = None
    elif failure == "frozen":
        frozen["status"] = "BLOCKED"
    result = exit_report(vertical, caps, frozen, "a" * 40)
    assert result["verdict"] == ("READY" if failure == "none" else "NOT_READY")
    assert result["check_summary"]["check_count"] == 60
    assert result["task_id"] == "TASK-P9-12"
    assert result["boundaries"]["phase_transition"] is False
    assert result["boundaries"]["production"] is False


def test_installed_boundary_probe_and_protected_product_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    installed_boundaries(tmp_path)
    caps = json.loads((tmp_path / "exit-capabilities.json").read_bytes())
    assert len(caps["checks"]) == 11
    assert all(row["status"] == "PASS" for row in caps["checks"])
    monkeypatch.setattr(
        "scripts.p9_exit_gate_audit.subprocess.check_output", lambda *a, **k: ""
    )
    assert frozen_inputs(Path.cwd())["status"] == "PASS"
    monkeypatch.setattr(
        "scripts.p9_exit_gate_audit.subprocess.check_output",
        lambda *a, **k: "backend/app/changed.py\n",
    )
    assert frozen_inputs(Path.cwd())["status"] == "BLOCKED"
