"""Plane-scoped append-only AuditEvent persistence primitives."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.infrastructure.workspace_persistence import (
    AUDIT_EVENTS,
    DocumentWriteResult,
    PersistenceFailure,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
    canonical_document,
    document_sha256,
    integrity_savepoint,
    load_document,
    reject,
    require_mapping,
    require_text,
)


class SqlAlchemyAuditRepository:
    """AuditEvent documents are exact-replayable and otherwise append-only."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find_by_id(
        self, connection: Connection, audit_event_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(AUDIT_EVENTS).where(
                AUDIT_EVENTS.c.data_plane == self._data_plane.value,
                AUDIT_EVENTS.c.audit_event_id == audit_event_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _find_by_idempotency(
        self,
        connection: Connection,
        *,
        scope: str,
        key_reference: str,
    ) -> RowMapping | None:
        row = connection.execute(
            select(AUDIT_EVENTS).where(
                AUDIT_EVENTS.c.data_plane == self._data_plane.value,
                AUDIT_EVENTS.c.idempotency_scope == scope,
                AUDIT_EVENTS.c.idempotency_key_reference == key_reference,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> dict[str, object]:
        document = load_document(
            row["document_json"],
            row["document_sha256"],
            expected_version="audit-event.v1",
            data_plane=self._data_plane,
        )
        expected = {
            "audit_event_id": row["audit_event_id"],
            "environment": row["environment"],
            "action": row["action"],
            "aggregate_type": row["aggregate_type"],
            "aggregate_id": row["aggregate_id"],
            "correlation_id": row["correlation_id"],
            "occurred_at_utc": row["occurred_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.audit_event",
                message="stored AuditEvent metadata failed integrity verification",
            )
        return document

    def _candidate(
        self, document: Mapping[str, object]
    ) -> tuple[dict[str, object], bytes, str | None, str | None]:
        candidate, canonical = canonical_document(
            document,
            expected_version="audit-event.v1",
            data_plane=self._data_plane,
        )
        for field in (
            "audit_event_id",
            "environment",
            "action",
            "aggregate_type",
            "aggregate_id",
            "correlation_id",
            "occurred_at_utc",
        ):
            require_text(candidate.get(field), field)
        idempotency_value = candidate.get("idempotency_reference")
        if idempotency_value is None:
            return candidate, canonical, None, None
        idempotency = require_mapping(idempotency_value, "idempotency_reference")
        return (
            candidate,
            canonical,
            require_text(idempotency.get("scope"), "idempotency_reference.scope"),
            require_text(
                idempotency.get("key_reference"),
                "idempotency_reference.key_reference",
            ),
        )

    def _resolve_existing(
        self, row: RowMapping, candidate_bytes: bytes
    ) -> DocumentWriteResult:
        stored = row["document_json"]
        if (
            not isinstance(stored, (bytes, bytearray, memoryview))
            or bytes(stored) != candidate_bytes
        ):
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="audit_event_id/idempotency_reference",
                message="AuditEvent identity or key is bound to different content",
            )
        return DocumentWriteResult(document=self._load(row), replayed=True)

    def append_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
    ) -> DocumentWriteResult:
        candidate, canonical, scope, key_reference = self._candidate(document)
        audit_event_id = require_text(candidate.get("audit_event_id"), "audit_event_id")
        existing = self._find_by_id(connection, audit_event_id)
        if existing is None and scope is not None and key_reference is not None:
            existing = self._find_by_idempotency(
                connection, scope=scope, key_reference=key_reference
            )
        if existing is not None:
            return self._resolve_existing(existing, canonical)

        parent = candidate.get("parent_audit_event_id")
        if (
            parent is not None
            and self._find_by_id(
                connection, require_text(parent, "parent_audit_event_id")
            )
            is None
        ):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="parent_audit_event_id",
                message="parent AuditEvent is absent from this plane",
            )
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(AUDIT_EVENTS).values(
                        data_plane=self._data_plane.value,
                        audit_event_id=audit_event_id,
                        environment=require_text(
                            candidate.get("environment"), "environment"
                        ),
                        action=require_text(candidate.get("action"), "action"),
                        aggregate_type=require_text(
                            candidate.get("aggregate_type"), "aggregate_type"
                        ),
                        aggregate_id=require_text(
                            candidate.get("aggregate_id"), "aggregate_id"
                        ),
                        correlation_id=require_text(
                            candidate.get("correlation_id"), "correlation_id"
                        ),
                        parent_audit_event_id=parent,
                        occurred_at_utc=require_text(
                            candidate.get("occurred_at_utc"), "occurred_at_utc"
                        ),
                        idempotency_scope=scope,
                        idempotency_key_reference=key_reference,
                        request_fingerprint=candidate.get("request_fingerprint"),
                        document_json=canonical,
                        document_sha256=document_sha256(canonical),
                    )
                )
        except IntegrityError:
            raced = self._find_by_id(connection, audit_event_id)
            if raced is None and scope is not None and key_reference is not None:
                raced = self._find_by_idempotency(
                    connection,
                    scope=scope,
                    key_reference=key_reference,
                )
            if raced is not None:
                return self._resolve_existing(raced, canonical)
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.append",
                message="AuditEvent insert conflicted with stored identity",
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
                message="AuditEvent transaction failed",
            )

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        require_text(audit_event_id, "audit_event_id")
        try:
            with self._engine.connect() as connection:
                row = self._find_by_id(connection, audit_event_id)
                return self._load(row) if row is not None else None
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get",
                message="AuditEvent query failed",
            )

    def list_for_aggregate(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
    ) -> tuple[dict[str, object], ...]:
        require_text(aggregate_type, "aggregate_type")
        require_text(aggregate_id, "aggregate_id")
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(AUDIT_EVENTS)
                    .where(
                        AUDIT_EVENTS.c.data_plane == self._data_plane.value,
                        AUDIT_EVENTS.c.aggregate_type == aggregate_type,
                        AUDIT_EVENTS.c.aggregate_id == aggregate_id,
                    )
                    .order_by(
                        AUDIT_EVENTS.c.occurred_at_utc,
                        AUDIT_EVENTS.c.audit_event_id,
                    )
                ).all()
                return tuple(self._load(row._mapping) for row in rows)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.list_for_aggregate",
                message="AuditEvent query failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="AuditEvent updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="AuditEvent deletion is forbidden",
        )


__all__ = ["SqlAlchemyAuditRepository"]
