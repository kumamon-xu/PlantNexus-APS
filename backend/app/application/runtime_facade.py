"""Transport-neutral application facade owned by the APS Runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Protocol, cast

from app.application.canonical_ingress import (
    CanonicalIngressApplicationService,
    CanonicalIngressOutcome,
    CanonicalIngressRecord,
    TrustedCanonicalIngressContext,
)
from app.application.planning_runs import (
    PlanningRunCancelCommand,
    PlanningRunCommandContext,
    PlanningRunOrchestrationService,
    PlanningRunRetryCommand,
)
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.domain.planning_run import (
    PlanningRunAttemptStatus,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
    PlanningRunReadModel,
)
from app.domain.types import format_utc_instant, parse_utc_instant


class RuntimeFacadeError(RuntimeError):
    """Stable, sanitized failure at the Runtime application boundary."""

    def __init__(
        self,
        code: str,
        *,
        field: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        self.retryable = retryable
        super().__init__(f"{code}: {field}: {message}")


class RuntimeIngressRepository(Protocol):
    @property
    def data_plane(self) -> object: ...

    def get_by_ingress_id(self, ingress_id: str) -> CanonicalIngressRecord | None: ...


class RuntimeDispatchReceipt(Protocol):
    @property
    def dispatch_id(self) -> str: ...

    @property
    def planning_run_id(self) -> str: ...

    @property
    def work_item_id(self) -> str: ...

    @property
    def worker_id(self) -> str: ...


class RuntimePlanningRunDispatcher(Protocol):
    def dispatch(self, work_item: Mapping[str, object]) -> RuntimeDispatchReceipt: ...


@dataclass(frozen=True, slots=True)
class RuntimeApplicationBinding:
    """Process-independent identity consumed by API and Worker façades."""

    data_plane: str
    environment: str
    code_commit: str
    runtime_resolution_bytes: bytes
    production_available: bool = False

    @classmethod
    def create(
        cls,
        *,
        data_plane: str,
        environment: str,
        code_commit: str,
        runtime_resolution: Mapping[str, object],
        production_available: bool = False,
    ) -> RuntimeApplicationBinding:
        if data_plane not in {"SIMULATION", "PRODUCTION"}:
            raise ValueError("Runtime application data plane is invalid")
        if environment not in {"DEVELOPMENT", "TEST", "BENCHMARK", "PRODUCTION"}:
            raise ValueError("Runtime application environment is invalid")
        if (data_plane == "PRODUCTION") != (environment == "PRODUCTION"):
            raise ValueError("Runtime application environment and data plane differ")
        if code_commit != "uncommitted" and (
            len(code_commit) != 40
            or any(character not in "0123456789abcdef" for character in code_commit)
        ):
            raise ValueError("Runtime application code commit is invalid")
        return cls(
            data_plane=data_plane,
            environment=environment,
            code_commit=code_commit,
            runtime_resolution_bytes=canonical_json_bytes(runtime_resolution),
            production_available=production_available,
        )

    @property
    def runtime_resolution(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.runtime_resolution_bytes))


@dataclass(frozen=True, slots=True)
class RuntimeDispatchWindow:
    available_at_utc: str
    timeout_at_utc: str

    def __post_init__(self) -> None:
        from app.domain.types import parse_utc_instant

        try:
            available = parse_utc_instant(self.available_at_utc)
            timeout = parse_utc_instant(self.timeout_at_utc)
        except ValueError as error:
            raise ValueError("Runtime dispatch window must contain UTC instants") from error
        if timeout <= available:
            raise ValueError("Runtime dispatch timeout must follow availability")

    def rebased(self, available_at_utc: str) -> RuntimeDispatchWindow:
        """Preserve the configured duration on a durable ingress timestamp."""

        original_available = parse_utc_instant(self.available_at_utc)
        original_timeout = parse_utc_instant(self.timeout_at_utc)
        available = parse_utc_instant(available_at_utc)
        return RuntimeDispatchWindow(
            available_at_utc=format_utc_instant(available),
            timeout_at_utc=format_utc_instant(
                available + (original_timeout - original_available)
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimePlanningRunSubmission:
    ingress: CanonicalIngressOutcome | None
    planning_run: PlanningRunReadModel | None
    dispatch: RuntimeDispatchReceipt | None


class APSRuntimeApplicationFacade:
    """Compose canonical ingress, durable PlanningRun, and async dispatch.

    HTTP adaptation remains a P8-07 concern.  This facade accepts only the
    trusted server context types already frozen by P8-03/P8-04.
    """

    def __init__(
        self,
        *,
        binding: RuntimeApplicationBinding,
        ingress: CanonicalIngressApplicationService,
        ingress_repository: RuntimeIngressRepository,
        planning_runs: PlanningRunOrchestrationService,
        dispatcher: RuntimePlanningRunDispatcher,
    ) -> None:
        repository_plane = getattr(ingress_repository.data_plane, "value", None)
        if (
            repository_plane != binding.data_plane
            or planning_runs.data_plane != binding.data_plane
        ):
            raise ValueError("Runtime application repositories must share one data plane")
        self._binding = binding
        self._ingress = ingress
        self._ingress_repository = ingress_repository
        self._planning_runs = planning_runs
        self._dispatcher = dispatcher

    @property
    def binding(self) -> RuntimeApplicationBinding:
        return self._binding

    @property
    def planning_runs(self) -> PlanningRunOrchestrationService:
        """Return the same internal port bound into the Solver Worker."""

        return self._planning_runs

    def _verify_context(
        self,
        *,
        data_plane: str,
        environment: str,
        code_commit: str,
        production_binding: bool,
        runtime_resolution: Mapping[str, object] | None = None,
    ) -> None:
        if data_plane != self._binding.data_plane:
            raise RuntimeFacadeError(
                "DATA_PLANE_MISMATCH",
                field="context.data_plane",
                message="Runtime context crossed its configured data plane",
            )
        if environment != self._binding.environment:
            raise RuntimeFacadeError(
                "RUNTIME_RESOLUTION_FAILED",
                field="context.environment",
                message="Runtime context environment differs from composition",
            )
        if code_commit != self._binding.code_commit:
            raise RuntimeFacadeError(
                "RUNTIME_RESOLUTION_FAILED",
                field="context.code_commit",
                message="Runtime context build differs from composition",
            )
        if data_plane == "PRODUCTION" and (
            not production_binding or not self._binding.production_available
        ):
            raise RuntimeFacadeError(
                "PRODUCTION_AUTHORITY_UNAVAILABLE",
                field="context.production_binding",
                message="Production Runtime authority is not configured",
            )
        if data_plane != "PRODUCTION" and production_binding:
            raise RuntimeFacadeError(
                "DATA_PLANE_MISMATCH",
                field="context.production_binding",
                message="Non-production Runtime cannot carry Production authority",
            )
        if (
            runtime_resolution is not None
            and dict(runtime_resolution) != self._binding.runtime_resolution
        ):
            raise RuntimeFacadeError(
                "RUNTIME_RESOLUTION_FAILED",
                field="context.runtime_resolution",
                message="Runtime context differs from the server composition",
            )

    @staticmethod
    def _command_context(
        context: TrustedCanonicalIngressContext,
        *,
        correlation_id: str,
    ) -> PlanningRunCommandContext:
        return PlanningRunCommandContext.create(
            actor_reference=context.actor_reference,
            capabilities=("view", "edit"),
            auth_policy_version=context.auth_policy_version,
            tenant_id=context.tenant_id,
            factory_id=context.factory_id,
            planning_scope_id=context.planning_scope_id,
            data_plane=context.data_plane,
            environment=context.environment,
            production_binding=context.production_binding,
            correlation_id=correlation_id,
            occurred_at_utc=context.occurred_at_utc,
            code_commit=context.code_commit,
        )

    def submit_canonical(
        self,
        raw_request: bytes,
        *,
        context: TrustedCanonicalIngressContext,
        dispatch_window: RuntimeDispatchWindow,
    ) -> RuntimePlanningRunSubmission:
        self._verify_context(
            data_plane=context.data_plane,
            environment=context.environment,
            code_commit=context.code_commit,
            production_binding=context.production_binding,
            runtime_resolution=context.runtime_resolution,
        )
        outcome = self._ingress.submit(raw_request, context=context)
        result = outcome.result
        accepted = result.get("accepted")
        if result.get("disposition") != "ACCEPTED" or not isinstance(
            accepted, Mapping
        ):
            return RuntimePlanningRunSubmission(
                ingress=outcome,
                planning_run=None,
                dispatch=None,
            )
        ingress_id = accepted.get("ingress_id")
        correlation_id = result.get("correlation_id")
        if not isinstance(ingress_id, str) or not isinstance(correlation_id, str):
            raise RuntimeFacadeError(
                "LINEAGE_INVALID",
                field="canonical_ingress_result",
                message="Accepted ingress lacks server-owned identity",
            )
        try:
            record = self._ingress_repository.get_by_ingress_id(ingress_id)
        except Exception as error:  # noqa: BLE001 - persistence detail is redacted
            raise RuntimeFacadeError(
                "SYSTEM_ERROR",
                field="canonical_ingress",
                message="Durable ingress lookup failed",
                retryable=True,
            ) from error
        if record is None:
            raise RuntimeFacadeError(
                "LINEAGE_INVALID",
                field="canonical_ingress",
                message="Accepted ingress is not durably available",
            )
        command_context = self._command_context(
            context, correlation_id=correlation_id
        )
        run_document = record.document.get("planning_run")
        planning_run_id = (
            run_document.get("planning_run_id")
            if isinstance(run_document, Mapping)
            else None
        )
        if not isinstance(planning_run_id, str):
            raise RuntimeFacadeError(
                "LINEAGE_INVALID",
                field="canonical_ingress.planning_run",
                message="Durable ingress lacks PlanningRun identity",
            )
        idempotency = result.get("idempotency")
        if (
            isinstance(idempotency, Mapping)
            and idempotency.get("outcome") == "REPLAYED"
        ):
            try:
                existing = self._planning_runs.read(
                    planning_run_id, context=command_context
                )
            except PlanningRunOrchestrationError as error:
                if error.code is not PlanningRunErrorCode.INVALID_REFERENCE:
                    raise
            else:
                return RuntimePlanningRunSubmission(
                    ingress=outcome,
                    planning_run=existing,
                    dispatch=None,
                )
        stable_window = dispatch_window.rebased(
            cast(str, record.document["occurred_at_utc"])
        )
        materialized = self._planning_runs.materialize(
            record,
            context=command_context,
            available_at_utc=stable_window.available_at_utc,
            timeout_at_utc=stable_window.timeout_at_utc,
        )
        model = self._planning_runs.read(
            cast(str, materialized.aggregate.document["planning_run_id"]),
            context=command_context,
        )
        receipt = (
            None
            if materialized.replayed
            else self._dispatch_queued(model, context=command_context)
        )
        return RuntimePlanningRunSubmission(
            ingress=outcome,
            planning_run=self._planning_runs.read(
                cast(str, materialized.aggregate.document["planning_run_id"]),
                context=command_context,
            ),
            dispatch=receipt,
        )

    def read_planning_run(
        self,
        planning_run_id: str,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunReadModel:
        self._verify_command_context(context)
        return self._planning_runs.read(planning_run_id, context=context)

    def cancel_planning_run(
        self,
        command: PlanningRunCancelCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> PlanningRunReadModel:
        self._verify_command_context(context)
        result = self._planning_runs.cancel(command, context=context)
        return self._planning_runs.read(
            cast(str, result.aggregate.document["planning_run_id"]), context=context
        )

    def retry_planning_run(
        self,
        command: PlanningRunRetryCommand,
        *,
        context: PlanningRunCommandContext,
    ) -> RuntimePlanningRunSubmission:
        self._verify_command_context(context)
        result = self._planning_runs.retry(command, context=context)
        model = self._planning_runs.read(command.planning_run_id, context=context)
        receipt = (
            None if result.replayed else self._dispatch_queued(model, context=context)
        )
        return RuntimePlanningRunSubmission(
            ingress=None,
            planning_run=self._planning_runs.read(
                cast(str, result.aggregate.document["planning_run_id"]), context=context
            ),
            dispatch=receipt,
        )

    def _verify_command_context(self, context: PlanningRunCommandContext) -> None:
        self._verify_context(
            data_plane=context.data_plane,
            environment=context.environment,
            code_commit=context.code_commit,
            production_binding=context.production_binding,
        )

    def _dispatch_queued(
        self,
        model: PlanningRunReadModel,
        *,
        context: PlanningRunCommandContext,
    ) -> RuntimeDispatchReceipt | None:
        if not model.attempts or not model.work_items:
            raise RuntimeFacadeError(
                "LINEAGE_INVALID",
                field="planning_run.work_item",
                message="PlanningRun has no durable queue work",
            )
        attempt = model.attempts[-1]
        work_item = model.work_items[-1]
        attempt_document = attempt.document
        work_document = work_item.document
        if attempt_document.get("attempt_id") != work_document.get("attempt_id"):
            raise RuntimeFacadeError(
                "LINEAGE_INVALID",
                field="planning_run.attempt",
                message="PlanningRun work does not bind the latest attempt",
            )
        if attempt_document.get("status") != PlanningRunAttemptStatus.QUEUED.value:
            return None
        try:
            return self._dispatcher.dispatch(work_document)
        except Exception as error:  # noqa: BLE001 - broker detail is redacted
            from app.application.planning_runs import PlanningRunAttemptFailureCommand

            run = model.aggregate.document
            try:
                self._planning_runs.record_attempt_failure(
                    PlanningRunAttemptFailureCommand(
                        planning_run_id=cast(str, run["planning_run_id"]),
                        expected_revision=cast(int, run["revision"]),
                        expected_state=cast(str, run["state"]),
                        expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                        attempt_id=cast(str, attempt_document["attempt_id"]),
                        attempt_number=cast(int, attempt_document["attempt_number"]),
                        expected_attempt_revision=cast(int, attempt_document["revision"]),
                        outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
                        failure_code="BROKER_DISPATCH_FAILED",
                        idempotency_key=(
                            f"runtime-dispatch-failure:{work_document['work_item_id']}"
                        ),
                        reason="Runtime could not acknowledge Solver work dispatch.",
                    ),
                    context=context,
                )
            except Exception as persistence_error:  # noqa: BLE001
                raise RuntimeFacadeError(
                    "SYSTEM_ERROR",
                    field="planning_run.dispatch_outcome",
                    message="Dispatch outcome could not be durably recorded",
                    retryable=True,
                ) from persistence_error
            raise RuntimeFacadeError(
                "QUEUE_FAILED",
                field="planning_run.dispatch",
                message="Solver work dispatch was rejected",
            ) from error


__all__ = [
    "APSRuntimeApplicationFacade",
    "RuntimeApplicationBinding",
    "RuntimeDispatchReceipt",
    "RuntimeDispatchWindow",
    "RuntimeFacadeError",
    "RuntimePlanningRunDispatcher",
    "RuntimePlanningRunSubmission",
]
