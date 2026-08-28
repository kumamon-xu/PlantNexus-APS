"""TASK-P4-08 dynamic-replan orchestration and atomic result application."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, cast

from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.domain.execution_contracts import contract_fingerprint
from app.domain.replan_application import (
    ReplanApplicationContext,
    ReplanApplicationError,
    ReplanApplicationFailure,
    build_dynamic_schedule_draft,
    reject_replan_application,
    require_replan_application_authorization,
    require_replan_request_context,
    schedule_content,
    schedule_identity,
    schedule_reference,
)
from app.infrastructure.replan_persistence import (
    ArtifactReference,
    ReplanAttemptReference,
    ReplanAuditAction,
    ReplanAuditRecord,
    ReplanResultReference,
    build_replan_attempt,
    build_replan_audit_record,
    build_replan_result,
)
from app.infrastructure.workspace_persistence import (
    PersistenceFailure,
    WorkspacePersistenceError,
)
from app.planning.policy.contracts import SolveLimitsDocument
from app.planning.problem.builder import build_planning_problem_v2
from app.planning.problem.contracts import (
    DemandPriorityInput,
    ImmutablePlanningProblemV2,
)
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.reporting.change_report import (
    build_change_report,
    kpi_evidence_reference,
)
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanResult,
    LexicographicReplanStrategy,
)
from app.planning.validation.change_report_precheck import validate_change_report
from app.planning.validation.replan_candidate_validator import (
    validate_replan_candidate,
)
from app.snapshots.canonical import ImmutablePlanningSnapshot


type TransactionFactory = Callable[[], AbstractContextManager[Connection]]


class WriteResultPort(Protocol):
    @property
    def document(self) -> dict[str, object]: ...

    @property
    def replayed(self) -> bool: ...


class StoredScheduleVersionPort(Protocol):
    @property
    def document(self) -> dict[str, object]: ...

    @property
    def state_revision(self) -> int: ...


class CurrentPublicationPort(Protocol):
    @property
    def schedule_version_id(self) -> str: ...

    @property
    def content_fingerprint(self) -> str: ...

    @property
    def target(self) -> str: ...


class StoredAppliedResultPort(Protocol):
    @property
    def result(self) -> dict[str, object]: ...

    @property
    def solver_report(self) -> dict[str, object]: ...

    @property
    def validation_report(self) -> dict[str, object]: ...

    @property
    def kpi(self) -> dict[str, object]: ...

    @property
    def change_report(self) -> dict[str, object]: ...


class StoredTerminalResultPort(Protocol):
    @property
    def result(self) -> dict[str, object]: ...

    @property
    def solver_report(self) -> dict[str, object]: ...


class ScheduleVersionRepositoryPort(Protocol):
    def get_record(self, schedule_version_id: str) -> StoredScheduleVersionPort | None: ...

    def get_record_in_transaction(
        self, connection: Connection, schedule_version_id: str
    ) -> StoredScheduleVersionPort | None: ...

    def put_in_transaction(
        self, connection: Connection, document: Mapping[str, object]
    ) -> WriteResultPort: ...


class PublicationRepositoryPort(Protocol):
    def get_current(
        self, *, target: str = "SIMULATION_INTERNAL"
    ) -> CurrentPublicationPort | None: ...

    def get_current_in_transaction(
        self, connection: Connection, *, target: str = "SIMULATION_INTERNAL"
    ) -> CurrentPublicationPort | None: ...


class SnapshotRepositoryPort(Protocol):
    def get_by_id(self, snapshot_id: str) -> ImmutablePlanningSnapshot | None: ...

    def get_by_id_in_transaction(
        self, connection: Connection, snapshot_id: str
    ) -> ImmutablePlanningSnapshot | None: ...


class ReplanRequestRepositoryPort(Protocol):
    def append_in_transaction(
        self, connection: Connection, document: Mapping[str, object]
    ) -> WriteResultPort: ...

    def get_in_transaction(
        self, connection: Connection, request_id: str
    ) -> dict[str, object] | None: ...


class ReplanLineageRepositoryPort(Protocol):
    def append_attempt_in_transaction(
        self, connection: Connection, attempt: ReplanAttemptReference
    ) -> WriteResultPort: ...

    def get_attempt_in_transaction(
        self, connection: Connection, attempt_id: str
    ) -> dict[str, object] | None: ...

    def get_result_for_attempt(
        self, attempt_id: str
    ) -> dict[str, object] | None: ...

    def get_applied_result_for_attempt(
        self, attempt_id: str
    ) -> StoredAppliedResultPort | None: ...

    def get_terminal_result_for_attempt(
        self, attempt_id: str
    ) -> StoredTerminalResultPort | None: ...

    def append_result_in_transaction(
        self, connection: Connection, result: ReplanResultReference
    ) -> WriteResultPort: ...

    def append_applied_result_in_transaction(
        self,
        connection: Connection,
        *,
        result: ReplanResultReference,
        solver_report: Mapping[str, object],
        validation_report: Mapping[str, object],
        kpi: Mapping[str, object],
        change_report: Mapping[str, object],
    ) -> WriteResultPort: ...

    def append_terminal_result_in_transaction(
        self,
        connection: Connection,
        *,
        result: ReplanResultReference,
        solver_report: Mapping[str, object],
    ) -> WriteResultPort: ...


class ReplanAuditRepositoryPort(Protocol):
    def append_in_transaction(
        self, connection: Connection, record: ReplanAuditRecord
    ) -> WriteResultPort: ...


class ReplanStrategyPort(Protocol):
    def solve(
        self,
        problem: Mapping[str, object],
        policy: Mapping[str, object],
        limits: SolveLimitsDocument,
        *,
        base_schedule: Mapping[str, object],
        effective_locks: Mapping[str, object],
        replan_request: Mapping[str, object],
        planning_run_id: str,
        code_commit: str,
    ) -> LexicographicReplanResult: ...


@dataclass(frozen=True, slots=True)
class ReplanApplicationInput:
    """Frozen artifacts/config needed to rebuild the exact request Problem."""

    request: Mapping[str, object]
    priority_facts: Mapping[str, DemandPriorityInput]
    problem_builder_version: str
    tick_seconds: int
    horizon_start_utc: str
    horizon_end_utc: str
    policy: Mapping[str, object]
    limits: SolveLimitsDocument
    before_kpi: Mapping[str, object]
    after_kpi: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ReplanApplicationResult:
    """Stable logical result returned for first commit and exact replay."""

    request: dict[str, object]
    attempt: dict[str, object]
    result: dict[str, object]
    schedule_version: dict[str, object] | None
    solver_report: dict[str, object] | None
    validation_report: dict[str, object] | None
    kpi: dict[str, object] | None
    change_report: dict[str, object] | None
    exact_replay: bool
    request_replayed: bool
    attempt_replayed: bool
    result_replayed: bool
    audit_replayed: bool


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field=field,
            message="must be an array",
        )
    return cast(Sequence[object], value)


def _persistence_failure(error: WorkspacePersistenceError) -> ReplanApplicationError:
    reason = {
        PersistenceFailure.DATA_PLANE_MISMATCH: ReplanApplicationFailure.DATA_PLANE_MISMATCH,
        PersistenceFailure.IDEMPOTENCY_CONFLICT: ReplanApplicationFailure.IDEMPOTENCY_CONFLICT,
        PersistenceFailure.IDENTITY_CONFLICT: ReplanApplicationFailure.LINEAGE_MISMATCH,
        PersistenceFailure.STATE_CONFLICT: ReplanApplicationFailure.STATE_CONFLICT,
    }.get(error.reason, ReplanApplicationFailure.PERSISTENCE_FAILED)
    return ReplanApplicationError(
        reason,
        field=error.field,
        message="durable Replan persistence rejected the operation",
    )


def _artifact(
    *, document_version: str, artifact_id: object, fingerprint: object
) -> ArtifactReference:
    if not isinstance(artifact_id, str) or not isinstance(fingerprint, str):
        reject_replan_application(
            ReplanApplicationFailure.INVALID_INPUT,
            field="artifact_reference",
            message="artifact identity is invalid",
        )
    return ArtifactReference(
        document_version=document_version,
        artifact_id=artifact_id,
        fingerprint=fingerprint,
    )


def _reference_matches(
    actual: Mapping[str, object], expected: Mapping[str, object], field: str
) -> None:
    if dict(actual) != dict(expected):
        reject_replan_application(
            ReplanApplicationFailure.LINEAGE_MISMATCH,
            field=field,
            message="immutable artifact reference differs",
        )


def _effective_freeze_evidence(
    projection: Mapping[str, object],
) -> dict[str, object]:
    freeze = dict(_mapping(projection.get("freeze_resolution"), "freeze_resolution"))
    lock_ids: set[str] = set()
    for section in (
        "explicit_hard_locks",
        "freeze_derived_hard_locks",
        "soft_locks",
    ):
        for raw in _sequence(projection.get(section), f"projection.{section}"):
            protection = _mapping(raw, f"projection.{section}[]")
            value = protection.get("reference_id", protection.get("lock_id"))
            if not isinstance(value, str):
                reject_replan_application(
                    ReplanApplicationFailure.LINEAGE_MISMATCH,
                    field=f"projection.{section}.reference_id",
                    message="effective lock identity is absent",
                )
            lock_ids.add(value)
    freeze["effective_lock_ids"] = sorted(lock_ids)
    return freeze


def _change_evidence(
    *,
    request: Mapping[str, object],
    base_schedule: Mapping[str, object],
    projection: Mapping[str, object],
    candidate: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    completed: dict[str, object] = {}
    reasons: dict[str, object] = {}
    for raw in _sequence(
        projection.get("completed_protections"), "completed_protections"
    ):
        protection = _mapping(raw, "completed_protections[]")
        operation_id = cast(str, protection.get("operation_id"))
        fact_id = cast(str, protection.get("reference_id"))
        reference = {
            "document_version": "execution-fact.v1",
            "artifact_id": fact_id,
            "fingerprint": contract_fingerprint(protection),
        }
        completed[operation_id] = reference
        reasons[operation_id] = [
            {
                "reason_code": "REMOVED_BY_COMPLETION_FACT",
                "evidence_refs": [reference],
            }
        ]

    base_content = _mapping(base_schedule.get("content"), "base_schedule.content")
    base_ids = {
        cast(str, _mapping(value, "base_assignment").get("operation_id"))
        for value in _sequence(base_content.get("assignments"), "base.assignments")
    }
    candidate_ids = {
        cast(str, _mapping(value, "candidate_assignment").get("operation_id"))
        for value in _sequence(candidate.get("assignments"), "candidate.assignments")
    }
    base_reference = {
        "document_version": cast(str, base_schedule["schedule_version_version"]),
        "artifact_id": cast(str, base_schedule["schedule_version_id"]),
        "fingerprint": cast(str, base_schedule["content_fingerprint"]),
    }
    stream = _mapping(request.get("event_stream"), "request.event_stream")
    event_ids = list(_sequence(stream.get("event_ids"), "event_stream.event_ids"))
    fingerprints = list(
        _sequence(stream.get("event_fingerprints"), "event_stream.event_fingerprints")
    )
    trigger_ids = set(_sequence(request.get("trigger_event_ids"), "trigger_event_ids"))
    trigger_refs = [
        {
            "document_version": "execution-event.v1",
            "artifact_id": event_id,
            "fingerprint": fingerprint,
        }
        for event_id, fingerprint in zip(event_ids, fingerprints, strict=True)
        if event_id in trigger_ids
    ]
    if not trigger_refs:
        trigger_refs = [dict(_mapping(request.get("new_snapshot"), "new_snapshot"))]
    for operation_id in sorted(base_ids & candidate_ids):
        base_assignment = next(
            _mapping(value, "base_assignment")
            for value in _sequence(base_content.get("assignments"), "base.assignments")
            if _mapping(value, "base_assignment").get("operation_id") == operation_id
        )
        candidate_assignment = next(
            _mapping(value, "candidate_assignment")
            for value in _sequence(candidate.get("assignments"), "candidate.assignments")
            if _mapping(value, "candidate_assignment").get("operation_id")
            == operation_id
        )
        before = tuple(base_assignment.get(field) for field in ("resource_id", "start_at_utc", "end_at_utc"))
        after = tuple(candidate_assignment.get(field) for field in ("resource_id", "start_at_utc", "end_at_utc"))
        if before == after:
            reasons[operation_id] = [
                {"reason_code": "NO_CHANGE", "evidence_refs": [base_reference]}
            ]
    for operation_id in sorted(candidate_ids - base_ids):
        reasons[operation_id] = [
            {"reason_code": "TRIGGER_EVENT", "evidence_refs": trigger_refs}
        ]
    return completed, reasons


class ReplanApplicationService:
    """Own request/attempt orchestration and the atomic P4 result boundary."""

    def __init__(
        self,
        *,
        transaction_factory: TransactionFactory,
        schedule_repository: ScheduleVersionRepositoryPort,
        publication_repository: PublicationRepositoryPort,
        snapshot_repository: SnapshotRepositoryPort,
        request_repository: ReplanRequestRepositoryPort,
        lineage_repository: ReplanLineageRepositoryPort,
        audit_repository: ReplanAuditRepositoryPort,
        strategy: ReplanStrategyPort | None = None,
    ) -> None:
        self._transaction_factory = transaction_factory
        self._schedule_repository = schedule_repository
        self._publication_repository = publication_repository
        self._snapshot_repository = snapshot_repository
        self._request_repository = request_repository
        self._lineage_repository = lineage_repository
        self._audit_repository = audit_repository
        self._strategy = LexicographicReplanStrategy() if strategy is None else strategy

    def _attempt(
        self, request: Mapping[str, object], context: ReplanApplicationContext
    ) -> ReplanAttemptReference:
        request_id = cast(str, request["request_id"])
        scope = f"SIMULATION/REPLAN/{request_id}"
        return build_replan_attempt(
            request_id=request_id,
            request_fingerprint=cast(str, request["request_fingerprint"]),
            planning_run_id=context.planning_run_id,
            attempt_number=context.attempt_number,
            idempotency_scope=scope,
            idempotency_key_reference=context.idempotency_key_reference,
            correlation_id=context.correlation_id,
            created_at_utc=context.occurred_at_utc,
        )

    def _audit(
        self,
        *,
        action: ReplanAuditAction,
        aggregate_type: str,
        aggregate_id: str,
        scope: str,
        request_fingerprint: str,
        context: ReplanApplicationContext,
    ) -> ReplanAuditRecord:
        return build_replan_audit_record(
            action=action,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            correlation_id=context.correlation_id,
            idempotency_scope=scope,
            idempotency_key_reference=context.idempotency_key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=context.occurred_at_utc,
        )

    def _persist_intent(
        self,
        *,
        request: Mapping[str, object],
        attempt: ReplanAttemptReference,
        context: ReplanApplicationContext,
    ) -> tuple[WriteResultPort, WriteResultPort, bool]:
        request_id = cast(str, request["request_id"])
        request_fingerprint = cast(str, request["request_fingerprint"])
        request_audit = self._audit(
            action=ReplanAuditAction.REPLAN_REQUEST_APPENDED,
            aggregate_type="REPLAN_REQUEST",
            aggregate_id=request_id,
            scope=f"{attempt.idempotency_scope}/REQUEST",
            request_fingerprint=request_fingerprint,
            context=context,
        )
        attempt_audit = self._audit(
            action=ReplanAuditAction.REPLAN_ATTEMPT_LINKED,
            aggregate_type="REPLAN_ATTEMPT",
            aggregate_id=attempt.attempt_id,
            scope=f"{attempt.idempotency_scope}/ATTEMPT",
            request_fingerprint=request_fingerprint,
            context=context,
        )
        try:
            with self._transaction_factory() as connection:
                request_write = self._request_repository.append_in_transaction(
                    connection, request
                )
                attempt_write = self._lineage_repository.append_attempt_in_transaction(
                    connection, attempt
                )
                request_audit_write = self._audit_repository.append_in_transaction(
                    connection, request_audit
                )
                attempt_audit_write = self._audit_repository.append_in_transaction(
                    connection, attempt_audit
                )
        except WorkspacePersistenceError as error:
            raise _persistence_failure(error) from error
        except SQLAlchemyError as error:
            raise ReplanApplicationError(
                ReplanApplicationFailure.PERSISTENCE_FAILED,
                field="intent.transaction",
                message="durable Replan intent transaction failed",
            ) from error
        return (
            request_write,
            attempt_write,
            request_audit_write.replayed and attempt_audit_write.replayed,
        )

    def _stored_result(
        self,
        *,
        request: Mapping[str, object],
        attempt: ReplanAttemptReference,
        request_write: WriteResultPort,
        attempt_write: WriteResultPort,
        audit_replayed: bool,
    ) -> ReplanApplicationResult | None:
        try:
            result = self._lineage_repository.get_result_for_attempt(attempt.attempt_id)
        except WorkspacePersistenceError as error:
            raise _persistence_failure(error) from error
        if result is None:
            return None
        if (
            result.get("request_id") != request.get("request_id")
            or result.get("request_fingerprint") != request.get("request_fingerprint")
            or result.get("planning_run_id") != attempt.planning_run_id
        ):
            reject_replan_application(
                ReplanApplicationFailure.IDEMPOTENCY_CONFLICT,
                field="stored.result",
                message="stored result belongs to different immutable input",
            )
        if result.get("planning_run_terminal_state") != "COMPLETED":
            try:
                terminal = self._lineage_repository.get_terminal_result_for_attempt(
                    attempt.attempt_id
                )
            except WorkspacePersistenceError as error:
                raise _persistence_failure(error) from error
            if terminal is None:
                reject_replan_application(
                    ReplanApplicationFailure.PERSISTENCE_FAILED,
                    field="stored.terminal_result",
                    message="terminal result has no immutable SolverReport envelope",
                )
            return ReplanApplicationResult(
                request=dict(request_write.document),
                attempt=dict(attempt_write.document),
                result=dict(terminal.result),
                schedule_version=None,
                solver_report=dict(terminal.solver_report),
                validation_report=None,
                kpi=None,
                change_report=None,
                exact_replay=True,
                request_replayed=request_write.replayed,
                attempt_replayed=attempt_write.replayed,
                result_replayed=True,
                audit_replayed=audit_replayed,
            )
        try:
            applied = self._lineage_repository.get_applied_result_for_attempt(
                attempt.attempt_id
            )
        except WorkspacePersistenceError as error:
            raise _persistence_failure(error) from error
        if applied is None:
            reject_replan_application(
                ReplanApplicationFailure.PERSISTENCE_FAILED,
                field="stored.applied_result",
                message="COMPLETED result has no immutable artifact envelope",
            )
        schedule_ref = _mapping(
            applied.result.get("new_schedule_version"), "new_schedule_version"
        )
        schedule = self._schedule_repository.get_record(
            cast(str, schedule_ref["artifact_id"])
        )
        if schedule is None or schedule.document.get("content_fingerprint") != (
            schedule_ref.get("fingerprint")
        ):
            reject_replan_application(
                ReplanApplicationFailure.PERSISTENCE_FAILED,
                field="stored.schedule_version",
                message="applied DRAFT is absent or failed exact reference verification",
            )
        return ReplanApplicationResult(
            request=dict(request_write.document),
            attempt=dict(attempt_write.document),
            result=dict(applied.result),
            schedule_version=dict(schedule.document),
            solver_report=dict(applied.solver_report),
            validation_report=dict(applied.validation_report),
            kpi=dict(applied.kpi),
            change_report=dict(applied.change_report),
            exact_replay=True,
            request_replayed=request_write.replayed,
            attempt_replayed=attempt_write.replayed,
            result_replayed=True,
            audit_replayed=audit_replayed,
        )

    def _current_base(self, request: Mapping[str, object]) -> dict[str, object]:
        base_reference = _mapping(
            request.get("base_schedule_version"), "base_schedule_version"
        )
        current = self._publication_repository.get_current()
        if (
            current is None
            or current.target != "SIMULATION_INTERNAL"
            or current.schedule_version_id != base_reference.get("schedule_version_id")
            or current.content_fingerprint != base_reference.get("content_fingerprint")
        ):
            reject_replan_application(
                ReplanApplicationFailure.STATE_CONFLICT,
                field="current_publication",
                message="ReplanRequest base is not the exact current PUBLISHED reference",
            )
        stored = self._schedule_repository.get_record(current.schedule_version_id)
        if stored is None:
            reject_replan_application(
                ReplanApplicationFailure.STATE_CONFLICT,
                field="base_schedule_version",
                message="current PUBLISHED base is absent",
            )
        base = dict(stored.document)
        expected = {
            "schedule_version_version": base.get("schedule_version_version"),
            "schedule_version_id": base.get("schedule_version_id"),
            "state": base.get("state"),
            "content_fingerprint": base.get("content_fingerprint"),
        }
        _reference_matches(base_reference, expected, "base_schedule_version")
        if base.get("state") != "PUBLISHED":
            reject_replan_application(
                ReplanApplicationFailure.STATE_CONFLICT,
                field="base_schedule_version.state",
                message="base ScheduleVersion is not PUBLISHED",
            )
        return base

    def _problem(
        self, input_: ReplanApplicationInput
    ) -> tuple[ImmutablePlanningSnapshot, ImmutablePlanningProblemV2]:
        snapshot_reference = _mapping(
            input_.request.get("new_snapshot"), "request.new_snapshot"
        )
        snapshot = self._snapshot_repository.get_by_id(
            cast(str, snapshot_reference.get("artifact_id"))
        )
        if snapshot is None:
            reject_replan_application(
                ReplanApplicationFailure.LINEAGE_MISMATCH,
                field="request.new_snapshot",
                message="referenced immutable Snapshot is absent",
            )
        _reference_matches(
            snapshot_reference,
            {
                "document_version": "planning-snapshot.v2",
                "artifact_id": snapshot.snapshot_id,
                "fingerprint": snapshot.snapshot_hash,
            },
            "request.new_snapshot",
        )
        problem = build_planning_problem_v2(
            snapshot,
            priority_facts=input_.priority_facts,
            problem_builder_version=input_.problem_builder_version,
            tick_seconds=input_.tick_seconds,
            horizon_start_utc=input_.horizon_start_utc,
            horizon_end_utc=input_.horizon_end_utc,
        )
        problem_reference = _mapping(
            input_.request.get("new_problem"), "request.new_problem"
        )
        _reference_matches(
            problem_reference,
            {
                "document_version": "planning-problem.v2",
                "artifact_id": "planning-problem-v2-"
                + problem.problem_hash.removeprefix("sha256:"),
                "fingerprint": problem.problem_hash,
            },
            "request.new_problem",
        )
        return snapshot, problem

    def _validate_base_lineage(
        self, base: Mapping[str, object], request: Mapping[str, object]
    ) -> None:
        lineage = _mapping(base.get("lineage"), "base_schedule.lineage")
        _reference_matches(
            _mapping(request.get("base_snapshot"), "request.base_snapshot"),
            _mapping(lineage.get("snapshot"), "base_schedule.lineage.snapshot"),
            "request.base_snapshot",
        )
        _reference_matches(
            _mapping(request.get("base_problem"), "request.base_problem"),
            _mapping(lineage.get("problem"), "base_schedule.lineage.problem"),
            "request.base_problem",
        )

    def _terminal_result(
        self,
        *,
        attempt: ReplanAttemptReference,
        solver_report: Mapping[str, object],
        terminal_state: str,
        context: ReplanApplicationContext,
    ) -> ReplanResultReference:
        solver_reference = _artifact(
            document_version="solver-report.v2",
            artifact_id=solver_report.get("report_id"),
            fingerprint=solver_report.get("report_fingerprint"),
        )
        return build_replan_result(
            attempt=attempt,
            planning_run_terminal_state=terminal_state,
            solver_report=solver_reference,
            validation_report=None,
            new_schedule_version=None,
            change_report=None,
            correlation_id=context.correlation_id,
            finished_at_utc=context.occurred_at_utc,
        )

    def execute(
        self,
        input_: ReplanApplicationInput,
        context: ReplanApplicationContext,
    ) -> ReplanApplicationResult:
        """Execute one request without auto-review, publish, export, or Simulation."""

        require_replan_application_authorization(context)
        request = dict(input_.request)
        require_replan_request_context(request, context)
        attempt = self._attempt(request, context)
        request_write, attempt_write, intent_audit_replayed = self._persist_intent(
            request=request, attempt=attempt, context=context
        )
        replay = self._stored_result(
            request=request,
            attempt=attempt,
            request_write=request_write,
            attempt_write=attempt_write,
            audit_replayed=intent_audit_replayed,
        )
        if replay is not None:
            return replay

        base = self._current_base(request)
        self._validate_base_lineage(base, request)
        snapshot, problem = self._problem(input_)
        projection = project_effective_locks(
            snapshot=snapshot,
            problem=problem,
            base_schedule=base,
            policy=input_.policy,
        ).document
        solve = self._strategy.solve(
            problem.document,
            input_.policy,
            input_.limits,
            base_schedule=base,
            effective_locks=projection,
            replan_request=request,
            planning_run_id=context.planning_run_id,
            code_commit=context.code_commit,
        )
        solver_report = dict(solve.solver_report)
        candidate_value = solver_report.get("candidate")
        outcome = _mapping(
            solver_report.get("planning_run_outcome"),
            "solver_report.planning_run_outcome",
        )
        if candidate_value is None:
            terminal_state = cast(str, outcome.get("state"))
            result_value = self._terminal_result(
                attempt=attempt,
                solver_report=solver_report,
                terminal_state=terminal_state,
                context=context,
            )
            audit = self._audit(
                action=ReplanAuditAction.REPLAN_RESULT_APPENDED,
                aggregate_type="REPLAN_RESULT",
                aggregate_id=result_value.result_id,
                scope=f"{attempt.idempotency_scope}/RESULT",
                request_fingerprint=attempt.request_fingerprint,
                context=context,
            )
            try:
                with self._transaction_factory() as connection:
                    result_write = (
                        self._lineage_repository.append_terminal_result_in_transaction(
                            connection,
                            result=result_value,
                            solver_report=solver_report,
                        )
                    )
                    audit_write = self._audit_repository.append_in_transaction(
                        connection, audit
                    )
            except WorkspacePersistenceError as error:
                raise _persistence_failure(error) from error
            except SQLAlchemyError as error:
                raise ReplanApplicationError(
                    ReplanApplicationFailure.PERSISTENCE_FAILED,
                    field="terminal_result.transaction",
                    message="durable terminal result transaction failed",
                ) from error
            return ReplanApplicationResult(
                request=dict(request_write.document),
                attempt=dict(attempt_write.document),
                result=dict(result_write.document),
                schedule_version=None,
                solver_report=solver_report,
                validation_report=None,
                kpi=None,
                change_report=None,
                exact_replay=False,
                request_replayed=request_write.replayed,
                attempt_replayed=attempt_write.replayed,
                result_replayed=result_write.replayed,
                audit_replayed=audit_write.replayed,
            )

        candidate = _mapping(candidate_value, "solver_report.candidate")
        if not solve.validation_reports:
            reject_replan_application(
                ReplanApplicationFailure.VALIDATION_FAILED,
                field="solver.validation_reports",
                message="solver produced no candidate validation evidence",
            )
        declared_objectives = _mapping(
            solve.validation_reports[-1].get("objective_values"),
            "solver.validation_reports[-1].objective_values",
        )
        base_content = _mapping(base.get("content"), "base_schedule.content")
        base_assignments = _sequence(
            base_content.get("assignments"), "base_schedule.content.assignments"
        )
        fresh_validation = validate_replan_candidate(
            problem=problem.document,
            base_assignments=base_assignments,
            effective_locks=projection,
            candidate=candidate,
            objective_evidence=declared_objectives,
        )
        if fresh_validation.get("status") != "PASS" or fresh_validation.get(
            "hard_violation_count"
        ) != 0:
            reject_replan_application(
                ReplanApplicationFailure.VALIDATION_FAILED,
                field="fresh_validation",
                message="fresh application validation rejected the candidate",
            )
        formal_validation = _mapping(
            fresh_validation.get("formal_validation"),
            "fresh_validation.formal_validation",
        )
        after_reference, after_tardiness, after_makespan = kpi_evidence_reference(
            input_.after_kpi, field="after_kpi"
        )
        measured = _mapping(
            fresh_validation.get("objective_values"),
            "fresh_validation.objective_values",
        )
        if (
            after_tardiness != measured.get("delivery")
            or after_makespan != measured.get("makespan")
        ):
            reject_replan_application(
                ReplanApplicationFailure.LINEAGE_MISMATCH,
                field="after_kpi",
                message="after KPI differs from fresh candidate objectives",
            )
        before_reference, _, _ = kpi_evidence_reference(
            input_.before_kpi, field="before_kpi"
        )
        base_lineage = _mapping(base.get("lineage"), "base_schedule.lineage")
        _reference_matches(
            _mapping(base_lineage.get("kpi"), "base_schedule.lineage.kpi"),
            before_reference,
            "before_kpi",
        )

        content = schedule_content(candidate=candidate, effective_locks=projection)
        applied_assignments = _sequence(
            content.get("assignments"), "schedule_content.assignments"
        )
        content_fingerprint = contract_fingerprint(content)
        schedule_version_id = schedule_identity(
            request_fingerprint=cast(str, request["request_fingerprint"]),
            context=context,
        )
        new_schedule_reference = schedule_reference(
            schedule_version_id=schedule_version_id,
            content_fingerprint=content_fingerprint,
        )
        validation_fingerprint = contract_fingerprint(formal_validation)
        validation_reference = {
            "document_version": "validation-report.v2",
            "artifact_id": "validation-report-"
            + validation_fingerprint.removeprefix("sha256:"),
            "fingerprint": validation_fingerprint,
        }
        solver_reference = {
            "document_version": "solver-report.v2",
            "artifact_id": solver_report["report_id"],
            "fingerprint": solver_report["report_fingerprint"],
        }
        stream = _mapping(request.get("event_stream"), "request.event_stream")
        change_context = {
            "environment": context.environment,
            "synthetic_provenance": request["synthetic_provenance"],
            "base_schedule_version": request["base_schedule_version"],
            "new_schedule_version": new_schedule_reference,
            "lineage": {
                "base_snapshot": request["base_snapshot"],
                "base_problem": request["base_problem"],
                "new_snapshot": request["new_snapshot"],
                "new_problem": request["new_problem"],
                "event_stream_fingerprint": stream["stream_fingerprint"],
                "fact_checkpoint": stream["fact_checkpoint"],
                "replan_request": {
                    "replan_request_version": "replan-request.v1",
                    "request_id": request["request_id"],
                    "request_fingerprint": request["request_fingerprint"],
                },
                "planning_run_id": context.planning_run_id,
                "policy": request["planning_policy"],
                "limits": request["solve_limits"],
                "solver_report": solver_reference,
                "validation_report": validation_reference,
            },
            "freeze_evidence": _effective_freeze_evidence(projection),
            "generated_at_utc": context.occurred_at_utc,
            "correlation_id": context.correlation_id,
        }
        removed_by_fact, reasons_by_operation = _change_evidence(
            request=request,
            base_schedule=base,
            projection=projection,
            candidate=candidate,
        )
        active_ids = cast(
            list[str], list(_sequence(projection.get("new_active_operation_ids"), "active_ids"))
        )
        soft_locks = _sequence(projection.get("soft_locks"), "soft_locks")
        change_value = build_change_report(
            context=change_context,
            base_assignments=base_assignments,
            new_assignments=applied_assignments,
            active_operation_ids=active_ids,
            active_soft_locks=soft_locks,
            removed_by_fact=removed_by_fact,
            reasons_by_operation=reasons_by_operation,
            before_kpi=input_.before_kpi,
            after_kpi=input_.after_kpi,
        )
        change_report = change_value.document
        precheck = validate_change_report(
            context=change_context,
            base_assignments=base_assignments,
            new_assignments=applied_assignments,
            active_operation_ids=active_ids,
            active_soft_locks=soft_locks,
            removed_by_fact=removed_by_fact,
            reasons_by_operation=reasons_by_operation,
            before_kpi=input_.before_kpi,
            after_kpi=input_.after_kpi,
            report=change_report,
        )
        stability = _mapping(
            measured.get("stability"), "fresh_validation.objective_values.stability"
        )
        expected_vector = [
            stability["soft_lock_violations"],
            stability["changed_existing_operations"],
            stability["resource_changes"],
            stability["absolute_start_shift_seconds"],
        ]
        if precheck.get("status") != "PASS" or precheck.get(
            "objective_vector"
        ) != expected_vector:
            reject_replan_application(
                ReplanApplicationFailure.CHANGE_REPORT_FAILED,
                field="change_report.precheck",
                message="independent ChangeReport precheck rejected the result",
            )
        draft = build_dynamic_schedule_draft(
            context=context,
            base_schedule=base,
            request=request,
            candidate=candidate,
            formal_validation=formal_validation,
            kpi=input_.after_kpi,
            solver_report=solver_report,
            change_report=change_report,
            effective_locks=projection,
        )
        if draft.kpi_reference != after_reference:
            reject_replan_application(
                ReplanApplicationFailure.LINEAGE_MISMATCH,
                field="schedule_version.lineage.kpi",
                message="DRAFT KPI reference differs from ChangeReport after KPI",
            )

        result_value = build_replan_result(
            attempt=attempt,
            planning_run_terminal_state="COMPLETED",
            solver_report=_artifact(
                document_version="solver-report.v2",
                artifact_id=draft.solver_reference["artifact_id"],
                fingerprint=draft.solver_reference["fingerprint"],
            ),
            validation_report=_artifact(
                document_version="validation-report.v2",
                artifact_id=draft.validation_reference["artifact_id"],
                fingerprint=draft.validation_reference["fingerprint"],
            ),
            new_schedule_version=_artifact(
                document_version="schedule-version.v2",
                artifact_id=draft.schedule_reference["schedule_version_id"],
                fingerprint=draft.schedule_reference["content_fingerprint"],
            ),
            change_report=_artifact(
                document_version="change-report.v1",
                artifact_id=draft.change_report_reference["report_id"],
                fingerprint=draft.change_report_reference["report_fingerprint"],
            ),
            correlation_id=context.correlation_id,
            finished_at_utc=context.occurred_at_utc,
        )
        result_audit = self._audit(
            action=ReplanAuditAction.REPLAN_RESULT_APPENDED,
            aggregate_type="REPLAN_RESULT",
            aggregate_id=result_value.result_id,
            scope=f"{attempt.idempotency_scope}/RESULT",
            request_fingerprint=attempt.request_fingerprint,
            context=context,
        )

        try:
            with self._transaction_factory() as connection:
                current = self._publication_repository.get_current_in_transaction(
                    connection
                )
                if (
                    current is None
                    or current.schedule_version_id != base["schedule_version_id"]
                    or current.content_fingerprint != base["content_fingerprint"]
                ):
                    reject_replan_application(
                        ReplanApplicationFailure.STATE_CONFLICT,
                        field="current_publication",
                        message="current PUBLISHED reference changed before apply",
                    )
                stored_base = self._schedule_repository.get_record_in_transaction(
                    connection, cast(str, base["schedule_version_id"])
                )
                if stored_base is None or stored_base.document != base:
                    reject_replan_application(
                        ReplanApplicationFailure.STATE_CONFLICT,
                        field="base_schedule_version",
                        message="base PUBLISHED carrier changed before apply",
                    )
                stored_request = self._request_repository.get_in_transaction(
                    connection, cast(str, request["request_id"])
                )
                stored_attempt = self._lineage_repository.get_attempt_in_transaction(
                    connection, attempt.attempt_id
                )
                if stored_request != request or stored_attempt != attempt.as_document():
                    reject_replan_application(
                        ReplanApplicationFailure.LINEAGE_MISMATCH,
                        field="request/attempt",
                        message="durable result lineage changed before apply",
                    )
                stored_snapshot = self._snapshot_repository.get_by_id_in_transaction(
                    connection, snapshot.snapshot_id
                )
                if stored_snapshot is None or stored_snapshot.canonical_bytes != (
                    snapshot.canonical_bytes
                ):
                    reject_replan_application(
                        ReplanApplicationFailure.LINEAGE_MISMATCH,
                        field="new_snapshot",
                        message="immutable Snapshot changed before apply",
                    )
                rebuilt = build_planning_problem_v2(
                    stored_snapshot,
                    priority_facts=input_.priority_facts,
                    problem_builder_version=input_.problem_builder_version,
                    tick_seconds=input_.tick_seconds,
                    horizon_start_utc=input_.horizon_start_utc,
                    horizon_end_utc=input_.horizon_end_utc,
                )
                if rebuilt.canonical_bytes != problem.canonical_bytes:
                    reject_replan_application(
                        ReplanApplicationFailure.LINEAGE_MISMATCH,
                        field="new_problem",
                        message="deterministic Problem changed before apply",
                    )
                schedule_write = self._schedule_repository.put_in_transaction(
                    connection, draft.document
                )
                result_write = (
                    self._lineage_repository.append_applied_result_in_transaction(
                        connection,
                        result=result_value,
                        solver_report=solver_report,
                        validation_report=fresh_validation,
                        kpi=input_.after_kpi,
                        change_report=change_report,
                    )
                )
                audit_write = self._audit_repository.append_in_transaction(
                    connection, result_audit
                )
        except ReplanApplicationError:
            raise
        except WorkspacePersistenceError as error:
            raise _persistence_failure(error) from error
        except SQLAlchemyError as error:
            raise ReplanApplicationError(
                ReplanApplicationFailure.PERSISTENCE_FAILED,
                field="result_application.transaction",
                message="atomic result application transaction failed",
            ) from error

        return ReplanApplicationResult(
            request=dict(request_write.document),
            attempt=dict(attempt_write.document),
            result=dict(result_write.document),
            schedule_version=dict(schedule_write.document),
            solver_report=solver_report,
            validation_report=dict(fresh_validation),
            kpi=dict(input_.after_kpi),
            change_report=change_report,
            exact_replay=False,
            request_replayed=request_write.replayed,
            attempt_replayed=attempt_write.replayed,
            result_replayed=result_write.replayed,
            audit_replayed=audit_write.replayed,
        )


__all__ = [
    "ReplanApplicationInput",
    "ReplanApplicationResult",
    "ReplanApplicationService",
]
