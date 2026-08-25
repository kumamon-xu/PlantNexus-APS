"""Server-derived, fail-closed authorization for the P3 HTTP boundary."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from fastapi import Request

from app.api.contracts import PlanningWorkspaceHttpError, public_http_error
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


_ACTOR = re.compile(r"actor:[A-Za-z0-9._:-]{1,240}")
_POLICY = re.compile(r"[A-Za-z0-9._:-]{1,256}")


@dataclass(frozen=True, slots=True)
class PrincipalContext:
    """Identity facts resolved by a server-side provider, never by request JSON."""

    actor_ref: str
    resolved_capabilities: frozenset[str]
    planning_run_scope: frozenset[str]
    schedule_version_scope: frozenset[str]
    export_job_scope: frozenset[str]
    auth_policy_version: str
    production_binding: bool = False


class AuthorizationProvider(Protocol):
    def resolve(self, bearer_token: str) -> PrincipalContext | None: ...


@dataclass(frozen=True, slots=True)
class AuthorizationAuditRecord:
    correlation_id: str
    actor_ref: str
    required_capability: str
    resource_type: str
    resource_id: str | None
    outcome: str
    reason: str
    data_plane: str
    environment: str


class AuthorizationAuditSink(Protocol):
    def record(self, event: AuthorizationAuditRecord) -> None: ...


class NullAuthorizationAuditSink:
    def record(self, event: AuthorizationAuditRecord) -> None:
        del event


class UnavailableAuthorizationProvider:
    """Default provider: no implicit development or Production identity."""

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        del bearer_token
        return None


def _environment(settings: Settings) -> str:
    mapping = {
        RuntimeEnvironment.DEVELOPMENT: "DEVELOPMENT",
        RuntimeEnvironment.TEST: "TEST",
        RuntimeEnvironment.BENCHMARK: "BENCHMARK",
        RuntimeEnvironment.PRODUCTION: "PRODUCTION",
    }
    value = mapping.get(settings.runtime_environment)
    if value is None:
        raise ValueError("runtime environment is not supported by workspace carriers")
    return value


def _plane(settings: Settings) -> str:
    if settings.data_plane is DataPlane.SIMULATION:
        return "SIMULATION"
    if settings.data_plane is DataPlane.PRODUCTION:
        return "PRODUCTION"
    raise ValueError("development data plane is not a workspace carrier plane")


def _record_denial(
    request: Request,
    *,
    correlation_id: str,
    actor_ref: str,
    required_capability: str,
    resource_type: str,
    resource_id: str | None,
    reason: str,
) -> None:
    settings: Settings = request.app.state.settings
    sink: AuthorizationAuditSink = request.app.state.authorization_audit_sink
    try:
        plane = _plane(settings)
    except ValueError:
        plane = settings.data_plane.value.upper()
    try:
        environment = _environment(settings)
    except ValueError:
        environment = settings.runtime_environment.value.upper()
    try:
        sink.record(
            AuthorizationAuditRecord(
                correlation_id=correlation_id,
                actor_ref=actor_ref,
                required_capability=required_capability,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="DENIED",
                reason=reason,
                data_plane=plane,
                environment=environment,
            )
        )
    except Exception:
        raise public_http_error(
            "PERSISTENCE_FAILED",
            correlation_id=correlation_id,
            field="authorization_audit",
        ) from None


def _deny(
    request: Request,
    *,
    correlation_id: str,
    actor_ref: str,
    required_capability: str,
    resource_type: str,
    resource_id: str | None,
    reason: str,
    status_code: int,
) -> PlanningWorkspaceHttpError:
    _record_denial(
        request,
        correlation_id=correlation_id,
        actor_ref=actor_ref,
        required_capability=required_capability,
        resource_type=resource_type,
        resource_id=resource_id,
        reason=reason,
    )
    return public_http_error(
        "AUTHORIZATION_DENIED",
        correlation_id=correlation_id,
        field="authorization",
        resource=(
            {"resource_type": resource_type, "resource_id": resource_id}
            if resource_id is not None
            else {"resource_type": resource_type}
        ),
        status_code=status_code,
    )


def _bearer(request: Request) -> str | None:
    value = request.headers.get("Authorization")
    if value is None:
        return None
    scheme, separator, token = value.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token or len(token) > 4096:
        return None
    return token


def _scope_allows(scope: frozenset[str], resource_id: str | None) -> bool:
    return resource_id is None or "*" in scope or resource_id in scope


def authorize_request(
    request: Request,
    *,
    correlation_id: str,
    required_capability: str,
    resource_type: str,
    resource_id: str | None = None,
) -> PrincipalContext:
    """Resolve a principal and enforce plane, capability, and resource scope."""

    settings: Settings = request.app.state.settings
    if settings.data_plane is DataPlane.PRODUCTION:
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref="actor:unresolved",
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="PRODUCTION_AUTHORITY_UNAVAILABLE",
            status_code=403,
        )
    if (
        settings.data_plane is not DataPlane.SIMULATION
        or not settings.simulation_api_enabled
    ):
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref="actor:unresolved",
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="SIMULATION_API_DISABLED",
            status_code=403,
        )
    token = _bearer(request)
    if token is None:
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref="actor:unresolved",
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="AUTHENTICATION_REQUIRED",
            status_code=401,
        )
    provider: AuthorizationProvider = request.app.state.authorization_provider
    try:
        principal = provider.resolve(token)
    except Exception:
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref="actor:unresolved",
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="AUTHORIZATION_PROVIDER_UNAVAILABLE",
            status_code=503,
        ) from None
    if principal is None:
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref="actor:unresolved",
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="INVALID_AUTHENTICATION",
            status_code=401,
        )
    if (
        _ACTOR.fullmatch(principal.actor_ref) is None
        or _POLICY.fullmatch(principal.auth_policy_version) is None
        or principal.production_binding
    ):
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref="actor:unresolved",
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="INVALID_PROVIDER_CONTEXT",
            status_code=403,
        )
    if required_capability not in principal.resolved_capabilities:
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref=principal.actor_ref,
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="CAPABILITY_DENIED",
            status_code=403,
        )
    scope = (
        principal.planning_run_scope
        if resource_type == "PLANNING_RUN"
        else principal.schedule_version_scope
        if resource_type == "SCHEDULE_VERSION"
        else principal.export_job_scope
        if resource_type == "EXPORT_JOB"
        else frozenset({"*"})
    )
    if not _scope_allows(scope, resource_id):
        raise _deny(
            request,
            correlation_id=correlation_id,
            actor_ref=principal.actor_ref,
            required_capability=required_capability,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="RESOURCE_SCOPE_DENIED",
            status_code=403,
        )
    return principal


def carrier_environment(settings: Settings) -> str:
    return _environment(settings)


def carrier_plane(settings: Settings) -> str:
    return _plane(settings)


__all__ = [
    "AuthorizationAuditRecord",
    "AuthorizationAuditSink",
    "AuthorizationProvider",
    "NullAuthorizationAuditSink",
    "PrincipalContext",
    "UnavailableAuthorizationProvider",
    "authorize_request",
    "carrier_environment",
    "carrier_plane",
]
