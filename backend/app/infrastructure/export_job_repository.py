"""Plane-scoped ExportJob idempotency, state-CAS, and lease primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.domain.state_machines.export_job import (
    ExportJobLeaseError,
    ExportJobPersistenceTransitionError,
    require_export_job_heartbeat,
    require_export_job_transition,
)
from app.domain.workspace_contracts import workspace_fingerprint
from app.infrastructure.workspace_persistence import (
    EXPORT_JOBS,
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
    require_utc,
    stored_utc,
)


_MUTABLE_EXPORT_FIELDS = frozenset(
    {
        "state",
        "attempt",
        "lease_reference",
        "heartbeat_at_utc",
        "artifact_manifest",
        "error",
        "updated_at_utc",
        "started_at_utc",
        "finished_at_utc",
        "cancelled_at_utc",
        "latest_audit_event_id",
        "job_fingerprint",
    }
)


@dataclass(frozen=True)
class StoredExportJob:
    document: dict[str, object]
    state_revision: int
    lease_expires_at_utc: datetime | None


class SqlAlchemyExportJobRepository:
    """Persist ExportJob carriers without running an exporter or worker."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        if data_plane is not WorkspaceDataPlane.SIMULATION:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="export-job.v1 supports internal Simulation only",
            )
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> WorkspaceDataPlane:
        return self._data_plane

    @staticmethod
    def _identity_fingerprint(document: dict[str, object]) -> str:
        return workspace_fingerprint(
            {
                key: value
                for key, value in document.items()
                if key not in _MUTABLE_EXPORT_FIELDS
            }
        )

    def _find_by_id(
        self, connection: Connection, export_job_id: str
    ) -> RowMapping | None:
        row = connection.execute(
            select(EXPORT_JOBS).where(
                EXPORT_JOBS.c.data_plane == self._data_plane.value,
                EXPORT_JOBS.c.export_job_id == export_job_id,
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
            select(EXPORT_JOBS).where(
                EXPORT_JOBS.c.data_plane == self._data_plane.value,
                EXPORT_JOBS.c.idempotency_scope == scope,
                EXPORT_JOBS.c.idempotency_key_reference == key_reference,
            )
        ).first()
        return row._mapping if row is not None else None

    def _load(self, row: RowMapping) -> StoredExportJob:
        document = load_document(
            row["document_json"],
            row["document_sha256"],
            expected_version="export-job.v1",
            data_plane=self._data_plane,
        )
        schedule = require_mapping(document.get("schedule_version"), "schedule_version")
        idempotency = require_mapping(
            document.get("idempotency_reference"), "idempotency_reference"
        )
        expected = {
            "export_job_id": row["export_job_id"],
            "state": row["state"],
            "environment": row["environment"],
            "target": row["target"],
            "package_profile": row["package_profile"],
            "attempt": row["attempt"],
            "lease_reference": row["lease_reference"],
            "heartbeat_at_utc": row["heartbeat_at_utc"],
            "job_fingerprint": row["job_fingerprint"],
            "updated_at_utc": row["updated_at_utc"],
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.export_job",
                message="stored ExportJob metadata failed integrity verification",
            )
        if (
            schedule.get("schedule_version_id") != row["schedule_version_id"]
            or schedule.get("content_fingerprint")
            != row["schedule_content_fingerprint"]
            or idempotency.get("scope") != row["idempotency_scope"]
            or idempotency.get("key_reference") != row["idempotency_key_reference"]
            or idempotency.get("request_fingerprint") != row["request_fingerprint"]
        ):
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.export_job",
                message="stored ExportJob identity failed integrity verification",
            )
        revision = row["state_revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="stored.state_revision",
                message="stored ExportJob state revision is invalid",
            )
        lease_value = row["lease_expires_at_utc"]
        lease_expiry = (
            stored_utc(lease_value, "stored.lease_expires_at_utc")
            if lease_value is not None
            else None
        )
        return StoredExportJob(
            document=document,
            state_revision=revision,
            lease_expires_at_utc=lease_expiry,
        )

    def _candidate(
        self, document: Mapping[str, object]
    ) -> tuple[dict[str, object], bytes, Mapping[str, object]]:
        candidate, canonical = canonical_document(
            document,
            expected_version="export-job.v1",
            data_plane=self._data_plane,
        )
        for field in (
            "export_job_id",
            "state",
            "environment",
            "target",
            "package_profile",
            "updated_at_utc",
            "job_fingerprint",
        ):
            require_text(candidate.get(field), field)
        require_integer(candidate.get("attempt"), "attempt")
        schedule = require_mapping(
            candidate.get("schedule_version"), "schedule_version"
        )
        for field in ("schedule_version_id", "content_fingerprint"):
            require_text(schedule.get(field), f"schedule_version.{field}")
        idempotency = require_mapping(
            candidate.get("idempotency_reference"), "idempotency_reference"
        )
        for field in ("scope", "key_reference", "request_fingerprint"):
            require_text(idempotency.get(field), f"idempotency_reference.{field}")
        return candidate, canonical, idempotency

    def _resolve_existing(
        self, row: RowMapping, candidate_bytes: bytes
    ) -> DocumentWriteResult:
        creation = row["creation_json"]
        if (
            not isinstance(creation, (bytes, bytearray, memoryview))
            or bytes(creation) != candidate_bytes
        ):
            reject(
                PersistenceFailure.IDEMPOTENCY_CONFLICT,
                field="export_job_id/idempotency_reference",
                message="ExportJob identity or key is bound to different creation bytes",
            )
        return DocumentWriteResult(document=self._load(row).document, replayed=True)

    def create_in_transaction(
        self,
        connection: Connection,
        document: Mapping[str, object],
    ) -> DocumentWriteResult:
        candidate, canonical, idempotency = self._candidate(document)
        if candidate.get("state") != "CREATED" or candidate.get("attempt") != 0:
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="state/attempt",
                message="new ExportJob must be CREATED with attempt zero",
            )
        export_job_id = require_text(candidate.get("export_job_id"), "export_job_id")
        scope = require_text(idempotency.get("scope"), "idempotency_reference.scope")
        key_reference = require_text(
            idempotency.get("key_reference"),
            "idempotency_reference.key_reference",
        )
        existing = self._find_by_id(connection, export_job_id)
        if existing is None:
            existing = self._find_by_idempotency(
                connection,
                scope=scope,
                key_reference=key_reference,
            )
        if existing is not None:
            return self._resolve_existing(existing, canonical)
        schedule = require_mapping(
            candidate.get("schedule_version"), "schedule_version"
        )
        schedule_version_id = require_text(
            schedule.get("schedule_version_id"),
            "schedule_version.schedule_version_id",
        )
        schedule_fingerprint = require_text(
            schedule.get("content_fingerprint"),
            "schedule_version.content_fingerprint",
        )
        stored_schedule = connection.execute(
            select(
                SCHEDULE_VERSIONS.c.state,
                SCHEDULE_VERSIONS.c.content_fingerprint,
            ).where(
                SCHEDULE_VERSIONS.c.data_plane == self._data_plane.value,
                SCHEDULE_VERSIONS.c.schedule_version_id == schedule_version_id,
            )
        ).first()
        if (
            stored_schedule is None
            or stored_schedule.state != "PUBLISHED"
            or stored_schedule.content_fingerprint != schedule_fingerprint
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="schedule_version",
                message="ExportJob source does not match a stored PUBLISHED version",
            )
        try:
            with integrity_savepoint(connection):
                connection.execute(
                    insert(EXPORT_JOBS).values(
                        data_plane=self._data_plane.value,
                        export_job_id=export_job_id,
                        state="CREATED",
                        environment=require_text(
                            candidate.get("environment"), "environment"
                        ),
                        schedule_version_id=schedule_version_id,
                        schedule_content_fingerprint=schedule_fingerprint,
                        target=require_text(candidate.get("target"), "target"),
                        package_profile=require_text(
                            candidate.get("package_profile"), "package_profile"
                        ),
                        idempotency_scope=scope,
                        idempotency_key_reference=key_reference,
                        request_fingerprint=require_text(
                            idempotency.get("request_fingerprint"),
                            "idempotency_reference.request_fingerprint",
                        ),
                        attempt=0,
                        lease_reference=None,
                        lease_expires_at_utc=None,
                        heartbeat_at_utc=None,
                        job_fingerprint=require_text(
                            candidate.get("job_fingerprint"), "job_fingerprint"
                        ),
                        creation_json=canonical,
                        document_json=canonical,
                        document_sha256=document_sha256(canonical),
                        state_revision=0,
                        updated_at_utc=require_text(
                            candidate.get("updated_at_utc"), "updated_at_utc"
                        ),
                    )
                )
        except IntegrityError:
            raced = self._find_by_id(connection, export_job_id)
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
                field="repository.create",
                message="ExportJob insert conflicted with stored identity",
            )
        return DocumentWriteResult(document=candidate, replayed=False)

    def create(self, document: Mapping[str, object]) -> DocumentWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.create_in_transaction(connection, document)
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.create",
                message="ExportJob transaction failed",
            )

    def get(self, export_job_id: str) -> StoredExportJob | None:
        require_text(export_job_id, "export_job_id")
        try:
            with self._engine.connect() as connection:
                row = self._find_by_id(connection, export_job_id)
                return self._load(row) if row is not None else None
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.get",
                message="ExportJob query failed",
            )

    def _require_identity(
        self, current: dict[str, object], candidate: dict[str, object]
    ) -> None:
        if self._identity_fingerprint(current) != self._identity_fingerprint(candidate):
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="export_job",
                message="ExportJob immutable identity changed",
            )

    def transition_in_transaction(
        self,
        connection: Connection,
        *,
        export_job_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
        observed_at_utc: datetime,
        expected_lease_reference: str | None = None,
        lease_expires_at_utc: datetime | None = None,
    ) -> StateWriteResult:
        require_text(export_job_id, "export_job_id")
        require_text(expected_state, "expected_state")
        require_integer(expected_state_revision, "expected_state_revision")
        observed = require_utc(observed_at_utc, "observed_at_utc")
        lease_expiry = (
            require_utc(lease_expires_at_utc, "lease_expires_at_utc")
            if lease_expires_at_utc is not None
            else None
        )
        candidate, canonical, _ = self._candidate(candidate_document)
        if candidate.get("export_job_id") != export_job_id:
            reject(
                PersistenceFailure.IDENTITY_CONFLICT,
                field="export_job_id",
                message="CAS candidate identity differs from requested identity",
            )
        row = self._find_by_id(connection, export_job_id)
        if row is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="export_job_id",
                message="ExportJob does not exist in this plane",
            )
        stored = self._load(row)
        current = stored.document
        if row["state"] != expected_state or stored.state_revision != (
            expected_state_revision
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_state/expected_state_revision",
                message="ExportJob compare-and-set precondition failed",
            )
        self._require_identity(current, candidate)
        if expected_state == "EXPORTING":
            if (
                not expected_lease_reference
                or current.get("lease_reference") != expected_lease_reference
                or stored.lease_expires_at_utc is None
                or observed >= stored.lease_expires_at_utc
            ):
                reject(
                    PersistenceFailure.LEASE_CONFLICT,
                    field="expected_lease_reference",
                    message="active ExportJob lease precondition failed",
                )
        if candidate.get("state") == "EXPORTING":
            if lease_expiry is None or lease_expiry <= observed:
                reject(
                    PersistenceFailure.LEASE_CONFLICT,
                    field="lease_expires_at_utc",
                    message="new ExportJob lease expiry must be in the future",
                )
        try:
            source, target = require_export_job_transition(
                current,
                candidate,
                lease_expires_at_utc=lease_expiry,
            )
        except ExportJobLeaseError:
            reject(
                PersistenceFailure.LEASE_CONFLICT,
                field="lease_reference",
                message="ExportJob transition lease is invalid",
            )
        except ExportJobPersistenceTransitionError:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="state/attempt",
                message="ExportJob transition is invalid",
            )
        result = connection.execute(
            update(EXPORT_JOBS)
            .where(
                EXPORT_JOBS.c.data_plane == self._data_plane.value,
                EXPORT_JOBS.c.export_job_id == export_job_id,
                EXPORT_JOBS.c.state == expected_state,
                EXPORT_JOBS.c.state_revision == expected_state_revision,
            )
            .values(
                state=target,
                attempt=require_integer(candidate.get("attempt"), "attempt"),
                lease_reference=candidate.get("lease_reference"),
                lease_expires_at_utc=lease_expiry,
                heartbeat_at_utc=candidate.get("heartbeat_at_utc"),
                job_fingerprint=require_text(
                    candidate.get("job_fingerprint"), "job_fingerprint"
                ),
                document_json=canonical,
                document_sha256=document_sha256(canonical),
                state_revision=expected_state_revision + 1,
                updated_at_utc=require_text(
                    candidate.get("updated_at_utc"), "updated_at_utc"
                ),
            )
        )
        if result.rowcount != 1:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_state/expected_state_revision",
                message="ExportJob compare-and-set lost a concurrent race",
            )
        return StateWriteResult(
            document=candidate,
            previous_state=source,
            state_revision=expected_state_revision + 1,
        )

    def transition(
        self,
        *,
        export_job_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
        observed_at_utc: datetime,
        expected_lease_reference: str | None = None,
        lease_expires_at_utc: datetime | None = None,
    ) -> StateWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.transition_in_transaction(
                    connection,
                    export_job_id=export_job_id,
                    expected_state=expected_state,
                    expected_state_revision=expected_state_revision,
                    candidate_document=candidate_document,
                    observed_at_utc=observed_at_utc,
                    expected_lease_reference=expected_lease_reference,
                    lease_expires_at_utc=lease_expires_at_utc,
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.transition",
                message="ExportJob transaction failed",
            )

    def heartbeat_in_transaction(
        self,
        connection: Connection,
        *,
        export_job_id: str,
        expected_state_revision: int,
        expected_lease_reference: str,
        candidate_document: Mapping[str, object],
        observed_at_utc: datetime,
        lease_expires_at_utc: datetime,
    ) -> StateWriteResult:
        require_text(export_job_id, "export_job_id")
        require_integer(expected_state_revision, "expected_state_revision")
        require_text(expected_lease_reference, "expected_lease_reference")
        observed = require_utc(observed_at_utc, "observed_at_utc")
        new_expiry = require_utc(lease_expires_at_utc, "lease_expires_at_utc")
        candidate, canonical, _ = self._candidate(candidate_document)
        row = self._find_by_id(connection, export_job_id)
        if row is None:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="export_job_id",
                message="ExportJob does not exist in this plane",
            )
        stored = self._load(row)
        if stored.state_revision != expected_state_revision:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_state_revision",
                message="ExportJob heartbeat compare-and-set precondition failed",
            )
        current = stored.document
        self._require_identity(current, candidate)
        if stored.lease_expires_at_utc is None:
            reject(
                PersistenceFailure.LEASE_CONFLICT,
                field="lease_expires_at_utc",
                message="ExportJob has no active lease",
            )
        try:
            require_export_job_heartbeat(
                current,
                candidate,
                expected_lease_reference=expected_lease_reference,
                stored_lease_expires_at_utc=stored.lease_expires_at_utc,
                observed_at_utc=observed,
                new_lease_expires_at_utc=new_expiry,
            )
        except ExportJobLeaseError:
            reject(
                PersistenceFailure.LEASE_CONFLICT,
                field="lease_reference",
                message="ExportJob heartbeat lease precondition failed",
            )
        except ExportJobPersistenceTransitionError:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="attempt/state",
                message="ExportJob heartbeat state is invalid",
            )
        result = connection.execute(
            update(EXPORT_JOBS)
            .where(
                EXPORT_JOBS.c.data_plane == self._data_plane.value,
                EXPORT_JOBS.c.export_job_id == export_job_id,
                EXPORT_JOBS.c.state == "EXPORTING",
                EXPORT_JOBS.c.state_revision == expected_state_revision,
                EXPORT_JOBS.c.lease_reference == expected_lease_reference,
            )
            .values(
                lease_expires_at_utc=new_expiry,
                heartbeat_at_utc=candidate.get("heartbeat_at_utc"),
                job_fingerprint=require_text(
                    candidate.get("job_fingerprint"), "job_fingerprint"
                ),
                document_json=canonical,
                document_sha256=document_sha256(canonical),
                state_revision=expected_state_revision + 1,
                updated_at_utc=require_text(
                    candidate.get("updated_at_utc"), "updated_at_utc"
                ),
            )
        )
        if result.rowcount != 1:
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="expected_state_revision",
                message="ExportJob heartbeat lost a concurrent race",
            )
        return StateWriteResult(
            document=candidate,
            previous_state="EXPORTING",
            state_revision=expected_state_revision + 1,
        )

    def heartbeat(
        self,
        *,
        export_job_id: str,
        expected_state_revision: int,
        expected_lease_reference: str,
        candidate_document: Mapping[str, object],
        observed_at_utc: datetime,
        lease_expires_at_utc: datetime,
    ) -> StateWriteResult:
        try:
            with self._engine.begin() as connection:
                return self.heartbeat_in_transaction(
                    connection,
                    export_job_id=export_job_id,
                    expected_state_revision=expected_state_revision,
                    expected_lease_reference=expected_lease_reference,
                    candidate_document=candidate_document,
                    observed_at_utc=observed_at_utc,
                    lease_expires_at_utc=lease_expires_at_utc,
                )
        except WorkspacePersistenceError:
            raise
        except SQLAlchemyError:
            reject(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="repository.heartbeat",
                message="ExportJob heartbeat transaction failed",
            )

    def update(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.update",
            message="ExportJob identity updates are forbidden; use CAS primitives",
        )

    def delete(self, *_args: object, **_kwargs: object) -> NoReturn:
        reject(
            PersistenceFailure.APPEND_ONLY,
            field="repository.delete",
            message="ExportJob deletion is forbidden",
        )


__all__ = ["SqlAlchemyExportJobRepository", "StoredExportJob"]
