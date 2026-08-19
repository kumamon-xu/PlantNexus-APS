"""Immutable Raw Staging values and stable, sanitized error semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import json
import re

_SHA256 = re.compile(r"[0-9a-f]{64}")


class StagingDataPlane(StrEnum):
    """The two business-data planes accepted by Raw Staging."""

    PRODUCTION = "production"
    SIMULATION = "simulation"


class StagingErrorCode(StrEnum):
    """Stable staging control-flow codes; raw values never enter messages."""

    INVALID_STAGING_METADATA = "INVALID_STAGING_METADATA"
    INVALID_CONTENT_DIGEST = "INVALID_CONTENT_DIGEST"
    DUPLICATE_ROW_IDENTITY = "DUPLICATE_ROW_IDENTITY"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    STAGING_TRANSACTION_FAILED = "STAGING_TRANSACTION_FAILED"


class ImportStagingError(ValueError):
    """A deterministic Raw Staging rejection safe for an operator or log."""

    def __init__(self, code: StagingErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code.value}: {message}")


def _require_text(value: str, *, field: str, maximum: int = 256) -> None:
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ImportStagingError(
            StagingErrorCode.INVALID_STAGING_METADATA,
            f"{field} must be non-empty bounded text without control characters",
        )


def _require_utc(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ImportStagingError(
            StagingErrorCode.INVALID_STAGING_METADATA,
            f"{field} must be timezone-aware UTC",
        )


@dataclass(frozen=True)
class SyntheticImportProvenance:
    """Replay identity retained for a simulation-plane source package."""

    scenario_id: str
    scenario_version: str
    seed: int
    factory_profile_id: str
    profile_version: str
    generator_id: str
    generator_version: str

    def __post_init__(self) -> None:
        for field in (
            "scenario_id",
            "scenario_version",
            "factory_profile_id",
            "profile_version",
            "generator_id",
            "generator_version",
        ):
            _require_text(getattr(self, field), field=field)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "seed must be a non-negative integer",
            )

    def fingerprint_projection(self) -> dict[str, str | int]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_version": self.scenario_version,
            "seed": self.seed,
            "factory_profile_id": self.factory_profile_id,
            "profile_version": self.profile_version,
            "generator_id": self.generator_id,
            "generator_version": self.generator_version,
        }


@dataclass(frozen=True)
class RawImportRow:
    """One opaque source row; the payload is preserved as bytes, never parsed here."""

    row_identity: str
    source_location: str
    raw_payload: bytes

    def __post_init__(self) -> None:
        _require_text(self.row_identity, field="row_identity")
        _require_text(self.source_location, field="source_location", maximum=512)
        if not isinstance(self.raw_payload, bytes):
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "raw_payload must be immutable bytes",
            )

    @property
    def payload_sha256(self) -> str:
        return sha256(self.raw_payload).hexdigest()


@dataclass(frozen=True)
class StagedImportBatch:
    """An immutable batch prepared for one atomic repository transaction."""

    batch_id: str
    idempotency_key: str
    source_system: str
    source_version: str
    content_sha256: str
    source_name: str
    media_type: str
    content_length_bytes: int
    received_at: datetime
    data_plane: StagingDataPlane
    rows: tuple[RawImportRow, ...]
    synthetic_provenance: SyntheticImportProvenance | None = None

    def __post_init__(self) -> None:
        for field in (
            "batch_id",
            "idempotency_key",
            "source_system",
            "source_version",
            "source_name",
            "media_type",
        ):
            _require_text(getattr(self, field), field=field)
        if "/" in self.source_name or "\\" in self.source_name:
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "source_name must be a leaf name without a path",
            )
        if _SHA256.fullmatch(self.content_sha256) is None:
            raise ImportStagingError(
                StagingErrorCode.INVALID_CONTENT_DIGEST,
                "content_sha256 must be a lowercase SHA-256 digest",
            )
        if (
            isinstance(self.content_length_bytes, bool)
            or not isinstance(self.content_length_bytes, int)
            or self.content_length_bytes < 0
        ):
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "content_length_bytes must be a non-negative integer",
            )
        _require_utc(self.received_at, field="received_at")
        if not isinstance(self.data_plane, StagingDataPlane):
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "data_plane must be an explicit staging data plane",
            )
        if not isinstance(self.rows, tuple):
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "rows must be an immutable tuple",
            )
        if any(not isinstance(row, RawImportRow) for row in self.rows):
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "rows must contain only RawImportRow values",
            )
        if self.synthetic_provenance is not None and not isinstance(
            self.synthetic_provenance, SyntheticImportProvenance
        ):
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "synthetic_provenance must use the staging provenance contract",
            )
        row_identities = [row.row_identity for row in self.rows]
        if len(row_identities) != len(set(row_identities)):
            raise ImportStagingError(
                StagingErrorCode.DUPLICATE_ROW_IDENTITY,
                "row_identity must be unique within a batch",
            )
        if self.data_plane is StagingDataPlane.PRODUCTION:
            if self.synthetic_provenance is not None:
                raise ImportStagingError(
                    StagingErrorCode.DATA_PLANE_MISMATCH,
                    "production staging forbids synthetic provenance",
                )
        elif self.synthetic_provenance is None:
            raise ImportStagingError(
                StagingErrorCode.DATA_PLANE_MISMATCH,
                "simulation staging requires synthetic provenance",
            )

    @property
    def request_fingerprint(self) -> str:
        """Fingerprint replay semantics without batch ID or receipt time."""

        projection: dict[str, object] = {
            "data_plane": self.data_plane.value,
            "source_system": self.source_system,
            "source_version": self.source_version,
            "content_sha256": self.content_sha256,
            "source_name": self.source_name,
            "media_type": self.media_type,
            "content_length_bytes": self.content_length_bytes,
            "synthetic_provenance": (
                self.synthetic_provenance.fingerprint_projection()
                if self.synthetic_provenance is not None
                else None
            ),
            "rows": [
                {
                    "row_identity": row.row_identity,
                    "source_location": row.source_location,
                    "payload_sha256": row.payload_sha256,
                }
                for row in self.rows
            ],
        }
        canonical = json.dumps(
            projection,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(canonical).hexdigest()


@dataclass(frozen=True)
class StagingWriteResult:
    batch: StagedImportBatch
    replayed: bool


__all__ = [
    "ImportStagingError",
    "RawImportRow",
    "StagedImportBatch",
    "StagingDataPlane",
    "StagingErrorCode",
    "StagingWriteResult",
    "SyntheticImportProvenance",
]
