"""Immutable PlanningSnapshot boundary with cycle-safe lazy exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import (
    ImmutablePlanningSnapshot,
    PlanningSnapshotDocument,
    PlanningSnapshotDocumentV2,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
    SnapshotWriteResult,
)

if TYPE_CHECKING:
    from .builder import build_planning_snapshot
    from .canonical import (
        SNAPSHOT_CANONICALIZATION_VERSION,
        SNAPSHOT_HASH_PROJECTION_VERSION,
        SNAPSHOT_SCHEMA_SET_VERSION,
        SNAPSHOT_VERSION,
        canonical_snapshot_bytes,
        import_dataset_hash_for,
        import_package_id_for,
        snapshot_hash_for,
        snapshot_hash_projection,
        snapshot_id_for_hash,
        verify_snapshot,
    )
    from .repository import SnapshotRepository

_CANONICAL_EXPORTS = {
    "SNAPSHOT_CANONICALIZATION_VERSION",
    "SNAPSHOT_HASH_PROJECTION_VERSION",
    "SNAPSHOT_SCHEMA_SET_VERSION",
    "SNAPSHOT_VERSION",
    "canonical_snapshot_bytes",
    "import_dataset_hash_for",
    "import_package_id_for",
    "snapshot_hash_for",
    "snapshot_hash_projection",
    "snapshot_id_for_hash",
    "verify_snapshot",
}


def __getattr__(name: str) -> object:
    if name == "build_planning_snapshot":
        from .builder import build_planning_snapshot

        return build_planning_snapshot
    if name == "SnapshotRepository":
        from .repository import SnapshotRepository

        return SnapshotRepository
    if name in _CANONICAL_EXPORTS:
        from . import canonical

        return getattr(canonical, name)
    raise AttributeError(name)


__all__ = [
    "SNAPSHOT_CANONICALIZATION_VERSION",
    "SNAPSHOT_HASH_PROJECTION_VERSION",
    "SNAPSHOT_SCHEMA_SET_VERSION",
    "SNAPSHOT_VERSION",
    "ImmutablePlanningSnapshot",
    "PlanningSnapshotDocument",
    "PlanningSnapshotDocumentV2",
    "SnapshotDataPlane",
    "SnapshotError",
    "SnapshotErrorCode",
    "SnapshotRepository",
    "SnapshotWriteResult",
    "build_planning_snapshot",
    "canonical_snapshot_bytes",
    "import_dataset_hash_for",
    "import_package_id_for",
    "snapshot_hash_for",
    "snapshot_hash_projection",
    "snapshot_id_for_hash",
    "verify_snapshot",
]
