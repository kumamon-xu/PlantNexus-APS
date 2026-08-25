"""Pure authorization, identity, carrier, and audit semantics for P3 export jobs."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import re
from typing import Never, cast

from app.domain.types import parse_utc_instant
from app.domain.workspace_contracts import (
    export_job_fingerprint,
    require_workspace_document,
    workspace_fingerprint,
)


EXPORT_JOB_SERVICE_VERSION = "export-job-service.v1"
_KEY = re.compile(r"[A-Za-z0-9._:-]{16,128}")
_ACTOR = re.compile(r"actor:[A-Za-z0-9._:-]+")
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|uncommitted)")
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,512}$")


class ExportJobFailure(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    PRODUCTION_AUTHORITY_UNAVAILABLE = "PRODUCTION_AUTHORITY_UNAVAILABLE"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    PUBLICATION_NOT_FOUND = "PUBLICATION_NOT_FOUND"
    STALE_SOURCE = "STALE_SOURCE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    LEASE_CONFLICT = "LEASE_CONFLICT"
    EXPORT_FAILED = "EXPORT_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ExportJobError(ValueError):
    def __init__(self, reason: ExportJobFailure, *, field: str) -> None:
        self.reason = reason
        self.field = field
        super().__init__(f"{reason.value}: {field}")


@dataclass(frozen=True, slots=True)
class ExportJobContext:
    actor_ref: str
    authenticated: bool
    resolved_capabilities: frozenset[str]
    schedule_version_scope: frozenset[str]
    export_job_scope: frozenset[str]
    auth_policy_version: str
    production_binding: bool
    occurred_at_utc: str
    code_commit: str
    parent_audit_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExportJobRequest:
    schedule_version_id: str
    expected_content_fingerprint: str
    raw_idempotency_key: str
    reason: str
    correlation_id: str
    environment: str
    synthetic_provenance: Mapping[str, object]
    data_plane: str = "SIMULATION"
    target: str = "SIMULATION_INTERNAL"


@dataclass(frozen=True, slots=True)
class ExportJobIdentity:
    export_job_id: str
    request_fingerprint: str
    key_reference: str
    idempotency_scope: str
    create_audit_event_id: str


def reject_export_job(reason: ExportJobFailure, field: str) -> Never:
    raise ExportJobError(reason, field=field)


def _safe_text(value: str, field: str) -> str:
    if not isinstance(value, str) or _SAFE_TEXT.fullmatch(value) is None:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, field)
    return value


def _request_projection(request: ExportJobRequest, key_reference: str) -> dict[str, object]:
    return {
        "service_version": EXPORT_JOB_SERVICE_VERSION,
        "schedule_version_id": request.schedule_version_id,
        "expected_content_fingerprint": request.expected_content_fingerprint,
        "key_reference": key_reference,
        "reason": request.reason,
        "correlation_id": request.correlation_id,
        "environment": request.environment,
        "synthetic_provenance": dict(request.synthetic_provenance),
        "data_plane": request.data_plane,
        "target": request.target,
        "package_profile": "p3-standard-export.v1",
    }


def export_job_identity(request: ExportJobRequest) -> ExportJobIdentity:
    for field in ("schedule_version_id", "reason", "correlation_id"):
        _safe_text(cast(str, getattr(request, field)), field)
    if _KEY.fullmatch(request.raw_idempotency_key) is None:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "raw_idempotency_key")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", request.expected_content_fingerprint):
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "expected_content_fingerprint")
    if request.environment not in {"DEVELOPMENT", "TEST", "BENCHMARK", "PRODUCTION"}:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "environment")
    key_reference = f"sha256:{sha256(request.raw_idempotency_key.encode()).hexdigest()}"
    projection = _request_projection(request, key_reference)
    request_fingerprint = workspace_fingerprint(projection)
    digest = sha256(f"{request.data_plane}/{request.schedule_version_id}/{key_reference}".encode()).hexdigest()
    export_job_id = f"export-job-{digest}"
    return ExportJobIdentity(
        export_job_id=export_job_id,
        request_fingerprint=request_fingerprint,
        key_reference=key_reference,
        idempotency_scope=f"{request.data_plane}/EXPORT/{request.schedule_version_id}/{request.target}",
        create_audit_event_id=audit_event_id(export_job_id, "CREATE", 0),
    )


def audit_event_id(export_job_id: str, phase: str, attempt: int) -> str:
    digest = sha256(f"{export_job_id}/{phase}/{attempt}".encode()).hexdigest()
    return f"audit-export-{digest}"


def lease_reference_for(export_job_id: str, attempt: int, owner_reference: str) -> str:
    _safe_text(owner_reference, "owner_reference")
    return f"sha256:{sha256(f'{export_job_id}/{attempt}/{owner_reference}'.encode()).hexdigest()}"


def require_export_authorization(
    request: ExportJobRequest,
    context: ExportJobContext,
) -> ExportJobIdentity:
    """Validate authority without reading a schedule, job, publication, or replay."""

    identity = export_job_identity(request)
    try:
        parse_utc_instant(context.occurred_at_utc)
    except Exception:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "context.occurred_at_utc")
    if _ACTOR.fullmatch(context.actor_ref) is None or not context.auth_policy_version:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "context.actor_ref/auth_policy_version")
    if _COMMIT.fullmatch(context.code_commit) is None:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "context.code_commit")
    if request.data_plane == "PRODUCTION" or request.environment == "PRODUCTION":
        reject_export_job(ExportJobFailure.PRODUCTION_AUTHORITY_UNAVAILABLE, "data_plane/environment")
    if request.data_plane != "SIMULATION" or request.target != "SIMULATION_INTERNAL":
        reject_export_job(ExportJobFailure.AUTHORIZATION_DENIED, "data_plane/target")
    if (
        not context.authenticated
        or "export" not in context.resolved_capabilities
        or request.schedule_version_id not in context.schedule_version_scope
    ):
        reject_export_job(ExportJobFailure.AUTHORIZATION_DENIED, "authorization")
    return identity


def require_job_authorization(
    export_job_id: str,
    context: ExportJobContext,
) -> None:
    try:
        parse_utc_instant(context.occurred_at_utc)
    except Exception:
        reject_export_job(ExportJobFailure.INVALID_REQUEST, "context.occurred_at_utc")
    if (
        not context.authenticated
        or "export" not in context.resolved_capabilities
        or export_job_id not in context.export_job_scope
        or context.production_binding
    ):
        reject_export_job(ExportJobFailure.AUTHORIZATION_DENIED, "authorization")


def build_created_export_job(
    request: ExportJobRequest,
    identity: ExportJobIdentity,
    context: ExportJobContext,
    schedule_version: Mapping[str, object],
    publication_result: Mapping[str, object],
) -> dict[str, object]:
    if require_workspace_document(schedule_version) != "schedule-version.v1" or schedule_version.get("state") != "PUBLISHED":
        reject_export_job(ExportJobFailure.STALE_SOURCE, "schedule_version.state")
    if require_workspace_document(publication_result) != "publication-result.v1":
        reject_export_job(ExportJobFailure.PUBLICATION_NOT_FOUND, "publication_result")
    published = publication_result.get("published_version")
    if not isinstance(published, Mapping):
        reject_export_job(ExportJobFailure.PUBLICATION_NOT_FOUND, "publication_result.published_version")
    if any(
        reference != schedule_version.get(field)
        for field, reference in (
            ("schedule_version_id", published.get("schedule_version_id")),
            ("content_fingerprint", published.get("content_fingerprint")),
        )
    ) or schedule_version.get("content_fingerprint") != request.expected_content_fingerprint:
        reject_export_job(ExportJobFailure.STALE_SOURCE, "schedule_version")
    document: dict[str, object] = {
        "export_job_version": "export-job.v2",
        "schema_set_version": "2.7.0",
        "canonicalization_version": "canonical-json.v1",
        "export_job_id": identity.export_job_id,
        "state": "CREATED",
        "schedule_version": {
            "schedule_version_id": schedule_version["schedule_version_id"],
            "state": "PUBLISHED",
            "content_fingerprint": schedule_version["content_fingerprint"],
        },
        "data_plane": "SIMULATION",
        "environment": request.environment,
        "synthetic": True,
        "synthetic_provenance": deepcopy(dict(request.synthetic_provenance)),
        "target": "SIMULATION_INTERNAL",
        "package_profile": "p3-standard-export.v1",
        "idempotency_reference": {
            "scope": identity.idempotency_scope,
            "key_reference": identity.key_reference,
            "request_fingerprint": identity.request_fingerprint,
        },
        "attempt": 0,
        "lease_reference": None,
        "heartbeat_at_utc": None,
        "artifact_manifest": None,
        "error": None,
        "created_at_utc": context.occurred_at_utc,
        "updated_at_utc": context.occurred_at_utc,
        "started_at_utc": None,
        "finished_at_utc": None,
        "cancelled_at_utc": None,
        "latest_audit_event_id": identity.create_audit_event_id,
        "job_fingerprint": "sha256:" + "0" * 64,
    }
    document["job_fingerprint"] = export_job_fingerprint(document)
    require_workspace_document(document)
    return document


def transition_export_job(
    current: Mapping[str, object],
    *,
    target_state: str,
    occurred_at_utc: str,
    audit_event_id_value: str,
    attempt: int | None = None,
    lease_reference: str | None = None,
    artifact_manifest: Mapping[str, object] | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    document = deepcopy(dict(current))
    source = cast(str, current["state"])
    effective_attempt = cast(int, current["attempt"]) if attempt is None else attempt
    document.update(
        {
            "state": target_state,
            "attempt": effective_attempt,
            "updated_at_utc": occurred_at_utc,
            "latest_audit_event_id": audit_event_id_value,
            "lease_reference": lease_reference if target_state == "EXPORTING" else None,
            "heartbeat_at_utc": occurred_at_utc if target_state == "EXPORTING" else None,
            "artifact_manifest": dict(artifact_manifest) if artifact_manifest is not None else None,
            "error": (
                {"error_namespace": "WORKSPACE_CONTROL", "reason": "EXPORT_FAILED", "message": _safe_text(error_message or "Export attempt failed.", "error_message")}
                if target_state == "EXPORT_FAILED"
                else None
            ),
        }
    )
    if target_state == "EXPORTING" and document.get("started_at_utc") is None:
        document["started_at_utc"] = occurred_at_utc
    if target_state in {"EXPORTED", "EXPORT_FAILED"}:
        document["finished_at_utc"] = occurred_at_utc
    elif target_state == "EXPORTING":
        document["finished_at_utc"] = None
    if target_state == "CANCELLED":
        document["cancelled_at_utc"] = occurred_at_utc
    if source == "EXPORT_FAILED" and target_state == "EXPORTING":
        document["cancelled_at_utc"] = None
    document["job_fingerprint"] = export_job_fingerprint(document)
    require_workspace_document(document)
    return document


def heartbeat_export_job(current: Mapping[str, object], *, occurred_at_utc: str) -> dict[str, object]:
    document = deepcopy(dict(current))
    document["heartbeat_at_utc"] = occurred_at_utc
    document["updated_at_utc"] = occurred_at_utc
    document["job_fingerprint"] = export_job_fingerprint(document)
    require_workspace_document(document)
    return document


def build_export_audit(
    job: Mapping[str, object],
    context: ExportJobContext,
    *,
    audit_event_id_value: str,
    action: str,
    before_state: str | None,
    after_state: str | None,
    outcome: str,
    error_reason: str | None = None,
    idempotent_create: bool = False,
    parent_audit_event_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, object]:
    reference = dict(cast(Mapping[str, object], job["schedule_version"]))
    idempotency = dict(cast(Mapping[str, object], job["idempotency_reference"]))
    event: dict[str, object] = {
        "audit_event_version": "audit-event.v1", "schema_set_version": "2.6.0", "canonicalization_version": "canonical-json.v1",
        "audit_event_id": audit_event_id_value, "occurred_at_utc": context.occurred_at_utc,
        "actor_ref": context.actor_ref, "resolved_capability": "export", "auth_policy_version": context.auth_policy_version,
        "environment": job["environment"], "data_plane": "SIMULATION", "synthetic": True,
        "synthetic_provenance": deepcopy(job["synthetic_provenance"]), "action": action,
        "aggregate_type": "EXPORT_JOB", "aggregate_id": job["export_job_id"], "target": "SIMULATION_INTERNAL",
        "intent_type": "EXPORT", "reason": "EXPORT_JOB_LIFECYCLE", "request_fingerprint": idempotency["request_fingerprint"],
        "idempotency_reference": idempotency if idempotent_create else None,
        "lineage": None, "before_state": before_state, "after_state": after_state,
        "source_version": reference, "new_version": None, "export_job_id": job["export_job_id"],
        "result": {
            "outcome": outcome, "replayed": False, "retryable": error_reason == "EXPORT_FAILED",
            "error": None if error_reason is None else {"error_namespace": "WORKSPACE_CONTROL", "reason": error_reason, "message": "Export lifecycle operation failed."},
        },
        "correlation_id": cast(str, correlation_id or job["export_job_id"]),
        "parent_audit_event_id": parent_audit_event_id,
        "code_commit": context.code_commit,
    }
    require_workspace_document(event)
    return event


def build_export_authorization_denial_audit(
    request: ExportJobRequest,
    context: ExportJobContext,
    identity: ExportJobIdentity,
) -> dict[str, object]:
    event_id = audit_event_id(identity.export_job_id, "DENIED", 0)
    event: dict[str, object] = {
        "audit_event_version": "audit-event.v1", "schema_set_version": "2.6.0", "canonicalization_version": "canonical-json.v1",
        "audit_event_id": event_id, "occurred_at_utc": context.occurred_at_utc,
        "actor_ref": context.actor_ref, "resolved_capability": "export", "auth_policy_version": context.auth_policy_version,
        "environment": request.environment, "data_plane": "SIMULATION", "synthetic": True,
        "synthetic_provenance": deepcopy(dict(request.synthetic_provenance)), "action": "CREATE_EXPORT",
        "aggregate_type": "EXPORT_JOB", "aggregate_id": identity.export_job_id,
        "target": "SIMULATION_INTERNAL", "intent_type": "EXPORT", "reason": request.reason,
        "request_fingerprint": identity.request_fingerprint, "idempotency_reference": None,
        "lineage": None, "before_state": None, "after_state": None,
        "source_version": {"schedule_version_id": request.schedule_version_id, "state": "PUBLISHED", "content_fingerprint": request.expected_content_fingerprint},
        "new_version": None, "export_job_id": identity.export_job_id,
        "result": {"outcome": "DENIED", "replayed": False, "retryable": False, "error": {"error_namespace": "WORKSPACE_CONTROL", "reason": "AUTHORIZATION_DENIED", "message": "Export authorization was denied."}},
        "correlation_id": request.correlation_id, "parent_audit_event_id": None,
        "code_commit": context.code_commit,
    }
    require_workspace_document(event)
    return event


__all__ = [
    "EXPORT_JOB_SERVICE_VERSION", "ExportJobContext", "ExportJobError", "ExportJobFailure",
    "ExportJobIdentity", "ExportJobRequest", "audit_event_id", "build_created_export_job",
    "build_export_audit", "build_export_authorization_denial_audit", "export_job_identity", "heartbeat_export_job", "lease_reference_for",
    "reject_export_job", "require_export_authorization", "require_job_authorization",
    "transition_export_job",
]
