"""Atomic internal publication application service for TASK-P3-08."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, cast

from app.domain.publication import (
    CurrentPublicationState,
    PublicationContext,
    PublicationError,
    PublicationFailure,
    PublicationIdentity,
    build_publication_authorization_denial_audit,
    build_publication_documents,
    build_publication_replay_result,
    prepare_publication,
    publication_identity,
    reject_publication,
    require_publication_authorization,
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


class CurrentPublicationReferencePort(Protocol):
    target: str
    schedule_version_id: str
    content_fingerprint: str
    publication_id: str
    reference_revision: int
    updated_at_utc: str


class PublicationWriteResultPort(Protocol):
    document: dict[str, object]
    replayed: bool
    current_reference: CurrentPublicationReferencePort | None
    current_changed: bool


class PublicationScheduleRepositoryPort(Protocol):
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


class PublicationAuditRepositoryPort(Protocol):
    def get(self, audit_event_id: str) -> dict[str, object] | None: ...

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> DocumentWriteResultPort: ...


class PublicationRepositoryPort(Protocol):
    def get_current(
        self, *, target: str = "SIMULATION_INTERNAL"
    ) -> CurrentPublicationReferencePort | None: ...

    def persist_and_set_current_in_transaction(
        self,
        connection: object,
        document: Mapping[str, object],
        *,
        expected_current: CurrentPublicationReferencePort | None,
    ) -> PublicationWriteResultPort: ...


type TransactionFactory = Callable[[], AbstractContextManager[object]]


@dataclass(frozen=True, slots=True)
class PublicationServiceResult:
    """Stable publication result for first commit or exact replay."""

    document: dict[str, object]
    published_version: dict[str, object]
    superseded_version: dict[str, object] | None
    audit_event_id: str
    current_schedule_version_id: str
    exact_replay: bool
    current_changed: bool


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_publication(
            PublicationFailure.PERSISTENCE_FAILED,
            field=field,
            message="stored publication evidence is incomplete",
        )
    return cast(Mapping[str, object], value)


def _reference(value: object, field: str) -> dict[str, object]:
    return dict(_mapping(value, field))


def _persistence_failure(error: Exception) -> PublicationError:
    raw_reason = getattr(error, "reason", None)
    reason = str(getattr(raw_reason, "value", raw_reason))
    raw_field = getattr(error, "field", "publication_transaction")
    field = raw_field if isinstance(raw_field, str) else "publication_transaction"
    if reason == "DATA_PLANE_MISMATCH":
        mapped = PublicationFailure.DATA_PLANE_MISMATCH
    elif reason in {"IDENTITY_CONFLICT", "IDEMPOTENCY_CONFLICT"}:
        mapped = PublicationFailure.IDEMPOTENCY_CONFLICT
    elif reason == "STATE_CONFLICT":
        mapped = (
            PublicationFailure.CURRENT_REFERENCE_CONFLICT
            if "current" in field or "previous" in field
            else PublicationFailure.STALE_SOURCE
        )
    else:
        mapped = PublicationFailure.PERSISTENCE_FAILED
    return PublicationError(
        mapped,
        field=field,
        message="publication persistence rejected the request",
    )


def _current_state(
    reference: CurrentPublicationReferencePort | None,
) -> CurrentPublicationState | None:
    if reference is None:
        return None
    return CurrentPublicationState(
        target=reference.target,
        schedule_version_id=reference.schedule_version_id,
        content_fingerprint=reference.content_fingerprint,
        publication_id=reference.publication_id,
    )


class PublicationService:
    """Authorize first, then atomically publish/current/supersede/audit."""

    def __init__(
        self,
        *,
        data_plane: str,
        transaction_factory: TransactionFactory,
        schedule_repository: PublicationScheduleRepositoryPort,
        audit_repository: PublicationAuditRepositoryPort,
        publication_repository: PublicationRepositoryPort,
    ) -> None:
        self._data_plane = data_plane
        self._transaction_factory = transaction_factory
        self._schedule_repository = schedule_repository
        self._audit_repository = audit_repository
        self._publication_repository = publication_repository

    @property
    def data_plane(self) -> str:
        return self._data_plane

    def _get_audit(self, audit_event_id: str) -> dict[str, object] | None:
        try:
            return self._audit_repository.get(audit_event_id)
        except PublicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _get_record(self, schedule_version_id: str) -> StoredScheduleVersionPort | None:
        try:
            return self._schedule_repository.get_record(schedule_version_id)
        except PublicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _get_schedule(self, schedule_version_id: str) -> dict[str, object] | None:
        try:
            return self._schedule_repository.get(schedule_version_id)
        except PublicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _get_current(self) -> CurrentPublicationReferencePort | None:
        try:
            return self._publication_repository.get_current(
                target="SIMULATION_INTERNAL"
            )
        except PublicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _check_audit_identity(
        self, audit: Mapping[str, object], identity: PublicationIdentity
    ) -> None:
        if audit.get("request_fingerprint") != identity.request_fingerprint:
            reject_publication(
                PublicationFailure.IDEMPOTENCY_CONFLICT,
                field="command.idempotency_key",
                message="is already bound to a different request fingerprint",
            )
        idempotency = _mapping(
            audit.get("idempotency_reference"), "audit.idempotency_reference"
        )
        expected_target = (
            "WORKSPACE_INTERNAL"
            if self._data_plane == "PRODUCTION"
            else "SIMULATION_INTERNAL"
        )
        expected = {
            "audit_event_id": identity.audit_event_id,
            "action": "PUBLISH",
            "aggregate_type": "SCHEDULE_VERSION",
            "aggregate_id": identity.schedule_version_id,
            "target": expected_target,
            "intent_type": "PUBLICATION",
        }
        if (
            any(audit.get(field) != value for field, value in expected.items())
            or idempotency.get("key_reference") != identity.key_reference
            or idempotency.get("request_fingerprint")
            != identity.request_fingerprint
        ):
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="audit_event",
                message="does not match the deterministic publication identity",
            )

    def _record_denial(
        self,
        command: Mapping[str, object],
        context: PublicationContext,
        identity: PublicationIdentity,
    ) -> None:
        existing = self._get_audit(identity.audit_event_id)
        if existing is not None:
            self._check_audit_identity(existing, identity)
            outcome = _mapping(existing.get("result"), "audit.result").get("outcome")
            if outcome in {"DENIED", "SUCCEEDED"}:
                return
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="audit.result",
                message="stored publication outcome is not replayable",
            )
        denial = build_publication_authorization_denial_audit(
            command,
            context,
            identity,
            data_plane=self._data_plane,
        )
        try:
            with self._transaction_factory() as connection:
                write = self._audit_repository.append_in_transaction(connection, denial)
                if write.document != denial:
                    reject_publication(
                        PublicationFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored denial differs from the exact request",
                    )
        except PublicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

    def _verify_replayed_schedules(
        self,
        command: Mapping[str, object],
        identity: PublicationIdentity,
        audit: Mapping[str, object],
    ) -> None:
        stored = self._get_schedule(identity.schedule_version_id)
        if stored is None:
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="schedule_version",
                message="publication audit exists without its durable ScheduleVersion",
            )
        source_reference = _reference(
            audit.get("source_version"), "audit.source_version"
        )
        published_reference = _reference(
            audit.get("new_version"), "audit.new_version"
        )
        if (
            source_reference.get("schedule_version_id")
            != identity.schedule_version_id
            or source_reference.get("state") != "APPROVED"
            or published_reference.get("schedule_version_id")
            != identity.schedule_version_id
            or published_reference.get("state") != "PUBLISHED"
            or published_reference.get("content_fingerprint")
            != stored.get("content_fingerprint")
            or stored.get("state") not in {"PUBLISHED", "SUPERSEDED"}
        ):
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="audit.source_version/new_version",
                message="does not bind the immutable stored publication",
            )
        evidence = _mapping(stored.get("publication"), "schedule_version.publication")
        if (
            evidence.get("publication_id") != identity.publication_id
            or evidence.get("audit_event_id") != identity.audit_event_id
            or evidence.get("target") != "SIMULATION_INTERNAL"
        ):
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="schedule_version.publication",
                message="does not bind the exact successful audit",
            )
        payload = _mapping(command.get("payload"), "command.payload")
        previous_value = payload.get("previous_current_version")
        if previous_value is None:
            return
        previous_reference = _mapping(
            previous_value, "command.payload.previous_current_version"
        )
        previous_id = cast(str, previous_reference["schedule_version_id"])
        previous = self._get_schedule(previous_id)
        if previous is None:
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="previous_current_version",
                message="supersession evidence exists without its durable Version",
            )
        superseded_by = _mapping(
            previous.get("superseded_by"), "previous_current.superseded_by"
        )
        if (
            previous.get("state") != "SUPERSEDED"
            or previous.get("content_fingerprint")
            != previous_reference.get("content_fingerprint")
            or superseded_by != published_reference
        ):
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="previous_current.superseded_by",
                message="does not bind the committed supersession",
            )

    def _replay(
        self,
        command: Mapping[str, object],
        identity: PublicationIdentity,
    ) -> PublicationServiceResult | None:
        audit = self._get_audit(identity.audit_event_id)
        if audit is None:
            return None
        self._check_audit_identity(audit, identity)
        result = _mapping(audit.get("result"), "audit.result")
        if result.get("outcome") == "DENIED":
            reject_publication(
                PublicationFailure.AUTHORIZATION_DENIED,
                field="command.idempotency_key",
                message="the exact publication identity is bound to a denied attempt",
            )
        if result.get("outcome") != "SUCCEEDED":
            reject_publication(
                PublicationFailure.PERSISTENCE_FAILED,
                field="audit.result",
                message="stored publication outcome is not a committed success",
            )
        self._verify_replayed_schedules(command, identity, audit)
        document = build_publication_replay_result(command, identity, audit)
        published = _reference(document["published_version"], "published_version")
        superseded_value = document["superseded_version"]
        superseded = (
            None
            if superseded_value is None
            else _reference(superseded_value, "superseded_version")
        )
        return PublicationServiceResult(
            document=document,
            published_version=published,
            superseded_version=superseded,
            audit_event_id=identity.audit_event_id,
            current_schedule_version_id=identity.schedule_version_id,
            exact_replay=True,
            current_changed=False,
        )

    def execute(
        self,
        command: Mapping[str, object],
        context: PublicationContext,
    ) -> PublicationServiceResult:
        """Execute one APPROVED-only internal publish without export/API/UI."""

        identity = publication_identity(command, data_plane=self._data_plane)
        try:
            require_publication_authorization(
                context,
                identity,
                command,
                data_plane=self._data_plane,
            )
        except PublicationError as error:
            if error.reason in {
                PublicationFailure.AUTHORIZATION_DENIED,
                PublicationFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
            }:
                self._record_denial(command, context, identity)
            raise
        replay = self._replay(command, identity)
        if replay is not None:
            return replay

        source_record = self._get_record(identity.schedule_version_id)
        if source_record is None:
            reject_publication(
                PublicationFailure.SOURCE_NOT_FOUND,
                field="command.source_id",
                message="does not identify an authorized ScheduleVersion in this plane",
            )
        current_reference = self._get_current()
        previous_record = (
            None
            if current_reference is None
            else self._get_record(current_reference.schedule_version_id)
        )
        if current_reference is not None and previous_record is None:
            reject_publication(
                PublicationFailure.PREVIOUS_CURRENT_NOT_FOUND,
                field="current.schedule_version_id",
                message="does not identify a durable current ScheduleVersion",
            )
        prepared = prepare_publication(
            source_record.document,
            previous_record.document if previous_record is not None else None,
            _current_state(current_reference),
            command,
            context,
            data_plane=self._data_plane,
        )
        documents = build_publication_documents(prepared)
        try:
            with self._transaction_factory() as connection:
                published_write = self._schedule_repository.transition_in_transaction(
                    connection,
                    schedule_version_id=identity.schedule_version_id,
                    expected_state="APPROVED",
                    expected_state_revision=source_record.state_revision,
                    candidate_document=documents.published_schedule,
                )
                if published_write.document != documents.published_schedule:
                    reject_publication(
                        PublicationFailure.IDEMPOTENCY_CONFLICT,
                        field="schedule_version",
                        message="stored state differs from the exact publication",
                    )
                if documents.superseded_schedule is not None:
                    if previous_record is None:
                        reject_publication(
                            PublicationFailure.PERSISTENCE_FAILED,
                            field="previous_current",
                            message="supersession candidate lost its durable source",
                        )
                    superseded_write = (
                        self._schedule_repository.transition_in_transaction(
                            connection,
                            schedule_version_id=cast(
                                str,
                                documents.superseded_schedule["schedule_version_id"],
                            ),
                            expected_state="PUBLISHED",
                            expected_state_revision=previous_record.state_revision,
                            candidate_document=documents.superseded_schedule,
                        )
                    )
                    if superseded_write.document != documents.superseded_schedule:
                        reject_publication(
                            PublicationFailure.IDEMPOTENCY_CONFLICT,
                            field="previous_current",
                            message="stored supersession differs from the exact request",
                        )
                audit_write = self._audit_repository.append_in_transaction(
                    connection, documents.audit_event
                )
                if audit_write.document != documents.audit_event:
                    reject_publication(
                        PublicationFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored audit differs from the exact publication",
                    )
                publication_write = (
                    self._publication_repository.persist_and_set_current_in_transaction(
                        connection,
                        documents.publication_result,
                        expected_current=current_reference,
                    )
                )
                if (
                    publication_write.document != documents.publication_result
                    or publication_write.replayed
                    or not publication_write.current_changed
                    or publication_write.current_reference is None
                    or publication_write.current_reference.schedule_version_id
                    != identity.schedule_version_id
                ):
                    reject_publication(
                        PublicationFailure.IDEMPOTENCY_CONFLICT,
                        field="publication_result/current_reference",
                        message="did not commit the exact current publication",
                    )
        except PublicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            mapped = _persistence_failure(error)
            if mapped.reason in {
                PublicationFailure.STALE_SOURCE,
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
            }:
                raced_replay = self._replay(command, identity)
                if raced_replay is not None:
                    return raced_replay
            raise mapped from error

        return PublicationServiceResult(
            document=documents.publication_result,
            published_version=_reference(
                documents.publication_result["published_version"],
                "published_version",
            ),
            superseded_version=(
                None
                if documents.publication_result["superseded_version"] is None
                else _reference(
                    documents.publication_result["superseded_version"],
                    "superseded_version",
                )
            ),
            audit_event_id=identity.audit_event_id,
            current_schedule_version_id=identity.schedule_version_id,
            exact_replay=False,
            current_changed=True,
        )


__all__ = [
    "CurrentPublicationReferencePort",
    "PublicationAuditRepositoryPort",
    "PublicationRepositoryPort",
    "PublicationScheduleRepositoryPort",
    "PublicationService",
    "PublicationServiceResult",
    "TransactionFactory",
]
