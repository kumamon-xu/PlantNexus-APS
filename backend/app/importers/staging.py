"""Pure Raw Staging assembly; adapters remain responsible for source reading."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from app.importers.contracts import (
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)


def build_staged_import_batch(
    *,
    batch_id: str,
    idempotency_key: str,
    source_system: str,
    source_version: str,
    content_sha256: str,
    source_name: str,
    media_type: str,
    content_length_bytes: int,
    received_at: datetime,
    data_plane: StagingDataPlane,
    rows: Iterable[RawImportRow],
    synthetic_provenance: SyntheticImportProvenance | None = None,
) -> StagedImportBatch:
    """Freeze opaque row bytes and provenance without parsing business values."""

    return StagedImportBatch(
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        source_system=source_system,
        source_version=source_version,
        content_sha256=content_sha256,
        source_name=source_name,
        media_type=media_type,
        content_length_bytes=content_length_bytes,
        received_at=received_at,
        data_plane=data_plane,
        rows=tuple(rows),
        synthetic_provenance=synthetic_provenance,
    )


__all__ = ["build_staged_import_batch"]
