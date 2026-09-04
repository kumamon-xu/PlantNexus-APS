"""Single-worker durable execution for Demo reset, planning, and urgent jobs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import cast

from .orchestration import (
    ControlJobStageSink,
    DemoOperationError,
    InitialPlanningOrchestrator,
    ResetOrchestrator,
)
from .persistence import (
    ControlStore,
    DemoPersistenceError,
    DemoRuntimePaths,
    JobRecord,
    JobRegistration,
    fingerprint,
    key_reference,
)
from .replanning import UrgentReplanOrchestrator
from .urgent import UrgentOrderCommand


@dataclass(frozen=True, slots=True)
class JobAccepted:
    job_id: str
    job_kind: str
    run_id: str | None
    status: str
    replayed: bool

    @property
    def document(self) -> dict[str, object]:
        return {
            "job_accepted_version": "cnc-demo-job-accepted.v1",
            "job_id": self.job_id,
            "job_kind": self.job_kind,
            "run_id": self.run_id,
            "status": self.status,
            "replayed": self.replayed,
        }


class DemoJobRunner:
    """At-most-one local worker; queue state is authoritative in control.db."""

    def __init__(
        self,
        *,
        repository_root: Path,
        paths: DemoRuntimePaths,
        control: ControlStore,
        auto_resume_queued: bool = True,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.paths = paths
        self.control = control
        self.reset = ResetOrchestrator(
            repository_root=self.repository_root, paths=paths, control=control
        )
        self.initial_plan = InitialPlanningOrchestrator(
            repository_root=self.repository_root, paths=paths, control=control
        )
        self.urgent_replan = UrgentReplanOrchestrator(
            repository_root=self.repository_root, paths=paths, control=control
        )
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="plantnexus-demo"
        )
        self._lock = Lock()
        self._futures: dict[str, Future[JobRecord]] = {}
        self.control.recover_interrupted()
        if auto_resume_queued:
            for job in self.control.queued_jobs():
                self.submit(job.job_id)

    def submit(self, job_id: str) -> Future[JobRecord]:
        with self._lock:
            existing = self._futures.get(job_id)
            if existing is not None:
                return existing
            future = self._executor.submit(self.run_inline, job_id)
            self._futures[job_id] = future
            return future

    def run_inline(self, job_id: str) -> JobRecord:
        job = self.control.get_job(job_id)
        if job is None:
            raise DemoPersistenceError(
                "JOB_NOT_FOUND", field="job_id", message="job does not exist"
            )
        if job.status == "SUCCEEDED":
            return job
        running = self.control.start_job(job_id, worker_id="demo-worker-1")
        stages = ControlJobStageSink(self.control, job_id)
        try:
            if running.job_kind == "RESET":
                profile_name = running.request.get("profile_name")
                expected = running.request.get("expected_active_run_id")
                if not isinstance(profile_name, str) or (
                    expected is not None and not isinstance(expected, str)
                ):
                    raise DemoOperationError(
                        "INVALID_REQUEST",
                        field="reset.request",
                        message="stored reset request is invalid",
                    )
                if running.run_id is None:
                    raise DemoOperationError(
                        "INVALID_REQUEST",
                        field="reset.run_id",
                        message="stored reset run identity is missing",
                    )
                result = self.reset.execute(
                    run_id=running.run_id,
                    profile_name=profile_name,
                    expected_active_run_id=cast(str | None, expected),
                    created_at_utc=running.created_at_utc,
                    stages=stages,
                ).document
            elif running.job_kind == "INITIAL_PLAN":
                expected_run_id = running.request.get("expected_run_id")
                if not isinstance(expected_run_id, str):
                    raise DemoOperationError(
                        "INVALID_REQUEST",
                        field="initial_plan.expected_run_id",
                        message="stored planning request is invalid",
                    )
                result = self.initial_plan.execute(
                    run_id=expected_run_id,
                    request_fingerprint=running.request_fingerprint,
                    idempotency_key_reference=running.key_reference,
                    correlation_id=running.correlation_id,
                    occurred_at_utc=running.created_at_utc,
                    stages=stages,
                ).document
            elif running.job_kind == "URGENT_REPLAN":
                try:
                    command = UrgentOrderCommand.model_validate(running.request)
                except ValueError as error:
                    raise DemoOperationError(
                        "INVALID_REQUEST",
                        field="urgent_order.request",
                        message="stored urgent request is invalid",
                    ) from error
                result = self.urgent_replan.execute(
                    command=command,
                    idempotency_key_reference=running.key_reference,
                    correlation_id=running.correlation_id,
                    occurred_at_utc=running.created_at_utc,
                    stages=stages,
                ).document
            else:
                raise DemoOperationError(
                    "INVALID_REQUEST",
                    field="job_kind",
                    message="job kind is not supported by this worker",
                )
            return self.control.complete_job(job_id, result)
        except DemoOperationError as error:
            return self.control.fail_job(job_id, error_code=error.code)
        except DemoPersistenceError as error:
            return self.control.fail_job(job_id, error_code=error.code)
        except Exception:  # noqa: BLE001 - never persist or expose raw exception text
            return self.control.fail_job(job_id, error_code="JOB_EXECUTION_FAILED")

    def wait(self, job_id: str, *, timeout: float = 60.0) -> JobRecord:
        with self._lock:
            future = self._futures.get(job_id)
        if future is None:
            record = self.control.get_job(job_id)
            if record is None:
                raise DemoPersistenceError(
                    "JOB_NOT_FOUND", field="job_id", message="job does not exist"
                )
            return record
        return future.result(timeout=timeout)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)


class DemoJobService:
    """Register idempotent commands before handing them to the worker."""

    def __init__(self, *, control: ControlStore, runner: DemoJobRunner) -> None:
        self.control = control
        self.runner = runner

    @staticmethod
    def _accepted(registration: JobRegistration) -> JobAccepted:
        job = registration.job
        return JobAccepted(
            job_id=job.job_id,
            job_kind=job.job_kind,
            run_id=job.run_id,
            status=job.status,
            replayed=registration.replayed,
        )

    def accept_reset(
        self,
        *,
        profile_name: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> JobAccepted:
        key_ref = key_reference(idempotency_key)
        existing = self.control.get_job_by_idempotency(
            job_kind="RESET", key_reference=key_ref
        )
        if existing is not None:
            if existing.request.get("profile_name") != profile_name:
                raise DemoPersistenceError(
                    "IDEMPOTENCY_CONFLICT",
                    field="Idempotency-Key",
                    message="same key is bound to different input",
                )
            if existing.status == "INTERRUPTED":
                self.runner.submit(existing.job_id)
            return self._accepted(JobRegistration(existing, replayed=True))
        active = self.control.active_run()
        expected_active = None if active is None else active.run_id
        request = {
            "request_version": "cnc-demo-reset-request.v1",
            "profile_name": profile_name,
            "expected_active_run_id": expected_active,
        }
        request_fingerprint = fingerprint(request)
        run_id = "run-" + sha256(
            f"RESET:{key_ref}".encode("utf-8")
        ).hexdigest()[:32]
        registration = self.control.register_job(
            job_kind="RESET",
            run_id=run_id,
            expected_active_run_id=expected_active,
            request_fingerprint=request_fingerprint,
            key_reference=key_ref,
            correlation_id=correlation_id,
            request_document=request,
        )
        if not registration.replayed and registration.job.status == "QUEUED":
            self.runner.submit(registration.job.job_id)
        return self._accepted(registration)

    def accept_initial_plan(
        self,
        *,
        expected_run_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> JobAccepted:
        request = {
            "request_version": "cnc-demo-initial-plan-request.v1",
            "expected_run_id": expected_run_id,
        }
        registration = self.control.register_job(
            job_kind="INITIAL_PLAN",
            run_id=expected_run_id,
            expected_active_run_id=expected_run_id,
            request_fingerprint=fingerprint(request),
            key_reference=key_reference(idempotency_key),
            correlation_id=correlation_id,
            request_document=request,
        )
        if registration.job.status == "INTERRUPTED" or (
            not registration.replayed and registration.job.status == "QUEUED"
        ):
            self.runner.submit(registration.job.job_id)
        return self._accepted(registration)

    def accept_urgent_order(
        self,
        *,
        command: UrgentOrderCommand,
        idempotency_key: str,
        correlation_id: str,
    ) -> JobAccepted:
        request = command.model_dump(mode="json")
        key_ref = key_reference(idempotency_key)
        existing = self.control.get_job_by_idempotency(
            job_kind="URGENT_REPLAN", key_reference=key_ref
        )
        if existing is not None:
            if existing.request != request:
                raise DemoPersistenceError(
                    "IDEMPOTENCY_CONFLICT",
                    field="Idempotency-Key",
                    message="same key is bound to different input",
                )
            if existing.status == "INTERRUPTED":
                self.runner.submit(existing.job_id)
            return self._accepted(JobRegistration(existing, replayed=True))
        # The stale run/current PUBLISHED/base and business-input checks are
        # intentionally read-only and precede durable job registration.
        self.runner.urgent_replan.preflight(command)
        registration = self.control.register_job(
            job_kind="URGENT_REPLAN",
            run_id=command.expected_run_id,
            expected_active_run_id=command.expected_run_id,
            request_fingerprint=fingerprint(request),
            key_reference=key_ref,
            correlation_id=correlation_id,
            request_document=request,
        )
        if not registration.replayed and registration.job.status == "QUEUED":
            self.runner.submit(registration.job.job_id)
        return self._accepted(registration)


__all__ = [
    "DemoJobRunner",
    "DemoJobService",
    "JobAccepted",
]
