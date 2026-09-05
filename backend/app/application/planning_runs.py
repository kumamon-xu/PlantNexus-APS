"""Transport-neutral durable PlanningRun orchestration.

P8-04 materializes the immutable P8-03 CREATED carrier, persists legal CAS
transitions, and emits queue-ready work items.  It never calls a broker,
Solver, Validator, or public HTTP adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from app.application.canonical_ingress import (
    CanonicalIngressRecord,
    verify_canonical_ingress_record,
)
from app.data_validation.canonical_ingress import (
    FrozenSchemaCatalog,
    canonical_fingerprint,
    canonical_json_bytes,
    idempotency_key_reference,
    run_fingerprint,
    scope_fingerprint,
)
from app.domain.planning_run import (
    ATTEMPT_RETRYABLE_STATUSES,
    ATTEMPT_TERMINAL_STATUSES,
    AUDIT_EVENT_SCHEMA_ID,
    PLANNING_RUN_COMMAND_RECORD_VERSION,
    PLANNING_RUN_TERMINAL_STATES,
    PlanningRunActionResult,
    PlanningRunAggregate,
    PlanningRunAttempt,
    PlanningRunAttemptStatus,
    PlanningRunCommandRecord,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
    PlanningRunReadModel,
    PlanningRunWorkItem,
    derived_identity,
    reject,
    require_planning_run_transition,
    verify_attempt,
    verify_command_record,
    verify_planning_run,
    verify_work_item,
)
from app.jobs.planning_run_work_item import (
    create_queued_attempt,
    create_work_item,
    transition_attempt,
)


type JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlanningRunCommandContext:
    """Server-derived actor, capability, scope, and build identity."""

    actor_reference: str
    capabilities: frozenset[str]
    auth_policy_version: str
    tenant_id: str
    factory_id: str
    planning_scope_id: str
    data_plane: str
    environment: str
    production_binding: bool
    correlation_id: str
    occurred_at_utc: str
    code_commit: str

    @classmethod
    def create(
        cls,
        *,
        actor_reference: str,
        capabilities: tuple[str, ...],
        auth_policy_version: str,
        tenant_id: str,
        factory_id: str,
        planning_scope_id: str,
        data_plane: str,
        environment: str,
        production_binding: bool,
        correlation_id: str,
        occurred_at_utc: str,
        code_commit: str,
    ) -> PlanningRunCommandContext:
        return cls(
            actor_reference=actor_reference,
            capabilities=frozenset(capabilities),
            auth_policy_version=auth_policy_version,
            tenant_id=tenant_id,
            factory_id=factory_id,
            planning_scope_id=planning_scope_id,
            data_plane=data_plane,
            environment=environment,
            production_binding=production_binding,
            correlation_id=correlation_id,
            occurred_at_utc=occurred_at_utc,
            code_commit=code_commit,
        )

    def effective_scope(self) -> JsonObject:
        base: JsonObject = {
            "tenant_id": self.tenant_id,
            "factory_id": self.factory_id,
            "planning_scope_id": self.planning_scope_id,
            "data_plane": self.data_plane,
            "environment": self.environment,
        }
        return {**base, "scope_fingerprint": scope_fingerprint(base)}


@dataclass(frozen=True, slots=True)
class PlanningRunTransitionCommand:
    planning_run_id: str
    expected_revision: int
    expected_state: str
    expected_run_fingerprint: str
    to_state: str
    idempotency_key: str
    reason: str
    artifacts: Mapping[str, object]
    attempt_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlanningRunCancelCommand:
    planning_run_id: str
    expected_revision: int
    expected_state: str
    expected_run_fingerprint: str
    idempotency_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class PlanningRunRetryCommand:
    planning_run_id: str
    expected_revision: int
    expected_state: str
    expected_run_fingerprint: str
    failed_attempt_id: str
    failed_attempt_number: int
    idempotency_key: str
    reason: str
    available_at_utc: str
    timeout_at_utc: str


@dataclass(frozen=True, slots=True)
class PlanningRunAttemptFailureCommand:
    planning_run_id: str
    expected_revision: int
    expected_state: str
    expected_run_fingerprint: str
    attempt_id: str
    attempt_number: int
    expected_attempt_revision: int
    outcome: PlanningRunAttemptStatus
    failure_code: str
    idempotency_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class PlanningRunAttemptStartCommand:
    planning_run_id: str
    expected_revision: int
    expected_state: str
    expected_run_fingerprint: str
    attempt_id: str
    attempt_number: int
    expected_attempt_revision: int
    idempotency_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class PlanningRunInitialization:
    aggregate: PlanningRunAggregate
    attempt: PlanningRunAttempt
    work_item: PlanningRunWorkItem
    audit_bytes: bytes
    transition_bytes: bytes
    command: PlanningRunCommandRecord


@dataclass(frozen=True, slots=True)
class PlanningRunTransitionMutation:
    previous: PlanningRunAggregate
    aggregate: PlanningRunAggregate
    previous_attempt: PlanningRunAttempt | None
    attempt: PlanningRunAttempt | None
    audit_bytes: bytes
    transition_bytes: bytes
    command: PlanningRunCommandRecord


@dataclass(frozen=True, slots=True)
class PlanningRunRetryMutation:
    aggregate: PlanningRunAggregate
    failed_attempt: PlanningRunAttempt
    attempt: PlanningRunAttempt
    work_item: PlanningRunWorkItem
    audit_bytes: bytes
    command: PlanningRunCommandRecord


@dataclass(frozen=True, slots=True)
class PlanningRunAttemptMutation:
    aggregate: PlanningRunAggregate
    previous_attempt: PlanningRunAttempt
    attempt: PlanningRunAttempt
    audit_bytes: bytes
    command: PlanningRunCommandRecord


@dataclass(frozen=True, slots=True)
class PlanningRunRepositoryWrite:
    command: PlanningRunCommandRecord
    replayed: bool


class PlanningRunRepository(Protocol):
    @property
    def data_plane(self) -> str: ...

    def get(self, planning_run_id: str) -> PlanningRunReadModel | None: ...

    def get_command(
        self, *, scope_fingerprint: str, key_reference: str
    ) -> PlanningRunCommandRecord | None: ...

    def materialize(
        self, initialization: PlanningRunInitialization
    ) -> PlanningRunRepositoryWrite: ...

    def apply_transition(
        self, mutation: PlanningRunTransitionMutation
    ) -> PlanningRunRepositoryWrite: ...

    def append_retry(
        self, mutation: PlanningRunRetryMutation
    ) -> PlanningRunRepositoryWrite: ...

    def update_attempt(
        self, mutation: PlanningRunAttemptMutation
    ) -> PlanningRunRepositoryWrite: ...


def _audit_reference(document: Mapping[str, object]) -> JsonObject:
    return {
        "document_version": "audit-event.v1",
        "artifact_id": document["audit_event_id"],
        "fingerprint": canonical_fingerprint(document),
    }


def _headless_error(
    *,
    code: str,
    planning_run_id: str,
    correlation_id: str,
) -> JsonObject:
    tuples: dict[str, tuple[str, str, str, str, str]] = {
        "DATA_VALIDATION_FAILED": (
            "DATA_ERROR",
            "DATA_VALIDATION",
            "Canonical planning data did not pass Data Validation.",
            "NOT_RETRYABLE",
            "FIX_REQUEST",
        ),
        "MODEL_INVALID": (
            "MODEL_INVALID",
            "PROBLEM_BUILD",
            "The PlanningProblem could not be built into a valid model.",
            "NOT_RETRYABLE",
            "FIX_REQUEST",
        ),
        "INFEASIBLE": (
            "INFEASIBLE",
            "SOLVER",
            "The validated planning model is infeasible.",
            "NOT_RETRYABLE",
            "FIX_REQUEST",
        ),
        "NO_SOLUTION_WITHIN_LIMIT": (
            "NO_SOLUTION_WITHIN_LIMIT",
            "SOLVER",
            "No solution was proven within the configured solve limit.",
            "RETRY_AFTER_OPERATOR_ACTION",
            "CONTACT_OPERATOR",
        ),
        "SCHEDULE_VALIDATION_FAILED": (
            "VALIDATION_FAILED",
            "VALIDATION",
            "The candidate schedule did not pass formal validation.",
            "NOT_RETRYABLE",
            "FIX_REQUEST",
        ),
        "RUN_CANCELLED": (
            "CANCELLED",
            "STATE",
            "The PlanningRun was cancelled by an authorized command.",
            "NOT_RETRYABLE",
            "READ_CURRENT_STATE",
        ),
        "SYSTEM_ERROR": (
            "SYSTEM_ERROR",
            "SYSTEM",
            "PlanningRun execution failed without exposing partial success.",
            "RETRY_SAME_REQUEST",
            "RETRY_SAME_IDEMPOTENCY_KEY",
        ),
    }
    category, stage, message, retryability, action = tuples[code]
    return {
        "error_version": "headless-error.v1",
        "namespace": "HEADLESS_RUNTIME",
        "registry_version": "headless-error-code-registry.v1",
        "category": category,
        "code": code,
        "stage": stage,
        "message": message,
        "pointer": None,
        "entity_reference": planning_run_id,
        "expected_contract": "planning-run.v1 frozen transition evidence",
        "correlation_id": correlation_id,
        "retryability": retryability,
        "action": action,
    }


class PlanningRunOrchestrationService:
    """Create/read/cancel/retry/CAS ports over one plane-bound repository."""

    def __init__(
        self,
        *,
        schemas: FrozenSchemaCatalog,
        repository: PlanningRunRepository,
    ) -> None:
        self._schemas = schemas
        self._repository = repository

    @property
    def data_plane(self) -> str:
        return self._repository.data_plane

    def _authorize(
        self,
        aggregate: PlanningRunAggregate,
        context: PlanningRunCommandContext,
        *,
        read_only: bool,
    ) -> None:
        if context.data_plane != self._repository.data_plane:
            reject(
                PlanningRunErrorCode.DATA_PLANE_MISMATCH,
                field="context.data_plane",
                message="Runtime context crossed the repository data plane",
            )
        if context.data_plane == "PRODUCTION" and not context.production_binding:
            reject(
                PlanningRunErrorCode.DATA_PLANE_MISMATCH,
                field="context.production_binding",
                message="Production PlanningRun authority is not bound",
            )
        allowed = {"view", "edit"} if read_only else {"edit"}
        if not context.capabilities.intersection(allowed):
            reject(
                PlanningRunErrorCode.AUTHORITY_CONFLICT,
                field="context.capabilities",
                message="Required server-derived PlanningRun capability is absent",
            )
        if aggregate.document.get("effective_scope") != context.effective_scope():
            reject(
                PlanningRunErrorCode.SCOPE_MISMATCH,
                field="context.effective_scope",
                message="Runtime context does not match PlanningRun scope",
            )

    @staticmethod
    def _scope(
        operation: str,
        aggregate: PlanningRunAggregate,
        context: PlanningRunCommandContext,
    ) -> str:
        return canonical_fingerprint(
            {
                "operation": operation,
                "planning_run_id": aggregate.document["planning_run_id"],
                "effective_scope": context.effective_scope(),
            }
        )

    def _audit(
        self,
        *,
        aggregate: PlanningRunAggregate,
        context: PlanningRunCommandContext,
        operation: str,
        reason: str,
        request_fingerprint: str,
        scope: str,
        key_reference: str,
        parent_audit_event_id: str | None,
    ) -> JsonObject:
        initial_record = aggregate.initial_document
        synthetic = context.data_plane == "SIMULATION"
        seed = {
            "operation": operation,
            "planning_run_id": initial_record["planning_run_id"],
            "scope_fingerprint": scope,
            "key_reference": key_reference,
            "request_fingerprint": request_fingerprint,
        }
        document: JsonObject = {
            "audit_event_version": "audit-event.v1",
            "schema_set_version": "2.6.0",
            "canonicalization_version": "canonical-json.v1",
            "audit_event_id": derived_identity("audit-event", seed),
            "occurred_at_utc": context.occurred_at_utc,
            "actor_ref": context.actor_reference,
            "resolved_capability": "edit",
            "auth_policy_version": context.auth_policy_version,
            "environment": context.environment,
            "data_plane": context.data_plane,
            "synthetic": synthetic,
            "action": "EDIT_SCHEDULE",
            "aggregate_type": "PLANNING_RUN",
            "aggregate_id": initial_record["planning_run_id"],
            "target": (
                "SIMULATION_INTERNAL"
                if context.data_plane == "SIMULATION"
                else "WORKSPACE_INTERNAL"
            ),
            "intent_type": "COMMAND",
            "reason": reason,
            "request_fingerprint": request_fingerprint,
            "idempotency_reference": {
                "scope": scope,
                "key_reference": key_reference,
                "request_fingerprint": request_fingerprint,
            },
            "lineage": None,
            "before_state": None,
            "after_state": None,
            "source_version": None,
            "new_version": None,
            "export_job_id": None,
            "result": {
                "outcome": "SUCCEEDED",
                "replayed": False,
                "retryable": False,
                "error": None,
            },
            "correlation_id": context.correlation_id,
            "parent_audit_event_id": parent_audit_event_id,
            "code_commit": context.code_commit,
        }
        if synthetic:
            # P8-03 already validated the payload provenance; preserve it from
            # the immutable creation audit rather than accepting client fields.
            document["synthetic_provenance"] = self._synthetic_provenance(aggregate)
        try:
            self._schemas.validate(AUDIT_EVENT_SCHEMA_ID, document)
        except ValueError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="audit_event",
                message="PlanningRun audit violates audit-event.v1",
            ) from error
        return document

    @staticmethod
    def _synthetic_provenance(aggregate: PlanningRunAggregate) -> Mapping[str, object]:
        # The original creation audit is embedded in the immutable ingress
        # record only at materialization time, so retain it in source metadata.
        source = aggregate.prepared_artifacts
        provenance = source.get("synthetic_provenance")
        if not isinstance(provenance, Mapping):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="prepared_artifacts.synthetic_provenance",
                message="Synthetic provenance is absent from orchestration source",
            )
        return provenance

    def _command_record(
        self,
        *,
        operation: str,
        aggregate: PlanningRunAggregate,
        attempt: PlanningRunAttempt | None,
        work_item: PlanningRunWorkItem | None,
        audit: Mapping[str, object] | None,
        scope: str,
        key_reference: str,
        request_fingerprint: str,
        occurred_at_utc: str,
    ) -> PlanningRunCommandRecord:
        base: JsonObject = {
            "command_record_version": PLANNING_RUN_COMMAND_RECORD_VERSION,
            "command_id": derived_identity(
                "planning-run-command",
                {
                    "scope_fingerprint": scope,
                    "key_reference": key_reference,
                    "request_fingerprint": request_fingerprint,
                },
            ),
            "operation": operation,
            "planning_run_id": aggregate.document["planning_run_id"],
            "scope_fingerprint": scope,
            "key_reference": key_reference,
            "request_fingerprint": request_fingerprint,
            "occurred_at_utc": occurred_at_utc,
            "audit": _audit_reference(audit) if audit is not None else None,
            "result": {
                "planning_run": aggregate.document,
                "attempt": attempt.document if attempt is not None else None,
                "work_item": work_item.document if work_item is not None else None,
            },
        }
        document = {**base, "record_fingerprint": canonical_fingerprint(base)}
        record = PlanningRunCommandRecord(canonical_json_bytes(document))
        verify_command_record(record)
        return record

    def _result_from_command(
        self,
        command: PlanningRunCommandRecord,
        *,
        source: PlanningRunAggregate,
        replayed: bool,
    ) -> PlanningRunActionResult:
        document = command.document
        result = cast(Mapping[str, object], document["result"])
        aggregate = PlanningRunAggregate(
            canonical_bytes=canonical_json_bytes(result["planning_run"]),
            initial_run_bytes=source.initial_run_bytes,
            prepared_artifacts_bytes=source.prepared_artifacts_bytes,
            source_ingress_id=source.source_ingress_id,
            source_record_fingerprint=source.source_record_fingerprint,
        )
        verify_planning_run(aggregate, schemas=self._schemas)
        raw_attempt = result.get("attempt")
        attempt = (
            PlanningRunAttempt(canonical_json_bytes(raw_attempt))
            if isinstance(raw_attempt, Mapping)
            else None
        )
        if attempt is not None:
            verify_attempt(attempt, aggregate=aggregate)
        raw_work = result.get("work_item")
        work_item = (
            PlanningRunWorkItem(canonical_json_bytes(raw_work))
            if isinstance(raw_work, Mapping)
            else None
        )
        if work_item is not None:
            if attempt is None:
                reject(
                    PlanningRunErrorCode.LINEAGE_INVALID,
                    field="planning_run_command.result.work_item",
                    message="Command work item has no attempt",
                )
            verify_work_item(work_item, aggregate=aggregate, attempt=attempt)
        audit = document.get("audit")
        return PlanningRunActionResult(
            aggregate=aggregate,
            attempt=attempt,
            work_item=work_item,
            audit_reference=(dict(audit) if isinstance(audit, Mapping) else None),
            replayed=replayed,
        )

    def _existing_result(
        self,
        *,
        scope: str,
        key_reference: str,
        request_fingerprint: str,
        source: PlanningRunAggregate,
    ) -> PlanningRunActionResult | None:
        try:
            existing = self._repository.get_command(
                scope_fingerprint=scope, key_reference=key_reference
            )
        except PlanningRunOrchestrationError:
            raise
        if existing is None:
            return None
        if existing.document.get("request_fingerprint") != request_fingerprint:
            reject(
                PlanningRunErrorCode.IDEMPOTENCY_CONFLICT,
                field="idempotency_key",
                message="Idempotency key is bound to different command content",
            )
        return self._result_from_command(existing, source=source, replayed=True)

    def materialize(
        self,
        ingress_record: CanonicalIngressRecord,
        *,
        context: PlanningRunCommandContext,
        available_at_utc: str,
        timeout_at_utc: str,
    ) -> PlanningRunActionResult:
        """Materialize the P8-03 CREATED carrier and one durable work item."""

        verify_canonical_ingress_record(ingress_record)
        source = ingress_record.document
        initial_run = cast(Mapping[str, object], source["planning_run"])
        prepared = dict(cast(Mapping[str, object], source["prepared_artifacts"]))
        canonical_request = cast(Mapping[str, object], source["canonical_request"])
        payload = cast(Mapping[str, object], canonical_request["payload"])
        if payload.get("synthetic") is True:
            provenance = payload.get("synthetic_provenance")
            if not isinstance(provenance, Mapping):
                reject(
                    PlanningRunErrorCode.LINEAGE_INVALID,
                    field="canonical_request.payload.synthetic_provenance",
                    message="Synthetic canonical ingress provenance is absent",
                )
            prepared["synthetic_provenance"] = provenance
        aggregate = PlanningRunAggregate(
            canonical_bytes=canonical_json_bytes(initial_run),
            initial_run_bytes=canonical_json_bytes(initial_run),
            prepared_artifacts_bytes=canonical_json_bytes(prepared),
            source_ingress_id=cast(str, source["ingress_id"]),
            source_record_fingerprint=cast(str, source["record_fingerprint"]),
        )
        verify_planning_run(aggregate, schemas=self._schemas)
        self._authorize(aggregate, context, read_only=False)
        scope = self._scope("MATERIALIZE", aggregate, context)
        ingress_identity = cast(Mapping[str, object], source["idempotency"])
        key_reference = cast(str, ingress_identity["key_reference"])
        request_fingerprint = canonical_fingerprint(
            {
                "operation": "MATERIALIZE",
                "source_ingress_id": aggregate.source_ingress_id,
                "source_record_fingerprint": aggregate.source_record_fingerprint,
                "planning_run_id": initial_run["planning_run_id"],
                "available_at_utc": available_at_utc,
                "timeout_at_utc": timeout_at_utc,
            }
        )
        existing = self._existing_result(
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            source=aggregate,
        )
        if existing is not None:
            return existing
        parent_audit = cast(
            Mapping[str, object],
            cast(Mapping[str, object], initial_run["last_transition"])["audit"],
        )
        audit = self._audit(
            aggregate=aggregate,
            context=context,
            operation="MATERIALIZE",
            reason="Materialize the durable PlanningRun and queue-ready attempt.",
            request_fingerprint=request_fingerprint,
            scope=scope,
            key_reference=key_reference,
            parent_audit_event_id=cast(str, parent_audit["artifact_id"]),
        )
        audit_reference = _audit_reference(audit)
        attempt = create_queued_attempt(
            aggregate,
            attempt_number=1,
            available_at_utc=available_at_utc,
            timeout_at_utc=timeout_at_utc,
            audit_reference=audit_reference,
        )
        work_item = create_work_item(
            aggregate, attempt=attempt, correlation_id=context.correlation_id
        )
        command = self._command_record(
            operation="MATERIALIZE",
            aggregate=aggregate,
            attempt=attempt,
            work_item=work_item,
            audit=audit,
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=context.occurred_at_utc,
        )
        transition = cast(Mapping[str, object], initial_run["last_transition"])
        write = self._repository.materialize(
            PlanningRunInitialization(
                aggregate=aggregate,
                attempt=attempt,
                work_item=work_item,
                audit_bytes=canonical_json_bytes(audit),
                transition_bytes=canonical_json_bytes(transition),
                command=command,
            )
        )
        return self._result_from_command(
            write.command, source=aggregate, replayed=write.replayed
        )

    def read(
        self,
        planning_run_id: str,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunReadModel:
        model = self._repository.get(planning_run_id)
        if model is None:
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="planning_run_id",
                message="PlanningRun does not exist in the selected data plane",
            )
        self._authorize(model.aggregate, context, read_only=True)
        verify_planning_run(model.aggregate, schemas=self._schemas)
        for attempt in model.attempts:
            verify_attempt(attempt, aggregate=model.aggregate)
        return model

    @staticmethod
    def _latest_attempt(model: PlanningRunReadModel) -> PlanningRunAttempt:
        if not model.attempts:
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="planning_run_attempt",
                message="PlanningRun has no durable attempt",
            )
        return model.attempts[-1]

    @staticmethod
    def _require_expected(
        aggregate: PlanningRunAggregate,
        *,
        revision: int,
        state: str,
        fingerprint: str,
    ) -> None:
        run = aggregate.document
        if (
            run.get("revision") != revision
            or run.get("state") != state
            or run.get("run_fingerprint") != fingerprint
        ):
            reject(
                PlanningRunErrorCode.STALE_RUN,
                field="expected_run",
                message="PlanningRun precondition is stale",
            )

    def cancel(
        self,
        command: PlanningRunCancelCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunActionResult:
        model = self.read(command.planning_run_id, context=context)
        run = model.aggregate.document
        transition = PlanningRunTransitionCommand(
            planning_run_id=command.planning_run_id,
            expected_revision=command.expected_revision,
            expected_state=command.expected_state,
            expected_run_fingerprint=command.expected_run_fingerprint,
            to_state="CANCELLED",
            idempotency_key=command.idempotency_key,
            reason=command.reason,
            artifacts=cast(Mapping[str, object], run["artifacts"]),
            attempt_id=(
                cast(str, self._latest_attempt(model).document["attempt_id"])
                if model.attempts
                else None
            ),
        )
        return self.transition(transition, context=context)

    def transition(
        self,
        command: PlanningRunTransitionCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunActionResult:
        """Apply one frozen PlanningRun pair without invoking business work."""

        model = self.read(command.planning_run_id, context=context)
        aggregate = model.aggregate
        self._authorize(aggregate, context, read_only=False)
        scope = self._scope(f"TRANSITION:{command.to_state}", aggregate, context)
        key_reference = idempotency_key_reference(command.idempotency_key)
        request_fingerprint = canonical_fingerprint(
            {
                "operation": "TRANSITION",
                "planning_run_id": command.planning_run_id,
                "expected_revision": command.expected_revision,
                "expected_state": command.expected_state,
                "expected_run_fingerprint": command.expected_run_fingerprint,
                "to_state": command.to_state,
                "reason": command.reason,
                "artifacts": command.artifacts,
                "attempt_id": command.attempt_id,
            }
        )
        existing = self._existing_result(
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            source=aggregate,
        )
        if existing is not None:
            return existing
        self._require_expected(
            aggregate,
            revision=command.expected_revision,
            state=command.expected_state,
            fingerprint=command.expected_run_fingerprint,
        )
        current = aggregate.document
        require_planning_run_transition(cast(str, current["state"]), command.to_state)
        last_audit = cast(
            Mapping[str, object],
            cast(Mapping[str, object], current["last_transition"])["audit"],
        )
        audit = self._audit(
            aggregate=aggregate,
            context=context,
            operation=f"TRANSITION:{command.to_state}",
            reason=command.reason,
            request_fingerprint=request_fingerprint,
            scope=scope,
            key_reference=key_reference,
            parent_audit_event_id=cast(str, last_audit["artifact_id"]),
        )
        audit_reference = _audit_reference(audit)
        previous_attempt: PlanningRunAttempt | None = None
        next_attempt: PlanningRunAttempt | None = None
        attempt_evidence = current.get("attempt")
        states_without_attempt_evidence = {
            "INGESTING",
            "VALIDATING",
            "SNAPSHOTTED",
            "DATA_REJECTED",
        }
        latest_attempt = self._latest_attempt(model)
        if (
            command.to_state in PLANNING_RUN_TERMINAL_STATES
            and command.attempt_id is None
        ):
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="attempt_id",
                message="Terminal transition must bind the latest durable attempt",
            )
        latest_status = PlanningRunAttemptStatus(
            cast(str, latest_attempt.document["status"])
        )
        if (
            command.to_state not in PLANNING_RUN_TERMINAL_STATES
            and latest_status in ATTEMPT_TERMINAL_STATUSES
        ):
            reject(
                PlanningRunErrorCode.ATTEMPT_NOT_RETRYABLE,
                field="attempt.status",
                message="A terminal attempt must be retried before run progress",
            )
        if (
            command.attempt_id is not None
            and command.to_state in states_without_attempt_evidence
            and command.to_state not in PLANNING_RUN_TERMINAL_STATES
        ):
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="attempt_id",
                message="Target state does not admit public attempt evidence",
            )
        if command.attempt_id is not None:
            candidates = [
                item
                for item in model.attempts
                if item.document.get("attempt_id") == command.attempt_id
            ]
            if len(candidates) != 1 or candidates[0] is not latest_attempt:
                reject(
                    PlanningRunErrorCode.STALE_ATTEMPT,
                    field="attempt_id",
                    message="Transition must use the latest durable attempt",
                )
            previous_attempt = candidates[0]
            attempt_document = previous_attempt.document
            status = PlanningRunAttemptStatus(cast(str, attempt_document["status"]))
            if status in ATTEMPT_TERMINAL_STATUSES:
                if (
                    status not in ATTEMPT_RETRYABLE_STATUSES
                    or command.to_state not in {"CANCELLED", "FAILED"}
                ):
                    reject(
                        PlanningRunErrorCode.ATTEMPT_NOT_RETRYABLE,
                        field="attempt.status",
                        message="Terminal attempt cannot advance this PlanningRun",
                    )
                next_status = status
            elif status is PlanningRunAttemptStatus.QUEUED and command.to_state not in {
                "CANCELLED",
                "FAILED",
                "DATA_REJECTED",
            }:
                next_status = PlanningRunAttemptStatus.ACTIVE
            elif command.to_state == "CANCELLED":
                next_status = PlanningRunAttemptStatus.CANCELLED
            elif command.to_state == "FAILED":
                next_status = (
                    PlanningRunAttemptStatus.DISPATCH_FAILED
                    if status is PlanningRunAttemptStatus.QUEUED
                    else PlanningRunAttemptStatus.FAILED
                )
            elif command.to_state == "DATA_REJECTED":
                next_status = PlanningRunAttemptStatus.CANCELLED
            elif command.to_state == "COMPLETED":
                next_status = PlanningRunAttemptStatus.SUCCEEDED
            elif command.to_state in {
                "MODEL_INVALID",
                "INFEASIBLE",
                "NO_SOLUTION_WITHIN_LIMIT",
                "VALIDATION_FAILED",
            }:
                next_status = PlanningRunAttemptStatus.FAILED
            else:
                next_status = status
            if next_status is not status:
                failure_codes = {
                    "FAILED": "SYSTEM_ERROR",
                    "MODEL_INVALID": "MODEL_INVALID",
                    "INFEASIBLE": "INFEASIBLE",
                    "NO_SOLUTION_WITHIN_LIMIT": "NO_SOLUTION_WITHIN_LIMIT",
                    "VALIDATION_FAILED": "SCHEDULE_VALIDATION_FAILED",
                }
                failure_code = failure_codes.get(command.to_state)
                next_attempt = transition_attempt(
                    previous_attempt,
                    aggregate=aggregate,
                    to_status=next_status,
                    occurred_at_utc=context.occurred_at_utc,
                    audit_reference=audit_reference,
                    failure_code=failure_code,
                    result_references=command.artifacts,
                )
            else:
                next_attempt = previous_attempt
            attempt_document = next_attempt.document
            attempt_evidence = (
                {
                    "attempt_id": attempt_document["attempt_id"],
                    "attempt_number": attempt_document["attempt_number"],
                    "runtime_resolution_fingerprint": attempt_document[
                        "runtime_resolution_fingerprint"
                    ],
                    "started_at_utc": attempt_document["started_at_utc"],
                    "finished_at_utc": attempt_document["finished_at_utc"],
                }
                if attempt_document["started_at_utc"] is not None
                and command.to_state not in states_without_attempt_evidence
                else None
            )
        if (
            command.to_state
            in {
                "BUILDING",
                "SOLVING",
                "SOLVED",
                "VERIFYING",
                "COMPLETED",
                "MODEL_INVALID",
                "INFEASIBLE",
                "NO_SOLUTION_WITHIN_LIMIT",
                "VALIDATION_FAILED",
            }
            and attempt_evidence is None
        ):
            reject(
                PlanningRunErrorCode.INVALID_REFERENCE,
                field="attempt_id",
                message="Target state requires a durable attempt",
            )
        cancellation: Mapping[str, object] | None = None
        error: Mapping[str, object] | None = None
        if command.to_state == "CANCELLED":
            cancellation = {
                "actor_reference": context.actor_reference,
                "reason": command.reason,
                "cancelled_at_utc": context.occurred_at_utc,
                "audit": audit_reference,
            }
            error = _headless_error(
                code="RUN_CANCELLED",
                planning_run_id=command.planning_run_id,
                correlation_id=context.correlation_id,
            )
        elif command.to_state == "FAILED":
            error = _headless_error(
                code="SYSTEM_ERROR",
                planning_run_id=command.planning_run_id,
                correlation_id=context.correlation_id,
            )
        elif (
            command.to_state
            in {
                "DATA_REJECTED",
                "MODEL_INVALID",
                "INFEASIBLE",
                "NO_SOLUTION_WITHIN_LIMIT",
                "VALIDATION_FAILED",
            }
        ):
            error = _headless_error(
                code={
                    "DATA_REJECTED": "DATA_VALIDATION_FAILED",
                    "MODEL_INVALID": "MODEL_INVALID",
                    "INFEASIBLE": "INFEASIBLE",
                    "NO_SOLUTION_WITHIN_LIMIT": "NO_SOLUTION_WITHIN_LIMIT",
                    "VALIDATION_FAILED": "SCHEDULE_VALIDATION_FAILED",
                }[command.to_state],
                planning_run_id=command.planning_run_id,
                correlation_id=context.correlation_id,
            )
        elif command.to_state not in PLANNING_RUN_TERMINAL_STATES:
            error = None
        transition_document = {
            "transition_version": "planning-run-transition.v1",
            "sequence": cast(int, current["revision"]),
            "from_state": current["state"],
            "to_state": command.to_state,
            "occurred_at_utc": context.occurred_at_utc,
            "audit": audit_reference,
        }
        next_run: JsonObject = {
            **current,
            "revision": cast(int, current["revision"]) + 1,
            "state": command.to_state,
            "terminal": command.to_state in PLANNING_RUN_TERMINAL_STATES,
            "allowed_actions": (
                ["READ"]
                if command.to_state in PLANNING_RUN_TERMINAL_STATES
                else ["READ", "CANCEL"]
            ),
            "attempt": attempt_evidence,
            "artifacts": dict(command.artifacts),
            "cancellation": cancellation,
            "error": error,
            "last_transition": transition_document,
            "audit_references": [
                *cast(list[object], current["audit_references"]),
                audit_reference,
            ],
            "updated_at_utc": context.occurred_at_utc,
            "run_fingerprint": "",
        }
        next_run["run_fingerprint"] = run_fingerprint(next_run)
        candidate = PlanningRunAggregate(
            canonical_bytes=canonical_json_bytes(next_run),
            initial_run_bytes=aggregate.initial_run_bytes,
            prepared_artifacts_bytes=aggregate.prepared_artifacts_bytes,
            source_ingress_id=aggregate.source_ingress_id,
            source_record_fingerprint=aggregate.source_record_fingerprint,
        )
        verify_planning_run(candidate, schemas=self._schemas, previous=current)
        command_record = self._command_record(
            operation=f"TRANSITION:{command.to_state}",
            aggregate=candidate,
            attempt=next_attempt,
            work_item=None,
            audit=audit,
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=context.occurred_at_utc,
        )
        write = self._repository.apply_transition(
            PlanningRunTransitionMutation(
                previous=aggregate,
                aggregate=candidate,
                previous_attempt=previous_attempt,
                attempt=next_attempt,
                audit_bytes=canonical_json_bytes(audit),
                transition_bytes=canonical_json_bytes(transition_document),
                command=command_record,
            )
        )
        return self._result_from_command(
            write.command, source=aggregate, replayed=write.replayed
        )

    def record_attempt_failure(
        self,
        command: PlanningRunAttemptFailureCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunActionResult:
        """Persist dispatch/timeout outcome without forging a business state."""

        if command.outcome not in {
            PlanningRunAttemptStatus.DISPATCH_FAILED,
            PlanningRunAttemptStatus.TIMED_OUT,
        }:
            reject(
                PlanningRunErrorCode.UNKNOWN_OUTCOME,
                field="outcome",
                message="Only dispatch failure or timeout is a P8-04 attempt outcome",
            )
        model = self.read(command.planning_run_id, context=context)
        aggregate = model.aggregate
        self._authorize(aggregate, context, read_only=False)
        scope = self._scope(f"ATTEMPT:{command.outcome.value}", aggregate, context)
        key_reference = idempotency_key_reference(command.idempotency_key)
        request_fingerprint = canonical_fingerprint(
            {
                "operation": "ATTEMPT_FAILURE",
                "planning_run_id": command.planning_run_id,
                "expected_revision": command.expected_revision,
                "expected_state": command.expected_state,
                "expected_run_fingerprint": command.expected_run_fingerprint,
                "attempt_id": command.attempt_id,
                "attempt_number": command.attempt_number,
                "expected_attempt_revision": command.expected_attempt_revision,
                "outcome": command.outcome.value,
                "failure_code": command.failure_code,
                "reason": command.reason,
            }
        )
        existing = self._existing_result(
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            source=aggregate,
        )
        if existing is not None:
            return existing
        if aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
            reject(
                PlanningRunErrorCode.INVALID_STATE_TRANSITION,
                field="planning_run.state",
                message="Terminal PlanningRun cannot accept attempt outcomes",
            )
        self._require_expected(
            aggregate,
            revision=command.expected_revision,
            state=command.expected_state,
            fingerprint=command.expected_run_fingerprint,
        )
        attempt = self._latest_attempt(model)
        attempt_document = attempt.document
        if (
            attempt_document["attempt_id"] != command.attempt_id
            or attempt_document["attempt_number"] != command.attempt_number
            or attempt_document["revision"] != command.expected_attempt_revision
        ):
            reject(
                PlanningRunErrorCode.STALE_ATTEMPT,
                field="attempt",
                message="Attempt precondition is stale",
            )
        last_audit = cast(
            Mapping[str, object],
            cast(Mapping[str, object], aggregate.document["last_transition"])["audit"],
        )
        audit = self._audit(
            aggregate=aggregate,
            context=context,
            operation=f"ATTEMPT:{command.outcome.value}",
            reason=command.reason,
            request_fingerprint=request_fingerprint,
            scope=scope,
            key_reference=key_reference,
            parent_audit_event_id=cast(str, last_audit["artifact_id"]),
        )
        updated = transition_attempt(
            attempt,
            aggregate=aggregate,
            to_status=command.outcome,
            occurred_at_utc=context.occurred_at_utc,
            audit_reference=_audit_reference(audit),
            failure_code=command.failure_code,
            result_references=cast(
                Mapping[str, object], aggregate.document["artifacts"]
            ),
        )
        command_record = self._command_record(
            operation=f"ATTEMPT:{command.outcome.value}",
            aggregate=aggregate,
            attempt=updated,
            work_item=None,
            audit=audit,
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=context.occurred_at_utc,
        )
        write = self._repository.update_attempt(
            PlanningRunAttemptMutation(
                aggregate=aggregate,
                previous_attempt=attempt,
                attempt=updated,
                audit_bytes=canonical_json_bytes(audit),
                command=command_record,
            )
        )
        return self._result_from_command(
            write.command, source=aggregate, replayed=write.replayed
        )

    def start_attempt(
        self,
        command: PlanningRunAttemptStartCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunActionResult:
        """Bind Worker ownership by advancing QUEUED to ACTIVE without a run pair."""

        model = self.read(command.planning_run_id, context=context)
        aggregate = model.aggregate
        self._authorize(aggregate, context, read_only=False)
        scope = self._scope("ATTEMPT:ACTIVE", aggregate, context)
        key_reference = idempotency_key_reference(command.idempotency_key)
        request_fingerprint = canonical_fingerprint(
            {
                "operation": "ATTEMPT_START",
                "planning_run_id": command.planning_run_id,
                "expected_revision": command.expected_revision,
                "expected_state": command.expected_state,
                "expected_run_fingerprint": command.expected_run_fingerprint,
                "attempt_id": command.attempt_id,
                "attempt_number": command.attempt_number,
                "expected_attempt_revision": command.expected_attempt_revision,
                "reason": command.reason,
            }
        )
        existing = self._existing_result(
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            source=aggregate,
        )
        if existing is not None:
            return existing
        if aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
            reject(
                PlanningRunErrorCode.INVALID_STATE_TRANSITION,
                field="planning_run.state",
                message="Terminal PlanningRun cannot start a Worker attempt",
            )
        self._require_expected(
            aggregate,
            revision=command.expected_revision,
            state=command.expected_state,
            fingerprint=command.expected_run_fingerprint,
        )
        attempt = self._latest_attempt(model)
        attempt_document = attempt.document
        if (
            attempt_document["attempt_id"] != command.attempt_id
            or attempt_document["attempt_number"] != command.attempt_number
            or attempt_document["revision"] != command.expected_attempt_revision
            or attempt_document["status"] != PlanningRunAttemptStatus.QUEUED.value
        ):
            reject(
                PlanningRunErrorCode.STALE_ATTEMPT,
                field="attempt",
                message="Only the latest QUEUED attempt can start",
            )
        last_audit = cast(
            Mapping[str, object],
            cast(
                Mapping[str, object], aggregate.document["last_transition"]
            )["audit"],
        )
        audit = self._audit(
            aggregate=aggregate,
            context=context,
            operation="ATTEMPT:ACTIVE",
            reason=command.reason,
            request_fingerprint=request_fingerprint,
            scope=scope,
            key_reference=key_reference,
            parent_audit_event_id=cast(str, last_audit["artifact_id"]),
        )
        updated = transition_attempt(
            attempt,
            aggregate=aggregate,
            to_status=PlanningRunAttemptStatus.ACTIVE,
            occurred_at_utc=context.occurred_at_utc,
            audit_reference=_audit_reference(audit),
            failure_code=None,
            result_references=cast(
                Mapping[str, object], aggregate.document["artifacts"]
            ),
        )
        command_record = self._command_record(
            operation="ATTEMPT:ACTIVE",
            aggregate=aggregate,
            attempt=updated,
            work_item=None,
            audit=audit,
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=context.occurred_at_utc,
        )
        write = self._repository.update_attempt(
            PlanningRunAttemptMutation(
                aggregate=aggregate,
                previous_attempt=attempt,
                attempt=updated,
                audit_bytes=canonical_json_bytes(audit),
                command=command_record,
            )
        )
        return self._result_from_command(
            write.command, source=aggregate, replayed=write.replayed
        )

    def retry(
        self,
        command: PlanningRunRetryCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunActionResult:
        """Create a new attempt/work item; never reopen a terminal Run."""

        model = self.read(command.planning_run_id, context=context)
        aggregate = model.aggregate
        self._authorize(aggregate, context, read_only=False)
        scope = self._scope("RETRY", aggregate, context)
        key_reference = idempotency_key_reference(command.idempotency_key)
        request_fingerprint = canonical_fingerprint(
            {
                "operation": "RETRY",
                "planning_run_id": command.planning_run_id,
                "expected_revision": command.expected_revision,
                "expected_state": command.expected_state,
                "expected_run_fingerprint": command.expected_run_fingerprint,
                "failed_attempt_id": command.failed_attempt_id,
                "failed_attempt_number": command.failed_attempt_number,
                "reason": command.reason,
                "available_at_utc": command.available_at_utc,
                "timeout_at_utc": command.timeout_at_utc,
            }
        )
        existing = self._existing_result(
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            source=aggregate,
        )
        if existing is not None:
            return existing
        self._require_expected(
            aggregate,
            revision=command.expected_revision,
            state=command.expected_state,
            fingerprint=command.expected_run_fingerprint,
        )
        if aggregate.document["state"] in PLANNING_RUN_TERMINAL_STATES:
            reject(
                PlanningRunErrorCode.INVALID_STATE_TRANSITION,
                field="planning_run.state",
                message="Terminal PlanningRun cannot be retried or reopened",
            )
        failed = self._latest_attempt(model)
        failed_document = failed.document
        if (
            failed_document["attempt_id"] != command.failed_attempt_id
            or failed_document["attempt_number"] != command.failed_attempt_number
        ):
            reject(
                PlanningRunErrorCode.STALE_ATTEMPT,
                field="failed_attempt",
                message="Retry does not reference the latest attempt",
            )
        status = PlanningRunAttemptStatus(cast(str, failed_document["status"]))
        if status not in ATTEMPT_RETRYABLE_STATUSES:
            reject(
                PlanningRunErrorCode.ATTEMPT_NOT_RETRYABLE,
                field="failed_attempt.status",
                message="Only dispatch-failed or timed-out attempts may be retried",
            )
        last_audit = cast(
            Mapping[str, object],
            cast(Mapping[str, object], aggregate.document["last_transition"])["audit"],
        )
        audit = self._audit(
            aggregate=aggregate,
            context=context,
            operation="RETRY",
            reason=command.reason,
            request_fingerprint=request_fingerprint,
            scope=scope,
            key_reference=key_reference,
            parent_audit_event_id=cast(str, last_audit["artifact_id"]),
        )
        attempt = create_queued_attempt(
            aggregate,
            attempt_number=cast(int, failed_document["attempt_number"]) + 1,
            available_at_utc=command.available_at_utc,
            timeout_at_utc=command.timeout_at_utc,
            audit_reference=_audit_reference(audit),
        )
        work_item = create_work_item(
            aggregate, attempt=attempt, correlation_id=context.correlation_id
        )
        command_record = self._command_record(
            operation="RETRY",
            aggregate=aggregate,
            attempt=attempt,
            work_item=work_item,
            audit=audit,
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=context.occurred_at_utc,
        )
        write = self._repository.append_retry(
            PlanningRunRetryMutation(
                aggregate=aggregate,
                failed_attempt=failed,
                attempt=attempt,
                work_item=work_item,
                audit_bytes=canonical_json_bytes(audit),
                command=command_record,
            )
        )
        return self._result_from_command(
            write.command, source=aggregate, replayed=write.replayed
        )


__all__ = [
    "PlanningRunAttemptFailureCommand",
    "PlanningRunAttemptStartCommand",
    "PlanningRunAttemptMutation",
    "PlanningRunCancelCommand",
    "PlanningRunCommandContext",
    "PlanningRunInitialization",
    "PlanningRunOrchestrationService",
    "PlanningRunRepository",
    "PlanningRunRepositoryWrite",
    "PlanningRunRetryCommand",
    "PlanningRunRetryMutation",
    "PlanningRunTransitionCommand",
    "PlanningRunTransitionMutation",
]
