"""Atomic application service for P3 ExportJob creation and execution lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from app.domain.export_job import (
    ExportJobContext,
    ExportJobError,
    ExportJobFailure,
    ExportJobRequest,
    audit_event_id,
    build_created_export_job,
    build_export_audit,
    build_export_authorization_denial_audit,
    export_job_identity,
    heartbeat_export_job,
    lease_reference_for,
    reject_export_job,
    require_export_authorization,
    require_job_authorization,
    transition_export_job,
)
from app.domain.types import parse_utc_instant


class StoredExportJobPort(Protocol):
    document: dict[str, object]
    state_revision: int
    lease_expires_at_utc: datetime | None


class StateWriteResultPort(Protocol):
    document: dict[str, object]
    state_revision: int


class ExportScheduleRepositoryPort(Protocol):
    def get_record(self, schedule_version_id: str) -> object | None: ...


class ExportJobRepositoryPort(Protocol):
    def get(self, export_job_id: str) -> StoredExportJobPort | None: ...

    def create_in_transaction(self, connection: object, document: Mapping[str, object]) -> object: ...

    def transition_in_transaction(
        self,
        connection: object,
        *,
        export_job_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
        observed_at_utc: datetime,
        expected_lease_reference: str | None = None,
        lease_expires_at_utc: datetime | None = None,
        allow_expired_lease_recovery: bool = False,
    ) -> StateWriteResultPort: ...

    def heartbeat_in_transaction(
        self,
        connection: object,
        *,
        export_job_id: str,
        expected_state_revision: int,
        expected_lease_reference: str,
        candidate_document: Mapping[str, object],
        observed_at_utc: datetime,
        lease_expires_at_utc: datetime,
    ) -> StateWriteResultPort: ...


class ExportAuditRepositoryPort(Protocol):
    def get(self, audit_event_id: str) -> dict[str, object] | None: ...
    def append(self, document: Mapping[str, object]) -> object: ...
    def append_in_transaction(self, connection: object, document: Mapping[str, object]) -> object: ...


type TransactionFactory = Callable[[], AbstractContextManager[object]]


@dataclass(frozen=True, slots=True)
class ExportJobServiceResult:
    document: dict[str, object]
    state_revision: int
    audit_event_id: str
    exact_replay: bool


def _persistence_error(error: Exception) -> ExportJobError:
    raw = getattr(getattr(error, "reason", None), "value", getattr(error, "reason", ""))
    mapping = {
        "IDEMPOTENCY_CONFLICT": ExportJobFailure.IDEMPOTENCY_CONFLICT,
        "IDENTITY_CONFLICT": ExportJobFailure.IDEMPOTENCY_CONFLICT,
        "STATE_CONFLICT": ExportJobFailure.STATE_CONFLICT,
        "LEASE_CONFLICT": ExportJobFailure.LEASE_CONFLICT,
        "DATA_PLANE_MISMATCH": ExportJobFailure.AUTHORIZATION_DENIED,
    }
    return ExportJobError(mapping.get(str(raw), ExportJobFailure.PERSISTENCE_FAILED), field=cast(str, getattr(error, "field", "persistence")))


def _record_document(record: object | None) -> dict[str, object] | None:
    if record is None:
        return None
    document = getattr(record, "document", record)
    return dict(document) if isinstance(document, Mapping) else None


class ExportJobService:
    """Authorize first; then use repository CAS and audit append in one transaction."""

    def __init__(
        self,
        *,
        transaction_factory: TransactionFactory,
        schedule_repository: ExportScheduleRepositoryPort,
        export_job_repository: ExportJobRepositoryPort,
        audit_repository: ExportAuditRepositoryPort,
    ) -> None:
        self._transaction_factory = transaction_factory
        self._schedule_repository = schedule_repository
        self._jobs = export_job_repository
        self._audits = audit_repository

    def _job(self, export_job_id: str) -> StoredExportJobPort:
        try:
            record = self._jobs.get(export_job_id)
        except ExportJobError:
            raise
        except Exception as error:
            raise _persistence_error(error) from error
        if record is None:
            reject_export_job(ExportJobFailure.SOURCE_NOT_FOUND, "export_job_id")
        return record

    def _transaction(self, action: Callable[[object], ExportJobServiceResult]) -> ExportJobServiceResult:
        try:
            with self._transaction_factory() as connection:
                return action(connection)
        except ExportJobError:
            raise
        except Exception as error:
            raise _persistence_error(error) from error

    def create(
        self,
        request: ExportJobRequest,
        context: ExportJobContext,
        *,
        publication_result: Mapping[str, object],
    ) -> ExportJobServiceResult:
        try:
            identity = require_export_authorization(request, context)
        except ExportJobError as error:
            if (
                error.reason is ExportJobFailure.AUTHORIZATION_DENIED
                and request.data_plane == "SIMULATION"
                and request.environment in {"DEVELOPMENT", "TEST", "BENCHMARK"}
            ):
                identity = export_job_identity(request)
                denial = build_export_authorization_denial_audit(
                    request, context, identity
                )
                try:
                    self._audits.append(denial)
                except Exception:
                    pass
            raise
        try:
            existing = self._jobs.get(identity.export_job_id)
        except Exception as error:
            raise _persistence_error(error) from error
        if existing is not None:
            reference = cast(Mapping[str, object], existing.document["idempotency_reference"])
            if reference.get("request_fingerprint") != identity.request_fingerprint:
                reject_export_job(ExportJobFailure.IDEMPOTENCY_CONFLICT, "idempotency_key")
            return ExportJobServiceResult(
                document=existing.document,
                state_revision=existing.state_revision,
                audit_event_id=identity.create_audit_event_id,
                exact_replay=True,
            )
        try:
            source_record = self._schedule_repository.get_record(request.schedule_version_id)
        except Exception as error:
            raise _persistence_error(error) from error
        source = _record_document(source_record)
        if source is None:
            reject_export_job(ExportJobFailure.SOURCE_NOT_FOUND, "schedule_version_id")
        job = build_created_export_job(request, identity, context, source, publication_result)
        audit = build_export_audit(
            job,
            context,
            audit_event_id_value=identity.create_audit_event_id,
            action="CREATE_EXPORT",
            before_state=None,
            after_state="CREATED",
            outcome="SUCCEEDED",
            idempotent_create=True,
            parent_audit_event_id=cast(str, publication_result["audit_event_id"]),
            correlation_id=request.correlation_id,
        )

        def persist(connection: object) -> ExportJobServiceResult:
            created = self._jobs.create_in_transaction(connection, job)
            self._audits.append_in_transaction(connection, audit)
            document = cast(dict[str, object], getattr(created, "document", job))
            replayed = bool(getattr(created, "replayed", False))
            return ExportJobServiceResult(document, 0, identity.create_audit_event_id, replayed)

        return self._transaction(persist)

    def _transition(
        self,
        export_job_id: str,
        context: ExportJobContext,
        *,
        target_state: str,
        audit_phase: str,
        action: str,
        attempt: int | None = None,
        lease_reference: str | None = None,
        lease_expires_at_utc: datetime | None = None,
        artifact_manifest: Mapping[str, object] | None = None,
        error_message: str | None = None,
        expected_lease_reference: str | None = None,
        allow_expired_lease_recovery: bool = False,
    ) -> ExportJobServiceResult:
        require_job_authorization(export_job_id, context)
        stored = self._job(export_job_id)
        current = stored.document
        source_state = cast(str, current["state"])
        effective_attempt = cast(int, current["attempt"]) if attempt is None else attempt
        event_id = audit_event_id(export_job_id, audit_phase, effective_attempt)
        candidate = transition_export_job(
            current,
            target_state=target_state,
            occurred_at_utc=context.occurred_at_utc,
            audit_event_id_value=event_id,
            attempt=effective_attempt,
            lease_reference=lease_reference,
            artifact_manifest=artifact_manifest,
            error_message=error_message,
        )
        outcome = "FAILED" if target_state == "EXPORT_FAILED" else "SUCCEEDED"
        audit = build_export_audit(
            candidate,
            context,
            audit_event_id_value=event_id,
            action=action,
            before_state=source_state,
            after_state=target_state,
            outcome=outcome,
            error_reason="EXPORT_FAILED" if target_state == "EXPORT_FAILED" else None,
            parent_audit_event_id=cast(str, current["latest_audit_event_id"]),
        )
        observed = parse_utc_instant(context.occurred_at_utc)

        def persist(connection: object) -> ExportJobServiceResult:
            state = self._jobs.transition_in_transaction(
                connection,
                export_job_id=export_job_id,
                expected_state=source_state,
                expected_state_revision=stored.state_revision,
                candidate_document=candidate,
                observed_at_utc=observed,
                expected_lease_reference=expected_lease_reference,
                lease_expires_at_utc=lease_expires_at_utc,
                allow_expired_lease_recovery=allow_expired_lease_recovery,
            )
            self._audits.append_in_transaction(connection, audit)
            return ExportJobServiceResult(state.document, state.state_revision, event_id, False)

        return self._transaction(persist)

    def claim(
        self,
        export_job_id: str,
        context: ExportJobContext,
        *,
        owner_reference: str,
        lease_expires_at_utc: datetime,
    ) -> ExportJobServiceResult:
        require_job_authorization(export_job_id, context)
        current = self._job(export_job_id)
        if current.document["state"] not in {"CREATED", "EXPORT_FAILED"}:
            reject_export_job(ExportJobFailure.STATE_CONFLICT, "state")
        attempt = cast(int, current.document["attempt"]) + 1
        lease = lease_reference_for(export_job_id, attempt, owner_reference)
        return self._transition(
            export_job_id,
            context,
            target_state="EXPORTING",
            audit_phase="ATTEMPT",
            action="CREATE_EXPORT" if attempt == 1 else "RETRY_EXPORT",
            attempt=attempt,
            lease_reference=lease,
            lease_expires_at_utc=lease_expires_at_utc,
        )

    def heartbeat(
        self,
        export_job_id: str,
        context: ExportJobContext,
        *,
        expected_lease_reference: str,
        lease_expires_at_utc: datetime,
    ) -> ExportJobServiceResult:
        require_job_authorization(export_job_id, context)
        stored = self._job(export_job_id)
        candidate = heartbeat_export_job(stored.document, occurred_at_utc=context.occurred_at_utc)
        observed = parse_utc_instant(context.occurred_at_utc)

        def persist(connection: object) -> ExportJobServiceResult:
            state = self._jobs.heartbeat_in_transaction(
                connection,
                export_job_id=export_job_id,
                expected_state_revision=stored.state_revision,
                expected_lease_reference=expected_lease_reference,
                candidate_document=candidate,
                observed_at_utc=observed,
                lease_expires_at_utc=lease_expires_at_utc,
            )
            return ExportJobServiceResult(state.document, state.state_revision, cast(str, candidate["latest_audit_event_id"]), False)

        return self._transaction(persist)

    def complete(self, export_job_id: str, context: ExportJobContext, *, expected_lease_reference: str, artifact_manifest: Mapping[str, object]) -> ExportJobServiceResult:
        return self._transition(export_job_id, context, target_state="EXPORTED", audit_phase="COMPLETED", action="CREATE_EXPORT", artifact_manifest=artifact_manifest, expected_lease_reference=expected_lease_reference)

    def fail(self, export_job_id: str, context: ExportJobContext, *, expected_lease_reference: str, error_message: str = "Export attempt failed.", expired_recovery: bool = False) -> ExportJobServiceResult:
        return self._transition(export_job_id, context, target_state="EXPORT_FAILED", audit_phase="RECOVERED" if expired_recovery else "FAILED", action="RETRY_EXPORT", error_message=error_message, expected_lease_reference=expected_lease_reference, allow_expired_lease_recovery=expired_recovery)

    def cancel(self, export_job_id: str, context: ExportJobContext, *, expected_lease_reference: str | None = None, expired_recovery: bool = False) -> ExportJobServiceResult:
        return self._transition(export_job_id, context, target_state="CANCELLED", audit_phase="CANCELLED", action="CANCEL_EXPORT", expected_lease_reference=expected_lease_reference, allow_expired_lease_recovery=expired_recovery)


__all__ = ["ExportJobService", "ExportJobServiceResult"]
