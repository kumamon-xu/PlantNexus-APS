"""Generate TASK-P8-05 Solver Worker reliability and engineering evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from time import perf_counter_ns
import tempfile
import tracemalloc
from typing import Any, Never, cast

from alembic import command
from alembic.config import Config
from celery import Celery
from sqlalchemy import Engine, create_engine, text

from app.application.canonical_ingress import (
    CanonicalIngressApplicationService,
    CanonicalIngressBuildPlan,
    TrustedCanonicalIngressContext,
)
from app.application.planning_runs import (
    PlanningRunCommandContext,
    PlanningRunOrchestrationService,
)
from app.application.schedule_versions import (
    ValidatedSolutionToScheduleVersionService,
)
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    FrozenSchemaCatalog,
    canonical_fingerprint,
    canonical_json_bytes,
    idempotency_key_reference,
    request_fingerprint,
)
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.planning_run_repository import (
    SqlAlchemyPlanningRunRepository,
)
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.contracts import JobStatus
from app.jobs.planning_run_solver_worker import (
    PlanningRunSolverWorker,
    WorkerDisposition,
    WorkerReliabilityPolicy,
)
from app.jobs.planning_run_task import (
    PLANNING_RUN_SOLVER_TASK,
    register_planning_run_task,
)
from app.jobs.planning_run_worker_contracts import PlanningRunResolvedInputs
from app.jobs.planning_run_worker_repository import (
    SqlAlchemyPlanningRunWorkerRepository,
)
from app.planning.contracts import contract_fingerprint
from app.planning.policy import simulation_delivery_policy, simulation_solve_limits
from app.planning.policy.contracts import (
    PlanningPolicyDocument,
    SolveLimitsDocument,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.strategies import GlobalCpSatStrategy, GlobalStrategyResult
from app.planning.validation.problem_schedule_validator import (
    ProblemScheduleValidator,
)
from app.snapshots import import_package_id_for


type JsonObject = dict[str, Any]

REPORT_VERSION = "p8-solver-worker-reliability-report.v1"
BENCHMARK_REPORT_VERSION = "p8-solver-worker-engineering-benchmark.v1"
PROFILE_VERSION = "p8-solver-worker-engineering-profile.v1"
TASK_ID = "TASK-P8-05"
TEST_ID = "TEST-P8-SOLVER-WORKER-001"
DIFF_BASE = "f8c962188295c6e9d3852cc8bb8708caf3203adc"
PROFILE_RELATIVE = "benchmarks/p8/solver-worker-engineering-profile.v1.json"
MIGRATION_HEAD = "0008_planning_run_solver_worker"
EVIDENCE_NOW = datetime(2026, 9, 5, 0, 0, 10, tzinfo=UTC)
AUTHORITY_REFERENCE = "authority:p8-worker-evidence"
MAPPING_FINGERPRINT = f"sha256:{'2' * 64}"


class WorkerCheckError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> Never:
    raise WorkerCheckError(code)


def _load_json(path: Path) -> JsonObject:
    if path.is_symlink() or not path.is_file():
        _fail("INPUT_NOT_REGULAR_FILE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("INPUT_PARSE_FAILED")
    if not isinstance(value, dict):
        _fail("INPUT_NOT_OBJECT")
    return cast(JsonObject, value)


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _file_fingerprint(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _check(check_id: str, passed: bool, evidence: object) -> JsonObject:
    return {
        "check_id": check_id,
        "result": "PASS" if passed else "FAIL",
        "evidence": evidence,
    }


def _load_profile(path: Path) -> JsonObject:
    profile = _load_json(path)
    if set(profile) != {
        "profile_version",
        "profile_id",
        "scenario_id",
        "data_plane",
        "environment",
        "synthetic",
        "random_seed",
        "measured_runs",
        "heartbeat_seconds",
        "lease_seconds",
        "max_wall_time_seconds",
        "max_workers",
        "thresholds",
        "production_sla",
    }:
        _fail("PROFILE_FIELD_SET_INVALID")
    if (
        profile["profile_version"] != PROFILE_VERSION
        or profile["data_plane"] != "SIMULATION"
        or profile["environment"] != "TEST"
        or profile["synthetic"] is not True
        or profile["measured_runs"] != 1
        or profile["max_workers"] != 1
        or profile["thresholds"] is not None
        or profile["production_sla"] != "NOT_DEFINED"
        or not isinstance(profile["heartbeat_seconds"], int)
        or not isinstance(profile["lease_seconds"], int)
        or profile["heartbeat_seconds"] < 1
        or profile["lease_seconds"] <= profile["heartbeat_seconds"]
    ):
        _fail("PROFILE_SEMANTICS_INVALID")
    return profile


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value != "uncommitted" and (
        len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail("CODE_COMMIT_INVALID")
    return value


def _runtime_resolution(root: Path) -> JsonObject:
    accepted = _load_json(
        root
        / "schemas"
        / "samples"
        / "canonical-ingress-result.v1.accepted.synthetic.json"
    )
    value = cast(Mapping[str, object], accepted["accepted"])["runtime_resolution"]
    if not isinstance(value, Mapping):
        _fail("RUNTIME_RESOLUTION_INVALID")
    return deepcopy(dict(value))


def _planning_policy() -> JsonObject:
    return cast(JsonObject, simulation_delivery_policy())


def _solve_limits(profile: Mapping[str, object]) -> JsonObject:
    return cast(
        JsonObject,
        simulation_solve_limits(
            limits_id="LIMITS-P8-WORKER-EVIDENCE-001",
            limits_revision="1.0.0",
            source_record_id="P8-WORKER-EVIDENCE-LIMITS-001",
            max_wall_time_seconds=cast(float, profile["max_wall_time_seconds"]),
            max_workers=cast(int, profile["max_workers"]),
            random_seed=cast(int, profile["random_seed"]),
        ),
    )


def _request_document(
    root: Path,
    *,
    policy: Mapping[str, object],
    limits: Mapping[str, object],
) -> JsonObject:
    payload = _load_json(
        root / "schemas" / "samples" / "import-package.v2.synthetic.json"
    )
    payload["package_id"] = import_package_id_for(payload)
    records = cast(Mapping[str, object], payload["records"])
    collections = sorted(
        name for name, values in records.items() if isinstance(values, list) and values
    )
    document: JsonObject = {
        "canonical_ingress_request_version": "canonical-ingress-request.v1",
        "schema_set_version": "2.10.0",
        "ingress_policy_version": "canonical-ingress-policy.v1",
        "canonicalization_version": "canonical-json.v1",
        "operation": "CREATE_PLANNING_RUN",
        "request_id": "REQUEST-P8-WORKER-EVIDENCE-001",
        "correlation_id": "CORRELATION-P8-WORKER-EVIDENCE-001",
        "idempotency_key": "p8-worker-evidence-key-0001",
        "request_fingerprint": "",
        "requested_scope": {
            "tenant_id": "TENANT-P8-APPLICATION",
            "factory_id": "FACTORY-001",
            "planning_scope_id": "PLANNING-P8-APPLICATION",
            "data_plane": "SIMULATION",
            "environment": "TEST",
        },
        "source_authority": {
            "authority_policy_version": "canonical-authority-policy.v1",
            "bindings": [
                {
                    "source_system": "schema_sample",
                    "source_version": "1.0.0",
                    "authority_reference": AUTHORITY_REFERENCE,
                    "canonical_collections": collections,
                }
            ],
            "mapping_provenance": [
                {
                    "source_system": "schema_sample",
                    "source_version": "1.0.0",
                    "mapping_profile_id": "MAPPING-P8-WORKER-EVIDENCE-001",
                    "mapping_profile_version": "1.0.0",
                    "mapping_profile_fingerprint": MAPPING_FINGERPRINT,
                }
            ],
        },
        "planning_inputs": {
            "planning_policy": {
                "document_version": policy["planning_policy_version"],
                "artifact_id": policy["policy_id"],
                "fingerprint": contract_fingerprint(policy),
            },
            "solve_limits": {
                "document_version": limits["solve_limits_version"],
                "artifact_id": limits["limits_id"],
                "fingerprint": contract_fingerprint(limits),
            },
        },
        "payload_fingerprint": canonical_fingerprint(payload),
        "payload": payload,
    }
    document["request_fingerprint"] = request_fingerprint(document)
    return document


def _ingress_context(
    request: Mapping[str, object],
    *,
    runtime_resolution: Mapping[str, object],
    code_commit: str,
) -> TrustedCanonicalIngressContext:
    scope = cast(Mapping[str, object], request["requested_scope"])
    return TrustedCanonicalIngressContext.create(
        actor_reference="actor:p8-worker-evidence",
        auth_policy_version="headless-auth-policy.v1",
        tenant_id=cast(str, scope["tenant_id"]),
        factory_id=cast(str, scope["factory_id"]),
        planning_scope_id=cast(str, scope["planning_scope_id"]),
        data_plane="SIMULATION",
        environment="TEST",
        production_binding=False,
        authorized_authority_references=(AUTHORITY_REFERENCE,),
        authorized_mapping_fingerprints=(MAPPING_FINGERPRINT,),
        runtime_resolution=runtime_resolution,
        build_plan=CanonicalIngressBuildPlan.create(
            planning_inputs=cast(Mapping[str, object], request["planning_inputs"]),
            cutoff_at_utc="2026-08-20T00:00:00Z",
            tick_seconds=60,
            horizon_start_utc="2026-08-20T00:00:00Z",
            horizon_end_utc="2026-08-21T00:00:00Z",
            priority_facts={
                "DEMAND-001": {
                    "priority_weight": 2,
                    "source_system": "plantnexus-synthetic-policy",
                    "source_version": "1.0.0",
                    "source_record_id": "P8-WORKER-EVIDENCE-DEMAND-001",
                }
            },
        ),
        occurred_at_utc="2026-09-05T00:00:00Z",
        code_commit=code_commit,
    )


class _FixedClock:
    def __call__(self) -> datetime:
        return EVIDENCE_NOW


class _ContextProvider:
    def __init__(self, *, code_commit: str) -> None:
        self._code_commit = code_commit

    def context_for(
        self, planning_run_id: str, *, occurred_at_utc: str
    ) -> PlanningRunCommandContext:
        del planning_run_id
        return PlanningRunCommandContext.create(
            actor_reference="actor:p8-solver-worker-evidence",
            capabilities=("view", "edit"),
            auth_policy_version="headless-auth-policy.v1",
            tenant_id="TENANT-P8-APPLICATION",
            factory_id="FACTORY-001",
            planning_scope_id="PLANNING-P8-APPLICATION",
            data_plane="SIMULATION",
            environment="TEST",
            production_binding=False,
            correlation_id="CORRELATION-P8-WORKER-EVIDENCE-001",
            occurred_at_utc=occurred_at_utc,
            code_commit=self._code_commit,
        )


class _RuntimeProvider:
    def __init__(self, document: Mapping[str, object]) -> None:
        self._document = deepcopy(dict(document))

    def current_resolution(self, planning_run_id: str) -> Mapping[str, object]:
        del planning_run_id
        return deepcopy(self._document)


class _InputResolver:
    def __init__(self, resolved: PlanningRunResolvedInputs) -> None:
        self._resolved = resolved

    def resolve(self, work_item: Mapping[str, object]) -> PlanningRunResolvedInputs:
        del work_item
        return self._resolved


class _MeasuredSolver:
    def __init__(self) -> None:
        self._delegate = GlobalCpSatStrategy()
        self.calls = 0
        self.elapsed_ns = 0

    def solve(
        self,
        problem: Mapping[str, object],
        policy: Mapping[str, object],
        limits: Mapping[str, object],
        *,
        planning_run_id: str,
        code_commit: str,
    ) -> GlobalStrategyResult:
        started = perf_counter_ns()
        try:
            return self._delegate.solve(
                cast(PlanningProblemDocumentV2, problem),
                cast(PlanningPolicyDocument, policy),
                cast(SolveLimitsDocument, limits),
                planning_run_id=planning_run_id,
                code_commit=code_commit,
            )
        finally:
            self.calls += 1
            self.elapsed_ns += perf_counter_ns() - started


class _MeasuredValidator:
    def __init__(self) -> None:
        self._delegate = ProblemScheduleValidator()
        self.calls = 0

    def validate(
        self, problem: Mapping[str, object], candidate: Mapping[str, object]
    ) -> Mapping[str, object]:
        self.calls += 1
        return self._delegate.validate(problem, candidate)


def _alembic_configuration(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(root / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))


def run_checks(root: Path, profile_path: Path) -> tuple[JsonObject, JsonObject]:
    profile = _load_profile(profile_path)
    policy = _planning_policy()
    limits = _solve_limits(profile)
    request = _request_document(root, policy=policy, limits=limits)
    runtime = _runtime_resolution(root)
    code_commit = _code_commit()
    with tempfile.TemporaryDirectory(prefix="plantnexus-p8-worker-") as directory:
        database_path = Path(directory) / "evidence.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = _alembic_configuration(root, database_url)
        command.upgrade(configuration, MIGRATION_HEAD)
        engine = create_engine(database_url)
        try:
            plane = WorkspaceDataPlane.SIMULATION
            ingress_repository = SqlAlchemyCanonicalIngressRepository(
                engine, data_plane=plane
            )
            ingress_context = _ingress_context(
                request,
                runtime_resolution=runtime,
                code_commit=code_commit,
            )
            ingress = CanonicalIngressApplicationService(
                contract=CanonicalIngressContract.from_schema_directory(
                    root / "schemas" / "json"
                ),
                repository=ingress_repository,
            ).submit(canonical_json_bytes(request), context=ingress_context)
            record = ingress_repository.get_by_idempotency(
                scope_fingerprint=ingress_context.idempotency_scope_fingerprint(),
                key_reference=idempotency_key_reference(
                    cast(str, request["idempotency_key"])
                ),
            )
            if ingress.result.get("disposition") != "ACCEPTED" or record is None:
                _fail("CANONICAL_INGRESS_NOT_ACCEPTED")

            orchestration = PlanningRunOrchestrationService(
                schemas=FrozenSchemaCatalog.from_directory(root / "schemas" / "json"),
                repository=SqlAlchemyPlanningRunRepository(engine, data_plane=plane),
            )
            context_provider = _ContextProvider(code_commit=code_commit)
            created = orchestration.materialize(
                record,
                context=context_provider.context_for(
                    "RUN-P8-WORKER-EVIDENCE-PENDING",
                    occurred_at_utc="2026-09-05T00:00:00Z",
                ),
                available_at_utc="2026-09-05T00:00:01Z",
                timeout_at_utc="2026-09-05T01:00:00Z",
            )
            if created.work_item is None:
                _fail("WORK_ITEM_NOT_MATERIALIZED")
            work = created.work_item.document
            resolved = PlanningRunResolvedInputs(
                import_quality_report=cast(
                    Mapping[str, object], record.document["import_quality_report"]
                ),
                snapshot=record.snapshot.document,
                problem=record.problem.document,
                planning_policy=policy,
                solve_limits=limits,
            )
            solver = _MeasuredSolver()
            validator = _MeasuredValidator()
            worker_repository = SqlAlchemyPlanningRunWorkerRepository(
                engine, data_plane=plane
            )
            worker = PlanningRunSolverWorker(
                orchestration=orchestration,
                worker_repository=worker_repository,
                input_resolver=_InputResolver(resolved),
                runtime_provider=_RuntimeProvider(runtime),
                context_provider=context_provider,
                solver=solver,
                validator=validator,
                publisher=ValidatedSolutionToScheduleVersionService(
                    data_plane=plane.value,
                    transaction_factory=engine.begin,
                    schedule_repository=SqlAlchemyScheduleVersionRepository(
                        engine, data_plane=plane
                    ),
                    audit_repository=SqlAlchemyAuditRepository(
                        engine, data_plane=plane
                    ),
                ),
                policy=WorkerReliabilityPolicy(
                    heartbeat_seconds=cast(int, profile["heartbeat_seconds"]),
                    lease_seconds=cast(int, profile["lease_seconds"]),
                ),
                clock=_FixedClock(),
            )
            run_id = cast(str, work["planning_run_id"])
            work_id = cast(str, work["work_item_id"])
            tracemalloc.start()
            started = perf_counter_ns()
            try:
                first = worker.execute(
                    planning_run_id=run_id,
                    work_item_id=work_id,
                    worker_id="worker:p8-evidence-primary",
                )
                first_elapsed_ns = perf_counter_ns() - started
                replay_started = perf_counter_ns()
                replay = worker.execute(
                    planning_run_id=run_id,
                    work_item_id=work_id,
                    worker_id="worker:p8-evidence-redelivery",
                )
                replay_elapsed_ns = perf_counter_ns() - replay_started
                _, peak_allocated_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

            final = orchestration.read(
                run_id,
                context=context_provider.context_for(
                    run_id, occurred_at_utc="2026-09-05T00:00:20Z"
                ),
            )
            job = worker_repository.get_job(first.job_id)
            checkpoint = worker_repository.get_result_for_work_item(work_id)
            if job is None or checkpoint is None:
                _fail("WORKER_EVIDENCE_MISSING")
            checkpoint_document = checkpoint.document
            counts = {
                "worker_jobs": _count(engine, "planning_run_worker_jobs"),
                "worker_results": _count(engine, "planning_run_worker_results"),
                "schedule_versions": _count(engine, "schedule_versions"),
                "schedule_audits": _count(engine, "audit_events"),
            }
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")

    recovery_test = (
        root / "backend" / "tests" / "integration" / "test_p8_solver_worker_recovery.py"
    )
    security_test = (
        root / "backend" / "tests" / "security" / "test_p8_solver_worker_security.py"
    )
    migration = (
        root
        / "backend"
        / "migrations"
        / "versions"
        / "0008_planning_run_solver_worker.py"
    )
    task_source = root / "backend" / "app" / "jobs" / "planning_run_task.py"
    recovery_text = recovery_test.read_text(encoding="utf-8")
    migration_text = migration.read_text(encoding="utf-8")
    task_text = task_source.read_text(encoding="utf-8")
    celery = Celery("p8-worker-check", broker="memory://")
    register_planning_run_task(celery)
    registered_task = celery.tasks[PLANNING_RUN_SOLVER_TASK]
    artifacts = cast(Mapping[str, object], final.aggregate.document["artifacts"])
    checks = [
        _check(
            "durable-real-solver-path",
            first.disposition is WorkerDisposition.COMPLETED
            and final.aggregate.document["state"] == "COMPLETED"
            and final.attempts[-1].document["status"] == "SUCCEEDED",
            {
                "planning_run_state": final.aggregate.document["state"],
                "attempt_status": final.attempts[-1].document["status"],
                "solver_calls": solver.calls,
            },
        ),
        _check(
            "fresh-independent-validator",
            validator.calls >= 2
            and checkpoint_document["outcome_state"] == "COMPLETED"
            and artifacts["validation_report"] is not None,
            {
                "validator_calls": validator.calls,
                "checkpoint_outcome": checkpoint_document["outcome_state"],
            },
        ),
        _check(
            "immutable-result-before-publication",
            counts
            == {
                "worker_jobs": 1,
                "worker_results": 1,
                "schedule_versions": 1,
                "schedule_audits": 1,
            }
            and all(value is not None for value in artifacts.values()),
            counts,
        ),
        _check(
            "exact-redelivery-one-business-result",
            replay.disposition is WorkerDisposition.EXACT_REPLAY
            and solver.calls == 1
            and counts["worker_results"] == counts["schedule_versions"] == 1,
            {
                "redelivery_disposition": replay.disposition.value,
                "solver_calls": solver.calls,
                "worker_results": counts["worker_results"],
                "schedule_versions": counts["schedule_versions"],
            },
        ),
        _check(
            "lease-cas-terminal-ack",
            job.status is JobStatus.SUCCEEDED
            and job.attempt == 1
            and job.lease_expires_at is None,
            {
                "job_status": job.status.value,
                "operational_attempt": job.attempt,
                "lease_cleared": job.lease_expires_at is None,
            },
        ),
        _check(
            "failure-injection-and-recovery-coverage",
            all(
                name in recovery_text
                for name in (
                    "test_concurrent_duplicate_delivery_cannot_steal_active_lease",
                    "test_cancel_during_solver_never_checkpoints_or_publishes",
                    "test_work_timeout_wins_over_a_later_solver_candidate",
                    "test_process_crash_times_out_attempt_then_explicit_retry_completes",
                    "test_crash_after_checkpoint_requeues_same_work_without_second_solve",
                    "test_crash_after_completed_cas_replays_checkpoint_without_resolve",
                    "test_result_transaction_outage_leaves_no_partial_business_result",
                    "test_independent_validator_rejects_a_tampered_solver_candidate",
                )
            ),
            {
                "test_source_fingerprint": _file_fingerprint(recovery_test),
                "required_scenarios": 8,
            },
        ),
        _check(
            "append-only-migration-and-replay",
            all(
                token in migration_text
                for token in (
                    '"planning_run_worker_jobs"',
                    '"planning_run_worker_results"',
                    "append-only",
                    "0007_planning_run_orchestration",
                )
            ),
            {
                "migration_head": MIGRATION_HEAD,
                "migration_fingerprint": _file_fingerprint(migration),
            },
        ),
        _check(
            "json-only-server-bound-task",
            registered_task.acks_late is True
            and registered_task.reject_on_worker_lost is True
            and registered_task.serializer == "json"
            and registered_task.max_retries is None
            and "plugin_path" not in task_text,
            {
                "task_name": PLANNING_RUN_SOLVER_TASK,
                "late_ack": registered_task.acks_late,
                "reject_on_worker_lost": registered_task.reject_on_worker_lost,
                "serializer": registered_task.serializer,
                "operational_retry_limit": registered_task.max_retries,
            },
        ),
        _check(
            "security-and-safe-evidence",
            security_test.is_file()
            and "p8-worker-evidence-key-0001"
            not in checkpoint.canonical_bytes.decode("utf-8")
            and "redis://" not in checkpoint.canonical_bytes.decode("utf-8"),
            {
                "security_test_fingerprint": _file_fingerprint(security_test),
                "raw_idempotency_key_in_checkpoint": False,
                "broker_url_in_checkpoint": False,
            },
        ),
    ]
    issues = [
        cast(str, item["check_id"]) for item in checks if item["result"] != "PASS"
    ]
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "validation_profile": "HIGH_RISK",
        "status": "PASS" if not issues else "FAIL",
        "check_count": len(checks),
        "checks": checks,
        "counts": counts,
        "identities": {
            "code_commit": code_commit,
            "profile_fingerprint": _file_fingerprint(profile_path),
            "runtime_resolution_fingerprint": runtime["resolution_fingerprint"],
            "work_item_fingerprint": work["work_item_fingerprint"],
            "worker_result_fingerprint": checkpoint_document["result_fingerprint"],
        },
        "reliability": {
            "delivery": "JSON_ONLY_LATE_ACK_WORKER_LOST_REJECT_PREFETCH_ONE",
            "claim": "DURABLE_LEASE_CAS",
            "business_retry": "EXPLICIT_P8_PLANNING_RUN_RETRY_ONLY",
            "checkpoint": "APPEND_ONLY_BEFORE_TERMINAL_RECONCILIATION",
            "ack_boundary": "AFTER_EXISTING_SCHEDULE_VERSION_APPLICATION",
        },
        "boundaries": {
            "data_plane": "SIMULATION",
            "environment": "TEST",
            "synthetic": True,
            "canonical_json_only": True,
            "third_party_adapter": "EXCLUDED",
            "demo": "EXCLUDED",
            "production_broker_database": "NOT_TESTED",
            "production_sla_claimed": False,
        },
        "issues": issues,
    }
    report["report_fingerprint"] = _fingerprint(report)
    benchmark: JsonObject = {
        "report_version": BENCHMARK_REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "status": "PASS" if not issues else "FAIL",
        "profile": {
            "profile_version": profile["profile_version"],
            "profile_id": profile["profile_id"],
            "scenario_id": profile["scenario_id"],
            "profile_fingerprint": _file_fingerprint(profile_path),
            "data_plane": profile["data_plane"],
            "environment": profile["environment"],
            "synthetic": profile["synthetic"],
            "measured_runs": profile["measured_runs"],
        },
        "observations": {
            "worker_end_to_end_elapsed_ns": first_elapsed_ns,
            "solver_elapsed_ns": solver.elapsed_ns,
            "exact_redelivery_elapsed_ns": replay_elapsed_ns,
            "peak_allocated_bytes": peak_allocated_bytes,
            "checkpoint_bytes": len(checkpoint.canonical_bytes),
            "solver_calls": solver.calls,
            "validator_calls": validator.calls,
            "schedule_versions": counts["schedule_versions"],
        },
        "measurement_semantics": "DEVELOPMENT_OBSERVATION_NO_SLA",
        "thresholds": None,
        "production_sla_claimed": False,
        "production_capacity_claimed": False,
        "issues": issues,
    }
    benchmark["report_fingerprint"] = _fingerprint(benchmark)
    return report, benchmark


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        _fail("UNSAFE_REPORT_PATH")
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(canonical_json_bytes(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        _fail("REPORT_WRITE_FAILED")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--profile", type=Path, default=Path(PROFILE_RELATIVE))
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p8-solver-worker-reliability.json"),
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        default=Path("build/benchmarks/p8-solver-worker-engineering.json"),
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    profile_path = arguments.profile
    if not profile_path.is_absolute():
        profile_path = root / profile_path
    report_path = arguments.report
    if not report_path.is_absolute():
        report_path = root / report_path
    benchmark_path = arguments.benchmark_report
    if not benchmark_path.is_absolute():
        benchmark_path = root / benchmark_path
    try:
        report, benchmark = run_checks(root, profile_path)
        _write_json(report_path, report)
        _write_json(benchmark_path, benchmark)
    except WorkerCheckError as error:
        error_code = error.code
    except Exception:  # noqa: BLE001 - machine failure remains sanitized
        error_code = "UNEXPECTED_CHECK_FAILURE"
    else:
        print(
            "PASS P8 Solver Worker: "
            f"checks={report['check_count']} solver_calls=1 issues=0"
        )
        return 0 if report["status"] == benchmark["status"] == "PASS" else 1
    failure = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "status": "FAIL",
        "issues": [error_code],
    }
    benchmark_failure = {
        "report_version": BENCHMARK_REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "status": "FAIL",
        "issues": [error_code],
    }
    _write_json(report_path, failure)
    _write_json(benchmark_path, benchmark_failure)
    print(f"FAIL P8 Solver Worker: {error_code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
