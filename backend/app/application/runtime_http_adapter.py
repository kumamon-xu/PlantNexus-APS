"""Server-owned context policy for the public Headless HTTP adapter.

The HTTP request may name a business scope, but it cannot manufacture the
effective Runtime context.  This module binds a strict operator document to
the already-composed Runtime identity and produces only the trusted context
types accepted by the P8 application façade.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
import json
import re
from typing import Any, NoReturn, cast

from app.application.canonical_ingress import (
    CanonicalIngressBuildPlan,
    TrustedCanonicalIngressContext,
)
from app.application.planning_runs import PlanningRunCommandContext
from app.application.runtime_facade import (
    RuntimeApplicationBinding,
    RuntimeDispatchWindow,
)
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.types import canonical_id, format_utc_instant, parse_utc_instant


type JsonObject = dict[str, Any]

RUNTIME_HTTP_POLICY_VERSION = "runtime-http-policy.v1"
RUNTIME_HTTP_CONTEXT_ADAPTER_VERSION = "runtime-http-context-adapter.v1"

_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_AUTHORITY = re.compile(r"authority:[A-Za-z0-9._:-]{1,246}")
_TOP_LEVEL_FIELDS = frozenset({"runtime_http_policy_version", "scopes"})
_SCOPE_FIELDS = frozenset(
    {
        "tenant_id",
        "factory_id",
        "planning_scope_id",
        "authorized_authority_references",
        "authorized_mapping_fingerprints",
        "build_plan",
        "dispatch_timeout_seconds",
    }
)
_BUILD_PLAN_FIELDS = frozenset(
    {
        "cutoff_at_utc",
        "tick_seconds",
        "horizon_start_utc",
        "horizon_end_utc",
        "priority_facts",
    }
)


class RuntimeHttpAdapterError(RuntimeError):
    """Stable error raised before invoking the Runtime application façade."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code}: {field}: {message}")


def _adapter_error(code: str, *, field: str, message: str) -> NoReturn:
    raise RuntimeHttpAdapterError(code, field=field, message=message)


@dataclass(frozen=True, slots=True)
class RuntimeHttpPrincipal:
    """Minimal server-resolved principal projection; no credential is retained."""

    actor_reference: str
    capabilities: tuple[str, ...]
    auth_policy_version: str
    production_binding: bool


@dataclass(frozen=True, slots=True)
class RuntimeHttpRequestedScope:
    """Requested coordinates that must match one operator-configured scope."""

    tenant_id: str
    factory_id: str
    planning_scope_id: str

    @classmethod
    def create(
        cls, *, tenant_id: str, factory_id: str, planning_scope_id: str
    ) -> RuntimeHttpRequestedScope:
        try:
            return cls(
                tenant_id=str(canonical_id(tenant_id)),
                factory_id=str(canonical_id(factory_id)),
                planning_scope_id=str(canonical_id(planning_scope_id)),
            )
        except (TypeError, ValueError) as error:
            raise RuntimeHttpAdapterError(
                "CONTRACT_VIOLATION",
                field="requested_scope",
                message="Requested scope identifiers are invalid",
            ) from error

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.tenant_id, self.factory_id, self.planning_scope_id)


@dataclass(frozen=True, slots=True)
class RuntimeHttpIngressContext:
    context: TrustedCanonicalIngressContext
    dispatch_window: RuntimeDispatchWindow


@dataclass(frozen=True, slots=True)
class _ScopePolicy:
    requested_scope: RuntimeHttpRequestedScope
    authorized_authority_references: tuple[str, ...]
    authorized_mapping_fingerprints: tuple[str, ...]
    cutoff_at_utc: str
    tick_seconds: int
    horizon_start_utc: str
    horizon_end_utc: str
    priority_facts_bytes: bytes
    dispatch_timeout_seconds: int

    @property
    def priority_facts(self) -> Mapping[str, Mapping[str, object]]:
        return cast(
            Mapping[str, Mapping[str, object]],
            json.loads(self.priority_facts_bytes),
        )


def _require_string_list(
    value: object,
    *,
    field: str,
    pattern: re.Pattern[str],
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > 256
        or any(
            not isinstance(item, str) or pattern.fullmatch(item) is None
            for item in value
        )
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"{field} must be a unique non-empty bounded list")
    return tuple(sorted(value))


def _scope_policy(value: object) -> _ScopePolicy:
    if not isinstance(value, Mapping) or set(value) != _SCOPE_FIELDS:
        raise ValueError("Runtime HTTP scope policy has an invalid field set")
    requested_scope = RuntimeHttpRequestedScope.create(
        tenant_id=cast(str, value["tenant_id"]),
        factory_id=cast(str, value["factory_id"]),
        planning_scope_id=cast(str, value["planning_scope_id"]),
    )
    authorities = _require_string_list(
        value["authorized_authority_references"],
        field="authorized_authority_references",
        pattern=_AUTHORITY,
    )
    mappings = _require_string_list(
        value["authorized_mapping_fingerprints"],
        field="authorized_mapping_fingerprints",
        pattern=_FINGERPRINT,
    )
    build = value["build_plan"]
    if not isinstance(build, Mapping) or set(build) != _BUILD_PLAN_FIELDS:
        raise ValueError("Runtime HTTP build plan has an invalid field set")
    cutoff = cast(str, build["cutoff_at_utc"])
    horizon_start = cast(str, build["horizon_start_utc"])
    horizon_end = cast(str, build["horizon_end_utc"])
    cutoff_instant = parse_utc_instant(cutoff)
    start_instant = parse_utc_instant(horizon_start)
    end_instant = parse_utc_instant(horizon_end)
    if cutoff_instant != start_instant or end_instant <= start_instant:
        raise ValueError("Runtime HTTP build horizon is inconsistent")
    tick_seconds = build["tick_seconds"]
    if type(tick_seconds) is not int or not 1 <= tick_seconds <= 86_400:
        raise ValueError("Runtime HTTP build tick is invalid")
    priority_facts = build["priority_facts"]
    if not isinstance(priority_facts, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, Mapping)
        for key, item in priority_facts.items()
    ):
        raise ValueError("Runtime HTTP priority facts are invalid")
    timeout = value["dispatch_timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= 86_400:
        raise ValueError("Runtime HTTP dispatch timeout is invalid")
    return _ScopePolicy(
        requested_scope=requested_scope,
        authorized_authority_references=authorities,
        authorized_mapping_fingerprints=mappings,
        cutoff_at_utc=cutoff,
        tick_seconds=tick_seconds,
        horizon_start_utc=horizon_start,
        horizon_end_utc=horizon_end,
        priority_facts_bytes=canonical_json_bytes(priority_facts),
        dispatch_timeout_seconds=timeout,
    )


@dataclass(frozen=True, slots=True)
class RuntimeHttpPolicyCatalog:
    """Immutable operator policy plus exact server planning-input references."""

    canonical_bytes: bytes
    planning_inputs_bytes: bytes
    scopes: tuple[_ScopePolicy, ...]

    @classmethod
    def create(
        cls,
        document: Mapping[str, object],
        *,
        planning_inputs: Mapping[str, object],
    ) -> RuntimeHttpPolicyCatalog:
        if set(document) != _TOP_LEVEL_FIELDS:
            raise ValueError("Runtime HTTP policy has an invalid field set")
        if document.get("runtime_http_policy_version") != RUNTIME_HTTP_POLICY_VERSION:
            raise ValueError("Runtime HTTP policy version is unsupported")
        raw_scopes = document.get("scopes")
        if not isinstance(raw_scopes, list) or not 1 <= len(raw_scopes) <= 1_000:
            raise ValueError("Runtime HTTP policy requires bounded scopes")
        scopes = tuple(_scope_policy(value) for value in raw_scopes)
        keys = [scope.requested_scope.key for scope in scopes]
        if len(set(keys)) != len(keys):
            raise ValueError("Runtime HTTP policy contains duplicate scopes")
        if set(planning_inputs) != {"planning_policy", "solve_limits"}:
            raise ValueError("Runtime planning inputs are invalid")
        return cls(
            canonical_bytes=canonical_json_bytes(document),
            planning_inputs_bytes=canonical_json_bytes(planning_inputs),
            scopes=scopes,
        )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(json.loads(self.canonical_bytes))

    @property
    def safe_reference(self) -> JsonObject:
        return {
            "policy_version": RUNTIME_HTTP_POLICY_VERSION,
            "policy_fingerprint": self.fingerprint,
            "configured_scope_count": len(self.scopes),
        }

    @property
    def planning_inputs(self) -> Mapping[str, object]:
        return cast(Mapping[str, object], json.loads(self.planning_inputs_bytes))


class RuntimeHttpContextAdapter:
    """Build trusted ingress/command contexts from one frozen Runtime binding."""

    def __init__(
        self,
        *,
        binding: RuntimeApplicationBinding,
        policy: RuntimeHttpPolicyCatalog,
    ) -> None:
        self._binding = binding
        self._policy = policy
        self._scopes = {scope.requested_scope.key: scope for scope in policy.scopes}

    @property
    def safe_reference(self) -> JsonObject:
        return {
            "adapter_version": RUNTIME_HTTP_CONTEXT_ADAPTER_VERSION,
            **self._policy.safe_reference,
        }

    def _policy_for(self, requested: RuntimeHttpRequestedScope) -> _ScopePolicy:
        policy = self._scopes.get(requested.key)
        if policy is None:
            _adapter_error(
                "SCOPE_MISMATCH",
                field="requested_scope",
                message="Requested scope is not configured for this Runtime",
            )
        return cast(_ScopePolicy, policy)

    def _window(
        self, policy: _ScopePolicy, occurred_at_utc: str
    ) -> RuntimeDispatchWindow:
        occurred = parse_utc_instant(occurred_at_utc)
        return RuntimeDispatchWindow(
            available_at_utc=format_utc_instant(occurred),
            timeout_at_utc=format_utc_instant(
                occurred + timedelta(seconds=policy.dispatch_timeout_seconds)
            ),
        )

    def ingress_context(
        self,
        request: Mapping[str, object],
        *,
        principal: RuntimeHttpPrincipal,
        occurred_at_utc: str,
    ) -> RuntimeHttpIngressContext:
        raw_scope = request.get("requested_scope")
        expected_scope_fields = {
            "tenant_id",
            "factory_id",
            "planning_scope_id",
            "data_plane",
            "environment",
        }
        if (
            not isinstance(raw_scope, Mapping)
            or set(raw_scope) != expected_scope_fields
        ):
            _adapter_error(
                "CONTRACT_VIOLATION",
                field="requested_scope",
                message="Canonical requested scope is invalid",
            )
        requested = RuntimeHttpRequestedScope.create(
            tenant_id=cast(str, raw_scope["tenant_id"]),
            factory_id=cast(str, raw_scope["factory_id"]),
            planning_scope_id=cast(str, raw_scope["planning_scope_id"]),
        )
        policy = self._policy_for(requested)
        if (
            raw_scope.get("data_plane") != self._binding.data_plane
            or raw_scope.get("environment") != self._binding.environment
        ):
            _adapter_error(
                "DATA_PLANE_MISMATCH",
                field="requested_scope.data_plane/environment",
                message="Requested Runtime plane or environment is unavailable",
            )
        if "edit" not in principal.capabilities:
            _adapter_error(
                "SCOPE_MISMATCH",
                field="principal.capabilities",
                message="Resolved principal cannot create a PlanningRun",
            )
        if principal.production_binding != self._binding.production_available:
            _adapter_error(
                "DATA_PLANE_MISMATCH",
                field="principal.production_binding",
                message="Principal authority differs from Runtime availability",
            )
        planning_inputs = request.get("planning_inputs")
        if not isinstance(planning_inputs, Mapping) or dict(planning_inputs) != dict(
            self._policy.planning_inputs
        ):
            _adapter_error(
                "INVALID_REFERENCE",
                field="planning_inputs",
                message="Planning inputs differ from the server catalog",
            )
        build_plan = CanonicalIngressBuildPlan.create(
            planning_inputs=planning_inputs,
            cutoff_at_utc=policy.cutoff_at_utc,
            tick_seconds=policy.tick_seconds,
            horizon_start_utc=policy.horizon_start_utc,
            horizon_end_utc=policy.horizon_end_utc,
            priority_facts=policy.priority_facts,
        )
        context = TrustedCanonicalIngressContext.create(
            actor_reference=principal.actor_reference,
            auth_policy_version=principal.auth_policy_version,
            tenant_id=requested.tenant_id,
            factory_id=requested.factory_id,
            planning_scope_id=requested.planning_scope_id,
            data_plane=self._binding.data_plane,
            environment=self._binding.environment,
            production_binding=principal.production_binding,
            authorized_authority_references=policy.authorized_authority_references,
            authorized_mapping_fingerprints=policy.authorized_mapping_fingerprints,
            runtime_resolution=self._binding.runtime_resolution,
            build_plan=build_plan,
            occurred_at_utc=occurred_at_utc,
            code_commit=self._binding.code_commit,
        )
        return RuntimeHttpIngressContext(
            context=context,
            dispatch_window=self._window(policy, occurred_at_utc),
        )

    def command_context(
        self,
        requested: RuntimeHttpRequestedScope,
        *,
        principal: RuntimeHttpPrincipal,
        correlation_id: str,
        occurred_at_utc: str,
    ) -> PlanningRunCommandContext:
        self._policy_for(requested)
        if principal.production_binding != self._binding.production_available:
            _adapter_error(
                "DATA_PLANE_MISMATCH",
                field="principal.production_binding",
                message="Principal authority differs from Runtime availability",
            )
        return PlanningRunCommandContext.create(
            actor_reference=principal.actor_reference,
            capabilities=principal.capabilities,
            auth_policy_version=principal.auth_policy_version,
            tenant_id=requested.tenant_id,
            factory_id=requested.factory_id,
            planning_scope_id=requested.planning_scope_id,
            data_plane=self._binding.data_plane,
            environment=self._binding.environment,
            production_binding=principal.production_binding,
            correlation_id=correlation_id,
            occurred_at_utc=occurred_at_utc,
            code_commit=self._binding.code_commit,
        )

    def dispatch_window(
        self,
        requested: RuntimeHttpRequestedScope,
        *,
        occurred_at_utc: str,
    ) -> RuntimeDispatchWindow:
        return self._window(self._policy_for(requested), occurred_at_utc)


__all__ = [
    "RUNTIME_HTTP_CONTEXT_ADAPTER_VERSION",
    "RUNTIME_HTTP_POLICY_VERSION",
    "RuntimeHttpAdapterError",
    "RuntimeHttpContextAdapter",
    "RuntimeHttpIngressContext",
    "RuntimeHttpPolicyCatalog",
    "RuntimeHttpPrincipal",
    "RuntimeHttpRequestedScope",
]
