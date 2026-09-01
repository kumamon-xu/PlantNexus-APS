"""Fail-closed aggregate-contract mutations for TASK-P6-09."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from tests.p6.p6_duration_gate_report import (
    P6DurationGateContractError,
    build_p6_duration_gate_manifest,
    run_p6_duration_vertical_slice_gate,
    validate_p6_duration_gate_manifest,
    validate_p6_duration_vertical_slice_report,
)


type JsonObject = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _refresh_report(report: JsonObject) -> None:
    report.pop("report_fingerprint", None)
    report["report_fingerprint"] = _fingerprint(report)


def _refresh_manifest(manifest: JsonObject) -> None:
    manifest.pop("manifest_fingerprint", None)
    manifest["manifest_fingerprint"] = _fingerprint(manifest)


@pytest.fixture(scope="module")
def valid_gate_pair(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[JsonObject, JsonObject]:
    report = run_p6_duration_vertical_slice_gate(
        root=ROOT,
        subreport_dir=tmp_path_factory.mktemp("p6-gate-contract-subreports"),
    )
    manifest = build_p6_duration_gate_manifest(report)
    validate_p6_duration_vertical_slice_report(report)
    validate_p6_duration_gate_manifest(manifest, report)
    return report, manifest


@pytest.mark.parametrize(
    ("_case_id", "mutate"),
    (
        ("unknown-field", lambda value: value.update({"unexpected": True})),
        ("failed-status", lambda value: value.update({"status": "FAIL"})),
        (
            "provider-app-drift",
            lambda value: value["dependency_evidence"][0].update(
                {"required_app_id": 1}
            ),
        ),
        (
            "owner-check-count-drift",
            lambda value: value["owner_replays"][0]["raw_safe_subreports"][
                "runtime"
            ].update({"check_count": 11}),
        ),
        (
            "semantic-projection-tamper",
            lambda value: value["owner_replays"][0]["raw_safe_subreports"][
                "monitoring"
            ]["semantic_projection"]["counts"].update({"automatic_actions": 1}),
        ),
        (
            "blocking-gap-injection",
            lambda value: value["blocking_gaps"].append(
                {"gap_id": "tampered", "status": "BLOCKING"}
            ),
        ),
        (
            "production-authority-injection",
            lambda value: value["boundaries"].update(
                {"production_authorized": True}
            ),
        ),
        (
            "scope-expansion",
            lambda value: value["scope_evidence"]["changed_paths"].append(
                ".github/workflows/ci.yml"
            ),
        ),
        (
            "negative-case-accepted",
            lambda value: value["negative_rejections"][0].update(
                {"status": "ACCEPTED"}
            ),
        ),
    ),
)
def test_gate_report_rejects_mutation(
    valid_gate_pair: tuple[JsonObject, JsonObject],
    _case_id: str,
    mutate: Any,
) -> None:
    report = deepcopy(valid_gate_pair[0])
    mutate(report)
    _refresh_report(report)
    with pytest.raises(P6DurationGateContractError):
        validate_p6_duration_vertical_slice_report(report)


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
        ("manifest-unknown-field", lambda value: value.update({"unknown": True})),
    ),
)
def test_gate_manifest_rejects_mutation(
    valid_gate_pair: tuple[JsonObject, JsonObject],
    _case_id: str,
    mutate: Any,
) -> None:
    manifest = deepcopy(valid_gate_pair[1])
    mutate(manifest)
    _refresh_manifest(manifest)
    with pytest.raises(P6DurationGateContractError):
        validate_p6_duration_gate_manifest(manifest, valid_gate_pair[0])
