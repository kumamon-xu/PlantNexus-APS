"""Atomic approval/rejection application service for TASK-P3-07."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, cast

from app.domain.authorization import (
    ApprovalDecisionContext,
    ApprovalDecisionError,
    ApprovalDecisionFailure,
    ApprovalDecisionIdentity,
    approval_decision_identity,
    build_approval_decision_documents,
    build_authorization_denial_audit,
    prepare_approval_decision,
    reject_approval_decision,
    require_approval_decision_authorization,
)


class DocumentWriteResultPort(Protocol):
    document: dict[str, object]
    replayed: bool


class StateWriteResultPort(Protocol):
    document: dict[str, object]
    state_revision: int


class StoredScheduleVersionPort(Protocol):
    document: dict[str, object]
    state_revision: int


class ApprovalScheduleRepositoryPort(Protocol):
    def get(self, schedule_version_id: str) -> dict[str, object] | None: ...

    def get_record(
        self, schedule_version_id: str
    ) -> StoredScheduleVersionPort | None: ...

    def transition_in_transaction(
        self,
        connection: object,
        *,
        schedule_version_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
    ) -> StateWriteResultPort: ...


class ApprovalAuditRepositoryPort(Protocol):
    def get(self, audit_event_id: str) -> dict[str, object] | None: ...

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> DocumentWriteResultPort: ...


type TransactionFactory = Callable[[], AbstractContextManager[object]]


@dataclass(frozen=True, slots=True)
class ApprovalDecisionResult:
    """Stable logical decision result returned for first commit or replay."""

    command_id: str
    command_type: str
    request_fingerprint: str
    source_version: dict[str, object]
    new_version: dict[str, object]
    audit_event_id: str
    correlation_id: str
    schedule_replayed: bool
    audit_replayed: bool

    @property
    def exact_replay(self) -> bool:
        return self.schedule_replayed and self.audit_replayed


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_approval_decision(
            ApprovalDecisionFailure.PERSISTENCE_FAILED,
            field=field,
            message="stored decision evidence is incomplete",
        )
    return cast(Mapping[str, object], value)


def _reference(value: object, field: str) -> dict[str, object]:
    return dict(_mapping(value, field))


def _persistence_failure(error: Exception) -> ApprovalDecisionError:
    raw_reason = getattr(error, "reason", None)
    reason = str(getattr(raw_reason, "value", raw_reason))
    raw_field = getattr(error, "field", "approval_transaction")
    field = raw_field if isinstance(raw_field, str) else "approval_transaction"
    mapping = {
        "DATA_PLANE_MISMATCH": ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
        "IDENTITY_CONFLICT": ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
        "IDEMPOTENCY_CONFLICT": ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
        "STATE_CONFLICT": ApprovalDecisionFailure.STALE_SOURCE,
    }
    return ApprovalDecisionError(
        mapping.get(reason, ApprovalDecisionFailure.PERSISTENCE_FAILED),
        field=field,
        message="approval decision persistence rejected the request",
    )


class ApprovalDecisionService:
    """Authorize before lookup, then atomically CAS state and append audit."""

    def __init__(
        self,
        *,
        data_plane: str,
        transaction_factory: TransactionFactory,
        schedule_repository: ApprovalScheduleRepositoryPort,
        audit_repository: ApprovalAuditRepositoryPort,
    ) -> None:
        self._data_plane = data_plane
        self._transaction_factory = transaction_factory
        self._schedule_repository = schedule_repository
        self._audit_repository = audit_repository

    @property
    def data_plane(self) -> str:
        return self._data_plane

    def _get_audit(self, audit_event_id: str) -> dict[str, object] | None:
        try:
            return self._audit_repository.get(audit_event_id)
        except ApprovalDecisionError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _get_record(self, schedule_version_id: str) -> StoredScheduleVersionPort | None:
        try:
            return self._schedule_repository.get_record(schedule_version_id)
        except ApprovalDecisionError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    @staticmethod
    def _check_audit_identity(
        audit: Mapping[str, object], identity: ApprovalDecisionIdentity
    ) -> None:
        if audit.get("request_fingerprint") != identity.request_fingerprint:
            reject_approval_decision(
                ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
                field="command.idempotency_key",
                message="is already bound to a different request fingerprint",
            )
        expected = {
            "audit_event_id": identity.audit_event_id,
            "action": identity.action,
            "aggregate_type": "SCHEDULE_VERSION",
            "aggregate_id": identity.schedule_version_id,
            "target": "WORKSPACE_INTERNAL",
            "intent_type": "DECISION",
        }
        if any(audit.get(field) != value for field, value in expected.items()):
            reject_approval_decision(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                field="audit_event",
                message="does not match the deterministic decision identity",
            )

    def _record_denial(
        self,
        command: Mapping[str, object],
        context: ApprovalDecisionContext,
        identity: ApprovalDecisionIdentity,
    ) -> None:
        existing = self._get_audit(identity.audit_event_id)
        if existing is not None:
            self._check_audit_identity(existing, identity)
            outcome = _mapping(existing.get("result"), "audit.result").get("outcome")
            if outcome in {"DENIED", "SUCCEEDED"}:
                return
            reject_approval_decision(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                field="audit.result",
                message="stored decision outcome is not replayable",
            )
        denial = build_authorization_denial_audit(
            command,
            context,
            identity,
            data_plane=self._data_plane,
        )
        try:
            with self._transaction_factory() as connection:
                write = self._audit_repository.append_in_transaction(connection, denial)
                if write.document != denial:
                    reject_approval_decision(
                        ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored denial differs from the exact request",
                    )
        except ApprovalDecisionError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _replay(
        self,
        command: Mapping[str, object],
        identity: ApprovalDecisionIdentity,
    ) -> ApprovalDecisionResult | None:
        audit = self._get_audit(identity.audit_event_id)
        if audit is None:
            return None
        self._check_audit_identity(audit, identity)
        result = _mapping(audit.get("result"), "audit.result")
        if result.get("outcome") == "DENIED":
            reject_approval_decision(
                ApprovalDecisionFailure.AUTHORIZATION_DENIED,
                field="command.idempotency_key",
                message="the exact decision identity is bound to a denied attempt",
            )
        if result.get("outcome") != "SUCCEEDED":
            reject_approval_decision(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                field="audit.result",
                message="stored decision outcome is not a committed success",
            )
        try:
            stored = self._schedule_repository.get(identity.schedule_version_id)
        except ApprovalDecisionError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error
        if stored is None:
            reject_approval_decision(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                field="schedule_version",
                message="decision audit exists without its durable ScheduleVersion",
            )
        source_reference = _reference(
            audit.get("source_version"), "audit.source_version"
        )
        new_reference = _reference(audit.get("new_version"), "audit.new_version")
        if (
            source_reference.get("schedule_version_id") != identity.schedule_version_id
            or source_reference.get("state") != "READY_FOR_REVIEW"
            or new_reference.get("schedule_version_id") != identity.schedule_version_id
            or new_reference.get("state") != identity.target_state
            or new_reference.get("content_fingerprint")
            != stored.get("content_fingerprint")
        ):
            reject_approval_decision(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                field="audit.source_version/new_version",
                message="does not bind the immutable stored decision",
            )
        decision = _mapping(stored.get("decision"), "schedule_version.decision")
        if (
            decision.get("decision") != identity.target_state
            or decision.get("capability") != identity.required_capability
            or decision.get("audit_event_id") != identity.audit_event_id
        ):
            reject_approval_decision(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                field="schedule_version.decision",
                message="does not bind the exact successful audit",
            )
        return ApprovalDecisionResult(
            command_id=cast(str, command["command_id"]),
            command_type=identity.command_type,
            request_fingerprint=identity.request_fingerprint,
            source_version=source_reference,
            new_version=new_reference,
            audit_event_id=identity.audit_event_id,
            correlation_id=cast(str, audit["correlation_id"]),
            schedule_replayed=True,
            audit_replayed=True,
        )

    def execute(
        self,
        command: Mapping[str, object],
        context: ApprovalDecisionContext,
    ) -> ApprovalDecisionResult:
        """Execute one READY-only decision without publish, API, UI, or Solver."""

        identity = approval_decision_identity(command, data_plane=self._data_plane)
        try:
            require_approval_decision_authorization(
                context,
                identity,
                command,
                data_plane=self._data_plane,
            )
        except ApprovalDecisionError as error:
            if error.reason in {
                ApprovalDecisionFailure.AUTHORIZATION_DENIED,
                ApprovalDecisionFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
            }:
                self._record_denial(command, context, identity)
            raise
        replay = self._replay(command, identity)
        if replay is not None:
            return replay
        record = self._get_record(identity.schedule_version_id)
        if record is None:
            reject_approval_decision(
                ApprovalDecisionFailure.SOURCE_NOT_FOUND,
                field="command.source_id",
                message="does not identify an authorized ScheduleVersion in this plane",
            )
        prepared = prepare_approval_decision(
            record.document,
            command,
            context,
            data_plane=self._data_plane,
        )
        documents = build_approval_decision_documents(prepared)
        try:
            with self._transaction_factory() as connection:
                transition = self._schedule_repository.transition_in_transaction(
                    connection,
                    schedule_version_id=identity.schedule_version_id,
                    expected_state="READY_FOR_REVIEW",
                    expected_state_revision=record.state_revision,
                    candidate_document=documents.decided_schedule,
                )
                if transition.document != documents.decided_schedule:
                    reject_approval_decision(
                        ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
                        field="schedule_version",
                        message="stored state differs from the exact decision",
                    )
                audit_write = self._audit_repository.append_in_transaction(
                    connection, documents.audit_event
                )
                if audit_write.document != documents.audit_event:
                    reject_approval_decision(
                        ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored audit differs from the exact decision",
                    )
        except ApprovalDecisionError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            mapped = _persistence_failure(error)
            if mapped.reason is ApprovalDecisionFailure.STALE_SOURCE:
                raced_replay = self._replay(command, identity)
                if raced_replay is not None:
                    return raced_replay
            raise mapped from error
        return ApprovalDecisionResult(
            command_id=cast(str, command["command_id"]),
            command_type=identity.command_type,
            request_fingerprint=identity.request_fingerprint,
            source_version=_reference(
                documents.audit_event["source_version"], "audit.source_version"
            ),
            new_version=_reference(
                documents.audit_event["new_version"], "audit.new_version"
            ),
            audit_event_id=identity.audit_event_id,
            correlation_id=cast(str, command["correlation_id"]),
            schedule_replayed=False,
            audit_replayed=audit_write.replayed,
        )


__all__ = [
    "ApprovalAuditRepositoryPort",
    "ApprovalDecisionResult",
    "ApprovalDecisionService",
    "ApprovalScheduleRepositoryPort",
    "TransactionFactory",
]
