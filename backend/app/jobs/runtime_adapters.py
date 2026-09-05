"""Server-owned adapters used by the P8 Runtime composition root."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import cast

from app.application.canonical_ingress import CanonicalIngressRecord
from app.application.planning_runs import (
    PlanningRunCommandContext,
    PlanningRunRepository,
)
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.jobs.planning_run_worker_contracts import (
    PlanningRunResolvedInputs,
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
    reject_worker,
)
from app.planning.contracts import PlanningContractError, contract_fingerprint
from app.planning.policy import validate_planning_policy, validate_solve_limits


type JsonObject = dict[str, object]


@dataclass(frozen=True, slots=True)
class FrozenPlanningArtifactCatalog:
    """One immutable, server-configured Policy/Limits pair.

    The Headless request carries references only.  Runtime configuration owns
    the corresponding executable documents and never accepts a path or
    document selector from the request or worker message.
    """

    planning_policy_bytes: bytes
    solve_limits_bytes: bytes
    data_plane: str

    @classmethod
    def create(
        cls,
        *,
        planning_policy: Mapping[str, object],
        solve_limits: Mapping[str, object],
        data_plane: str,
    ) -> FrozenPlanningArtifactCatalog:
        try:
            validate_planning_policy(planning_policy)
            validate_solve_limits(solve_limits)
        except PlanningContractError as error:
            raise ValueError("Runtime planning artifact contract is invalid") from error
        if data_plane not in {"SIMULATION", "PRODUCTION"}:
            raise ValueError("Runtime planning artifact data plane is invalid")
        if (
            planning_policy.get("data_plane") != data_plane
            or solve_limits.get("data_plane") != data_plane
        ):
            raise ValueError("Runtime planning artifacts crossed their data plane")
        return cls(
            planning_policy_bytes=canonical_json_bytes(planning_policy),
            solve_limits_bytes=canonical_json_bytes(solve_limits),
            data_plane=data_plane,
        )

    @property
    def planning_policy(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.planning_policy_bytes))

    @property
    def solve_limits(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.solve_limits_bytes))

    @staticmethod
    def _reference(
        document: Mapping[str, object], *, version_field: str, id_field: str
    ) -> JsonObject:
        return {
            "document_version": document[version_field],
            "artifact_id": document[id_field],
            "fingerprint": contract_fingerprint(document),
        }

    @property
    def planning_policy_reference(self) -> JsonObject:
        return self._reference(
            self.planning_policy,
            version_field="planning_policy_version",
            id_field="policy_id",
        )

    @property
    def solve_limits_reference(self) -> JsonObject:
        return self._reference(
            self.solve_limits,
            version_field="solve_limits_version",
            id_field="limits_id",
        )

    def resolve(
        self, *, planning_policy_reference: object, solve_limits_reference: object
    ) -> tuple[JsonObject, JsonObject]:
        if (
            not isinstance(planning_policy_reference, Mapping)
            or dict(planning_policy_reference) != self.planning_policy_reference
            or not isinstance(solve_limits_reference, Mapping)
            or dict(solve_limits_reference) != self.solve_limits_reference
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="work_item.inputs",
                message="Planning artifacts differ from the server catalog",
            )
        return self.planning_policy, self.solve_limits


class RepositoryPlanningInputResolver:
    """Resolve a work item from durable ingress plus the frozen catalog."""

    def __init__(
        self,
        *,
        ingress_repository: SqlAlchemyCanonicalIngressRepository,
        catalog: FrozenPlanningArtifactCatalog,
    ) -> None:
        if ingress_repository.data_plane.value != catalog.data_plane:
            raise ValueError("Input resolver ports must bind the same data plane")
        self._ingress_repository = ingress_repository
        self._catalog = catalog

    def resolve(self, work_item: Mapping[str, object]) -> PlanningRunResolvedInputs:
        prepared = work_item.get("prepared_artifacts")
        inputs = work_item.get("inputs")
        if not isinstance(prepared, Mapping) or not isinstance(inputs, Mapping):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="work_item",
                message="Work item input references are invalid",
            )
        # P8-04 intentionally keeps the canonical-ingress reference on the
        # durable aggregate rather than exposing another worker selector.
        planning_run_id = work_item.get("planning_run_id")
        if not isinstance(planning_run_id, str):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="work_item.planning_run_id",
                message="Work item PlanningRun identity is invalid",
            )
        record = self._record_for_planning_run(planning_run_id)

        record_document = record.document
        run = record_document.get("planning_run")
        record_prepared = record_document.get("prepared_artifacts")
        if (
            not isinstance(run, Mapping)
            or run.get("planning_run_id") != work_item.get("planning_run_id")
            or not isinstance(record_prepared, Mapping)
            or any(
                record_prepared.get(field) != prepared.get(field)
                for field in ("import_quality_report", "snapshot", "problem")
            )
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="work_item.prepared_artifacts",
                message="Durable ingress differs from the frozen work item",
            )
        policy, limits = self._catalog.resolve(
            planning_policy_reference=inputs.get("planning_policy"),
            solve_limits_reference=inputs.get("solve_limits"),
        )
        return PlanningRunResolvedInputs(
            import_quality_report=cast(
                Mapping[str, object], record_document["import_quality_report"]
            ),
            snapshot=record.snapshot.document,
            problem=record.problem.document,
            planning_policy=policy,
            solve_limits=limits,
        )

    def _record_for_planning_run(self, planning_run_id: str) -> CanonicalIngressRecord:
        try:
            record = self._ingress_repository.get_by_planning_run_id(planning_run_id)
        except Exception as error:  # noqa: BLE001 - sanitize persistence detail
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="canonical_ingress",
                message="Durable canonical ingress lookup failed",
                retryable=True,
            ) from error
        if record is None:
            reject_worker(
                PlanningRunWorkerErrorCode.INPUT_MISMATCH,
                field="canonical_ingress",
                message="PlanningRun has no durable canonical ingress",
            )
        return record


class RepositoryPlanningRunContextProvider:
    """Derive the internal Worker authority from the persisted run scope."""

    def __init__(
        self,
        *,
        repository: PlanningRunRepository,
        environment: str,
        code_commit: str,
    ) -> None:
        self._repository = repository
        self._environment = environment
        self._code_commit = code_commit

    def context_for(
        self, planning_run_id: str, *, occurred_at_utc: str
    ) -> PlanningRunCommandContext:
        try:
            model = self._repository.get(planning_run_id)
        except Exception as error:  # noqa: BLE001 - sanitize persistence detail
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_context",
                message="PlanningRun scope lookup failed",
                retryable=True,
            ) from error
        if model is None:
            reject_worker(
                PlanningRunWorkerErrorCode.INVALID_WORK_ITEM,
                field="planning_run_id",
                message="PlanningRun is unavailable",
            )
        scope = model.aggregate.document.get("effective_scope")
        correlation_id = (
            model.work_items[-1].document.get("correlation_id")
            if model.work_items
            else None
        )
        if (
            not isinstance(scope, Mapping)
            or scope.get("environment") != self._environment
            or not isinstance(correlation_id, str)
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RUNTIME_MISMATCH,
                field="worker_context",
                message="PlanningRun scope differs from Runtime composition",
            )
        return PlanningRunCommandContext.create(
            actor_reference="actor:aps-runtime-worker",
            capabilities=("view", "edit"),
            auth_policy_version="aps-runtime-worker-policy.v1",
            tenant_id=cast(str, scope["tenant_id"]),
            factory_id=cast(str, scope["factory_id"]),
            planning_scope_id=cast(str, scope["planning_scope_id"]),
            data_plane=cast(str, scope["data_plane"]),
            environment=cast(str, scope["environment"]),
            production_binding=False,
            correlation_id=correlation_id,
            occurred_at_utc=occurred_at_utc,
            code_commit=self._code_commit,
        )


__all__ = [
    "FrozenPlanningArtifactCatalog",
    "RepositoryPlanningInputResolver",
    "RepositoryPlanningRunContextProvider",
]
