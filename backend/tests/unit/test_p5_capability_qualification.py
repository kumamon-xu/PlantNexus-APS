"""Unit and fail-closed tests for TASK-P5-01 qualification decisions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import cast

import pytest

from scripts.p5_capability_qualification import (
    EXPECTED_CANDIDATES,
    QualificationError,
    decide_record,
    load_qualification_bundle,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = "fixtures/simulation/p5/qualification/evidence-manifest.v1.json"


@pytest.fixture(scope="module")
def bundle():  # type: ignore[no-untyped-def]
    return load_qualification_bundle(ROOT)


def test_nine_records_are_complete_independent_and_fail_closed(bundle) -> None:  # type: ignore[no-untyped-def]
    decisions = [decide_record(record, bundle.profile) for record in bundle.records]
    assert tuple(row["candidate_id"] for row in decisions) == EXPECTED_CANDIDATES
    assert all(row["decision"] == "DEFERRED" for row in decisions)
    assert all(row["failed_selection_facts"] for row in decisions)
    assert all(row["evidence_gaps"] for row in decisions)
    assert len({row["decision_fingerprint"] for row in decisions}) == 9


def test_same_input_has_identical_decision_fingerprints(bundle) -> None:  # type: ignore[no-untyped-def]
    first = [decide_record(record, bundle.profile) for record in bundle.records]
    second = [decide_record(deepcopy(record), bundle.profile) for record in bundle.records]
    assert [row["decision_fingerprint"] for row in first] == [
        row["decision_fingerprint"] for row in second
    ]


def test_all_true_rule_selects_and_one_missing_fact_defers(bundle) -> None:  # type: ignore[no-untyped-def]
    selected = deepcopy(bundle.records[0])
    evidence = cast(dict[str, object], selected["evidence"])
    benchmark = cast(dict[str, object], evidence["benchmark"])
    benchmark["qualified"] = True
    selected["selection_facts"] = {
        "source_is_qualified": True,
        "source_replay_verified": True,
        "current_approximation_unacceptable": True,
        "candidate_specific_gate_passed": True,
        "policy_inputs_defined": True,
    }
    selected["expected_decision"] = "SELECTED"
    assert decide_record(selected, bundle.profile)["decision"] == "SELECTED"

    deferred = deepcopy(selected)
    cast(dict[str, object], deferred["selection_facts"])[
        "candidate_specific_gate_passed"
    ] = False
    deferred["expected_decision"] = "DEFERRED"
    decision = decide_record(deferred, bundle.profile)
    assert decision["decision"] == "DEFERRED"
    assert decision["failed_selection_facts"] == ["candidate_specific_gate_passed"]


def test_unknown_profile_and_declared_decision_mismatch_fail(bundle) -> None:  # type: ignore[no-untyped-def]
    unknown = deepcopy(bundle.profile)
    unknown["profile_version"] = "unknown-profile.v1"
    with pytest.raises(QualificationError, match="UNKNOWN_PROFILE"):
        decide_record(bundle.records[0], unknown)

    mismatched = deepcopy(bundle.records[0])
    mismatched["expected_decision"] = "SELECTED"
    with pytest.raises(QualificationError, match="DECISION_EXPECTATION_MISMATCH"):
        decide_record(mismatched, bundle.profile)


def test_real_simulation_and_benchmark_sources_cannot_be_mixed(bundle) -> None:  # type: ignore[no-untyped-def]
    mixed = deepcopy(bundle.records[0])
    evidence = cast(dict[str, object], mixed["evidence"])
    real = cast(dict[str, object], evidence["real_requirement"])
    real["source_ids"] = ["SIM-ASSUMPTION-013"]
    with pytest.raises(QualificationError, match="SOURCE_ISOLATION_VIOLATION"):
        decide_record(mixed, bundle.profile)


def _copy_manifest_assets(destination: Path) -> None:
    manifest_path = ROOT / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = [MANIFEST, manifest["profile"]["path"]]
    paths.extend(row["path"] for row in manifest["candidate_records"])
    paths.extend(row["path"] for row in manifest["source_assets"])
    for relative in paths:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_manifest_hash_mismatch_is_blocking(tmp_path: Path) -> None:
    _copy_manifest_assets(tmp_path)
    tampered = tmp_path / "fixtures/simulation/p5/qualification/batch-processing.v1.json"
    tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(QualificationError, match="EVIDENCE_HASH_MISMATCH"):
        load_qualification_bundle(tmp_path)


def test_manifest_declares_no_real_material_or_new_numeric_assumption(bundle) -> None:  # type: ignore[no-untyped-def]
    assert bundle.manifest["boundaries"] == {
        "real_requirement_material": "NOT_PROVIDED",
        "new_numeric_simulation_assumption": "NONE",
        "candidate_implementation": "PROHIBITED",
        "support_state_change": "PROHIBITED",
        "p5_02_auto_start": "PROHIBITED",
        "production_capacity_sla": "NOT_ESTABLISHED",
    }
