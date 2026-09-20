"""Durable replan execution using the existing run, lease and P4 owners."""

from __future__ import annotations

from contextlib import contextmanager
from copy import copy
from dataclasses import replace
from typing import Any, cast
from collections.abc import Mapping

from app.application.replan_application import (
    ReplanApplicationInput,
    ReplanApplicationService,
    _mapping,
    _reference_matches,
)
from app.application.runtime_replan import artifact
from app.data_validation.canonical_ingress import canonical_fingerprint
from app.domain.planning_run import PLANNING_RUN_TERMINAL_STATES
from app.domain.replan_application import ReplanApplicationContext
from app.domain.replan_application import ReplanApplicationError
from app.extensions.contracts import RuntimeExtensionError
from app.application.runtime_dynamic_replanning import RuntimeEventError
from app.infrastructure.runtime_replan_repository import (
    ReplanCheckpointRepository,
    TransactionEngine,
    lock_run,
)
from app.infrastructure.replan_repository import SqlAlchemyReplanLineageRepository
from app.jobs.contracts import JobStatus
from app.jobs.planning_run_solver_worker import (
    PlanningRunSolverWorker,
    PlanningRunWorkerRecovery,
    _HeartbeatGuard,
)
from app.jobs.planning_run_worker_contracts import (
    PlanningRunWorkerErrorCode,
    reject_worker,
)
from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError
from app.planning.reporting.replan_kpi import build_replan_kpi
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanStrategy,
    LexicographicReplanResult,
)


class RuntimeReplanService(ReplanApplicationService):
    """Read successor lineage without changing the frozen P4 service owner."""

    def _validate_base_lineage(
        self, base: Mapping[str, object], request: Mapping[str, object]
    ) -> None:
        if base.get("schedule_version_version") != "schedule-version.v2":
            return super()._validate_base_lineage(base, request)
        lineage = _mapping(base.get("lineage"), "base_schedule.lineage")
        for name in ("snapshot", "problem"):
            _reference_matches(
                _mapping(request.get("base_" + name), "request.base_" + name),
                _mapping(
                    lineage.get("new_" + name), "base_schedule.lineage.new_" + name
                ),
                "request.base_" + name,
            )


class RuntimeReplanWorker(PlanningRunSolverWorker):
    def __init__(self, normal: PlanningRunSolverWorker, application: Any) -> None:
        self.__dict__.update(normal.__dict__)
        self._normal = normal
        self._application = application
        self._orchestration = application.orchestration
        self._checkpoints = ReplanCheckpointRepository(application.engine)

    def execute(
        self, *, planning_run_id: str, work_item_id: str, worker_id: str
    ) -> Any:
        try:
            return self._execute(
                planning_run_id=planning_run_id,
                work_item_id=work_item_id,
                worker_id=worker_id,
            )
        except (
            RuntimeEventError,
            ReplanApplicationError,
            PlanningRunWorkerError,
            RuntimeExtensionError,
            ValueError,
        ) as error:
            if isinstance(error, PlanningRunWorkerError) and error.code in {
                PlanningRunWorkerErrorCode.LEASE_BUSY,
                PlanningRunWorkerErrorCode.LEASE_LOST,
                PlanningRunWorkerErrorCode.NOT_AVAILABLE,
                PlanningRunWorkerErrorCode.RUNTIME_MISMATCH,
            }:
                raise
            model = self._read(planning_run_id)
            if "runtime_replan" not in model.aggregate.prepared_artifacts:
                raise
            work, _ = self._select_work(model, work_item_id)
            job = self._worker_repository.ensure_job(
                work.document, now=self._now()
            ).record
            if (
                job.status is not JobStatus.RUNNING
                or job.worker_id != worker_id
                or job.lease_expires_at is None
                or self._now() >= job.lease_expires_at
            ):
                raise
            if isinstance(error, RuntimeExtensionError):
                self._fail_extension_execution(
                    job=job, worker_id=worker_id, work=work.document, error=error
                )
            if model.aggregate.document["state"] not in PLANNING_RUN_TERMINAL_STATES:
                model = self._transition(
                    model,
                    work=work.document,
                    to_state="FAILED",
                    artifacts=model.aggregate.document["artifacts"],
                    bind_attempt=True,
                )
                code = str(
                    getattr(
                        error,
                        "reason",
                        getattr(error, "code", "REPLAN_EXECUTION_FAILED"),
                    )
                )
                self._worker_repository.complete(
                    job.job_id,
                    worker_id=worker_id,
                    now=self._now(),
                    succeeded=False,
                    failure_code=code,
                )
                return self._terminal_execution(
                    job=job,
                    work=work.document,
                    state=model.aggregate.document["state"],
                    checkpoint_replayed=self._checkpoints.get(work_item_id) is not None,
                    publication_replayed=False,
                )
            return self._complete_terminal_job(
                job=job,
                worker_id=worker_id,
                work=work.document,
                state=model.aggregate.document["state"],
                checkpoint_replayed=self._checkpoints.get(work_item_id) is not None,
                publication_replayed=False,
            )

    def _timeout(self, model: Any, *, work: Any, job: Any, worker_id: str) -> Any:
        outcome = super()._timeout(model, work=work, job=job, worker_id=worker_id)
        current = self._read(work["planning_run_id"])
        if current.aggregate.document["state"] not in PLANNING_RUN_TERMINAL_STATES:
            current = self._transition(
                current,
                work=work,
                to_state="FAILED",
                artifacts=current.aggregate.document["artifacts"],
                bind_attempt=True,
            )
        return replace(outcome, planning_run_state=current.aggregate.document["state"])

    def _execute(
        self, *, planning_run_id: str, work_item_id: str, worker_id: str
    ) -> Any:
        model = self._read(planning_run_id)
        frozen = model.aggregate.prepared_artifacts.get("runtime_replan")
        if frozen is None:
            return self._normal.execute(
                planning_run_id=planning_run_id,
                work_item_id=work_item_id,
                worker_id=worker_id,
            )
        work_value, _ = self._select_work(model, work_item_id)
        work = work_value.document
        self._verify_runtime(work)
        application = self._application
        if (
            frozen["policy"] != application.policy
            or frozen["binding_fingerprint"]
            != canonical_fingerprint(
                application.events._bindings.get(frozen["request"]["planning_scope_id"])
            )
            or frozen["limits"] != application.catalog.solve_limits
            or frozen["fingerprint"]
            != canonical_fingerprint(
                {k: v for k, v in frozen.items() if k != "fingerprint"}
            )
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="replan.input",
                message="Frozen replan configuration differs",
            )
        checkpoint = self._checkpoints.get(work_item_id)
        replayed_checkpoint = checkpoint is not None
        if checkpoint is not None and (
            checkpoint["planning_run_id"] != planning_run_id
            or checkpoint["input_fingerprint"] != frozen["fingerprint"]
            or checkpoint["work_fingerprint"] != work["work_item_fingerprint"]
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="replan.checkpoint",
                message="Checkpoint differs from work",
            )
        repository = self._worker_repository
        now = self._now()
        job = repository.ensure_job(work, now=now).record
        expired_without_checkpoint = False
        if (
            job.status is JobStatus.RUNNING
            and job.lease_expires_at is not None
            and now >= job.lease_expires_at
        ):
            job = repository.mark_expired_stalled(job.job_id, now=now)
            expired_without_checkpoint = checkpoint is None
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            # A timeout may have committed its job/attempt before the process
            # stopped. Finish the same run; never create another solve attempt.
            if (
                job.status is JobStatus.FAILED
                and model.aggregate.document["state"]
                not in PLANNING_RUN_TERMINAL_STATES
            ):
                model = self._transition(
                    model,
                    work=work,
                    to_state="FAILED",
                    artifacts=model.aggregate.document["artifacts"],
                    bind_attempt=True,
                )
            return self._terminal_execution(
                job=job,
                work=work,
                state=model.aggregate.document["state"],
                checkpoint_replayed=checkpoint is not None,
                publication_replayed=model.aggregate.document["state"] == "COMPLETED",
            )
        if job.status is JobStatus.RUNNING:
            reject_worker(
                PlanningRunWorkerErrorCode.LEASE_BUSY,
                field="replan.lease",
                message="Another Worker owns this work",
                retryable=True,
            )
        from app.domain.types import parse_utc_instant

        if now < parse_utc_instant(work["available_at_utc"]):
            reject_worker(
                PlanningRunWorkerErrorCode.NOT_AVAILABLE,
                field="replan.available",
                message="Work is not available",
                retryable=True,
            )
        job = repository.claim(
            job.job_id,
            worker_id=worker_id,
            now=now,
            lease_seconds=self._policy.lease_seconds,
        )
        model = self._read(planning_run_id)
        if model.aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
            return self._complete_terminal_job(
                job=job,
                worker_id=worker_id,
                work=work,
                state=model.aggregate.document["state"],
                checkpoint_replayed=checkpoint is not None,
                publication_replayed=model.aggregate.document["state"] == "COMPLETED",
            )
        if now >= parse_utc_instant(work["timeout_at_utc"]):
            return self._timeout(model, work=work, job=job, worker_id=worker_id)
        model = self._start_attempt(model, work=work)
        if expired_without_checkpoint:
            model = self._transition(
                model,
                work=work,
                to_state="FAILED",
                artifacts=model.aggregate.document["artifacts"],
                bind_attempt=True,
            )
            return self._complete_terminal_job(
                job=job,
                worker_id=worker_id,
                work=work,
                state="FAILED",
                checkpoint_replayed=False,
                publication_replayed=False,
            )
        with _HeartbeatGuard(
            repository=repository,
            job_id=job.job_id,
            worker_id=worker_id,
            policy=self._policy,
            clock=self._now,
        ) as guard:
            model = self._advance_to_solve(model, work=work, guard=guard)
            after_kpi: dict[str, Any] = {}
            outer = self

            def check_current() -> None:
                guard.beat()
                current = outer._read(planning_run_id)
                if current.aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
                    reject_worker(
                        PlanningRunWorkerErrorCode.RUN_CANCELLED,
                        field="replan.run",
                        message="Run became terminal",
                    )
                if outer._now() >= parse_utc_instant(work["timeout_at_utc"]):
                    reject_worker(
                        PlanningRunWorkerErrorCode.ATTEMPT_TIMED_OUT,
                        field="replan.timeout",
                        message="Work expired",
                    )
                with application.engine.begin() as connection:
                    application.checkpoint(connection, frozen["request"])

            class Strategy:
                def solve(self, *args: Any, **kwargs: Any) -> Any:
                    nonlocal checkpoint
                    check_current()
                    if checkpoint is None:
                        outer._invoke_extension_before_solve(
                            planning_run_id=planning_run_id, problem=frozen["problem"]
                        )
                        solved = LexicographicReplanStrategy().solve(*args, **kwargs)
                        metrics = None
                        if solved.candidate is not None:
                            metrics = {
                                "kpi": build_replan_kpi(
                                    snapshot=frozen["snapshot"],
                                    problem=frozen["problem"],
                                    report=solved.solver_report,
                                )
                            }
                            application.schemas.validate(
                                "urn:plantnexus:aps:schema:kpi:v3", metrics["kpi"]
                            )
                        check_current()
                        checkpoint = outer._checkpoints.put(
                            {
                                "version": "runtime-replan-checkpoint.v1",
                                "work_item_id": work_item_id,
                                "planning_run_id": planning_run_id,
                                "input_fingerprint": frozen["fingerprint"],
                                "work_fingerprint": work["work_item_fingerprint"],
                                "solver_report": solved.solver_report,
                                "round_reports": list(solved.round_reports),
                                "validation_reports": list(solved.validation_reports),
                                "result_metrics": metrics,
                            }
                        )
                    application.schemas.validate(
                        "urn:plantnexus:aps:schema:solver-report:v2",
                        checkpoint["solver_report"],
                    )
                    if checkpoint["result_metrics"] is not None:
                        rebuilt = build_replan_kpi(
                            snapshot=frozen["snapshot"],
                            problem=frozen["problem"],
                            report=checkpoint["solver_report"],
                        )
                        if rebuilt != checkpoint["result_metrics"]["kpi"]:
                            reject_worker(
                                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                                field="checkpoint.kpi",
                                message="Checkpoint KPI does not match actual candidate",
                            )
                        after_kpi.update(checkpoint["result_metrics"]["kpi"])
                    return LexicographicReplanResult(
                        checkpoint["solver_report"],
                        tuple(checkpoint["round_reports"]),
                        tuple(checkpoint["validation_reports"]),
                    )

            @contextmanager
            def transaction() -> Any:
                check_current()
                current = outer._read(planning_run_id)
                run = current.aggregate.document
                with application.engine.begin() as connection:
                    lock_run(
                        connection,
                        run_id=planning_run_id,
                        revision=run["revision"],
                        fingerprint=run["run_fingerprint"],
                        data_plane="SIMULATION",
                    )
                    application.checkpoint(connection, frozen["request"])
                    # The run write lock orders cancellation and result application.
                    locked_job = repository.lock_active_lease(
                        connection,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        now=outer._now(),
                    )
                    yield connection
                    if outer._now() >= parse_utc_instant(work["timeout_at_utc"]) or (
                        locked_job.lease_expires_at is None
                        or outer._now() >= locked_job.lease_expires_at
                    ):
                        reject_worker(
                            PlanningRunWorkerErrorCode.ATTEMPT_TIMED_OUT,
                            field="replan.commit",
                            message="Result deadline expired",
                        )
                    local = copy(outer)
                    scoped = TransactionEngine(application.engine, connection)
                    local._orchestration = application.orchestrator(scoped)
                    lineage = SqlAlchemyReplanLineageRepository(
                        cast(Any, scoped), data_plane=application.plane
                    )
                    stored = lineage.get_result_for_attempt_in_transaction(
                        connection, frozen["attempt"]["attempt_id"]
                    )
                    if stored is None:
                        return
                    if checkpoint["solver_report"]["candidate"] is not None:
                        applied = lineage.get_applied_result_for_attempt_in_transaction(
                            connection, frozen["attempt"]["attempt_id"]
                        )
                        terminal = None
                    else:
                        applied = None
                        terminal = (
                            lineage.get_terminal_result_for_attempt_in_transaction(
                                connection, frozen["attempt"]["attempt_id"]
                            )
                        )
                    artifacts = local._base_artifacts(work)
                    if applied is None and terminal is None:
                        raise ValueError("Stored result has no complete evidence")
                    report = cast(
                        Any,
                        applied.solver_report
                        if applied is not None
                        else cast(Any, terminal).solver_report,
                    )
                    artifacts["solver_report"] = artifact(
                        "solver-report.v2",
                        report["report_id"],
                        report["report_fingerprint"],
                    )
                    current = local._read(planning_run_id)
                    if applied is not None:
                        candidate = report["candidate"]
                        artifacts["planning_solution"] = artifact(
                            "replan-candidate.v1",
                            "replan-candidate-"
                            + candidate["candidate_fingerprint"][7:],
                            candidate["candidate_fingerprint"],
                        )
                        current = local._transition(
                            current,
                            work=work,
                            to_state="SOLVED",
                            artifacts=artifacts,
                            bind_attempt=True,
                        )
                        current = local._transition(
                            current,
                            work=work,
                            to_state="VERIFYING",
                            artifacts=artifacts,
                            bind_attempt=True,
                        )
                        artifacts["validation_report"] = cast(
                            Any, applied.change_report
                        )["lineage"]["validation_report"]
                        schedule = cast(Any, applied.change_report)[
                            "new_schedule_version"
                        ]
                        artifacts["schedule_version"] = artifact(
                            "schedule-version.v2",
                            schedule["schedule_version_id"],
                            schedule["content_fingerprint"],
                        )
                        local._transition(
                            current,
                            work=work,
                            to_state="COMPLETED",
                            artifacts=artifacts,
                            bind_attempt=True,
                        )
                    else:
                        local._transition(
                            current,
                            work=work,
                            to_state=report["planning_run_outcome"]["state"],
                            artifacts=artifacts,
                            bind_attempt=True,
                        )

            attempt = frozen["attempt"]
            created = frozen["created_context"]
            admission = None
            if self._extension_executor is not None:
                admission = self._extension_executor.candidate_admission(
                    scope=self._extension_scope(planning_run_id),
                    planning_run_id=planning_run_id,
                    runtime_identity=lambda: self._current_runtime(planning_run_id),
                    validator_factory=lambda: self._validator,
                )
            service = RuntimeReplanService(
                transaction_factory=transaction,
                schedule_repository=application.schedules,
                publication_repository=application.publications,
                snapshot_repository=application.events._snapshots,
                request_repository=application.requests,
                lineage_repository=application.lineage,
                audit_repository=application.audits,
                strategy=Strategy(),
                admission=admission,
            )
            service.execute(
                ReplanApplicationInput(
                    request=frozen["request"],
                    **frozen["build_plan"],
                    policy=frozen["policy"],
                    limits=frozen["limits"],
                    before_kpi=frozen["before_kpi"],
                    after_kpi=after_kpi,
                ),
                ReplanApplicationContext(
                    data_plane="SIMULATION",
                    environment=created["environment"],
                    production_binding=False,
                    actor_ref=created["actor_reference"],
                    idempotency_key_reference=attempt["idempotency_key_reference"],
                    correlation_id=attempt["correlation_id"],
                    occurred_at_utc=attempt["created_at_utc"],
                    planning_run_id=planning_run_id,
                    attempt_number=attempt["attempt_number"],
                    code_commit=created["code_commit"],
                ),
            )
            guard.check()
        return self._complete_terminal_job(
            job=job,
            worker_id=worker_id,
            work=work,
            state=self._read(planning_run_id).aggregate.document["state"],
            checkpoint_replayed=replayed_checkpoint,
            publication_replayed=False,
        )

    def _recover_expired_job(
        self, job_id: str, *, recovery_worker_id: str, now: Any
    ) -> Any:
        binding = self._worker_repository.get_binding(job_id)
        if binding is not None:
            model = self._read(binding.planning_run_id)
            if "runtime_replan" in model.aggregate.prepared_artifacts:
                self.execute(
                    planning_run_id=binding.planning_run_id,
                    work_item_id=binding.work_item_id,
                    worker_id=recovery_worker_id,
                )
                return PlanningRunWorkerRecovery(
                    job_id, binding.planning_run_id, binding.attempt_id, "TERMINAL_ACK"
                )
        return self._normal._recover_expired_job(
            job_id, recovery_worker_id=recovery_worker_id, now=now
        )
