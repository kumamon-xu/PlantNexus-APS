"""Shared deterministic fixtures for TEST-P8-PLANNING-RUN-001."""

from __future__ import annotations

from threading import Lock
from typing import cast

from app.application.canonical_ingress import (
    CanonicalIngressApplicationService,
    CanonicalIngressRecord,
)
from app.application.planning_runs import (
    PlanningRunAttemptMutation,
    PlanningRunCommandContext,
    PlanningRunInitialization,
    PlanningRunRepositoryWrite,
    PlanningRunRetryMutation,
    PlanningRunTransitionMutation,
)
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    FrozenSchemaCatalog,
    canonical_json_bytes,
    idempotency_key_reference,
)
from app.domain.planning_run import (
    PlanningRunCommandRecord,
    PlanningRunErrorCode,
    PlanningRunReadModel,
    reject,
)
from backend.tests.contract.p8_canonical_ingress_support import (
    CODE_COMMIT,
    InMemoryCanonicalIngressRepository,
    SCHEMA_DIRECTORY,
    request_document,
    trusted_context,
)


def schemas() -> FrozenSchemaCatalog:
    return FrozenSchemaCatalog.from_directory(SCHEMA_DIRECTORY)


def canonical_ingress_record(
    *,
    data_plane: str = "SIMULATION",
    environment: str = "TEST",
) -> CanonicalIngressRecord:
    request = request_document(data_plane=data_plane, environment=environment)
    repository = InMemoryCanonicalIngressRepository()
    service = CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=repository,
    )
    outcome = service.submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )
    assert outcome.result["disposition"] == "ACCEPTED"
    record = repository.get_by_idempotency(
        scope_fingerprint=trusted_context(request).idempotency_scope_fingerprint(),
        key_reference=idempotency_key_reference(cast(str, request["idempotency_key"])),
    )
    assert record is not None
    return record


def command_context(
    *,
    capabilities: tuple[str, ...] = ("view", "edit"),
    tenant_id: str = "TENANT-P8-APPLICATION",
    data_plane: str = "SIMULATION",
    environment: str = "TEST",
    production_binding: bool = False,
    correlation_id: str = "CORRELATION-P8-RUN-001",
    occurred_at_utc: str = "2026-09-05T00:00:00Z",
) -> PlanningRunCommandContext:
    return PlanningRunCommandContext.create(
        actor_reference="actor:p8-planning-run-test",
        capabilities=capabilities,
        auth_policy_version="headless-auth-policy.v1",
        tenant_id=tenant_id,
        factory_id="FACTORY-001",
        planning_scope_id="PLANNING-P8-APPLICATION",
        data_plane=data_plane,
        environment=environment,
        production_binding=production_binding,
        correlation_id=correlation_id,
        occurred_at_utc=occurred_at_utc,
        code_commit=CODE_COMMIT,
    )


class InMemoryPlanningRunRepository:
    """Thread-safe port double with exact command and CAS behavior."""

    def __init__(self, *, data_plane: str = "SIMULATION") -> None:
        self._data_plane = data_plane
        self._models: dict[str, PlanningRunReadModel] = {}
        self._commands: dict[tuple[str, str], PlanningRunCommandRecord] = {}
        self._lock = Lock()
        self.audit_count = 0
        self.transition_count = 0

    @property
    def data_plane(self) -> str:
        return self._data_plane

    def get(self, planning_run_id: str) -> PlanningRunReadModel | None:
        with self._lock:
            return self._models.get(planning_run_id)

    def get_command(
        self, *, scope_fingerprint: str, key_reference: str
    ) -> PlanningRunCommandRecord | None:
        with self._lock:
            return self._commands.get((scope_fingerprint, key_reference))

    def _existing(
        self, command: PlanningRunCommandRecord
    ) -> PlanningRunRepositoryWrite | None:
        document = command.document
        key = (
            cast(str, document["scope_fingerprint"]),
            cast(str, document["key_reference"]),
        )
        existing = self._commands.get(key)
        if existing is None:
            return None
        if existing.document["request_fingerprint"] != document["request_fingerprint"]:
            reject(
                PlanningRunErrorCode.IDEMPOTENCY_CONFLICT,
                field="idempotency_key",
                message="In-memory command key conflict",
            )
        return PlanningRunRepositoryWrite(command=existing, replayed=True)

    def _put_command(self, command: PlanningRunCommandRecord) -> None:
        document = command.document
        self._commands[
            (
                cast(str, document["scope_fingerprint"]),
                cast(str, document["key_reference"]),
            )
        ] = command

    def materialize(
        self, initialization: PlanningRunInitialization
    ) -> PlanningRunRepositoryWrite:
        with self._lock:
            existing = self._existing(initialization.command)
            if existing is not None:
                return existing
            run_id = cast(str, initialization.aggregate.document["planning_run_id"])
            if run_id in self._models:
                reject(
                    PlanningRunErrorCode.IDEMPOTENCY_CONFLICT,
                    field="planning_run_id",
                    message="Run already materialized",
                )
            self._models[run_id] = PlanningRunReadModel(
                aggregate=initialization.aggregate,
                attempts=(initialization.attempt,),
                work_items=(initialization.work_item,),
            )
            self._put_command(initialization.command)
            self.audit_count += 1
            self.transition_count += 1
            return PlanningRunRepositoryWrite(
                command=initialization.command, replayed=False
            )

    def apply_transition(
        self, mutation: PlanningRunTransitionMutation
    ) -> PlanningRunRepositoryWrite:
        with self._lock:
            existing = self._existing(mutation.command)
            if existing is not None:
                return existing
            run_id = cast(str, mutation.previous.document["planning_run_id"])
            model = self._models.get(run_id)
            if (
                model is None
                or model.aggregate.canonical_bytes != mutation.previous.canonical_bytes
            ):
                reject(
                    PlanningRunErrorCode.STALE_RUN,
                    field="planning_run",
                    message="In-memory CAS lost",
                )
            attempts = list(model.attempts)
            if mutation.previous_attempt is not None and mutation.attempt is not None:
                if (
                    attempts[-1].canonical_bytes
                    != mutation.previous_attempt.canonical_bytes
                ):
                    reject(
                        PlanningRunErrorCode.STALE_ATTEMPT,
                        field="attempt",
                        message="In-memory attempt CAS lost",
                    )
                attempts[-1] = mutation.attempt
            self._models[run_id] = PlanningRunReadModel(
                aggregate=mutation.aggregate,
                attempts=tuple(attempts),
                work_items=model.work_items,
            )
            self._put_command(mutation.command)
            self.audit_count += 1
            self.transition_count += 1
            return PlanningRunRepositoryWrite(command=mutation.command, replayed=False)

    def append_retry(
        self, mutation: PlanningRunRetryMutation
    ) -> PlanningRunRepositoryWrite:
        with self._lock:
            existing = self._existing(mutation.command)
            if existing is not None:
                return existing
            run_id = cast(str, mutation.aggregate.document["planning_run_id"])
            model = self._models.get(run_id)
            if (
                model is None
                or model.aggregate.canonical_bytes != mutation.aggregate.canonical_bytes
                or model.attempts[-1].canonical_bytes
                != mutation.failed_attempt.canonical_bytes
            ):
                reject(
                    PlanningRunErrorCode.STALE_ATTEMPT,
                    field="failed_attempt",
                    message="In-memory retry CAS lost",
                )
            self._models[run_id] = PlanningRunReadModel(
                aggregate=model.aggregate,
                attempts=(*model.attempts, mutation.attempt),
                work_items=(*model.work_items, mutation.work_item),
            )
            self._put_command(mutation.command)
            self.audit_count += 1
            return PlanningRunRepositoryWrite(command=mutation.command, replayed=False)

    def update_attempt(
        self, mutation: PlanningRunAttemptMutation
    ) -> PlanningRunRepositoryWrite:
        with self._lock:
            existing = self._existing(mutation.command)
            if existing is not None:
                return existing
            run_id = cast(str, mutation.aggregate.document["planning_run_id"])
            model = self._models.get(run_id)
            if (
                model is None
                or model.aggregate.canonical_bytes != mutation.aggregate.canonical_bytes
                or model.attempts[-1].canonical_bytes
                != mutation.previous_attempt.canonical_bytes
            ):
                reject(
                    PlanningRunErrorCode.STALE_ATTEMPT,
                    field="attempt",
                    message="In-memory attempt CAS lost",
                )
            self._models[run_id] = PlanningRunReadModel(
                aggregate=model.aggregate,
                attempts=(*model.attempts[:-1], mutation.attempt),
                work_items=model.work_items,
            )
            self._put_command(mutation.command)
            self.audit_count += 1
            return PlanningRunRepositoryWrite(command=mutation.command, replayed=False)


__all__ = [
    "InMemoryPlanningRunRepository",
    "canonical_ingress_record",
    "command_context",
    "schemas",
]
