"""Server-owned host identity, scope authorization, and audit contracts.

Bearer syntax and provider-specific claims stop at the verifier port.  The
application adapter accepts only a small verified identity projection and
derives every permission and business scope from an immutable operator policy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any, NoReturn, Protocol, cast
from uuid import uuid4

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.types import canonical_id, format_utc_instant, parse_utc_instant


type JsonObject = dict[str, Any]

VERIFIED_HOST_IDENTITY_VERSION = "verified-host-identity.v1"
HOST_AUTHORIZATION_POLICY_VERSION = "host-authorization-policy.v1"
HOST_AUTHORIZATION_AUDIT_VERSION = "headless-authorization-audit.v1"

HEADLESS_OPERATION_CAPABILITIES: Mapping[str, str] = {
    "createHeadlessPlanningRun": "edit",
    "getHeadlessPlanningRunStatus": "view",
    "cancelHeadlessPlanningRun": "edit",
    "retryHeadlessPlanningRun": "edit",
    "getHeadlessPlanningRunResult": "view",
}

_VISIBLE_ASCII = re.compile(r"[!-~]{1,512}")
_ACTOR = re.compile(r"actor:[A-Za-z0-9._:-]{1,240}")
_SUBJECT = re.compile(r"subject:[A-Za-z0-9._:-]{1,238}")
_POLICY_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_PROVIDER = re.compile(r"identity-provider:[A-Za-z0-9._:-]{1,238}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_AUDIT_ID = re.compile(r"host-authz-event-[0-9a-f]{32}")
_CORRELATION = re.compile(r"[!-~]{1,256}")
_RESOURCE_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_POLICY_FIELDS = frozenset(
    {
        "host_authorization_policy_version",
        "policy_id",
        "identity_provider_reference",
        "issuer",
        "audience",
        "environment",
        "data_plane",
        "production_binding",
        "max_assertion_lifetime_seconds",
        "revoked_subject_references",
        "revoked_assertion_references",
        "principals",
    }
)
_PRINCIPAL_FIELDS = frozenset({"subject_ref", "actor_ref", "operations", "scopes"})
_SCOPE_FIELDS = frozenset({"tenant_id", "factory_id", "planning_scope_id"})
_NON_PRODUCTION_ENVIRONMENTS = frozenset({"DEVELOPMENT", "TEST", "BENCHMARK"})
_AUDIT_FIELDS = frozenset(
    {
        "audit_version",
        "audit_event_id",
        "occurred_at_utc",
        "operation_id",
        "required_capability",
        "outcome",
        "reason",
        "actor_ref",
        "subject_ref",
        "identity_provider_reference",
        "assertion_reference",
        "auth_policy_version",
        "auth_policy_fingerprint",
        "requested_scope",
        "scope_fingerprint",
        "resource_type",
        "resource_reference",
        "data_plane",
        "environment",
        "correlation_id",
    }
)


class HostAuthorizationReason(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    PRODUCTION_AUTHORITY_UNAVAILABLE = "PRODUCTION_AUTHORITY_UNAVAILABLE"
    SIMULATION_API_DISABLED = "SIMULATION_API_DISABLED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_AUTHENTICATION = "INVALID_AUTHENTICATION"
    IDENTITY_PROVIDER_UNAVAILABLE = "IDENTITY_PROVIDER_UNAVAILABLE"
    IDENTITY_CONFIGURATION_UNAVAILABLE = "IDENTITY_CONFIGURATION_UNAVAILABLE"
    INVALID_PROVIDER_CONTEXT = "INVALID_PROVIDER_CONTEXT"
    ISSUER_MISMATCH = "ISSUER_MISMATCH"
    AUDIENCE_MISMATCH = "AUDIENCE_MISMATCH"
    ASSERTION_NOT_YET_VALID = "ASSERTION_NOT_YET_VALID"
    ASSERTION_EXPIRED = "ASSERTION_EXPIRED"
    ASSERTION_LIFETIME_EXCEEDED = "ASSERTION_LIFETIME_EXCEEDED"
    ASSERTION_REVOKED = "ASSERTION_REVOKED"
    SUBJECT_REVOKED = "SUBJECT_REVOKED"
    SUBJECT_UNMAPPED = "SUBJECT_UNMAPPED"
    OPERATION_DENIED = "OPERATION_DENIED"
    FACTORY_SCOPE_DENIED = "FACTORY_SCOPE_DENIED"
    AUDIT_PERSISTENCE_FAILED = "AUDIT_PERSISTENCE_FAILED"


_STATUS_BY_REASON: Mapping[HostAuthorizationReason, int] = {
    HostAuthorizationReason.PRODUCTION_AUTHORITY_UNAVAILABLE: 403,
    HostAuthorizationReason.SIMULATION_API_DISABLED: 403,
    HostAuthorizationReason.AUTHENTICATION_REQUIRED: 401,
    HostAuthorizationReason.INVALID_AUTHENTICATION: 401,
    HostAuthorizationReason.IDENTITY_PROVIDER_UNAVAILABLE: 503,
    HostAuthorizationReason.IDENTITY_CONFIGURATION_UNAVAILABLE: 503,
    HostAuthorizationReason.INVALID_PROVIDER_CONTEXT: 401,
    HostAuthorizationReason.ISSUER_MISMATCH: 401,
    HostAuthorizationReason.AUDIENCE_MISMATCH: 401,
    HostAuthorizationReason.ASSERTION_NOT_YET_VALID: 401,
    HostAuthorizationReason.ASSERTION_EXPIRED: 401,
    HostAuthorizationReason.ASSERTION_LIFETIME_EXCEEDED: 401,
    HostAuthorizationReason.ASSERTION_REVOKED: 401,
    HostAuthorizationReason.SUBJECT_REVOKED: 403,
    HostAuthorizationReason.SUBJECT_UNMAPPED: 403,
    HostAuthorizationReason.OPERATION_DENIED: 403,
    HostAuthorizationReason.FACTORY_SCOPE_DENIED: 403,
    HostAuthorizationReason.AUDIT_PERSISTENCE_FAILED: 500,
}


class HostAuthorizationError(RuntimeError):
    """Stable failure whose provider detail is never copied to HTTP or audit."""

    def __init__(self, reason: HostAuthorizationReason) -> None:
        self.reason = reason
        self.status_code = _STATUS_BY_REASON[reason]
        super().__init__(reason.value)


@dataclass(frozen=True, slots=True, order=True)
class HostPlanningScope:
    tenant_id: str
    factory_id: str
    planning_scope_id: str

    @classmethod
    def create(
        cls, *, tenant_id: str, factory_id: str, planning_scope_id: str
    ) -> HostPlanningScope:
        try:
            values = tuple(
                str(canonical_id(value))
                for value in (tenant_id, factory_id, planning_scope_id)
            )
        except (TypeError, ValueError) as error:
            raise ValueError("host planning scope is invalid") from error
        if any(value == "*" for value in values):
            raise ValueError("host planning scope cannot use wildcard authority")
        return cls(*values)

    @property
    def document(self) -> JsonObject:
        return {
            "tenant_id": self.tenant_id,
            "factory_id": self.factory_id,
            "planning_scope_id": self.planning_scope_id,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.document)


@dataclass(frozen=True, slots=True)
class VerifiedHostIdentity:
    """Provider-neutral assertion facts; raw bearer and arbitrary claims are absent."""

    subject_ref: str
    identity_provider_reference: str
    issuer: str
    audience: str
    issued_at_utc: str
    expires_at_utc: str
    identity_version: str = VERIFIED_HOST_IDENTITY_VERSION

    @classmethod
    def create(
        cls,
        *,
        subject_ref: str,
        identity_provider_reference: str,
        issuer: str,
        audience: str,
        issued_at_utc: str,
        expires_at_utc: str,
    ) -> VerifiedHostIdentity:
        if _SUBJECT.fullmatch(subject_ref) is None:
            raise ValueError("verified subject reference is invalid")
        if _PROVIDER.fullmatch(identity_provider_reference) is None:
            raise ValueError("identity provider reference is invalid")
        if (
            _VISIBLE_ASCII.fullmatch(issuer) is None
            or _VISIBLE_ASCII.fullmatch(audience) is None
        ):
            raise ValueError("identity issuer or audience is invalid")
        issued = parse_utc_instant(issued_at_utc)
        expires = parse_utc_instant(expires_at_utc)
        if (
            format_utc_instant(issued) != issued_at_utc
            or format_utc_instant(expires) != expires_at_utc
            or expires <= issued
        ):
            raise ValueError("identity assertion lifetime is invalid")
        return cls(
            subject_ref=subject_ref,
            identity_provider_reference=identity_provider_reference,
            issuer=issuer,
            audience=audience,
            issued_at_utc=issued_at_utc,
            expires_at_utc=expires_at_utc,
        )


class HostIdentityProvider(Protocol):
    """Replaceable verifier; implementations own token parsing and cryptography."""

    def verify(self, bearer_token: str) -> VerifiedHostIdentity | None: ...


class UnavailableHostIdentityProvider:
    def verify(self, bearer_token: str) -> VerifiedHostIdentity | None:
        del bearer_token
        raise RuntimeError("host identity provider is not configured")


@dataclass(frozen=True, slots=True)
class _PrincipalGrant:
    subject_ref: str
    actor_ref: str
    operations: frozenset[str]
    scopes: frozenset[HostPlanningScope]


def _strict_string(value: object, *, field: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _strict_string_list(
    value: object,
    *,
    field: str,
    pattern: re.Pattern[str],
    allow_empty: bool,
    maximum: int = 1_000,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded list")
    if not allow_empty and not value:
        raise ValueError(f"{field} must not be empty")
    result = tuple(_strict_string(item, field=field, pattern=pattern) for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{field} contains duplicates")
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class HostAuthorizationPolicyCatalog:
    """Strict server-owned subject, operation, and exact factory-scope mapping."""

    canonical_bytes: bytes
    policy_id: str
    identity_provider_reference: str
    issuer: str
    audience: str
    environment: str
    data_plane: str
    max_assertion_lifetime_seconds: int
    grants: tuple[_PrincipalGrant, ...]
    revoked_subject_references: frozenset[str]
    revoked_assertion_references: frozenset[str]

    @classmethod
    def create(cls, document: Mapping[str, object]) -> HostAuthorizationPolicyCatalog:
        if set(document) != _POLICY_FIELDS:
            raise ValueError("host authorization policy has an invalid field set")
        if document.get("host_authorization_policy_version") != (
            HOST_AUTHORIZATION_POLICY_VERSION
        ):
            raise ValueError("host authorization policy version is unsupported")
        policy_id = _strict_string(
            document.get("policy_id"), field="policy_id", pattern=_POLICY_ID
        )
        provider = _strict_string(
            document.get("identity_provider_reference"),
            field="identity_provider_reference",
            pattern=_PROVIDER,
        )
        issuer = _strict_string(
            document.get("issuer"), field="issuer", pattern=_VISIBLE_ASCII
        )
        audience = _strict_string(
            document.get("audience"), field="audience", pattern=_VISIBLE_ASCII
        )
        environment = document.get("environment")
        data_plane = document.get("data_plane")
        if environment not in _NON_PRODUCTION_ENVIRONMENTS or data_plane != "SIMULATION":
            raise ValueError("host authorization policy is non-Production only")
        if document.get("production_binding") is not False:
            raise ValueError("host authorization policy cannot grant Production")
        maximum_lifetime = document.get("max_assertion_lifetime_seconds")
        if (
            type(maximum_lifetime) is not int
            or not 1 <= maximum_lifetime <= 86_400
        ):
            raise ValueError("maximum assertion lifetime is invalid")
        revoked_subjects = _strict_string_list(
            document.get("revoked_subject_references"),
            field="revoked_subject_references",
            pattern=_SUBJECT,
            allow_empty=True,
        )
        revoked_assertions = _strict_string_list(
            document.get("revoked_assertion_references"),
            field="revoked_assertion_references",
            pattern=_FINGERPRINT,
            allow_empty=True,
        )
        raw_principals = document.get("principals")
        if (
            not isinstance(raw_principals, list)
            or not raw_principals
            or len(raw_principals) > 1_000
        ):
            raise ValueError("host authorization policy requires bounded principals")
        grants: list[_PrincipalGrant] = []
        normalized_principals: list[JsonObject] = []
        for index, raw_principal in enumerate(raw_principals):
            if not isinstance(raw_principal, Mapping) or set(raw_principal) != (
                _PRINCIPAL_FIELDS
            ):
                raise ValueError(f"principals[{index}] has an invalid field set")
            subject_ref = _strict_string(
                raw_principal.get("subject_ref"),
                field=f"principals[{index}].subject_ref",
                pattern=_SUBJECT,
            )
            actor_ref = _strict_string(
                raw_principal.get("actor_ref"),
                field=f"principals[{index}].actor_ref",
                pattern=_ACTOR,
            )
            operations = _strict_string_list(
                raw_principal.get("operations"),
                field=f"principals[{index}].operations",
                pattern=_POLICY_ID,
                allow_empty=False,
                maximum=len(HEADLESS_OPERATION_CAPABILITIES),
            )
            if not set(operations).issubset(HEADLESS_OPERATION_CAPABILITIES):
                raise ValueError("principal contains an unknown Headless operation")
            raw_scopes = raw_principal.get("scopes")
            if (
                not isinstance(raw_scopes, list)
                or not raw_scopes
                or len(raw_scopes) > 1_000
            ):
                raise ValueError("principal requires bounded exact scopes")
            scopes: list[HostPlanningScope] = []
            for scope_index, raw_scope in enumerate(raw_scopes):
                if not isinstance(raw_scope, Mapping) or set(raw_scope) != _SCOPE_FIELDS:
                    raise ValueError(
                        f"principals[{index}].scopes[{scope_index}] is invalid"
                    )
                scopes.append(
                    HostPlanningScope.create(
                        tenant_id=cast(str, raw_scope["tenant_id"]),
                        factory_id=cast(str, raw_scope["factory_id"]),
                        planning_scope_id=cast(str, raw_scope["planning_scope_id"]),
                    )
                )
            if len(set(scopes)) != len(scopes):
                raise ValueError("principal contains duplicate factory scopes")
            grant = _PrincipalGrant(
                subject_ref=subject_ref,
                actor_ref=actor_ref,
                operations=frozenset(operations),
                scopes=frozenset(scopes),
            )
            grants.append(grant)
            normalized_principals.append(
                {
                    "subject_ref": subject_ref,
                    "actor_ref": actor_ref,
                    "operations": list(operations),
                    "scopes": [scope.document for scope in sorted(scopes)],
                }
            )
        if len({grant.subject_ref for grant in grants}) != len(grants):
            raise ValueError("host authorization policy contains duplicate subjects")
        normalized_principals.sort(key=lambda value: cast(str, value["subject_ref"]))
        normalized: JsonObject = {
            "host_authorization_policy_version": HOST_AUTHORIZATION_POLICY_VERSION,
            "policy_id": policy_id,
            "identity_provider_reference": provider,
            "issuer": issuer,
            "audience": audience,
            "environment": environment,
            "data_plane": data_plane,
            "production_binding": False,
            "max_assertion_lifetime_seconds": maximum_lifetime,
            "revoked_subject_references": list(revoked_subjects),
            "revoked_assertion_references": list(revoked_assertions),
            "principals": normalized_principals,
        }
        return cls(
            canonical_bytes=canonical_json_bytes(normalized),
            policy_id=policy_id,
            identity_provider_reference=provider,
            issuer=issuer,
            audience=audience,
            environment=cast(str, environment),
            data_plane=cast(str, data_plane),
            max_assertion_lifetime_seconds=cast(int, maximum_lifetime),
            grants=tuple(grants),
            revoked_subject_references=frozenset(revoked_subjects),
            revoked_assertion_references=frozenset(revoked_assertions),
        )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(json.loads(self.canonical_bytes))

    @property
    def safe_reference(self) -> JsonObject:
        return {
            "policy_version": HOST_AUTHORIZATION_POLICY_VERSION,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.fingerprint,
            "identity_provider_reference": self.identity_provider_reference,
            "principal_count": len(self.grants),
            "scope_count": sum(len(grant.scopes) for grant in self.grants),
        }

    def grant_for(self, subject_ref: str) -> _PrincipalGrant | None:
        return next(
            (grant for grant in self.grants if grant.subject_ref == subject_ref), None
        )


@dataclass(frozen=True, slots=True)
class HostAuthorizationRequest:
    operation_id: str
    requested_scope: HostPlanningScope
    resource_type: str
    resource_id: str | None
    correlation_id: str
    occurred_at_utc: str

    @classmethod
    def create(
        cls,
        *,
        operation_id: str,
        tenant_id: str,
        factory_id: str,
        planning_scope_id: str,
        resource_type: str,
        resource_id: str | None,
        correlation_id: str,
        occurred_at_utc: str,
    ) -> HostAuthorizationRequest:
        if operation_id not in HEADLESS_OPERATION_CAPABILITIES:
            raise ValueError("Headless operation is not registered")
        if _RESOURCE_TYPE.fullmatch(resource_type) is None:
            raise ValueError("authorization resource type is invalid")
        if resource_id is not None:
            resource_id = str(canonical_id(resource_id))
        if _CORRELATION.fullmatch(correlation_id) is None:
            raise ValueError("authorization correlation is invalid")
        occurred = parse_utc_instant(occurred_at_utc)
        if format_utc_instant(occurred) != occurred_at_utc:
            raise ValueError("authorization time is not canonical")
        return cls(
            operation_id=operation_id,
            requested_scope=HostPlanningScope.create(
                tenant_id=tenant_id,
                factory_id=factory_id,
                planning_scope_id=planning_scope_id,
            ),
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
            occurred_at_utc=occurred_at_utc,
        )


@dataclass(frozen=True, slots=True)
class HostAuthorizationAuditRecord:
    document: JsonObject
    canonical_bytes: bytes
    fingerprint: str

    @classmethod
    def create(cls, document: Mapping[str, object]) -> HostAuthorizationAuditRecord:
        """Validate the complete sanitized carrier before any durable append."""

        if set(document) != _AUDIT_FIELDS:
            raise ValueError("host authorization audit has an invalid field set")
        if document.get("audit_version") != HOST_AUTHORIZATION_AUDIT_VERSION:
            raise ValueError("host authorization audit version is unsupported")
        event_id = _strict_string(
            document.get("audit_event_id"), field="audit_event_id", pattern=_AUDIT_ID
        )
        operation_id = document.get("operation_id")
        if operation_id not in HEADLESS_OPERATION_CAPABILITIES:
            raise ValueError("host authorization audit operation is invalid")
        operation_id = cast(str, operation_id)
        required_capability = document.get("required_capability")
        if required_capability != HEADLESS_OPERATION_CAPABILITIES[operation_id]:
            raise ValueError("host authorization audit capability is invalid")
        outcome = document.get("outcome")
        if outcome not in {"ALLOWED", "DENIED"}:
            raise ValueError("host authorization audit outcome is invalid")
        try:
            reason = HostAuthorizationReason(document.get("reason"))
        except (TypeError, ValueError):
            raise ValueError("host authorization audit reason is invalid") from None
        if (outcome == "ALLOWED") != (reason is HostAuthorizationReason.AUTHORIZED):
            raise ValueError("host authorization audit outcome and reason conflict")
        actor_ref = _strict_string(
            document.get("actor_ref"), field="actor_ref", pattern=_ACTOR
        )

        def optional_string(field: str, pattern: re.Pattern[str]) -> str | None:
            value = document.get(field)
            if value is None:
                return None
            return _strict_string(value, field=field, pattern=pattern)

        subject_ref = optional_string("subject_ref", _SUBJECT)
        provider_ref = optional_string("identity_provider_reference", _PROVIDER)
        assertion_ref = optional_string("assertion_reference", _FINGERPRINT)
        policy_version = optional_string("auth_policy_version", _POLICY_ID)
        policy_fingerprint = optional_string("auth_policy_fingerprint", _FINGERPRINT)
        if (provider_ref is None) != (policy_version is None) or (
            policy_version is None
        ) != (policy_fingerprint is None):
            raise ValueError("host authorization audit policy reference is incomplete")
        if outcome == "ALLOWED" and (
            subject_ref is None
            or assertion_ref is None
            or provider_ref is None
            or policy_version is None
            or policy_fingerprint is None
        ):
            raise ValueError("allowed host authorization audit lacks authority evidence")

        raw_scope = document.get("requested_scope")
        if not isinstance(raw_scope, Mapping) or set(raw_scope) != _SCOPE_FIELDS:
            raise ValueError("host authorization audit scope is invalid")
        scope = HostPlanningScope.create(
            tenant_id=cast(str, raw_scope["tenant_id"]),
            factory_id=cast(str, raw_scope["factory_id"]),
            planning_scope_id=cast(str, raw_scope["planning_scope_id"]),
        )
        if document.get("scope_fingerprint") != scope.fingerprint:
            raise ValueError("host authorization audit scope fingerprint is invalid")
        resource_type = _strict_string(
            document.get("resource_type"),
            field="resource_type",
            pattern=_RESOURCE_TYPE,
        )
        resource_reference = optional_string("resource_reference", _FINGERPRINT)
        correlation = _strict_string(
            document.get("correlation_id"),
            field="correlation_id",
            pattern=_CORRELATION,
        )
        occurred_at = document.get("occurred_at_utc")
        if not isinstance(occurred_at, str):
            raise ValueError("host authorization audit time is invalid")
        parsed_time = parse_utc_instant(occurred_at)
        if format_utc_instant(parsed_time) != occurred_at:
            raise ValueError("host authorization audit time is not canonical")
        data_plane = document.get("data_plane")
        environment = document.get("environment")
        if data_plane == "SIMULATION":
            if environment not in _NON_PRODUCTION_ENVIRONMENTS:
                raise ValueError("host authorization audit Simulation binding is invalid")
        elif data_plane == "PRODUCTION":
            if environment != "PRODUCTION":
                raise ValueError("host authorization audit Production binding is invalid")
        else:
            raise ValueError("host authorization audit data plane is invalid")

        normalized: JsonObject = {
            "audit_version": HOST_AUTHORIZATION_AUDIT_VERSION,
            "audit_event_id": event_id,
            "occurred_at_utc": occurred_at,
            "operation_id": operation_id,
            "required_capability": required_capability,
            "outcome": outcome,
            "reason": reason.value,
            "actor_ref": actor_ref,
            "subject_ref": subject_ref,
            "identity_provider_reference": provider_ref,
            "assertion_reference": assertion_ref,
            "auth_policy_version": policy_version,
            "auth_policy_fingerprint": policy_fingerprint,
            "requested_scope": scope.document,
            "scope_fingerprint": scope.fingerprint,
            "resource_type": resource_type,
            "resource_reference": resource_reference,
            "data_plane": data_plane,
            "environment": environment,
            "correlation_id": correlation,
        }
        canonical = canonical_json_bytes(normalized)
        return cls(
            document=normalized,
            canonical_bytes=canonical,
            fingerprint=canonical_fingerprint(normalized),
        )


class HostAuthorizationAuditSink(Protocol):
    def append(self, record: HostAuthorizationAuditRecord) -> None: ...


class HostAuthorizationPort(Protocol):
    def authorize(
        self,
        authorization_header: str | None,
        request: HostAuthorizationRequest,
    ) -> AuthorizedHostPrincipal: ...


@dataclass(frozen=True, slots=True)
class AuthorizedHostPrincipal:
    actor_reference: str
    subject_reference: str
    application_capability: str
    auth_policy_version: str
    auth_policy_fingerprint: str
    assertion_reference: str
    requested_scope: HostPlanningScope
    production_binding: bool = False


def _token_reference(token: str) -> str:
    return f"sha256:{sha256(token.encode('utf-8')).hexdigest()}"


def _bearer(authorization_header: str | None) -> tuple[str | None, str | None]:
    if authorization_header is None:
        return None, None
    scheme, separator, token = authorization_header.partition(" ")
    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not token
        or len(token) > 4_096
        or any(character.isspace() for character in token)
    ):
        return None, None
    return token, _token_reference(token)


def _resource_reference(request: HostAuthorizationRequest) -> str | None:
    if request.resource_id is None:
        return None
    return canonical_fingerprint(
        {"resource_type": request.resource_type, "resource_id": request.resource_id}
    )


def _audit_record(
    request: HostAuthorizationRequest,
    *,
    event_id: str,
    environment: str,
    data_plane: str,
    policy: HostAuthorizationPolicyCatalog | None,
    outcome: str,
    reason: HostAuthorizationReason,
    assertion_reference: str | None,
    subject_ref: str | None,
    actor_ref: str,
) -> HostAuthorizationAuditRecord:
    if _AUDIT_ID.fullmatch(event_id) is None:
        raise ValueError("host authorization audit identity is invalid")
    document: JsonObject = {
        "audit_version": HOST_AUTHORIZATION_AUDIT_VERSION,
        "audit_event_id": event_id,
        "occurred_at_utc": request.occurred_at_utc,
        "operation_id": request.operation_id,
        "required_capability": HEADLESS_OPERATION_CAPABILITIES[request.operation_id],
        "outcome": outcome,
        "reason": reason.value,
        "actor_ref": actor_ref,
        "subject_ref": subject_ref,
        "identity_provider_reference": (
            policy.identity_provider_reference if policy is not None else None
        ),
        "assertion_reference": assertion_reference,
        "auth_policy_version": policy.policy_id if policy is not None else None,
        "auth_policy_fingerprint": policy.fingerprint if policy is not None else None,
        "requested_scope": request.requested_scope.document,
        "scope_fingerprint": request.requested_scope.fingerprint,
        "resource_type": request.resource_type,
        "resource_reference": _resource_reference(request),
        "data_plane": data_plane,
        "environment": environment,
        "correlation_id": request.correlation_id,
    }
    return HostAuthorizationAuditRecord.create(document)


class HostAuthorizationAdapter:
    """Verify one opaque assertion, derive exact authority, and audit the decision."""

    def __init__(
        self,
        *,
        provider: HostIdentityProvider,
        policy: HostAuthorizationPolicyCatalog,
        audit_sink: HostAuthorizationAuditSink,
        environment: str,
        data_plane: str,
        simulation_api_enabled: bool,
        audit_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._audit_sink = audit_sink
        self._environment = environment
        self._data_plane = data_plane
        self._simulation_api_enabled = simulation_api_enabled
        self._audit_id_factory = audit_id_factory or (
            lambda: f"host-authz-event-{uuid4().hex}"
        )
        if policy.environment != environment or policy.data_plane != data_plane:
            raise ValueError("host authorization policy does not match Runtime binding")

    @property
    def safe_reference(self) -> JsonObject:
        return {
            "adapter_version": "host-authorization-adapter.v1",
            **self._policy.safe_reference,
        }

    def _append(
        self,
        request: HostAuthorizationRequest,
        *,
        outcome: str,
        reason: HostAuthorizationReason,
        assertion_reference: str | None,
        subject_ref: str | None,
        actor_ref: str,
    ) -> None:
        try:
            record = _audit_record(
                request,
                event_id=self._audit_id_factory(),
                environment=self._environment,
                data_plane=self._data_plane,
                policy=self._policy,
                outcome=outcome,
                reason=reason,
                assertion_reference=assertion_reference,
                subject_ref=subject_ref,
                actor_ref=actor_ref,
            )
            self._audit_sink.append(record)
        except Exception:
            raise HostAuthorizationError(
                HostAuthorizationReason.AUDIT_PERSISTENCE_FAILED
            ) from None

    def _deny(
        self,
        request: HostAuthorizationRequest,
        reason: HostAuthorizationReason,
        *,
        assertion_reference: str | None = None,
        subject_ref: str | None = None,
        actor_ref: str = "actor:unresolved",
    ) -> NoReturn:
        self._append(
            request,
            outcome="DENIED",
            reason=reason,
            assertion_reference=assertion_reference,
            subject_ref=subject_ref,
            actor_ref=actor_ref,
        )
        raise HostAuthorizationError(reason)

    def authorize(
        self,
        authorization_header: str | None,
        request: HostAuthorizationRequest,
    ) -> AuthorizedHostPrincipal:
        if self._data_plane == "PRODUCTION" or self._environment == "PRODUCTION":
            self._deny(
                request, HostAuthorizationReason.PRODUCTION_AUTHORITY_UNAVAILABLE
            )
        if self._data_plane != "SIMULATION" or not self._simulation_api_enabled:
            self._deny(request, HostAuthorizationReason.SIMULATION_API_DISABLED)
        token, assertion_reference = _bearer(authorization_header)
        if token is None:
            self._deny(
                request,
                (
                    HostAuthorizationReason.AUTHENTICATION_REQUIRED
                    if authorization_header is None
                    else HostAuthorizationReason.INVALID_AUTHENTICATION
                ),
            )
        try:
            identity = self._provider.verify(cast(str, token))
        except Exception:
            self._deny(
                request,
                HostAuthorizationReason.IDENTITY_PROVIDER_UNAVAILABLE,
                assertion_reference=assertion_reference,
            )
        if identity is None:
            self._deny(
                request,
                HostAuthorizationReason.INVALID_AUTHENTICATION,
                assertion_reference=assertion_reference,
            )
        if not isinstance(identity, VerifiedHostIdentity):
            self._deny(
                request,
                HostAuthorizationReason.INVALID_PROVIDER_CONTEXT,
                assertion_reference=assertion_reference,
            )
        identity = cast(VerifiedHostIdentity, identity)
        try:
            normalized_identity = VerifiedHostIdentity.create(
                subject_ref=identity.subject_ref,
                identity_provider_reference=identity.identity_provider_reference,
                issuer=identity.issuer,
                audience=identity.audience,
                issued_at_utc=identity.issued_at_utc,
                expires_at_utc=identity.expires_at_utc,
            )
        except (TypeError, ValueError):
            self._deny(
                request,
                HostAuthorizationReason.INVALID_PROVIDER_CONTEXT,
                assertion_reference=assertion_reference,
            )
        if normalized_identity != identity:
            self._deny(
                request,
                HostAuthorizationReason.INVALID_PROVIDER_CONTEXT,
                assertion_reference=assertion_reference,
            )
        identity = normalized_identity
        subject_ref = identity.subject_ref
        if identity.identity_provider_reference != self._policy.identity_provider_reference:
            self._deny(
                request,
                HostAuthorizationReason.INVALID_PROVIDER_CONTEXT,
                assertion_reference=assertion_reference,
            )
        if identity.issuer != self._policy.issuer:
            self._deny(
                request,
                HostAuthorizationReason.ISSUER_MISMATCH,
                assertion_reference=assertion_reference,
            )
        if identity.audience != self._policy.audience:
            self._deny(
                request,
                HostAuthorizationReason.AUDIENCE_MISMATCH,
                assertion_reference=assertion_reference,
            )
        issued = parse_utc_instant(identity.issued_at_utc)
        expires = parse_utc_instant(identity.expires_at_utc)
        now = parse_utc_instant(request.occurred_at_utc)
        if issued > now:
            self._deny(
                request,
                HostAuthorizationReason.ASSERTION_NOT_YET_VALID,
                assertion_reference=assertion_reference,
            )
        if expires <= now:
            self._deny(
                request,
                HostAuthorizationReason.ASSERTION_EXPIRED,
                assertion_reference=assertion_reference,
            )
        if expires - issued > timedelta(
            seconds=self._policy.max_assertion_lifetime_seconds
        ):
            self._deny(
                request,
                HostAuthorizationReason.ASSERTION_LIFETIME_EXCEEDED,
                assertion_reference=assertion_reference,
            )
        if assertion_reference in self._policy.revoked_assertion_references:
            self._deny(
                request,
                HostAuthorizationReason.ASSERTION_REVOKED,
                assertion_reference=assertion_reference,
            )
        if subject_ref in self._policy.revoked_subject_references:
            self._deny(
                request,
                HostAuthorizationReason.SUBJECT_REVOKED,
                assertion_reference=assertion_reference,
                subject_ref=subject_ref,
            )
        grant = self._policy.grant_for(subject_ref)
        if grant is None:
            self._deny(
                request,
                HostAuthorizationReason.SUBJECT_UNMAPPED,
                assertion_reference=assertion_reference,
                subject_ref=subject_ref,
            )
        grant = cast(_PrincipalGrant, grant)
        if request.operation_id not in grant.operations:
            self._deny(
                request,
                HostAuthorizationReason.OPERATION_DENIED,
                assertion_reference=assertion_reference,
                subject_ref=subject_ref,
                actor_ref=grant.actor_ref,
            )
        if request.requested_scope not in grant.scopes:
            self._deny(
                request,
                HostAuthorizationReason.FACTORY_SCOPE_DENIED,
                assertion_reference=assertion_reference,
                subject_ref=subject_ref,
                actor_ref=grant.actor_ref,
            )
        self._append(
            request,
            outcome="ALLOWED",
            reason=HostAuthorizationReason.AUTHORIZED,
            assertion_reference=assertion_reference,
            subject_ref=subject_ref,
            actor_ref=grant.actor_ref,
        )
        return AuthorizedHostPrincipal(
            actor_reference=grant.actor_ref,
            subject_reference=subject_ref,
            application_capability=HEADLESS_OPERATION_CAPABILITIES[request.operation_id],
            auth_policy_version=self._policy.policy_id,
            auth_policy_fingerprint=self._policy.fingerprint,
            assertion_reference=cast(str, assertion_reference),
            requested_scope=request.requested_scope,
        )


class UnavailableHostAuthorizationAdapter:
    """Explicit fail-closed adapter for a Runtime without configured host trust."""

    def __init__(
        self,
        *,
        audit_sink: HostAuthorizationAuditSink,
        environment: str,
        data_plane: str,
        audit_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._audit_sink = audit_sink
        self._environment = environment
        self._data_plane = data_plane
        self._audit_id_factory = audit_id_factory or (
            lambda: f"host-authz-event-{uuid4().hex}"
        )

    @property
    def safe_reference(self) -> JsonObject:
        return {
            "adapter_version": "host-authorization-adapter.v1",
            "policy_version": None,
            "policy_fingerprint": None,
            "availability": "UNAVAILABLE",
        }

    def authorize(
        self,
        authorization_header: str | None,
        request: HostAuthorizationRequest,
    ) -> NoReturn:
        _, assertion_reference = _bearer(authorization_header)
        reason = (
            HostAuthorizationReason.PRODUCTION_AUTHORITY_UNAVAILABLE
            if self._data_plane == "PRODUCTION" or self._environment == "PRODUCTION"
            else HostAuthorizationReason.IDENTITY_CONFIGURATION_UNAVAILABLE
        )
        try:
            self._audit_sink.append(
                _audit_record(
                    request,
                    event_id=self._audit_id_factory(),
                    environment=self._environment,
                    data_plane=self._data_plane,
                    policy=None,
                    outcome="DENIED",
                    reason=reason,
                    assertion_reference=assertion_reference,
                    subject_ref=None,
                    actor_ref="actor:unresolved",
                )
            )
        except Exception:
            raise HostAuthorizationError(
                HostAuthorizationReason.AUDIT_PERSISTENCE_FAILED
            ) from None
        raise HostAuthorizationError(reason)


__all__ = [
    "HEADLESS_OPERATION_CAPABILITIES",
    "HOST_AUTHORIZATION_AUDIT_VERSION",
    "HOST_AUTHORIZATION_POLICY_VERSION",
    "VERIFIED_HOST_IDENTITY_VERSION",
    "AuthorizedHostPrincipal",
    "HostAuthorizationAdapter",
    "HostAuthorizationAuditRecord",
    "HostAuthorizationAuditSink",
    "HostAuthorizationError",
    "HostAuthorizationPort",
    "HostAuthorizationPolicyCatalog",
    "HostAuthorizationReason",
    "HostAuthorizationRequest",
    "HostIdentityProvider",
    "HostPlanningScope",
    "UnavailableHostAuthorizationAdapter",
    "UnavailableHostIdentityProvider",
]
