"""Atomic content-command and review-submit service for TASK-P3-06."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, cast

from app.domain.schedule_commands import (
    ScheduleCommandContext,
    ScheduleCommandError,
    ScheduleCommandFailure,
    build_review_submission_documents,
    build_schedule_command_documents,
    prepare_review_submission,
    prepare_schedule_command,
    reject_command,
    require_schedule_command_authorization,
    schedule_command_identity,
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


class ScheduleVersionCommandRepositoryPort(Protocol):
    def get(self, schedule_version_id: str) -> dict[str, object] | None: ...

    def get_record(
        self, schedule_version_id: str
    ) -> StoredScheduleVersionPort | None: ...

    def put_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> DocumentWriteResultPort: ...

    def transition_in_transaction(
        self,
        connection: object,
        *,
        schedule_version_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
    ) -> StateWriteResultPort: ...


class AuditCommandRepositoryPort(Protocol):
    def get(self, audit_event_id: str) -> dict[str, object] | None: ...

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> DocumentWriteResultPort: ...


class FormalScheduleValidatorPort(Protocol):
    def validate(
        self,
        problem: Mapping[str, object],
        candidate: Mapping[str, object],
    ) -> Mapping[str, object]: ...


type TransactionFactory = Callable[[], AbstractContextManager[object]]
type ValidatorFactory = Callable[[], FormalScheduleValidatorPort]


@dataclass(frozen=True, slots=True)
class ScheduleCommandResult:
    """Stable logical result for DRAFT creation or explicit READY submission."""

    command_id: str
    command_type: str
    request_fingerprint: str
    source_version: dict[str, object]
    new_version: dict[str, object]
    validation_report: dict[str, object]
    audit_event_id: str
    correlation_id: str
    schedule_replayed: bool
    audit_replayed: bool

    @property
    def exact_replay(self) -> bool:
        return self.schedule_replayed and self.audit_replayed


def _persistence_failure(error: Exception) -> ScheduleCommandError:
    raw_reason = getattr(error, "reason", None)
    reason = str(getattr(raw_reason, "value", raw_reason))
    raw_field = getattr(error, "field", "workspace_transaction")
    field = raw_field if isinstance(raw_field, str) else "workspace_transaction"
    mapping = {
        "DATA_PLANE_MISMATCH": ScheduleCommandFailure.DATA_PLANE_MISMATCH,
        "IDENTITY_CONFLICT": ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
        "IDEMPOTENCY_CONFLICT": ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
        "STATE_CONFLICT": ScheduleCommandFailure.STALE_SOURCE,
    }
    return ScheduleCommandError(
        mapping.get(reason, ScheduleCommandFailure.PERSISTENCE_FAILED),
        field=field,
        message="workspace command persistence rejected the request",
    )


def _reference(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        reject_command(
            ScheduleCommandFailure.PERSISTENCE_FAILED,
            field=field,
            message="stored command evidence is incomplete",
        )
    return dict(cast(Mapping[str, object], value))


class ScheduleCommandService:
    """Fresh-validate and atomically commit DRAFT or same-content READY plus audit."""

    def __init__(
        self,
        *,
        data_plane: str,
        transaction_factory: TransactionFactory,
        schedule_repository: ScheduleVersionCommandRepositoryPort,
        audit_repository: AuditCommandRepositoryPort,
        validator_factory: ValidatorFactory,
    ) -> None:
        self._data_plane = data_plane
        self._transaction_factory = transaction_factory
        self._schedule_repository = schedule_repository
        self._audit_repository = audit_repository
        self._validator_factory = validator_factory

    @property
    def data_plane(self) -> str:
        return self._data_plane

    def _fresh_validate(
        self,
        problem: Mapping[str, object],
        candidate: Mapping[str, object],
    ) -> Mapping[str, object]:
        try:
            validator = self._validator_factory()
            return validator.validate(problem, candidate)
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise ScheduleCommandError(
                ScheduleCommandFailure.MIXED_LINEAGE,
                field="problem/validator_candidate",
                message="fresh formal validation could not evaluate the candidate",
            ) from error

    def _replay(
        self,
        command: Mapping[str, object],
        *,
        identity_request_fingerprint: str,
        audit_event_id: str,
        schedule_version_id: str,
    ) -> ScheduleCommandResult | None:
        audit = self._audit_repository.get(audit_event_id)
        if audit is None:
            return None
        if audit.get("request_fingerprint") != identity_request_fingerprint:
            reject_command(
                ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
                field="command.idempotency_key",
                message="is already bound to a different request fingerprint",
            )
        stored = self._schedule_repository.get(schedule_version_id)
        if stored is None:
            reject_command(
                ScheduleCommandFailure.PERSISTENCE_FAILED,
                field="schedule_version",
                message="idempotency audit exists without its durable result",
            )
        new_reference = _reference(audit.get("new_version"), "audit.new_version")
        if new_reference.get(
            "schedule_version_id"
        ) != schedule_version_id or new_reference.get(
            "content_fingerprint"
        ) != stored.get("content_fingerprint"):
            reject_command(
                ScheduleCommandFailure.PERSISTENCE_FAILED,
                field="audit.new_version",
                message="does not bind the immutable stored result",
            )
        lineage = _reference(stored.get("lineage"), "schedule_version.lineage")
        validation = _reference(
            lineage.get("validation_report"),
            "schedule_version.lineage.validation_report",
        )
        return ScheduleCommandResult(
            command_id=cast(str, command["command_id"]),
            command_type=cast(str, command["command_type"]),
            request_fingerprint=identity_request_fingerprint,
            source_version=_reference(
                audit.get("source_version"), "audit.source_version"
            ),
            new_version=new_reference,
            validation_report=validation,
            audit_event_id=audit_event_id,
            correlation_id=cast(str, audit["correlation_id"]),
            schedule_replayed=True,
            audit_replayed=True,
        )

    def _submit_for_review(
        self,
        command: Mapping[str, object],
        problem: Mapping[str, object],
        context: ScheduleCommandContext,
        record: StoredScheduleVersionPort,
    ) -> ScheduleCommandResult:
        prepared = prepare_review_submission(
            record.document,
            problem,
            command,
            context,
            data_plane=self._data_plane,
        )
        report = self._fresh_validate(
            prepared.problem,
            prepared.validator_candidate,
        )
        documents = build_review_submission_documents(prepared, report)
        try:
            with self._transaction_factory() as connection:
                transition = self._schedule_repository.transition_in_transaction(
                    connection,
                    schedule_version_id=prepared.identity.schedule_version_id,
                    expected_state="DRAFT",
                    expected_state_revision=record.state_revision,
                    candidate_document=documents.ready_for_review,
                )
                if transition.document != documents.ready_for_review:
                    reject_command(
                        ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
                        field="schedule_version",
                        message="stored READY result differs from the exact request",
                    )
                audit_write = self._audit_repository.append_in_transaction(
                    connection, documents.audit_event
                )
                if audit_write.document != documents.audit_event:
                    reject_command(
                        ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored review audit differs from the exact request",
                    )
        except ScheduleCommandError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error
        return ScheduleCommandResult(
            command_id=cast(str, command["command_id"]),
            command_type=prepared.identity.command_type,
            request_fingerprint=prepared.identity.request_fingerprint,
            source_version=_reference(
                documents.audit_event["source_version"], "audit.source_version"
            ),
            new_version=_reference(
                documents.audit_event["new_version"], "audit.new_version"
            ),
            validation_report=_reference(
                cast(Mapping[str, object], documents.ready_for_review["lineage"])[
                    "validation_report"
                ],
                "schedule_version.lineage.validation_report",
            ),
            audit_event_id=prepared.identity.audit_event_id,
            correlation_id=cast(str, command["correlation_id"]),
            schedule_replayed=False,
            audit_replayed=audit_write.replayed,
        )

    def execute(
        self,
        command: Mapping[str, object],
        problem: Mapping[str, object],
        context: ScheduleCommandContext,
    ) -> ScheduleCommandResult:
        """Execute one command without Solver, source update, or failed version."""

        identity = schedule_command_identity(command, data_plane=self._data_plane)
        require_schedule_command_authorization(
            context, identity, data_plane=self._data_plane
        )
        replay = self._replay(
            command,
            identity_request_fingerprint=identity.request_fingerprint,
            audit_event_id=identity.audit_event_id,
            schedule_version_id=identity.schedule_version_id,
        )
        if replay is not None:
            return replay
        source_id = cast(str, command["source_id"])
        if identity.command_type == "SUBMIT_FOR_REVIEW":
            record = self._schedule_repository.get_record(source_id)
            if record is None:
                reject_command(
                    ScheduleCommandFailure.SOURCE_NOT_FOUND,
                    field="command.source_id",
                    message="does not identify a ScheduleVersion in this plane",
                )
            return self._submit_for_review(command, problem, context, record)
        source = self._schedule_repository.get(source_id)
        if source is None:
            reject_command(
                ScheduleCommandFailure.SOURCE_NOT_FOUND,
                field="command.source_id",
                message="does not identify a ScheduleVersion in this plane",
            )
        prepared = prepare_schedule_command(
            source,
            problem,
            command,
            context,
            data_plane=self._data_plane,
        )
        report = self._fresh_validate(
            prepared.problem,
            prepared.validator_candidate,
        )
        documents = build_schedule_command_documents(prepared, report)
        try:
            with self._transaction_factory() as connection:
                schedule_write = self._schedule_repository.put_in_transaction(
                    connection, documents.draft
                )
                if schedule_write.document != documents.draft:
                    reject_command(
                        ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
                        field="schedule_version",
                        message="stored command result differs from the exact request",
                    )
                audit_write = self._audit_repository.append_in_transaction(
                    connection, documents.audit_event
                )
                if audit_write.document != documents.audit_event:
                    reject_command(
                        ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored command audit differs from the exact request",
                    )
        except ScheduleCommandError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error
        source_reference = _reference(
            documents.audit_event["source_version"], "audit.source_version"
        )
        new_reference = _reference(
            documents.audit_event["new_version"], "audit.new_version"
        )
        validation_reference = _reference(
            cast(Mapping[str, object], documents.draft["lineage"])["validation_report"],
            "schedule_version.lineage.validation_report",
        )
        return ScheduleCommandResult(
            command_id=cast(str, command["command_id"]),
            command_type=identity.command_type,
            request_fingerprint=identity.request_fingerprint,
            source_version=source_reference,
            new_version=new_reference,
            validation_report=validation_reference,
            audit_event_id=identity.audit_event_id,
            correlation_id=cast(str, command["correlation_id"]),
            schedule_replayed=schedule_write.replayed,
            audit_replayed=audit_write.replayed,
        )


__all__ = [
    "AuditCommandRepositoryPort",
    "FormalScheduleValidatorPort",
    "ScheduleCommandResult",
    "ScheduleCommandService",
    "ScheduleVersionCommandRepositoryPort",
    "TransactionFactory",
    "ValidatorFactory",
]
