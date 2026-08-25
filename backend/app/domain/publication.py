"""Authority-neutral internal publication semantics for TASK-P3-08.

The frozen Workspace carriers express publication intent and results while a
server-resolved context supplies authentication, capability, policy, and
resource scope.  This module is pure: it performs no repository or network
access and implements Simulation-internal publication only.  Production
publication remains default-denied by governance OPEN-002/010.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Never, cast

from app.domain.types import ContractValueError, format_utc_instant, parse_utc_instant
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    publication_result_fingerprint,
    require_workspace_document,
    workspace_fingerprint,
)


PUBLICATION_SERVICE_VERSION = "publication-service.v1"

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


class PublicationFailure(StrEnum):
    """Stable, sanitized failures for the P3 publication boundary."""

    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    PRODUCTION_AUTHORITY_UNAVAILABLE = "PRODUCTION_AUTHORITY_UNAVAILABLE"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    PREVIOUS_CURRENT_NOT_FOUND = "PREVIOUS_CURRENT_NOT_FOUND"
    STALE_SOURCE = "STALE_SOURCE"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    CURRENT_REFERENCE_CONFLICT = "CURRENT_REFERENCE_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class PublicationError(ValueError):
    """One fail-closed publication rejection without adapter detail."""

    def __init__(
        self,
        reason: PublicationFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value}: {field}: {message}")


@dataclass(frozen=True, slots=True)
class PublicationContext:
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
class PublicationIdentity:
    """Deterministic identity available before source or replay lookup."""

    request_fingerprint: str
    key_reference: str
    schedule_version_id: str
    publication_id: str
    audit_event_id: str


@dataclass(frozen=True, slots=True)
class CurrentPublicationState:
    """Domain projection of the durable current-publication CAS reference."""

    target: str
    schedule_version_id: str
    content_fingerprint: str
    publication_id: str


@dataclass(frozen=True, slots=True)
class PreparedPublication:
    """One authorized APPROVED source and optional current PUBLISHED source."""

    source: dict[str, object]
    previous_current: dict[str, object] | None
    current: CurrentPublicationState | None
    command: dict[str, object]
    identity: PublicationIdentity
    context: PublicationContext
    data_plane: str


@dataclass(frozen=True, slots=True)
class PublicationDocuments:
    """All documents that must commit in one publication transaction."""

    published_schedule: dict[str, object]
    superseded_schedule: dict[str, object] | None
    publication_result: dict[str, object]
    audit_event: dict[str, object]
    identity: PublicationIdentity


def reject_publication(
    reason: PublicationFailure,
    *,
    field: str,
    message: str,
) -> Never:
    raise PublicationError(reason, field=field, message=message)


def _clone(value: Mapping[str, object]) -> dict[str, object]:
    import json

    return cast(dict[str, object], json.loads(canonical_workspace_bytes(value)))


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def _text(value: object, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must be bounded non-empty text",
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must not contain control characters",
        )
    return value


def _reason(value: object, field: str) -> str:
    text = _text(value, field)
    if _SECRET_TEXT.search(text) is not None:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must not contain credential-like material",
        )
    return text


def _canonical_id(value: object, field: str) -> str:
    text = _text(value, field, maximum=256)
    if _CANONICAL_ID.fullmatch(text) is None:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must be a canonical identifier",
        )
    return text


def _fingerprint(value: object, field: str) -> str:
    text = _text(value, field, maximum=71)
    if _FINGERPRINT.fullmatch(text) is None:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must be a sha256 fingerprint",
        )
    return text


def _utc(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = parse_utc_instant(text)
    except ContractValueError as error:
        raise PublicationError(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must be a valid RFC 3339 UTC instant ending in Z",
        ) from error
    if format_utc_instant(parsed) != text:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="must use canonical second-precision UTC",
        )
    return text


def _require_fields(
    value: Mapping[str, object], expected: frozenset[str], field: str
) -> None:
    if frozenset(value) != expected:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field=field,
            message="fields do not match the frozen publication contract",
        )


def _version_reference(
    value: object,
    field: str,
    *,
    expected_state: str | None = None,
) -> dict[str, object]:
    reference = _mapping(value, field)
    _require_fields(
        reference,
        frozenset({"schedule_version_id", "state", "content_fingerprint"}),
        field,
    )
    result: dict[str, object] = {
        "schedule_version_id": _canonical_id(
            reference.get("schedule_version_id"), f"{field}.schedule_version_id"
        ),
        "state": _text(reference.get("state"), f"{field}.state", maximum=32),
        "content_fingerprint": _fingerprint(
            reference.get("content_fingerprint"), f"{field}.content_fingerprint"
        ),
    }
    if expected_state is not None and result["state"] != expected_state:
        reject_publication(
            PublicationFailure.INVALID_STATE_TRANSITION,
            field=f"{field}.state",
            message=f"must be {expected_state}",
        )
    return result


def _validate_context(context: PublicationContext, *, data_plane: str) -> None:
    actor_ref = _text(context.actor_ref, "context.actor_ref", maximum=256)
    if _ACTOR_REFERENCE.fullmatch(actor_ref) is None:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="context.actor_ref",
            message="must be a sanitized actor reference",
        )
    if not isinstance(context.authenticated, bool) or not isinstance(
        context.production_binding, bool
    ):
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="context.authentication",
            message="authentication and production binding must be boolean",
        )
    policy = _text(context.auth_policy_version, "context.auth_policy_version")
    _utc(context.occurred_at_utc, "context.occurred_at_utc")
    if _GIT_COMMIT.fullmatch(context.code_commit) is None:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="context.code_commit",
            message="must be a full Git commit or uncommitted",
        )
    if context.parent_audit_event_id is not None:
        _canonical_id(context.parent_audit_event_id, "context.parent_audit_event_id")
    for capability in context.resolved_capabilities:
        if capability not in _APPLICATION_CAPABILITIES:
            reject_publication(
                PublicationFailure.INVALID_REQUEST,
                field="context.resolved_capabilities",
                message="contains an unknown application capability",
            )
    for resource_id in context.schedule_version_scope:
        _canonical_id(resource_id, "context.schedule_version_scope")
    if data_plane not in {"SIMULATION", "PRODUCTION"}:
        reject_publication(
            PublicationFailure.DATA_PLANE_MISMATCH,
            field="data_plane",
            message="must be SIMULATION or PRODUCTION",
        )
    if data_plane == "SIMULATION" and not any(
        marker in policy.lower() for marker in ("simulation", "test")
    ):
        reject_publication(
            PublicationFailure.AUTHORIZATION_DENIED,
            field="context.auth_policy_version",
            message="Simulation publication requires an explicit test policy",
        )


def publication_identity(
    command: Mapping[str, object], *, data_plane: str
) -> PublicationIdentity:
    """Validate one PUBLISH command and derive its hashed identities."""

    expected_fields = set(_COMMAND_FIELDS)
    if "synthetic_provenance" not in command:
        expected_fields.remove("synthetic_provenance")
    _require_fields(command, frozenset(expected_fields), "command")
    try:
        require_workspace_document(command)
    except (TypeError, ValueError) as error:
        raise PublicationError(
            PublicationFailure.INVALID_REQUEST,
            field=getattr(error, "field", "command"),
            message="failed the frozen workspace command contract",
        ) from error
    if command.get("command_type") != "PUBLISH":
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="command.command_type",
            message="TASK-P3-08 accepts only PUBLISH",
        )
    if command.get("required_capability") != "publish":
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="command.required_capability",
            message="must be publish",
        )
    source_id = _canonical_id(command.get("source_id"), "command.source_id")
    _canonical_id(command.get("command_id"), "command.command_id")
    _canonical_id(command.get("correlation_id"), "command.correlation_id")
    _reason(command.get("reason"), "command.reason")
    request_fingerprint = _fingerprint(
        command.get("request_fingerprint"), "command.request_fingerprint"
    )
    _fingerprint(
        command.get("expected_content_fingerprint"),
        "command.expected_content_fingerprint",
    )
    if command.get("expected_state") != "APPROVED":
        reject_publication(
            PublicationFailure.INVALID_STATE_TRANSITION,
            field="command.expected_state",
            message="publication requires APPROVED",
        )
    if command.get("data_plane") != data_plane:
        reject_publication(
            PublicationFailure.DATA_PLANE_MISMATCH,
            field="command.data_plane",
            message="does not match the repository plane",
        )
    if command.get("target") != "SIMULATION_INTERNAL":
        reject_publication(
            PublicationFailure.DATA_PLANE_MISMATCH,
            field="command.target",
            message="TASK-P3-08 accepts only the internal Simulation target",
        )
    synthetic = command.get("synthetic")
    if not isinstance(synthetic, bool):
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="command.synthetic",
            message="must be boolean",
        )
    if synthetic is True:
        _mapping(command.get("synthetic_provenance"), "command.synthetic_provenance")
    elif "synthetic_provenance" in command:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="command.synthetic_provenance",
            message="is forbidden for non-synthetic publication",
        )
    environment = command.get("environment")
    if data_plane == "SIMULATION" and environment not in {
        "DEVELOPMENT",
        "TEST",
        "BENCHMARK",
    }:
        reject_publication(
            PublicationFailure.DATA_PLANE_MISMATCH,
            field="command.environment",
            message="is not a Simulation environment",
        )
    if data_plane == "PRODUCTION" and (
        environment != "PRODUCTION" or synthetic is not False
    ):
        reject_publication(
            PublicationFailure.DATA_PLANE_MISMATCH,
            field="command.environment/synthetic",
            message="is not a Production carrier",
        )
    key = _text(command.get("idempotency_key"), "command.idempotency_key", maximum=128)
    if _IDEMPOTENCY_KEY.fullmatch(key) is None:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="command.idempotency_key",
            message="does not match the frozen idempotency key contract",
        )
    scope = _text(command.get("idempotency_scope"), "command.idempotency_scope")
    expected_scope = f"{data_plane}/PUBLISH/{source_id}/SIMULATION_INTERNAL"
    if scope != expected_scope:
        reject_publication(
            PublicationFailure.INVALID_REQUEST,
            field="command.idempotency_scope",
            message="does not match the server-derived publication scope",
        )
    payload = _mapping(command.get("payload"), "command.payload")
    _require_fields(payload, frozenset({"previous_current_version"}), "command.payload")
    if payload.get("previous_current_version") is not None:
        _version_reference(
            payload.get("previous_current_version"),
            "command.payload.previous_current_version",
            expected_state="PUBLISHED",
        )
    key_reference = workspace_fingerprint(
        {"idempotency_scope": scope, "idempotency_key": key}
    )
    suffix = key_reference.removeprefix("sha256:")
    return PublicationIdentity(
        request_fingerprint=request_fingerprint,
        key_reference=key_reference,
        schedule_version_id=source_id,
        publication_id=f"publication-{suffix}",
        audit_event_id=f"audit-event-publication-{suffix}",
    )


def require_publication_authorization(
    context: PublicationContext,
    identity: PublicationIdentity,
    command: Mapping[str, object],
    *,
    data_plane: str,
) -> None:
    """Fail closed before source, replay, or current-reference lookup."""

    _validate_context(context, data_plane=data_plane)
    if data_plane == "PRODUCTION":
        reject_publication(
            PublicationFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
            field="data_plane",
            message="Production publication authority and channel are not configured",
        )
    if context.production_binding:
        reject_publication(
            PublicationFailure.AUTHORIZATION_DENIED,
            field="context.production_binding",
            message="Simulation test policy cannot carry a Production binding",
        )
    if command.get("synthetic") is not True:
        reject_publication(
            PublicationFailure.AUTHORIZATION_DENIED,
            field="command.synthetic",
            message="Simulation publication policy is limited to synthetic resources",
        )
    if not context.authenticated:
        reject_publication(
            PublicationFailure.AUTHORIZATION_DENIED,
            field="context.authenticated",
            message="an authenticated principal is required",
        )
    if "publish" not in context.resolved_capabilities:
        reject_publication(
            PublicationFailure.AUTHORIZATION_DENIED,
            field="context.resolved_capabilities",
            message="does not contain the server-required publish capability",
        )
    if identity.schedule_version_id not in context.schedule_version_scope:
        reject_publication(
            PublicationFailure.AUTHORIZATION_DENIED,
            field="context.schedule_version_scope",
            message="does not include the requested ScheduleVersion",
        )


def _validate_schedule_document(
    document: Mapping[str, object], *, field: str, failure: PublicationFailure
) -> None:
    try:
        require_workspace_document(document)
    except (TypeError, ValueError) as error:
        raise PublicationError(
            failure,
            field=getattr(error, "field", field),
            message="authoritative ScheduleVersion failed its frozen carrier contract",
        ) from error


def prepare_publication(
    source: Mapping[str, object],
    previous_current: Mapping[str, object] | None,
    current: CurrentPublicationState | None,
    command: Mapping[str, object],
    context: PublicationContext,
    *,
    data_plane: str,
) -> PreparedPublication:
    """Bind one authorized request to APPROVED source and current PUBLISHED state."""

    identity = publication_identity(command, data_plane=data_plane)
    require_publication_authorization(
        context, identity, command, data_plane=data_plane
    )
    _validate_schedule_document(
        source, field="source", failure=PublicationFailure.STALE_SOURCE
    )
    if source.get("schedule_version_id") != identity.schedule_version_id:
        reject_publication(
            PublicationFailure.STALE_SOURCE,
            field="command.source_id",
            message="does not match the authoritative ScheduleVersion",
        )
    if source.get("state") != "APPROVED":
        reject_publication(
            PublicationFailure.INVALID_STATE_TRANSITION,
            field="source.state",
            message="only APPROVED can be published",
        )
    if source.get("content_fingerprint") != command.get("expected_content_fingerprint"):
        reject_publication(
            PublicationFailure.STALE_SOURCE,
            field="command.expected_content_fingerprint",
            message="does not match the authoritative ScheduleVersion",
        )
    for field in ("data_plane", "environment", "synthetic"):
        if source.get(field) != command.get(field):
            reject_publication(
                PublicationFailure.DATA_PLANE_MISMATCH,
                field=f"command.{field}",
                message="does not match the authoritative ScheduleVersion",
            )
    if source.get("synthetic_provenance") != command.get("synthetic_provenance"):
        reject_publication(
            PublicationFailure.DATA_PLANE_MISMATCH,
            field="command.synthetic_provenance",
            message="does not match the authoritative ScheduleVersion",
        )
    decision = _mapping(source.get("decision"), "source.decision")
    if decision.get("decision") != "APPROVED" or decision.get("capability") != "approve":
        reject_publication(
            PublicationFailure.INVALID_STATE_TRANSITION,
            field="source.decision",
            message="APPROVED source lacks approved decision evidence",
        )
    if source.get("publication") is not None or source.get("superseded_by") is not None:
        reject_publication(
            PublicationFailure.INVALID_STATE_TRANSITION,
            field="source.publication/superseded_by",
            message="APPROVED source must not contain publication state",
        )

    payload = _mapping(command.get("payload"), "command.payload")
    requested_previous_value = payload.get("previous_current_version")
    if current is None:
        if requested_previous_value is not None or previous_current is not None:
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="command.payload.previous_current_version",
                message="must be null when no current publication exists",
            )
    else:
        if current.target != "SIMULATION_INTERNAL":
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="current.target",
                message="does not match the internal Simulation target",
            )
        requested_previous = _version_reference(
            requested_previous_value,
            "command.payload.previous_current_version",
            expected_state="PUBLISHED",
        )
        expected_previous = {
            "schedule_version_id": current.schedule_version_id,
            "state": "PUBLISHED",
            "content_fingerprint": current.content_fingerprint,
        }
        if requested_previous != expected_previous:
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="command.payload.previous_current_version",
                message="does not match the durable current reference",
            )
        if previous_current is None:
            reject_publication(
                PublicationFailure.PREVIOUS_CURRENT_NOT_FOUND,
                field="current.schedule_version_id",
                message="does not identify a durable current ScheduleVersion",
            )
        _validate_schedule_document(
            previous_current,
            field="previous_current",
            failure=PublicationFailure.CURRENT_REFERENCE_CONFLICT,
        )
        if previous_current.get("schedule_version_id") != current.schedule_version_id:
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="previous_current.schedule_version_id",
                message="does not match the durable current reference",
            )
        if previous_current.get("state") != "PUBLISHED":
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="previous_current.state",
                message="current ScheduleVersion must be PUBLISHED",
            )
        if previous_current.get("content_fingerprint") != current.content_fingerprint:
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="previous_current.content_fingerprint",
                message="does not match the durable current reference",
            )
        publication = _mapping(
            previous_current.get("publication"), "previous_current.publication"
        )
        if (
            publication.get("publication_id") != current.publication_id
            or publication.get("target") != "SIMULATION_INTERNAL"
        ):
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="previous_current.publication",
                message="does not bind the durable current publication",
            )
        if previous_current.get("superseded_by") is not None:
            reject_publication(
                PublicationFailure.CURRENT_REFERENCE_CONFLICT,
                field="previous_current.superseded_by",
                message="current PUBLISHED ScheduleVersion is already superseded",
            )
        if current.schedule_version_id == identity.schedule_version_id:
            reject_publication(
                PublicationFailure.INVALID_STATE_TRANSITION,
                field="source.schedule_version_id",
                message="cannot publish the current ScheduleVersion again",
            )

    return PreparedPublication(
        source=_clone(source),
        previous_current=(
            _clone(previous_current) if previous_current is not None else None
        ),
        current=current,
        command=_clone(command),
        identity=identity,
        context=context,
        data_plane=data_plane,
    )


def _schedule_reference(
    schedule: Mapping[str, object], state: str
) -> dict[str, object]:
    return {
        "schedule_version_id": schedule["schedule_version_id"],
        "state": state,
        "content_fingerprint": schedule["content_fingerprint"],
    }


def _audit_base(
    command: Mapping[str, object],
    context: PublicationContext,
    identity: PublicationIdentity,
    *,
    lineage: Mapping[str, object] | None,
    target: str,
) -> dict[str, object]:
    event: dict[str, object] = {
        "audit_event_version": "audit-event.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "audit_event_id": identity.audit_event_id,
        "occurred_at_utc": context.occurred_at_utc,
        "actor_ref": context.actor_ref,
        "resolved_capability": "publish",
        "auth_policy_version": context.auth_policy_version,
        "environment": command["environment"],
        "data_plane": command["data_plane"],
        "synthetic": command["synthetic"],
        "action": "PUBLISH",
        "aggregate_type": "SCHEDULE_VERSION",
        "aggregate_id": identity.schedule_version_id,
        "target": target,
        "intent_type": "PUBLICATION",
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


def build_publication_documents(prepared: PreparedPublication) -> PublicationDocuments:
    """Build same-content publish/supersede/result/audit documents."""

    source = prepared.source
    identity = prepared.identity
    source_reference = _schedule_reference(source, "APPROVED")
    published_reference = _schedule_reference(source, "PUBLISHED")

    published = deepcopy(source)
    published.update(
        {
            "state": "PUBLISHED",
            "publication": {
                "publication_id": identity.publication_id,
                "target": "SIMULATION_INTERNAL",
                "published_at_utc": prepared.context.occurred_at_utc,
                "audit_event_id": identity.audit_event_id,
            },
            "allowed_actions": ["view", "export"],
        }
    )

    previous_reference: dict[str, object] | None = None
    superseded_reference: dict[str, object] | None = None
    superseded: dict[str, object] | None = None
    if prepared.previous_current is not None:
        previous_reference = _schedule_reference(
            prepared.previous_current, "PUBLISHED"
        )
        superseded_reference = _schedule_reference(
            prepared.previous_current, "SUPERSEDED"
        )
        superseded = deepcopy(prepared.previous_current)
        superseded.update(
            {
                "state": "SUPERSEDED",
                "superseded_by": deepcopy(published_reference),
                "allowed_actions": ["view"],
            }
        )

    result: dict[str, object] = {
        "publication_result_version": "publication-result.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "publication_id": identity.publication_id,
        "data_plane": "SIMULATION",
        "environment": prepared.command["environment"],
        "synthetic": True,
        "synthetic_provenance": deepcopy(
            prepared.command["synthetic_provenance"]
        ),
        "target": "SIMULATION_INTERNAL",
        "source_approved_version": source_reference,
        "published_version": published_reference,
        "previous_current_version": previous_reference,
        "superseded_version": superseded_reference,
        "idempotency_reference": {
            "scope": prepared.command["idempotency_scope"],
            "key_reference": identity.key_reference,
            "request_fingerprint": identity.request_fingerprint,
        },
        "replayed": False,
        "published_at_utc": prepared.context.occurred_at_utc,
        "audit_event_id": identity.audit_event_id,
        "result_fingerprint": "sha256:" + "0" * 64,
    }
    result["result_fingerprint"] = publication_result_fingerprint(result)

    lineage = _mapping(source.get("lineage"), "source.lineage")
    audit_event = _audit_base(
        prepared.command,
        prepared.context,
        identity,
        lineage=lineage,
        target="SIMULATION_INTERNAL",
    )
    audit_event.update(
        {
            "before_state": "APPROVED",
            "after_state": "PUBLISHED",
            "source_version": source_reference,
            "new_version": published_reference,
            "result": {
                "outcome": "SUCCEEDED",
                "replayed": False,
                "retryable": False,
                "error": None,
            },
        }
    )
    try:
        require_workspace_document(published)
        if superseded is not None:
            require_workspace_document(superseded)
        require_workspace_document(result)
        require_workspace_document(audit_event)
    except (TypeError, ValueError) as error:
        raise PublicationError(
            PublicationFailure.INVALID_REQUEST,
            field=getattr(error, "field", "publication_documents"),
            message="constructed publication failed its frozen carrier contract",
        ) from error
    return PublicationDocuments(
        published_schedule=published,
        superseded_schedule=superseded,
        publication_result=result,
        audit_event=audit_event,
        identity=identity,
    )


def build_publication_replay_result(
    command: Mapping[str, object],
    identity: PublicationIdentity,
    audit_event: Mapping[str, object],
) -> dict[str, object]:
    """Reconstruct the exact logical success with a replay marker."""

    source_reference = _version_reference(
        audit_event.get("source_version"),
        "audit.source_version",
        expected_state="APPROVED",
    )
    published_reference = _version_reference(
        audit_event.get("new_version"),
        "audit.new_version",
        expected_state="PUBLISHED",
    )
    payload = _mapping(command.get("payload"), "command.payload")
    previous_value = payload.get("previous_current_version")
    previous_reference = (
        None
        if previous_value is None
        else _version_reference(
            previous_value,
            "command.payload.previous_current_version",
            expected_state="PUBLISHED",
        )
    )
    superseded_reference = (
        None
        if previous_reference is None
        else {**previous_reference, "state": "SUPERSEDED"}
    )
    result: dict[str, object] = {
        "publication_result_version": "publication-result.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "publication_id": identity.publication_id,
        "data_plane": "SIMULATION",
        "environment": command["environment"],
        "synthetic": True,
        "synthetic_provenance": deepcopy(command["synthetic_provenance"]),
        "target": "SIMULATION_INTERNAL",
        "source_approved_version": source_reference,
        "published_version": published_reference,
        "previous_current_version": previous_reference,
        "superseded_version": superseded_reference,
        "idempotency_reference": {
            "scope": command["idempotency_scope"],
            "key_reference": identity.key_reference,
            "request_fingerprint": identity.request_fingerprint,
        },
        "replayed": True,
        "published_at_utc": audit_event["occurred_at_utc"],
        "audit_event_id": identity.audit_event_id,
        "result_fingerprint": "sha256:" + "0" * 64,
    }
    result["result_fingerprint"] = publication_result_fingerprint(result)
    try:
        require_workspace_document(result)
    except (TypeError, ValueError) as error:
        raise PublicationError(
            PublicationFailure.PERSISTENCE_FAILED,
            field=getattr(error, "field", "publication_result"),
            message="stored publication evidence cannot form a replay result",
        ) from error
    return result


def build_publication_authorization_denial_audit(
    command: Mapping[str, object],
    context: PublicationContext,
    identity: PublicationIdentity,
    *,
    data_plane: str,
) -> dict[str, object]:
    """Build one sanitized denial event without reading the resource."""

    _validate_context(context, data_plane=data_plane)
    event = _audit_base(
        command,
        context,
        identity,
        lineage=None,
        target=(
            "WORKSPACE_INTERNAL"
            if data_plane == "PRODUCTION"
            else "SIMULATION_INTERNAL"
        ),
    )
    event["result"] = {
        "outcome": "DENIED",
        "replayed": False,
        "retryable": False,
        "error": {
            "error_namespace": "WORKSPACE_CONTROL",
            "reason": "AUTHORIZATION_DENIED",
            "message": "Publication authorization was denied.",
        },
    }
    try:
        require_workspace_document(event)
    except (TypeError, ValueError) as error:
        raise PublicationError(
            PublicationFailure.INVALID_REQUEST,
            field=getattr(error, "field", "audit_event"),
            message="constructed denial audit failed its frozen carrier contract",
        ) from error
    return event


__all__ = [
    "PUBLICATION_SERVICE_VERSION",
    "CurrentPublicationState",
    "PreparedPublication",
    "PublicationContext",
    "PublicationDocuments",
    "PublicationError",
    "PublicationFailure",
    "PublicationIdentity",
    "build_publication_authorization_denial_audit",
    "build_publication_documents",
    "build_publication_replay_result",
    "prepare_publication",
    "publication_identity",
    "reject_publication",
    "require_publication_authorization",
]
