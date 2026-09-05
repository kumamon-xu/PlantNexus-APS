"""Shared synthetic composition for TEST-P8-SOLVER-WORKER-001."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine

from app.application.canonical_ingress import CanonicalIngressApplicationService
from app.application.planning_runs import (
    PlanningRunCommandContext,
    PlanningRunOrchestrationService,
)
from app.application.schedule_versions import ValidatedSolutionToScheduleVersionService
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    canonical_json_bytes,
    idempotency_key_reference,
    request_fingerprint,
)
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.planning_run_repository import SqlAlchemyPlanningRunRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.planning_run_solver_worker import (
    PlanningRunSolverWorker,
    WorkerReliabilityPolicy,
)
from app.jobs.planning_run_worker_contracts import PlanningRunResolvedInputs
from app.jobs.planning_run_worker_repository import (
    SqlAlchemyPlanningRunWorkerRepository,
)
from app.planning.contracts import contract_fingerprint
from app.planning.policy import simulation_delivery_policy, simulation_solve_limits
from app.planning.strategies import GlobalCpSatStrategy
from app.planning.validation.problem_schedule_validator import (
    ProblemScheduleValidator,
)
from backend.tests.contract.p8_canonical_ingress_support import (
    ROOT,
    SCHEMA_DIRECTORY,
    request_document,
    runtime_resolution,
    trusted_context,
)
from backend.tests.contract.p8_planning_run_support import command_context, schemas


CODE_COMMIT = "f8c962188295c6e9d3852cc8bb8708caf3203adc"
WORKER_NOW = datetime(2026, 9, 5, 0, 0, 10, tzinfo=UTC)


def load_document(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def planning_policy() -> dict[str, Any]:
    return cast(dict[str, Any], simulation_delivery_policy())


def solve_limits() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        simulation_solve_limits(
            limits_id="LIMITS-P8-WORKER-001",
            limits_revision="1.0.0",
            source_record_id="P8-WORKER-LIMITS-001",
            max_wall_time_seconds=30.0,
            max_workers=1,
            random_seed=20260905,
        ),
    )


def worker_request() -> dict[str, Any]:
    request = request_document(
        request_id="REQUEST-P8-WORKER-001",
        correlation_id="CORRELATION-P8-WORKER-001",
        idempotency_key="p8-worker-ingress-key-0001",
    )
    policy = planning_policy()
    limits = solve_limits()
    request["planning_inputs"] = {
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
    }
    request["request_fingerprint"] = request_fingerprint(request)
    return request


def alembic_configuration(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def migrated_engine(database_path: Path) -> tuple[Engine, Config]:
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = alembic_configuration(database_url)
    command.upgrade(configuration, "head")
    return create_engine(database_url), configuration


class FixedClock:
    def __init__(self, value: datetime = WORKER_NOW) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class FixedContextProvider:
    def context_for(
        self, planning_run_id: str, *, occurred_at_utc: str
    ) -> PlanningRunCommandContext:
        del planning_run_id
        base = command_context(occurred_at_utc=occurred_at_utc)
        return PlanningRunCommandContext.create(
            actor_reference="actor:p8-solver-worker",
            capabilities=("view", "edit"),
            auth_policy_version=base.auth_policy_version,
            tenant_id=base.tenant_id,
            factory_id=base.factory_id,
            planning_scope_id=base.planning_scope_id,
            data_plane=base.data_plane,
            environment=base.environment,
            production_binding=base.production_binding,
            correlation_id="CORRELATION-P8-WORKER-001",
            occurred_at_utc=occurred_at_utc,
            code_commit=CODE_COMMIT,
        )


class FixedRuntimeProvider:
    def __init__(self, document: Mapping[str, object]) -> None:
        self.document = deepcopy(dict(document))

    def current_resolution(self, planning_run_id: str) -> Mapping[str, object]:
        del planning_run_id
        return deepcopy(self.document)


class FixedInputResolver:
    def __init__(self, resolved: PlanningRunResolvedInputs) -> None:
        self.resolved = resolved

    def resolve(self, work_item: Mapping[str, object]) -> PlanningRunResolvedInputs:
        del work_item
        return self.resolved


def materialize_worker_run(engine: Engine):
    request = worker_request()
    ingress_repository = SqlAlchemyCanonicalIngressRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    outcome = CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=ingress_repository,
    ).submit(canonical_json_bytes(request), context=trusted_context(request))
    assert outcome.result["disposition"] == "ACCEPTED"
    record = ingress_repository.get_by_idempotency(
        scope_fingerprint=trusted_context(request).idempotency_scope_fingerprint(),
        key_reference=idempotency_key_reference(cast(str, request["idempotency_key"])),
    )
    assert record is not None
    orchestration = PlanningRunOrchestrationService(
        schemas=schemas(),
        repository=SqlAlchemyPlanningRunRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
    )
    created = orchestration.materialize(
        record,
        context=command_context(
            correlation_id="CORRELATION-P8-WORKER-001",
            occurred_at_utc="2026-09-05T00:00:00Z",
        ),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    resolved = PlanningRunResolvedInputs(
        import_quality_report=cast(
            Mapping[str, object], record.document["import_quality_report"]
        ),
        snapshot=record.snapshot.document,
        problem=record.problem.document,
        planning_policy=planning_policy(),
        solve_limits=solve_limits(),
    )
    return created, orchestration, resolved


def worker_for(
    engine: Engine,
    *,
    orchestration: PlanningRunOrchestrationService,
    resolved: PlanningRunResolvedInputs,
    clock: FixedClock | None = None,
    runtime: Mapping[str, object] | None = None,
    solver: object | None = None,
    validator: object | None = None,
    publisher: object | None = None,
    worker_repository: SqlAlchemyPlanningRunWorkerRepository | None = None,
    reliability_policy: WorkerReliabilityPolicy | None = None,
) -> PlanningRunSolverWorker:
    plane = WorkspaceDataPlane.SIMULATION
    lifecycle = publisher or ValidatedSolutionToScheduleVersionService(
        data_plane=plane.value,
        transaction_factory=engine.begin,
        schedule_repository=SqlAlchemyScheduleVersionRepository(
            engine, data_plane=plane
        ),
        audit_repository=SqlAlchemyAuditRepository(engine, data_plane=plane),
    )
    return PlanningRunSolverWorker(
        orchestration=orchestration,
        worker_repository=worker_repository
        or SqlAlchemyPlanningRunWorkerRepository(engine, data_plane=plane),
        input_resolver=FixedInputResolver(resolved),
        runtime_provider=FixedRuntimeProvider(runtime or runtime_resolution()),
        context_provider=FixedContextProvider(),
        solver=cast(Any, solver or GlobalCpSatStrategy()),
        validator=cast(Any, validator or ProblemScheduleValidator()),
        publisher=cast(Any, lifecycle),
        policy=reliability_policy
        or WorkerReliabilityPolicy(heartbeat_seconds=30, lease_seconds=120),
        clock=clock or FixedClock(),
    )


__all__ = [
    "CODE_COMMIT",
    "FixedClock",
    "FixedContextProvider",
    "FixedInputResolver",
    "FixedRuntimeProvider",
    "WORKER_NOW",
    "alembic_configuration",
    "materialize_worker_run",
    "migrated_engine",
    "planning_policy",
    "solve_limits",
    "worker_for",
    "worker_request",
]
