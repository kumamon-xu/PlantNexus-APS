"""Plane-scoped append-only ExecutionEvent ledger repository."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.infrastructure.replan_persistence import (
    EXECUTION_EVENT_LEDGER,
    canonical_p4_document,
    load_p4_document,
)
from app.infrastructure.workspace_persistence import (
    DocumentWriteResult,
    PersistenceFailure,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
    document_sha256,
    integrity_savepoint,
    reject,
    require_integer,
    require_mapping,
    require_text,
)


class SqlAlchemyExecutionEventRepository:
    """Store exact P4 ExecutionEvent bytes under one immutable authority stream."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find_by_id(self, connection: Connection, event_id: str) -> RowMapping | None:
        row = connection.execute(
            select(EXECUTION_EVENT_LEDGER).where(
                EXECUTION_EVENT_LEDGER.c.data_plane == self._data_plane.value,
                EXECUTION_EVENT_LEDGER.c.event_id == event_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _find_by_position(
        self,
        connection: Connection,
        *,
        authority_id: str,
        stream_id: str,
        stream_version: str,
        source_position: int,
    ) -> RowMapping | None:
        row = connection.execute(
            select(EXECUTION_EVENT_LEDGER).where(
                EXECUTION_EVENT_LEDGER.c.data_plane == self._data_plane.value,
                EXECUTION_EVENT_LEDGER.c.authority_id == authority_id,
                EXECUTION_EVENT_LEDGER.c.stream_id == stream_id,
                EXECUTION_EVENT_LEDGER.c.stream_version == stream_version,
                EXECUTION_EVENT_LEDGER.c.source_position == source_position,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> dict[str, object]:
        document = load_p4_document(
            row["document_json"],
            row["document_sha256"],
            expected_version="execution-event.v1",
            data_plane=self._data_plane,
        )
        authority = require_mapping(document.get("authority"), "authority")
        stream = require_mapping(document.get("source_stream"), "source_stream")
        expected: dict[str, object] = {
            "event_id": row["event_id"],
            "event_fingerprint": row["event_fingerprint"],
            "event_type": row["event_type"],
            "environment": row["environment"],
            "factory_id": row["factory_id"],
            "planning_scope_id": row["planning_scope_id"],
            "source_position": row["source_position"],
            "occurred_at_utc": row["occurred_at_utc"],
            "received_at_utc": row["received_at_utc"],
            "correlation_id": row["correlation_id"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.execution_event",
                message="stored ExecutionEvent metadata failed integrity verification",
            )
        nested_expected = {
            "authority.authority_id": (
                authority.get("authority_id"),
                row["authority_id"],
            ),
            "authority.authority_scope": (
                authority.get("authority_scope"),
                row["authority_scope"],
            ),
            "source_stream.stream_id": (stream.get("stream_id"), row["stream_id"]),
            "source_stream.stream_version": (
                stream.get("stream_version"),
                row["stream_version"],
            ),
        }
        if any(actual != expected for actual, expected in nested_expected.values()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.execution_event_stream",
                message="stored authority stream metadata failed integrity verification",
            )
        return document

    def _candidate(
        self, document: Mapping[str, object]
    ) -> tuple[dict[str, object], bytes, Mapping[str, object], Mapping[str, object]]:
        candidate, canonical = canonical_p4_document(
            document,
            expected_version="execution-event.v1",
            data_plane=self._data_plane,
        )
        authority = require_mapping(candidate.get("authority"), "authority")
        stream = require_mapping(candidate.get("source_stream"), "source_stream")
        return candidate, canonical, authority, stream

    def _resolve_existing(
        self, row: RowMapping, canonical: bytes
    ) -> DocumentWriteResult:
        stored = row["document_json"]
        if (
            not isinstance(stored, (bytes, bytearray, memoryview))
            or bytes(stored) != canonical
        ):
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="event_id/source_position",
                message="event identity or authority position has different content",
            )
        return DocumentWriteResult(document=self._load(row), replayed=True)

    def append_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
    ) -> DocumentWriteResult:
        candidate, canonical, authority, stream = self._candidate(document)
        event_id = require_text(candidate.get("event_id"), "event_id")
        authority_id = require_text(authority.get("authority_id"), "authority.authority_id")
        stream_id = require_text(stream.get("stream_id"), "source_stream.stream_id")
        stream_version = require_text(
            stream.get("stream_version"), "source_stream.stream_version"
        )
        source_position = require_integer(
            candidate.get("source_position"), "source_position", minimum=1
        )
        existing = self._find_by_id(connection, event_id)
        if existing is None:
            existing = self._find_by_position(
                connection,
                authority_id=authority_id,
                stream_id=stream_id,
                stream_version=stream_version,
                source_position=source_position,
            )
        if existing is not None:
            return self._resolve_existing(existing, canonical)
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(EXECUTION_EVENT_LEDGER).values(
                        data_plane=self._data_plane.value,
                        event_id=event_id,
                        event_fingerprint=require_text(
                            candidate.get("event_fingerprint"), "event_fingerprint"
                        ),
                        event_type=require_text(
                            candidate.get("event_type"), "event_type"
                        ),
                        environment=require_text(
                            candidate.get("environment"), "environment"
                        ),
                        factory_id=require_text(
                            candidate.get("factory_id"), "factory_id"
                        ),
                        planning_scope_id=require_text(
                            candidate.get("planning_scope_id"), "planning_scope_id"
                        ),
                        authority_id=authority_id,
                        authority_scope=require_text(
                            authority.get("authority_scope"),
                            "authority.authority_scope",
                        ),
                        stream_id=stream_id,
                        stream_version=stream_version,
                        source_position=source_position,
                        occurred_at_utc=require_text(
                            candidate.get("occurred_at_utc"), "occurred_at_utc"
                        ),
                        received_at_utc=require_text(
                            candidate.get("received_at_utc"), "received_at_utc"
                        ),
                        correlation_id=require_text(
                            candidate.get("correlation_id"), "correlation_id"
                        ),
                        document_json=canonical,
                        document_sha256=document_sha256(canonical),
                    )
                )
        except IntegrityError:
            raced = self._find_by_id(connection, event_id)
            if raced is None:
                raced = self._find_by_position(
                    connection,
                    authority_id=authority_id,
                    stream_id=stream_id,
                    stream_version=stream_version,
                    source_position=source_position,
                )
            if raced is not None:
                return self._resolve_existing(raced, canonical)
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.append",
                message="ExecutionEvent insert conflicted with stored identity",
            )
        return DocumentWriteResult(document=candidate, replayed=False)

    def append(self, document: Mapping[str, object]) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.append_in_transaction(connection, document)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.append",
                message="ExecutionEvent transaction failed",
            )

    def get(self, event_id: str) -> dict[str, object] | None:
        require_text(event_id, "event_id")
        try:
            with self._engine.connect() as connection:
                row = self._find_by_id(connection, event_id)
                return self._load(row) if row is not None else None
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get",
                message="ExecutionEvent query failed",
            )

    def list_stream(
        self,
        *,
        authority_id: str,
        stream_id: str,
        stream_version: str,
        after_position: int = 0,
    ) -> tuple[dict[str, object], ...]:
        require_text(authority_id, "authority_id")
        require_text(stream_id, "stream_id")
        require_text(stream_version, "stream_version")
        require_integer(after_position, "after_position", minimum=0)
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(EXECUTION_EVENT_LEDGER)
                    .where(
                        EXECUTION_EVENT_LEDGER.c.data_plane
                        == self._data_plane.value,
                        EXECUTION_EVENT_LEDGER.c.authority_id == authority_id,
                        EXECUTION_EVENT_LEDGER.c.stream_id == stream_id,
                        EXECUTION_EVENT_LEDGER.c.stream_version == stream_version,
                        EXECUTION_EVENT_LEDGER.c.source_position > after_position,
                    )
                    .order_by(EXECUTION_EVENT_LEDGER.c.source_position)
                ).all()
                return tuple(self._load(row._mapping) for row in rows)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.list_stream",
                message="ExecutionEvent stream query failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="ExecutionEvent updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="ExecutionEvent deletion is forbidden",
        )


__all__ = ["SqlAlchemyExecutionEventRepository"]
