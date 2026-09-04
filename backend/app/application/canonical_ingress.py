"""P8 canonical-only ingress application boundary.

The service accepts exactly the frozen P8 request carrier. Authentication,
effective scope, Runtime resolution and build facts are supplied by trusted
Runtime composition and can never be selected by request JSON.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any, Protocol, cast

from app.data_validation.canonical_ingress import (
    CANONICALIZATION_VERSION,
    CANONICAL_INGRESS_RESULT_VERSION,
    HEADLESS_SCHEMA_SET_VERSION,
    CanonicalIngressContract,
    CanonicalIngressContractCode,
    CanonicalIngressContractError,
    canonical_fingerprint,
    canonical_json_bytes,
    idempotency_key_reference,
    result_fingerprint,
    run_fingerprint,
    scope_fingerprint,
)
from app.data_validation.contracts import DataValidationResult
from app.data_validation.validator import validate_import_package
from app.domain.production import OrderExpansionError
from app.normalization.order_expansion import expand_orders
from app.planning.problem.builder import build_planning_problem_v2
from app.planning.problem.contracts import (
    ImmutablePlanningProblemV2,
    PlanningProblemError,
)
from app.snapshots.builder import build_planning_snapshot
from app.snapshots.contracts import ImmutablePlanningSnapshot, SnapshotError


type JsonObject = dict[str, Any]

CANONICAL_INGRESS_BUILD_PLAN_VERSION = "canonical-ingress-build-plan.v1"
CANONICAL_INGRESS_RECORD_VERSION = "canonical-ingress-record.v1"
PROBLEM_BUILDER_VERSION = "planning-problem-builder.v2"


class CanonicalIngressPersistenceCode(StrEnum):
    """Sanitized persistence failures exposed through the application port."""

    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    CONTENT_CONFLICT = "CONTENT_CONFLICT"
    APPEND_ONLY = "APPEND_ONLY"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class CanonicalIngressPersistenceError(RuntimeError):
    def __init__(
        self,
        code: CanonicalIngressPersistenceCode,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code.value}: {field}: {message}")


@dataclass(frozen=True, slots=True)
class CanonicalIngressBuildPlan:
    """Immutable server-owned facts needed by the existing Snapshot/Problem chain."""

    canonical_bytes: bytes

    @classmethod
    def create(
        cls,
        *,
        planning_inputs: Mapping[str, object],
        cutoff_at_utc: str,
        tick_seconds: int,
        horizon_start_utc: str,
        horizon_end_utc: str,
        priority_facts: Mapping[str, Mapping[str, object]],
    ) -> CanonicalIngressBuildPlan:
        base: JsonObject = {
            "build_plan_version": CANONICAL_INGRESS_BUILD_PLAN_VERSION,
            "planning_inputs": planning_inputs,
            "cutoff_at_utc": cutoff_at_utc,
            "problem_builder_version": PROBLEM_BUILDER_VERSION,
            "tick_seconds": tick_seconds,
            "horizon_start_utc": horizon_start_utc,
            "horizon_end_utc": horizon_end_utc,
            "priority_facts": priority_facts,
        }
        document = {**base, "build_plan_fingerprint": canonical_fingerprint(base)}
        result = cls(canonical_bytes=canonical_json_bytes(document))
        result.verify()
        return result

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))

    def verify(self) -> None:
        try:
            document = self.document
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                "canonical ingress build plan is not valid JSON"
            ) from error
        expected_fields = {
            "build_plan_version",
            "planning_inputs",
            "cutoff_at_utc",
            "problem_builder_version",
            "tick_seconds",
            "horizon_start_utc",
            "horizon_end_utc",
            "priority_facts",
            "build_plan_fingerprint",
        }
        if set(document) != expected_fields:
            raise ValueError("canonical ingress build plan has an invalid field set")
        if (
            document["build_plan_version"] != CANONICAL_INGRESS_BUILD_PLAN_VERSION
            or document["problem_builder_version"] != PROBLEM_BUILDER_VERSION
        ):
            raise ValueError("canonical ingress build plan version is unsupported")
        tick_seconds = document["tick_seconds"]
        if type(tick_seconds) is not int or tick_seconds <= 0:
            raise ValueError("canonical ingress build plan tick must be positive")
        expected = canonical_fingerprint(
            {
                key: value
                for key, value in document.items()
                if key != "build_plan_fingerprint"
            }
        )
        if document["build_plan_fingerprint"] != expected:
            raise ValueError("canonical ingress build plan fingerprint is invalid")


@dataclass(frozen=True, slots=True)
class TrustedCanonicalIngressContext:
    """Server-owned authorization, authority and Runtime resolution evidence."""

    actor_reference: str
    resolved_capability: str
    auth_policy_version: str
    tenant_id: str
    factory_id: str
    planning_scope_id: str
    data_plane: str
    environment: str
    production_binding: bool
    authorized_authority_references: tuple[str, ...]
    authorized_mapping_fingerprints: tuple[str, ...]
    runtime_resolution_bytes: bytes
    build_plan: CanonicalIngressBuildPlan
    occurred_at_utc: str
    code_commit: str

    @classmethod
    def create(
        cls,
        *,
        actor_reference: str,
        auth_policy_version: str,
        tenant_id: str,
        factory_id: str,
        planning_scope_id: str,
        data_plane: str,
        environment: str,
        production_binding: bool,
        authorized_authority_references: tuple[str, ...],
        authorized_mapping_fingerprints: tuple[str, ...],
        runtime_resolution: Mapping[str, object],
        build_plan: CanonicalIngressBuildPlan,
        occurred_at_utc: str,
        code_commit: str,
    ) -> TrustedCanonicalIngressContext:
        return cls(
            actor_reference=actor_reference,
            resolved_capability="edit",
            auth_policy_version=auth_policy_version,
            tenant_id=tenant_id,
            factory_id=factory_id,
            planning_scope_id=planning_scope_id,
            data_plane=data_plane,
            environment=environment,
            production_binding=production_binding,
            authorized_authority_references=tuple(
                sorted(set(authorized_authority_references))
            ),
            authorized_mapping_fingerprints=tuple(
                sorted(set(authorized_mapping_fingerprints))
            ),
            runtime_resolution_bytes=canonical_json_bytes(runtime_resolution),
            build_plan=build_plan,
            occurred_at_utc=occurred_at_utc,
            code_commit=code_commit,
        )

    @property
    def runtime_resolution(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.runtime_resolution_bytes))

    def effective_scope(self) -> JsonObject:
        base: JsonObject = {
            "tenant_id": self.tenant_id,
            "factory_id": self.factory_id,
            "planning_scope_id": self.planning_scope_id,
            "data_plane": self.data_plane,
            "environment": self.environment,
        }
        return {**base, "scope_fingerprint": scope_fingerprint(base)}

    def idempotency_scope_fingerprint(self) -> str:
        return canonical_fingerprint(
            {
                "operation": "CREATE_PLANNING_RUN",
                "actor_reference": self.actor_reference,
                "resolved_capability": self.resolved_capability,
                "auth_policy_version": self.auth_policy_version,
                "effective_scope": self.effective_scope(),
            }
        )


@dataclass(frozen=True, slots=True)
class CanonicalIngressRecord:
    """One durable ingress record and its immutable prepared artifacts."""

    canonical_bytes: bytes
    snapshot: ImmutablePlanningSnapshot
    problem: ImmutablePlanningProblemV2

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))


@dataclass(frozen=True, slots=True)
class CanonicalIngressWriteResult:
    record: CanonicalIngressRecord
    replayed: bool


class CanonicalIngressRepository(Protocol):
    def get_by_idempotency(
        self,
        *,
        scope_fingerprint: str,
        key_reference: str,
    ) -> CanonicalIngressRecord | None: ...

    def commit(self, record: CanonicalIngressRecord) -> CanonicalIngressWriteResult: ...


@dataclass(frozen=True, slots=True)
class CanonicalIngressOutcome:
    """Transport-neutral response plus artifacts useful to the Runtime."""

    canonical_result_bytes: bytes
    planning_run_bytes: bytes | None
    quality_report_bytes: bytes | None
    snapshot: ImmutablePlanningSnapshot | None
    problem: ImmutablePlanningProblemV2 | None
    replayed: bool

    @property
    def result(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_result_bytes))

    @property
    def planning_run(self) -> JsonObject | None:
        if self.planning_run_bytes is None:
            return None
        return cast(JsonObject, json.loads(self.planning_run_bytes))

    @property
    def observability(self) -> JsonObject:
        result = self.result
        accepted = result.get("accepted")
        run = (
            cast(Mapping[str, object], accepted).get("planning_run")
            if isinstance(accepted, Mapping)
            else None
        )
        return {
            "event": "canonical_ingress.completed",
            "request_id": result["request_id"],
            "correlation_id": result["correlation_id"],
            "request_fingerprint": result["request_fingerprint"],
            "result_id": result["result_id"],
            "result_fingerprint": result["result_fingerprint"],
            "disposition": result["disposition"],
            "idempotency_outcome": cast(Mapping[str, object], result["idempotency"])[
                "outcome"
            ],
            "planning_run_id": (
                cast(Mapping[str, object], run).get("planning_run_id")
                if isinstance(run, Mapping)
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class _HeadlessErrorSpec:
    category: str
    code: str
    stage: str
    message: str
    pointer: str | None
    expected_contract: str
    retryability: str
    action: str


def _identity(prefix: str, value: object) -> str:
    return f"{prefix}-{canonical_fingerprint(value).removeprefix('sha256:')}"


def _artifact_reference(
    document_version: str, artifact_id: str, fingerprint: str
) -> JsonObject:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": fingerprint,
    }


def _headless_error(
    spec: _HeadlessErrorSpec,
    *,
    correlation_id: str,
    entity_reference: str | None,
) -> JsonObject:
    return {
        "error_version": "headless-error.v1",
        "namespace": "HEADLESS_RUNTIME",
        "registry_version": "headless-error-code-registry.v1",
        "category": spec.category,
        "code": spec.code,
        "stage": spec.stage,
        "message": spec.message,
        "pointer": spec.pointer,
        "entity_reference": entity_reference,
        "expected_contract": spec.expected_contract,
        "correlation_id": correlation_id,
        "retryability": spec.retryability,
        "action": spec.action,
    }


_SCOPE_MISMATCH = _HeadlessErrorSpec(
    "SCOPE_ERROR",
    "SCOPE_MISMATCH",
    "AUTHORIZATION",
    "The requested business scope is not authorized by the Runtime context.",
    "/requested_scope",
    "requested scope equal to server-resolved effective scope",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_DATA_PLANE_MISMATCH = _HeadlessErrorSpec(
    "SCOPE_ERROR",
    "DATA_PLANE_MISMATCH",
    "AUTHORIZATION",
    "The requested data plane is not available in the Runtime context.",
    "/requested_scope/data_plane",
    "authorized and isolated Runtime data plane",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_AUTHORITY_CONFLICT = _HeadlessErrorSpec(
    "AUTHORITY_ERROR",
    "AUTHORITY_CONFLICT",
    "CONTRACT",
    "Canonical source authority is not authorized by the Runtime context.",
    "/source_authority",
    "server-authorized authority and mapping references",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_INVALID_REFERENCE = _HeadlessErrorSpec(
    "DATA_ERROR",
    "INVALID_REFERENCE",
    "CONTRACT",
    "Planning input references do not match the server-owned build plan.",
    "/planning_inputs",
    "exact server-resolved planning input references",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_RUNTIME_RESOLUTION_FAILED = _HeadlessErrorSpec(
    "SYSTEM_ERROR",
    "RUNTIME_RESOLUTION_FAILED",
    "RUNTIME_RESOLUTION",
    "The Runtime could not provide a valid pinned component resolution.",
    None,
    "valid server-owned runtime-resolution.v1",
    "RETRY_AFTER_OPERATOR_ACTION",
    "CONTACT_OPERATOR",
)
_DATA_VALIDATION_FAILED = _HeadlessErrorSpec(
    "DATA_ERROR",
    "DATA_VALIDATION_FAILED",
    "DATA_VALIDATION",
    "Canonical data failed the versioned Data Validation quality gate.",
    "/payload",
    "zero-error PASS import-quality-report.v1",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_LINEAGE_INVALID = _HeadlessErrorSpec(
    "AUTHORITY_ERROR",
    "LINEAGE_INVALID",
    "SNAPSHOT",
    "Canonical payload lineage could not produce an immutable Snapshot.",
    "/payload",
    "content-derived canonical Import and Snapshot lineage",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_MODEL_INVALID = _HeadlessErrorSpec(
    "MODEL_INVALID",
    "MODEL_INVALID",
    "PROBLEM_BUILD",
    "Canonical data could not produce a valid immutable planning model.",
    "/payload",
    "planning-snapshot.v2 and planning-problem.v2 build contract",
    "NOT_RETRYABLE",
    "FIX_REQUEST",
)
_IDEMPOTENCY_CONFLICT = _HeadlessErrorSpec(
    "CONFLICT",
    "IDEMPOTENCY_CONFLICT",
    "IDEMPOTENCY",
    "The idempotency key is bound to a different request fingerprint.",
    "/idempotency_key",
    "same scope and key require the original request fingerprint",
    "NOT_RETRYABLE",
    "READ_CURRENT_STATE",
)
_SYSTEM_ERROR = _HeadlessErrorSpec(
    "SYSTEM_ERROR",
    "SYSTEM_ERROR",
    "SYSTEM",
    "Canonical ingress persistence failed without committing partial effects.",
    None,
    "atomic durable ingress transaction",
    "RETRY_SAME_REQUEST",
    "RETRY_SAME_IDEMPOTENCY_KEY",
)


class CanonicalIngressApplicationService:
    """Validate, materialize and atomically commit one P8 canonical request."""

    def __init__(
        self,
        *,
        contract: CanonicalIngressContract,
        repository: CanonicalIngressRepository,
    ) -> None:
        self._contract = contract
        self._repository = repository

    def submit(
        self,
        raw_request: bytes,
        *,
        context: TrustedCanonicalIngressContext,
    ) -> CanonicalIngressOutcome:
        request = self._contract.parse_request(raw_request)
        effective_scope = context.effective_scope()

        scope_error = self._scope_error(request, context, effective_scope)
        if scope_error is not None:
            return self._rejected(
                request,
                context=context,
                spec=scope_error,
                effective_scope=None,
            )
        if not self._authority_is_authorized(request, context):
            return self._rejected(
                request,
                context=context,
                spec=_AUTHORITY_CONFLICT,
                effective_scope=effective_scope,
            )

        key_reference = idempotency_key_reference(cast(str, request["idempotency_key"]))
        idempotency_scope = context.idempotency_scope_fingerprint()
        try:
            existing = self._repository.get_by_idempotency(
                scope_fingerprint=idempotency_scope,
                key_reference=key_reference,
            )
        except CanonicalIngressPersistenceError:
            return self._rejected(
                request,
                context=context,
                spec=_SYSTEM_ERROR,
                effective_scope=effective_scope,
            )
        if existing is not None:
            if existing.document.get("request_fingerprint") != request.get(
                "request_fingerprint"
            ):
                return self._rejected(
                    request,
                    context=context,
                    spec=_IDEMPOTENCY_CONFLICT,
                    effective_scope=effective_scope,
                    key_reference=key_reference,
                    idempotency_scope=idempotency_scope,
                    idempotency_outcome="CONFLICT",
                )
            return self._replay(request, existing)

        try:
            self._contract.validate_runtime_resolution(context.runtime_resolution)
            context.build_plan.verify()
        except (CanonicalIngressContractError, ValueError):
            return self._rejected(
                request,
                context=context,
                spec=_RUNTIME_RESOLUTION_FAILED,
                effective_scope=effective_scope,
            )
        build_plan = context.build_plan.document
        if build_plan.get("planning_inputs") != request.get("planning_inputs"):
            return self._rejected(
                request,
                context=context,
                spec=_INVALID_REFERENCE,
                effective_scope=effective_scope,
            )

        payload = cast(Mapping[str, object], request["payload"])
        quality = validate_import_package(payload)
        if not quality.passed:
            return self._rejected(
                request,
                context=context,
                spec=_DATA_VALIDATION_FAILED,
                effective_scope=effective_scope,
                quality=quality,
            )

        try:
            expansion = expand_orders(
                cast(Any, payload), cast(Mapping[str, object], quality.document)
            )
            snapshot = build_planning_snapshot(
                payload,
                cast(Mapping[str, object], quality.document),
                expansion,
                cutoff_at_utc=cast(str, build_plan["cutoff_at_utc"]),
            )
            problem = build_planning_problem_v2(
                snapshot,
                priority_facts=cast(
                    Mapping[str, Mapping[str, object]], build_plan["priority_facts"]
                ),
                problem_builder_version=cast(
                    str, build_plan["problem_builder_version"]
                ),
                tick_seconds=cast(int, build_plan["tick_seconds"]),
                horizon_start_utc=cast(str, build_plan["horizon_start_utc"]),
                horizon_end_utc=cast(str, build_plan["horizon_end_utc"]),
            )
        except SnapshotError:
            return self._rejected(
                request,
                context=context,
                spec=_LINEAGE_INVALID,
                effective_scope=effective_scope,
                quality=quality,
            )
        except (OrderExpansionError, PlanningProblemError):
            return self._rejected(
                request,
                context=context,
                spec=_MODEL_INVALID,
                effective_scope=effective_scope,
                quality=quality,
            )

        record = self._build_record(
            request=request,
            context=context,
            effective_scope=effective_scope,
            idempotency_scope=idempotency_scope,
            key_reference=key_reference,
            quality=quality,
            snapshot=snapshot,
            problem=problem,
        )
        try:
            write = self._repository.commit(record)
        except CanonicalIngressPersistenceError as error:
            spec = (
                _IDEMPOTENCY_CONFLICT
                if error.code is CanonicalIngressPersistenceCode.IDEMPOTENCY_CONFLICT
                else _SYSTEM_ERROR
            )
            return self._rejected(
                request,
                context=context,
                spec=spec,
                effective_scope=effective_scope,
                key_reference=(
                    key_reference if spec is _IDEMPOTENCY_CONFLICT else None
                ),
                idempotency_scope=(
                    idempotency_scope if spec is _IDEMPOTENCY_CONFLICT else None
                ),
                idempotency_outcome=(
                    "CONFLICT" if spec is _IDEMPOTENCY_CONFLICT else "NOT_RECORDED"
                ),
                quality=quality,
            )
        if write.replayed and write.record.document.get(
            "request_fingerprint"
        ) != request.get("request_fingerprint"):
            return self._rejected(
                request,
                context=context,
                spec=_IDEMPOTENCY_CONFLICT,
                effective_scope=effective_scope,
                key_reference=key_reference,
                idempotency_scope=idempotency_scope,
                idempotency_outcome="CONFLICT",
                quality=quality,
            )
        if write.replayed:
            return self._replay(request, write.record)
        return self._outcome_from_record(write.record, replayed=False)

    def _scope_error(
        self,
        request: Mapping[str, object],
        context: TrustedCanonicalIngressContext,
        effective_scope: Mapping[str, object],
    ) -> _HeadlessErrorSpec | None:
        requested = cast(Mapping[str, object], request["requested_scope"])
        if requested.get("data_plane") != context.data_plane:
            return _DATA_PLANE_MISMATCH
        if context.data_plane == "PRODUCTION" and not context.production_binding:
            return _DATA_PLANE_MISMATCH
        try:
            self._contract.validate_effective_scope(
                effective_scope, requested_scope=requested
            )
        except CanonicalIngressContractError as error:
            if error.code is CanonicalIngressContractCode.DATA_PLANE_MISMATCH:
                return _DATA_PLANE_MISMATCH
            return _SCOPE_MISMATCH
        return None

    @staticmethod
    def _authority_is_authorized(
        request: Mapping[str, object], context: TrustedCanonicalIngressContext
    ) -> bool:
        authority = cast(Mapping[str, object], request["source_authority"])
        bindings = cast(list[Mapping[str, object]], authority["bindings"])
        mappings = cast(list[Mapping[str, object]], authority["mapping_provenance"])
        request_authorities = {
            cast(str, item["authority_reference"]) for item in bindings
        }
        request_mappings = {
            cast(str, item["mapping_profile_fingerprint"]) for item in mappings
        }
        return request_authorities == set(
            context.authorized_authority_references
        ) and request_mappings == set(context.authorized_mapping_fingerprints)

    def _build_record(
        self,
        *,
        request: JsonObject,
        context: TrustedCanonicalIngressContext,
        effective_scope: JsonObject,
        idempotency_scope: str,
        key_reference: str,
        quality: DataValidationResult,
        snapshot: ImmutablePlanningSnapshot,
        problem: ImmutablePlanningProblemV2,
    ) -> CanonicalIngressRecord:
        seed = {
            "idempotency_scope_fingerprint": idempotency_scope,
            "idempotency_key_reference": key_reference,
            "request_fingerprint": request["request_fingerprint"],
        }
        ingress_id = _identity("canonical-ingress", seed)
        planning_run_id = _identity("planning-run", seed)
        audit_event_id = _identity("audit-event", {**seed, "transition": 0})
        result_id = _identity(
            "canonical-ingress-result", {**seed, "outcome": "CREATED"}
        )
        payload = cast(Mapping[str, object], request["payload"])
        payload_reference = _artifact_reference(
            "import-package.v2",
            cast(str, payload["package_id"]),
            cast(str, request["payload_fingerprint"]),
        )
        audit = self._build_audit(
            request=request,
            context=context,
            planning_run_id=planning_run_id,
            audit_event_id=audit_event_id,
            idempotency_scope=idempotency_scope,
            key_reference=key_reference,
            synthetic=cast(bool, payload["synthetic"]),
            synthetic_provenance=cast(
                Mapping[str, object] | None, payload.get("synthetic_provenance")
            ),
        )
        self._contract.validate_audit_event(audit)
        audit_reference = _artifact_reference(
            "audit-event.v1", audit_event_id, canonical_fingerprint(audit)
        )
        runtime_resolution = context.runtime_resolution
        artifacts = {
            "import_quality_report": None,
            "snapshot": None,
            "problem": None,
            "planning_solution": None,
            "solver_report": None,
            "validation_report": None,
            "schedule_version": None,
        }
        planning_run: JsonObject = {
            "planning_run_version": "planning-run.v1",
            "schema_set_version": HEADLESS_SCHEMA_SET_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "transition_registry_version": "state-machines.v1",
            "error_registry_version": "headless-error-code-registry.v1",
            "planning_run_id": planning_run_id,
            "revision": 1,
            "state": "CREATED",
            "terminal": False,
            "allowed_actions": ["READ", "CANCEL"],
            "effective_scope": effective_scope,
            "ingress": {
                "request_id": request["request_id"],
                "request_fingerprint": request["request_fingerprint"],
                "ingress_id": ingress_id,
                "payload": payload_reference,
                "idempotency_key_reference": key_reference,
                "idempotency_scope_fingerprint": idempotency_scope,
            },
            "runtime_resolution": runtime_resolution,
            "inputs": request["planning_inputs"],
            "attempt": None,
            "artifacts": artifacts,
            "cancellation": None,
            "error": None,
            "last_transition": {
                "transition_version": "planning-run-transition.v1",
                "sequence": 0,
                "from_state": None,
                "to_state": "CREATED",
                "occurred_at_utc": context.occurred_at_utc,
                "audit": audit_reference,
            },
            "audit_references": [audit_reference],
            "created_at_utc": context.occurred_at_utc,
            "updated_at_utc": context.occurred_at_utc,
            "run_fingerprint": "",
        }
        planning_run["run_fingerprint"] = run_fingerprint(planning_run)
        self._contract.validate_planning_run(planning_run, request=request)
        result = self._accepted_result(
            request=request,
            result_id=result_id,
            occurred_at_utc=context.occurred_at_utc,
            effective_scope=effective_scope,
            idempotency_scope=idempotency_scope,
            key_reference=key_reference,
            ingress_id=ingress_id,
            payload_reference=payload_reference,
            runtime_resolution=runtime_resolution,
            planning_run=planning_run,
            audit_reference=audit_reference,
            outcome="CREATED",
        )
        self._contract.validate_result(
            result, request=request, planning_run=planning_run
        )
        sanitized_request = {
            key: value for key, value in request.items() if key != "idempotency_key"
        }
        sanitized_request["idempotency_key_reference"] = key_reference
        quality_reference = _artifact_reference(
            "import-quality-report.v1",
            cast(str, quality.document["report_id"]),
            canonical_fingerprint(quality.document),
        )
        problem_reference = _artifact_reference(
            "planning-problem.v2",
            f"planning-problem-{problem.problem_hash.removeprefix('sha256:')}",
            problem.problem_hash,
        )
        snapshot_reference = _artifact_reference(
            "planning-snapshot.v2",
            snapshot.snapshot_id,
            snapshot.snapshot_hash,
        )
        base: JsonObject = {
            "record_version": CANONICAL_INGRESS_RECORD_VERSION,
            "ingress_id": ingress_id,
            "request_id": request["request_id"],
            "correlation_id": request["correlation_id"],
            "request_fingerprint": request["request_fingerprint"],
            "canonical_request": sanitized_request,
            "effective_scope": effective_scope,
            "idempotency": {
                "scope_fingerprint": idempotency_scope,
                "key_reference": key_reference,
            },
            "runtime_resolution": runtime_resolution,
            "build_plan": context.build_plan.document,
            "import_quality_report": quality.document,
            "prepared_artifacts": {
                "import_quality_report": quality_reference,
                "snapshot": snapshot_reference,
                "problem": problem_reference,
            },
            "planning_run": planning_run,
            "audit_event": audit,
            "canonical_ingress_result": result,
            "occurred_at_utc": context.occurred_at_utc,
        }
        record_document = {
            **base,
            "record_fingerprint": canonical_fingerprint(base),
        }
        return CanonicalIngressRecord(
            canonical_bytes=canonical_json_bytes(record_document),
            snapshot=snapshot,
            problem=problem,
        )

    @staticmethod
    def _build_audit(
        *,
        request: Mapping[str, object],
        context: TrustedCanonicalIngressContext,
        planning_run_id: str,
        audit_event_id: str,
        idempotency_scope: str,
        key_reference: str,
        synthetic: bool,
        synthetic_provenance: Mapping[str, object] | None,
    ) -> JsonObject:
        audit: JsonObject = {
            "audit_event_version": "audit-event.v1",
            "schema_set_version": "2.6.0",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "audit_event_id": audit_event_id,
            "occurred_at_utc": context.occurred_at_utc,
            "actor_ref": context.actor_reference,
            "resolved_capability": context.resolved_capability,
            "auth_policy_version": context.auth_policy_version,
            "environment": context.environment,
            "data_plane": context.data_plane,
            "synthetic": synthetic,
            "action": "EDIT_SCHEDULE",
            "aggregate_type": "PLANNING_RUN",
            "aggregate_id": planning_run_id,
            "target": (
                "SIMULATION_INTERNAL"
                if context.data_plane == "SIMULATION"
                else "WORKSPACE_INTERNAL"
            ),
            "intent_type": "COMMAND",
            "reason": "Create a PlanningRun from validated canonical input.",
            "request_fingerprint": request["request_fingerprint"],
            "idempotency_reference": {
                "scope": idempotency_scope,
                "key_reference": key_reference,
                "request_fingerprint": request["request_fingerprint"],
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
            "correlation_id": request["correlation_id"],
            "parent_audit_event_id": None,
            "code_commit": context.code_commit,
        }
        if synthetic:
            audit["synthetic_provenance"] = synthetic_provenance
        return audit

    @staticmethod
    def _accepted_result(
        *,
        request: Mapping[str, object],
        result_id: str,
        occurred_at_utc: str,
        effective_scope: Mapping[str, object],
        idempotency_scope: str,
        key_reference: str,
        ingress_id: str,
        payload_reference: Mapping[str, object],
        runtime_resolution: Mapping[str, object],
        planning_run: Mapping[str, object],
        audit_reference: Mapping[str, object],
        outcome: str,
    ) -> JsonObject:
        base: JsonObject = {
            "canonical_ingress_result_version": CANONICAL_INGRESS_RESULT_VERSION,
            "schema_set_version": HEADLESS_SCHEMA_SET_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "result_id": result_id,
            "request_id": request["request_id"],
            "correlation_id": request["correlation_id"],
            "request_fingerprint": request["request_fingerprint"],
            "disposition": "ACCEPTED",
            "side_effects": "PLANNING_RUN_CREATED_OR_REPLAYED",
            "idempotency": {
                "outcome": outcome,
                "key_reference": key_reference,
                "scope_fingerprint": idempotency_scope,
            },
            "effective_scope": effective_scope,
            "accepted": {
                "ingress_id": ingress_id,
                "payload": payload_reference,
                "runtime_resolution": runtime_resolution,
                "planning_run": {
                    "document_version": "planning-run.v1",
                    "planning_run_id": planning_run["planning_run_id"],
                    "revision": planning_run["revision"],
                    "state": planning_run["state"],
                    "run_fingerprint": planning_run["run_fingerprint"],
                },
                "audit": audit_reference,
            },
            "rejection": None,
            "occurred_at_utc": occurred_at_utc,
            "result_fingerprint": "",
        }
        base["result_fingerprint"] = result_fingerprint(base)
        return base

    def _rejected(
        self,
        request: Mapping[str, object],
        *,
        context: TrustedCanonicalIngressContext,
        spec: _HeadlessErrorSpec,
        effective_scope: Mapping[str, object] | None,
        key_reference: str | None = None,
        idempotency_scope: str | None = None,
        idempotency_outcome: str = "NOT_RECORDED",
        quality: DataValidationResult | None = None,
    ) -> CanonicalIngressOutcome:
        result_id = _identity(
            "canonical-ingress-result",
            {
                "request_id": request["request_id"],
                "correlation_id": request["correlation_id"],
                "request_fingerprint": request["request_fingerprint"],
                "outcome": idempotency_outcome,
                "error_code": spec.code,
                "occurred_at_utc": context.occurred_at_utc,
            },
        )
        base: JsonObject = {
            "canonical_ingress_result_version": CANONICAL_INGRESS_RESULT_VERSION,
            "schema_set_version": HEADLESS_SCHEMA_SET_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "result_id": result_id,
            "request_id": request["request_id"],
            "correlation_id": request["correlation_id"],
            "request_fingerprint": request["request_fingerprint"],
            "disposition": "REJECTED",
            "side_effects": "NONE",
            "idempotency": {
                "outcome": idempotency_outcome,
                "key_reference": key_reference,
                "scope_fingerprint": idempotency_scope,
            },
            "effective_scope": effective_scope,
            "accepted": None,
            "rejection": _headless_error(
                spec,
                correlation_id=cast(str, request["correlation_id"]),
                entity_reference=cast(str, request["request_id"]),
            ),
            "occurred_at_utc": context.occurred_at_utc,
            "result_fingerprint": "",
        }
        base["result_fingerprint"] = result_fingerprint(base)
        self._contract.validate_result(base, request=request)
        return CanonicalIngressOutcome(
            canonical_result_bytes=canonical_json_bytes(base),
            planning_run_bytes=None,
            quality_report_bytes=(quality.canonical_bytes if quality else None),
            snapshot=None,
            problem=None,
            replayed=False,
        )

    def _replay(
        self,
        request: Mapping[str, object],
        record: CanonicalIngressRecord,
    ) -> CanonicalIngressOutcome:
        document = record.document
        created = cast(Mapping[str, object], document["canonical_ingress_result"])
        planning_run = cast(Mapping[str, object], document["planning_run"])
        accepted = cast(Mapping[str, object], created["accepted"])
        audit_reference = cast(Mapping[str, object], accepted["audit"])
        payload_reference = cast(Mapping[str, object], accepted["payload"])
        idempotency = cast(Mapping[str, object], created["idempotency"])
        replay_id = _identity(
            "canonical-ingress-replay-result",
            {
                "created_result_id": created["result_id"],
                "request_id": request["request_id"],
                "correlation_id": request["correlation_id"],
            },
        )
        replay = self._accepted_result(
            request=request,
            result_id=replay_id,
            occurred_at_utc=cast(str, created["occurred_at_utc"]),
            effective_scope=cast(Mapping[str, object], created["effective_scope"]),
            idempotency_scope=cast(str, idempotency["scope_fingerprint"]),
            key_reference=cast(str, idempotency["key_reference"]),
            ingress_id=cast(str, accepted["ingress_id"]),
            payload_reference=payload_reference,
            runtime_resolution=cast(
                Mapping[str, object], accepted["runtime_resolution"]
            ),
            planning_run=planning_run,
            audit_reference=audit_reference,
            outcome="REPLAYED",
        )
        self._contract.validate_result(
            replay, request=request, planning_run=planning_run
        )
        return CanonicalIngressOutcome(
            canonical_result_bytes=canonical_json_bytes(replay),
            planning_run_bytes=canonical_json_bytes(planning_run),
            quality_report_bytes=canonical_json_bytes(
                document["import_quality_report"]
            ),
            snapshot=record.snapshot,
            problem=record.problem,
            replayed=True,
        )

    @staticmethod
    def _outcome_from_record(
        record: CanonicalIngressRecord, *, replayed: bool
    ) -> CanonicalIngressOutcome:
        document = record.document
        result = cast(Mapping[str, object], document["canonical_ingress_result"])
        planning_run = cast(Mapping[str, object], document["planning_run"])
        return CanonicalIngressOutcome(
            canonical_result_bytes=canonical_json_bytes(result),
            planning_run_bytes=canonical_json_bytes(planning_run),
            quality_report_bytes=canonical_json_bytes(
                document["import_quality_report"]
            ),
            snapshot=record.snapshot,
            problem=record.problem,
            replayed=replayed,
        )


def verify_canonical_ingress_record(record: CanonicalIngressRecord) -> None:
    """Verify immutable record bytes and prepared artifact lineage."""

    try:
        document = record.document
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CanonicalIngressPersistenceError(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field="record_json",
            message="Stored canonical ingress record is unreadable",
        ) from error
    if document.get("record_version") != CANONICAL_INGRESS_RECORD_VERSION:
        raise CanonicalIngressPersistenceError(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field="record_version",
            message="Stored canonical ingress record version is unsupported",
        )
    expected = canonical_fingerprint(
        {key: value for key, value in document.items() if key != "record_fingerprint"}
    )
    if document.get("record_fingerprint") != expected:
        raise CanonicalIngressPersistenceError(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field="record_fingerprint",
            message="Stored canonical ingress record fingerprint is invalid",
        )
    prepared = document.get("prepared_artifacts")
    if not isinstance(prepared, Mapping):
        raise CanonicalIngressPersistenceError(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field="prepared_artifacts",
            message="Stored canonical ingress artifact references are invalid",
        )
    snapshot_ref = prepared.get("snapshot")
    problem_ref = prepared.get("problem")
    if (
        not isinstance(snapshot_ref, Mapping)
        or snapshot_ref.get("artifact_id") != record.snapshot.snapshot_id
        or snapshot_ref.get("fingerprint") != record.snapshot.snapshot_hash
        or not isinstance(problem_ref, Mapping)
        or problem_ref.get("fingerprint") != record.problem.problem_hash
        or record.problem.snapshot_id != record.snapshot.snapshot_id
    ):
        raise CanonicalIngressPersistenceError(
            CanonicalIngressPersistenceCode.CONTENT_CONFLICT,
            field="prepared_artifacts",
            message="Stored canonical ingress artifact lineage is inconsistent",
        )


__all__ = [
    "CANONICAL_INGRESS_BUILD_PLAN_VERSION",
    "CANONICAL_INGRESS_RECORD_VERSION",
    "CanonicalIngressApplicationService",
    "CanonicalIngressBuildPlan",
    "CanonicalIngressOutcome",
    "CanonicalIngressPersistenceCode",
    "CanonicalIngressPersistenceError",
    "CanonicalIngressRecord",
    "CanonicalIngressRepository",
    "CanonicalIngressWriteResult",
    "TrustedCanonicalIngressContext",
    "verify_canonical_ingress_record",
]
