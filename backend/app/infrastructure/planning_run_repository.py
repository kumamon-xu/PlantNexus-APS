"""Plane-scoped SQLAlchemy persistence for P8 PlanningRun orchestration."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from hashlib import sha256
import json
from typing import NoReturn, cast

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.application.planning_runs import (
    PlanningRunAttemptMutation,
    PlanningRunInitialization,
    PlanningRunRepositoryWrite,
    PlanningRunRetryMutation,
    PlanningRunTransitionMutation,
)
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.planning_run import (
    ATTEMPT_RETRYABLE_STATUSES,
    PlanningRunAggregate,
    PlanningRunAttempt,
    PlanningRunAttemptStatus,
    PlanningRunCommandRecord,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
    PlanningRunReadModel,
    PlanningRunWorkItem,
    reject,
    verify_attempt,
    verify_command_record,
    verify_work_item,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane


_METADATA = MetaData()


class _ConcurrentMaterializeRace(RuntimeError):
    """Leave a stale SQLite read transaction before replay lookup."""


_CANONICAL_INGRESS = Table(
    "canonical_ingress_records",
    _METADATA,
    Column("ingress_id", String(length=256), primary_key=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("run_fingerprint", String(length=71), nullable=False),
    Column("record_json", LargeBinary(), nullable=False),
    Column("record_sha256", String(length=64), nullable=False),
)

_PLANNING_RUNS = Table(
    "planning_runs",
    _METADATA,
    Column("planning_run_id", String(length=256), primary_key=True),
    Column("ingress_id", String(length=256), nullable=False, unique=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("tenant_id", String(length=256), nullable=False),
    Column("factory_id", String(length=256), nullable=False),
    Column("planning_scope_id", String(length=256), nullable=False),
    Column("revision", Integer(), nullable=False),
    Column("state", String(length=32), nullable=False),
    Column("terminal", Boolean(), nullable=False),
    Column("run_fingerprint", String(length=71), nullable=False),
    Column("source_record_fingerprint", String(length=71), nullable=False),
    Column("initial_run_json", LargeBinary(), nullable=False),
    Column("initial_run_sha256", String(length=64), nullable=False),
    Column("prepared_artifacts_json", LargeBinary(), nullable=False),
    Column("prepared_artifacts_sha256", String(length=64), nullable=False),
    Column("current_run_json", LargeBinary(), nullable=False),
    Column("current_run_sha256", String(length=64), nullable=False),
    Column("updated_at_utc", String(length=32), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
Index(
    "ix_planning_runs_scope_state",
    _PLANNING_RUNS.c.data_plane,
    _PLANNING_RUNS.c.tenant_id,
    _PLANNING_RUNS.c.factory_id,
    _PLANNING_RUNS.c.planning_scope_id,
    _PLANNING_RUNS.c.state,
)

_ATTEMPTS = Table(
    "planning_run_attempts",
    _METADATA,
    Column("attempt_id", String(length=256), primary_key=True),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("data_plane", String(length=16), nullable=False),
    Column("attempt_number", Integer(), nullable=False),
    Column("revision", Integer(), nullable=False),
    Column("status", String(length=32), nullable=False),
    Column("expected_run_revision", Integer(), nullable=False),
    Column("expected_run_state", String(length=32), nullable=False),
    Column("expected_run_fingerprint", String(length=71), nullable=False),
    Column("runtime_resolution_fingerprint", String(length=71), nullable=False),
    Column("extension_set_fingerprint", String(length=71), nullable=False),
    Column("available_at_utc", String(length=32), nullable=False),
    Column("timeout_at_utc", String(length=32), nullable=False),
    Column("attempt_json", LargeBinary(), nullable=False),
    Column("attempt_sha256", String(length=64), nullable=False),
    Column("updated_at_utc", String(length=32), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
    UniqueConstraint(
        "planning_run_id",
        "attempt_number",
        name="uq_planning_run_attempt_number",
    ),
)
Index(
    "ix_planning_run_attempts_run_status",
    _ATTEMPTS.c.data_plane,
    _ATTEMPTS.c.planning_run_id,
    _ATTEMPTS.c.status,
    _ATTEMPTS.c.attempt_number,
)

_WORK_ITEMS = Table(
    "planning_run_work_items",
    _METADATA,
    Column("work_item_id", String(length=256), primary_key=True),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("attempt_id", String(length=256), nullable=False, unique=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("attempt_number", Integer(), nullable=False),
    Column("expected_run_revision", Integer(), nullable=False),
    Column("expected_run_state", String(length=32), nullable=False),
    Column("expected_run_fingerprint", String(length=71), nullable=False),
    Column("work_item_fingerprint", String(length=71), nullable=False),
    Column("available_at_utc", String(length=32), nullable=False),
    Column("timeout_at_utc", String(length=32), nullable=False),
    Column("work_item_json", LargeBinary(), nullable=False),
    Column("work_item_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
Index(
    "ix_planning_run_work_items_ready",
    _WORK_ITEMS.c.data_plane,
    _WORK_ITEMS.c.available_at_utc,
    _WORK_ITEMS.c.timeout_at_utc,
    _WORK_ITEMS.c.attempt_number,
)

_AUDITS = Table(
    "planning_run_audit_records",
    _METADATA,
    Column("audit_event_id", String(length=256), primary_key=True),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("data_plane", String(length=16), nullable=False),
    Column("operation", String(length=64), nullable=False),
    Column("audit_fingerprint", String(length=71), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
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
    "ix_planning_run_audit_run_time",
    _AUDITS.c.data_plane,
    _AUDITS.c.planning_run_id,
    _AUDITS.c.occurred_at_utc,
)

_TRANSITIONS = Table(
    "planning_run_transitions",
    _METADATA,
    Column("planning_run_id", String(length=256), primary_key=True),
    Column("sequence", Integer(), primary_key=True),
    Column("data_plane", String(length=16), nullable=False),
    Column("from_state", String(length=32), nullable=True),
    Column("to_state", String(length=32), nullable=False),
    Column("before_run_fingerprint", String(length=71), nullable=True),
    Column("after_run_fingerprint", String(length=71), nullable=False),
    Column("audit_event_id", String(length=256), nullable=False),
    Column("audit_fingerprint", String(length=71), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("transition_json", LargeBinary(), nullable=False),
    Column("transition_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)

_COMMANDS = Table(
    "planning_run_command_records",
    _METADATA,
    Column("command_id", String(length=256), primary_key=True),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("data_plane", String(length=16), nullable=False),
    Column("operation", String(length=64), nullable=False),
    Column("scope_fingerprint", String(length=71), nullable=False),
    Column("key_reference", String(length=71), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("command_json", LargeBinary(), nullable=False),
    Column("command_sha256", String(length=64), nullable=False),
    Column(
        "stored_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
    UniqueConstraint(
        "data_plane",
        "scope_fingerprint",
        "key_reference",
        name="uq_planning_run_command_idempotency",
    ),
)
Index(
    "ix_planning_run_commands_run_time",
    _COMMANDS.c.data_plane,
    _COMMANDS.c.planning_run_id,
    _COMMANDS.c.occurred_at_utc,
)


def _bytes(row: RowMapping, field: str) -> bytes:
    value = row[field]
    if not isinstance(value, (bytes, bytearray, memoryview)):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored canonical bytes are invalid",
        )
    return bytes(value)


def _text(row: RowMapping, field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored text metadata is invalid",
        )
    return value


def _integer(row: RowMapping, field: str) -> int:
    value = row[field]
    if type(value) is not int:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored integer metadata is invalid",
        )
    return value


def _boolean(row: RowMapping, field: str) -> bool:
    value = row[field]
    if type(value) is not bool:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored boolean metadata is invalid",
        )
    return value


def _verified_bytes(row: RowMapping, field: str, digest_field: str) -> bytes:
    raw = _bytes(row, field)
    if sha256(raw).hexdigest() != _text(row, digest_field):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored canonical digest is invalid",
        )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlanningRunOrchestrationError(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored canonical JSON is unreadable",
        ) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=f"stored.{field}",
            message="Stored bytes are not canonical JSON",
        )
    return raw


class SqlAlchemyPlanningRunRepository:
    """Durable CAS repository permanently bound to one APS data plane."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> str:
        return self._data_plane.value

    @contextmanager
    def _consistent_read_connection(self) -> Iterator[Connection]:
        """Keep run/attempt/work rows on one database snapshot."""

        connection = self._engine.connect()
        try:
            if connection.dialect.name == "postgresql":
                connection = connection.execution_options(
                    isolation_level="REPEATABLE READ"
                )
            elif connection.dialect.name == "sqlite":
                # Python's sqlite legacy transaction mode does not BEGIN for
                # SELECT, so issue it explicitly before the first row read.
                connection.exec_driver_sql("BEGIN")
            yield connection
        finally:
            if connection.in_transaction():
                connection.rollback()
            connection.close()

    def _aggregate(self, row: RowMapping) -> PlanningRunAggregate:
        aggregate = PlanningRunAggregate(
            canonical_bytes=_verified_bytes(
                row, "current_run_json", "current_run_sha256"
            ),
            initial_run_bytes=_verified_bytes(
                row, "initial_run_json", "initial_run_sha256"
            ),
            prepared_artifacts_bytes=_verified_bytes(
                row, "prepared_artifacts_json", "prepared_artifacts_sha256"
            ),
            source_ingress_id=_text(row, "ingress_id"),
            source_record_fingerprint=_text(row, "source_record_fingerprint"),
        )
        document = aggregate.document
        scope = document.get("effective_scope")
        if (
            not isinstance(scope, Mapping)
            or document.get("planning_run_id") != _text(row, "planning_run_id")
            or aggregate.source_ingress_id != _text(row, "ingress_id")
            or document.get("revision") != _integer(row, "revision")
            or document.get("state") != _text(row, "state")
            or document.get("terminal") is not _boolean(row, "terminal")
            or document.get("run_fingerprint") != _text(row, "run_fingerprint")
            or aggregate.source_record_fingerprint
            != _text(row, "source_record_fingerprint")
            or document.get("updated_at_utc") != _text(row, "updated_at_utc")
            or scope.get("data_plane") != self.data_plane
            or scope.get("environment") != _text(row, "environment")
            or scope.get("tenant_id") != _text(row, "tenant_id")
            or scope.get("factory_id") != _text(row, "factory_id")
            or scope.get("planning_scope_id") != _text(row, "planning_scope_id")
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="stored.planning_run",
                message="PlanningRun row and canonical carrier differ",
            )
        return aggregate

    def _attempt(
        self, row: RowMapping, aggregate: PlanningRunAggregate
    ) -> PlanningRunAttempt:
        attempt = PlanningRunAttempt(
            _verified_bytes(row, "attempt_json", "attempt_sha256")
        )
        verify_attempt(attempt, aggregate=aggregate)
        document = attempt.document
        expected_updated_at = (
            document["finished_at_utc"]
            or document["started_at_utc"]
            or document["available_at_utc"]
        )
        if (
            document.get("attempt_id") != _text(row, "attempt_id")
            or document.get("planning_run_id") != _text(row, "planning_run_id")
            or _text(row, "data_plane") != self.data_plane
            or document.get("attempt_number") != _integer(row, "attempt_number")
            or document.get("revision") != _integer(row, "revision")
            or document.get("status") != _text(row, "status")
            or document.get("expected_run_revision")
            != _integer(row, "expected_run_revision")
            or document.get("expected_run_state")
            != _text(row, "expected_run_state")
            or document.get("expected_run_fingerprint")
            != _text(row, "expected_run_fingerprint")
            or document.get("runtime_resolution_fingerprint")
            != _text(row, "runtime_resolution_fingerprint")
            or document.get("extension_set_fingerprint")
            != _text(row, "extension_set_fingerprint")
            or document.get("available_at_utc") != _text(row, "available_at_utc")
            or document.get("timeout_at_utc") != _text(row, "timeout_at_utc")
            or expected_updated_at != _text(row, "updated_at_utc")
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="stored.planning_run_attempt",
                message="Attempt row and canonical record differ",
            )
        return attempt

    def _work_item(
        self,
        row: RowMapping,
        *,
        aggregate: PlanningRunAggregate,
        attempts: Mapping[str, PlanningRunAttempt],
    ) -> PlanningRunWorkItem:
        work_item = PlanningRunWorkItem(
            _verified_bytes(row, "work_item_json", "work_item_sha256")
        )
        attempt_id = _text(row, "attempt_id")
        attempt = attempts.get(attempt_id)
        if attempt is None:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="stored.work_item.attempt_id",
                message="Work item attempt is absent",
            )
        verify_work_item(
            work_item,
            aggregate=aggregate,
            attempt=attempt,
            bind_attempt_audit=False,
        )
        document = work_item.document
        if (
            document.get("work_item_id") != _text(row, "work_item_id")
            or document.get("planning_run_id") != _text(row, "planning_run_id")
            or document.get("attempt_id") != attempt_id
            or _text(row, "data_plane") != self.data_plane
            or document.get("attempt_number") != _integer(row, "attempt_number")
            or document.get("expected_run_revision")
            != _integer(row, "expected_run_revision")
            or document.get("expected_run_state")
            != _text(row, "expected_run_state")
            or document.get("expected_run_fingerprint")
            != _text(row, "expected_run_fingerprint")
            or document.get("work_item_fingerprint")
            != _text(row, "work_item_fingerprint")
            or document.get("available_at_utc") != _text(row, "available_at_utc")
            or document.get("timeout_at_utc") != _text(row, "timeout_at_utc")
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="stored.planning_run_work_item",
                message="Work-item row and canonical record differ",
            )
        return work_item

    def _command(self, row: RowMapping) -> PlanningRunCommandRecord:
        command = PlanningRunCommandRecord(
            _verified_bytes(row, "command_json", "command_sha256")
        )
        verify_command_record(command)
        document = command.document
        if (
            document.get("command_id") != _text(row, "command_id")
            or document.get("planning_run_id") != _text(row, "planning_run_id")
            or _text(row, "data_plane") != self.data_plane
            or document.get("operation") != _text(row, "operation")
            or document.get("scope_fingerprint")
            != _text(row, "scope_fingerprint")
            or document.get("key_reference") != _text(row, "key_reference")
            or document.get("request_fingerprint")
            != _text(row, "request_fingerprint")
            or document.get("occurred_at_utc") != _text(row, "occurred_at_utc")
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="stored.planning_run_command",
                message="Command row and canonical record differ",
            )
        return command

    def _get_row(
        self, connection: Connection, planning_run_id: str
    ) -> RowMapping | None:
        return (
            connection.execute(
                select(_PLANNING_RUNS).where(
                    _PLANNING_RUNS.c.planning_run_id == planning_run_id,
                    _PLANNING_RUNS.c.data_plane == self.data_plane,
                )
            )
            .mappings()
            .first()
        )

    def get(self, planning_run_id: str) -> PlanningRunReadModel | None:
        try:
            with self._consistent_read_connection() as connection:
                row = self._get_row(connection, planning_run_id)
                if row is None:
                    return None
                aggregate = self._aggregate(row)
                attempt_rows = (
                    connection.execute(
                        select(_ATTEMPTS)
                        .where(
                            _ATTEMPTS.c.planning_run_id == planning_run_id,
                            _ATTEMPTS.c.data_plane == self.data_plane,
                        )
                        .order_by(_ATTEMPTS.c.attempt_number)
                    )
                    .mappings()
                    .all()
                )
                attempts = tuple(
                    self._attempt(item, aggregate) for item in attempt_rows
                )
                if [item.document["attempt_number"] for item in attempts] != list(
                    range(1, len(attempts) + 1)
                ):
                    reject(
                        PlanningRunErrorCode.LINEAGE_INVALID,
                        field="stored.attempt_number",
                        message="Attempt sequence has a gap",
                    )
                attempt_map = {
                    cast(str, item.document["attempt_id"]): item for item in attempts
                }
                work_rows = (
                    connection.execute(
                        select(_WORK_ITEMS)
                        .where(
                            _WORK_ITEMS.c.planning_run_id == planning_run_id,
                            _WORK_ITEMS.c.data_plane == self.data_plane,
                        )
                        .order_by(_WORK_ITEMS.c.attempt_number)
                    )
                    .mappings()
                    .all()
                )
                work_items = tuple(
                    self._work_item(item, aggregate=aggregate, attempts=attempt_map)
                    for item in work_rows
                )
                if (
                    len(work_items) != len(attempts)
                    or [item.document["attempt_id"] for item in work_items]
                    != [item.document["attempt_id"] for item in attempts]
                ):
                    reject(
                        PlanningRunErrorCode.LINEAGE_INVALID,
                        field="stored.planning_run_work_items",
                        message="Attempt and immutable work-item sequences differ",
                    )
                return PlanningRunReadModel(
                    aggregate=aggregate, attempts=attempts, work_items=work_items
                )
        except PlanningRunOrchestrationError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.SYSTEM_ERROR,
                field="repository.get",
                message="PlanningRun read failed",
            ) from error

    def _get_command_row(
        self,
        connection: Connection,
        *,
        scope_fingerprint: str,
        key_reference: str,
    ) -> RowMapping | None:
        return (
            connection.execute(
                select(_COMMANDS).where(
                    _COMMANDS.c.data_plane == self.data_plane,
                    _COMMANDS.c.scope_fingerprint == scope_fingerprint,
                    _COMMANDS.c.key_reference == key_reference,
                )
            )
            .mappings()
            .first()
        )

    def get_command(
        self, *, scope_fingerprint: str, key_reference: str
    ) -> PlanningRunCommandRecord | None:
        try:
            with self._engine.connect() as connection:
                row = self._get_command_row(
                    connection,
                    scope_fingerprint=scope_fingerprint,
                    key_reference=key_reference,
                )
                return self._command(row) if row is not None else None
        except PlanningRunOrchestrationError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.SYSTEM_ERROR,
                field="repository.get_command",
                message="PlanningRun idempotency lookup failed",
            ) from error

    def _existing_command(
        self, connection: Connection, command: PlanningRunCommandRecord
    ) -> PlanningRunRepositoryWrite | None:
        document = command.document
        row = self._get_command_row(
            connection,
            scope_fingerprint=cast(str, document["scope_fingerprint"]),
            key_reference=cast(str, document["key_reference"]),
        )
        if row is None:
            return None
        existing = self._command(row)
        if existing.document.get("request_fingerprint") != document.get(
            "request_fingerprint"
        ):
            reject(
                PlanningRunErrorCode.IDEMPOTENCY_CONFLICT,
                field="idempotency_key",
                message="Stored command uses the key for different content",
            )
        return PlanningRunRepositoryWrite(command=existing, replayed=True)

    def _race_result(
        self,
        command: PlanningRunCommandRecord,
        *,
        missing_code: PlanningRunErrorCode = PlanningRunErrorCode.IDEMPOTENCY_CONFLICT,
        missing_field: str = "repository.write",
        missing_message: str = "Concurrent PlanningRun write conflicted",
    ) -> PlanningRunRepositoryWrite:
        document = command.document
        existing = self.get_command(
            scope_fingerprint=cast(str, document["scope_fingerprint"]),
            key_reference=cast(str, document["key_reference"]),
        )
        if existing is not None and existing.document.get(
            "request_fingerprint"
        ) == document.get("request_fingerprint"):
            return PlanningRunRepositoryWrite(command=existing, replayed=True)
        if existing is not None:
            reject(
                PlanningRunErrorCode.IDEMPOTENCY_CONFLICT,
                field="idempotency_key",
                message="Concurrent command reused a key for different content",
            )
        reject(missing_code, field=missing_field, message=missing_message)

    @staticmethod
    def _run_values(aggregate: PlanningRunAggregate) -> dict[str, object]:
        run = aggregate.document
        scope = cast(Mapping[str, object], run["effective_scope"])
        return {
            "planning_run_id": run["planning_run_id"],
            "ingress_id": aggregate.source_ingress_id,
            "data_plane": scope["data_plane"],
            "environment": scope["environment"],
            "tenant_id": scope["tenant_id"],
            "factory_id": scope["factory_id"],
            "planning_scope_id": scope["planning_scope_id"],
            "revision": run["revision"],
            "state": run["state"],
            "terminal": run["terminal"],
            "run_fingerprint": run["run_fingerprint"],
            "source_record_fingerprint": aggregate.source_record_fingerprint,
            "initial_run_json": aggregate.initial_run_bytes,
            "initial_run_sha256": sha256(aggregate.initial_run_bytes).hexdigest(),
            "prepared_artifacts_json": aggregate.prepared_artifacts_bytes,
            "prepared_artifacts_sha256": sha256(
                aggregate.prepared_artifacts_bytes
            ).hexdigest(),
            "current_run_json": aggregate.canonical_bytes,
            "current_run_sha256": sha256(aggregate.canonical_bytes).hexdigest(),
            "updated_at_utc": run["updated_at_utc"],
        }

    def _attempt_values(self, attempt: PlanningRunAttempt) -> dict[str, object]:
        document = attempt.document
        return {
            "attempt_id": document["attempt_id"],
            "planning_run_id": document["planning_run_id"],
            "data_plane": self.data_plane,
            "attempt_number": document["attempt_number"],
            "revision": document["revision"],
            "status": document["status"],
            "expected_run_revision": document["expected_run_revision"],
            "expected_run_state": document["expected_run_state"],
            "expected_run_fingerprint": document["expected_run_fingerprint"],
            "runtime_resolution_fingerprint": document[
                "runtime_resolution_fingerprint"
            ],
            "extension_set_fingerprint": document["extension_set_fingerprint"],
            "available_at_utc": document["available_at_utc"],
            "timeout_at_utc": document["timeout_at_utc"],
            "attempt_json": attempt.canonical_bytes,
            "attempt_sha256": sha256(attempt.canonical_bytes).hexdigest(),
            "updated_at_utc": document["finished_at_utc"]
            or document["started_at_utc"]
            or document["available_at_utc"],
        }

    def _work_values(self, work_item: PlanningRunWorkItem) -> dict[str, object]:
        document = work_item.document
        return {
            "work_item_id": document["work_item_id"],
            "planning_run_id": document["planning_run_id"],
            "attempt_id": document["attempt_id"],
            "data_plane": self.data_plane,
            "attempt_number": document["attempt_number"],
            "expected_run_revision": document["expected_run_revision"],
            "expected_run_state": document["expected_run_state"],
            "expected_run_fingerprint": document["expected_run_fingerprint"],
            "work_item_fingerprint": document["work_item_fingerprint"],
            "available_at_utc": document["available_at_utc"],
            "timeout_at_utc": document["timeout_at_utc"],
            "work_item_json": work_item.canonical_bytes,
            "work_item_sha256": sha256(work_item.canonical_bytes).hexdigest(),
        }

    def _insert_audit(
        self,
        connection: Connection,
        *,
        audit_bytes: bytes,
        operation: str,
        planning_run_id: str,
    ) -> None:
        try:
            document = cast(Mapping[str, object], json.loads(audit_bytes))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="audit_event",
                message="Audit event is unreadable",
            ) from error
        if canonical_json_bytes(document) != audit_bytes:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="audit_event",
                message="Audit event is not canonical JSON",
            )
        connection.execute(
            insert(_AUDITS).values(
                audit_event_id=document["audit_event_id"],
                planning_run_id=planning_run_id,
                data_plane=self.data_plane,
                operation=operation,
                audit_fingerprint=canonical_fingerprint(document),
                occurred_at_utc=document["occurred_at_utc"],
                audit_json=audit_bytes,
                audit_sha256=sha256(audit_bytes).hexdigest(),
            )
        )

    def _insert_transition(
        self,
        connection: Connection,
        *,
        aggregate: PlanningRunAggregate,
        transition_bytes: bytes,
        before_run_fingerprint: str | None,
    ) -> None:
        document = cast(Mapping[str, object], json.loads(transition_bytes))
        if canonical_json_bytes(document) != transition_bytes:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="transition",
                message="Transition evidence is not canonical JSON",
            )
        audit = cast(Mapping[str, object], document["audit"])
        connection.execute(
            insert(_TRANSITIONS).values(
                planning_run_id=aggregate.document["planning_run_id"],
                sequence=document["sequence"],
                data_plane=self.data_plane,
                from_state=document["from_state"],
                to_state=document["to_state"],
                before_run_fingerprint=before_run_fingerprint,
                after_run_fingerprint=aggregate.document["run_fingerprint"],
                audit_event_id=audit["artifact_id"],
                audit_fingerprint=audit["fingerprint"],
                occurred_at_utc=document["occurred_at_utc"],
                transition_json=transition_bytes,
                transition_sha256=sha256(transition_bytes).hexdigest(),
            )
        )

    def _insert_command(
        self, connection: Connection, command: PlanningRunCommandRecord
    ) -> None:
        verify_command_record(command)
        document = command.document
        connection.execute(
            insert(_COMMANDS).values(
                command_id=document["command_id"],
                planning_run_id=document["planning_run_id"],
                data_plane=self.data_plane,
                operation=document["operation"],
                scope_fingerprint=document["scope_fingerprint"],
                key_reference=document["key_reference"],
                request_fingerprint=document["request_fingerprint"],
                occurred_at_utc=document["occurred_at_utc"],
                command_json=command.canonical_bytes,
                command_sha256=sha256(command.canonical_bytes).hexdigest(),
            )
        )

    def _source_matches(
        self, connection: Connection, aggregate: PlanningRunAggregate
    ) -> None:
        row = (
            connection.execute(
                select(_CANONICAL_INGRESS).where(
                    _CANONICAL_INGRESS.c.ingress_id == aggregate.source_ingress_id,
                    _CANONICAL_INGRESS.c.data_plane == self.data_plane,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="source_ingress_id",
                message="Durable canonical ingress source is absent",
            )
        raw = _verified_bytes(row, "record_json", "record_sha256")
        source = cast(Mapping[str, object], json.loads(raw))
        expected_source_fingerprint = canonical_fingerprint(
            {key: value for key, value in source.items() if key != "record_fingerprint"}
        )
        expected_prepared = dict(
            cast(Mapping[str, object], source.get("prepared_artifacts", {}))
        )
        canonical_request = source.get("canonical_request")
        payload = (
            canonical_request.get("payload")
            if isinstance(canonical_request, Mapping)
            else None
        )
        if isinstance(payload, Mapping) and payload.get("synthetic") is True:
            expected_prepared["synthetic_provenance"] = payload.get(
                "synthetic_provenance"
            )
        if (
            source.get("record_fingerprint") != aggregate.source_record_fingerprint
            or source.get("record_fingerprint") != expected_source_fingerprint
            or row["planning_run_id"] != aggregate.document.get("planning_run_id")
            or row["run_fingerprint"]
            != aggregate.initial_document.get("run_fingerprint")
            or source.get("planning_run") != aggregate.initial_document
            or expected_prepared != aggregate.prepared_artifacts
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="source_ingress",
                message="PlanningRun source differs from durable canonical ingress",
            )

    def materialize(
        self, initialization: PlanningRunInitialization
    ) -> PlanningRunRepositoryWrite:
        verify_attempt(initialization.attempt, aggregate=initialization.aggregate)
        verify_work_item(
            initialization.work_item,
            aggregate=initialization.aggregate,
            attempt=initialization.attempt,
        )
        verify_command_record(initialization.command)
        try:
            with self._engine.begin() as connection:
                replay = self._existing_command(connection, initialization.command)
                if replay is not None:
                    return replay
                self._source_matches(connection, initialization.aggregate)
                existing_run = self._get_row(
                    connection,
                    cast(str, initialization.aggregate.document["planning_run_id"]),
                )
                if existing_run is not None:
                    raise _ConcurrentMaterializeRace
                connection.execute(
                    insert(_PLANNING_RUNS).values(
                        **self._run_values(initialization.aggregate)
                    )
                )
                self._insert_transition(
                    connection,
                    aggregate=initialization.aggregate,
                    transition_bytes=initialization.transition_bytes,
                    before_run_fingerprint=None,
                )
                self._insert_audit(
                    connection,
                    audit_bytes=initialization.audit_bytes,
                    operation="MATERIALIZE",
                    planning_run_id=cast(
                        str, initialization.aggregate.document["planning_run_id"]
                    ),
                )
                connection.execute(
                    insert(_ATTEMPTS).values(
                        **self._attempt_values(initialization.attempt)
                    )
                )
                try:
                    connection.execute(
                        insert(_WORK_ITEMS).values(
                            **self._work_values(initialization.work_item)
                        )
                    )
                except SQLAlchemyError as error:
                    raise PlanningRunOrchestrationError(
                        PlanningRunErrorCode.QUEUE_FAILED,
                        field="planning_run_work_item",
                        message="Queue-ready work item could not be committed",
                    ) from error
                self._insert_command(connection, initialization.command)
            return PlanningRunRepositoryWrite(
                command=initialization.command, replayed=False
            )
        except _ConcurrentMaterializeRace:
            return self._race_result(initialization.command)
        except PlanningRunOrchestrationError:
            raise
        except IntegrityError:
            return self._race_result(initialization.command)
        except SQLAlchemyError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.SYSTEM_ERROR,
                field="repository.materialize",
                message="PlanningRun materialization failed atomically",
            ) from error

    def _require_current(
        self, connection: Connection, aggregate: PlanningRunAggregate
    ) -> RowMapping:
        run_id = cast(str, aggregate.document["planning_run_id"])
        row = self._get_row(connection, run_id)
        if row is None:
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="planning_run_id",
                message="PlanningRun does not exist",
            )
        if (
            row["revision"] != aggregate.document["revision"]
            or row["state"] != aggregate.document["state"]
            or row["run_fingerprint"] != aggregate.document["run_fingerprint"]
            or _verified_bytes(row, "current_run_json", "current_run_sha256")
            != aggregate.canonical_bytes
        ):
            reject(
                PlanningRunErrorCode.STALE_RUN,
                field="planning_run",
                message="PlanningRun CAS precondition is stale",
            )
        return row

    def _require_attempt(
        self, connection: Connection, attempt: PlanningRunAttempt
    ) -> RowMapping:
        document = attempt.document
        row = (
            connection.execute(
                select(_ATTEMPTS).where(
                    _ATTEMPTS.c.attempt_id == document["attempt_id"],
                    _ATTEMPTS.c.data_plane == self.data_plane,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="attempt_id",
                message="PlanningRun attempt does not exist",
            )
        if (
            row["revision"] != document["revision"]
            or row["status"] != document["status"]
            or _verified_bytes(row, "attempt_json", "attempt_sha256")
            != attempt.canonical_bytes
        ):
            reject(
                PlanningRunErrorCode.STALE_ATTEMPT,
                field="attempt",
                message="Attempt CAS precondition is stale",
            )
        return row

    def _update_attempt(
        self,
        connection: Connection,
        *,
        previous: PlanningRunAttempt,
        attempt: PlanningRunAttempt,
    ) -> None:
        if previous.canonical_bytes == attempt.canonical_bytes:
            return
        result = connection.execute(
            update(_ATTEMPTS)
            .where(
                _ATTEMPTS.c.attempt_id == previous.document["attempt_id"],
                _ATTEMPTS.c.data_plane == self.data_plane,
                _ATTEMPTS.c.revision == previous.document["revision"],
                _ATTEMPTS.c.status == previous.document["status"],
            )
            .values(**self._attempt_values(attempt))
        )
        if result.rowcount != 1:
            reject(
                PlanningRunErrorCode.STALE_ATTEMPT,
                field="attempt",
                message="Attempt CAS update lost a concurrent race",
            )

    def apply_transition(
        self, mutation: PlanningRunTransitionMutation
    ) -> PlanningRunRepositoryWrite:
        if mutation.attempt is not None:
            verify_attempt(
                mutation.attempt,
                aggregate=mutation.aggregate,
                previous=(
                    mutation.previous_attempt.document
                    if mutation.previous_attempt is not None
                    and mutation.previous_attempt.canonical_bytes
                    != mutation.attempt.canonical_bytes
                    else None
                ),
            )
        verify_command_record(mutation.command)
        try:
            with self._engine.begin() as connection:
                replay = self._existing_command(connection, mutation.command)
                if replay is not None:
                    return replay
                self._require_current(connection, mutation.previous)
                if mutation.previous_attempt is not None:
                    self._require_attempt(connection, mutation.previous_attempt)
                    if mutation.attempt is not None:
                        self._update_attempt(
                            connection,
                            previous=mutation.previous_attempt,
                            attempt=mutation.attempt,
                        )
                command_document = mutation.command.document
                self._insert_audit(
                    connection,
                    audit_bytes=mutation.audit_bytes,
                    operation=cast(str, command_document["operation"]),
                    planning_run_id=cast(
                        str, mutation.aggregate.document["planning_run_id"]
                    ),
                )
                self._insert_transition(
                    connection,
                    aggregate=mutation.aggregate,
                    transition_bytes=mutation.transition_bytes,
                    before_run_fingerprint=cast(
                        str, mutation.previous.document["run_fingerprint"]
                    ),
                )
                values = self._run_values(mutation.aggregate)
                for immutable in (
                    "planning_run_id",
                    "ingress_id",
                    "data_plane",
                    "environment",
                    "tenant_id",
                    "factory_id",
                    "planning_scope_id",
                    "source_record_fingerprint",
                    "initial_run_json",
                    "initial_run_sha256",
                    "prepared_artifacts_json",
                    "prepared_artifacts_sha256",
                ):
                    values.pop(immutable)
                result = connection.execute(
                    update(_PLANNING_RUNS)
                    .where(
                        _PLANNING_RUNS.c.planning_run_id
                        == mutation.previous.document["planning_run_id"],
                        _PLANNING_RUNS.c.data_plane == self.data_plane,
                        _PLANNING_RUNS.c.revision
                        == mutation.previous.document["revision"],
                        _PLANNING_RUNS.c.state == mutation.previous.document["state"],
                        _PLANNING_RUNS.c.run_fingerprint
                        == mutation.previous.document["run_fingerprint"],
                    )
                    .values(**values)
                )
                if result.rowcount != 1:
                    reject(
                        PlanningRunErrorCode.STALE_RUN,
                        field="planning_run",
                        message="PlanningRun CAS update lost a concurrent race",
                    )
                self._insert_command(connection, mutation.command)
            return PlanningRunRepositoryWrite(command=mutation.command, replayed=False)
        except PlanningRunOrchestrationError as error:
            if error.code in {
                PlanningRunErrorCode.STALE_RUN,
                PlanningRunErrorCode.STALE_ATTEMPT,
            }:
                return self._race_result(
                    mutation.command,
                    missing_code=error.code,
                    missing_field=error.field,
                    missing_message=error.message,
                )
            raise
        except IntegrityError:
            return self._race_result(
                mutation.command,
                missing_code=PlanningRunErrorCode.STALE_RUN,
                missing_field="planning_run",
                missing_message="Concurrent PlanningRun transition lost its CAS race",
            )
        except SQLAlchemyError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.SYSTEM_ERROR,
                field="repository.apply_transition",
                message="PlanningRun transition failed atomically",
            ) from error

    def append_retry(
        self, mutation: PlanningRunRetryMutation
    ) -> PlanningRunRepositoryWrite:
        verify_attempt(mutation.attempt, aggregate=mutation.aggregate)
        verify_work_item(
            mutation.work_item,
            aggregate=mutation.aggregate,
            attempt=mutation.attempt,
        )
        try:
            with self._engine.begin() as connection:
                replay = self._existing_command(connection, mutation.command)
                if replay is not None:
                    return replay
                self._require_current(connection, mutation.aggregate)
                self._require_attempt(connection, mutation.failed_attempt)
                failed = mutation.failed_attempt.document
                if PlanningRunAttemptStatus(cast(str, failed["status"])) not in (
                    ATTEMPT_RETRYABLE_STATUSES
                ):
                    reject(
                        PlanningRunErrorCode.ATTEMPT_NOT_RETRYABLE,
                        field="failed_attempt.status",
                        message="Stored attempt is not retryable",
                    )
                latest = connection.scalar(
                    select(func.max(_ATTEMPTS.c.attempt_number)).where(
                        _ATTEMPTS.c.planning_run_id
                        == mutation.aggregate.document["planning_run_id"],
                        _ATTEMPTS.c.data_plane == self.data_plane,
                    )
                )
                if latest != failed["attempt_number"]:
                    reject(
                        PlanningRunErrorCode.STALE_ATTEMPT,
                        field="failed_attempt",
                        message="Retry lost a newer-attempt race",
                    )
                command_document = mutation.command.document
                self._insert_audit(
                    connection,
                    audit_bytes=mutation.audit_bytes,
                    operation=cast(str, command_document["operation"]),
                    planning_run_id=cast(
                        str, mutation.aggregate.document["planning_run_id"]
                    ),
                )
                connection.execute(
                    insert(_ATTEMPTS).values(**self._attempt_values(mutation.attempt))
                )
                try:
                    connection.execute(
                        insert(_WORK_ITEMS).values(
                            **self._work_values(mutation.work_item)
                        )
                    )
                except SQLAlchemyError as error:
                    raise PlanningRunOrchestrationError(
                        PlanningRunErrorCode.QUEUE_FAILED,
                        field="planning_run_work_item",
                        message="Retry work item could not be committed",
                    ) from error
                self._insert_command(connection, mutation.command)
            return PlanningRunRepositoryWrite(command=mutation.command, replayed=False)
        except PlanningRunOrchestrationError as error:
            if error.code in {
                PlanningRunErrorCode.STALE_RUN,
                PlanningRunErrorCode.STALE_ATTEMPT,
            }:
                return self._race_result(
                    mutation.command,
                    missing_code=error.code,
                    missing_field=error.field,
                    missing_message=error.message,
                )
            raise
        except IntegrityError:
            return self._race_result(
                mutation.command,
                missing_code=PlanningRunErrorCode.STALE_ATTEMPT,
                missing_field="failed_attempt",
                missing_message="Concurrent PlanningRun retry lost its CAS race",
            )
        except SQLAlchemyError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.SYSTEM_ERROR,
                field="repository.append_retry",
                message="PlanningRun retry failed atomically",
            ) from error

    def update_attempt(
        self, mutation: PlanningRunAttemptMutation
    ) -> PlanningRunRepositoryWrite:
        verify_attempt(
            mutation.attempt,
            aggregate=mutation.aggregate,
            previous=mutation.previous_attempt.document,
        )
        try:
            with self._engine.begin() as connection:
                replay = self._existing_command(connection, mutation.command)
                if replay is not None:
                    return replay
                self._require_current(connection, mutation.aggregate)
                self._require_attempt(connection, mutation.previous_attempt)
                self._update_attempt(
                    connection,
                    previous=mutation.previous_attempt,
                    attempt=mutation.attempt,
                )
                command_document = mutation.command.document
                self._insert_audit(
                    connection,
                    audit_bytes=mutation.audit_bytes,
                    operation=cast(str, command_document["operation"]),
                    planning_run_id=cast(
                        str, mutation.aggregate.document["planning_run_id"]
                    ),
                )
                self._insert_command(connection, mutation.command)
            return PlanningRunRepositoryWrite(command=mutation.command, replayed=False)
        except PlanningRunOrchestrationError as error:
            if error.code in {
                PlanningRunErrorCode.STALE_RUN,
                PlanningRunErrorCode.STALE_ATTEMPT,
            }:
                return self._race_result(
                    mutation.command,
                    missing_code=error.code,
                    missing_field=error.field,
                    missing_message=error.message,
                )
            raise
        except IntegrityError:
            return self._race_result(
                mutation.command,
                missing_code=PlanningRunErrorCode.STALE_ATTEMPT,
                missing_field="attempt",
                missing_message="Concurrent attempt update lost its CAS race",
            )
        except SQLAlchemyError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.SYSTEM_ERROR,
                field="repository.update_attempt",
                message="PlanningRun attempt update failed atomically",
            ) from error

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PlanningRunErrorCode.APPEND_ONLY,
            field="repository.update",
            message="Direct PlanningRun updates are forbidden; use CAS commands",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PlanningRunErrorCode.APPEND_ONLY,
            field="repository.delete",
            message="PlanningRun lineage cannot be deleted",
        )


__all__ = ["SqlAlchemyPlanningRunRepository"]
