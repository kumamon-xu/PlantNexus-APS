"""Plane-scoped ScheduleVersion insert and state-CAS persistence primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.domain.state_machines.schedule_version import (
    ScheduleVersionPersistenceTransitionError,
    immutable_schedule_fingerprint,
    require_schedule_version_transition,
)
from app.domain.workspace_contracts import canonical_workspace_bytes
from app.infrastructure.workspace_persistence import (
    SCHEDULE_VERSIONS,
    DocumentWriteResult,
    PersistenceFailure,
    StateWriteResult,
    WorkspaceDataPlane,
    WorkspacePersistenceError,
    canonical_document,
    document_sha256,
    integrity_savepoint,
    load_document,
    reject,
    require_integer,
    require_mapping,
    require_text,
)


@dataclass(frozen=True)
class StoredScheduleVersion:
    document: dict[str, object]
    state_revision: int


class SqlAlchemyScheduleVersionRepository:
    """Persist immutable version content while CAS-updating state metadata."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find(
        self, connection: Connection, schedule_version_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(SCHEDULE_VERSIONS).where(
                SCHEDULE_VERSIONS.c.data_plane == self._data_plane.value,
                SCHEDULE_VERSIONS.c.schedule_version_id == schedule_version_id,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> dict[str, object]:
        document = load_document(
            row["document_json"],
            row["document_sha256"],
            expected_version="schedule-version.v1",
            data_plane=self._data_plane,
        )
        expected = {
            "schedule_version_id": row["schedule_version_id"],
            "revision": row["revision"],
            "state": row["state"],
            "content_fingerprint": row["content_fingerprint"],
            "created_at_utc": row["created_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.schedule_version",
                message="stored ScheduleVersion metadata failed integrity verification",
            )
        if immutable_schedule_fingerprint(document) != row["immutable_fingerprint"]:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.immutable_fingerprint",
                message="stored ScheduleVersion content failed integrity verification",
            )
        return document

    def _candidate(
        self, document: Mapping[str, object]
    ) -> tuple[dict[str, object], bytes]:
        candidate, canonical = canonical_document(
            document,
            expected_version="schedule-version.v1",
            data_plane=self._data_plane,
        )
        require_text(candidate.get("schedule_version_id"), "schedule_version_id")
        require_integer(candidate.get("revision"), "revision", minimum=1)
        require_text(candidate.get("state"), "state")
        require_text(candidate.get("environment"), "environment")
        require_text(candidate.get("content_fingerprint"), "content_fingerprint")
        require_text(candidate.get("created_at_utc"), "created_at_utc")
        if not isinstance(candidate.get("synthetic"), bool):
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="synthetic",
                message="must be boolean",
            )
        require_mapping(candidate.get("content"), "content")
        return candidate, canonical

    def _assert_parent(
        self,
        connection: Connection,
        candidate: dict[str, object],
    ) -> str | None:
        parent_value = candidate.get("parent_schedule_version")
        if parent_value is None:
            return None
        parent = require_mapping(parent_value, "parent_schedule_version")
        parent_id = require_text(
            parent.get("schedule_version_id"),
            "parent_schedule_version.schedule_version_id",
        )
        parent_row = self._find(connection, parent_id)
        if parent_row is None:
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="parent_schedule_version.schedule_version_id",
                message="parent ScheduleVersion is absent from this plane",
            )
        stored_parent = self._load(parent_row)
        for field in ("state", "content_fingerprint"):
            if stored_parent.get(field) != parent.get(field):
                reject(
                    PersistenceFailure.IDENTITY_CONFLICT,
                    field=f"parent_schedule_version.{field}",
                    message="parent reference does not match stored ScheduleVersion",
                )
        return parent_id

    def _resolve_existing(
        self,
        row: RowMapping,
        candidate_bytes: bytes,
    ) -> DocumentWriteResult:
        creation = row["creation_json"]
        if (
            not isinstance(creation, (bytes, bytearray, memoryview))
            or bytes(creation) != candidate_bytes
        ):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="schedule_version_id",
                message="ScheduleVersion identity is bound to different creation bytes",
            )
        return DocumentWriteResult(document=self._load(row), replayed=True)

    def put_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
    ) -> DocumentWriteResult:
        candidate, canonical = self._candidate(document)
        schedule_version_id = require_text(
            candidate.get("schedule_version_id"), "schedule_version_id"
        )
        existing = self._find(connection, schedule_version_id)
        if existing is not None:
            return self._resolve_existing(existing, canonical)
        parent_id = self._assert_parent(connection, candidate)
        content = require_mapping(candidate.get("content"), "content")
        content_bytes = canonical_workspace_bytes(content)
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(SCHEDULE_VERSIONS).values(
                        data_plane=self._data_plane.value,
                        schedule_version_id=schedule_version_id,
                        revision=require_integer(
                            candidate.get("revision"), "revision", minimum=1
                        ),
                        state=require_text(candidate.get("state"), "state"),
                        environment=require_text(
                            candidate.get("environment"), "environment"
                        ),
                        synthetic=candidate["synthetic"],
                        parent_schedule_version_id=parent_id,
                        content_fingerprint=require_text(
                            candidate.get("content_fingerprint"),
                            "content_fingerprint",
                        ),
                        immutable_fingerprint=immutable_schedule_fingerprint(candidate),
                        content_json=content_bytes,
                        creation_json=canonical,
                        document_json=canonical,
                        document_sha256=document_sha256(canonical),
                        state_revision=0,
                        created_at_utc=require_text(
                            candidate.get("created_at_utc"), "created_at_utc"
                        ),
                    )
                )
        except IntegrityError:
            raced = self._find(connection, schedule_version_id)
            if raced is not None:
                return self._resolve_existing(raced, canonical)
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="repository.put",
                message="ScheduleVersion insert conflicted with stored identity",
            )
        return DocumentWriteResult(document=candidate, replayed=False)

    def put(self, document: Mapping[str, object]) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.put_in_transaction(connection, document)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.put",
                message="ScheduleVersion transaction failed",
            )

    def get(self, schedule_version_id: str) -> dict[str, object] | None:
        record = self.get_record(schedule_version_id)
        return record.document if record is not None else None

    def get_record(self, schedule_version_id: str) -> StoredScheduleVersion | None:
        require_text(schedule_version_id, "schedule_version_id")
        try:
            with self._engine.connect() as connection:
                row = self._find(connection, schedule_version_id)
                if row is None:
                    return None
                revision = row["state_revision"]
                if (
                    isinstance(revision, bool)
                    or not isinstance(revision, int)
                    or revision < 0
                ):
                    reject(
                        PersistenceFailure.PERSISTENCE_FAILED,
                        field="stored.state_revision",
                        message="stored ScheduleVersion state revision is invalid",
                    )
                return StoredScheduleVersion(
                    document=self._load(row),
                    state_revision=revision,
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get",
                message="ScheduleVersion query failed",
            )

    def transition_in_transaction(
        self,
        connection: Connection,
        *,
        schedule_version_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
    ) -> StateWriteResult:
        require_text(schedule_version_id, "schedule_version_id")
        require_text(expected_state, "expected_state")
        require_integer(expected_state_revision, "expected_state_revision")
        candidate, canonical = self._candidate(candidate_document)
        if candidate.get("schedule_version_id") != schedule_version_id:
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="schedule_version_id",
                message="CAS candidate identity differs from requested identity",
            )
        row = self._find(connection, schedule_version_id)
        if row is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="schedule_version_id",
                message="ScheduleVersion does not exist in this plane",
            )
        current = self._load(row)
        if row["state"] != expected_state or row["state_revision"] != (
            expected_state_revision
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_state/expected_state_revision",
                message="ScheduleVersion compare-and-set precondition failed",
            )
        try:
            source, target = require_schedule_version_transition(current, candidate)
        except ScheduleVersionPersistenceTransitionError:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="state/content",
                message="ScheduleVersion transition or immutable content is invalid",
            )
        result = connection.execute(
            update(SCHEDULE_VERSIONS)
            .where(
                SCHEDULE_VERSIONS.c.data_plane == self._data_plane.value,
                SCHEDULE_VERSIONS.c.schedule_version_id == schedule_version_id,
                SCHEDULE_VERSIONS.c.state == expected_state,
                SCHEDULE_VERSIONS.c.state_revision == expected_state_revision,
            )
            .values(
                state=target,
                document_json=canonical,
                document_sha256=document_sha256(canonical),
                state_revision=expected_state_revision + 1,
            )
        )
        if result.rowcount != 1:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_state/expected_state_revision",
                message="ScheduleVersion compare-and-set lost a concurrent race",
            )
        return StateWriteResult(
            document=candidate,
            previous_state=source,
            state_revision=expected_state_revision + 1,
        )

    def transition(
        self,
        *,
        schedule_version_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
    ) -> StateWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.transition_in_transaction(
                    connection,
                    schedule_version_id=schedule_version_id,
                    expected_state=expected_state,
                    expected_state_revision=expected_state_revision,
                    candidate_document=candidate_document,
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.transition",
                message="ScheduleVersion transaction failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="ScheduleVersion content updates are forbidden; use state CAS",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="ScheduleVersion deletion is forbidden",
        )


__all__ = ["SqlAlchemyScheduleVersionRepository", "StoredScheduleVersion"]
