"""Repository boundary for insert-only Raw Staging persistence."""

from __future__ import annotations

from typing import Protocol

from app.importers.contracts import (
    StagedImportBatch,
    StagingDataPlane,
    StagingWriteResult,
)


class ImportStagingRepository(Protocol):
    """No update/delete/canonical conversion exists on the staging boundary."""

    @property
    def data_plane(self) -> StagingDataPlane: ...

    def stage(self, batch: StagedImportBatch) -> StagingWriteResult: ...

    def get(self, batch_id: str) -> StagedImportBatch | None: ...


__all__ = ["ImportStagingRepository"]
