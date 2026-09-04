"""Atomic SQLAlchemy persistence for P8 canonical ingress.

Repository instances are permanently bound to one data plane. The ingress
claim, immutable Snapshot, immutable PlanningProblem and audit event commit in
one database transaction; no method permits in-place mutation.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from typing import NoReturn, cast

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.application.canonical_ingress import (
    CanonicalIngressPersistenceCode,
    CanonicalIngressPersistenceError,
    CanonicalIngressRecord,
    CanonicalIngressWriteResult,
    verify_canonical_ingress_record,
)
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import (
    WorkspaceDataPlane,
    integrity_savepoint,
)
from app.planning.problem.contracts import (
    ImmutablePlanningProblemV2,
    PlanningProblemError,
)
from app.planning.problem.hashing import verify_problem_v2
from app.snapshots.contracts import SnapshotDataPlane, SnapshotError


_METADATA = MetaData()

_CANONICAL_INGRESS = Table(
    "canonical_ingress_records",
    _METADATA,
    Column("ingress_id", String(length=256), primary_key=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("tenant_id", String(length=256), nullable=False),
    Column("factory_id", String(length=256), nullable=False),
    Column("planning_scope_id", String(length=256), nullable=False),
    Column("request_id", String(length=256), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("idempotency_scope_fingerprint", String(length=71), nullable=False),
    Column("idempotency_key_reference", String(length=71), nullable=False),
    Column("payload_id", String(length=256), nullable=False),
    Column("payload_fingerprint", String(length=71), nullable=False),
    Column("runtime_resolution_fingerprint", String(length=71), nullable=False),
    Column("extension_set_fingerprint", String(length=71), nullable=False),
    Column("snapshot_id", String(length=256), nullable=False),
    Column("snapshot_hash", String(length=71), nullable=False),
    Column("problem_id", String(length=256), nullable=False),
    Column("problem_hash", String(length=71), nullable=False),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("run_fingerprint", String(length=71), nullable=False),
    Column("result_id", String(length=256), nullable=False),
    Column("result_fingerprint", String(length=71), nullable=False),
    Column("audit_event_id", String(length=256), nullable=False),
    Column("audit_fingerprint", String(length=71), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("record_json", LargeBinary(), nullable=False),
    Column("record_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
    UniqueConstraint(
        "idempotency_scope_fingerprint",
        "idempotency_key_reference",
        name="uq_canonical_ingress_idempotency",
    ),
    UniqueConstraint(
        "data_plane",
        "tenant_id",
        "request_id",
        name="uq_canonical_ingress_scope_request",
    ),
    UniqueConstraint("planning_run_id", name="uq_canonical_ingress_planning_run"),
    UniqueConstraint("result_id", name="uq_canonical_ingress_result"),
)
Index(
    "ix_canonical_ingress_scope_time",
    _CANONICAL_INGRESS.c.data_plane,
    _CANONICAL_INGRESS.c.tenant_id,
    _CANONICAL_INGRESS.c.factory_id,
    _CANONICAL_INGRESS.c.planning_scope_id,
    _CANONICAL_INGRESS.c.occurred_at_utc,
)
Index(
    "ix_canonical_ingress_correlation",
    _CANONICAL_INGRESS.c.data_plane,
    _CANONICAL_INGRESS.c.correlation_id,
)

_PLANNING_PROBLEMS = Table(
    "planning_problems",
    _METADATA,
    Column("problem_hash", String(length=71), primary_key=True),
    Column("problem_id", String(length=256), nullable=False, unique=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("snapshot_id", String(length=256), nullable=False),
    Column("snapshot_hash", String(length=71), nullable=False),
    Column("problem_version", String(length=64), nullable=False),
    Column("problem_builder_version", String(length=64), nullable=False),
    Column("canonicalization_version", String(length=64), nullable=False),
    Column("canonical_json", LargeBinary(), nullable=False),
    Column("canonical_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
Index(
    "ix_planning_problems_plane_snapshot",
    _PLANNING_PROBLEMS.c.data_plane,
    _PLANNING_PROBLEMS.c.snapshot_id,
)

_CANONICAL_INGRESS_AUDIT = Table(
    "canonical_ingress_audit_records",
    _METADATA,
    Column("audit_event_id", String(length=256), primary_key=True),
    Column("audit_fingerprint", String(length=71), nullable=False),
    Column("data_plane", String(length=16), nullable=False),
    Column("ingress_id", String(length=256), nullable=False, unique=True),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("request_id", String(length=256), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("idempotency_scope_fingerprint", String(length=71), nullable=False),
    Column("idempotency_key_reference", String(length=71), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("record_json", LargeBinary(), nullable=False),
    Column("record_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
Index(
    "ix_canonical_ingress_audit_run_time",
    _CANONICAL_INGRESS_AUDIT.c.data_plane,
    _CANONICAL_INGRESS_AUDIT.c.planning_run_id,
    _CANONICAL_INGRESS_AUDIT.c.occurred_at_utc,
)


def _reject(
    code: CanonicalIngressPersistenceCode,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise CanonicalIngressPersistenceError(code, field=field, message=message)


def _text(row: RowMapping, field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        _reject(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field=f"stored.{field}",
            message="Stored canonical ingress metadata is invalid",
        )
    return value


def _bytes(row: RowMapping, field: str) -> bytes:
    value = row[field]
    if not isinstance(value, (bytes, bytearray, memoryview)):
        _reject(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field=f"stored.{field}",
            message="Stored canonical ingress bytes are invalid",
        )
    return bytes(value)


def _contains_raw_idempotency_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return "idempotency_key" in value or any(
            _contains_raw_idempotency_key(child) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_raw_idempotency_key(child) for child in value)
    return False


class SqlAlchemyCanonicalIngressRepository:
    """One append-only repository permanently isolated to one P8 data plane."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane
        snapshot_plane = (
            SnapshotDataPlane.SIMULATION
            if data_plane is WorkspaceDataPlane.SIMULATION
            else SnapshotDataPlane.PRODUCTION
        )
        self._snapshots = SqlAlchemySnapshotRepository(
            engine, data_plane=snapshot_plane
        )

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find_by_idempotency(
        self,
        connection: Connection,
        *,
        scope_fingerprint: str,
        key_reference: str,
    ) -> RowMapping | None:
        row = connection.execute(
            select(_CANONICAL_INGRESS).where(
                _CANONICAL_INGRESS.c.data_plane == self._data_plane.value,
                _CANONICAL_INGRESS.c.idempotency_scope_fingerprint == scope_fingerprint,
                _CANONICAL_INGRESS.c.idempotency_key_reference == key_reference,
            )
        ).first()
        return row._mapping if row is not None else None

    def _find_problem(
        self,
        connection: Connection,
        *,
        problem_hash: str | None = None,
        problem_id: str | None = None,
    ) -> RowMapping | None:
        clauses = [_PLANNING_PROBLEMS.c.data_plane == self._data_plane.value]
        if problem_hash is not None:
            clauses.append(_PLANNING_PROBLEMS.c.problem_hash == problem_hash)
        if problem_id is not None:
            clauses.append(_PLANNING_PROBLEMS.c.problem_id == problem_id)
        row = connection.execute(select(_PLANNING_PROBLEMS).where(*clauses)).first()
        return row._mapping if row is not None else None

    def _load_problem(self, row: RowMapping) -> ImmutablePlanningProblemV2:
        canonical_bytes = _bytes(row, "canonical_json")
        if sha256(canonical_bytes).hexdigest() != _text(row, "canonical_sha256"):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.problem.canonical_sha256",
                message="Stored PlanningProblem bytes were modified",
            )
        problem = ImmutablePlanningProblemV2(
            canonical_bytes=canonical_bytes,
            problem_hash=_text(row, "problem_hash"),
            snapshot_id=_text(row, "snapshot_id"),
            problem_builder_version=_text(row, "problem_builder_version"),
        )
        try:
            verify_problem_v2(problem)
        except PlanningProblemError as error:
            raise CanonicalIngressPersistenceError(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.problem",
                message="Stored PlanningProblem failed integrity verification",
            ) from error
        document = problem.document
        if document["problem_version"] != _text(row, "problem_version") or document[
            "canonicalization_version"
        ] != _text(row, "canonicalization_version"):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.problem.metadata",
                message="Stored PlanningProblem metadata differs from its bytes",
            )
        return problem

    def _put_problem(
        self,
        connection: Connection,
        *,
        record: CanonicalIngressRecord,
        problem_id: str,
    ) -> None:
        problem = record.problem
        verify_problem_v2(problem)
        existing = self._find_problem(
            connection, problem_hash=problem.problem_hash
        ) or self._find_problem(connection, problem_id=problem_id)
        if existing is not None:
            stored = self._load_problem(existing)
            if (
                stored.problem_hash != problem.problem_hash
                or stored.canonical_bytes != problem.canonical_bytes
                or _text(existing, "problem_id") != problem_id
            ):
                _reject(
                    CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                    field="planning_problem",
                    message="PlanningProblem identity has different immutable content",
                )
            return
        document = problem.document
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(_PLANNING_PROBLEMS).values(
                        problem_hash=problem.problem_hash,
                        problem_id=problem_id,
                        data_plane=self._data_plane.value,
                        snapshot_id=problem.snapshot_id,
                        snapshot_hash=record.snapshot.snapshot_hash,
                        problem_version=document["problem_version"],
                        problem_builder_version=problem.problem_builder_version,
                        canonicalization_version=document["canonicalization_version"],
                        canonical_json=problem.canonical_bytes,
                        canonical_sha256=sha256(problem.canonical_bytes).hexdigest(),
                    )
                )
        except IntegrityError:
            existing = self._find_problem(
                connection, problem_hash=problem.problem_hash
            ) or self._find_problem(connection, problem_id=problem_id)
            if existing is None:
                _reject(
                    CanonicalIngressPersistenceCode.PERSISTENCE_FAILED,
                    field="planning_problem",
                    message="PlanningProblem insert lost an unresolved identity race",
                )
            stored = self._load_problem(existing)
            if (
                stored.canonical_bytes != problem.canonical_bytes
                or _text(existing, "problem_id") != problem_id
            ):
                _reject(
                    CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                    field="planning_problem",
                    message="PlanningProblem identity collision changed content",
                )

    def _put_audit(
        self,
        connection: Connection,
        *,
        record: CanonicalIngressRecord,
    ) -> None:
        document = record.document
        audit = cast(Mapping[str, object], document["audit_event"])
        audit_bytes = canonical_json_bytes(audit)
        audit_id = cast(str, audit["audit_event_id"])
        fingerprint = canonical_fingerprint(audit)
        row = connection.execute(
            select(_CANONICAL_INGRESS_AUDIT).where(
                _CANONICAL_INGRESS_AUDIT.c.audit_event_id == audit_id
            )
        ).first()
        if row is not None:
            stored = row._mapping
            if (
                _text(stored, "data_plane") != self._data_plane.value
                or _text(stored, "audit_fingerprint") != fingerprint
                or _bytes(stored, "record_json") != audit_bytes
            ):
                _reject(
                    CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                    field="audit_event",
                    message="Audit identity has different immutable content",
                )
            return
        idempotency = cast(Mapping[str, object], document["idempotency"])
        run = cast(Mapping[str, object], document["planning_run"])
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(_CANONICAL_INGRESS_AUDIT).values(
                        audit_event_id=audit_id,
                        audit_fingerprint=fingerprint,
                        data_plane=self._data_plane.value,
                        ingress_id=document["ingress_id"],
                        planning_run_id=run["planning_run_id"],
                        request_id=document["request_id"],
                        correlation_id=document["correlation_id"],
                        request_fingerprint=document["request_fingerprint"],
                        idempotency_scope_fingerprint=idempotency["scope_fingerprint"],
                        idempotency_key_reference=idempotency["key_reference"],
                        occurred_at_utc=document["occurred_at_utc"],
                        record_json=audit_bytes,
                        record_sha256=sha256(audit_bytes).hexdigest(),
                    )
                )
        except IntegrityError:
            row = connection.execute(
                select(_CANONICAL_INGRESS_AUDIT).where(
                    _CANONICAL_INGRESS_AUDIT.c.audit_event_id == audit_id
                )
            ).first()
            if row is None or _bytes(row._mapping, "record_json") != audit_bytes:
                _reject(
                    CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                    field="audit_event",
                    message="Audit insert lost an immutable identity race",
                )

    def _load(self, connection: Connection, row: RowMapping) -> CanonicalIngressRecord:
        record_bytes = _bytes(row, "record_json")
        if sha256(record_bytes).hexdigest() != _text(row, "record_sha256"):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.record_sha256",
                message="Stored canonical ingress bytes were modified",
            )
        try:
            document = json.loads(record_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CanonicalIngressPersistenceError(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.record_json",
                message="Stored canonical ingress JSON is unreadable",
            ) from error
        if (
            not isinstance(document, dict)
            or canonical_json_bytes(document) != record_bytes
        ):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.record_json",
                message="Stored canonical ingress bytes are not canonical-json.v1",
            )
        if _contains_raw_idempotency_key(document):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.canonical_request",
                message="Stored canonical ingress contains a forbidden raw key",
            )
        if (
            document.get("ingress_id") != _text(row, "ingress_id")
            or document.get("request_id") != _text(row, "request_id")
            or document.get("request_fingerprint") != _text(row, "request_fingerprint")
        ):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.metadata",
                message="Stored canonical ingress metadata differs from its bytes",
            )
        snapshot = self._snapshots.get_by_id_in_transaction(
            connection, _text(row, "snapshot_id")
        )
        if snapshot is None or snapshot.snapshot_hash != _text(row, "snapshot_hash"):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.snapshot",
                message="Canonical ingress Snapshot reference cannot be verified",
            )
        problem_row = self._find_problem(
            connection, problem_hash=_text(row, "problem_hash")
        )
        if problem_row is None or _text(problem_row, "problem_id") != _text(
            row, "problem_id"
        ):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.problem",
                message="Canonical ingress PlanningProblem reference cannot be verified",
            )
        problem = self._load_problem(problem_row)
        audit = cast(Mapping[str, object], document["audit_event"])
        audit_bytes = canonical_json_bytes(audit)
        audit_row = connection.execute(
            select(_CANONICAL_INGRESS_AUDIT).where(
                _CANONICAL_INGRESS_AUDIT.c.audit_event_id
                == _text(row, "audit_event_id"),
                _CANONICAL_INGRESS_AUDIT.c.data_plane == self._data_plane.value,
            )
        ).first()
        if (
            audit_row is None
            or _bytes(audit_row._mapping, "record_json") != audit_bytes
            or _text(audit_row._mapping, "audit_fingerprint")
            != canonical_fingerprint(audit)
        ):
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="stored.audit_event",
                message="Canonical ingress audit reference cannot be verified",
            )
        record = CanonicalIngressRecord(
            canonical_bytes=record_bytes,
            snapshot=snapshot,
            problem=problem,
        )
        verify_canonical_ingress_record(record)
        return record

    def _resolve_existing(
        self,
        connection: Connection,
        row: RowMapping,
        *,
        request_fingerprint: str,
    ) -> CanonicalIngressWriteResult:
        if _text(row, "request_fingerprint") != request_fingerprint:
            _reject(
                CanonicalIngressPersistenceCode.IDEMPOTENCY_CONFLICT,
                field="idempotency_key_reference",
                message="Idempotency identity is bound to another request",
            )
        return CanonicalIngressWriteResult(
            record=self._load(connection, row), replayed=True
        )

    def get_by_idempotency(
        self,
        *,
        scope_fingerprint: str,
        key_reference: str,
    ) -> CanonicalIngressRecord | None:
        try:
            with self._engine.connect() as connection:
                row = self._find_by_idempotency(
                    connection,
                    scope_fingerprint=scope_fingerprint,
                    key_reference=key_reference,
                )
                return self._load(connection, row) if row is not None else None
        except CanonicalIngressPersistenceError:
            raise
        except (SnapshotError, PlanningProblemError, SQLAlchemyError) as error:
            raise CanonicalIngressPersistenceError(
                CanonicalIngressPersistenceCode.PERSISTENCE_FAILED,
                field="repository.get_by_idempotency",
                message="Canonical ingress lookup failed",
            ) from error

    def commit(self, record: CanonicalIngressRecord) -> CanonicalIngressWriteResult:
        verify_canonical_ingress_record(record)
        document = record.document
        scope = cast(Mapping[str, object], document["effective_scope"])
        if scope.get("data_plane") != self._data_plane.value:
            _reject(
                CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                field="effective_scope.data_plane",
                message="Canonical ingress crossed its repository data plane",
            )
        idempotency = cast(Mapping[str, object], document["idempotency"])
        request_fingerprint = cast(str, document["request_fingerprint"])
        scope_fingerprint = cast(str, idempotency["scope_fingerprint"])
        key_reference = cast(str, idempotency["key_reference"])
        try:
            with self._engine.begin() as connection:
                existing = self._find_by_idempotency(
                    connection,
                    scope_fingerprint=scope_fingerprint,
                    key_reference=key_reference,
                )
                if existing is not None:
                    return self._resolve_existing(
                        connection,
                        existing,
                        request_fingerprint=request_fingerprint,
                    )
                values = self._row_values(record)
                try:
                    with integrity_savepoint(connection):
                        connection.execute(insert(_CANONICAL_INGRESS).values(**values))
                except IntegrityError:
                    existing = self._find_by_idempotency(
                        connection,
                        scope_fingerprint=scope_fingerprint,
                        key_reference=key_reference,
                    )
                    if existing is not None:
                        return self._resolve_existing(
                            connection,
                            existing,
                            request_fingerprint=request_fingerprint,
                        )
                    _reject(
                        CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
                        field="canonical_ingress",
                        message="Canonical ingress identity already has other content",
                    )
                self._snapshots.put_in_transaction(connection, record.snapshot)
                prepared = cast(Mapping[str, object], document["prepared_artifacts"])
                problem_reference = cast(Mapping[str, object], prepared["problem"])
                self._put_problem(
                    connection,
                    record=record,
                    problem_id=cast(str, problem_reference["artifact_id"]),
                )
                self._put_audit(connection, record=record)
            return CanonicalIngressWriteResult(record=record, replayed=False)
        except CanonicalIngressPersistenceError:
            raise
        except (SnapshotError, PlanningProblemError, SQLAlchemyError) as error:
            raise CanonicalIngressPersistenceError(
                CanonicalIngressPersistenceCode.PERSISTENCE_FAILED,
                field="repository.commit",
                message="Canonical ingress transaction failed",
            ) from error

    def _row_values(self, record: CanonicalIngressRecord) -> dict[str, object]:
        document = record.document
        scope = cast(Mapping[str, object], document["effective_scope"])
        idempotency = cast(Mapping[str, object], document["idempotency"])
        prepared = cast(Mapping[str, object], document["prepared_artifacts"])
        payload = cast(
            Mapping[str, object],
            cast(Mapping[str, object], document["canonical_request"])["payload"],
        )
        runtime = cast(Mapping[str, object], document["runtime_resolution"])
        extension_set = cast(Mapping[str, object], runtime["extension_set"])
        snapshot_ref = cast(Mapping[str, object], prepared["snapshot"])
        problem_ref = cast(Mapping[str, object], prepared["problem"])
        run = cast(Mapping[str, object], document["planning_run"])
        run_ingress = cast(Mapping[str, object], run["ingress"])
        payload_ref = cast(Mapping[str, object], run_ingress["payload"])
        result = cast(Mapping[str, object], document["canonical_ingress_result"])
        audit = cast(Mapping[str, object], document["audit_event"])
        audit_fingerprint = canonical_fingerprint(audit)
        return {
            "ingress_id": document["ingress_id"],
            "data_plane": scope["data_plane"],
            "environment": scope["environment"],
            "tenant_id": scope["tenant_id"],
            "factory_id": scope["factory_id"],
            "planning_scope_id": scope["planning_scope_id"],
            "request_id": document["request_id"],
            "correlation_id": document["correlation_id"],
            "request_fingerprint": document["request_fingerprint"],
            "idempotency_scope_fingerprint": idempotency["scope_fingerprint"],
            "idempotency_key_reference": idempotency["key_reference"],
            "payload_id": payload["package_id"],
            "payload_fingerprint": payload_ref["fingerprint"],
            "runtime_resolution_fingerprint": runtime["resolution_fingerprint"],
            "extension_set_fingerprint": extension_set["extension_set_fingerprint"],
            "snapshot_id": snapshot_ref["artifact_id"],
            "snapshot_hash": snapshot_ref["fingerprint"],
            "problem_id": problem_ref["artifact_id"],
            "problem_hash": problem_ref["fingerprint"],
            "planning_run_id": run["planning_run_id"],
            "run_fingerprint": run["run_fingerprint"],
            "result_id": result["result_id"],
            "result_fingerprint": result["result_fingerprint"],
            "audit_event_id": audit["audit_event_id"],
            "audit_fingerprint": audit_fingerprint,
            "occurred_at_utc": document["occurred_at_utc"],
            "record_json": record.canonical_bytes,
            "record_sha256": sha256(record.canonical_bytes).hexdigest(),
        }

    def update(self, _record: CanonicalIngressRecord) -> NoReturn:
        _reject(
            CanonicalIngressPersistenceCode.APPEND_ONLY,
            field="repository.update",
            message="Canonical ingress records are append-only",
        )

    def delete(self, _ingress_id: str) -> NoReturn:
        _reject(
            CanonicalIngressPersistenceCode.APPEND_ONLY,
            field="repository.delete",
            message="Canonical ingress records are append-only",
        )


__all__ = ["SqlAlchemyCanonicalIngressRepository"]
