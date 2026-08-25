"""Authority-neutral P3 approval/rejection domain semantics.

The frozen ``workspace-command.v1`` carrier expresses decision intent while
the server-resolved context supplies authentication, capability, policy, and
resource scope.  This module is pure: it reads no repository, performs no
network call, and never selects a real organization role or identity provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Never, cast

from app.domain.types import (
    ContractValueError,
    format_utc_instant,
    parse_utc_instant,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    require_workspace_document,
    workspace_fingerprint,
)


APPROVAL_DECISION_SERVICE_VERSION = "approval-decision-service.v1"

_COMMAND_FIELDS = frozenset(
    {
        "workspace_command_version",
        "schema_set_version",
        "canonicalization_version",
        "command_id",
        "command_type",
        "required_capability",
        "idempotency_key",
        "idempotency_scope",
        "request_fingerprint",
        "source_id",
        "expected_state",
        "expected_content_fingerprint",
        "data_plane",
        "environment",
        "synthetic",
        "synthetic_provenance",
        "target",
        "reason",
        "correlation_id",
        "payload",
    }
)
_DECISION_CAPABILITY = {"APPROVE": "approve", "REJECT": "reject"}
_DECISION_STATE = {"APPROVE": "APPROVED", "REJECT": "REJECTED"}
_DECISION_ACTIONS = {
    "APPROVE": ["view", "publish"],
    "REJECT": ["view", "edit", "lock"],
}
_APPLICATION_CAPABILITIES = frozenset(
    {"view", "edit", "lock", "approve", "reject", "publish", "export", "audit"}
)
_ACTOR_REFERENCE = re.compile(r"actor:[A-Za-z0-9._:-]+")
_CANONICAL_ID = re.compile(r"[^\s\x00-\x1f\x7f]+")
_GIT_COMMIT = re.compile(r"(?:[0-9a-f]{40}|uncommitted)")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{16,128}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_SECRET_TEXT = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|password\s*=|token\s*=|"
    r"secret\s*=|cookie\s*=|postgres(?:ql)?://|redis://)"
)


class ApprovalDecisionFailure(StrEnum):
    """Stable, sanitized failures for the P3 decision boundary."""

    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    PRODUCTION_AUTHORITY_UNAVAILABLE = "PRODUCTION_AUTHORITY_UNAVAILABLE"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    STALE_SOURCE = "STALE_SOURCE"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ApprovalDecisionError(ValueError):
    """One fail-closed decision rejection without credential or adapter detail."""

    def __init__(
        self,
        reason: ApprovalDecisionFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value}: {field}: {message}")


@dataclass(frozen=True, slots=True)
class ApprovalDecisionContext:
    """Server-resolved authorization facts, never client role claims."""

    actor_ref: str
    authenticated: bool
    resolved_capabilities: frozenset[str]
    schedule_version_scope: frozenset[str]
    auth_policy_version: str
    production_binding: bool
    occurred_at_utc: str
    code_commit: str
    parent_audit_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalDecisionIdentity:
    """Deterministic identity available before source or replay lookup."""

    command_type: str
    action: str
    required_capability: str
    target_state: str
    request_fingerprint: str
    key_reference: str
    schedule_version_id: str
    audit_event_id: str


@dataclass(frozen=True, slots=True)
class PreparedApprovalDecision:
    """An authorized READY source bound to one exact decision request."""

    source: dict[str, object]
    command: dict[str, object]
    identity: ApprovalDecisionIdentity
    context: ApprovalDecisionContext
    data_plane: str


@dataclass(frozen=True, slots=True)
class ApprovalDecisionDocuments:
    """Schedule state candidate and success audit committed atomically."""

    decided_schedule: dict[str, object]
    audit_event: dict[str, object]
    identity: ApprovalDecisionIdentity


def reject_approval_decision(
    reason: ApprovalDecisionFailure,
    *,
    field: str,
    message: str,
) -> Never:
    raise ApprovalDecisionError(reason, field=field, message=message)


def _clone(value: Mapping[str, object]) -> dict[str, object]:
    import json

    return cast(dict[str, object], json.loads(canonical_workspace_bytes(value)))


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def _text(value: object, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must be bounded non-empty text",
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must not contain control characters",
        )
    return value


def _reason(value: object, field: str) -> str:
    text = _text(value, field)
    if _SECRET_TEXT.search(text) is not None:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must not contain credential-like material",
        )
    return text


def _canonical_id(value: object, field: str) -> str:
    text = _text(value, field, maximum=256)
    if _CANONICAL_ID.fullmatch(text) is None:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must be a canonical identifier",
        )
    return text


def _fingerprint(value: object, field: str) -> str:
    text = _text(value, field, maximum=71)
    if _FINGERPRINT.fullmatch(text) is None:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must be a sha256 fingerprint",
        )
    return text


def _utc(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = parse_utc_instant(text)
    except ContractValueError as error:
        raise ApprovalDecisionError(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must be a valid RFC 3339 UTC instant ending in Z",
        ) from error
    if format_utc_instant(parsed) != text:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="must use canonical second-precision UTC",
        )
    return text


def _require_fields(
    value: Mapping[str, object], expected: frozenset[str], field: str
) -> None:
    if frozenset(value) != expected:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=field,
            message="fields do not match the frozen decision contract",
        )


def _validate_context(
    context: ApprovalDecisionContext,
    *,
    data_plane: str,
) -> None:
    actor_ref = _text(context.actor_ref, "context.actor_ref", maximum=256)
    if _ACTOR_REFERENCE.fullmatch(actor_ref) is None:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="context.actor_ref",
            message="must be a sanitized actor reference",
        )
    if not isinstance(context.authenticated, bool) or not isinstance(
        context.production_binding, bool
    ):
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="context.authentication",
            message="authentication and production binding must be boolean",
        )
    policy = _text(context.auth_policy_version, "context.auth_policy_version")
    _utc(context.occurred_at_utc, "context.occurred_at_utc")
    if _GIT_COMMIT.fullmatch(context.code_commit) is None:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="context.code_commit",
            message="must be a full Git commit or uncommitted",
        )
    if context.parent_audit_event_id is not None:
        _canonical_id(context.parent_audit_event_id, "context.parent_audit_event_id")
    for capability in context.resolved_capabilities:
        if capability not in _APPLICATION_CAPABILITIES:
            reject_approval_decision(
                ApprovalDecisionFailure.INVALID_REQUEST,
                field="context.resolved_capabilities",
                message="contains an unknown application capability",
            )
    for resource_id in context.schedule_version_scope:
        _canonical_id(resource_id, "context.schedule_version_scope")
    if data_plane not in {"SIMULATION", "PRODUCTION"}:
        reject_approval_decision(
            ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
            field="data_plane",
            message="must be SIMULATION or PRODUCTION",
        )
    if data_plane == "SIMULATION" and not any(
        marker in policy.lower() for marker in ("simulation", "test")
    ):
        reject_approval_decision(
            ApprovalDecisionFailure.AUTHORIZATION_DENIED,
            field="context.auth_policy_version",
            message="Simulation decisions require an explicit test policy",
        )


def approval_decision_identity(
    command: Mapping[str, object], *, data_plane: str
) -> ApprovalDecisionIdentity:
    """Validate an APPROVE/REJECT command and derive its hashed identity."""

    expected_fields = set(_COMMAND_FIELDS)
    if "synthetic_provenance" not in command:
        expected_fields.remove("synthetic_provenance")
    _require_fields(command, frozenset(expected_fields), "command")
    try:
        require_workspace_document(command)
    except (TypeError, ValueError) as error:
        raise ApprovalDecisionError(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=getattr(error, "field", "command"),
            message="failed the frozen workspace command contract",
        ) from error
    command_type = _text(command.get("command_type"), "command.command_type")
    if command_type not in _DECISION_CAPABILITY:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="command.command_type",
            message="TASK-P3-07 accepts only APPROVE or REJECT",
        )
    _require_fields(
        _mapping(command.get("payload"), "command.payload"),
        frozenset(),
        "command.payload",
    )
    source_id = _canonical_id(command.get("source_id"), "command.source_id")
    _canonical_id(command.get("command_id"), "command.command_id")
    _canonical_id(command.get("correlation_id"), "command.correlation_id")
    _reason(command.get("reason"), "command.reason")
    _fingerprint(command.get("request_fingerprint"), "command.request_fingerprint")
    _fingerprint(
        command.get("expected_content_fingerprint"),
        "command.expected_content_fingerprint",
    )
    if command.get("expected_state") != "READY_FOR_REVIEW":
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_STATE_TRANSITION,
            field="command.expected_state",
            message="approval decisions require READY_FOR_REVIEW",
        )
    if command.get("data_plane") != data_plane:
        reject_approval_decision(
            ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
            field="command.data_plane",
            message="does not match the repository plane",
        )
    if command.get("target") != "WORKSPACE_INTERNAL":
        reject_approval_decision(
            ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
            field="command.target",
            message="approval decisions are workspace-internal only",
        )
    synthetic = command.get("synthetic")
    if not isinstance(synthetic, bool):
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="command.synthetic",
            message="must be boolean",
        )
    if synthetic is True:
        _mapping(command.get("synthetic_provenance"), "command.synthetic_provenance")
    elif "synthetic_provenance" in command:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="command.synthetic_provenance",
            message="is forbidden for non-synthetic decisions",
        )
    environment = command.get("environment")
    if data_plane == "SIMULATION" and environment not in {
        "DEVELOPMENT",
        "TEST",
        "BENCHMARK",
    }:
        reject_approval_decision(
            ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
            field="command.environment",
            message="is not a Simulation environment",
        )
    if data_plane == "PRODUCTION" and (
        environment != "PRODUCTION" or synthetic is not False
    ):
        reject_approval_decision(
            ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
            field="command.environment/synthetic",
            message="is not a Production carrier",
        )
    key = _text(command.get("idempotency_key"), "command.idempotency_key", maximum=128)
    if _IDEMPOTENCY_KEY.fullmatch(key) is None:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="command.idempotency_key",
            message="does not match the frozen idempotency key contract",
        )
    scope = _text(command.get("idempotency_scope"), "command.idempotency_scope")
    expected_scope = f"{data_plane}/{command_type}/{source_id}/WORKSPACE_INTERNAL"
    if scope != expected_scope:
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field="command.idempotency_scope",
            message="does not match the server-derived decision scope",
        )
    key_reference = workspace_fingerprint(
        {"idempotency_scope": scope, "idempotency_key": key}
    )
    suffix = key_reference.removeprefix("sha256:")
    return ApprovalDecisionIdentity(
        command_type=command_type,
        action=command_type,
        required_capability=_DECISION_CAPABILITY[command_type],
        target_state=_DECISION_STATE[command_type],
        request_fingerprint=cast(str, command["request_fingerprint"]),
        key_reference=key_reference,
        schedule_version_id=source_id,
        audit_event_id=f"audit-event-decision-{suffix}",
    )


def require_approval_decision_authorization(
    context: ApprovalDecisionContext,
    identity: ApprovalDecisionIdentity,
    command: Mapping[str, object],
    *,
    data_plane: str,
) -> None:
    """Fail closed before source or idempotency-result lookup."""

    _validate_context(context, data_plane=data_plane)
    if data_plane == "PRODUCTION":
        reject_approval_decision(
            ApprovalDecisionFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
            field="data_plane",
            message="Production approval authority is not configured",
        )
    if context.production_binding:
        reject_approval_decision(
            ApprovalDecisionFailure.AUTHORIZATION_DENIED,
            field="context.production_binding",
            message="Simulation test policy cannot carry a Production binding",
        )
    if command.get("synthetic") is not True:
        reject_approval_decision(
            ApprovalDecisionFailure.AUTHORIZATION_DENIED,
            field="command.synthetic",
            message="Simulation decision policy is limited to synthetic resources",
        )
    if not context.authenticated:
        reject_approval_decision(
            ApprovalDecisionFailure.AUTHORIZATION_DENIED,
            field="context.authenticated",
            message="an authenticated principal is required",
        )
    if identity.required_capability not in context.resolved_capabilities:
        reject_approval_decision(
            ApprovalDecisionFailure.AUTHORIZATION_DENIED,
            field="context.resolved_capabilities",
            message="does not contain the server-required decision capability",
        )
    if identity.schedule_version_id not in context.schedule_version_scope:
        reject_approval_decision(
            ApprovalDecisionFailure.AUTHORIZATION_DENIED,
            field="context.schedule_version_scope",
            message="does not include the requested ScheduleVersion",
        )


def prepare_approval_decision(
    source: Mapping[str, object],
    command: Mapping[str, object],
    context: ApprovalDecisionContext,
    *,
    data_plane: str,
) -> PreparedApprovalDecision:
    """Bind an authorized decision to one exact READY immutable Version."""

    identity = approval_decision_identity(command, data_plane=data_plane)
    require_approval_decision_authorization(
        context, identity, command, data_plane=data_plane
    )
    try:
        require_workspace_document(source)
    except (TypeError, ValueError) as error:
        raise ApprovalDecisionError(
            ApprovalDecisionFailure.STALE_SOURCE,
            field=getattr(error, "field", "source"),
            message="authoritative ScheduleVersion failed its carrier contract",
        ) from error
    if source.get("schedule_version_id") != identity.schedule_version_id:
        reject_approval_decision(
            ApprovalDecisionFailure.STALE_SOURCE,
            field="command.source_id",
            message="does not match the authoritative ScheduleVersion",
        )
    if source.get("state") != "READY_FOR_REVIEW":
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_STATE_TRANSITION,
            field="source.state",
            message="only READY_FOR_REVIEW can receive a decision",
        )
    if source.get("content_fingerprint") != command.get("expected_content_fingerprint"):
        reject_approval_decision(
            ApprovalDecisionFailure.STALE_SOURCE,
            field="command.expected_content_fingerprint",
            message="does not match the authoritative ScheduleVersion",
        )
    for field in ("data_plane", "environment", "synthetic"):
        if source.get(field) != command.get(field):
            reject_approval_decision(
                ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
                field=f"command.{field}",
                message="does not match the authoritative ScheduleVersion",
            )
    if source.get("synthetic_provenance") != command.get("synthetic_provenance"):
        reject_approval_decision(
            ApprovalDecisionFailure.DATA_PLANE_MISMATCH,
            field="command.synthetic_provenance",
            message="does not match the authoritative ScheduleVersion",
        )
    if any(
        source.get(field) is not None
        for field in ("decision", "publication", "superseded_by")
    ):
        reject_approval_decision(
            ApprovalDecisionFailure.INVALID_STATE_TRANSITION,
            field="source.decision/publication/superseded_by",
            message="READY_FOR_REVIEW must not contain prior decision state",
        )
    return PreparedApprovalDecision(
        source=_clone(source),
        command=_clone(command),
        identity=identity,
        context=context,
        data_plane=data_plane,
    )


def _audit_base(
    command: Mapping[str, object],
    context: ApprovalDecisionContext,
    identity: ApprovalDecisionIdentity,
    *,
    lineage: Mapping[str, object] | None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "audit_event_version": "audit-event.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "audit_event_id": identity.audit_event_id,
        "occurred_at_utc": context.occurred_at_utc,
        "actor_ref": context.actor_ref,
        "resolved_capability": identity.required_capability,
        "auth_policy_version": context.auth_policy_version,
        "environment": command["environment"],
        "data_plane": command["data_plane"],
        "synthetic": command["synthetic"],
        "action": identity.action,
        "aggregate_type": "SCHEDULE_VERSION",
        "aggregate_id": identity.schedule_version_id,
        "target": "WORKSPACE_INTERNAL",
        "intent_type": "DECISION",
        "reason": command["reason"],
        "request_fingerprint": identity.request_fingerprint,
        "idempotency_reference": {
            "scope": command["idempotency_scope"],
            "key_reference": identity.key_reference,
            "request_fingerprint": identity.request_fingerprint,
        },
        "lineage": deepcopy(lineage) if lineage is not None else None,
        "before_state": None,
        "after_state": None,
        "source_version": None,
        "new_version": None,
        "export_job_id": None,
        "result": {},
        "correlation_id": command["correlation_id"],
        "parent_audit_event_id": context.parent_audit_event_id,
        "code_commit": context.code_commit,
    }
    if command.get("synthetic") is True:
        event["synthetic_provenance"] = deepcopy(command["synthetic_provenance"])
    return event


def build_approval_decision_documents(
    prepared: PreparedApprovalDecision,
) -> ApprovalDecisionDocuments:
    """Build a same-content state decision and its successful audit."""

    source = prepared.source
    identity = prepared.identity
    decided = deepcopy(source)
    decided.update(
        {
            "state": identity.target_state,
            "decision": {
                "decision": identity.target_state,
                "actor_ref": prepared.context.actor_ref,
                "capability": identity.required_capability,
                "reason": prepared.command["reason"],
                "decided_at_utc": prepared.context.occurred_at_utc,
                "audit_event_id": identity.audit_event_id,
            },
            "allowed_actions": list(_DECISION_ACTIONS[identity.command_type]),
        }
    )
    version_reference = {
        "schedule_version_id": identity.schedule_version_id,
        "state": "READY_FOR_REVIEW",
        "content_fingerprint": source["content_fingerprint"],
    }
    decided_reference = {
        **version_reference,
        "state": identity.target_state,
    }
    lineage = _mapping(source.get("lineage"), "source.lineage")
    audit_event = _audit_base(
        prepared.command,
        prepared.context,
        identity,
        lineage=lineage,
    )
    audit_event.update(
        {
            "before_state": "READY_FOR_REVIEW",
            "after_state": identity.target_state,
            "source_version": version_reference,
            "new_version": decided_reference,
            "result": {
                "outcome": "SUCCEEDED",
                "replayed": False,
                "retryable": False,
                "error": None,
            },
        }
    )
    try:
        require_workspace_document(decided)
        require_workspace_document(audit_event)
    except (TypeError, ValueError) as error:
        raise ApprovalDecisionError(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=getattr(error, "field", "schedule_version/audit_event"),
            message="constructed decision failed its frozen carrier contract",
        ) from error
    return ApprovalDecisionDocuments(
        decided_schedule=decided,
        audit_event=audit_event,
        identity=identity,
    )


def build_authorization_denial_audit(
    command: Mapping[str, object],
    context: ApprovalDecisionContext,
    identity: ApprovalDecisionIdentity,
    *,
    data_plane: str,
) -> dict[str, object]:
    """Build one sanitized high-risk denial event without reading the resource."""

    _validate_context(context, data_plane=data_plane)
    event = _audit_base(command, context, identity, lineage=None)
    event["result"] = {
        "outcome": "DENIED",
        "replayed": False,
        "retryable": False,
        "error": {
            "error_namespace": "WORKSPACE_CONTROL",
            "reason": "AUTHORIZATION_DENIED",
            "message": "Approval decision authorization was denied.",
        },
    }
    try:
        require_workspace_document(event)
    except (TypeError, ValueError) as error:
        raise ApprovalDecisionError(
            ApprovalDecisionFailure.INVALID_REQUEST,
            field=getattr(error, "field", "audit_event"),
            message="constructed denial audit failed its frozen carrier contract",
        ) from error
    return event


__all__ = [
    "APPROVAL_DECISION_SERVICE_VERSION",
    "ApprovalDecisionContext",
    "ApprovalDecisionDocuments",
    "ApprovalDecisionError",
    "ApprovalDecisionFailure",
    "ApprovalDecisionIdentity",
    "PreparedApprovalDecision",
    "approval_decision_identity",
    "build_approval_decision_documents",
    "build_authorization_denial_audit",
    "prepare_approval_decision",
    "reject_approval_decision",
    "require_approval_decision_authorization",
]
