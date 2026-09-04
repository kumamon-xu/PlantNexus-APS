"""Fail-closed local Simulation identity for the standalone Demo app."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
import os
from pathlib import Path
import secrets
from uuid import uuid4

from app.api.dependencies.authorization import (
    AuthorizationAuditRecord,
    PrincipalContext,
)
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .persistence import ControlStore, DemoPersistenceError, DemoRuntimePaths


DEMO_AUTH_POLICY_VERSION = "demo-local-simulation-auth.v1"
DEMO_ACTOR_REF = "actor:cnc-demo-presenter"
DEMO_SESSION_COOKIE = "plantnexus_demo_session"
DEMO_CAPABILITIES = frozenset(
    {
        "view",
        "event_ingest",
        "event_view",
        "replan",
        "replan_control",
        "replan_view",
        "demo_reset",
        "demo_plan",
        "demo_activate",
    }
)

IPAddress = IPv4Address | IPv6Address
IPNetwork = IPv4Network | IPv6Network


@dataclass(frozen=True, slots=True)
class DemoClientAccessPolicy:
    """Authorize the direct socket peer; forwarded headers are never trusted."""

    lan_enabled: bool = False
    allowed_networks: tuple[IPNetwork, ...] = ()

    @classmethod
    def loopback_only(cls) -> DemoClientAccessPolicy:
        return cls()

    def allows(self, peer_host: str) -> bool:
        if peer_host in {"localhost", "testclient"}:
            return True
        candidate = peer_host.partition("%")[0]
        try:
            address: IPAddress = ip_address(candidate)
        except ValueError:
            return False
        if address.is_loopback:
            return True
        return self.lan_enabled and any(
            address.version == network.version and address in network
            for network in self.allowed_networks
        )


class DemoClientAccessMiddleware:
    """Fail closed before static or API content is exposed to a denied peer."""

    def __init__(self, app: ASGIApp, *, policy: DemoClientAccessPolicy) -> None:
        self.app = app
        self.policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            client = scope.get("client")
            peer_host = "" if client is None else str(client[0])
            if not self.policy.allows(peer_host):
                raw_headers = {
                    key.decode("latin-1").lower(): value.decode("latin-1")
                    for key, value in scope.get("headers", [])
                }
                supplied = raw_headers.get("x-correlation-id")
                correlation_id = (
                    supplied
                    if supplied
                    and len(supplied) <= 256
                    and not any(character.isspace() for character in supplied)
                    else f"correlation-demo-{uuid4().hex}"
                )
                response = JSONResponse(
                    status_code=403,
                    content={
                        "error_version": "cnc-demo-error.v1",
                        "code": "AUTHORIZATION_DENIED",
                        "field": "client",
                        "message": "The Demo request could not be completed.",
                        "correlation_id": correlation_id,
                    },
                    headers={
                        "X-Correlation-Id": correlation_id,
                        "Cache-Control": "no-store",
                    },
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def load_or_create_local_token(paths: DemoRuntimePaths) -> str:
    """Load one non-production secret without ever including it in an error."""

    path = paths.token_file
    try:
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
        else:
            token = secrets.token_urlsafe(48)
            try:
                descriptor = os.open(
                    path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                token = path.read_text(encoding="utf-8").strip()
            else:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(token + "\n")
                try:
                    path.chmod(0o600)
                except OSError:
                    pass
    except (OSError, UnicodeError) as error:
        raise DemoPersistenceError(
            "AUTHORIZATION_PROVIDER_UNAVAILABLE",
            field="local_session",
            message="local Demo session could not be initialized",
        ) from error
    if not 32 <= len(token) <= 512 or any(character.isspace() for character in token):
        raise DemoPersistenceError(
            "AUTHORIZATION_PROVIDER_UNAVAILABLE",
            field="local_session",
            message="local Demo session is invalid",
        )
    return token


@dataclass(frozen=True, slots=True)
class SimulationLocalAuthorizationProvider:
    """Resolve exactly one local token to a scoped Simulation principal."""

    token: str
    capabilities: frozenset[str] = DEMO_CAPABILITIES
    planning_run_scope: frozenset[str] = frozenset({"*"})
    schedule_version_scope: frozenset[str] = frozenset({"*"})
    export_job_scope: frozenset[str] = frozenset()
    planning_scope_scope: frozenset[str] = frozenset({"*"})

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        if not hmac.compare_digest(bearer_token, self.token):
            return None
        return PrincipalContext(
            actor_ref=DEMO_ACTOR_REF,
            resolved_capabilities=self.capabilities,
            planning_run_scope=self.planning_run_scope,
            schedule_version_scope=self.schedule_version_scope,
            export_job_scope=self.export_job_scope,
            auth_policy_version=DEMO_AUTH_POLICY_VERSION,
            production_binding=False,
            planning_scope_scope=self.planning_scope_scope,
        )


@dataclass(frozen=True, slots=True)
class ControlAuthorizationAuditSink:
    """Persist sanitized authorization denials outside formal schedule audit."""

    control: ControlStore

    def record(self, event: AuthorizationAuditRecord) -> None:
        self.control.append_authorization_audit(
            correlation_id=event.correlation_id,
            actor_ref=event.actor_ref,
            capability=event.required_capability,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            outcome=event.outcome,
            reason=event.reason,
        )


def token_file_is_inside_runtime(paths: DemoRuntimePaths, path: Path) -> bool:
    try:
        path.resolve().relative_to(paths.root)
    except ValueError:
        return False
    return True


__all__ = [
    "ControlAuthorizationAuditSink",
    "DemoClientAccessMiddleware",
    "DemoClientAccessPolicy",
    "DEMO_ACTOR_REF",
    "DEMO_AUTH_POLICY_VERSION",
    "DEMO_CAPABILITIES",
    "DEMO_SESSION_COOKIE",
    "SimulationLocalAuthorizationProvider",
    "load_or_create_local_token",
    "token_file_is_inside_runtime",
]
