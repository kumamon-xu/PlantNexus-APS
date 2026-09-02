"""Fail-closed mutations for the independent TASK-P6-10 Exit audit."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from tests.p6.p6_exit_gate_audit import (
    P6ExitGateAuditError,
    build_p6_exit_gate_manifest,
    main,
    run_p6_exit_gate_audit,
    validate_p6_exit_gate_manifest,
    validate_p6_exit_gate_report,
    validate_provider_observation,
)


type JsonObject = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]
OBSERVATION_PATH = ROOT / "docs/p6-exit-gate-audit-observations.v1.json"


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _load_observation() -> JsonObject:
    value = json.loads(OBSERVATION_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _refresh(value: JsonObject, field: str) -> None:
    value.pop(field, None)
    value[field] = _fingerprint(value)


@pytest.fixture(scope="module")
def valid_exit_pair(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[JsonObject, JsonObject]:
    report = run_p6_exit_gate_audit(
        root=ROOT,
        provider_observation=_load_observation(),
        subreport_dir=tmp_path_factory.mktemp("p6-exit-contract-subreports"),
    )
    manifest = build_p6_exit_gate_manifest(report)
    validate_p6_exit_gate_report(report)
    validate_p6_exit_gate_manifest(manifest, report)
    return report, manifest


@pytest.mark.parametrize(
    ("_case_id", "mutate"),
    (
        (
            "task-status-drift",
            lambda value: value["task_topology"]["tasks"][9].update(
                {"status": "in_progress"}
            ),
        ),
        (
            "provider-app-drift",
            lambda value: value["provider_runs"][0]["required_check"].update(
                {"app_id": 1}
            ),
        ),
        (
            "provider-run-id-drift",
            lambda value: value["provider_runs"][0].update({"run_id": 1}),
        ),
        (
            "artifact-digest-mismatch",
            lambda value: value["provider_runs"][0]["artifacts"][0].update(
                {"digest_match": False}
            ),
        ),
        (
            "artifact-expired-at-activation",
            lambda value: value["provider_runs"][0]["artifacts"][0].update(
                {"expires_at": "2026-09-01T23:59:59Z"}
            ),
        ),
        (
            "failure-chain-rerun-substitution",
            lambda value: value["failure_corrective_chain"][0].update(
                {"rerun_used": True}
            ),
        ),
        (
            "register-closed-by-audit",
            lambda value: value["registers"]["closed_by_audit"].append("OPEN-001"),
        ),
        (
            "p7-boundary-injection",
            lambda value: value["boundaries"].update(
                {"p7_reality_calibration": "ENTERED"}
            ),
        ),
    ),
)
def test_provider_observation_rejects_mutation(
    _case_id: str,
    mutate: Any,
) -> None:
    observation = _load_observation()
    mutate(observation)
    _refresh(observation, "observation_fingerprint")
    with pytest.raises(P6ExitGateAuditError):
        validate_provider_observation(observation, ROOT)


@pytest.mark.parametrize(
    ("_case_id", "mutate"),
    (
        ("not-ready-substitution", lambda value: value.update({"decision": "NOT_READY"})),
        (
            "provider-inventory-drift",
            lambda value: value["provider_evidence"].update(
                {"provider_inventory_fingerprint": "sha256:" + "0" * 64}
            ),
        ),
        (
            "stale-gate-substitution",
            lambda value: value["fresh_p6_gate"].update({"repeat_count": 1}),
        ),
        (
            "check-identity-drift",
            lambda value: value["checks"][0].update({"check_id": "tampered"}),
        ),
        (
            "scope-expansion",
            lambda value: value["scope_evidence"]["changed_paths"].append(
                ".github/workflows/ci.yml"
            ),
        ),
        (
            "production-readiness-injection",
            lambda value: value["boundaries"].update(
                {"production_readiness": "CLAIMED"}
            ),
        ),
        ("unknown-field", lambda value: value.update({"unexpected": True})),
    ),
)
def test_exit_report_rejects_mutation(
    valid_exit_pair: tuple[JsonObject, JsonObject],
    _case_id: str,
    mutate: Any,
) -> None:
    report = deepcopy(valid_exit_pair[0])
    mutate(report)
    _refresh(report, "report_fingerprint")
    with pytest.raises(P6ExitGateAuditError):
        validate_p6_exit_gate_report(report)


@pytest.mark.parametrize(
    ("_case_id", "mutate"),
    (
        (
            "manifest-provider-app-drift",
            lambda value: value["provider_binding"].update({"required_app_id": 1}),
        ),
        (
            "manifest-report-fingerprint-drift",
            lambda value: value.update({"report_fingerprint": "sha256:" + "0" * 64}),
        ),
        ("manifest-not-ready", lambda value: value.update({"decision": "NOT_READY"})),
        ("manifest-unknown-field", lambda value: value.update({"unknown": True})),
    ),
)
def test_exit_manifest_rejects_mutation(
    valid_exit_pair: tuple[JsonObject, JsonObject],
    _case_id: str,
    mutate: Any,
) -> None:
    manifest = deepcopy(valid_exit_pair[1])
    mutate(manifest)
    _refresh(manifest, "manifest_fingerprint")
    with pytest.raises(P6ExitGateAuditError):
        validate_p6_exit_gate_manifest(manifest, valid_exit_pair[0])


def test_cli_emits_not_ready_and_blocking_gap_for_invalid_observation(
    tmp_path: Path,
) -> None:
    observation = _load_observation()
    observation["required_check"]["app_id"] = 1
    _refresh(observation, "observation_fingerprint")
    observation_path = tmp_path / "invalid-observation.json"
    report_path = tmp_path / "report.json"
    manifest_path = tmp_path / "manifest.json"
    observation_path.write_text(
        json.dumps(observation, ensure_ascii=False), encoding="utf-8"
    )

    exit_code = main(
        [
            "--root",
            str(ROOT),
            "--provider-observation",
            str(observation_path),
            "--report",
            str(report_path),
            "--manifest",
            str(manifest_path),
            "--subreport-dir",
            str(tmp_path / "subreports"),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["decision"] == "NOT_READY"
    assert report["issues"][0]["field"] == "observation.required_check"
    assert report["blocking_gaps"][0]["status"] == "BLOCKING"
    assert report["implementation_provider"] == "NOT_ELIGIBLE"
    assert manifest["decision"] == "NOT_READY"
    assert manifest["provider_binding"] == "NOT_ELIGIBLE"
