"""Atomic P3-04 validated-output to reviewable ScheduleVersion use case."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from app.domain.schedule_version import (
    ScheduleVersionCreationContext,
    ScheduleVersionLifecycleError,
    ScheduleVersionLifecycleFailure,
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
    reject_lifecycle,
)
from app.planning.reporting.kpi import build_kpi_v2
from app.planning.reporting.solver_report import (
    ReportingContractError,
    ReportingContractErrorCode,
)


class DocumentWriteResultPort(Protocol):
    @property
    def document(self) -> dict[str, object]: ...

    @property
    def replayed(self) -> bool: ...


class StateWriteResultPort(Protocol):
    @property
    def document(self) -> dict[str, object]: ...

    @property
    def state_revision(self) -> int: ...


class ScheduleVersionRepositoryPort(Protocol):
    def put_in_transaction(
        self, connection: Any, document: Mapping[str, object]
    ) -> DocumentWriteResultPort: ...

    def transition_in_transaction(
        self,
        connection: Any,
        *,
        schedule_version_id: str,
        expected_state: str,
        expected_state_revision: int,
        candidate_document: Mapping[str, object],
    ) -> StateWriteResultPort: ...


class AuditRepositoryPort(Protocol):
    def append_in_transaction(
        self, connection: Any, document: Mapping[str, object]
    ) -> DocumentWriteResultPort: ...


type TransactionFactory = Callable[[], AbstractContextManager[Any]]


@dataclass(frozen=True, slots=True)
class ScheduleVersionLifecycleResult:
    """The committed READY version and its exact append-only audit evidence."""

    schedule_version: dict[str, object]
    audit_event: dict[str, object]
    schedule_version_id: str
    audit_event_id: str
    request_fingerprint: str
    validation_fingerprint: str
    kpi_fingerprint: str
    schedule_replayed: bool
    transition_replayed: bool
    audit_replayed: bool
    state_revision: int

    @property
    def exact_replay(self) -> bool:
        return (
            self.schedule_replayed and self.transition_replayed and self.audit_replayed
        )


def _reporting_failure(error: ReportingContractError) -> ScheduleVersionLifecycleError:
    mapping = {
        ReportingContractErrorCode.VALIDATION_FAILED: (
            ScheduleVersionLifecycleFailure.VALIDATION_FAILED
        ),
        ReportingContractErrorCode.MIXED_LINEAGE: (
            ScheduleVersionLifecycleFailure.MIXED_LINEAGE
        ),
    }
    return ScheduleVersionLifecycleError(
        mapping.get(error.code, ScheduleVersionLifecycleFailure.INVALID_INPUT),
        field=error.field,
        message="validated output failed the fresh P2 reporting boundary",
    )


def _persistence_failure(error: Exception) -> ScheduleVersionLifecycleError:
    mapping = {
        "DATA_PLANE_MISMATCH": (ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH),
        "IDENTITY_CONFLICT": (ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT),
        "IDEMPOTENCY_CONFLICT": (ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT),
        "STATE_CONFLICT": ScheduleVersionLifecycleFailure.STATE_CONFLICT,
    }
    raw_reason = getattr(error, "reason", None)
    reason = getattr(raw_reason, "value", raw_reason)
    raw_field = getattr(error, "field", "workspace_transaction")
    field = raw_field if isinstance(raw_field, str) else "workspace_transaction"
    return ScheduleVersionLifecycleError(
        mapping.get(str(reason), ScheduleVersionLifecycleFailure.PERSISTENCE_FAILED),
        field=field,
        message="workspace lifecycle persistence rejected the request",
    )


class ValidatedSolutionToScheduleVersionService:
    """Revalidate P2 evidence, then atomically persist DRAFT→READY plus audit."""

    def __init__(
        self,
        *,
        data_plane: str,
        transaction_factory: TransactionFactory,
        schedule_repository: ScheduleVersionRepositoryPort,
        audit_repository: AuditRepositoryPort,
    ) -> None:
        self._data_plane = data_plane
        self._transaction_factory = transaction_factory
        self._schedule_repository = schedule_repository
        self._audit_repository = audit_repository

    @property
    def data_plane(self) -> str:
        return self._data_plane

    def create_reviewable(
        self,
        output: ValidatedPlanningOutput,
        context: ScheduleVersionCreationContext,
    ) -> ScheduleVersionLifecycleResult:
        """Create one reviewable version without mutating PlanningRun or inputs."""

        try:
            fresh_kpi = build_kpi_v2(
                snapshot=output.snapshot,
                problem=output.problem,
                solution=output.solution,
                solver_report=output.solver_report,
                validation_report=output.validation_report,
                import_quality_report=output.import_quality_report,
            )
        except ReportingContractError as error:
            raise _reporting_failure(error) from error
        if fresh_kpi.document != output.kpi:
            reject_lifecycle(
                ScheduleVersionLifecycleFailure.MIXED_LINEAGE,
                field="kpi",
                message="supplied KPI differs from the fresh validated calculation",
            )

        documents = build_reviewable_schedule_documents(
            output,
            context,
            data_plane=self._data_plane,
        )
        try:
            with self._transaction_factory() as connection:
                creation = self._schedule_repository.put_in_transaction(
                    connection, documents.draft
                )
                stored_state = creation.document.get("state")
                if stored_state == "DRAFT":
                    if creation.document != documents.draft:
                        reject_lifecycle(
                            ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
                            field="schedule_version",
                            message="stored DRAFT differs from the exact request",
                        )
                    transition = self._schedule_repository.transition_in_transaction(
                        connection,
                        schedule_version_id=documents.schedule_version_id,
                        expected_state="DRAFT",
                        expected_state_revision=0,
                        candidate_document=documents.ready_for_review,
                    )
                    final_document = transition.document
                    state_revision = transition.state_revision
                    transition_replayed = False
                elif stored_state == "READY_FOR_REVIEW":
                    if creation.document != documents.ready_for_review:
                        reject_lifecycle(
                            ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
                            field="schedule_version",
                            message="stored READY version differs from the exact request",
                        )
                    final_document = creation.document
                    state_revision = 1
                    transition_replayed = True
                else:
                    reject_lifecycle(
                        ScheduleVersionLifecycleFailure.STATE_CONFLICT,
                        field="schedule_version.state",
                        message="only exact DRAFT or READY replay can be consumed",
                    )

                audit = self._audit_repository.append_in_transaction(
                    connection, documents.audit_event
                )
                if audit.document != documents.audit_event:
                    reject_lifecycle(
                        ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
                        field="audit_event",
                        message="stored audit event differs from the exact request",
                    )
        except ScheduleVersionLifecycleError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize adapter failures
            raise _persistence_failure(error) from error

        return ScheduleVersionLifecycleResult(
            schedule_version=final_document,
            audit_event=audit.document,
            schedule_version_id=documents.schedule_version_id,
            audit_event_id=documents.audit_event_id,
            request_fingerprint=documents.request_fingerprint,
            validation_fingerprint=documents.validation_fingerprint,
            kpi_fingerprint=documents.kpi_fingerprint,
            schedule_replayed=creation.replayed,
            transition_replayed=transition_replayed,
            audit_replayed=audit.replayed,
            state_revision=state_revision,
        )


__all__ = [
    "AuditRepositoryPort",
    "ScheduleVersionRepositoryPort",
    "ScheduleVersionLifecycleResult",
    "TransactionFactory",
    "ValidatedSolutionToScheduleVersionService",
]
