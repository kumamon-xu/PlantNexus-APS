"""Idempotent PublicationResult and current-reference storage primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.infrastructure.workspace_persistence import (
    PUBLICATION_CURRENT_REFERENCES,
    PUBLICATION_RESULTS,
    SCHEDULE_VERSIONS,
    CurrentPublicationReference,
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


@dataclass(frozen=True)
class PublicationPersistenceResult:
    document: dict[str, object]
    replayed: bool
    current_reference: CurrentPublicationReference | None
    current_changed: bool


class SqlAlchemyPublicationRepository:
    """Store internal Simulation result carriers without authorizing publish."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        if data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="publication-result.v1 supports internal Simulation only",
            )
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    def _find_by_id(
        self, connection: Connection, publication_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(PUBLICATION_RESULTS).where(
                PUBLICATION_RESULTS.c.data_plane == self._data_plane.value,
                PUBLICATION_RESULTS.c.publication_id == publication_id,
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
            select(PUBLICATION_RESULTS).where(
                PUBLICATION_RESULTS.c.data_plane == self._data_plane.value,
                PUBLICATION_RESULTS.c.idempotency_scope == scope,
                PUBLICATION_RESULTS.c.idempotency_key_reference == key_reference,
            )
        ).first()
        return row._mapping if row is not None else None

    def _current_row(self, connection: Connection, target: str) -> RowMapping | None:
        row = connection.execute(
            select(PUBLICATION_CURRENT_REFERENCES).where(
                PUBLICATION_CURRENT_REFERENCES.c.data_plane == self._data_plane.value,
                PUBLICATION_CURRENT_REFERENCES.c.target == target,
            )
        ).first()
        return row._mapping if row is not None else None

    def _reference(self, row: RowMapping) -> CurrentPublicationReference:
        try:
            stored_plane = WorkspaceDataPlane(row["data_plane"])
        except (TypeError, ValueError):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.data_plane",
                message="stored current publication reference is invalid",
            )
        values = {
            field: require_text(row[field], f"stored.{field}")
            for field in (
                "target",
                "schedule_version_id",
                "content_fingerprint",
                "publication_id",
                "updated_at_utc",
            )
        }
        revision = row["reference_revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.reference_revision",
                message="stored current publication reference is invalid",
            )
        return CurrentPublicationReference(
            data_plane=stored_plane,
            target=values["target"],
            schedule_version_id=values["schedule_version_id"],
            content_fingerprint=values["content_fingerprint"],
            publication_id=values["publication_id"],
            reference_revision=revision,
            updated_at_utc=values["updated_at_utc"],
        )

    def _load(self, row: RowMapping) -> dict[str, object]:
        document = load_document(
            row["document_json"],
            row["document_sha256"],
            expected_version="publication-result.v1",
            data_plane=self._data_plane,
        )
        expected = {
            "publication_id": row["publication_id"],
            "target": row["target"],
            "result_fingerprint": row["result_fingerprint"],
            "published_at_utc": row["published_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.publication_result",
                message="stored PublicationResult metadata failed integrity verification",
            )
        return document

    def _candidate(
        self, document: Mapping[str, object]
    ) -> tuple[dict[str, object], bytes, Mapping[str, object]]:
        candidate, canonical = canonical_document(
            document,
            expected_version="publication-result.v1",
            data_plane=self._data_plane,
        )
        for field in (
            "publication_id",
            "target",
            "published_at_utc",
            "result_fingerprint",
        ):
            require_text(candidate.get(field), field)
        idempotency = require_mapping(
            candidate.get("idempotency_reference"), "idempotency_reference"
        )
        for field in ("scope", "key_reference", "request_fingerprint"):
            require_text(idempotency.get(field), f"idempotency_reference.{field}")
        return candidate, canonical, idempotency

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
                field="publication_id/idempotency_reference",
                message="publication identity or key is bound to a different result",
            )
        return DocumentWriteResult(document=self._load(row), replayed=True)

    def persist_result_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
    ) -> DocumentWriteResult:
        candidate, canonical, idempotency = self._candidate(document)
        publication_id = require_text(candidate.get("publication_id"), "publication_id")
        scope = require_text(idempotency.get("scope"), "idempotency_reference.scope")
        key_reference = require_text(
            idempotency.get("key_reference"),
            "idempotency_reference.key_reference",
        )
        existing = self._find_by_id(connection, publication_id)
        if existing is None:
            existing = self._find_by_idempotency(
                connection,
                scope=scope,
                key_reference=key_reference,
            )
        if existing is not None:
            return self._resolve_existing(existing, canonical)
        source = require_mapping(
            candidate.get("source_approved_version"), "source_approved_version"
        )
        published = require_mapping(
            candidate.get("published_version"), "published_version"
        )
        previous_value = candidate.get("previous_current_version")
        previous = (
            None
            if previous_value is None
            else require_mapping(previous_value, "previous_current_version")
        )
        published_id, published_fingerprint = self._require_published_schedule(
            connection, published
        )
        source_id = require_text(
            source.get("schedule_version_id"),
            "source_approved_version.schedule_version_id",
        )
        if source_id != published_id or source.get("content_fingerprint") != (
            published_fingerprint
        ):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="source_approved_version",
                message="source and published references do not preserve identity/content",
            )
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(PUBLICATION_RESULTS).values(
                        data_plane=self._data_plane.value,
                        publication_id=publication_id,
                        target=require_text(candidate.get("target"), "target"),
                        source_schedule_version_id=source_id,
                        published_schedule_version_id=published_id,
                        previous_current_version_id=(
                            require_text(
                                previous.get("schedule_version_id"),
                                "previous_current_version.schedule_version_id",
                            )
                            if previous is not None
                            else None
                        ),
                        idempotency_scope=scope,
                        idempotency_key_reference=key_reference,
                        request_fingerprint=require_text(
                            idempotency.get("request_fingerprint"),
                            "idempotency_reference.request_fingerprint",
                        ),
                        result_fingerprint=require_text(
                            candidate.get("result_fingerprint"),
                            "result_fingerprint",
                        ),
                        published_at_utc=require_text(
                            candidate.get("published_at_utc"), "published_at_utc"
                        ),
                        document_json=canonical,
                        document_sha256=document_sha256(canonical),
                    )
                )
        except IntegrityError:
            raced = self._find_by_id(connection, publication_id)
            if raced is None:
                raced = self._find_by_idempotency(
                    connection,
                    scope=scope,
                    key_reference=key_reference,
                )
            if raced is not None:
                return self._resolve_existing(raced, canonical)
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="repository.persist_result",
                message="PublicationResult conflicted with stored identity",
            )
        return DocumentWriteResult(document=candidate, replayed=False)

    def persist_result(self, document: Mapping[str, object]) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.persist_result_in_transaction(connection, document)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.persist_result",
                message="PublicationResult transaction failed",
            )

    def _require_published_schedule(
        self,
        connection: Connection,
        published: Mapping[str, object],
    ) -> tuple[str, str]:
        schedule_id = require_text(
            published.get("schedule_version_id"),
            "published_version.schedule_version_id",
        )
        fingerprint = require_text(
            published.get("content_fingerprint"),
            "published_version.content_fingerprint",
        )
        row = connection.execute(
            select(
                SCHEDULE_VERSIONS.c.state,
                SCHEDULE_VERSIONS.c.content_fingerprint,
            ).where(
                SCHEDULE_VERSIONS.c.data_plane == self._data_plane.value,
                SCHEDULE_VERSIONS.c.schedule_version_id == schedule_id,
            )
        ).first()
        if (
            row is None
            or row.state != "PUBLISHED"
            or row.content_fingerprint != (fingerprint)
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="published_version",
                message="published reference does not match stored PUBLISHED version",
            )
        return schedule_id, fingerprint

    def persist_and_set_current_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
        *,
        expected_current: CurrentPublicationReference | None,
    ) -> PublicationPersistenceResult:
        stored_result = self.persist_result_in_transaction(connection, document)
        result_document = stored_result.document
        target = require_text(result_document.get("target"), "target")
        current_row = self._current_row(connection, target)
        current = self._reference(current_row) if current_row is not None else None
        published = require_mapping(
            result_document.get("published_version"), "published_version"
        )
        schedule_id, fingerprint = self._require_published_schedule(
            connection, published
        )
        publication_id = require_text(
            result_document.get("publication_id"), "publication_id"
        )

        if stored_result.replayed:
            return PublicationPersistenceResult(
                document=result_document,
                replayed=True,
                current_reference=current,
                current_changed=False,
            )

        previous_value = result_document.get("previous_current_version")
        if current is None:
            if expected_current is not None or previous_value is not None:
                reject(
                    PersistenceFailure.STATE_CONFLICT,
                    field="previous_current_version",
                    message="current publication CAS expected an empty target",
                )
            connection.execute(
                insert(PUBLICATION_CURRENT_REFERENCES).values(
                    data_plane=self._data_plane.value,
                    target=target,
                    schedule_version_id=schedule_id,
                    content_fingerprint=fingerprint,
                    publication_id=publication_id,
                    reference_revision=0,
                    updated_at_utc=require_text(
                        result_document.get("published_at_utc"), "published_at_utc"
                    ),
                )
            )
            new_row = self._current_row(connection, target)
            if new_row is None:
                reject(
                    PersistenceFailure.PERSISTENCE_FAILED,
                    field="current_reference",
                    message="current publication reference was not stored",
                )
            return PublicationPersistenceResult(
                document=result_document,
                replayed=False,
                current_reference=self._reference(new_row),
                current_changed=True,
            )

        if expected_current != current:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_current",
                message="current publication compare-and-set precondition failed",
            )
        previous = require_mapping(previous_value, "previous_current_version")
        if (
            previous.get("schedule_version_id") != current.schedule_version_id
            or previous.get("content_fingerprint") != current.content_fingerprint
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="previous_current_version",
                message="result does not describe the stored current reference",
            )
        update_result = connection.execute(
            update(PUBLICATION_CURRENT_REFERENCES)
            .where(
                PUBLICATION_CURRENT_REFERENCES.c.data_plane == self._data_plane.value,
                PUBLICATION_CURRENT_REFERENCES.c.target == target,
                PUBLICATION_CURRENT_REFERENCES.c.reference_revision
                == current.reference_revision,
            )
            .values(
                schedule_version_id=schedule_id,
                content_fingerprint=fingerprint,
                publication_id=publication_id,
                reference_revision=current.reference_revision + 1,
                updated_at_utc=require_text(
                    result_document.get("published_at_utc"), "published_at_utc"
                ),
            )
        )
        if update_result.rowcount != 1:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_current",
                message="current publication compare-and-set lost a concurrent race",
            )
        new_row = self._current_row(connection, target)
        if new_row is None:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="current_reference",
                message="current publication reference was not stored",
            )
        return PublicationPersistenceResult(
            document=result_document,
            replayed=False,
            current_reference=self._reference(new_row),
            current_changed=True,
        )

    def persist_and_set_current(
        self,
        document: Mapping[str, object],
        *,
        expected_current: CurrentPublicationReference | None,
    ) -> PublicationPersistenceResult:
        try:
            with self._engine.begin() as connection:
                return self.persist_and_set_current_in_transaction(
                    connection,
                    document,
                    expected_current=expected_current,
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.persist_and_set_current",
                message="publication persistence transaction failed",
            )

    def get_current(
        self, *, target: str = "SIMULATION_INTERNAL"
    ) -> CurrentPublicationReference | None:
        require_text(target, "target")
        try:
            with self._engine.connect() as connection:
                return self.get_current_in_transaction(connection, target=target)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get_current",
                message="current publication query failed",
            )

    def get_current_in_transaction(
        self,
        connection: Connection,
        *,
        target: str = "SIMULATION_INTERNAL",
    ) -> CurrentPublicationReference | None:
        """Re-read the current reference inside a caller-owned transaction."""

        require_text(target, "target")
        row = self._current_row(connection, target)
        return self._reference(row) if row is not None else None

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="PublicationResult updates are forbidden",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="PublicationResult deletion is forbidden",
        )


__all__ = ["PublicationPersistenceResult", "SqlAlchemyPublicationRepository"]
