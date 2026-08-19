"""Repository boundary for content-addressed PlanningSnapshot persistence."""

from __future__ import annotations

from typing import Protocol

from .contracts import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotWriteResult,
)


class SnapshotRepository(Protocol):
    """Insert/replay and read only; mutation is absent from the domain boundary."""

    @property
    def data_plane(self) -> SnapshotDataPlane: ...

    def put(self, snapshot: ImmutablePlanningSnapshot) -> SnapshotWriteResult: ...

    def get_by_id(self, snapshot_id: str) -> ImmutablePlanningSnapshot | None: ...

    def get_by_hash(self, snapshot_hash: str) -> ImmutablePlanningSnapshot | None: ...


__all__ = ["SnapshotRepository"]
