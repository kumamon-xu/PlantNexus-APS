"""P4 checkpoint, request, attempt/result, and audit persistence adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import NoReturn, cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.domain.execution_contracts import (
    P4ContractError,
    canonical_contract_bytes,
    contract_fingerprint,
    require_p4_document,
)
from app.infrastructure.replan_persistence import (
    EXECUTION_EVENT_LEDGER,
    REPLAN_ATTEMPTS,
    REPLAN_AUDIT_RECORDS,
    REPLAN_PROJECTION_CHECKPOINTS,
    REPLAN_REQUEST_EVENTS,
    REPLAN_REQUESTS,
    REPLAN_RESULTS,
    ArtifactReference,
    ProjectionCheckpoint,
    ReplanAttemptReference,
    ReplanAuditRecord,
    ReplanResultReference,
    canonical_p4_document,
    internal_record_bytes,
    internal_record_sha256,
    load_internal_record,
    load_p4_document,
    validate_projection_checkpoint,
    validate_replan_attempt,
    validate_replan_audit_record,
    validate_replan_result,
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


@dataclass(frozen=True)
class StoredProjectionCheckpoint:
    checkpoint: ProjectionCheckpoint
    state_revision: int


@dataclass(frozen=True)
class CheckpointWriteResult:
    checkpoint: ProjectionCheckpoint
    replayed: bool
    state_revision: int


@dataclass(frozen=True)
class StoredAppliedReplanResult:
    """A terminal result plus the durable immutable ChangeReport envelope."""

    result: dict[str, object]
    solver_report: dict[str, object]
    validation_report: dict[str, object]
    kpi: dict[str, object]
    change_report: dict[str, object]


@dataclass(frozen=True)
class StoredTerminalReplanResult:
    """A non-success terminal result plus its durable SolverReport bytes."""

    result: dict[str, object]
    solver_report: dict[str, object]


_APPLIED_RESULT_ENVELOPE_VERSION = "replan-applied-result-envelope.v1"
_TERMINAL_RESULT_ENVELOPE_VERSION = "replan-terminal-result-envelope.v1"


def _canonical_solver_report(
    document: Mapping[str, object],
) -> dict[str, object]:
    """Canonicalize solver-report.v2, which intentionally has no data-plane field."""

    candidate = dict(document)
    try:
        observed_version = require_p4_document(candidate)
        canonical = canonical_contract_bytes(candidate)
    except P4ContractError:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="solver_report",
            message="SolverReport failed semantic integrity precheck",
        )
    if observed_version != "solver-report.v2":
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="solver_report.solver_report_version",
            message="only solver-report.v2 is accepted",
        )
    return cast(dict[str, object], json.loads(canonical))


def _artifact_from_mapping(value: object, field: str) -> ArtifactReference:
    reference = require_mapping(value, field)
    return ArtifactReference(
        document_version=require_text(
            reference.get("document_version"), f"{field}.document_version"
        ),
        artifact_id=require_text(reference.get("artifact_id"), f"{field}.artifact_id"),
        fingerprint=require_text(reference.get("fingerprint"), f"{field}.fingerprint"),
    )


def _optional_artifact(value: object, field: str) -> ArtifactReference | None:
    return None if value is None else _artifact_from_mapping(value, field)


class SqlAlchemyProjectionCheckpointRepository:
    """CAS-update the operational projection checkpoint for one authority stream."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find_scope(
        self,
        connection: Connection,
        *,
        factory_id: str,
        planning_scope_id: str,
        authority_id: str,
        stream_id: str,
        stream_version: str,
    ) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_PROJECTION_CHECKPOINTS).where(
                REPLAN_PROJECTION_CHECKPOINTS.c.data_plane == self._data_plane.value,
                REPLAN_PROJECTION_CHECKPOINTS.c.factory_id == factory_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.planning_scope_id == planning_scope_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.authority_id == authority_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.stream_id == stream_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.stream_version == stream_version,
            )
        ).first()
        return row._mapping if row is not None else None

    def _find(
        self, connection: Connection, checkpoint: ProjectionCheckpoint
    ) -> RowMapping | None:
        return self._find_scope(
            connection,
            factory_id=checkpoint.factory_id,
            planning_scope_id=checkpoint.planning_scope_id,
            authority_id=checkpoint.authority_id,
            stream_id=checkpoint.stream_id,
            stream_version=checkpoint.stream_version,
        )

    def _load(self, row: RowMapping) -> StoredProjectionCheckpoint:
        document = load_internal_record(
            row["checkpoint_json"],
            row["checkpoint_sha256"],
            expected_version=ProjectionCheckpoint.record_version,
        )
        checkpoint = ProjectionCheckpoint(
            factory_id=require_text(document.get("factory_id"), "factory_id"),
            planning_scope_id=require_text(
                document.get("planning_scope_id"), "planning_scope_id"
            ),
            authority_id=require_text(document.get("authority_id"), "authority_id"),
            stream_id=require_text(document.get("stream_id"), "stream_id"),
            stream_version=require_text(
                document.get("stream_version"), "stream_version"
            ),
            last_applied_position=require_integer(
                document.get("last_applied_position"),
                "last_applied_position",
                minimum=1,
            ),
            prefix_fingerprint=require_text(
                document.get("prefix_fingerprint"), "prefix_fingerprint"
            ),
            fact_checkpoint=_artifact_from_mapping(
                document.get("fact_checkpoint"), "fact_checkpoint"
            ),
            updated_at_utc=require_text(
                document.get("updated_at_utc"), "updated_at_utc"
            ),
        )
        canonical = validate_projection_checkpoint(checkpoint)
        if canonical != bytes(row["checkpoint_json"]):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.projection_checkpoint",
                message="stored checkpoint failed canonical integrity verification",
            )
        expected: dict[str, object] = {
            "factory_id": row["factory_id"],
            "planning_scope_id": row["planning_scope_id"],
            "authority_id": row["authority_id"],
            "stream_id": row["stream_id"],
            "stream_version": row["stream_version"],
            "last_applied_position": row["last_applied_position"],
            "prefix_fingerprint": row["prefix_fingerprint"],
            "updated_at_utc": row["updated_at_utc"],
        }
        if any(
            checkpoint.as_document().get(field) != value
            for field, value in expected.items()
        ):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.projection_checkpoint",
                message="stored checkpoint metadata failed integrity verification",
            )
        fact = checkpoint.fact_checkpoint
        if (
            fact.document_version != row["fact_checkpoint_version"]
            or fact.artifact_id != row["fact_checkpoint_id"]
            or fact.fingerprint != row["fact_checkpoint_fingerprint"]
        ):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.fact_checkpoint",
                message="stored fact checkpoint reference failed integrity verification",
            )
        revision = require_integer(row["state_revision"], "state_revision", minimum=0)
        return StoredProjectionCheckpoint(
            checkpoint=checkpoint, state_revision=revision
        )

    def put_initial_in_transaction(
        self,
        connection: Connection,
        checkpoint: ProjectionCheckpoint,
    ) -> CheckpointWriteResult:
        canonical = validate_projection_checkpoint(checkpoint)
        if self._data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="P4 Production checkpoint persistence is not established",
            )
        existing = self._find(connection, checkpoint)
        if existing is not None:
            stored = self._load(existing)
            if canonical != bytes(existing["checkpoint_json"]):
                reject(
                    PersistenceFailure.STATE_CONFLICT,
                    field="checkpoint.scope",
                    message="checkpoint scope already has different state",
                )
            return CheckpointWriteResult(
                checkpoint=stored.checkpoint,
                replayed=True,
                state_revision=stored.state_revision,
            )
        fact = checkpoint.fact_checkpoint
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(REPLAN_PROJECTION_CHECKPOINTS).values(
                        data_plane=self._data_plane.value,
                        factory_id=checkpoint.factory_id,
                        planning_scope_id=checkpoint.planning_scope_id,
                        authority_id=checkpoint.authority_id,
                        stream_id=checkpoint.stream_id,
                        stream_version=checkpoint.stream_version,
                        last_applied_position=checkpoint.last_applied_position,
                        prefix_fingerprint=checkpoint.prefix_fingerprint,
                        fact_checkpoint_version=fact.document_version,
                        fact_checkpoint_id=fact.artifact_id,
                        fact_checkpoint_fingerprint=fact.fingerprint,
                        checkpoint_json=canonical,
                        checkpoint_sha256=internal_record_sha256(canonical),
                        state_revision=0,
                        updated_at_utc=checkpoint.updated_at_utc,
                    )
                )
        except IntegrityError:
            raced = self._find(connection, checkpoint)
            if raced is not None and bytes(raced["checkpoint_json"]) == canonical:
                stored = self._load(raced)
                return CheckpointWriteResult(
                    checkpoint=stored.checkpoint,
                    replayed=True,
                    state_revision=stored.state_revision,
                )
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="checkpoint.scope",
                message="checkpoint insert lost a concurrent race",
            )
        return CheckpointWriteResult(
            checkpoint=checkpoint, replayed=False, state_revision=0
        )

    def advance_in_transaction(
        self,
        connection: Connection,
        *,
        expected_position: int,
        expected_state_revision: int,
        checkpoint: ProjectionCheckpoint,
    ) -> CheckpointWriteResult:
        require_integer(expected_position, "expected_position", minimum=1)
        require_integer(expected_state_revision, "expected_state_revision", minimum=0)
        canonical = validate_projection_checkpoint(checkpoint)
        if self._data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="P4 Production checkpoint persistence is not established",
            )
        row = self._find(connection, checkpoint)
        if row is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="checkpoint.scope",
                message="projection checkpoint does not exist",
            )
        current = self._load(row)
        if canonical == bytes(row["checkpoint_json"]):
            return CheckpointWriteResult(
                checkpoint=current.checkpoint,
                replayed=True,
                state_revision=current.state_revision,
            )
        if (
            current.checkpoint.last_applied_position != expected_position
            or current.state_revision != expected_state_revision
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_position/expected_state_revision",
                message="projection checkpoint compare-and-set precondition failed",
            )
        if checkpoint.last_applied_position <= expected_position:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="last_applied_position",
                message="projection checkpoint cannot move backward or self-transition",
            )
        fact = checkpoint.fact_checkpoint
        result = connection.execute(
            update(REPLAN_PROJECTION_CHECKPOINTS)
            .where(
                REPLAN_PROJECTION_CHECKPOINTS.c.data_plane == self._data_plane.value,
                REPLAN_PROJECTION_CHECKPOINTS.c.factory_id == checkpoint.factory_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.planning_scope_id
                == checkpoint.planning_scope_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.authority_id == checkpoint.authority_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.stream_id == checkpoint.stream_id,
                REPLAN_PROJECTION_CHECKPOINTS.c.stream_version
                == checkpoint.stream_version,
                REPLAN_PROJECTION_CHECKPOINTS.c.last_applied_position
                == expected_position,
                REPLAN_PROJECTION_CHECKPOINTS.c.state_revision
                == expected_state_revision,
            )
            .values(
                last_applied_position=checkpoint.last_applied_position,
                prefix_fingerprint=checkpoint.prefix_fingerprint,
                fact_checkpoint_version=fact.document_version,
                fact_checkpoint_id=fact.artifact_id,
                fact_checkpoint_fingerprint=fact.fingerprint,
                checkpoint_json=canonical,
                checkpoint_sha256=internal_record_sha256(canonical),
                state_revision=expected_state_revision + 1,
                updated_at_utc=checkpoint.updated_at_utc,
            )
        )
        if result.rowcount != 1:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_position/expected_state_revision",
                message="projection checkpoint compare-and-set lost a concurrent race",
            )
        return CheckpointWriteResult(
            checkpoint=checkpoint,
            replayed=False,
            state_revision=expected_state_revision + 1,
        )

    def put_initial(self, checkpoint: ProjectionCheckpoint) -> CheckpointWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.put_initial_in_transaction(connection, checkpoint)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.put_initial",
                message="projection checkpoint transaction failed",
            )

    def advance(
        self,
        *,
        expected_position: int,
        expected_state_revision: int,
        checkpoint: ProjectionCheckpoint,
    ) -> CheckpointWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.advance_in_transaction(
                    connection,
                    expected_position=expected_position,
                    expected_state_revision=expected_state_revision,
                    checkpoint=checkpoint,
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.advance",
                message="projection checkpoint transaction failed",
            )

    def get(
        self, checkpoint: ProjectionCheckpoint
    ) -> StoredProjectionCheckpoint | None:
        try:
            with self._engine.connect() as connection:
                row = self._find(connection, checkpoint)
                return self._load(row) if row is not None else None
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get",
                message="projection checkpoint query failed",
            )

    def get_scope_in_transaction(
        self,
        connection: Connection,
        *,
        factory_id: str,
        planning_scope_id: str,
        authority_id: str,
        stream_id: str,
        stream_version: str,
    ) -> StoredProjectionCheckpoint | None:
        """Read a checkpoint under the caller's atomic projection boundary."""

        for field, value in (
            ("factory_id", factory_id),
            ("planning_scope_id", planning_scope_id),
            ("authority_id", authority_id),
            ("stream_id", stream_id),
            ("stream_version", stream_version),
        ):
            require_text(value, field)
        row = self._find_scope(
            connection,
            factory_id=factory_id,
            planning_scope_id=planning_scope_id,
            authority_id=authority_id,
            stream_id=stream_id,
            stream_version=stream_version,
        )
        return self._load(row) if row is not None else None

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="projection checkpoint deletion is forbidden",
        )


class SqlAlchemyReplanRequestRepository:
    """Persist immutable ReplanRequest carriers after durable lineage checks."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find(self, connection: Connection, request_id: str) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_REQUESTS).where(
                REPLAN_REQUESTS.c.data_plane == self._data_plane.value,
                REPLAN_REQUESTS.c.request_id == request_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> dict[str, object]:
        document = load_p4_document(
            row["document_json"],
            row["document_sha256"],
            expected_version="replan-request.v1",
            data_plane=self._data_plane,
        )
        stream = require_mapping(document.get("event_stream"), "event_stream")
        authority = require_mapping(stream.get("authority"), "event_stream.authority")
        source_stream = require_mapping(
            stream.get("source_stream"), "event_stream.source_stream"
        )
        fact = require_mapping(
            stream.get("fact_checkpoint"), "event_stream.fact_checkpoint"
        )
        base = require_mapping(
            document.get("base_schedule_version"), "base_schedule_version"
        )
        expected: dict[str, object] = {
            "request_id": row["request_id"],
            "request_fingerprint": row["request_fingerprint"],
            "environment": row["environment"],
            "factory_id": row["factory_id"],
            "planning_scope_id": row["planning_scope_id"],
            "requested_at_utc": row["requested_at_utc"],
            "correlation_id": row["correlation_id"],
        }
        nested = (
            (authority.get("authority_id"), row["authority_id"]),
            (source_stream.get("stream_id"), row["stream_id"]),
            (source_stream.get("stream_version"), row["stream_version"]),
            (stream.get("from_position"), row["from_position"]),
            (stream.get("through_position"), row["through_position"]),
            (stream.get("stream_fingerprint"), row["stream_fingerprint"]),
            (fact.get("document_version"), row["fact_checkpoint_version"]),
            (fact.get("artifact_id"), row["fact_checkpoint_id"]),
            (fact.get("fingerprint"), row["fact_checkpoint_fingerprint"]),
            (base.get("schedule_version_id"), row["base_schedule_version_id"]),
        )
        if any(
            document.get(field) != value for field, value in expected.items()
        ) or any(actual != value for actual, value in nested):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_request",
                message="stored ReplanRequest metadata failed integrity verification",
            )
        return document

    def _resolve_existing(
        self, row: RowMapping, canonical: bytes
    ) -> DocumentWriteResult:
        if bytes(row["document_json"]) != canonical:
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="request_id/request_fingerprint",
                message="ReplanRequest identity is bound to different content",
            )
        return DocumentWriteResult(document=self._load(row), replayed=True)

    def _assert_checkpoint(
        self,
        connection: Connection,
        *,
        candidate: Mapping[str, object],
        stream: Mapping[str, object],
        authority: Mapping[str, object],
        source_stream: Mapping[str, object],
        fact: Mapping[str, object],
    ) -> None:
        row = connection.execute(
            select(REPLAN_PROJECTION_CHECKPOINTS).where(
                REPLAN_PROJECTION_CHECKPOINTS.c.data_plane == self._data_plane.value,
                REPLAN_PROJECTION_CHECKPOINTS.c.factory_id
                == candidate.get("factory_id"),
                REPLAN_PROJECTION_CHECKPOINTS.c.planning_scope_id
                == candidate.get("planning_scope_id"),
                REPLAN_PROJECTION_CHECKPOINTS.c.authority_id
                == authority.get("authority_id"),
                REPLAN_PROJECTION_CHECKPOINTS.c.stream_id
                == source_stream.get("stream_id"),
                REPLAN_PROJECTION_CHECKPOINTS.c.stream_version
                == source_stream.get("stream_version"),
            )
        ).first()
        if row is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="event_stream.fact_checkpoint",
                message="durable projection checkpoint is absent",
            )
        stored = row._mapping
        expected = (
            (stored["last_applied_position"], stream.get("through_position")),
            (stored["prefix_fingerprint"], stream.get("stream_fingerprint")),
            (stored["fact_checkpoint_version"], fact.get("document_version")),
            (stored["fact_checkpoint_id"], fact.get("artifact_id")),
            (stored["fact_checkpoint_fingerprint"], fact.get("fingerprint")),
        )
        if any(actual != value for actual, value in expected):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="event_stream.fact_checkpoint",
                message="request does not match the durable projection checkpoint",
            )

    def _event_links(
        self,
        connection: Connection,
        *,
        candidate: Mapping[str, object],
        stream: Mapping[str, object],
        authority: Mapping[str, object],
        source_stream: Mapping[str, object],
    ) -> tuple[dict[str, object], ...]:
        event_ids = stream.get("event_ids")
        event_fingerprints = stream.get("event_fingerprints")
        if not isinstance(event_ids, Sequence) or isinstance(event_ids, (str, bytes)):
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="event_stream.event_ids",
                message="must be an ordered sequence",
            )
        if not isinstance(event_fingerprints, Sequence) or isinstance(
            event_fingerprints, (str, bytes)
        ):
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="event_stream.event_fingerprints",
                message="must be an ordered sequence",
            )
        if len(event_ids) != len(event_fingerprints):
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="event_stream",
                message="event identity and fingerprint counts differ",
            )
        from_position = require_integer(
            stream.get("from_position"), "event_stream.from_position", minimum=1
        )
        links: list[dict[str, object]] = []
        for ordinal, (event_id_value, fingerprint_value) in enumerate(
            zip(event_ids, event_fingerprints, strict=True)
        ):
            event_id = require_text(event_id_value, f"event_ids[{ordinal}]")
            fingerprint = require_text(
                fingerprint_value, f"event_fingerprints[{ordinal}]"
            )
            source_position = from_position + ordinal
            row = connection.execute(
                select(EXECUTION_EVENT_LEDGER).where(
                    EXECUTION_EVENT_LEDGER.c.data_plane == self._data_plane.value,
                    EXECUTION_EVENT_LEDGER.c.event_id == event_id,
                )
            ).first()
            if row is None:
                reject(
                    PersistenceFailure.STATE_CONFLICT,
                    field=f"event_stream.event_ids[{ordinal}]",
                    message="referenced ExecutionEvent is absent from the ledger",
                )
            stored = row._mapping
            expected = (
                (stored["event_fingerprint"], fingerprint),
                (stored["factory_id"], candidate.get("factory_id")),
                (stored["planning_scope_id"], candidate.get("planning_scope_id")),
                (stored["authority_id"], authority.get("authority_id")),
                (stored["stream_id"], source_stream.get("stream_id")),
                (stored["stream_version"], source_stream.get("stream_version")),
                (stored["source_position"], source_position),
            )
            if any(actual != value for actual, value in expected):
                reject(
                    PersistenceFailure.STATE_CONFLICT,
                    field=f"event_stream.event_ids[{ordinal}]",
                    message="referenced ExecutionEvent lineage does not match",
                )
            links.append(
                {
                    "data_plane": self._data_plane.value,
                    "request_id": require_text(
                        candidate.get("request_id"), "request_id"
                    ),
                    "event_ordinal": ordinal,
                    "event_id": event_id,
                    "event_fingerprint": fingerprint,
                    "source_position": source_position,
                }
            )
        return tuple(links)

    def append_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
    ) -> DocumentWriteResult:
        candidate, canonical = canonical_p4_document(
            document,
            expected_version="replan-request.v1",
            data_plane=self._data_plane,
        )
        request_id = require_text(candidate.get("request_id"), "request_id")
        existing = self._find(connection, request_id)
        if existing is not None:
            return self._resolve_existing(existing, canonical)
        stream = require_mapping(candidate.get("event_stream"), "event_stream")
        authority = require_mapping(stream.get("authority"), "event_stream.authority")
        source_stream = require_mapping(
            stream.get("source_stream"), "event_stream.source_stream"
        )
        fact = require_mapping(
            stream.get("fact_checkpoint"), "event_stream.fact_checkpoint"
        )
        base = require_mapping(
            candidate.get("base_schedule_version"), "base_schedule_version"
        )
        self._assert_checkpoint(
            connection,
            candidate=candidate,
            stream=stream,
            authority=authority,
            source_stream=source_stream,
            fact=fact,
        )
        links = self._event_links(
            connection,
            candidate=candidate,
            stream=stream,
            authority=authority,
            source_stream=source_stream,
        )
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(REPLAN_REQUESTS).values(
                        data_plane=self._data_plane.value,
                        request_id=request_id,
                        request_fingerprint=require_text(
                            candidate.get("request_fingerprint"),
                            "request_fingerprint",
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
                        authority_id=require_text(
                            authority.get("authority_id"),
                            "event_stream.authority.authority_id",
                        ),
                        stream_id=require_text(
                            source_stream.get("stream_id"),
                            "event_stream.source_stream.stream_id",
                        ),
                        stream_version=require_text(
                            source_stream.get("stream_version"),
                            "event_stream.source_stream.stream_version",
                        ),
                        from_position=require_integer(
                            stream.get("from_position"),
                            "event_stream.from_position",
                            minimum=1,
                        ),
                        through_position=require_integer(
                            stream.get("through_position"),
                            "event_stream.through_position",
                            minimum=1,
                        ),
                        stream_fingerprint=require_text(
                            stream.get("stream_fingerprint"),
                            "event_stream.stream_fingerprint",
                        ),
                        fact_checkpoint_version=require_text(
                            fact.get("document_version"),
                            "event_stream.fact_checkpoint.document_version",
                        ),
                        fact_checkpoint_id=require_text(
                            fact.get("artifact_id"),
                            "event_stream.fact_checkpoint.artifact_id",
                        ),
                        fact_checkpoint_fingerprint=require_text(
                            fact.get("fingerprint"),
                            "event_stream.fact_checkpoint.fingerprint",
                        ),
                        base_schedule_version_id=require_text(
                            base.get("schedule_version_id"),
                            "base_schedule_version.schedule_version_id",
                        ),
                        requested_at_utc=require_text(
                            candidate.get("requested_at_utc"), "requested_at_utc"
                        ),
                        correlation_id=require_text(
                            candidate.get("correlation_id"), "correlation_id"
                        ),
                        document_json=canonical,
                        document_sha256=document_sha256(canonical),
                    )
                )
                connection.execute(insert(REPLAN_REQUEST_EVENTS), links)
        except IntegrityError:
            raced = self._find(connection, request_id)
            if raced is not None:
                return self._resolve_existing(raced, canonical)
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.append",
                message="ReplanRequest insert conflicted with durable lineage",
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
                message="ReplanRequest transaction failed",
            )

    def get(self, request_id: str) -> dict[str, object] | None:
        require_text(request_id, "request_id")
        try:
            with self._engine.connect() as connection:
                return self.get_in_transaction(connection, request_id)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get",
                message="ReplanRequest query failed",
            )

    def get_in_transaction(
        self, connection: Connection, request_id: str
    ) -> dict[str, object] | None:
        """Re-read an immutable request inside a caller-owned transaction."""

        require_text(request_id, "request_id")
        row = self._find(connection, request_id)
        return self._load(row) if row is not None else None

    def list_event_ids(self, request_id: str) -> tuple[str, ...]:
        require_text(request_id, "request_id")
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(REPLAN_REQUEST_EVENTS.c.event_id)
                    .where(
                        REPLAN_REQUEST_EVENTS.c.data_plane == self._data_plane.value,
                        REPLAN_REQUEST_EVENTS.c.request_id == request_id,
                    )
                    .order_by(REPLAN_REQUEST_EVENTS.c.event_ordinal)
                ).all()
                return tuple(cast(str, row.event_id) for row in rows)
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.list_event_ids",
                message="ReplanRequest event-link query failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="ReplanRequest updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="ReplanRequest deletion is forbidden",
        )


class SqlAlchemyReplanLineageRepository:
    """Append request-to-PlanningRun attempt and terminal result references."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    def _attempt_by_id(
        self, connection: Connection, attempt_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_ATTEMPTS).where(
                REPLAN_ATTEMPTS.c.data_plane == self._data_plane.value,
                REPLAN_ATTEMPTS.c.attempt_id == attempt_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _attempt_conflict(
        self, connection: Connection, attempt: ReplanAttemptReference
    ) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_ATTEMPTS).where(
                REPLAN_ATTEMPTS.c.data_plane == self._data_plane.value,
                (
                    (
                        (REPLAN_ATTEMPTS.c.request_id == attempt.request_id)
                        & (REPLAN_ATTEMPTS.c.attempt_number == attempt.attempt_number)
                    )
                    | (REPLAN_ATTEMPTS.c.planning_run_id == attempt.planning_run_id)
                    | (
                        (
                            REPLAN_ATTEMPTS.c.idempotency_scope
                            == attempt.idempotency_scope
                        )
                        & (
                            REPLAN_ATTEMPTS.c.idempotency_key_reference
                            == attempt.idempotency_key_reference
                        )
                    )
                ),
            )
        ).first()
        return row._mapping if row is not None else None

    def _load_attempt(self, row: RowMapping) -> dict[str, object]:
        document = load_internal_record(
            row["record_json"],
            row["record_sha256"],
            expected_version=ReplanAttemptReference.record_version,
        )
        attempt = ReplanAttemptReference(
            attempt_id=require_text(document.get("attempt_id"), "attempt_id"),
            attempt_fingerprint=require_text(
                document.get("attempt_fingerprint"), "attempt_fingerprint"
            ),
            request_id=require_text(document.get("request_id"), "request_id"),
            request_fingerprint=require_text(
                document.get("request_fingerprint"), "request_fingerprint"
            ),
            planning_run_id=require_text(
                document.get("planning_run_id"), "planning_run_id"
            ),
            attempt_number=require_integer(
                document.get("attempt_number"), "attempt_number", minimum=1
            ),
            idempotency_scope=require_text(
                document.get("idempotency_scope"), "idempotency_scope"
            ),
            idempotency_key_reference=require_text(
                document.get("idempotency_key_reference"),
                "idempotency_key_reference",
            ),
            correlation_id=require_text(
                document.get("correlation_id"), "correlation_id"
            ),
            created_at_utc=require_text(
                document.get("created_at_utc"), "created_at_utc"
            ),
        )
        canonical = validate_replan_attempt(attempt)
        if canonical != bytes(row["record_json"]):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_attempt",
                message="stored attempt failed canonical integrity verification",
            )
        expected: dict[str, object] = {
            "attempt_id": row["attempt_id"],
            "attempt_fingerprint": row["attempt_fingerprint"],
            "request_id": row["request_id"],
            "request_fingerprint": row["request_fingerprint"],
            "planning_run_id": row["planning_run_id"],
            "attempt_number": row["attempt_number"],
            "idempotency_scope": row["idempotency_scope"],
            "idempotency_key_reference": row["idempotency_key_reference"],
            "correlation_id": row["correlation_id"],
            "created_at_utc": row["created_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_attempt",
                message="stored attempt metadata failed integrity verification",
            )
        return document

    def append_attempt_in_transaction(
        self,
        connection: Connection,
        attempt: ReplanAttemptReference,
    ) -> DocumentWriteResult:
        canonical = validate_replan_attempt(attempt)
        if self._data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="P4 Production attempt persistence is not established",
            )
        request = connection.execute(
            select(REPLAN_REQUESTS).where(
                REPLAN_REQUESTS.c.data_plane == self._data_plane.value,
                REPLAN_REQUESTS.c.request_id == attempt.request_id,
            )
        ).first()
        if request is None or request._mapping["request_fingerprint"] != (
            attempt.request_fingerprint
        ):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="request_id/request_fingerprint",
                message="attempt does not reference the stored ReplanRequest",
            )
        existing = self._attempt_by_id(connection, attempt.attempt_id)
        if existing is None:
            existing = self._attempt_conflict(connection, attempt)
        if existing is not None:
            if bytes(existing["record_json"]) != canonical:
                reject(
                    PersistenceFailure.IDEMPOTENCY_CONFLICT,
                    field="attempt identity/idempotency",
                    message="attempt identity or key has different content",
                )
            return DocumentWriteResult(
                document=self._load_attempt(existing), replayed=True
            )
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(REPLAN_ATTEMPTS).values(
                        data_plane=self._data_plane.value,
                        attempt_id=attempt.attempt_id,
                        attempt_fingerprint=attempt.attempt_fingerprint,
                        request_id=attempt.request_id,
                        request_fingerprint=attempt.request_fingerprint,
                        planning_run_id=attempt.planning_run_id,
                        attempt_number=attempt.attempt_number,
                        idempotency_scope=attempt.idempotency_scope,
                        idempotency_key_reference=attempt.idempotency_key_reference,
                        correlation_id=attempt.correlation_id,
                        created_at_utc=attempt.created_at_utc,
                        record_json=canonical,
                        record_sha256=internal_record_sha256(canonical),
                    )
                )
        except IntegrityError:
            raced = self._attempt_by_id(connection, attempt.attempt_id)
            if raced is None:
                raced = self._attempt_conflict(connection, attempt)
            if raced is not None and bytes(raced["record_json"]) == canonical:
                return DocumentWriteResult(
                    document=self._load_attempt(raced), replayed=True
                )
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.append_attempt",
                message="attempt insert conflicted with stored lineage",
            )
        return DocumentWriteResult(document=attempt.as_document(), replayed=False)

    def append_attempt(self, attempt: ReplanAttemptReference) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.append_attempt_in_transaction(connection, attempt)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.append_attempt",
                message="replan attempt transaction failed",
            )

    def _result_by_id(
        self, connection: Connection, result_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_RESULTS).where(
                REPLAN_RESULTS.c.data_plane == self._data_plane.value,
                REPLAN_RESULTS.c.result_id == result_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _result_by_attempt(
        self, connection: Connection, attempt_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_RESULTS).where(
                REPLAN_RESULTS.c.data_plane == self._data_plane.value,
                REPLAN_RESULTS.c.attempt_id == attempt_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _result_value(self, document: Mapping[str, object]) -> ReplanResultReference:
        result = ReplanResultReference(
            result_id=require_text(document.get("result_id"), "result_id"),
            result_fingerprint=require_text(
                document.get("result_fingerprint"), "result_fingerprint"
            ),
            attempt_id=require_text(document.get("attempt_id"), "attempt_id"),
            request_id=require_text(document.get("request_id"), "request_id"),
            request_fingerprint=require_text(
                document.get("request_fingerprint"), "request_fingerprint"
            ),
            planning_run_id=require_text(
                document.get("planning_run_id"), "planning_run_id"
            ),
            planning_run_terminal_state=require_text(
                document.get("planning_run_terminal_state"),
                "planning_run_terminal_state",
            ),
            solver_report=_optional_artifact(
                document.get("solver_report"), "solver_report"
            ),
            validation_report=_optional_artifact(
                document.get("validation_report"), "validation_report"
            ),
            new_schedule_version=_optional_artifact(
                document.get("new_schedule_version"), "new_schedule_version"
            ),
            change_report=_optional_artifact(
                document.get("change_report"), "change_report"
            ),
            correlation_id=require_text(
                document.get("correlation_id"), "correlation_id"
            ),
            finished_at_utc=require_text(
                document.get("finished_at_utc"), "finished_at_utc"
            ),
        )
        validate_replan_result(result)
        return result

    def _load_result_record(
        self, row: RowMapping
    ) -> tuple[
        dict[str, object],
        dict[str, dict[str, object] | None] | None,
    ]:
        raw = row["record_json"]
        try:
            parsed = json.loads(bytes(raw).decode("utf-8"))
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_result",
                message="stored result record is invalid",
            )
        version = parsed.get("record_version") if isinstance(parsed, dict) else None
        if version == _APPLIED_RESULT_ENVELOPE_VERSION:
            envelope = load_internal_record(
                raw,
                row["record_sha256"],
                expected_version=_APPLIED_RESULT_ENVELOPE_VERSION,
            )
            result_document = require_mapping(envelope.get("result"), "result")
            solver_document = require_mapping(
                envelope.get("solver_report"), "solver_report"
            )
            validation_document = require_mapping(
                envelope.get("validation_report"), "validation_report"
            )
            kpi_document = require_mapping(envelope.get("kpi"), "kpi")
            change_document = require_mapping(
                envelope.get("change_report"), "change_report"
            )
            result = self._result_value(result_document)
            solver = _canonical_solver_report(solver_document)
            validation = cast(
                dict[str, object],
                json.loads(canonical_contract_bytes(validation_document)),
            )
            validation_basis = {
                key: value
                for key, value in validation.items()
                if key not in {"report_id", "report_fingerprint"}
            }
            if validation.get("report_fingerprint") != contract_fingerprint(
                validation_basis
            ):
                reject(
                    PersistenceFailure.PERSISTENCE_FAILED,
                    field="stored.replan_result.validation_report",
                    message="candidate validation identity is invalid",
                )
            kpi = cast(
                dict[str, object], json.loads(canonical_contract_bytes(kpi_document))
            )
            change, _ = canonical_p4_document(
                change_document,
                expected_version="change-report.v1",
                data_plane=self._data_plane,
            )
            reference = result.change_report
            solver_reference = result.solver_report
            validation_reference = result.validation_report
            schedule_reference = result.new_schedule_version
            formal_validation = require_mapping(
                validation.get("formal_validation"),
                "validation_report.formal_validation",
            )
            after_kpi = require_mapping(change.get("after_kpi"), "change_report.after_kpi")
            report_schedule = require_mapping(
                change.get("new_schedule_version"),
                "change_report.new_schedule_version",
            )
            if (
                reference is None
                or reference.artifact_id != change.get("report_id")
                or reference.fingerprint != change.get("report_fingerprint")
                or solver_reference is None
                or solver_reference.artifact_id != solver.get("report_id")
                or solver_reference.fingerprint != solver.get("report_fingerprint")
                or validation_reference is None
                or validation_reference.fingerprint
                != contract_fingerprint(formal_validation)
                or after_kpi.get("artifact_id") != kpi.get("kpi_id")
                or after_kpi.get("fingerprint") != contract_fingerprint(kpi)
                or schedule_reference is None
                or report_schedule.get("schedule_version_id")
                != schedule_reference.artifact_id
                or report_schedule.get("content_fingerprint")
                != schedule_reference.fingerprint
            ):
                reject(
                    PersistenceFailure.PERSISTENCE_FAILED,
                    field="stored.replan_result.change_report",
                    message="applied result envelope references differ",
                )
            document = result.as_document()
            artifacts: dict[str, dict[str, object] | None] | None = {
                "solver_report": solver,
                "validation_report": validation,
                "kpi": kpi,
                "change_report": change,
            }
        elif version == _TERMINAL_RESULT_ENVELOPE_VERSION:
            envelope = load_internal_record(
                raw,
                row["record_sha256"],
                expected_version=_TERMINAL_RESULT_ENVELOPE_VERSION,
            )
            result_document = require_mapping(envelope.get("result"), "result")
            solver_document = require_mapping(
                envelope.get("solver_report"), "solver_report"
            )
            result = self._result_value(result_document)
            solver = _canonical_solver_report(solver_document)
            solver_reference = result.solver_report
            if (
                result.planning_run_terminal_state == "COMPLETED"
                or solver_reference is None
                or solver_reference.artifact_id != solver.get("report_id")
                or solver_reference.fingerprint != solver.get("report_fingerprint")
                or result.validation_report is not None
                or result.new_schedule_version is not None
                or result.change_report is not None
            ):
                reject(
                    PersistenceFailure.PERSISTENCE_FAILED,
                    field="stored.replan_result.solver_report",
                    message="terminal result envelope references differ",
                )
            document = result.as_document()
            artifacts = {
                "solver_report": solver,
                "validation_report": None,
                "kpi": None,
                "change_report": None,
            }
        else:
            document = load_internal_record(
                raw,
                row["record_sha256"],
                expected_version=ReplanResultReference.record_version,
            )
            result = self._result_value(document)
            artifacts = None
        canonical = validate_replan_result(result)
        if artifacts is None and canonical != bytes(raw):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_result",
                message="stored result failed canonical integrity verification",
            )
        expected: dict[str, object] = {
            "result_id": row["result_id"],
            "result_fingerprint": row["result_fingerprint"],
            "attempt_id": row["attempt_id"],
            "request_id": row["request_id"],
            "request_fingerprint": row["request_fingerprint"],
            "planning_run_id": row["planning_run_id"],
            "planning_run_terminal_state": row["planning_run_terminal_state"],
            "correlation_id": row["correlation_id"],
            "finished_at_utc": row["finished_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_result",
                message="stored result metadata failed integrity verification",
            )
        return document, artifacts

    def _load_result(self, row: RowMapping) -> dict[str, object]:
        return self._load_result_record(row)[0]

    def _load_applied_result(self, row: RowMapping) -> StoredAppliedReplanResult:
        result, artifacts = self._load_result_record(row)
        if artifacts is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="stored.replan_result",
                message="stored result has no applied ChangeReport envelope",
            )
        solver = artifacts["solver_report"]
        validation = artifacts["validation_report"]
        kpi = artifacts["kpi"]
        change = artifacts["change_report"]
        if solver is None or validation is None or kpi is None or change is None:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_result",
                message="COMPLETED result artifact envelope is incomplete",
            )
        return StoredAppliedReplanResult(
            result=result,
            solver_report=solver,
            validation_report=validation,
            kpi=kpi,
            change_report=change,
        )

    def _load_terminal_result(self, row: RowMapping) -> StoredTerminalReplanResult:
        result, artifacts = self._load_result_record(row)
        if artifacts is None or artifacts["solver_report"] is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="stored.replan_result",
                message="stored terminal result has no SolverReport envelope",
            )
        if result.get("planning_run_terminal_state") == "COMPLETED":
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="stored.replan_result",
                message="stored result is not a non-success terminal",
            )
        return StoredTerminalReplanResult(
            result=result,
            solver_report=artifacts["solver_report"],
        )

    def append_result_in_transaction(
        self,
        connection: Connection,
        result: ReplanResultReference,
    ) -> DocumentWriteResult:
        canonical = validate_replan_result(result)
        return self._append_result_record_in_transaction(
            connection,
            result=result,
            record_bytes=canonical,
        )

    def _append_result_record_in_transaction(
        self,
        connection: Connection,
        *,
        result: ReplanResultReference,
        record_bytes: bytes,
    ) -> DocumentWriteResult:
        if self._data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="P4 Production result persistence is not established",
            )
        attempt_row = self._attempt_by_id(connection, result.attempt_id)
        if attempt_row is None:
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="attempt_id",
                message="result references an absent attempt",
            )
        attempt = attempt_row
        expected_attempt = (
            (attempt["request_id"], result.request_id),
            (attempt["request_fingerprint"], result.request_fingerprint),
            (attempt["planning_run_id"], result.planning_run_id),
        )
        if any(actual != value for actual, value in expected_attempt):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="result.lineage",
                message="result does not match its stored attempt lineage",
            )
        existing = self._result_by_id(connection, result.result_id)
        if existing is None:
            existing = self._result_by_attempt(connection, result.attempt_id)
        if existing is not None:
            if bytes(existing["record_json"]) != record_bytes:
                reject(
                    PersistenceFailure.IDEMPOTENCY_CONFLICT,
                    field="result_id/attempt_id",
                    message="result identity or attempt has different content",
                )
            return DocumentWriteResult(
                document=self._load_result(existing), replayed=True
            )
        solver = result.solver_report
        validation = result.validation_report
        schedule = result.new_schedule_version
        change = result.change_report
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(REPLAN_RESULTS).values(
                        data_plane=self._data_plane.value,
                        result_id=result.result_id,
                        result_fingerprint=result.result_fingerprint,
                        attempt_id=result.attempt_id,
                        request_id=result.request_id,
                        request_fingerprint=result.request_fingerprint,
                        planning_run_id=result.planning_run_id,
                        planning_run_terminal_state=(
                            result.planning_run_terminal_state
                        ),
                        solver_report_id=(
                            solver.artifact_id if solver is not None else None
                        ),
                        solver_report_fingerprint=(
                            solver.fingerprint if solver is not None else None
                        ),
                        validation_report_id=(
                            validation.artifact_id if validation is not None else None
                        ),
                        validation_report_fingerprint=(
                            validation.fingerprint if validation is not None else None
                        ),
                        new_schedule_version_id=(
                            schedule.artifact_id if schedule is not None else None
                        ),
                        new_schedule_content_fingerprint=(
                            schedule.fingerprint if schedule is not None else None
                        ),
                        change_report_id=(
                            change.artifact_id if change is not None else None
                        ),
                        change_report_fingerprint=(
                            change.fingerprint if change is not None else None
                        ),
                        correlation_id=result.correlation_id,
                        finished_at_utc=result.finished_at_utc,
                        record_json=record_bytes,
                        record_sha256=internal_record_sha256(record_bytes),
                    )
                )
        except IntegrityError:
            raced = self._result_by_id(connection, result.result_id)
            if raced is None:
                raced = self._result_by_attempt(connection, result.attempt_id)
            if raced is not None and bytes(raced["record_json"]) == record_bytes:
                return DocumentWriteResult(
                    document=self._load_result(raced), replayed=True
                )
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.append_result",
                message="result insert conflicted with stored lineage",
            )
        return DocumentWriteResult(document=result.as_document(), replayed=False)

    def append_applied_result_in_transaction(
        self,
        connection: Connection,
        *,
        result: ReplanResultReference,
        solver_report: Mapping[str, object],
        validation_report: Mapping[str, object],
        kpi: Mapping[str, object],
        change_report: Mapping[str, object],
    ) -> DocumentWriteResult:
        """Atomically store a COMPLETED result and its immutable report bytes."""

        validate_replan_result(result)
        solver = _canonical_solver_report(solver_report)
        validation = cast(
            dict[str, object], json.loads(canonical_contract_bytes(validation_report))
        )
        validation_basis = {
            key: value
            for key, value in validation.items()
            if key not in {"report_id", "report_fingerprint"}
        }
        canonical_validation_fingerprint = contract_fingerprint(validation_basis)
        canonical_kpi = cast(
            dict[str, object], json.loads(canonical_contract_bytes(kpi))
        )
        report, _ = canonical_p4_document(
            change_report,
            expected_version="change-report.v1",
            data_plane=self._data_plane,
        )
        reference = result.change_report
        solver_reference = result.solver_report
        validation_reference = result.validation_report
        schedule = result.new_schedule_version
        formal_validation = require_mapping(
            validation.get("formal_validation"),
            "validation_report.formal_validation",
        )
        after_kpi = require_mapping(report.get("after_kpi"), "change_report.after_kpi")
        report_schedule = require_mapping(
            report.get("new_schedule_version"),
            "change_report.new_schedule_version",
        )
        if (
            result.planning_run_terminal_state != "COMPLETED"
            or reference is None
            or reference.artifact_id != report.get("report_id")
            or reference.fingerprint != report.get("report_fingerprint")
            or solver_reference is None
            or solver_reference.artifact_id != solver.get("report_id")
            or solver_reference.fingerprint != solver.get("report_fingerprint")
            or validation.get("report_fingerprint")
            != canonical_validation_fingerprint
            or validation_reference is None
            or validation_reference.fingerprint
            != contract_fingerprint(formal_validation)
            or after_kpi.get("artifact_id") != canonical_kpi.get("kpi_id")
            or after_kpi.get("fingerprint") != contract_fingerprint(canonical_kpi)
            or schedule is None
            or report_schedule.get("schedule_version_id") != schedule.artifact_id
            or report_schedule.get("content_fingerprint") != schedule.fingerprint
        ):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="result/change_report",
                message="applied result and ChangeReport references differ",
            )
        envelope = internal_record_bytes(
            {
                "record_version": _APPLIED_RESULT_ENVELOPE_VERSION,
                "result": result.as_document(),
                "solver_report": solver,
                "validation_report": validation,
                "kpi": canonical_kpi,
                "change_report": report,
            }
        )
        return self._append_result_record_in_transaction(
            connection,
            result=result,
            record_bytes=envelope,
        )

    def append_terminal_result_in_transaction(
        self,
        connection: Connection,
        *,
        result: ReplanResultReference,
        solver_report: Mapping[str, object],
    ) -> DocumentWriteResult:
        """Atomically store a non-success terminal and exact SolverReport bytes."""

        validate_replan_result(result)
        solver = _canonical_solver_report(solver_report)
        solver_reference = result.solver_report
        if (
            result.planning_run_terminal_state == "COMPLETED"
            or solver_reference is None
            or solver_reference.artifact_id != solver.get("report_id")
            or solver_reference.fingerprint != solver.get("report_fingerprint")
            or result.validation_report is not None
            or result.new_schedule_version is not None
            or result.change_report is not None
        ):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="result/solver_report",
                message="terminal result and SolverReport references differ",
            )
        envelope = internal_record_bytes(
            {
                "record_version": _TERMINAL_RESULT_ENVELOPE_VERSION,
                "result": result.as_document(),
                "solver_report": solver,
            }
        )
        return self._append_result_record_in_transaction(
            connection,
            result=result,
            record_bytes=envelope,
        )

    def append_result(self, result: ReplanResultReference) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.append_result_in_transaction(connection, result)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.append_result",
                message="replan result transaction failed",
            )

    def get_attempt(self, attempt_id: str) -> dict[str, object] | None:
        require_text(attempt_id, "attempt_id")
        try:
            with self._engine.connect() as connection:
                return self.get_attempt_in_transaction(connection, attempt_id)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get_attempt",
                message="replan attempt query failed",
            )

    def get_attempt_in_transaction(
        self, connection: Connection, attempt_id: str
    ) -> dict[str, object] | None:
        require_text(attempt_id, "attempt_id")
        row = self._attempt_by_id(connection, attempt_id)
        return self._load_attempt(row) if row is not None else None

    def get_result_for_attempt(self, attempt_id: str) -> dict[str, object] | None:
        require_text(attempt_id, "attempt_id")
        try:
            with self._engine.connect() as connection:
                return self.get_result_for_attempt_in_transaction(
                    connection, attempt_id
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get_result_for_attempt",
                message="replan result query failed",
            )

    def get_result_for_attempt_in_transaction(
        self, connection: Connection, attempt_id: str
    ) -> dict[str, object] | None:
        require_text(attempt_id, "attempt_id")
        row = self._result_by_attempt(connection, attempt_id)
        return self._load_result(row) if row is not None else None

    def get_applied_result_for_attempt(
        self, attempt_id: str
    ) -> StoredAppliedReplanResult | None:
        require_text(attempt_id, "attempt_id")
        try:
            with self._engine.connect() as connection:
                return self.get_applied_result_for_attempt_in_transaction(
                    connection, attempt_id
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get_applied_result_for_attempt",
                message="applied replan result query failed",
            )

    def get_applied_result_for_attempt_in_transaction(
        self, connection: Connection, attempt_id: str
    ) -> StoredAppliedReplanResult | None:
        require_text(attempt_id, "attempt_id")
        row = self._result_by_attempt(connection, attempt_id)
        return self._load_applied_result(row) if row is not None else None

    def get_terminal_result_for_attempt(
        self, attempt_id: str
    ) -> StoredTerminalReplanResult | None:
        require_text(attempt_id, "attempt_id")
        try:
            with self._engine.connect() as connection:
                return self.get_terminal_result_for_attempt_in_transaction(
                    connection, attempt_id
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get_terminal_result_for_attempt",
                message="terminal result query failed",
            )

    def get_terminal_result_for_attempt_in_transaction(
        self, connection: Connection, attempt_id: str
    ) -> StoredTerminalReplanResult | None:
        require_text(attempt_id, "attempt_id")
        row = self._result_by_attempt(connection, attempt_id)
        return self._load_terminal_result(row) if row is not None else None

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="replan attempt/result updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="replan attempt/result deletion is forbidden",
        )


class SqlAlchemyReplanAuditRepository:
    """Append exact internal transaction audit records without P3 schema drift."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    def _find_by_id(
        self, connection: Connection, audit_record_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(REPLAN_AUDIT_RECORDS).where(
                REPLAN_AUDIT_RECORDS.c.data_plane == self._data_plane.value,
                REPLAN_AUDIT_RECORDS.c.audit_record_id == audit_record_id,
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
            select(REPLAN_AUDIT_RECORDS).where(
                REPLAN_AUDIT_RECORDS.c.data_plane == self._data_plane.value,
                REPLAN_AUDIT_RECORDS.c.idempotency_scope == scope,
                REPLAN_AUDIT_RECORDS.c.idempotency_key_reference == key_reference,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> dict[str, object]:
        document = load_internal_record(
            row["record_json"],
            row["record_sha256"],
            expected_version=ReplanAuditRecord.record_version,
        )
        expected: dict[str, object] = {
            "audit_record_id": row["audit_record_id"],
            "audit_fingerprint": row["audit_fingerprint"],
            "action": row["action"],
            "aggregate_type": row["aggregate_type"],
            "aggregate_id": row["aggregate_id"],
            "correlation_id": row["correlation_id"],
            "idempotency_scope": row["idempotency_scope"],
            "idempotency_key_reference": row["idempotency_key_reference"],
            "request_fingerprint": row["request_fingerprint"],
            "occurred_at_utc": row["occurred_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.replan_audit",
                message="stored audit metadata failed integrity verification",
            )
        return document

    def append_in_transaction(
        self,
        connection: Connection,
        record: ReplanAuditRecord,
    ) -> DocumentWriteResult:
        canonical = validate_replan_audit_record(record)
        if self._data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="P4 Production audit persistence is not established",
            )
        existing = self._find_by_id(connection, record.audit_record_id)
        if existing is None:
            existing = self._find_by_idempotency(
                connection,
                scope=record.idempotency_scope,
                key_reference=record.idempotency_key_reference,
            )
        if existing is not None:
            if bytes(existing["record_json"]) != canonical:
                reject(
                    PersistenceFailure.IDEMPOTENCY_CONFLICT,
                    field="audit identity/idempotency",
                    message="audit identity or key has different content",
                )
            return DocumentWriteResult(document=self._load(existing), replayed=True)
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(REPLAN_AUDIT_RECORDS).values(
                        data_plane=self._data_plane.value,
                        audit_record_id=record.audit_record_id,
                        audit_fingerprint=record.audit_fingerprint,
                        action=record.action.value,
                        aggregate_type=record.aggregate_type,
                        aggregate_id=record.aggregate_id,
                        correlation_id=record.correlation_id,
                        idempotency_scope=record.idempotency_scope,
                        idempotency_key_reference=(record.idempotency_key_reference),
                        request_fingerprint=record.request_fingerprint,
                        occurred_at_utc=record.occurred_at_utc,
                        record_json=canonical,
                        record_sha256=internal_record_sha256(canonical),
                    )
                )
        except IntegrityError:
            raced = self._find_by_id(connection, record.audit_record_id)
            if raced is None:
                raced = self._find_by_idempotency(
                    connection,
                    scope=record.idempotency_scope,
                    key_reference=record.idempotency_key_reference,
                )
            if raced is not None and bytes(raced["record_json"]) == canonical:
                return DocumentWriteResult(document=self._load(raced), replayed=True)
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.append_audit",
                message="audit insert conflicted with stored identity",
            )
        return DocumentWriteResult(document=record.as_document(), replayed=False)

    def append(self, record: ReplanAuditRecord) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.append_in_transaction(connection, record)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.append_audit",
                message="replan audit transaction failed",
            )

    def list_for_aggregate(
        self, *, aggregate_type: str, aggregate_id: str
    ) -> tuple[dict[str, object], ...]:
        require_text(aggregate_type, "aggregate_type")
        require_text(aggregate_id, "aggregate_id")
        try:
            with self._engine.connect() as connection:
                rows = connection.execute(
                    select(REPLAN_AUDIT_RECORDS)
                    .where(
                        REPLAN_AUDIT_RECORDS.c.data_plane == self._data_plane.value,
                        REPLAN_AUDIT_RECORDS.c.aggregate_type == aggregate_type,
                        REPLAN_AUDIT_RECORDS.c.aggregate_id == aggregate_id,
                    )
                    .order_by(
                        REPLAN_AUDIT_RECORDS.c.occurred_at_utc,
                        REPLAN_AUDIT_RECORDS.c.audit_record_id,
                    )
                ).all()
                return tuple(self._load(row._mapping) for row in rows)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.list_for_aggregate",
                message="replan audit query failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="replan audit updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="replan audit deletion is forbidden",
        )


__all__ = [
    "CheckpointWriteResult",
    "SqlAlchemyProjectionCheckpointRepository",
    "SqlAlchemyReplanAuditRepository",
    "SqlAlchemyReplanLineageRepository",
    "SqlAlchemyReplanRequestRepository",
    "StoredAppliedReplanResult",
    "StoredProjectionCheckpoint",
    "StoredTerminalReplanResult",
]
