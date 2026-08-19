"""SQLAlchemy Core adapter for atomic, insert-only Raw Staging persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NoReturn, cast

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.importers.contracts import (
    ImportStagingError,
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    StagingErrorCode,
    StagingWriteResult,
    SyntheticImportProvenance,
)

_METADATA = MetaData()

_BATCHES = Table(
    "raw_import_batches",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("batch_id", String(length=256), primary_key=True),
    Column("idempotency_key", String(length=256), nullable=False),
    Column("request_fingerprint", String(length=64), nullable=False),
    Column("source_system", String(length=256), nullable=False),
    Column("source_version", String(length=256), nullable=False),
    Column("content_sha256", String(length=64), nullable=False),
    Column("source_name", String(length=256), nullable=False),
    Column("media_type", String(length=256), nullable=False),
    Column("content_length_bytes", BigInteger(), nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("row_count", Integer(), nullable=False),
    Column("synthetic_scenario_id", String(length=256), nullable=True),
    Column("synthetic_scenario_version", String(length=256), nullable=True),
    Column("synthetic_seed", BigInteger(), nullable=True),
    Column("synthetic_factory_profile_id", String(length=256), nullable=True),
    Column("synthetic_profile_version", String(length=256), nullable=True),
    Column("synthetic_generator_id", String(length=256), nullable=True),
    Column("synthetic_generator_version", String(length=256), nullable=True),
)

_ROWS = Table(
    "raw_import_rows",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("batch_id", String(length=256), primary_key=True),
    Column("row_identity", String(length=256), primary_key=True),
    Column("position", Integer(), nullable=False),
    Column("source_location", String(length=512), nullable=False),
    Column("raw_payload", LargeBinary(), nullable=False),
    Column("payload_sha256", String(length=64), nullable=False),
)


def _stored_integrity_failure() -> NoReturn:
    raise ImportStagingError(
        StagingErrorCode.STAGING_TRANSACTION_FAILED,
        "stored Raw Staging data failed integrity verification",
    )


def _text(row: RowMapping, key: str) -> str:
    value = row[key]
    if not isinstance(value, str):
        _stored_integrity_failure()
    return value


def _integer(row: RowMapping, key: str) -> int:
    value = row[key]
    if isinstance(value, bool) or not isinstance(value, int):
        _stored_integrity_failure()
    return value


def _optional_text(row: RowMapping, key: str) -> str | None:
    value = row[key]
    if value is not None and not isinstance(value, str):
        _stored_integrity_failure()
    return value


def _received_at(row: RowMapping) -> datetime:
    value = row["received_at"]
    if not isinstance(value, datetime):
        _stored_integrity_failure()
    if value.tzinfo is None:
        # SQLite drops timezone information; all writes were validated as UTC.
        return value.replace(tzinfo=UTC)
    if value.utcoffset() != timedelta(0):
        _stored_integrity_failure()
    return value


class SqlAlchemyImportStagingRepository:
    """A repository instance is permanently scoped to one configured data plane."""

    def __init__(self, engine: Engine, *, data_plane: StagingDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> StagingDataPlane:
        return self._data_plane

    def _assert_plane(self, batch: StagedImportBatch) -> None:
        if batch.data_plane is not self._data_plane:
            raise ImportStagingError(
                StagingErrorCode.DATA_PLANE_MISMATCH,
                "batch data plane does not match the repository data plane",
            )

    def _batch_values(self, batch: StagedImportBatch) -> dict[str, object]:
        provenance = batch.synthetic_provenance
        return {
            "data_plane": batch.data_plane.value,
            "batch_id": batch.batch_id,
            "idempotency_key": batch.idempotency_key,
            "request_fingerprint": batch.request_fingerprint,
            "source_system": batch.source_system,
            "source_version": batch.source_version,
            "content_sha256": batch.content_sha256,
            "source_name": batch.source_name,
            "media_type": batch.media_type,
            "content_length_bytes": batch.content_length_bytes,
            "received_at": batch.received_at,
            "row_count": len(batch.rows),
            "synthetic_scenario_id": provenance.scenario_id if provenance else None,
            "synthetic_scenario_version": (
                provenance.scenario_version if provenance else None
            ),
            "synthetic_seed": provenance.seed if provenance else None,
            "synthetic_factory_profile_id": (
                provenance.factory_profile_id if provenance else None
            ),
            "synthetic_profile_version": (
                provenance.profile_version if provenance else None
            ),
            "synthetic_generator_id": provenance.generator_id if provenance else None,
            "synthetic_generator_version": (
                provenance.generator_version if provenance else None
            ),
        }

    def _find_by_idempotency(
        self,
        connection: Connection,
        batch: StagedImportBatch,
    ) -> RowMapping | None:
        row = connection.execute(
            select(_BATCHES).where(
                _BATCHES.c.data_plane == self._data_plane.value,
                _BATCHES.c.source_system == batch.source_system,
                _BATCHES.c.idempotency_key == batch.idempotency_key,
            )
        ).first()
        return row._mapping if row is not None else None

    def _find_by_batch_id(
        self,
        connection: Connection,
        batch_id: str,
    ) -> RowMapping | None:
        row = connection.execute(
            select(_BATCHES).where(
                _BATCHES.c.data_plane == self._data_plane.value,
                _BATCHES.c.batch_id == batch_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, connection: Connection, batch_row: RowMapping) -> StagedImportBatch:
        batch_id = _text(batch_row, "batch_id")
        stored_rows = connection.execute(
            select(_ROWS)
            .where(
                _ROWS.c.data_plane == self._data_plane.value,
                _ROWS.c.batch_id == batch_id,
            )
            .order_by(_ROWS.c.position)
        ).all()
        rows: list[RawImportRow] = []
        for expected_position, stored in enumerate(stored_rows):
            row = stored._mapping
            if _integer(row, "position") != expected_position:
                _stored_integrity_failure()
            payload_value = row["raw_payload"]
            if not isinstance(payload_value, (bytes, bytearray, memoryview)):
                _stored_integrity_failure()
            raw_row = RawImportRow(
                row_identity=_text(row, "row_identity"),
                source_location=_text(row, "source_location"),
                raw_payload=bytes(payload_value),
            )
            if raw_row.payload_sha256 != _text(row, "payload_sha256"):
                _stored_integrity_failure()
            rows.append(raw_row)
        if len(rows) != _integer(batch_row, "row_count"):
            _stored_integrity_failure()

        try:
            stored_plane = StagingDataPlane(_text(batch_row, "data_plane"))
        except ValueError:
            _stored_integrity_failure()
        provenance: SyntheticImportProvenance | None = None
        if stored_plane is StagingDataPlane.SIMULATION:
            seed = batch_row["synthetic_seed"]
            if isinstance(seed, bool) or not isinstance(seed, int):
                _stored_integrity_failure()
            provenance = SyntheticImportProvenance(
                scenario_id=cast(str, _optional_text(batch_row, "synthetic_scenario_id")),
                scenario_version=cast(
                    str,
                    _optional_text(batch_row, "synthetic_scenario_version"),
                ),
                seed=seed,
                factory_profile_id=cast(
                    str,
                    _optional_text(batch_row, "synthetic_factory_profile_id"),
                ),
                profile_version=cast(
                    str,
                    _optional_text(batch_row, "synthetic_profile_version"),
                ),
                generator_id=cast(
                    str,
                    _optional_text(batch_row, "synthetic_generator_id"),
                ),
                generator_version=cast(
                    str,
                    _optional_text(batch_row, "synthetic_generator_version"),
                ),
            )

        batch = StagedImportBatch(
            batch_id=batch_id,
            idempotency_key=_text(batch_row, "idempotency_key"),
            source_system=_text(batch_row, "source_system"),
            source_version=_text(batch_row, "source_version"),
            content_sha256=_text(batch_row, "content_sha256"),
            source_name=_text(batch_row, "source_name"),
            media_type=_text(batch_row, "media_type"),
            content_length_bytes=_integer(batch_row, "content_length_bytes"),
            received_at=_received_at(batch_row),
            data_plane=stored_plane,
            rows=tuple(rows),
            synthetic_provenance=provenance,
        )
        if batch.request_fingerprint != _text(batch_row, "request_fingerprint"):
            _stored_integrity_failure()
        return batch

    def _resolve_existing(
        self,
        connection: Connection,
        existing: RowMapping,
        candidate: StagedImportBatch,
    ) -> StagingWriteResult:
        if _text(existing, "request_fingerprint") != candidate.request_fingerprint:
            raise ImportStagingError(
                StagingErrorCode.IDEMPOTENCY_CONFLICT,
                "idempotency key was reused with different staged content or source version",
            )
        return StagingWriteResult(batch=self._load(connection, existing), replayed=True)

    def _resolve_integrity_collision(
        self, candidate: StagedImportBatch
    ) -> StagingWriteResult:
        try:
            with self._engine.connect() as connection:
                existing = self._find_by_idempotency(connection, candidate)
                if existing is not None:
                    return self._resolve_existing(connection, existing, candidate)
        except ImportStagingError:
            raise
        except SQLAlchemyError:
            pass
        raise ImportStagingError(
            StagingErrorCode.STAGING_TRANSACTION_FAILED,
            "Raw Staging transaction failed",
        ) from None

    def stage(self, batch: StagedImportBatch) -> StagingWriteResult:
        self._assert_plane(batch)
        try:
            with self._engine.begin() as connection:
                existing = self._find_by_idempotency(connection, batch)
                if existing is not None:
                    return self._resolve_existing(connection, existing, batch)
                connection.execute(insert(_BATCHES).values(**self._batch_values(batch)))
                if batch.rows:
                    connection.execute(
                        insert(_ROWS),
                        [
                            {
                                "data_plane": batch.data_plane.value,
                                "batch_id": batch.batch_id,
                                "row_identity": row.row_identity,
                                "position": position,
                                "source_location": row.source_location,
                                "raw_payload": row.raw_payload,
                                "payload_sha256": row.payload_sha256,
                            }
                            for position, row in enumerate(batch.rows)
                        ],
                    )
                return StagingWriteResult(batch=batch, replayed=False)
        except ImportStagingError:
            raise
        except IntegrityError:
            return self._resolve_integrity_collision(batch)
        except SQLAlchemyError:
            raise ImportStagingError(
                StagingErrorCode.STAGING_TRANSACTION_FAILED,
                "Raw Staging transaction failed",
            ) from None

    def get(self, batch_id: str) -> StagedImportBatch | None:
        if not isinstance(batch_id, str) or not batch_id:
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "batch_id must be non-empty text",
            )
        try:
            with self._engine.connect() as connection:
                batch_row = self._find_by_batch_id(connection, batch_id)
                return self._load(connection, batch_row) if batch_row is not None else None
        except ImportStagingError:
            raise
        except SQLAlchemyError:
            raise ImportStagingError(
                StagingErrorCode.STAGING_TRANSACTION_FAILED,
                "Raw Staging query failed",
            ) from None


__all__ = ["SqlAlchemyImportStagingRepository"]
