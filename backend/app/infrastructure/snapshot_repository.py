"""SQLAlchemy adapter for isolated, content-addressed Snapshot persistence."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import re
from typing import NoReturn

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    LargeBinary,
    MetaData,
    String,
    Table,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.snapshots.canonical import verify_snapshot
from app.snapshots.contracts import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
    SnapshotWriteResult,
)
from app.infrastructure.workspace_persistence import integrity_savepoint

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_METADATA = MetaData()

_SNAPSHOTS = Table(
    "planning_snapshots",
    _METADATA,
    Column("snapshot_hash", String(length=71), primary_key=True),
    Column("snapshot_id", String(length=256), nullable=False, unique=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("snapshot_version", String(length=64), nullable=False),
    Column("canonicalization_version", String(length=64), nullable=False),
    Column("cutoff_at_utc", String(length=32), nullable=False),
    Column("canonical_sha256", String(length=64), nullable=False),
    Column("canonical_json", LargeBinary(), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
Index(
    "ix_planning_snapshots_plane_cutoff",
    _SNAPSHOTS.c.data_plane,
    _SNAPSHOTS.c.cutoff_at_utc,
)


def _reject(
    code: SnapshotErrorCode,
    *,
    field: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise SnapshotError(
        code,
        field=field,
        expected_contract=expected_contract,
        message=message,
    )


def _text(row: RowMapping, key: str) -> str:
    value = row[key]
    if not isinstance(value, str):
        _reject(
            SnapshotErrorCode.CONTENT_CONFLICT,
            field=f"stored.{key}",
            expected_contract="valid immutable Snapshot storage",
            message="Stored Snapshot metadata failed integrity verification",
        )
    return value


def _bytes(row: RowMapping, key: str) -> bytes:
    value = row[key]
    if not isinstance(value, (bytes, bytearray, memoryview)):
        _reject(
            SnapshotErrorCode.CONTENT_CONFLICT,
            field=f"stored.{key}",
            expected_contract="canonical Snapshot bytes",
            message="Stored Snapshot payload failed integrity verification",
        )
    return bytes(value)


class SqlAlchemySnapshotRepository:
    """A repository instance is permanently scoped to one data plane."""

    def __init__(self, engine: Engine, *, data_plane: SnapshotDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> SnapshotDataPlane:
        return self._data_plane

    def _assert_plane(self, snapshot: ImmutablePlanningSnapshot) -> None:
        verify_snapshot(snapshot)
        if snapshot.data_plane is not self._data_plane:
            _reject(
                SnapshotErrorCode.DATA_PLANE_MISMATCH,
                field="data_plane",
                expected_contract=self._data_plane.value,
                message="Snapshot does not belong to this repository data plane",
            )

    def _find_by_hash(
        self, connection: Connection, snapshot_hash: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(_SNAPSHOTS).where(
                _SNAPSHOTS.c.data_plane == self._data_plane.value,
                _SNAPSHOTS.c.snapshot_hash == snapshot_hash,
            )
        ).first()
        return row._mapping if row is not None else None

    def _find_by_id(
        self, connection: Connection, snapshot_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(_SNAPSHOTS).where(
                _SNAPSHOTS.c.data_plane == self._data_plane.value,
                _SNAPSHOTS.c.snapshot_id == snapshot_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> ImmutablePlanningSnapshot:
        canonical_bytes = _bytes(row, "canonical_json")
        observed_digest = sha256(canonical_bytes).hexdigest()
        if observed_digest != _text(row, "canonical_sha256"):
            _reject(
                SnapshotErrorCode.CONTENT_CONFLICT,
                field="stored.canonical_sha256",
                expected_contract="SHA-256 of stored canonical bytes",
                message="Stored Snapshot bytes were modified",
            )
        try:
            stored_plane = SnapshotDataPlane(_text(row, "data_plane"))
        except ValueError:
            _reject(
                SnapshotErrorCode.CONTENT_CONFLICT,
                field="stored.data_plane",
                expected_contract="production or simulation",
                message="Stored Snapshot data plane is invalid",
            )
        snapshot = ImmutablePlanningSnapshot(
            canonical_bytes=canonical_bytes,
            snapshot_id=_text(row, "snapshot_id"),
            snapshot_hash=_text(row, "snapshot_hash"),
            data_plane=stored_plane,
        )
        verify_snapshot(snapshot)
        if snapshot.data_plane is not self._data_plane:
            _reject(
                SnapshotErrorCode.DATA_PLANE_MISMATCH,
                field="stored.data_plane",
                expected_contract=self._data_plane.value,
                message="Query crossed the repository data-plane boundary",
            )
        return snapshot

    def _resolve_existing(
        self,
        row: RowMapping,
        candidate: ImmutablePlanningSnapshot,
    ) -> SnapshotWriteResult:
        try:
            stored = self._load(row)
        except SnapshotError as error:
            raise SnapshotError(
                SnapshotErrorCode.CONTENT_CONFLICT,
                field="stored.snapshot",
                expected_contract="one valid byte-exact document per content identity",
                message="Stored identity is bound to invalid or different content",
            ) from error
        if (
            stored.snapshot_id != candidate.snapshot_id
            or stored.snapshot_hash != candidate.snapshot_hash
            or stored.canonical_bytes != candidate.canonical_bytes
        ):
            _reject(
                SnapshotErrorCode.CONTENT_CONFLICT,
                field="snapshot_hash/snapshot_id",
                expected_contract="one byte-exact document per content identity",
                message="Snapshot identity is already bound to different content",
            )
        return SnapshotWriteResult(snapshot=stored, replayed=True)

    def _resolve_integrity_collision(
        self, candidate: ImmutablePlanningSnapshot
    ) -> SnapshotWriteResult:
        try:
            with self._engine.connect() as connection:
                existing = self._find_by_hash(connection, candidate.snapshot_hash)
                if existing is None:
                    existing = self._find_by_id(connection, candidate.snapshot_id)
                if existing is not None:
                    return self._resolve_existing(existing, candidate)
        except SnapshotError:
            raise
        except SQLAlchemyError:
            pass
        _reject(
            SnapshotErrorCode.SNAPSHOT_PERSISTENCE_FAILED,
            field="repository.put",
            expected_contract="atomic insert or exact replay",
            message="Snapshot transaction failed",
        )

    def put(self, snapshot: ImmutablePlanningSnapshot) -> SnapshotWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.put_in_transaction(connection, snapshot)
        except SnapshotError:
            raise
        except SQLAlchemyError:
            _reject(
                SnapshotErrorCode.SNAPSHOT_PERSISTENCE_FAILED,
                field="repository.put",
                expected_contract="atomic insert or exact replay",
                message="Snapshot transaction failed",
            )

    def put_in_transaction(
        self,
        connection: Connection,
        snapshot: ImmutablePlanningSnapshot,
    ) -> SnapshotWriteResult:
        """Insert/replay a Snapshot on the caller's projection transaction."""

        self._assert_plane(snapshot)
        document = snapshot.document
        existing = self._find_by_hash(connection, snapshot.snapshot_hash)
        if existing is None:
            existing = self._find_by_id(connection, snapshot.snapshot_id)
        if existing is not None:
            return self._resolve_existing(existing, snapshot)
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(_SNAPSHOTS).values(
                        snapshot_hash=snapshot.snapshot_hash,
                        snapshot_id=snapshot.snapshot_id,
                        data_plane=snapshot.data_plane.value,
                        snapshot_version=document["snapshot_version"],
                        canonicalization_version=document["canonicalization_version"],
                        cutoff_at_utc=document["cutoff_at_utc"],
                        canonical_sha256=sha256(snapshot.canonical_bytes).hexdigest(),
                        canonical_json=snapshot.canonical_bytes,
                    )
                )
        except IntegrityError:
            existing = self._find_by_hash(connection, snapshot.snapshot_hash)
            if existing is None:
                existing = self._find_by_id(connection, snapshot.snapshot_id)
            if existing is not None:
                return self._resolve_existing(existing, snapshot)
            _reject(
                SnapshotErrorCode.SNAPSHOT_PERSISTENCE_FAILED,
                field="repository.put",
                expected_contract="atomic insert or exact replay",
                message="Snapshot insert lost an unresolved identity race",
            )
        return SnapshotWriteResult(snapshot=snapshot, replayed=False)

    def get_by_id_in_transaction(
        self, connection: Connection, snapshot_id: str
    ) -> ImmutablePlanningSnapshot | None:
        if not isinstance(snapshot_id, str) or not snapshot_id:
            _reject(
                SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
                field="snapshot_id",
                expected_contract="non-empty Snapshot ID",
                message="Snapshot ID is invalid",
            )
        row = self._find_by_id(connection, snapshot_id)
        return self._load(row) if row is not None else None

    def get_by_hash_in_transaction(
        self, connection: Connection, snapshot_hash: str
    ) -> ImmutablePlanningSnapshot | None:
        if _SHA256.fullmatch(snapshot_hash) is None:
            _reject(
                SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
                field="snapshot_hash",
                expected_contract="sha256:<64 lowercase hex>",
                message="Snapshot hash is invalid",
            )
        row = self._find_by_hash(connection, snapshot_hash)
        return self._load(row) if row is not None else None

    def get_by_id(self, snapshot_id: str) -> ImmutablePlanningSnapshot | None:
        if not isinstance(snapshot_id, str) or not snapshot_id:
            _reject(
                SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
                field="snapshot_id",
                expected_contract="non-empty Snapshot ID",
                message="Snapshot ID is invalid",
            )
        return self._get(lambda connection: self._find_by_id(connection, snapshot_id))

    def get_by_hash(self, snapshot_hash: str) -> ImmutablePlanningSnapshot | None:
        if _SHA256.fullmatch(snapshot_hash) is None:
            _reject(
                SnapshotErrorCode.INVALID_SNAPSHOT_INPUT,
                field="snapshot_hash",
                expected_contract="sha256:<64 lowercase hex>",
                message="Snapshot hash is invalid",
            )
        return self._get(
            lambda connection: self._find_by_hash(connection, snapshot_hash)
        )

    def _get(
        self,
        finder: Callable[[Connection], RowMapping | None],
    ) -> ImmutablePlanningSnapshot | None:
        try:
            with self._engine.connect() as connection:
                row = finder(connection)
                return self._load(row) if row is not None else None
        except SnapshotError:
            raise
        except SQLAlchemyError:
            _reject(
                SnapshotErrorCode.SNAPSHOT_PERSISTENCE_FAILED,
                field="repository.get",
                expected_contract="plane-scoped immutable read",
                message="Snapshot query failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        _reject(
            SnapshotErrorCode.IMMUTABLE_SNAPSHOT,
            field="repository.update",
            expected_contract="insert-only PlanningSnapshot storage",
            message="PlanningSnapshot updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        _reject(
            SnapshotErrorCode.IMMUTABLE_SNAPSHOT,
            field="repository.delete",
            expected_contract="insert-only PlanningSnapshot storage",
            message="PlanningSnapshot deletes are forbidden",
        )


__all__ = ["SqlAlchemySnapshotRepository"]
