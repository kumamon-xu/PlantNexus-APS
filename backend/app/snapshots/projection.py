"""Finalize a projected PlanningSnapshot v2 without mutating its predecessor."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import cast

from app.domain.canonical_records import (
    COLLECTION_ID_FIELDS,
    PlanningSnapshotDocumentV2,
    validate_planning_snapshot_v2,
)

from .canonical import (
    canonical_snapshot_bytes,
    snapshot_hash_for,
    snapshot_id_for_hash,
    verify_snapshot,
)
from .contracts import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
)


def build_projected_snapshot(
    projected_document: Mapping[str, object],
) -> ImmutablePlanningSnapshot:
    """Recompute counts, identity, hash and canonical bytes for one new Snapshot."""

    candidate = cast(dict[str, object], deepcopy(projected_document))
    records = cast(dict[str, object], candidate["records"])
    counts = {
        collection: len(cast(list[object], records[collection]))
        for collection in COLLECTION_ID_FIELDS
    }
    counts["operation_instances"] = len(
        cast(list[object], candidate["operation_instances"])
    )
    counts["operation_precedence_edges"] = len(
        cast(list[object], candidate["operation_precedence_edges"])
    )
    candidate["entity_counts"] = counts
    candidate.pop("snapshot_id", None)
    candidate.pop("snapshot_hash", None)
    snapshot_hash = snapshot_hash_for(candidate)
    snapshot_id = snapshot_id_for_hash(snapshot_hash)
    candidate["snapshot_id"] = snapshot_id
    candidate["snapshot_hash"] = snapshot_hash
    try:
        validate_planning_snapshot_v2(cast(PlanningSnapshotDocumentV2, candidate))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise SnapshotError(
            SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
            field=getattr(error, "field", "projected_snapshot"),
            expected_contract="valid projected planning-snapshot.v2",
            message="Projected facts failed Snapshot semantic validation",
        ) from error
    canonical_bytes = canonical_snapshot_bytes(candidate)
    snapshot = ImmutablePlanningSnapshot(
        canonical_bytes=canonical_bytes,
        snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash,
        data_plane=(
            SnapshotDataPlane.SIMULATION
            if candidate.get("synthetic") is True
            else SnapshotDataPlane.PRODUCTION
        ),
    )
    verify_snapshot(snapshot)
    return snapshot


__all__ = ["build_projected_snapshot"]
