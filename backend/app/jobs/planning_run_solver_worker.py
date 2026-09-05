"""Crash-recoverable P8 PlanningRun Solver Worker application boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import Event, Thread
from typing import Any, Protocol, cast

from app.application.planning_runs import (
    PlanningRunAttemptFailureCommand,
    PlanningRunAttemptStartCommand,
    PlanningRunCommandContext,
    PlanningRunOrchestrationService,
    PlanningRunTransitionCommand,
)
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    runtime_resolution_fingerprint,
)
from app.domain.planning_run import (
    ATTEMPT_TERMINAL_STATUSES,
    PLANNING_RUN_TERMINAL_STATES,
    PlanningRunAttempt,
    PlanningRunAttemptStatus,
    PlanningRunReadModel,
    PlanningRunWorkItem,
)
from app.domain.schedule_version import (
    ScheduleVersionCreationContext,
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
)
from app.domain.types import format_utc_instant, parse_utc_instant
from app.jobs.contracts import JobRecord, JobStatus
from app.jobs.planning_run_worker_contracts import (
    PlanningRunResolvedInputs,
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
    PlanningRunWorkerResult,
    build_worker_result,
    reject_worker,
    verify_worker_result,
)
from app.jobs.planning_run_worker_repository import (
    SqlAlchemyPlanningRunWorkerRepository,
)
from app.planning.contracts import (
    PlanningContractError,
    SolverStatus,
    contract_fingerprint,
    outcome_for_solver_status,
    validate_contract_bundle,
)
from app.planning.reporting.kpi import build_kpi_v2


type JsonObject = dict[str, Any]
Clock = Callable[[], datetime]

_ARTIFACT_FIELDS = (
    "import_quality_report",
    "snapshot",
    "problem",
    "planning_solution",
    "solver_report",
    "validation_report",
    "schedule_version",
)


class PlanningInputResolver(Protocol):
    def resolve(self, work_item: Mapping[str, object]) -> PlanningRunResolvedInputs: ...


class RuntimeResolutionProvider(Protocol):
    def current_resolution(self, planning_run_id: str) -> Mapping[str, object]: ...


class PlanningRunContextProvider(Protocol):
    def context_for(
        self, planning_run_id: str, *, occurred_at_utc: str
    ) -> PlanningRunCommandContext: ...


class SolverResult(Protocol):
    @property
    def solution(self) -> Mapping[str, object]: ...

    @property
    def solver_report(self) -> Mapping[str, object]: ...


class PlanningSolver(Protocol):
    def solve(
        self,
        problem: Mapping[str, object],
        policy: Mapping[str, object],
        limits: Mapping[str, object],
        *,
        planning_run_id: str,
        code_commit: str,
    ) -> SolverResult: ...


class FormalValidator(Protocol):
    def validate(
        self, problem: Mapping[str, object], candidate: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class ScheduleLifecycleResult(Protocol):
    @property
    def schedule_version(self) -> Mapping[str, object]: ...


class ScheduleVersionPublisher(Protocol):
    def create_reviewable(
        self,
        output: ValidatedPlanningOutput,
        context: ScheduleVersionCreationContext,
    ) -> ScheduleLifecycleResult: ...


@dataclass(frozen=True, slots=True)
class WorkerReliabilityPolicy:
    heartbeat_seconds: int = 30
    lease_seconds: int = 120

    def __post_init__(self) -> None:
        if self.heartbeat_seconds < 1:
            raise ValueError("heartbeat_seconds must be positive")
        if self.lease_seconds <= self.heartbeat_seconds:
            raise ValueError("lease_seconds must be longer than heartbeat_seconds")


class WorkerDisposition(StrEnum):
    COMPLETED = "COMPLETED"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    EXACT_REPLAY = "EXACT_REPLAY"


@dataclass(frozen=True, slots=True)
class PlanningRunWorkerExecution:
    job_id: str
    planning_run_id: str
    attempt_id: str
    work_item_id: str
    disposition: WorkerDisposition
    planning_run_state: str
    checkpoint_replayed: bool
    publication_replayed: bool

    def as_document(self) -> JsonObject:
        return {
            "job_id": self.job_id,
            "planning_run_id": self.planning_run_id,
            "attempt_id": self.attempt_id,
            "work_item_id": self.work_item_id,
            "disposition": self.disposition.value,
            "planning_run_state": self.planning_run_state,
            "checkpoint_replayed": self.checkpoint_replayed,
            "publication_replayed": self.publication_replayed,
        }


@dataclass(frozen=True, slots=True)
class PlanningRunWorkerRecovery:
    job_id: str
    planning_run_id: str
    attempt_id: str
    action: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def _reference(
    *, document_version: str, artifact_id: str, fingerprint: str
) -> JsonObject:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": fingerprint,
    }


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_worker(
            PlanningRunWorkerErrorCode.INPUT_MISMATCH,
            field=field,
            message="Expected a server-resolved object",
        )
    return cast(Mapping[str, object], value)


class _HeartbeatGuard:
    """Extend one SQL lease while the blocking Solver owns the work."""

    def __init__(
        self,
        *,
        repository: SqlAlchemyPlanningRunWorkerRepository,
        job_id: str,
        worker_id: str,
        policy: WorkerReliabilityPolicy,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._job_id = job_id
        self._worker_id = worker_id
        self._policy = policy
        self._clock = clock
        self._stop = Event()
        self._failure: PlanningRunWorkerError | None = None
        self._thread = Thread(
            target=self._run,
            name=f"p8-heartbeat-{job_id[:12]}",
            daemon=True,
        )

    def __enter__(self) -> _HeartbeatGuard:
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.wait(self._policy.heartbeat_seconds):
            try:
                self._repository.heartbeat(
                    self._job_id,
                    worker_id=self._worker_id,
                    now=self._clock(),
                    lease_seconds=self._policy.lease_seconds,
                )
            except PlanningRunWorkerError as error:
                self._failure = error
                self._stop.set()

    def beat(self) -> None:
        self.check()
        self._repository.heartbeat(
            self._job_id,
            worker_id=self._worker_id,
            now=self._clock(),
            lease_seconds=self._policy.lease_seconds,
        )

    def check(self) -> None:
        if self._failure is not None:
            raise self._failure

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


class PlanningRunSolverWorker:
    """Consume one immutable work item and reconcile exactly one business result."""

    def __init__(
        self,
        *,
        orchestration: PlanningRunOrchestrationService,
        worker_repository: SqlAlchemyPlanningRunWorkerRepository,
        input_resolver: PlanningInputResolver,
        runtime_provider: RuntimeResolutionProvider,
        context_provider: PlanningRunContextProvider,
        solver: PlanningSolver,
        validator: FormalValidator,
        publisher: ScheduleVersionPublisher,
        policy: WorkerReliabilityPolicy | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self._orchestration = orchestration
        self._worker_repository = worker_repository
        self._input_resolver = input_resolver
        self._runtime_provider = runtime_provider
        self._context_provider = context_provider
        self._solver = solver
        self._validator = validator
        self._publisher = publisher
        self._policy = policy or WorkerReliabilityPolicy()
        self._clock = clock
        if orchestration.data_plane != worker_repository.data_plane:
            raise ValueError("Worker repositories must bind the same data plane")

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("Worker clock must return timezone-aware UTC")
        return value.astimezone(UTC)

    def _context(
        self, planning_run_id: str, *, now: datetime | None = None
    ) -> PlanningRunCommandContext:
        occurred = format_utc_instant(now or self._now())
        try:
            context = self._context_provider.context_for(
                planning_run_id, occurred_at_utc=occurred
            )
        except PlanningRunWorkerError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize composition failure
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_context",
                message="Worker command context resolution failed",
                retryable=True,
            ) from error
        if not isinstance(context, PlanningRunCommandContext):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="worker_context",
                message="Worker command context is invalid",
            )
        if context.data_plane != self._worker_repository.data_plane:
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="worker_context.data_plane",
                message="Worker authority crossed its configured data plane",
            )
        return context

    def _read(self, planning_run_id: str) -> PlanningRunReadModel:
        return self._orchestration.read(
            planning_run_id, context=self._context(planning_run_id)
        )

    @staticmethod
    def _select_work(
        model: PlanningRunReadModel, work_item_id: str
    ) -> tuple[PlanningRunWorkItem, PlanningRunAttempt]:
        matches = [
            work
            for work in model.work_items
            if work.document["work_item_id"] == work_item_id
        ]
        if len(matches) != 1:
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_WORK_ITEM,
                field="work_item_id",
                message="Work item is absent or ambiguous",
            )
        work = matches[0]
        attempts = [
            attempt
            for attempt in model.attempts
            if attempt.document["attempt_id"] == work.document["attempt_id"]
        ]
        if len(attempts) != 1 or attempts[0] is not model.attempts[-1]:
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_WORK_ITEM,
                field="attempt_id",
                message="Work item does not bind the latest durable attempt",
            )
        return work, attempts[0]

    def _current_runtime(self, planning_run_id: str) -> Mapping[str, object]:
        try:
            value = self._runtime_provider.current_resolution(planning_run_id)
        except PlanningRunWorkerError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize composition failure
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="runtime_resolution",
                message="Worker Runtime composition resolution failed",
                retryable=True,
            ) from error
        if not isinstance(value, Mapping):
            reject_worker(
                PlanningRunWorkerErrorCode.RUNTIME_MISMATCH,
                field="runtime_resolution",
                message="Worker Runtime composition is invalid",
            )
        return cast(Mapping[str, object], value)

    def _verify_runtime(self, work: Mapping[str, object]) -> None:
        expected = _mapping(work.get("runtime_resolution"), "runtime_resolution")
        actual = self._current_runtime(cast(str, work["planning_run_id"]))
        if actual.get("resolution_fingerprint") != runtime_resolution_fingerprint(
            actual
        ) or dict(actual) != dict(expected):
            reject_worker(
                PlanningRunWorkerErrorCode.RUNTIME_MISMATCH,
                field="runtime_resolution",
                message="Worker Runtime composition differs from the frozen work item",
            )

    @staticmethod
    def _require_reference(
        reference: object,
        *,
        document: Mapping[str, object],
        version_field: str,
        id_field: str,
        fingerprint: str,
        field: str,
    ) -> None:
        value = _mapping(reference, field)
        expected = {
            "document_version": document.get(version_field),
            "artifact_id": document.get(id_field),
            "fingerprint": fingerprint,
        }
        if dict(value) != expected:
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field=field,
                message="Resolved input differs from its frozen artifact reference",
            )

    def _verify_inputs(
        self,
        work: Mapping[str, object],
        resolved: PlanningRunResolvedInputs,
    ) -> None:
        prepared = _mapping(work.get("prepared_artifacts"), "prepared_artifacts")
        inputs = _mapping(work.get("inputs"), "inputs")
        quality = resolved.import_quality_report
        snapshot = resolved.snapshot
        problem = resolved.problem
        policy = resolved.planning_policy
        limits = resolved.solve_limits
        self._require_reference(
            prepared.get("import_quality_report"),
            document=quality,
            version_field="report_version",
            id_field="report_id",
            fingerprint=canonical_fingerprint(quality),
            field="prepared_artifacts.import_quality_report",
        )
        self._require_reference(
            prepared.get("snapshot"),
            document=snapshot,
            version_field="snapshot_version",
            id_field="snapshot_id",
            fingerprint=cast(str, snapshot.get("snapshot_hash")),
            field="prepared_artifacts.snapshot",
        )
        problem_hash = cast(str, problem.get("problem_hash"))
        problem_with_identity = {
            **problem,
            "_worker_problem_id": f"planning-problem-{problem_hash.removeprefix('sha256:')}",
        }
        self._require_reference(
            prepared.get("problem"),
            document=problem_with_identity,
            version_field="problem_version",
            id_field="_worker_problem_id",
            fingerprint=problem_hash,
            field="prepared_artifacts.problem",
        )
        self._require_reference(
            inputs.get("planning_policy"),
            document=policy,
            version_field="planning_policy_version",
            id_field="policy_id",
            fingerprint=contract_fingerprint(policy),
            field="inputs.planning_policy",
        )
        self._require_reference(
            inputs.get("solve_limits"),
            document=limits,
            version_field="solve_limits_version",
            id_field="limits_id",
            fingerprint=contract_fingerprint(limits),
            field="inputs.solve_limits",
        )
        if any(
            document.get("data_plane") != self._worker_repository.data_plane
            for document in (snapshot, problem, policy)
            if "data_plane" in document
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="resolved_inputs.data_plane",
                message="Resolved input crossed its configured data plane",
            )

    @staticmethod
    def _base_artifacts(work: Mapping[str, object]) -> JsonObject:
        prepared = _mapping(work.get("prepared_artifacts"), "prepared_artifacts")
        return {
            "import_quality_report": prepared["import_quality_report"],
            "snapshot": prepared["snapshot"],
            "problem": prepared["problem"],
            "planning_solution": None,
            "solver_report": None,
            "validation_report": None,
            "schedule_version": None,
        }

    def _transition(
        self,
        model: PlanningRunReadModel,
        *,
        work: Mapping[str, object],
        to_state: str,
        artifacts: Mapping[str, object],
        bind_attempt: bool,
    ) -> PlanningRunReadModel:
        run = model.aggregate.document
        attempt_id = cast(str, work["attempt_id"]) if bind_attempt else None
        result = self._orchestration.transition(
            PlanningRunTransitionCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=cast(int, run["revision"]),
                expected_state=cast(str, run["state"]),
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                to_state=to_state,
                idempotency_key=(
                    f"p8-worker:{work['work_item_id']}:transition:{to_state}"
                ),
                reason=f"Solver Worker advanced the durable run to {to_state}.",
                artifacts=artifacts,
                attempt_id=attempt_id,
            ),
            context=self._context(cast(str, run["planning_run_id"])),
        )
        return self._read(cast(str, result.aggregate.document["planning_run_id"]))

    def _start_attempt(
        self,
        model: PlanningRunReadModel,
        *,
        work: Mapping[str, object],
    ) -> PlanningRunReadModel:
        attempt = model.attempts[-1]
        if attempt.document["status"] == PlanningRunAttemptStatus.ACTIVE.value:
            return model
        if attempt.document["status"] != PlanningRunAttemptStatus.QUEUED.value:
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_WORK_ITEM,
                field="attempt.status",
                message="Only a QUEUED durable attempt can start",
            )
        run = model.aggregate.document
        self._orchestration.start_attempt(
            PlanningRunAttemptStartCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=cast(int, run["revision"]),
                expected_state=cast(str, run["state"]),
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                attempt_id=cast(str, attempt.document["attempt_id"]),
                attempt_number=cast(int, attempt.document["attempt_number"]),
                expected_attempt_revision=cast(int, attempt.document["revision"]),
                idempotency_key=f"p8-worker:{work['work_item_id']}:attempt:start",
                reason="Solver Worker claimed the durable attempt lease.",
            ),
            context=self._context(cast(str, run["planning_run_id"])),
        )
        return self._read(cast(str, run["planning_run_id"]))

    def _record_preclaim_failure(
        self,
        model: PlanningRunReadModel,
        *,
        work: Mapping[str, object],
        failure_code: str,
    ) -> None:
        attempt = model.attempts[-1]
        if attempt.document["status"] != PlanningRunAttemptStatus.QUEUED.value:
            return
        run = model.aggregate.document
        self._orchestration.record_attempt_failure(
            PlanningRunAttemptFailureCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=cast(int, run["revision"]),
                expected_state=cast(str, run["state"]),
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                attempt_id=cast(str, attempt.document["attempt_id"]),
                attempt_number=cast(int, attempt.document["attempt_number"]),
                expected_attempt_revision=cast(int, attempt.document["revision"]),
                outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
                failure_code=failure_code,
                idempotency_key=(
                    f"p8-worker:{work['work_item_id']}:dispatch:{failure_code}"
                ),
                reason="Worker rejected the work before acquiring execution ownership.",
            ),
            context=self._context(cast(str, run["planning_run_id"])),
        )

    def _timeout(
        self,
        model: PlanningRunReadModel,
        *,
        work: Mapping[str, object],
        job: JobRecord,
        worker_id: str,
    ) -> PlanningRunWorkerExecution:
        latest = self._read(cast(str, work["planning_run_id"]))
        run = latest.aggregate.document
        attempt = latest.attempts[-1]
        status = PlanningRunAttemptStatus(cast(str, attempt.document["status"]))
        if run["state"] not in PLANNING_RUN_TERMINAL_STATES and status not in (
            ATTEMPT_TERMINAL_STATUSES
        ):
            self._orchestration.record_attempt_failure(
                PlanningRunAttemptFailureCommand(
                    planning_run_id=cast(str, run["planning_run_id"]),
                    expected_revision=cast(int, run["revision"]),
                    expected_state=cast(str, run["state"]),
                    expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                    attempt_id=cast(str, attempt.document["attempt_id"]),
                    attempt_number=cast(int, attempt.document["attempt_number"]),
                    expected_attempt_revision=cast(int, attempt.document["revision"]),
                    outcome=PlanningRunAttemptStatus.TIMED_OUT,
                    failure_code="WORK_ITEM_TIMEOUT",
                    idempotency_key=(
                        f"p8-worker:{work['work_item_id']}:attempt:timeout"
                    ),
                    reason="Immutable Worker execution window elapsed.",
                ),
                context=self._context(cast(str, run["planning_run_id"])),
            )
        self._worker_repository.complete(
            job.job_id,
            worker_id=worker_id,
            now=self._now(),
            succeeded=False,
            failure_code="WORK_ITEM_TIMEOUT",
        )
        return PlanningRunWorkerExecution(
            job_id=job.job_id,
            planning_run_id=cast(str, work["planning_run_id"]),
            attempt_id=cast(str, work["attempt_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            disposition=WorkerDisposition.TIMED_OUT,
            planning_run_state=cast(str, run["state"]),
            checkpoint_replayed=False,
            publication_replayed=False,
        )

    def _advance_to_solve(
        self,
        model: PlanningRunReadModel,
        *,
        work: Mapping[str, object],
        guard: _HeartbeatGuard,
    ) -> PlanningRunReadModel:
        base = self._base_artifacts(work)
        snapshotted = {**base, "problem": None}
        empty = {name: None for name in _ARTIFACT_FIELDS}
        while True:
            guard.beat()
            state = cast(str, model.aggregate.document["state"])
            if state in PLANNING_RUN_TERMINAL_STATES or state in {
                "SOLVING",
                "SOLVED",
                "VERIFYING",
            }:
                return model
            if state == "CREATED":
                model = self._transition(
                    model,
                    work=work,
                    to_state="INGESTING",
                    artifacts=empty,
                    bind_attempt=False,
                )
            elif state == "INGESTING":
                model = self._transition(
                    model,
                    work=work,
                    to_state="VALIDATING",
                    artifacts=empty,
                    bind_attempt=False,
                )
            elif state == "VALIDATING":
                model = self._transition(
                    model,
                    work=work,
                    to_state="SNAPSHOTTED",
                    artifacts=snapshotted,
                    bind_attempt=False,
                )
            elif state == "SNAPSHOTTED":
                model = self._transition(
                    model,
                    work=work,
                    to_state="BUILDING",
                    artifacts=snapshotted,
                    bind_attempt=True,
                )
            elif state == "BUILDING":
                model = self._transition(
                    model,
                    work=work,
                    to_state="SOLVING",
                    artifacts=base,
                    bind_attempt=True,
                )
            else:
                reject_worker(
                    PlanningRunWorkerErrorCode.INVALID_WORK_ITEM,
                    field="planning_run.state",
                    message="Worker cannot resume from this PlanningRun state",
                )

    @staticmethod
    def _solver_artifacts(
        base: Mapping[str, object],
        *,
        solution: Mapping[str, object],
        solver_report: Mapping[str, object],
    ) -> JsonObject:
        return {
            **base,
            "planning_solution": _reference(
                document_version="planning-solution.v1",
                artifact_id=cast(str, solution["solution_id"]),
                fingerprint=contract_fingerprint(solution),
            ),
            "solver_report": _reference(
                document_version="solver-report.v1",
                artifact_id=cast(str, solver_report["report_id"]),
                fingerprint=contract_fingerprint(solver_report),
            ),
        }

    def _build_checkpoint(
        self,
        *,
        job: JobRecord,
        work: Mapping[str, object],
        resolved: PlanningRunResolvedInputs,
        solution: Mapping[str, object],
        solver_report: Mapping[str, object],
    ) -> PlanningRunWorkerResult:
        status = SolverStatus(cast(str, solution["solver_status"]))
        outcome = outcome_for_solver_status(status)
        base = self._base_artifacts(work)
        if not outcome.candidate_available:
            artifacts = {
                **base,
                "planning_solution": None,
                "solver_report": _reference(
                    document_version="solver-report.v1",
                    artifact_id=cast(str, solver_report["report_id"]),
                    fingerprint=contract_fingerprint(solver_report),
                ),
            }
            return build_worker_result(
                job_id=job.job_id,
                data_plane=self._worker_repository.data_plane,
                work_item=work,
                outcome_state=outcome.planning_run_state.value,
                artifact_references=artifacts,
                planning_solution=solution,
                solver_report=solver_report,
                validation_report=None,
                kpi=None,
                schedule_context=None,
                schedule_version_reference=None,
                created_at_utc=format_utc_instant(self._now()),
            )

        fresh_validation = self._validator.validate(resolved.problem, solution)
        solved = self._solver_artifacts(
            base, solution=solution, solver_report=solver_report
        )
        validation_reference = _reference(
            document_version="validation-report.v2",
            artifact_id=(
                "validation-report-"
                f"{contract_fingerprint(fresh_validation).removeprefix('sha256:')}"
            ),
            fingerprint=contract_fingerprint(fresh_validation),
        )
        if (
            fresh_validation.get("status") != "PASS"
            or fresh_validation.get("hard_violation_count") != 0
        ):
            return build_worker_result(
                job_id=job.job_id,
                data_plane=self._worker_repository.data_plane,
                work_item=work,
                outcome_state="VALIDATION_FAILED",
                artifact_references={
                    **solved,
                    "validation_report": validation_reference,
                },
                planning_solution=solution,
                solver_report=solver_report,
                validation_report=fresh_validation,
                kpi=None,
                schedule_context=None,
                schedule_version_reference=None,
                created_at_utc=format_utc_instant(self._now()),
            )

        kpi = build_kpi_v2(
            snapshot=resolved.snapshot,
            problem=resolved.problem,
            solution=solution,
            solver_report=solver_report,
            validation_report=fresh_validation,
            import_quality_report=resolved.import_quality_report,
        ).document
        command_context = self._context(cast(str, work["planning_run_id"]))
        schedule_context = ScheduleVersionCreationContext(
            planning_run_state="COMPLETED",
            environment=command_context.environment,
            actor_ref=command_context.actor_reference,
            auth_policy_version=command_context.auth_policy_version,
            occurred_at_utc=command_context.occurred_at_utc,
            correlation_id=cast(str, work["correlation_id"]),
            idempotency_key_reference=canonical_fingerprint(
                {
                    "operation": "P8_WORKER_SCHEDULE_VERSION",
                    "work_item_id": work["work_item_id"],
                }
            ),
            reason="Create a reviewable version from the validated Solver result.",
        )
        output = ValidatedPlanningOutput(
            snapshot=resolved.snapshot,
            problem=resolved.problem,
            solution=solution,
            solver_report=solver_report,
            validation_report=fresh_validation,
            import_quality_report=resolved.import_quality_report,
            kpi=kpi,
        )
        schedule_documents = build_reviewable_schedule_documents(
            output,
            schedule_context,
            data_plane=self._worker_repository.data_plane,
        )
        schedule_reference = _reference(
            document_version="schedule-version.v1",
            artifact_id=schedule_documents.schedule_version_id,
            fingerprint=cast(
                str, schedule_documents.ready_for_review["content_fingerprint"]
            ),
        )
        return build_worker_result(
            job_id=job.job_id,
            data_plane=self._worker_repository.data_plane,
            work_item=work,
            outcome_state="COMPLETED",
            artifact_references={
                **solved,
                "validation_report": validation_reference,
                "schedule_version": schedule_reference,
            },
            planning_solution=solution,
            solver_report=solver_report,
            validation_report=fresh_validation,
            kpi=kpi,
            schedule_context=asdict(schedule_context),
            schedule_version_reference=schedule_reference,
            created_at_utc=command_context.occurred_at_utc,
        )

    def _validated_output(
        self,
        checkpoint: PlanningRunWorkerResult,
        *,
        resolved: PlanningRunResolvedInputs,
    ) -> tuple[ValidatedPlanningOutput, ScheduleVersionCreationContext]:
        verify_worker_result(checkpoint, data_plane=self._worker_repository.data_plane)
        document = checkpoint.document
        if document["outcome_state"] != "COMPLETED":
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.outcome_state",
                message="Only a completed checkpoint can create a ScheduleVersion",
            )
        documents = _mapping(document["documents"], "worker_result.documents")
        solution = _mapping(
            documents["planning_solution"], "worker_result.documents.planning_solution"
        )
        solver_report = _mapping(
            documents["solver_report"], "worker_result.documents.solver_report"
        )
        validation = _mapping(
            documents["validation_report"],
            "worker_result.documents.validation_report",
        )
        kpi = _mapping(documents["kpi"], "worker_result.documents.kpi")
        fresh = self._validator.validate(resolved.problem, solution)
        if dict(fresh) != dict(validation):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.documents.validation_report",
                message="Stored validation differs from a fresh formal validation",
            )
        rebuilt_kpi = build_kpi_v2(
            snapshot=resolved.snapshot,
            problem=resolved.problem,
            solution=solution,
            solver_report=solver_report,
            validation_report=validation,
            import_quality_report=resolved.import_quality_report,
        ).document
        if rebuilt_kpi != kpi:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.documents.kpi",
                message="Stored KPI differs from a fresh calculation",
            )
        raw_context = _mapping(
            document["schedule_context"], "worker_result.schedule_context"
        )
        try:
            context = ScheduleVersionCreationContext(
                planning_run_state=cast(str, raw_context["planning_run_state"]),
                environment=cast(str, raw_context["environment"]),
                actor_ref=cast(str, raw_context["actor_ref"]),
                auth_policy_version=cast(str, raw_context["auth_policy_version"]),
                occurred_at_utc=cast(str, raw_context["occurred_at_utc"]),
                correlation_id=cast(str, raw_context["correlation_id"]),
                idempotency_key_reference=cast(
                    str, raw_context["idempotency_key_reference"]
                ),
                reason=cast(str, raw_context["reason"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.schedule_context",
                message="Stored ScheduleVersion context is invalid",
            ) from error
        output = ValidatedPlanningOutput(
            snapshot=resolved.snapshot,
            problem=resolved.problem,
            solution=solution,
            solver_report=solver_report,
            validation_report=validation,
            import_quality_report=resolved.import_quality_report,
            kpi=kpi,
        )
        schedule = build_reviewable_schedule_documents(
            output, context, data_plane=self._worker_repository.data_plane
        )
        expected_schedule_reference = _reference(
            document_version="schedule-version.v1",
            artifact_id=schedule.schedule_version_id,
            fingerprint=cast(str, schedule.ready_for_review["content_fingerprint"]),
        )
        if document["schedule_version_reference"] != expected_schedule_reference:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.schedule_version_reference",
                message="Stored ScheduleVersion reference cannot be rebuilt",
            )
        return output, context

    def _verify_checkpoint_lineage(
        self,
        checkpoint: PlanningRunWorkerResult,
        *,
        work: Mapping[str, object],
        resolved: PlanningRunResolvedInputs,
    ) -> None:
        """Rebind every stored output/reference before state or publication use."""

        verify_worker_result(
            checkpoint,
            expected_work_item=work,
            data_plane=self._worker_repository.data_plane,
        )
        document = checkpoint.document
        runtime = _mapping(work["runtime_resolution"], "work.runtime_resolution")
        if (
            document["planning_run_id"] != work["planning_run_id"]
            or document["runtime_resolution_fingerprint"]
            != runtime["resolution_fingerprint"]
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.lineage",
                message="Worker checkpoint differs from the active run lineage",
            )
        artifacts = _mapping(
            document["artifact_references"], "worker_result.artifact_references"
        )
        base = self._base_artifacts(work)
        for field in ("import_quality_report", "snapshot", "problem"):
            if artifacts[field] != base[field]:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field=f"worker_result.artifact_references.{field}",
                    message="Worker checkpoint changed an immutable input reference",
                )
        documents = _mapping(document["documents"], "worker_result.documents")
        solution = _mapping(
            documents["planning_solution"],
            "worker_result.documents.planning_solution",
        )
        solver_report = _mapping(
            documents["solver_report"], "worker_result.documents.solver_report"
        )
        try:
            validate_contract_bundle(
                resolved.planning_policy,
                resolved.solve_limits,
                solution,
                solver_report,
            )
            status = SolverStatus(cast(str, solver_report.get("solver_status")))
        except (PlanningContractError, KeyError, TypeError, ValueError) as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.documents",
                message="Stored Solver result contract is invalid",
            ) from error
        if solver_report.get("planning_run_id") != work["planning_run_id"] or artifacts[
            "solver_report"
        ] != _reference(
            document_version="solver-report.v1",
            artifact_id=cast(str, solver_report.get("report_id")),
            fingerprint=contract_fingerprint(solver_report),
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.documents.solver_report",
                message="Solver report reference or run lineage is invalid",
            )
        solver_outcome = outcome_for_solver_status(status)
        outcome = cast(str, document["outcome_state"])
        if solver_outcome.candidate_available:
            if outcome not in {"COMPLETED", "VALIDATION_FAILED"}:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result.outcome_state",
                    message="Candidate Solver status has an invalid Worker outcome",
                )
            if solution.get("solver_status") != status.value or artifacts[
                "planning_solution"
            ] != _reference(
                document_version="planning-solution.v1",
                artifact_id=cast(str, solution.get("solution_id")),
                fingerprint=contract_fingerprint(solution),
            ):
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result.documents.planning_solution",
                    message="PlanningSolution reference or status is invalid",
                )
            solution_reference = _mapping(
                solver_report.get("solution"), "solver_report.solution"
            )
            if solution_reference.get("solution_id") != solution.get(
                "solution_id"
            ) or solution_reference.get("solution_fingerprint") != contract_fingerprint(
                solution
            ):
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="solver_report.solution",
                    message="Solver report does not bind the PlanningSolution bytes",
                )
            validation = _mapping(
                documents["validation_report"],
                "worker_result.documents.validation_report",
            )
            expected_validation = _reference(
                document_version="validation-report.v2",
                artifact_id=(
                    "validation-report-"
                    f"{contract_fingerprint(validation).removeprefix('sha256:')}"
                ),
                fingerprint=contract_fingerprint(validation),
            )
            if artifacts["validation_report"] != expected_validation:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result.documents.validation_report",
                    message="ValidationReport reference is invalid",
                )
            try:
                fresh_validation = self._validator.validate(resolved.problem, solution)
            except Exception as error:  # noqa: BLE001 - sanitize Validator failure
                raise PlanningRunWorkerError(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result.documents.validation_report",
                    message="Stored candidate cannot be independently validated",
                ) from error
            validation_passed = (
                fresh_validation.get("status") == "PASS"
                and fresh_validation.get("hard_violation_count") == 0
            )
            if dict(fresh_validation) != dict(validation) or validation_passed != (
                outcome == "COMPLETED"
            ):
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result.documents.validation_report",
                    message="Stored validation outcome differs from a fresh validation",
                )
        elif (
            outcome != solver_outcome.planning_run_state.value
            or artifacts["planning_solution"] is not None
            or artifacts["validation_report"] is not None
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.outcome_state",
                message="Non-candidate Solver status has invalid result references",
            )

    def _publish_checkpoint(
        self,
        checkpoint: PlanningRunWorkerResult,
        *,
        resolved: PlanningRunResolvedInputs,
    ) -> bool:
        checkpoint_document = checkpoint.document
        planning_run_id = cast(str, checkpoint_document["planning_run_id"])
        actual_runtime = self._current_runtime(planning_run_id)
        if (
            actual_runtime.get("resolution_fingerprint")
            != runtime_resolution_fingerprint(actual_runtime)
            or actual_runtime.get("resolution_fingerprint")
            != checkpoint_document["runtime_resolution_fingerprint"]
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RUNTIME_MISMATCH,
                field="runtime_resolution",
                message="Runtime composition changed before result publication",
            )
        output, context = self._validated_output(checkpoint, resolved=resolved)
        try:
            result = self._publisher.create_reviewable(output, context)
        except Exception as error:  # noqa: BLE001 - sanitize application adapter
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="schedule_version.publication",
                message="Validated ScheduleVersion application failed",
                retryable=True,
            ) from error
        reference = cast(
            Mapping[str, object], checkpoint.document["schedule_version_reference"]
        )
        if (
            result.schedule_version.get("schedule_version_id")
            != reference["artifact_id"]
            or result.schedule_version.get("content_fingerprint")
            != reference["fingerprint"]
            or result.schedule_version.get("state") != "READY_FOR_REVIEW"
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="schedule_version.publication",
                message="ScheduleVersion application returned another result",
            )
        return bool(getattr(result, "exact_replay", False))

    def _apply_checkpoint(
        self,
        model: PlanningRunReadModel,
        *,
        work: Mapping[str, object],
        checkpoint: PlanningRunWorkerResult,
        resolved: PlanningRunResolvedInputs,
        guard: _HeartbeatGuard,
    ) -> tuple[PlanningRunReadModel, bool]:
        self._verify_checkpoint_lineage(checkpoint, work=work, resolved=resolved)
        document = checkpoint.document
        artifacts = cast(Mapping[str, object], document["artifact_references"])
        outcome = cast(str, document["outcome_state"])
        state = cast(str, model.aggregate.document["state"])
        if state == "CANCELLED":
            return model, False
        if state in PLANNING_RUN_TERMINAL_STATES:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="planning_run.state",
                message="Worker checkpoint conflicts with a terminal PlanningRun",
            )
        if outcome in {
            "MODEL_INVALID",
            "INFEASIBLE",
            "NO_SOLUTION_WITHIN_LIMIT",
            "CANCELLED",
            "FAILED",
        }:
            if state != "SOLVING":
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="planning_run.state",
                    message="Solver terminal checkpoint cannot bind this run state",
                )
            guard.beat()
            return (
                self._transition(
                    model,
                    work=work,
                    to_state=outcome,
                    artifacts=artifacts,
                    bind_attempt=True,
                ),
                False,
            )

        solved_artifacts = {
            **artifacts,
            "validation_report": None,
            "schedule_version": None,
        }
        if state == "SOLVING":
            guard.beat()
            model = self._transition(
                model,
                work=work,
                to_state="SOLVED",
                artifacts=solved_artifacts,
                bind_attempt=True,
            )
            state = "SOLVED"
        if state == "SOLVED":
            guard.beat()
            model = self._transition(
                model,
                work=work,
                to_state="VERIFYING",
                artifacts=solved_artifacts,
                bind_attempt=True,
            )
            state = "VERIFYING"
        if state != "VERIFYING":
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="planning_run.state",
                message="Validated checkpoint cannot bind this run state",
            )
        guard.beat()
        self._verify_runtime(work)
        model = self._transition(
            model,
            work=work,
            to_state=outcome,
            artifacts=artifacts,
            bind_attempt=True,
        )
        publication_replayed = False
        if outcome == "COMPLETED":
            publication_replayed = self._publish_checkpoint(
                checkpoint, resolved=resolved
            )
        return model, publication_replayed

    def _terminal_execution(
        self,
        *,
        job: JobRecord,
        work: Mapping[str, object],
        state: str,
        checkpoint_replayed: bool,
        publication_replayed: bool,
    ) -> PlanningRunWorkerExecution:
        disposition = (
            WorkerDisposition.TIMED_OUT
            if job.failure_code == "WORK_ITEM_TIMEOUT"
            else WorkerDisposition.COMPLETED
            if state == "COMPLETED"
            else WorkerDisposition.CANCELLED
            if state == "CANCELLED"
            else WorkerDisposition.TERMINAL_FAILURE
        )
        return PlanningRunWorkerExecution(
            job_id=job.job_id,
            planning_run_id=cast(str, work["planning_run_id"]),
            attempt_id=cast(str, work["attempt_id"]),
            work_item_id=cast(str, work["work_item_id"]),
            disposition=disposition,
            planning_run_state=state,
            checkpoint_replayed=checkpoint_replayed,
            publication_replayed=publication_replayed,
        )

    def _complete_terminal_job(
        self,
        *,
        job: JobRecord,
        worker_id: str,
        work: Mapping[str, object],
        state: str,
        checkpoint_replayed: bool,
        publication_replayed: bool,
    ) -> PlanningRunWorkerExecution:
        self._worker_repository.complete(
            job.job_id,
            worker_id=worker_id,
            now=self._now(),
            succeeded=True,
        )
        return self._terminal_execution(
            job=job,
            work=work,
            state=state,
            checkpoint_replayed=checkpoint_replayed,
            publication_replayed=publication_replayed,
        )

    def _handle_existing_terminal(
        self,
        *,
        model: PlanningRunReadModel,
        work: Mapping[str, object],
        resolved: PlanningRunResolvedInputs,
        job: JobRecord,
        worker_id: str,
    ) -> PlanningRunWorkerExecution:
        state = cast(str, model.aggregate.document["state"])
        publication_replayed = False
        checkpoint_replayed = False
        if state == "COMPLETED":
            checkpoint = self._worker_repository.get_result_for_work_item(
                cast(str, work["work_item_id"])
            ) or self._worker_repository.get_latest_result_for_run(
                cast(str, work["planning_run_id"])
            )
            if checkpoint is None:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result",
                    message="Completed PlanningRun has no recovery checkpoint",
                )
            self._verify_checkpoint_lineage(checkpoint, work=work, resolved=resolved)
            publication_replayed = self._publish_checkpoint(
                checkpoint, resolved=resolved
            )
            checkpoint_replayed = True
        return self._complete_terminal_job(
            job=job,
            worker_id=worker_id,
            work=work,
            state=state,
            checkpoint_replayed=checkpoint_replayed,
            publication_replayed=publication_replayed,
        )

    def execute(
        self,
        *,
        planning_run_id: str,
        work_item_id: str,
        worker_id: str,
    ) -> PlanningRunWorkerExecution:
        """Execute/reconcile one message; no automatic business attempt is created."""

        if not planning_run_id or not work_item_id or not worker_id:
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_MESSAGE,
                field="task_message",
                message="Task message identities must be non-empty",
            )
        model = self._read(planning_run_id)
        work_value, attempt = self._select_work(model, work_item_id)
        work = work_value.document
        if work["planning_run_id"] != planning_run_id:
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_MESSAGE,
                field="planning_run_id",
                message="Task message and durable work item differ",
            )
        try:
            self._verify_runtime(work)
        except PlanningRunWorkerError as error:
            if error.code is PlanningRunWorkerErrorCode.RUNTIME_MISMATCH:
                self._record_preclaim_failure(
                    model,
                    work=work,
                    failure_code=error.code.value,
                )
            raise
        try:
            resolved = self._input_resolver.resolve(work)
        except PlanningRunWorkerError as error:
            if error.code is PlanningRunWorkerErrorCode.INPUT_MISMATCH:
                self._record_preclaim_failure(
                    model,
                    work=work,
                    failure_code=error.code.value,
                )
            raise
        except Exception as error:  # noqa: BLE001 - sanitize composition failure
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="resolved_inputs",
                message="Worker input resolution failed",
                retryable=True,
            ) from error
        try:
            if not isinstance(resolved, PlanningRunResolvedInputs):
                reject_worker(
                    PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                    field="resolved_inputs",
                    message="Worker input resolver returned an invalid carrier",
                )
            self._verify_inputs(work, resolved)
        except PlanningRunWorkerError as error:
            if error.code in {
                PlanningRunWorkerErrorCode.RUNTIME_MISMATCH,
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
            }:
                self._record_preclaim_failure(
                    model,
                    work=work,
                    failure_code=error.code.value,
                )
            raise
        except Exception as error:  # noqa: BLE001 - sanitize resolved input values
            mismatch = PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="resolved_inputs",
                message="Worker resolved inputs are invalid",
            )
            self._record_preclaim_failure(
                model,
                work=work,
                failure_code=mismatch.code.value,
            )
            raise mismatch from error

        now = self._now()
        available = parse_utc_instant(cast(str, work["available_at_utc"]))
        timeout = parse_utc_instant(cast(str, work["timeout_at_utc"]))
        ensured = self._worker_repository.ensure_job(work, now=now)
        stored_job = ensured.record
        if (
            stored_job.status is JobStatus.RUNNING
            and stored_job.lease_expires_at is not None
            and now >= stored_job.lease_expires_at
        ):
            self._recover_expired_job(
                stored_job.job_id,
                recovery_worker_id=worker_id,
                now=now,
            )
            refreshed = self._worker_repository.get_job(stored_job.job_id)
            if refreshed is None:
                reject_worker(
                    PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                    field="worker_job",
                    message="Recovered Worker job is absent",
                    retryable=True,
                )
            stored_job = refreshed
        if stored_job.status is JobStatus.SUCCEEDED:
            state = cast(str, self._read(planning_run_id).aggregate.document["state"])
            if state not in PLANNING_RUN_TERMINAL_STATES:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_job.status",
                    message="Successful Worker job has a nonterminal PlanningRun",
                )
            checkpoint = self._worker_repository.get_result_for_work_item(work_item_id)
            if state == "COMPLETED" and checkpoint is None:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field="worker_result",
                    message="Completed PlanningRun has no recovery checkpoint",
                )
            return PlanningRunWorkerExecution(
                job_id=stored_job.job_id,
                planning_run_id=planning_run_id,
                attempt_id=cast(str, work["attempt_id"]),
                work_item_id=work_item_id,
                disposition=WorkerDisposition.EXACT_REPLAY,
                planning_run_state=state,
                checkpoint_replayed=checkpoint is not None,
                publication_replayed=False,
            )
        if stored_job.status is JobStatus.FAILED:
            state = cast(str, self._read(planning_run_id).aggregate.document["state"])
            return self._terminal_execution(
                job=stored_job,
                work=work,
                state=state,
                checkpoint_replayed=(
                    self._worker_repository.get_result_for_work_item(work_item_id)
                    is not None
                ),
                publication_replayed=False,
            )
        if stored_job.status is JobStatus.RUNNING:
            reject_worker(
                PlanningRunWorkerErrorCode.LEASE_BUSY,
                field="worker_job.lease",
                message="Duplicate delivery found an active lease",
                retryable=True,
            )
        if now < available:
            reject_worker(
                PlanningRunWorkerErrorCode.NOT_AVAILABLE,
                field="work_item.available_at_utc",
                message="Work item is not available yet",
                retryable=True,
            )
        job = self._worker_repository.claim(
            stored_job.job_id,
            worker_id=worker_id,
            now=now,
            lease_seconds=self._policy.lease_seconds,
        )
        model = self._read(planning_run_id)
        if model.aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
            return self._handle_existing_terminal(
                model=model,
                work=work,
                resolved=resolved,
                job=job,
                worker_id=worker_id,
            )
        if now >= timeout:
            return self._timeout(model, work=work, job=job, worker_id=worker_id)
        model = self._start_attempt(model, work=work)

        with _HeartbeatGuard(
            repository=self._worker_repository,
            job_id=job.job_id,
            worker_id=worker_id,
            policy=self._policy,
            clock=self._now,
        ) as guard:
            model = self._advance_to_solve(model, work=work, guard=guard)
            state = cast(str, model.aggregate.document["state"])
            if state in PLANNING_RUN_TERMINAL_STATES:
                return self._complete_terminal_job(
                    job=job,
                    worker_id=worker_id,
                    work=work,
                    state=state,
                    checkpoint_replayed=False,
                    publication_replayed=False,
                )
            if self._now() >= timeout:
                return self._timeout(model, work=work, job=job, worker_id=worker_id)
            checkpoint = self._worker_repository.get_result_for_work_item(work_item_id)
            checkpoint_replayed = checkpoint is not None
            if checkpoint is None and state in {"SOLVED", "VERIFYING"}:
                checkpoint = self._worker_repository.get_latest_result_for_run(
                    planning_run_id
                )
                checkpoint_replayed = checkpoint is not None
            if checkpoint is None:
                if state != "SOLVING":
                    reject_worker(
                        PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                        field="worker_result",
                        message="Resumed run has no immutable Solver checkpoint",
                    )
                try:
                    solver_result = self._solver.solve(
                        resolved.problem,
                        resolved.planning_policy,
                        resolved.solve_limits,
                        planning_run_id=planning_run_id,
                        code_commit=self._context(planning_run_id).code_commit,
                    )
                    solution = solver_result.solution
                    solver_report = solver_result.solver_report
                    validate_contract_bundle(
                        resolved.planning_policy,
                        resolved.solve_limits,
                        solution,
                        solver_report,
                    )
                except (PlanningContractError, KeyError, TypeError, ValueError):
                    terminal = self._transition(
                        self._read(planning_run_id),
                        work=work,
                        to_state="MODEL_INVALID",
                        artifacts=cast(
                            Mapping[str, object],
                            self._read(planning_run_id).aggregate.document["artifacts"],
                        ),
                        bind_attempt=True,
                    )
                    self._worker_repository.complete(
                        job.job_id,
                        worker_id=worker_id,
                        now=self._now(),
                        succeeded=False,
                        failure_code="MODEL_INVALID",
                    )
                    return self._terminal_execution(
                        job=job,
                        work=work,
                        state=cast(str, terminal.aggregate.document["state"]),
                        checkpoint_replayed=False,
                        publication_replayed=False,
                    )
                except Exception as error:  # noqa: BLE001 - sanitize Solver failure
                    try:
                        current = self._read(planning_run_id)
                        if current.aggregate.document["state"] not in (
                            PLANNING_RUN_TERMINAL_STATES
                        ):
                            self._transition(
                                current,
                                work=work,
                                to_state="FAILED",
                                artifacts=cast(
                                    Mapping[str, object],
                                    current.aggregate.document["artifacts"],
                                ),
                                bind_attempt=True,
                            )
                        self._worker_repository.complete(
                            job.job_id,
                            worker_id=worker_id,
                            now=self._now(),
                            succeeded=False,
                            failure_code="SOLVER_EXECUTION_FAILED",
                        )
                    except PlanningRunWorkerError:
                        raise
                    raise PlanningRunWorkerError(
                        PlanningRunWorkerErrorCode.EXECUTION_FAILED,
                        field="solver",
                        message="Solver execution failed",
                    ) from error
                guard.beat()
                if self._now() >= timeout:
                    return self._timeout(model, work=work, job=job, worker_id=worker_id)
                latest = self._read(planning_run_id)
                if latest.aggregate.document["state"] == "CANCELLED":
                    return self._complete_terminal_job(
                        job=job,
                        worker_id=worker_id,
                        work=work,
                        state="CANCELLED",
                        checkpoint_replayed=False,
                        publication_replayed=False,
                    )
                self._verify_runtime(work)
                self._verify_inputs(work, resolved)
                try:
                    checkpoint = self._build_checkpoint(
                        job=job,
                        work=work,
                        resolved=resolved,
                        solution=solution,
                        solver_report=solver_report,
                    )
                except Exception as error:  # noqa: BLE001 - sanitize validation failure
                    try:
                        current = self._read(planning_run_id)
                        if current.aggregate.document["state"] not in (
                            PLANNING_RUN_TERMINAL_STATES
                        ):
                            self._transition(
                                current,
                                work=work,
                                to_state="FAILED",
                                artifacts=cast(
                                    Mapping[str, object],
                                    current.aggregate.document["artifacts"],
                                ),
                                bind_attempt=True,
                            )
                        self._worker_repository.complete(
                            job.job_id,
                            worker_id=worker_id,
                            now=self._now(),
                            succeeded=False,
                            failure_code="VALIDATOR_EXECUTION_FAILED",
                        )
                    except PlanningRunWorkerError:
                        raise
                    raise PlanningRunWorkerError(
                        PlanningRunWorkerErrorCode.EXECUTION_FAILED,
                        field="formal_validator",
                        message="Formal validation or result construction failed",
                    ) from error
                write = self._worker_repository.put_result(checkpoint)
                checkpoint = write.result
                checkpoint_replayed = write.replayed
            guard.check()
            model = self._read(planning_run_id)
            if model.aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
                return self._handle_existing_terminal(
                    model=model,
                    work=work,
                    resolved=resolved,
                    job=job,
                    worker_id=worker_id,
                )
            if self._now() >= timeout:
                return self._timeout(model, work=work, job=job, worker_id=worker_id)
            model, publication_replayed = self._apply_checkpoint(
                model,
                work=work,
                checkpoint=checkpoint,
                resolved=resolved,
                guard=guard,
            )
            guard.check()

        state = cast(str, model.aggregate.document["state"])
        return self._complete_terminal_job(
            job=job,
            worker_id=worker_id,
            work=work,
            state=state,
            checkpoint_replayed=checkpoint_replayed,
            publication_replayed=publication_replayed,
        )

    def _recover_expired_job(
        self,
        job_id: str,
        *,
        recovery_worker_id: str,
        now: datetime,
    ) -> PlanningRunWorkerRecovery | None:
        stalled = self._worker_repository.mark_expired_stalled(job_id, now=now)
        if stalled.status is not JobStatus.STALLED:
            return None
        binding = self._worker_repository.get_binding(job_id)
        if binding is None:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_job.binding",
                message="Expired Worker job has no durable work binding",
            )
        model = self._read(binding.planning_run_id)
        state = cast(str, model.aggregate.document["state"])
        if state == "COMPLETED":
            action = "REQUEUE"
        elif state in PLANNING_RUN_TERMINAL_STATES:
            self._worker_repository.claim(
                job_id,
                worker_id=recovery_worker_id,
                now=now,
                lease_seconds=self._policy.lease_seconds,
            )
            self._worker_repository.complete(
                job_id,
                worker_id=recovery_worker_id,
                now=now,
                succeeded=True,
            )
            action = "TERMINAL_ACK"
        else:
            work_value, _ = self._select_work(model, binding.work_item_id)
            work = work_value.document
            checkpoint = self._worker_repository.get_result_for_work_item(
                binding.work_item_id
            )
            work_timed_out = now >= parse_utc_instant(cast(str, work["timeout_at_utc"]))
            if checkpoint is not None and not work_timed_out:
                verify_worker_result(
                    checkpoint,
                    expected_work_item=work,
                    data_plane=self._worker_repository.data_plane,
                )
                action = "REQUEUE"
            else:
                claimed = self._worker_repository.claim(
                    job_id,
                    worker_id=recovery_worker_id,
                    now=now,
                    lease_seconds=self._policy.lease_seconds,
                )
                self._timeout(
                    model,
                    work=work,
                    job=claimed,
                    worker_id=recovery_worker_id,
                )
                action = "TIMED_OUT"
        return PlanningRunWorkerRecovery(
            job_id, binding.planning_run_id, binding.attempt_id, action
        )

    def recover_expired(
        self, *, recovery_worker_id: str
    ) -> tuple[PlanningRunWorkerRecovery, ...]:
        """Fence expired leases, replay checkpoints, or time out unfinished attempts."""

        recovered: list[PlanningRunWorkerRecovery] = []
        now = self._now()
        for job_id in self._worker_repository.expired_running_job_ids(now=now):
            recovery = self._recover_expired_job(
                job_id,
                recovery_worker_id=recovery_worker_id,
                now=now,
            )
            if recovery is not None:
                recovered.append(recovery)
        return tuple(recovered)


__all__ = [
    "FormalValidator",
    "PlanningInputResolver",
    "PlanningRunContextProvider",
    "PlanningRunSolverWorker",
    "PlanningRunWorkerExecution",
    "PlanningRunWorkerRecovery",
    "RuntimeResolutionProvider",
    "ScheduleVersionPublisher",
    "WorkerDisposition",
    "WorkerReliabilityPolicy",
]
