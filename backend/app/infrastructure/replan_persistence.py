"""Shared fail-closed primitives for bounded P4 replan persistence.

This module defines relational projections and internal storage records only.
It does not interpret ExecutionEvent payloads, project facts, run a solver, or
create a ScheduleVersion or ChangeReport.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from typing import ClassVar, NoReturn, cast

from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

from app.domain.execution_contracts import (
    P4ContractError,
    canonical_contract_bytes,
    contract_fingerprint,
    require_p4_document,
)
from app.infrastructure.workspace_persistence import (
    PersistenceFailure,
    WorkspaceDataPlane,
    reject,
    require_integer,
    require_text,
)


_METADATA = MetaData()

EXECUTION_EVENT_LEDGER = Table(
    "execution_event_ledger",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("event_id", String(length=256), primary_key=True),
    Column("event_fingerprint", String(length=71), nullable=False),
    Column("event_type", String(length=64), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("factory_id", String(length=256), nullable=False),
    Column("planning_scope_id", String(length=256), nullable=False),
    Column("authority_id", String(length=256), nullable=False),
    Column("authority_scope", String(length=768), nullable=False),
    Column("stream_id", String(length=256), nullable=False),
    Column("stream_version", String(length=64), nullable=False),
    Column("source_position", Integer(), nullable=False),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("received_at_utc", String(length=32), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("document_json", LargeBinary(), nullable=False),
    Column("document_sha256", String(length=64), nullable=False),
    UniqueConstraint(
        "data_plane",
        "authority_id",
        "stream_id",
        "stream_version",
        "source_position",
        name="uq_execution_event_ledger_stream_position",
    ),
)

REPLAN_PROJECTION_CHECKPOINTS = Table(
    "replan_projection_checkpoints",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("factory_id", String(length=256), primary_key=True),
    Column("planning_scope_id", String(length=256), primary_key=True),
    Column("authority_id", String(length=256), primary_key=True),
    Column("stream_id", String(length=256), primary_key=True),
    Column("stream_version", String(length=64), primary_key=True),
    Column("last_applied_position", Integer(), nullable=False),
    Column("prefix_fingerprint", String(length=71), nullable=False),
    Column("fact_checkpoint_version", String(length=128), nullable=False),
    Column("fact_checkpoint_id", String(length=256), nullable=False),
    Column("fact_checkpoint_fingerprint", String(length=71), nullable=False),
    Column("checkpoint_json", LargeBinary(), nullable=False),
    Column("checkpoint_sha256", String(length=64), nullable=False),
    Column("state_revision", Integer(), nullable=False),
    Column("updated_at_utc", String(length=32), nullable=False),
)

REPLAN_REQUESTS = Table(
    "replan_requests",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("request_id", String(length=256), primary_key=True),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("environment", String(length=32), nullable=False),
    Column("factory_id", String(length=256), nullable=False),
    Column("planning_scope_id", String(length=256), nullable=False),
    Column("authority_id", String(length=256), nullable=False),
    Column("stream_id", String(length=256), nullable=False),
    Column("stream_version", String(length=64), nullable=False),
    Column("from_position", Integer(), nullable=False),
    Column("through_position", Integer(), nullable=False),
    Column("stream_fingerprint", String(length=71), nullable=False),
    Column("fact_checkpoint_version", String(length=128), nullable=False),
    Column("fact_checkpoint_id", String(length=256), nullable=False),
    Column("fact_checkpoint_fingerprint", String(length=71), nullable=False),
    Column("base_schedule_version_id", String(length=256), nullable=False),
    Column("requested_at_utc", String(length=32), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("document_json", LargeBinary(), nullable=False),
    Column("document_sha256", String(length=64), nullable=False),
    UniqueConstraint(
        "data_plane",
        "request_fingerprint",
        name="uq_replan_requests_fingerprint",
    ),
)

REPLAN_REQUEST_EVENTS = Table(
    "replan_request_events",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("request_id", String(length=256), primary_key=True),
    Column("event_ordinal", Integer(), primary_key=True),
    Column("event_id", String(length=256), nullable=False),
    Column("event_fingerprint", String(length=71), nullable=False),
    Column("source_position", Integer(), nullable=False),
    UniqueConstraint(
        "data_plane",
        "request_id",
        "event_id",
        name="uq_replan_request_events_event",
    ),
    ForeignKeyConstraint(
        ["data_plane", "request_id"],
        ["replan_requests.data_plane", "replan_requests.request_id"],
        name="fk_replan_request_events_request",
    ),
    ForeignKeyConstraint(
        ["data_plane", "event_id"],
        ["execution_event_ledger.data_plane", "execution_event_ledger.event_id"],
        name="fk_replan_request_events_event",
    ),
)

REPLAN_ATTEMPTS = Table(
    "replan_attempts",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("attempt_id", String(length=256), primary_key=True),
    Column("attempt_fingerprint", String(length=71), nullable=False),
    Column("request_id", String(length=256), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("attempt_number", Integer(), nullable=False),
    Column("idempotency_scope", String(length=512), nullable=False),
    Column("idempotency_key_reference", String(length=71), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("created_at_utc", String(length=32), nullable=False),
    Column("record_json", LargeBinary(), nullable=False),
    Column("record_sha256", String(length=64), nullable=False),
    UniqueConstraint(
        "data_plane",
        "request_id",
        "attempt_number",
        name="uq_replan_attempts_request_number",
    ),
    UniqueConstraint(
        "data_plane", "planning_run_id", name="uq_replan_attempts_planning_run"
    ),
    UniqueConstraint(
        "data_plane",
        "idempotency_scope",
        "idempotency_key_reference",
        name="uq_replan_attempts_idempotency",
    ),
    ForeignKeyConstraint(
        ["data_plane", "request_id"],
        ["replan_requests.data_plane", "replan_requests.request_id"],
        name="fk_replan_attempts_request",
    ),
)

REPLAN_RESULTS = Table(
    "replan_results",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("result_id", String(length=256), primary_key=True),
    Column("result_fingerprint", String(length=71), nullable=False),
    Column("attempt_id", String(length=256), nullable=False),
    Column("request_id", String(length=256), nullable=False),
    Column("request_fingerprint", String(length=71), nullable=False),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("planning_run_terminal_state", String(length=32), nullable=False),
    Column("solver_report_id", String(length=256)),
    Column("solver_report_fingerprint", String(length=71)),
    Column("validation_report_id", String(length=256)),
    Column("validation_report_fingerprint", String(length=71)),
    Column("new_schedule_version_id", String(length=256)),
    Column("new_schedule_content_fingerprint", String(length=71)),
    Column("change_report_id", String(length=256)),
    Column("change_report_fingerprint", String(length=71)),
    Column("correlation_id", String(length=256), nullable=False),
    Column("finished_at_utc", String(length=32), nullable=False),
    Column("record_json", LargeBinary(), nullable=False),
    Column("record_sha256", String(length=64), nullable=False),
    UniqueConstraint("data_plane", "attempt_id", name="uq_replan_results_attempt"),
    ForeignKeyConstraint(
        ["data_plane", "attempt_id"],
        ["replan_attempts.data_plane", "replan_attempts.attempt_id"],
        name="fk_replan_results_attempt",
    ),
    ForeignKeyConstraint(
        ["data_plane", "request_id"],
        ["replan_requests.data_plane", "replan_requests.request_id"],
        name="fk_replan_results_request",
    ),
)

REPLAN_AUDIT_RECORDS = Table(
    "replan_audit_records",
    _METADATA,
    Column("data_plane", String(length=16), primary_key=True),
    Column("audit_record_id", String(length=256), primary_key=True),
    Column("audit_fingerprint", String(length=71), nullable=False),
    Column("action", String(length=64), nullable=False),
    Column("aggregate_type", String(length=64), nullable=False),
    Column("aggregate_id", String(length=256), nullable=False),
    Column("correlation_id", String(length=256), nullable=False),
    Column("idempotency_scope", String(length=512), nullable=False),
    Column("idempotency_key_reference", String(length=71), nullable=False),
    Column("request_fingerprint", String(length=71)),
    Column("occurred_at_utc", String(length=32), nullable=False),
    Column("record_json", LargeBinary(), nullable=False),
    Column("record_sha256", String(length=64), nullable=False),
    UniqueConstraint(
        "data_plane",
        "idempotency_scope",
        "idempotency_key_reference",
        name="uq_replan_audit_records_idempotency",
    ),
)


@dataclass(frozen=True)
class ArtifactReference:
    document_version: str
    artifact_id: str
    fingerprint: str

    def as_document(self) -> dict[str, object]:
        return {
            "document_version": self.document_version,
            "artifact_id": self.artifact_id,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class ProjectionCheckpoint:
    record_version: ClassVar[str] = "replan-projection-checkpoint.v1"

    factory_id: str
    planning_scope_id: str
    authority_id: str
    stream_id: str
    stream_version: str
    last_applied_position: int
    prefix_fingerprint: str
    fact_checkpoint: ArtifactReference
    updated_at_utc: str

    def as_document(self) -> dict[str, object]:
        return {
            "record_version": self.record_version,
            "factory_id": self.factory_id,
            "planning_scope_id": self.planning_scope_id,
            "authority_id": self.authority_id,
            "stream_id": self.stream_id,
            "stream_version": self.stream_version,
            "last_applied_position": self.last_applied_position,
            "prefix_fingerprint": self.prefix_fingerprint,
            "fact_checkpoint": self.fact_checkpoint.as_document(),
            "updated_at_utc": self.updated_at_utc,
        }


@dataclass(frozen=True)
class ReplanAttemptReference:
    record_version: ClassVar[str] = "replan-attempt-reference.v1"

    attempt_id: str
    attempt_fingerprint: str
    request_id: str
    request_fingerprint: str
    planning_run_id: str
    attempt_number: int
    idempotency_scope: str
    idempotency_key_reference: str
    correlation_id: str
    created_at_utc: str

    def as_document(self) -> dict[str, object]:
        return {
            "record_version": self.record_version,
            "attempt_id": self.attempt_id,
            "attempt_fingerprint": self.attempt_fingerprint,
            "request_id": self.request_id,
            "request_fingerprint": self.request_fingerprint,
            "planning_run_id": self.planning_run_id,
            "attempt_number": self.attempt_number,
            "idempotency_scope": self.idempotency_scope,
            "idempotency_key_reference": self.idempotency_key_reference,
            "correlation_id": self.correlation_id,
            "created_at_utc": self.created_at_utc,
        }


@dataclass(frozen=True)
class ReplanResultReference:
    record_version: ClassVar[str] = "replan-result-reference.v1"

    result_id: str
    result_fingerprint: str
    attempt_id: str
    request_id: str
    request_fingerprint: str
    planning_run_id: str
    planning_run_terminal_state: str
    solver_report: ArtifactReference | None
    validation_report: ArtifactReference | None
    new_schedule_version: ArtifactReference | None
    change_report: ArtifactReference | None
    correlation_id: str
    finished_at_utc: str

    def as_document(self) -> dict[str, object]:
        return {
            "record_version": self.record_version,
            "result_id": self.result_id,
            "result_fingerprint": self.result_fingerprint,
            "attempt_id": self.attempt_id,
            "request_id": self.request_id,
            "request_fingerprint": self.request_fingerprint,
            "planning_run_id": self.planning_run_id,
            "planning_run_terminal_state": self.planning_run_terminal_state,
            "solver_report": _artifact_document(self.solver_report),
            "validation_report": _artifact_document(self.validation_report),
            "new_schedule_version": _artifact_document(self.new_schedule_version),
            "change_report": _artifact_document(self.change_report),
            "correlation_id": self.correlation_id,
            "finished_at_utc": self.finished_at_utc,
        }


class ReplanAuditAction(StrEnum):
    EXECUTION_EVENT_APPENDED = "EXECUTION_EVENT_APPENDED"
    PROJECTION_CHECKPOINT_COMMITTED = "PROJECTION_CHECKPOINT_COMMITTED"
    REPLAN_REQUEST_APPENDED = "REPLAN_REQUEST_APPENDED"
    REPLAN_ATTEMPT_LINKED = "REPLAN_ATTEMPT_LINKED"
    REPLAN_RESULT_APPENDED = "REPLAN_RESULT_APPENDED"


@dataclass(frozen=True)
class ReplanAuditRecord:
    record_version: ClassVar[str] = "replan-persistence-audit.v1"

    audit_record_id: str
    audit_fingerprint: str
    action: ReplanAuditAction
    aggregate_type: str
    aggregate_id: str
    correlation_id: str
    idempotency_scope: str
    idempotency_key_reference: str
    request_fingerprint: str | None
    occurred_at_utc: str

    def as_document(self) -> dict[str, object]:
        return {
            "record_version": self.record_version,
            "audit_record_id": self.audit_record_id,
            "audit_fingerprint": self.audit_fingerprint,
            "action": self.action.value,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "correlation_id": self.correlation_id,
            "idempotency_scope": self.idempotency_scope,
            "idempotency_key_reference": self.idempotency_key_reference,
            "request_fingerprint": self.request_fingerprint,
            "occurred_at_utc": self.occurred_at_utc,
        }


TERMINAL_PLANNING_RUN_STATES = frozenset(
    {
        "COMPLETED",
        "DATA_REJECTED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "CANCELLED",
        "FAILED",
    }
)


def _artifact_document(reference: ArtifactReference | None) -> dict[str, object] | None:
    return reference.as_document() if reference is not None else None


def _without(
    document: Mapping[str, object], *excluded: str
) -> dict[str, object]:
    return {key: value for key, value in document.items() if key not in excluded}


def _derived_identity(prefix: str, fingerprint: str) -> str:
    return f"{prefix}{fingerprint.removeprefix('sha256:')}"


def _require_sha256(value: object, field: str) -> str:
    fingerprint = require_text(value, field)
    digest = fingerprint.removeprefix("sha256:")
    if (
        not fingerprint.startswith("sha256:")
        or len(digest) != 64
        or digest.lower() != digest
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be a lowercase sha256 fingerprint",
        )
    return fingerprint


def _require_utc_text(value: object, field: str) -> str:
    timestamp = require_text(value, field)
    if not timestamp.endswith("Z"):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be canonical UTC with a trailing Z",
        )
    try:
        parsed = datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
    except ValueError:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be a valid UTC timestamp",
        )
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=field,
            message="must be UTC",
        )
    return timestamp


def _validate_artifact(
    reference: ArtifactReference | None,
    field: str,
    *,
    expected_version: str | None = None,
) -> None:
    if reference is None:
        return
    require_text(reference.document_version, f"{field}.document_version")
    require_text(reference.artifact_id, f"{field}.artifact_id")
    _require_sha256(reference.fingerprint, f"{field}.fingerprint")
    if expected_version is not None and reference.document_version != expected_version:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field=f"{field}.document_version",
            message="does not match the approved reference version",
        )


def canonical_p4_document(
    document: Mapping[str, object],
    *,
    expected_version: str,
    data_plane: WorkspaceDataPlane,
) -> tuple[dict[str, object], bytes]:
    candidate = dict(document)
    try:
        observed_version = require_p4_document(candidate)
        canonical = canonical_contract_bytes(candidate)
    except P4ContractError:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="document",
            message="P4 carrier failed semantic integrity precheck",
        )
    if observed_version != expected_version:
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="document_version",
            message="P4 carrier version is not accepted by this repository",
        )
    if candidate.get("data_plane") != data_plane.value:
        reject(
            PersistenceFailure.DATA_PLANE_MISMATCH,
            field="data_plane",
            message="document does not belong to this repository plane",
        )
    if data_plane is not WorkspaceDataPlane.SIMULATION:
        reject(
            PersistenceFailure.DATA_PLANE_MISMATCH,
            field="data_plane",
            message="P4 Production persistence is not established",
        )
    return candidate, canonical


def load_p4_document(
    value: object,
    digest: object,
    *,
    expected_version: str,
    data_plane: WorkspaceDataPlane,
) -> dict[str, object]:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored carrier bytes are invalid",
        )
    raw = bytes(value)
    if not isinstance(digest, str) or sha256(raw).hexdigest() != digest:
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_sha256",
            message="stored carrier digest mismatch",
        )
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored carrier is not canonical JSON",
        )
    if not isinstance(document, dict):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored carrier root is invalid",
        )
    candidate, canonical = canonical_p4_document(
        cast(Mapping[str, object], document),
        expected_version=expected_version,
        data_plane=data_plane,
    )
    if canonical != raw:
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.document_json",
            message="stored carrier bytes are not canonical",
        )
    return candidate


def internal_record_bytes(document: Mapping[str, object]) -> bytes:
    return canonical_contract_bytes(document)


def internal_record_sha256(record_bytes: bytes) -> str:
    return sha256(record_bytes).hexdigest()


def load_internal_record(
    value: object,
    digest: object,
    *,
    expected_version: str,
) -> dict[str, object]:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.record_json",
            message="stored record bytes are invalid",
        )
    raw = bytes(value)
    if not isinstance(digest, str) or internal_record_sha256(raw) != digest:
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.record_sha256",
            message="stored record digest mismatch",
        )
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.record_json",
            message="stored record is not canonical JSON",
        )
    if not isinstance(document, dict) or document.get("record_version") != (
        expected_version
    ):
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.record_version",
            message="stored record version mismatch",
        )
    if internal_record_bytes(cast(Mapping[str, object], document)) != raw:
        reject(
            PersistenceFailure.PERSISTENCE_FAILED,
            field="stored.record_json",
            message="stored record bytes are not canonical",
        )
    return cast(dict[str, object], document)


def validate_projection_checkpoint(checkpoint: ProjectionCheckpoint) -> bytes:
    for field, value in (
        ("factory_id", checkpoint.factory_id),
        ("planning_scope_id", checkpoint.planning_scope_id),
        ("authority_id", checkpoint.authority_id),
        ("stream_id", checkpoint.stream_id),
        ("stream_version", checkpoint.stream_version),
    ):
        require_text(value, field)
    require_integer(
        checkpoint.last_applied_position, "last_applied_position", minimum=1
    )
    _require_sha256(checkpoint.prefix_fingerprint, "prefix_fingerprint")
    _validate_artifact(checkpoint.fact_checkpoint, "fact_checkpoint")
    _require_utc_text(checkpoint.updated_at_utc, "updated_at_utc")
    return internal_record_bytes(checkpoint.as_document())


def build_replan_attempt(
    *,
    request_id: str,
    request_fingerprint: str,
    planning_run_id: str,
    attempt_number: int,
    idempotency_scope: str,
    idempotency_key_reference: str,
    correlation_id: str,
    created_at_utc: str,
) -> ReplanAttemptReference:
    payload: dict[str, object] = {
        "record_version": ReplanAttemptReference.record_version,
        "request_id": request_id,
        "request_fingerprint": request_fingerprint,
        "planning_run_id": planning_run_id,
        "attempt_number": attempt_number,
        "idempotency_scope": idempotency_scope,
        "idempotency_key_reference": idempotency_key_reference,
        "correlation_id": correlation_id,
        "created_at_utc": created_at_utc,
    }
    fingerprint = contract_fingerprint(payload)
    return ReplanAttemptReference(
        attempt_id=_derived_identity("replan-attempt-", fingerprint),
        attempt_fingerprint=fingerprint,
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        planning_run_id=planning_run_id,
        attempt_number=attempt_number,
        idempotency_scope=idempotency_scope,
        idempotency_key_reference=idempotency_key_reference,
        correlation_id=correlation_id,
        created_at_utc=created_at_utc,
    )


def validate_replan_attempt(attempt: ReplanAttemptReference) -> bytes:
    document = attempt.as_document()
    for field in (
        "attempt_id",
        "request_id",
        "planning_run_id",
        "idempotency_scope",
        "correlation_id",
    ):
        require_text(document.get(field), field)
    require_integer(attempt.attempt_number, "attempt_number", minimum=1)
    _require_sha256(attempt.request_fingerprint, "request_fingerprint")
    _require_sha256(
        attempt.idempotency_key_reference, "idempotency_key_reference"
    )
    _require_utc_text(attempt.created_at_utc, "created_at_utc")
    expected = contract_fingerprint(
        _without(document, "attempt_id", "attempt_fingerprint")
    )
    if attempt.attempt_fingerprint != expected or attempt.attempt_id != (
        _derived_identity("replan-attempt-", expected)
    ):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="attempt_id/attempt_fingerprint",
            message="attempt identity does not match canonical content",
        )
    return internal_record_bytes(document)


def build_replan_result(
    *,
    attempt: ReplanAttemptReference,
    planning_run_terminal_state: str,
    solver_report: ArtifactReference | None,
    validation_report: ArtifactReference | None,
    new_schedule_version: ArtifactReference | None,
    change_report: ArtifactReference | None,
    correlation_id: str,
    finished_at_utc: str,
) -> ReplanResultReference:
    payload: dict[str, object] = {
        "record_version": ReplanResultReference.record_version,
        "attempt_id": attempt.attempt_id,
        "request_id": attempt.request_id,
        "request_fingerprint": attempt.request_fingerprint,
        "planning_run_id": attempt.planning_run_id,
        "planning_run_terminal_state": planning_run_terminal_state,
        "solver_report": _artifact_document(solver_report),
        "validation_report": _artifact_document(validation_report),
        "new_schedule_version": _artifact_document(new_schedule_version),
        "change_report": _artifact_document(change_report),
        "correlation_id": correlation_id,
        "finished_at_utc": finished_at_utc,
    }
    fingerprint = contract_fingerprint(payload)
    return ReplanResultReference(
        result_id=_derived_identity("replan-result-", fingerprint),
        result_fingerprint=fingerprint,
        attempt_id=attempt.attempt_id,
        request_id=attempt.request_id,
        request_fingerprint=attempt.request_fingerprint,
        planning_run_id=attempt.planning_run_id,
        planning_run_terminal_state=planning_run_terminal_state,
        solver_report=solver_report,
        validation_report=validation_report,
        new_schedule_version=new_schedule_version,
        change_report=change_report,
        correlation_id=correlation_id,
        finished_at_utc=finished_at_utc,
    )


def validate_replan_result(result: ReplanResultReference) -> bytes:
    document = result.as_document()
    for field in (
        "result_id",
        "attempt_id",
        "request_id",
        "planning_run_id",
        "correlation_id",
    ):
        require_text(document.get(field), field)
    _require_sha256(result.request_fingerprint, "request_fingerprint")
    _require_utc_text(result.finished_at_utc, "finished_at_utc")
    if result.planning_run_terminal_state not in TERMINAL_PLANNING_RUN_STATES:
        reject(
            PersistenceFailure.STATE_CONFLICT,
            field="planning_run_terminal_state",
            message="result must reference an existing terminal PlanningRun state",
        )
    _validate_artifact(result.solver_report, "solver_report", expected_version="solver-report.v2")
    _validate_artifact(
        result.validation_report,
        "validation_report",
        expected_version="validation-report.v2",
    )
    _validate_artifact(
        result.new_schedule_version,
        "new_schedule_version",
        expected_version="schedule-version.v2",
    )
    _validate_artifact(
        result.change_report,
        "change_report",
        expected_version="change-report.v1",
    )
    if result.planning_run_terminal_state == "COMPLETED":
        if any(
            reference is None
            for reference in (
                result.solver_report,
                result.validation_report,
                result.new_schedule_version,
                result.change_report,
            )
        ):
            reject(
                PersistenceFailure.STATE_CONFLICT,
                field="result.references",
                message="COMPLETED result requires all approved artifact references",
            )
    elif result.new_schedule_version is not None or result.change_report is not None:
        reject(
            PersistenceFailure.STATE_CONFLICT,
            field="result.references",
            message="non-COMPLETED result cannot expose success references",
        )
    expected = contract_fingerprint(
        _without(document, "result_id", "result_fingerprint")
    )
    if result.result_fingerprint != expected or result.result_id != (
        _derived_identity("replan-result-", expected)
    ):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="result_id/result_fingerprint",
            message="result identity does not match canonical content",
        )
    return internal_record_bytes(document)


def build_replan_audit_record(
    *,
    action: ReplanAuditAction,
    aggregate_type: str,
    aggregate_id: str,
    correlation_id: str,
    idempotency_scope: str,
    idempotency_key_reference: str,
    request_fingerprint: str | None,
    occurred_at_utc: str,
) -> ReplanAuditRecord:
    payload: dict[str, object] = {
        "record_version": ReplanAuditRecord.record_version,
        "action": action.value,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "correlation_id": correlation_id,
        "idempotency_scope": idempotency_scope,
        "idempotency_key_reference": idempotency_key_reference,
        "request_fingerprint": request_fingerprint,
        "occurred_at_utc": occurred_at_utc,
    }
    fingerprint = contract_fingerprint(payload)
    return ReplanAuditRecord(
        audit_record_id=_derived_identity("replan-audit-", fingerprint),
        audit_fingerprint=fingerprint,
        action=action,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        correlation_id=correlation_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_reference=idempotency_key_reference,
        request_fingerprint=request_fingerprint,
        occurred_at_utc=occurred_at_utc,
    )


def validate_replan_audit_record(record: ReplanAuditRecord) -> bytes:
    document = record.as_document()
    for field in (
        "audit_record_id",
        "aggregate_type",
        "aggregate_id",
        "correlation_id",
        "idempotency_scope",
    ):
        require_text(document.get(field), field)
    _require_sha256(record.idempotency_key_reference, "idempotency_key_reference")
    if record.request_fingerprint is not None:
        _require_sha256(record.request_fingerprint, "request_fingerprint")
    _require_utc_text(record.occurred_at_utc, "occurred_at_utc")
    expected = contract_fingerprint(
        _without(document, "audit_record_id", "audit_fingerprint")
    )
    if record.audit_fingerprint != expected or record.audit_record_id != (
        _derived_identity("replan-audit-", expected)
    ):
        reject(
            PersistenceFailure.INVALID_DOCUMENT,
            field="audit_record_id/audit_fingerprint",
            message="audit identity does not match canonical content",
        )
    return internal_record_bytes(document)


def unreachable() -> NoReturn:
    """Typing-only guard for fail-closed branches."""

    raise AssertionError("unreachable")


__all__ = [
    "EXECUTION_EVENT_LEDGER",
    "REPLAN_ATTEMPTS",
    "REPLAN_AUDIT_RECORDS",
    "REPLAN_PROJECTION_CHECKPOINTS",
    "REPLAN_REQUESTS",
    "REPLAN_REQUEST_EVENTS",
    "REPLAN_RESULTS",
    "TERMINAL_PLANNING_RUN_STATES",
    "ArtifactReference",
    "ProjectionCheckpoint",
    "ReplanAttemptReference",
    "ReplanAuditAction",
    "ReplanAuditRecord",
    "ReplanResultReference",
    "build_replan_attempt",
    "build_replan_audit_record",
    "build_replan_result",
    "canonical_p4_document",
    "internal_record_bytes",
    "internal_record_sha256",
    "load_internal_record",
    "load_p4_document",
    "validate_projection_checkpoint",
    "validate_replan_attempt",
    "validate_replan_audit_record",
    "validate_replan_result",
]
