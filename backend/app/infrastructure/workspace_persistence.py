"""Shared, fail-closed primitives for P3 workspace persistence adapters.

The module contains storage types and integrity checks only.  It deliberately
does not own authorization, business state gates, approval, publication, or
export execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import json
from typing import NoReturn, cast

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.engine import Connection

from app.domain.workspace_contracts import (
    WorkspaceContractError,
    canonical_workspace_bytes,
    require_workspace_document,
)


class WorkspaceDataPlane(StrEnum):
    """The two P3 carrier planes; repository instances never cross them."""

    SIMULATION = "SIMULATION"
    PRODUCTION = "PRODUCTION"


class PersistenceFailure(StrEnum):
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    LEASE_CONFLICT = "LEASE_CONFLICT"
    APPEND_ONLY = "APPEND_ONLY"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class WorkspacePersistenceError(RuntimeError):
    """Sanitized module-local error; SQL and credentials are never exposed."""

    def __init__(
        self,
        reason: PersistenceFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        super().__init__(f"{reason.value}: {field}: {message}")


@dataclass(frozen=True)
class DocumentWriteResult:
    document: dict[str, object]
    replayed: bool


@dataclass(frozen=True)
class StateWriteResult:
    document: dict[str, object]
    previous_state: str
    state_revision: int


@dataclass(frozen=True)
class CurrentPublicationReference:
    data_plane: WorkspaceDataPlane
    target: str
    schedule_version_id: str
    content_fingerprint: str
    publication_id: str
    reference_revision: int
    updated_at_utc: str


_METADATA = MetaData()

SCHEDULE_VERSIONS = Table(
    "schedule_versions",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("schedule_version_id", String(length=256), primary_key=True),
    Column("revision", Integer(), nullable=False),
    Column("state", String(length=32), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("synthetic", Boolean(), nullable=False),
    Column("parent_schedule_version_id", String(length=256)),
    Column("content_fingerprint", String(length=71), nullable=False),
    Column("immutable_fingerprint", String(length=71), nullable=False),
    Column("content_json", LargeBinary(), nullable=False),
    Column("creation_json", LargeBinary(), nullable=False),
    Column("document_json", LargeBinary(), nullable=False),
    Column("document_sha256", String(length=64), nullable=False),
    Column("state_revision", Integer(), nullable=False),
    Column("created_at_utc", String(length=32), nullable=False),
)

AUDIT_EVENTS = Table(
    "audit_events",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("audit_event_id", String(length=256), primary_key=True),
    Column("environment", String(length=32), nullable=False),
    Column("action", String(length=64), nullable=False),
    Column("aggregate_type", String(length=32), nullable=False),
    Column("aggregate_id", String(length=256), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("parent_audit_event_id", String(length=256)),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("idempotency_scope", String(length=512)),
    Column("idempotency_key_reference", String(length=71)),
    Column("request_fingerprint", String(length=71)),
    Column("document_json", LargeBinary(), nullable=False),
    Column("document_sha256", String(length=64), nullable=False),
    UniqueConstraint(
        "data_plane",
        "idempotency_scope",
        "idempotency_key_reference",
        name="uq_audit_events_plane_idempotency",
    ),
)

PUBLICATION_RESULTS = Table(
    "publication_results",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("publication_id", String(length=256), primary_key=True),
    Column("target", String(length=64), nullable=False),
    Column("source_schedule_version_id", String(length=256), nullable=False),
    Column("published_schedule_version_id", String(length=256), nullable=False),
    Column("previous_current_version_id", String(length=256)),
    Column("idempotency_scope", String(length=512), nullable=False),
    Column("idempotency_key_reference", String(length=71), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("result_fingerprint", String(length=71), nullable=False),
    Column("published_at_utc", String(length=32), nullable=False),
    Column("document_json", LargeBinary(), nullable=False),
    Column("document_sha256", String(length=64), nullable=False),
    UniqueConstraint(
        "data_plane",
        "idempotency_scope",
        "idempotency_key_reference",
        name="uq_publication_results_plane_idempotency",
    ),
)

PUBLICATION_CURRENT_REFERENCES = Table(
    "publication_current_references",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("target", String(length=64), primary_key=True),
    Column("schedule_version_id", String(length=256), nullable=False),
    Column("content_fingerprint", String(length=71), nullable=False),
    Column("publication_id", String(length=256), nullable=False),
    Column("reference_revision", Integer(), nullable=False),
    Column("updated_at_utc", String(length=32), nullable=False),
    ForeignKeyConstraint(
        ["data_plane", "schedule_version_id"],
        ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
    ),
)

EXPORT_JOBS = Table(
    "export_jobs",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("export_job_id", String(length=256), primary_key=True),
    Column("state", String(length=32), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("schedule_version_id", String(length=256), nullable=False),
    Column("schedule_content_fingerprint", String(length=71), nullable=False),
    Column("target", String(length=64), nullable=False),
    Column("package_profile", String(length=64), nullable=False),
    Column("idempotency_scope", String(length=512), nullable=False),
    Column("idempotency_key_reference", String(length=71), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("attempt", Integer(), nullable=False),
    Column("lease_reference", String(length=71)),
    Column("lease_expires_at_utc", DateTime(timezone=True)),
    Column("heartbeat_at_utc", String(length=32)),
    Column("job_fingerprint", String(length=71), nullable=False),
    Column("creation_json", LargeBinary(), nullable=False),
    Column("document_json", LargeBinary(), nullable=False),
    Column("document_sha256", String(length=64), nullable=False),
    Column("state_revision", Integer(), nullable=False),
    Column("updated_at_utc", String(length=32), nullable=False),
)

_REQUIRED_TOP_LEVEL_FIELDS: Mapping[str, frozenset[str]] = {
    "schedule-version.v1": frozenset(
        {
            "schedule_version_version",
            "schema_set_version",
            "canonicalization_version",
            "schedule_version_id",
            "revision",
            "state",
            "data_plane",
            "environment",
            "synthetic",
            "parent_schedule_version",
            "source_kind",
            "lineage",
            "content",
            "content_fingerprint",
            "validation",
            "decision",
            "publication",
            "superseded_by",
            "allowed_actions",
            "created_at_utc",
            "created_by_actor_ref",
        }
    ),
    "audit-event.v1": frozenset(
        {
            "audit_event_version",
            "schema_set_version",
            "canonicalization_version",
            "audit_event_id",
            "occurred_at_utc",
            "actor_ref",
            "resolved_capability",
            "auth_policy_version",
            "environment",
            "data_plane",
            "synthetic",
            "action",
            "aggregate_type",
            "aggregate_id",
            "target",
            "intent_type",
            "reason",
            "request_fingerprint",
            "idempotency_reference",
            "lineage",
            "before_state",
            "after_state",
            "source_version",
            "new_version",
            "export_job_id",
            "result",
            "correlation_id",
            "parent_audit_event_id",
            "code_commit",
        }
    ),
    "publication-result.v1": frozenset(
        {
            "publication_result_version",
            "schema_set_version",
            "canonicalization_version",
            "publication_id",
            "data_plane",
            "environment",
            "synthetic",
            "synthetic_provenance",
            "target",
            "source_approved_version",
            "published_version",
            "previous_current_version",
            "superseded_version",
            "idempotency_reference",
            "replayed",
            "published_at_utc",
            "audit_event_id",
            "result_fingerprint",
        }
    ),
    "export-job.v1": frozenset(
        {
            "export_job_version",
            "schema_set_version",
            "canonicalization_version",
            "export_job_id",
            "state",
            "schedule_version",
            "data_plane",
            "environment",
            "synthetic",
            "synthetic_provenance",
            "target",
            "package_profile",
            "idempotency_reference",
            "attempt",
            "lease_reference",
            "heartbeat_at_utc",
            "artifact_manifest",
            "error",
            "created_at_utc",
            "updated_at_utc",
            "started_at_utc",
            "finished_at_utc",
            "cancelled_at_utc",
            "latest_audit_event_id",
            "job_fingerprint",
        }
    ),
    "export-job.v2": frozenset(
        {
            "export_job_version",
            "schema_set_version",
            "canonicalization_version",
            "export_job_id",
            "state",
            "schedule_version",
            "data_plane",
            "environment",
            "synthetic",
            "synthetic_provenance",
            "target",
            "package_profile",
            "idempotency_reference",
            "attempt",
            "lease_reference",
            "heartbeat_at_utc",
            "artifact_manifest",
            "error",
            "created_at_utc",
            "updated_at_utc",
            "started_at_utc",
            "finished_at_utc",
            "cancelled_at_utc",
            "latest_audit_event_id",
            "job_fingerprint",
        }
    ),
}


def _require_top_level_shape(
    document: Mapping[str, object], expected_version: str
) -> None:
    required = _REQUIRED_TOP_LEVEL_FIELDS[expected_version]
    optional = (
        frozenset({"synthetic_provenance"})
        if expected_version in {"schedule-version.v1", "audit-event.v1"}
        else frozenset()
    )
    missing = sorted(required.difference(document))
    if missing:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=missing[0],
            message="required carrier field is missing",
        )
    unknown = sorted(set(document).difference(required | optional))
    if unknown:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=unknown[0],
            message="unknown carrier field is forbidden",
        )
    synthetic = document.get("synthetic")
    has_provenance = "synthetic_provenance" in document
    if synthetic is True and not has_provenance:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="synthetic_provenance",
            message="synthetic carrier requires explicit provenance",
        )
    if synthetic is False and has_provenance:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="synthetic_provenance",
            message="non-synthetic carrier cannot include synthetic provenance",
        )
    if document.get("data_plane") == WorkspaceDataPlane.PRODUCTION.value:
        if document.get("environment") != "PRODUCTION" or synthetic is not False:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="environment/synthetic",
                message="Production carrier environment/provenance is invalid",
            )
        if expected_version == "schedule-version.v1" and (
            document.get("state")
            not in {"DRAFT", "READY_FOR_REVIEW", "APPROVED", "REJECTED"}
            or document.get("publication") is not None
            or document.get("superseded_by") is not None
        ):
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="state/publication/superseded_by",
                message="Production ScheduleVersion cannot carry publication state",
            )
        if (
            expected_version == "audit-event.v1"
            and document.get("target") != "WORKSPACE_INTERNAL"
        ):
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="target",
                message="Production AuditEvent target is invalid",
            )
    elif document.get("environment") not in {"DEVELOPMENT", "TEST", "BENCHMARK"}:
        reject(
            PersistenceFailure.DATA_PLANE_MISMATCH,
            field="environment",
            message="Simulation carrier environment is invalid",
        )
    if expected_version in {
        "publication-result.v1",
        "export-job.v1",
        "export-job.v2",
    } and (
        document.get("target") != "SIMULATION_INTERNAL" or synthetic is not True
    ):
        reject(
            PersistenceFailure.DATA_PLANE_MISMATCH,
            field="target/synthetic",
            message="internal Simulation carrier boundary is invalid",
        )


def reject(
    reason: PersistenceFailure,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise WorkspacePersistenceError(reason, field=field, message=message)


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be non-empty text",
        )
    return value


def require_integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message=f"must be an integer >= {minimum}",
        )
    return value


def require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def canonical_document(
    document: Mapping[str, object],
    *,
    expected_version: str,
    data_plane: WorkspaceDataPlane,
) -> tuple[dict[str, object], bytes]:
    """Return a detached canonical document after pure carrier prechecks."""

    try:
        version = require_workspace_document(document)
        if version != expected_version:
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="$",
                message=f"expected {expected_version}",
            )
        _require_top_level_shape(document, expected_version)
        if document.get("data_plane") != data_plane.value:
            reject(
                PersistenceFailure.DATA_PLANE_MISMATCH,
                field="data_plane",
                message="document does not belong to this repository plane",
            )
        canonical = canonical_workspace_bytes(document)
        detached = json.loads(canonical.decode("utf-8"))
        if not isinstance(detached, dict):
            reject(
                PersistenceFailure.INVALID_DOCUMENT,
                field="$",
                message="document must be an object",
            )
        return cast(dict[str, object], detached), canonical
    except WorkspacePersistenceError:
        raise
    except (WorkspaceContractError, KeyError, TypeError, ValueError) as error:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=getattr(error, "field", "$"),
            message="workspace carrier failed integrity precheck",
        )


def load_document(
    value: object,
    digest: object,
    *,
    expected_version: str | tuple[str, ...],
    data_plane: WorkspaceDataPlane,
) -> dict[str, object]:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored document failed integrity verification",
        )
    document_bytes = bytes(value)
    if not isinstance(digest, str) or sha256(document_bytes).hexdigest() != digest:
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_sha256",
            message="stored document failed integrity verification",
        )
    try:
        parsed = json.loads(document_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored document failed integrity verification",
        )
    if not isinstance(parsed, dict):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored document failed integrity verification",
        )
    try:
        allowed_versions = (
            (expected_version,) if isinstance(expected_version, str) else expected_version
        )
        actual_version = require_workspace_document(cast(dict[str, object], parsed))
        if actual_version not in allowed_versions:
            raise WorkspaceContractError("$", "stored document version is not allowed")
        loaded, _ = canonical_document(
            cast(dict[str, object], parsed),
            expected_version=actual_version,
            data_plane=data_plane,
        )
    except WorkspacePersistenceError:
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored document failed integrity verification",
        )
    return loaded


def document_sha256(document_bytes: bytes) -> str:
    return sha256(document_bytes).hexdigest()


@contextmanager
def integrity_savepoint(connection: Connection) -> Iterator[None]:
    """Keep PostgreSQL usable after a race without breaking SQLite rollback."""

    if connection.dialect.name == "postgresql":
        with connection.begin_nested():
            yield
    else:
        yield


def require_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be timezone-aware UTC",
        )
    return value.astimezone(UTC)


def stored_utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field=field,
            message="stored UTC timestamp is invalid",
        )
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    if value.utcoffset() != timedelta(0):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field=field,
            message="stored UTC timestamp is invalid",
        )
    return value


__all__ = [
    "AUDIT_EVENTS",
    "EXPORT_JOBS",
    "PUBLICATION_CURRENT_REFERENCES",
    "PUBLICATION_RESULTS",
    "SCHEDULE_VERSIONS",
    "CurrentPublicationReference",
    "DocumentWriteResult",
    "PersistenceFailure",
    "StateWriteResult",
    "WorkspaceDataPlane",
    "WorkspacePersistenceError",
    "canonical_document",
    "document_sha256",
    "integrity_savepoint",
    "load_document",
    "reject",
    "require_integer",
    "require_mapping",
    "require_text",
    "require_utc",
    "stored_utc",
]
