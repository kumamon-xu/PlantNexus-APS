"""Audit completeness and explicit negative Gate evidence cannot fail open."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any
import pytest
from scripts.p9_runtime_vertical_gate import operations, verdict
from scripts.ci_execution import check_report


def test_missing_operation_polarity_is_not_inferred_from_inventory() -> None:
    api = {
        "paths": {
            f"/r/{i}": {"get": {"operationId": f"op{i}", "responses": {"200": {}}}}
            for i in range(34)
        }
    }
    rows = operations(
        api, [{"method": "GET", "path": "/r/0", "status": 200, "test_id": "one"}]
    )
    assert all(r["status"] == "NOT_RUN" for r in rows)
    rows = operations(
        api,
        [
            {"method": "GET", "path": "/r/0", "status": status, "test_id": "one"}
            for status in (200, 403)
        ],
    )
    assert rows[0]["status"] == "PASS" and rows[0]["undeclared_statuses"] == ["403"]
    api["paths"].pop("/r/0")
    with pytest.raises(ValueError, match="INVENTORY"):
        operations(api, [])


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "sha",
        "task",
        "audit",
        "issues",
        "summary",
        "empty",
        "result",
        "filename",
    ],
)
def test_negative_gate_preserves_exact_identity_and_all_blockers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    for key, value in {
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
    }.items():
        monkeypatch.setenv(key, value)
    report: dict[str, Any] = verdict(
        [
            {
                "check_id": "readiness",
                "status": "BLOCKED",
                "summary": "Missing declared 503 response",
            }
        ],
        "a" * 40,
    )
    original = deepcopy(report)
    if mutation == "sha":
        report["code_commit"] = "b" * 40
    if mutation == "task":
        report["task_id"] = "TASK-P9-10"
    if mutation == "audit":
        report["audit_status"] = "FAIL"
    if mutation == "issues":
        report["issues"] = ["error"]
    if mutation == "summary":
        report["check_summary"]["blocked_count"] = 0
    if mutation == "empty":
        report["blocking_gaps"] = []
    if mutation == "result":
        report["result"] = "FAIL"
    path = tmp_path / (
        "unrelated.json" if mutation == "filename" else "ci-p9-vertical.json"
    )
    path.write_text(json.dumps(report), encoding="utf-8")
    if mutation == "none":
        check_report(path)
        assert json.loads(path.read_bytes()) == original
        assert original["verdict"] == "NOT_READY"
    else:
        with pytest.raises(ValueError):
            check_report(path)


def test_changed_candidate_and_existing_evidence_fail_before_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import p9_runtime_vertical_gate as gate

    monkeypatch.setattr(
        gate.subprocess,
        "check_output",
        lambda args, **kwargs: "a" * 40 if args[1] == "rev-parse" else "",
    )
    package = tmp_path / "changed.zip"
    package.write_bytes(b"wrong candidate")
    output = tmp_path / "audit"
    with pytest.raises(ValueError, match="CANDIDATE_DIGEST_MISMATCH"):
        gate.audit(tmp_path, output, package, package, "redis://127.0.0.1:1", "a" * 40)
    before = (output / "audit-input.json").read_bytes()
    with pytest.raises(FileExistsError):
        gate.audit(tmp_path, output, package, package, "redis://127.0.0.1:1", "a" * 40)
    assert (output / "audit-input.json").read_bytes() == before


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "source_revision",
        "runtime_version",
        "kit_version",
        "kit_sha256",
        "contract",
    ],
)
def test_corrective_identity_rejects_mixed_or_unbound_candidates(
    tmp_path: Path, fault: str | None
) -> None:
    from scripts.p9_runtime_vertical_gate import candidate_identity, RETAINED_CANDIDATE

    value = {
        **RETAINED_CANDIDATE,
        "source_revision": "a" * 40,
        "runtime_version": "0.2.1",
        "kit_version": "1.1.1",
    }
    if fault:
        value[fault] = "incorrect"
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    if fault:
        with pytest.raises(ValueError, match="CANDIDATE_IDENTITY_INVALID"):
            candidate_identity(path, "a" * 40)
    else:
        assert candidate_identity(path, "a" * 40) == value
    assert candidate_identity(None, "a" * 40) == RETAINED_CANDIDATE


@pytest.mark.parametrize(
    "fault", [None, "description", "200", "extra", "operation", "route"]
)
def test_readiness_addition_preserves_every_old_operation_byte(
    fault: str | None,
) -> None:
    from app.api.headless_api_check import _preserves_operation, _operation_hash

    old: dict[str, Any] = {
        "operationId": "ready",
        "responses": {"200": {"description": "OK"}},
    }
    row = {
        "method": "GET",
        "path": "/health/ready",
        "operation_sha256": _operation_hash(old),
    }
    assert _preserves_operation(old, row)
    new = deepcopy(old)
    new["responses"]["503"] = {"description": "Required dependency is not ready"}
    if fault == "description":
        new["responses"]["503"]["description"] = "different"
    if fault == "200":
        new["responses"]["200"] = {}
    if fault == "extra":
        new["responses"]["418"] = {}
    if fault == "operation":
        new["operationId"] = "changed"
    if fault == "route":
        row["path"] = "/other"
    assert _preserves_operation(new, row) is (fault is None)
