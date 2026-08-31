"""Versioned transport contracts for the P3 planning-workspace HTTP API.

This module deliberately contains transport adaptation only.  The injected
``PlanningWorkspaceApplicationPort`` remains the sole owner of read, command,
validation, state-transition, publication, and export semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict

from app.domain.workspace_contracts import require_workspace_document


API_PREFIX = "/api/v1"
API_ERROR_VERSION = "planning-workspace-error.v1"
API_CONTRACT_VERSION = "planning-workspace-http.v1"
MAX_QUERY_CARRIER_BYTES = 16_384

_SAFE_ID = re.compile(r"[^\s\x00-\x1f\x7f]{1,256}")
_SAFE_FIELD = re.compile(r"[A-Za-z0-9_.\[\]/-]{1,256}")

_QUERY_FIELDS = frozenset(
    {
        "workspace_query_version",
        "schema_set_version",
        "canonicalization_version",
        "direction",
        "query_kind",
        "data_plane",
        "environment",
        "synthetic",
        "resource",
        "view",
        "schedule_version_precondition",
        "sort",
        "filters",
        "page",
        "query_fingerprint",
        "correlation_id",
        "result",
    }
)
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
        "target",
        "reason",
        "correlation_id",
        "payload",
    }
)
_COMMAND_PAYLOAD_FIELDS = {
    "MOVE_OPERATION": frozenset(
        {"operation_id", "resource_id", "start_at_utc", "end_at_utc"}
    ),
    "ASSIGN_RESOURCE": frozenset({"operation_id", "resource_id"}),
    "SET_LOCK": frozenset({"lock"}),
    "REMOVE_LOCK": frozenset({"lock_id", "operation_id"}),
    "SUBMIT_FOR_REVIEW": frozenset(),
    "APPROVE": frozenset(),
    "REJECT": frozenset(),
    "PUBLISH": frozenset({"previous_current_version"}),
    "REQUEST_EXPORT": frozenset({"package_profile"}),
    "RETRY_EXPORT": frozenset({"expected_attempt"}),
    "CANCEL_EXPORT": frozenset({"expected_attempt"}),
}


class PlanningWorkspaceOperation(StrEnum):
    GET_PLANNING_RUN = "GET_PLANNING_RUN"
    GET_SCHEDULE_VERSION = "GET_SCHEDULE_VERSION"
    VALIDATE_SCHEDULE_VERSION = "VALIDATE_SCHEDULE_VERSION"
    APPROVE_SCHEDULE_VERSION = "APPROVE_SCHEDULE_VERSION"
    REJECT_SCHEDULE_VERSION = "REJECT_SCHEDULE_VERSION"
    PUBLISH_SCHEDULE_VERSION = "PUBLISH_SCHEDULE_VERSION"
    QUERY_WORKSPACE = "QUERY_WORKSPACE"
    COMPARE_SCHEDULE_VERSIONS = "COMPARE_SCHEDULE_VERSIONS"
    EXECUTE_SCHEDULE_COMMAND = "EXECUTE_SCHEDULE_COMMAND"
    LIST_AUDIT_EVENTS = "LIST_AUDIT_EVENTS"
    CREATE_EXPORT_JOB = "CREATE_EXPORT_JOB"
    GET_EXPORT_JOB = "GET_EXPORT_JOB"
    DOWNLOAD_EXPORT_PACKAGE = "DOWNLOAD_EXPORT_PACKAGE"
    RETRY_EXPORT_JOB = "RETRY_EXPORT_JOB"
    CANCEL_EXPORT_JOB = "CANCEL_EXPORT_JOB"


@dataclass(frozen=True, slots=True)
class PlanningWorkspaceRequestContext:
    """Server-derived request facts; never populated from body role claims."""

    correlation_id: str
    actor_ref: str
    authenticated: bool
    resolved_capabilities: frozenset[str]
    planning_run_scope: frozenset[str]
    schedule_version_scope: frozenset[str]
    export_job_scope: frozenset[str]
    auth_policy_version: str
    production_binding: bool
    occurred_at_utc: str
    code_commit: str
    data_plane: str
    environment: str
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class PlanningWorkspaceApplicationRequest:
    """One already-authenticated HTTP operation presented to application code."""

    operation: PlanningWorkspaceOperation
    context: PlanningWorkspaceRequestContext
    resource_id: str | None = None
    view: str | None = None
    document: dict[str, object] | None = None
    compared_version_precondition: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PlanningWorkspaceDownload:
    """Verified binary result returned only by the bounded download operation."""

    content: bytes
    filename: str
    media_type: str
    package_id: str
    manifest_fingerprint: str
    archive_fingerprint: str
    completion_audit_event_id: str
    correlation_id: str


type PlanningWorkspaceApplicationResult = (
    Mapping[str, object] | PlanningWorkspaceDownload
)


class PlanningWorkspaceApplicationPort(Protocol):
    """Application façade used by the router; implementations compose P3-05..09."""

    def execute(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> PlanningWorkspaceApplicationResult: ...


type PlanningWorkspaceHandler = Callable[
    [PlanningWorkspaceApplicationRequest], PlanningWorkspaceApplicationResult
]


class RoutedPlanningWorkspaceApplication:
    """Small composition helper binding HTTP operations to application handlers."""

    def __init__(
        self,
        handlers: Mapping[PlanningWorkspaceOperation, PlanningWorkspaceHandler],
    ) -> None:
        self._handlers = dict(handlers)

    def execute(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> PlanningWorkspaceApplicationResult:
        handler = self._handlers.get(request.operation)
        if handler is None:
            raise PlanningWorkspaceApplicationError(
                "SERVICE_UNAVAILABLE",
                field="operation",
                message="application handler is not configured",
            )
        result = handler(request)
        if not isinstance(result, (Mapping, PlanningWorkspaceDownload)):
            raise PlanningWorkspaceApplicationError(
                "PERSISTENCE_FAILED",
                field="application_result",
                message="application result is not a JSON object",
            )
        return result


class UnavailablePlanningWorkspaceApplication:
    """Fail-closed default until an authorized application composition is injected."""

    def execute(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> PlanningWorkspaceApplicationResult:
        del request
        raise PlanningWorkspaceApplicationError(
            "SERVICE_UNAVAILABLE",
            field="application",
            message="planning workspace application is not configured",
        )


class PlanningWorkspaceApplicationError(RuntimeError):
    """Sanitized adapter error for application façades and test compositions."""

    def __init__(self, reason: str, *, field: str, message: str) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason}: {field}: {message}")


class ProductErrorReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    category: str
    code: str


class WorkspaceControlErrorReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    control_version: str = "workspace-control.v1"
    reason: str


class PlanningWorkspaceErrorEnvelope(BaseModel):
    """Stable public error shape; internal exception text is never serialized."""

    model_config = ConfigDict(extra="forbid", strict=True)

    error_version: str = API_ERROR_VERSION
    namespace: str
    product_error: ProductErrorReference | None
    workspace_control_error: WorkspaceControlErrorReference | None
    message: str
    details: dict[str, str]
    correlation_id: str
    retryable: bool
    resource: dict[str, str] | None


class PlanningWorkspaceHttpError(Exception):
    def __init__(
        self,
        status_code: int,
        envelope: PlanningWorkspaceErrorEnvelope,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.envelope = envelope
        self.headers = dict(headers or {})
        super().__init__(envelope.message)


_AUTH_REASONS = frozenset(
    {"AUTHORIZATION_DENIED", "UNAUTHORIZED", "PRODUCTION_AUTHORITY_UNAVAILABLE"}
)
_NOT_FOUND_REASONS = frozenset(
    {
        "SOURCE_NOT_FOUND",
        "SOURCE_MISSING",
        "PUBLICATION_NOT_FOUND",
        "PREVIOUS_CURRENT_NOT_FOUND",
        "NOT_FOUND",
    }
)
_CONFLICT_REASONS = frozenset(
    {
        "STALE_SOURCE",
        "STALE_VERSION",
        "STALE_CURSOR",
        "STATE_CONFLICT",
        "INVALID_STATE_TRANSITION",
        "CURRENT_REFERENCE_CONFLICT",
        "LEASE_CONFLICT",
        "LOCK_CONFLICT",
        "IMMUTABLE_EXECUTION_FACT",
        "IDENTITY_CONFLICT",
        "LINEAGE_MISMATCH",
        "POSITION_CONFLICT",
        "STREAM_GAP",
        "LATE_EVENT",
        "NO_OP",
    }
)
_INVALID_REASONS = frozenset(
    {
        "INVALID_REQUEST",
        "INVALID_COMMAND",
        "INVALID_QUERY",
        "INVALID_INPUT",
        "INVALID_REFERENCE",
        "INVALID_TIME",
        "DATA_PLANE_MISMATCH",
        "MIXED_LINEAGE",
        "KPI_MISMATCH",
        "PLANNING_RUN_NOT_COMPLETED",
        "AUTHORITY_MISMATCH",
        "CHANGE_REPORT_INCOMPLETE",
    }
)
_SYSTEM_REASONS = frozenset(
    {"PERSISTENCE_FAILED", "EXPORT_FAILED", "SERVICE_UNAVAILABLE", "SYSTEM_ERROR"}
)


def _reason(error: BaseException) -> str:
    value = getattr(error, "reason", None)
    value = getattr(value, "value", value)
    return value if isinstance(value, str) and value else "SYSTEM_ERROR"


def _field(error: BaseException) -> str:
    value = getattr(error, "field", "request")
    if isinstance(value, str) and _SAFE_FIELD.fullmatch(value):
        return value
    return "request"


def _resource(value: Mapping[str, str] | None) -> dict[str, str] | None:
    if value is None:
        return None
    result: dict[str, str] = {}
    for key, item in value.items():
        if _SAFE_FIELD.fullmatch(key) and _SAFE_ID.fullmatch(item):
            result[key] = item
    return result or None


def public_http_error(
    reason: str,
    *,
    correlation_id: str,
    field: str = "request",
    resource: Mapping[str, str] | None = None,
    status_code: int | None = None,
) -> PlanningWorkspaceHttpError:
    """Create a safe public error without copying exception messages or values."""

    if reason in _AUTH_REASONS:
        status = status_code or 403
        control_reason = "AUTHORIZATION_DENIED"
        product = None
        message = "Authorization denied."
    elif reason == "IDEMPOTENCY_CONFLICT":
        status = status_code or 409
        control_reason = "IDEMPOTENCY_CONFLICT"
        product = None
        message = "The idempotency key conflicts with an earlier request."
    elif reason == "UNKNOWN_OUTCOME":
        status = status_code or 503
        control_reason = "UNKNOWN_OUTCOME"
        product = None
        message = "The operation outcome is unknown; query the exact result before retrying."
    elif reason == "EXPORT_FAILED":
        status = status_code or 500
        control_reason = "EXPORT_FAILED"
        product = None
        message = "The export operation failed."
    else:
        control_reason = None
        if reason in _NOT_FOUND_REASONS:
            status = status_code or 404
            category, code = "DATA_ERROR", "INVALID_REFERENCE"
            message = "The requested resource was not found."
        elif reason == "VALIDATION_FAILED":
            status = status_code or 422
            category, code = "VALIDATION_FAILED", "SCHEDULE_VALIDATION_FAILED"
            message = "The schedule failed independent validation."
        elif reason in _CONFLICT_REASONS:
            status = status_code or 409
            category, code = "DATA_ERROR", "INVALID_STATE_TRANSITION"
            message = "The request conflicts with current authoritative state."
        elif reason in _INVALID_REASONS:
            status = status_code or 422
            category = "DATA_ERROR"
            code = "INVALID_TIME" if reason == "INVALID_TIME" else "INVALID_REFERENCE"
            message = "The request failed the published contract."
        elif reason in _SYSTEM_REASONS:
            status = status_code or (503 if reason == "SERVICE_UNAVAILABLE" else 500)
            category, code = "SYSTEM_ERROR", "SYSTEM_ERROR"
            message = "The service could not complete the request."
        else:
            status = status_code or 500
            category, code = "SYSTEM_ERROR", "SYSTEM_ERROR"
            message = "The service could not complete the request."
            reason = "SYSTEM_ERROR"
        product = ProductErrorReference(category=category, code=code)

    envelope = PlanningWorkspaceErrorEnvelope(
        namespace="WORKSPACE_CONTROL" if control_reason is not None else "PRODUCT",
        product_error=product,
        workspace_control_error=(
            WorkspaceControlErrorReference(reason=control_reason)
            if control_reason is not None
            else None
        ),
        message=message,
        details={
            "field": field if _SAFE_FIELD.fullmatch(field) else "request",
            "reason": reason,
        },
        correlation_id=correlation_id,
        retryable=status == 503 and reason != "UNKNOWN_OUTCOME",
        resource=_resource(resource),
    )
    headers = {
        "X-Correlation-Id": correlation_id,
        "Cache-Control": "no-store",
    }
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return PlanningWorkspaceHttpError(status, envelope, headers=headers)


def application_error_to_http(
    error: BaseException,
    *,
    correlation_id: str,
    resource: Mapping[str, str] | None = None,
) -> PlanningWorkspaceHttpError:
    if isinstance(error, PlanningWorkspaceHttpError):
        return error
    return public_http_error(
        _reason(error),
        correlation_id=correlation_id,
        field=_field(error),
        resource=resource,
    )


def require_query_carrier(
    value: str | Mapping[str, object],
    *,
    expected_views: Sequence[str],
    schedule_version_id: str | None = None,
) -> dict[str, object]:
    """Decode and bind one strict ``workspace-query.v1`` REQUEST carrier."""

    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_QUERY_CARRIER_BYTES:
            raise PlanningWorkspaceApplicationError(
                "INVALID_QUERY", field="workspace_query", message="query is too large"
            )
        try:
            decoded = json.loads(value)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise PlanningWorkspaceApplicationError(
                "INVALID_QUERY", field="workspace_query", message="query is invalid"
            ) from error
        if not isinstance(decoded, Mapping):
            raise PlanningWorkspaceApplicationError(
                "INVALID_QUERY",
                field="workspace_query",
                message="query must be an object",
            )
        document = dict(cast(Mapping[str, object], decoded))
    else:
        document = dict(value)
    expected_fields = set(_QUERY_FIELDS)
    if document.get("synthetic") is True:
        expected_fields.add("synthetic_provenance")
    if set(document) != expected_fields:
        raise PlanningWorkspaceApplicationError(
            "INVALID_QUERY", field="workspace_query", message="query fields drifted"
        )
    resource_value = document.get("resource")
    precondition_value = document.get("schedule_version_precondition")
    sort_value = document.get("sort")
    filters_value = document.get("filters")
    page_value = document.get("page")
    if (
        not isinstance(resource_value, Mapping)
        or set(resource_value) != {"resource_type", "resource_id"}
        or (
            precondition_value is not None
            and (
                not isinstance(precondition_value, Mapping)
                or set(precondition_value)
                != {"schedule_version_id", "state", "content_fingerprint"}
            )
        )
        or not isinstance(sort_value, list)
        or any(
            not isinstance(term, Mapping) or set(term) != {"field", "direction"}
            for term in sort_value
        )
        or not isinstance(filters_value, Mapping)
        or set(filters_value)
        != {
            "order_ids",
            "operation_ids",
            "resource_ids",
            "states",
            "start_at_or_after_utc",
            "start_before_utc",
        }
        or not isinstance(page_value, Mapping)
        or set(page_value) != {"size", "cursor"}
    ):
        raise PlanningWorkspaceApplicationError(
            "INVALID_QUERY",
            field="workspace_query",
            message="nested query fields drifted",
        )
    try:
        contract = require_workspace_document(document)
    except (TypeError, ValueError) as error:
        raise PlanningWorkspaceApplicationError(
            "INVALID_QUERY", field="workspace_query", message="query contract failed"
        ) from error
    if (
        contract != "workspace-query.v1"
        or document.get("direction") != "REQUEST"
        or document.get("result") is not None
        or document.get("view") not in set(expected_views)
    ):
        raise PlanningWorkspaceApplicationError(
            "INVALID_QUERY", field="workspace_query", message="query route mismatch"
        )
    resource = document.get("resource")
    if not isinstance(resource, Mapping):
        raise PlanningWorkspaceApplicationError(
            "INVALID_QUERY", field="resource", message="resource is invalid"
        )
    if schedule_version_id is None:
        if (
            resource.get("resource_type") != "WORKSPACE"
            or resource.get("resource_id") is not None
        ):
            raise PlanningWorkspaceApplicationError(
                "INVALID_QUERY", field="resource", message="workspace resource mismatch"
            )
    elif (
        resource.get("resource_type") != "SCHEDULE_VERSION"
        or resource.get("resource_id") != schedule_version_id
    ):
        raise PlanningWorkspaceApplicationError(
            "INVALID_QUERY", field="resource", message="schedule resource mismatch"
        )
    return document


_COMMAND_CAPABILITIES = {
    "MOVE_OPERATION": "edit",
    "ASSIGN_RESOURCE": "edit",
    "SET_LOCK": "lock",
    "REMOVE_LOCK": "lock",
    "SUBMIT_FOR_REVIEW": "edit",
    "APPROVE": "approve",
    "REJECT": "reject",
    "PUBLISH": "publish",
    "REQUEST_EXPORT": "export",
    "RETRY_EXPORT": "export",
    "CANCEL_EXPORT": "export",
}


def require_command_carrier(
    document: Mapping[str, object],
    *,
    expected_command_types: Sequence[str],
    source_id: str,
    idempotency_key: str,
) -> tuple[dict[str, object], str]:
    """Validate route/body/header binding and return server-derived capability."""

    result = dict(document)
    expected_fields = set(_COMMAND_FIELDS)
    if result.get("synthetic") is True:
        expected_fields.add("synthetic_provenance")
    command_type_value = result.get("command_type")
    payload_value = result.get("payload")
    expected_payload = _COMMAND_PAYLOAD_FIELDS.get(
        cast(str, command_type_value), frozenset({"__unsupported__"})
    )
    if (
        set(result) != expected_fields
        or not isinstance(payload_value, Mapping)
        or set(payload_value) != expected_payload
    ):
        raise PlanningWorkspaceApplicationError(
            "INVALID_COMMAND", field="body", message="command fields drifted"
        )
    if command_type_value == "SET_LOCK":
        lock = payload_value.get("lock")
        if not isinstance(lock, Mapping) or set(lock) != {
            "lock_id",
            "operation_id",
            "lock_type",
            "resource_id",
            "start_at_utc",
            "end_at_utc",
        }:
            raise PlanningWorkspaceApplicationError(
                "INVALID_COMMAND", field="payload.lock", message="lock fields drifted"
            )
    if command_type_value == "PUBLISH":
        previous = payload_value.get("previous_current_version")
        if previous is not None and (
            not isinstance(previous, Mapping)
            or set(previous) != {"schedule_version_id", "state", "content_fingerprint"}
        ):
            raise PlanningWorkspaceApplicationError(
                "INVALID_COMMAND",
                field="payload.previous_current_version",
                message="version reference fields drifted",
            )
    try:
        contract = require_workspace_document(result)
    except (TypeError, ValueError) as error:
        raise PlanningWorkspaceApplicationError(
            "INVALID_COMMAND", field="body", message="command contract failed"
        ) from error
    command_type = result.get("command_type")
    if (
        contract != "workspace-command.v1"
        or command_type not in set(expected_command_types)
        or result.get("source_id") != source_id
        or result.get("idempotency_key") != idempotency_key
    ):
        raise PlanningWorkspaceApplicationError(
            "INVALID_COMMAND", field="body", message="command route binding failed"
        )
    capability = _COMMAND_CAPABILITIES.get(cast(str, command_type))
    if capability is None or result.get("required_capability") != capability:
        raise PlanningWorkspaceApplicationError(
            "INVALID_COMMAND",
            field="required_capability",
            message="capability mismatch",
        )
    return result, capability


__all__ = [
    "API_CONTRACT_VERSION",
    "API_ERROR_VERSION",
    "API_PREFIX",
    "PlanningWorkspaceApplicationError",
    "PlanningWorkspaceApplicationPort",
    "PlanningWorkspaceApplicationRequest",
    "PlanningWorkspaceApplicationResult",
    "PlanningWorkspaceDownload",
    "PlanningWorkspaceErrorEnvelope",
    "PlanningWorkspaceHandler",
    "PlanningWorkspaceHttpError",
    "PlanningWorkspaceOperation",
    "PlanningWorkspaceRequestContext",
    "RoutedPlanningWorkspaceApplication",
    "UnavailablePlanningWorkspaceApplication",
    "application_error_to_http",
    "public_http_error",
    "require_command_carrier",
    "require_query_carrier",
]
