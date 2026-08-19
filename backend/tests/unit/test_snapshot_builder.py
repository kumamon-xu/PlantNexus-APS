"""Unit evidence for immutable PlanningSnapshot v2 construction and hashing."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import cast

import pytest

from app.data_validation import validate_import_package
from app.domain.production import OrderExpansionResult, canonical_expansion_bytes
from app.normalization.order_expansion import expand_orders
from app.snapshots import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
    build_planning_snapshot,
    import_package_id_for,
    snapshot_hash_for,
    snapshot_hash_projection,
    verify_snapshot,
)

ROOT = Path(__file__).resolve().parents[3]
CUTOFF = "2026-08-20T00:00:00Z"


def _import_document(*, synthetic: bool = True) -> dict[str, object]:
    document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if not synthetic:
        document["synthetic"] = False
        document.pop("synthetic_provenance")
    document["package_id"] = import_package_id_for(document)
    return document


def _chain(
    document: dict[str, object] | None = None,
    *,
    cutoff: str = CUTOFF,
) -> tuple[dict[str, object], dict[str, object], OrderExpansionResult, ImmutablePlanningSnapshot]:
    import_document = document or _import_document()
    quality = cast(dict[str, object], validate_import_package(import_document).document)
    expansion = expand_orders(cast(object, import_document), quality)  # type: ignore[arg-type]
    snapshot = build_planning_snapshot(
        import_document,
        quality,
        expansion,
        cutoff_at_utc=cutoff,
    )
    return import_document, quality, expansion, snapshot


def _reordered_expansion(expansion: OrderExpansionResult) -> OrderExpansionResult:
    document = deepcopy(expansion.document)
    document["operation_instances"].reverse()
    document["operation_precedence_edges"].reverse()
    for instance in document["operation_instances"]:
        instance["resource_options"].reverse()
        instance["required_capabilities"].reverse()
        instance["lock_ids"].reverse()
    canonical_bytes = canonical_expansion_bytes(cast(dict[str, object], document))
    return OrderExpansionResult(
        document=document,
        canonical_bytes=canonical_bytes,
        expansion_hash=f"sha256:{sha256(canonical_bytes).hexdigest()}",
    )


def test_snapshot_hash_vector_round_trip_and_counts() -> None:
    import_document, quality, expansion, first = _chain()
    second = build_planning_snapshot(
        import_document,
        quality,
        expansion,
        cutoff_at_utc=CUTOFF,
    )

    assert first == second
    assert first.snapshot_hash == (
        "sha256:44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a"
    )
    assert first.snapshot_id == (
        "planning-snapshot-v2-44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a"
    )
    assert json.loads(first.canonical_bytes) == first.document
    assert first.document["import_package"]["dataset_hash"].startswith("sha256:")
    assert first.document["entity_counts"]["operation_instances"] == 2
    assert first.document["entity_counts"]["operation_precedence_edges"] == 1
    verify_snapshot(first)


def test_snapshot_orders_all_unordered_facts_and_expansion_values() -> None:
    document = _import_document()
    records = cast(dict[str, list[dict[str, object]]], document["records"])
    for collection, values in records.items():
        if collection != "canonical_records_version":
            values.reverse()
    cast(list[str], records["resources"][0]["capabilities"]).reverse()
    cast(list[str], records["routing_operations"][0]["required_capabilities"]).reverse()
    document["package_id"] = import_package_id_for(document)
    import_document, quality, expansion, reordered_import_snapshot = _chain(document)
    reordered_expansion_snapshot = build_planning_snapshot(
        import_document,
        quality,
        _reordered_expansion(expansion),
        cutoff_at_utc=CUTOFF,
    )
    baseline = _chain()[3]

    assert reordered_import_snapshot == baseline
    assert reordered_expansion_snapshot == baseline


def test_hash_projection_excludes_self_and_non_contract_transport_noise() -> None:
    snapshot = _chain()[3]
    noisy = cast(dict[str, object], deepcopy(snapshot.document))
    noisy["snapshot_id"] = "ignored-self-id"
    noisy["snapshot_hash"] = "sha256:" + "0" * 64
    noisy["received_at_utc"] = "2099-01-01T00:00:00Z"
    noisy["generated_at_utc"] = "2099-01-02T00:00:00Z"
    noisy["random_uuid"] = "ignored-runtime-noise"

    assert snapshot_hash_for(noisy) == snapshot.snapshot_hash
    projection = snapshot_hash_projection(noisy)
    assert "snapshot_id" not in projection
    assert "snapshot_hash" not in projection
    assert "received_at_utc" not in projection
    assert "generated_at_utc" not in projection
    assert projection["cutoff_at_utc"] == CUTOFF


def test_cutoff_fact_rule_and_version_changes_change_hash() -> None:
    baseline = _chain()[3]
    changed_cutoff = _chain(cutoff="2026-08-20T00:00:01Z")[3]

    changed_fact_document = _import_document()
    records = cast(dict[str, list[dict[str, object]]], changed_fact_document["records"])
    records["factories"][0]["factory_code"] = "F001-CHANGED"
    changed_fact_document["package_id"] = import_package_id_for(changed_fact_document)
    changed_fact = _chain(changed_fact_document)[3]

    changed_rule_document = _import_document()
    changed_rule_document["normalization_rule_version"] = "normalization.changed.v2"
    changed_rule_document["package_id"] = import_package_id_for(changed_rule_document)
    changed_rule = _chain(changed_rule_document)[3]

    changed_expansion_version = cast(dict[str, object], deepcopy(baseline.document))
    changed_expansion_version["expansion_version"] = "order-expansion.v2"

    assert changed_cutoff.snapshot_hash != baseline.snapshot_hash
    assert changed_fact.snapshot_hash != baseline.snapshot_hash
    assert changed_rule.snapshot_hash != baseline.snapshot_hash
    assert snapshot_hash_for(changed_expansion_version) != baseline.snapshot_hash


def test_snapshot_value_cannot_be_mutated_through_a_document_copy() -> None:
    snapshot = _chain()[3]
    document_copy = snapshot.document
    document_copy["records"]["factories"][0]["factory_code"] = "MUTATED"

    assert snapshot.document["records"]["factories"][0]["factory_code"] == "F001"
    assert snapshot.snapshot_hash.endswith("e591a")
    with pytest.raises(AttributeError):
        snapshot.snapshot_hash = "sha256:" + "0" * 64  # type: ignore[misc]


def test_builder_rejects_fail_report_stale_package_and_mismatched_expansion() -> None:
    import_document, quality, expansion, _snapshot = _chain()

    fail_report = deepcopy(quality)
    fail_report["status"] = "FAIL"
    with pytest.raises(SnapshotError) as failure:
        build_planning_snapshot(
            import_document,
            fail_report,
            expansion,
            cutoff_at_utc=CUTOFF,
        )
    assert failure.value.code is SnapshotErrorCode.QUALITY_REPORT_REQUIRED

    stale = deepcopy(import_document)
    stale_records = cast(dict[str, list[dict[str, object]]], stale["records"])
    stale_records["factories"][0]["factory_code"] = "UNBOUND-CHANGE"
    with pytest.raises(SnapshotError) as stale_error:
        build_planning_snapshot(stale, quality, expansion, cutoff_at_utc=CUTOFF)
    assert stale_error.value.code is SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH

    other = _import_document()
    other["normalization_rule_version"] = "normalization.other.v1"
    other["package_id"] = import_package_id_for(other)
    other_quality = cast(dict[str, object], validate_import_package(other).document)
    with pytest.raises(SnapshotError) as mismatch:
        build_planning_snapshot(
            other,
            other_quality,
            expansion,
            cutoff_at_utc=CUTOFF,
        )
    assert mismatch.value.code is SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH


def test_builder_rejects_invalid_cutoff_and_tampered_expansion_hash() -> None:
    import_document, quality, expansion, _snapshot = _chain()
    with pytest.raises(SnapshotError) as invalid_cutoff:
        build_planning_snapshot(
            import_document,
            quality,
            expansion,
            cutoff_at_utc="2026-08-20T08:00:00+08:00",
        )
    assert invalid_cutoff.value.code is SnapshotErrorCode.INVALID_SNAPSHOT_INPUT

    tampered = OrderExpansionResult(
        document=expansion.document,
        canonical_bytes=expansion.canonical_bytes,
        expansion_hash="sha256:" + "0" * 64,
    )
    with pytest.raises(SnapshotError) as invalid_expansion:
        build_planning_snapshot(
            import_document,
            quality,
            tampered,
            cutoff_at_utc=CUTOFF,
        )
    assert invalid_expansion.value.code is SnapshotErrorCode.SNAPSHOT_INPUT_MISMATCH


def test_production_snapshot_has_no_synthetic_provenance() -> None:
    production = _chain(_import_document(synthetic=False))[3]
    synthetic = _chain()[3]

    assert production.data_plane is SnapshotDataPlane.PRODUCTION
    assert production.document["synthetic"] is False
    assert "synthetic_provenance" not in production.document
    assert synthetic.data_plane is SnapshotDataPlane.SIMULATION
    assert synthetic.document.get("synthetic_provenance", {})["seed"] == 20260819


def test_verify_snapshot_rejects_tampered_bytes_and_plane() -> None:
    snapshot = _chain()[3]
    tampered_document = cast(dict[str, object], deepcopy(snapshot.document))
    tampered_document["cutoff_at_utc"] = "2026-08-20T00:00:01Z"
    tampered_bytes = json.dumps(
        tampered_document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    tampered = ImmutablePlanningSnapshot(
        canonical_bytes=tampered_bytes,
        snapshot_id=snapshot.snapshot_id,
        snapshot_hash=snapshot.snapshot_hash,
        data_plane=snapshot.data_plane,
    )
    with pytest.raises(SnapshotError) as hash_error:
        verify_snapshot(tampered)
    assert hash_error.value.code is SnapshotErrorCode.HASH_MISMATCH

    wrong_plane = ImmutablePlanningSnapshot(
        canonical_bytes=snapshot.canonical_bytes,
        snapshot_id=snapshot.snapshot_id,
        snapshot_hash=snapshot.snapshot_hash,
        data_plane=SnapshotDataPlane.PRODUCTION,
    )
    with pytest.raises(SnapshotError) as plane_error:
        verify_snapshot(wrong_plane)
    assert plane_error.value.code is SnapshotErrorCode.DATA_PLANE_MISMATCH
