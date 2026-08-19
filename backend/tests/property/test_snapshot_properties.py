"""Generated replay and mutation properties for PlanningSnapshot v2."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import string
from typing import cast

from hypothesis import given, seed, settings
from hypothesis import strategies as st

from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.normalization.order_expansion import expand_orders
from app.snapshots import (
    ImmutablePlanningSnapshot,
    build_planning_snapshot,
    import_package_id_for,
    snapshot_hash_for,
)

ROOT = Path(__file__).resolve().parents[3]
CUTOFF = "2026-08-20T00:00:00Z"


def _import_document() -> dict[str, object]:
    document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["package_id"] = import_package_id_for(document)
    return document


def _build(
    document: dict[str, object], *, cutoff: str = CUTOFF
) -> ImmutablePlanningSnapshot:
    quality = validate_import_package(document).document
    expansion = expand_orders(cast(ImportPackageDocumentV2, document), quality)
    return build_planning_snapshot(
        document,
        quality,
        expansion,
        cutoff_at_utc=cutoff,
    )


@seed(20260820)
@settings(max_examples=32, deadline=None)
@given(reverse_flags=st.lists(st.booleans(), min_size=16, max_size=16))
def test_collection_permutations_preserve_bytes_hash_and_id(
    reverse_flags: list[bool],
) -> None:
    baseline_document = _import_document()
    permuted = deepcopy(baseline_document)
    records = cast(dict[str, object], permuted["records"])
    collections = sorted(key for key, value in records.items() if isinstance(value, list))
    for reverse, collection in zip(reverse_flags, collections, strict=True):
        if reverse:
            cast(list[object], records[collection]).reverse()
    if reverse_flags[0]:
        cast(
            list[str],
            cast(list[dict[str, object]], records["resources"])[0]["capabilities"],
        ).reverse()
    if reverse_flags[1]:
        cast(
            list[str],
            cast(list[dict[str, object]], records["routing_operations"])[0][
                "required_capabilities"
            ],
        ).reverse()
    permuted["package_id"] = import_package_id_for(permuted)

    baseline = _build(baseline_document)
    replay = _build(permuted)
    assert replay.canonical_bytes == baseline.canonical_bytes
    assert replay.snapshot_hash == baseline.snapshot_hash
    assert replay.snapshot_id == baseline.snapshot_id


@seed(20260821)
@settings(max_examples=32, deadline=None)
@given(
    suffix=st.text(alphabet=string.ascii_uppercase + string.digits, min_size=1, max_size=8)
)
def test_business_fact_mutation_is_deterministic_and_changes_hash(suffix: str) -> None:
    baseline = _build(_import_document())
    changed_document = _import_document()
    records = cast(dict[str, object], changed_document["records"])
    factories = cast(list[dict[str, object]], records["factories"])
    factories[0]["factory_code"] = f"F001-{suffix}"
    changed_document["package_id"] = import_package_id_for(changed_document)

    changed = _build(changed_document)
    replay = _build(deepcopy(changed_document))
    assert changed == replay
    assert changed.snapshot_hash != baseline.snapshot_hash
    assert changed.snapshot_id != baseline.snapshot_id


@seed(20260822)
@settings(max_examples=24, deadline=None)
@given(second=st.integers(min_value=1, max_value=59))
def test_cutoff_mutation_changes_hash_without_changing_facts(second: int) -> None:
    document = _import_document()
    baseline = _build(document)
    changed = _build(
        deepcopy(document), cutoff=f"2026-08-20T00:00:{second:02d}Z"
    )
    assert changed.document["records"] == baseline.document["records"]
    assert changed.snapshot_hash != baseline.snapshot_hash


@seed(20260823)
@settings(max_examples=24, deadline=None)
@given(
    received=st.text(max_size=32),
    generated=st.text(max_size=32),
    runtime_id=st.text(max_size=32),
)
def test_non_contract_runtime_noise_is_outside_hash_projection(
    received: str,
    generated: str,
    runtime_id: str,
) -> None:
    snapshot = _build(_import_document())
    noisy = cast(dict[str, object], deepcopy(snapshot.document))
    noisy["received_at"] = received
    noisy["generated_at"] = generated
    noisy["runtime_uuid"] = runtime_id
    noisy["snapshot_id"] = runtime_id
    noisy["snapshot_hash"] = "sha256:" + "f" * 64
    assert snapshot_hash_for(noisy) == snapshot.snapshot_hash
