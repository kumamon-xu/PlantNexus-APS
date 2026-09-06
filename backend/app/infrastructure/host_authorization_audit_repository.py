"""Append-only SQLAlchemy persistence for P8 Headless authorization decisions."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, NoReturn, cast

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
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.application.host_authorization import HostAuthorizationAuditRecord
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)


type JsonObject = dict[str, Any]

_METADATA = MetaData()
_AUDITS = Table(
    "headless_authorization_audit_records",
    _METADATA,
    Column("audit_event_id", String(length=64), primary_key=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("operation_id", String(length=64), nullable=False),
    Column("outcome", String(length=16), nullable=False),
    Column("reason", String(length=64), nullable=False),
    Column("actor_ref", String(length=256), nullable=False),
    Column("scope_fingerprint", String(length=71), nullable=False),
    Column("resource_reference", String(length=71), nullable=True),
    Column("correlation_id", String(length=256), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("audit_fingerprint", String(length=71), nullable=False),
    Column("audit_json", LargeBinary(), nullable=False),
    Column("audit_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
Index(
    "ix_headless_authorization_audit_scope_time",
    _AUDITS.c.data_plane,
    _AUDITS.c.scope_fingerprint,
    _AUDITS.c.occurred_at_utc,
)
Index(
    "ix_headless_authorization_audit_correlation",
    _AUDITS.c.data_plane,
    _AUDITS.c.correlation_id,
    _AUDITS.c.audit_event_id,
)

class HostAuthorizationAuditPersistenceError(RuntimeError):
    """Sanitized append/read failure; database detail remains internal."""


def _fail(message: str) -> NoReturn:
    raise HostAuthorizationAuditPersistenceError(message)


def _require_document(record: HostAuthorizationAuditRecord) -> JsonObject:
    document = record.document
    try:
        validated = HostAuthorizationAuditRecord.create(document)
    except (TypeError, ValueError):
        _fail("authorization audit contract is invalid")
    if validated.canonical_bytes != record.canonical_bytes:
        _fail("authorization audit bytes are not canonical")
    if validated.fingerprint != record.fingerprint:
        _fail("authorization audit fingerprint is invalid")
    return validated.document


class SqlAlchemyHostAuthorizationAuditRepository:
    """Persist exact sanitized records; mutation is rejected by database triggers."""

    def __init__(self, engine: Engine, *, data_plane: str) -> None:
        if data_plane not in {"SIMULATION", "PRODUCTION"}:
            raise ValueError("authorization audit data plane is invalid")
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> str:
        return self._data_plane

    def _find(self, audit_event_id: str) -> RowMapping | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(_AUDITS).where(
                    _AUDITS.c.audit_event_id == audit_event_id,
                    _AUDITS.c.data_plane == self._data_plane,
                )
            ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> JsonObject:
        stored = row["audit_json"]
        if not isinstance(stored, (bytes, bytearray, memoryview)):
            _fail("stored authorization audit bytes are invalid")
        raw = bytes(stored)
        if sha256(raw).hexdigest() != row["audit_sha256"]:
            _fail("stored authorization audit digest is invalid")
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail("stored authorization audit is unreadable")
        if not isinstance(document, dict) or canonical_json_bytes(document) != raw:
            _fail("stored authorization audit is not canonical")
        expected = {
            "audit_event_id": row["audit_event_id"],
            "data_plane": row["data_plane"],
            "environment": row["environment"],
            "operation_id": row["operation_id"],
            "outcome": row["outcome"],
            "reason": row["reason"],
            "actor_ref": row["actor_ref"],
            "scope_fingerprint": row["scope_fingerprint"],
            "resource_reference": row["resource_reference"],
            "correlation_id": row["correlation_id"],
            "occurred_at_utc": row["occurred_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            _fail("stored authorization audit metadata failed integrity verification")
        if canonical_fingerprint(document) != row["audit_fingerprint"]:
            _fail("stored authorization audit fingerprint failed verification")
        return cast(JsonObject, document)

    def append(self, record: HostAuthorizationAuditRecord) -> None:
        document = _require_document(record)
        if document.get("data_plane") != self._data_plane:
            _fail("authorization audit crossed its bound data plane")
        values = {
            "audit_event_id": document["audit_event_id"],
            "data_plane": document["data_plane"],
            "environment": document["environment"],
            "operation_id": document["operation_id"],
            "outcome": document["outcome"],
            "reason": document["reason"],
            "actor_ref": document["actor_ref"],
            "scope_fingerprint": document["scope_fingerprint"],
            "resource_reference": document["resource_reference"],
            "correlation_id": document["correlation_id"],
            "occurred_at_utc": document["occurred_at_utc"],
            "audit_fingerprint": record.fingerprint,
            "audit_json": record.canonical_bytes,
            "audit_sha256": sha256(record.canonical_bytes).hexdigest(),
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(_AUDITS).values(**values))
        except IntegrityError:
            existing = self._find(cast(str, document["audit_event_id"]))
            if existing is not None and bytes(existing["audit_json"]) == (
                record.canonical_bytes
            ):
                return
            _fail("authorization audit identity conflicts with stored content")
        except SQLAlchemyError:
            _fail("authorization audit persistence failed")

    def get(self, audit_event_id: str) -> JsonObject | None:
        try:
            row = self._find(audit_event_id)
            return self._load(row) if row is not None else None
        except HostAuthorizationAuditPersistenceError:
            raise
        except SQLAlchemyError:
            _fail("authorization audit query failed")

    def list_for_correlation(self, correlation_id: str) -> tuple[JsonObject, ...]:
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(_AUDITS)
                    .where(
                        _AUDITS.c.data_plane == self._data_plane,
                        _AUDITS.c.correlation_id == correlation_id,
                    )
                    .order_by(_AUDITS.c.occurred_at_utc, _AUDITS.c.audit_event_id)
                ).all()
            return tuple(self._load(row._mapping) for row in rows)
        except HostAuthorizationAuditPersistenceError:
            raise
        except SQLAlchemyError:
            _fail("authorization audit query failed")

    def count(self) -> int:
        try:
            with self._engine.connect() as connection:
                value = connection.scalar(
                    select(func.count()).select_from(_AUDITS).where(
                        _AUDITS.c.data_plane == self._data_plane
                    )
                )
            return int(value or 0)
        except SQLAlchemyError:
            _fail("authorization audit count failed")

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        _fail("authorization audit updates are forbidden")

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        _fail("authorization audit deletion is forbidden")


__all__ = [
    "HostAuthorizationAuditPersistenceError",
    "SqlAlchemyHostAuthorizationAuditRepository",
]
