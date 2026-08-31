"""Versioned transport contracts for the P4 dynamic-replanning HTTP API.

The module validates HTTP-only query/action carriers and the already-published
P4 domain carriers.  It deliberately owns no event projection, replan,
solver, validator, state-transition, or ChangeReport calculation behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any, Literal, Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.execution_contracts import (
    contract_fingerprint,
    require_p4_document,
)


DYNAMIC_REPLANNING_API_VERSION = "dynamic-replanning-http.v1"
DYNAMIC_REPLANNING_QUERY_VERSION = "dynamic-replanning-query.v1"
DYNAMIC_REPLANNING_ACTION_VERSION = "replan-attempt-action-http.v1"
DYNAMIC_REPLANNING_RESPONSE_VERSION = "dynamic-replanning-response.v1"
MAX_REPLANNING_QUERY_BYTES = 16_384

_CANONICAL_ID = re.compile(r"[^\s\x00-\x1f\x7f]{1,256}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_EVENT_ID = re.compile(r"execution-event-[0-9a-f]{64}")
_REQUEST_ID = re.compile(r"replan-request-[0-9a-f]{64}")
_REPORT_ID = re.compile(r"change-report-[0-9a-f]{64}")
_ATTEMPT_ID = re.compile(r"replan-attempt-[0-9a-f]{64}")
_ACTION_ID = re.compile(r"replan-action-[0-9a-f]{64}")
_SAFE_REASON = re.compile(r"(?s)(?=.*\S)[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]{1,512}")
_SENSITIVE_REASON_MARKERS = (
    "bearer ",
    "password",
    "postgresql://",
    "redis://",
    "secret",
    "token",
)

_QUERY_FIELDS = frozenset(
    {
        "replanning_query_version",
        "api_contract_version",
        "canonicalization_version",
        "query_kind",
        "resource_id",
        "planning_scope_id",
        "authority_id",
        "stream_id",
        "stream_version",
        "from_position",
        "through_position",
        "attempt_id",
        "request_fingerprint",
        "report_fingerprint",
        "page",
        "data_plane",
        "environment",
        "production_binding",
        "correlation_id",
        "query_fingerprint",
    }
)
_QUERY_KINDS = frozenset(
    {
        "EXECUTION_EVENT",
        "EXECUTION_EVENT_STREAM",
        "REPLAN_REQUEST",
        "REPLAN_RESULT",
        "CHANGE_REPORT",
    }
)
_ACTIVE_PLANNING_RUN_STATES = frozenset(
    {
        "CREATED",
        "INGESTING",
        "VALIDATING",
        "SNAPSHOTTED",
        "BUILDING",
        "SOLVING",
        "SOLVED",
        "VERIFYING",
    }
)
_RETRYABLE_TERMINAL_PLANNING_RUN_STATES = frozenset(
    {
        "DATA_REJECTED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "CANCELLED",
        "FAILED",
    }
)


class DynamicReplanningOperation(StrEnum):
    APPEND_EXECUTION_EVENT = "APPEND_EXECUTION_EVENT"
    GET_EXECUTION_EVENT = "GET_EXECUTION_EVENT"
    LIST_EXECUTION_EVENTS = "LIST_EXECUTION_EVENTS"
    CREATE_REPLAN_REQUEST = "CREATE_REPLAN_REQUEST"
    GET_REPLAN_REQUEST = "GET_REPLAN_REQUEST"
    CANCEL_REPLAN_REQUEST = "CANCEL_REPLAN_REQUEST"
    RETRY_REPLAN_REQUEST = "RETRY_REPLAN_REQUEST"
    GET_REPLAN_RESULT = "GET_REPLAN_RESULT"
    GET_CHANGE_REPORT = "GET_CHANGE_REPORT"


@dataclass(frozen=True, slots=True)
class DynamicReplanningRequestContext:
    """Server-derived request facts; raw credentials and keys are excluded."""

    correlation_id: str
    actor_ref: str
    authenticated: bool
    resolved_capabilities: frozenset[str]
    planning_scope_scope: frozenset[str]
    auth_policy_version: str
    production_binding: bool
    occurred_at_utc: str
    code_commit: str
    data_plane: str
    environment: str
    idempotency_key_reference: str | None = None


@dataclass(frozen=True, slots=True)
class DynamicReplanningApplicationRequest:
    """One validated and authorized P4 HTTP operation for an application facade."""

    operation: DynamicReplanningOperation
    context: DynamicReplanningRequestContext
    resource_id: str | None
    planning_scope_id: str
    document: dict[str, object] | None = None
    query: dict[str, object] | None = None


type DynamicReplanningApplicationResult = Mapping[str, object]


class DynamicReplanningApplicationPort(Protocol):
    """Facade boundary; concrete owners compose P4-04/P4-08/P4-11 services."""

    def execute(
        self, request: DynamicReplanningApplicationRequest
    ) -> DynamicReplanningApplicationResult: ...


type DynamicReplanningHandler = Callable[
    [DynamicReplanningApplicationRequest], DynamicReplanningApplicationResult
]


class DynamicReplanningApplicationError(RuntimeError):
    """Sanitized adapter error consumed by the shared public HTTP mapper."""

    def __init__(self, reason: str, *, field: str, message: str) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason}: {field}: {message}")


class RoutedDynamicReplanningApplication:
    """Explicit operation-to-handler composition helper."""

    def __init__(
        self,
        handlers: Mapping[DynamicReplanningOperation, DynamicReplanningHandler],
    ) -> None:
        self._handlers = dict(handlers)

    def execute(
        self, request: DynamicReplanningApplicationRequest
    ) -> DynamicReplanningApplicationResult:
        handler = self._handlers.get(request.operation)
        if handler is None:
            raise DynamicReplanningApplicationError(
                "SERVICE_UNAVAILABLE",
                field="operation",
                message="dynamic replanning handler is not configured",
            )
        result = handler(request)
        if not isinstance(result, Mapping):
            raise DynamicReplanningApplicationError(
                "PERSISTENCE_FAILED",
                field="application_result",
                message="application result is not a JSON object",
            )
        return result


class UnavailableDynamicReplanningApplication:
    """Fail-closed default until an authorized facade is injected."""

    def execute(
        self, request: DynamicReplanningApplicationRequest
    ) -> DynamicReplanningApplicationResult:
        del request
        raise DynamicReplanningApplicationError(
            "SERVICE_UNAVAILABLE",
            field="application",
            message="dynamic replanning application is not configured",
        )


class ReplanAttemptActionDocument(BaseModel):
    """HTTP-only CAS command; it never gives ReplanRequest a state machine."""

    model_config = ConfigDict(extra="forbid", strict=True)

    replan_action_version: Literal["replan-attempt-action-http.v1"]
    api_contract_version: Literal["dynamic-replanning-http.v1"]
    canonicalization_version: Literal["canonical-json.v1"]
    action_id: str = Field(pattern=r"^replan-action-[0-9a-f]{64}$")
    action: Literal["CANCEL", "RETRY"]
    request_id: str = Field(pattern=r"^replan-request-[0-9a-f]{64}$")
    request_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_attempt_id: str = Field(pattern=r"^replan-attempt-[0-9a-f]{64}$")
    expected_attempt_number: int = Field(ge=1)
    expected_planning_run_state: str
    reason: str = Field(min_length=1, max_length=512)
    data_plane: Literal["SIMULATION"]
    environment: Literal["DEVELOPMENT", "TEST", "BENCHMARK"]
    production_binding: Literal[False]
    correlation_id: str = Field(min_length=1, max_length=256)
    idempotency_key_reference: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if _CANONICAL_ID.fullmatch(self.correlation_id) is None:
            raise ValueError("correlation_id must be canonical")
        if _SAFE_REASON.fullmatch(self.reason) is None or any(
            marker in self.reason.casefold() for marker in _SENSITIVE_REASON_MARKERS
        ):
            raise ValueError("reason must be sanitized non-empty text")
        allowed_states = (
            _ACTIVE_PLANNING_RUN_STATES
            if self.action == "CANCEL"
            else _RETRYABLE_TERMINAL_PLANNING_RUN_STATES
        )
        if self.expected_planning_run_state not in allowed_states:
            raise ValueError("expected PlanningRun state is invalid for action")
        document = self.model_dump(mode="json")
        expected_fingerprint = contract_fingerprint(
            {
                key: value
                for key, value in document.items()
                if key not in {"action_id", "action_fingerprint"}
            }
        )
        expected_id = (
            "replan-action-" + expected_fingerprint.removeprefix("sha256:")
        )
        if self.action_fingerprint != expected_fingerprint or self.action_id != expected_id:
            raise ValueError("action identity does not match canonical content")
        return self


class DynamicReplanningResponseEnvelope(BaseModel):
    """Stable transport envelope around one application-owned result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    response_version: Literal["dynamic-replanning-response.v1"]
    operation: str
    resource_type: str
    resource_id: str | None
    result: dict[str, Any]
    replayed: bool
    correlation_id: str


def idempotency_key_reference(raw_key: str) -> str:
    """Hash the bounded HTTP key before it crosses the transport boundary."""

    if (
        not 16 <= len(raw_key) <= 128
        or _CANONICAL_ID.fullmatch(raw_key) is None
    ):
        raise DynamicReplanningApplicationError(
            "INVALID_REQUEST",
            field="Idempotency-Key",
            message="idempotency key is invalid",
        )
    return f"sha256:{sha256(raw_key.encode('utf-8')).hexdigest()}"


def require_execution_event(document: Mapping[str, object]) -> dict[str, object]:
    result = dict(document)
    try:
        version = require_p4_document(result)
    except (TypeError, ValueError) as error:
        raise DynamicReplanningApplicationError(
            "INVALID_INPUT",
            field="execution_event",
            message="ExecutionEvent contract failed",
        ) from error
    if version != "execution-event.v1":
        raise DynamicReplanningApplicationError(
            "INVALID_INPUT",
            field="execution_event_version",
            message="route requires execution-event.v1",
        )
    return result


def require_replan_request(document: Mapping[str, object]) -> dict[str, object]:
    result = dict(document)
    try:
        version = require_p4_document(result)
    except (TypeError, ValueError) as error:
        raise DynamicReplanningApplicationError(
            "INVALID_INPUT",
            field="replan_request",
            message="ReplanRequest contract failed",
        ) from error
    if version != "replan-request.v1":
        raise DynamicReplanningApplicationError(
            "INVALID_INPUT",
            field="replan_request_version",
            message="route requires replan-request.v1",
        )
    return result


def require_replan_action(
    document: Mapping[str, object],
    *,
    action: str,
    request_id: str,
    key_reference: str,
) -> dict[str, object]:
    try:
        parsed = ReplanAttemptActionDocument.model_validate(dict(document))
    except (TypeError, ValueError) as error:
        raise DynamicReplanningApplicationError(
            "INVALID_REQUEST",
            field="replan_action",
            message="replan action contract failed",
        ) from error
    if (
        parsed.action != action
        or parsed.request_id != request_id
        or parsed.idempotency_key_reference != key_reference
    ):
        raise DynamicReplanningApplicationError(
            "INVALID_REQUEST",
            field="replan_action",
            message="route, action, or idempotency binding differs",
        )
    return cast(dict[str, object], parsed.model_dump(mode="json"))


def require_replanning_query(
    value: str | Mapping[str, object],
    *,
    query_kind: str,
    resource_id: str | None,
) -> dict[str, object]:
    """Decode, fingerprint, and route-bind one HTTP-only P4 query carrier."""

    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_REPLANNING_QUERY_BYTES:
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field="query", message="query is too large"
            )
        try:
            decoded = json.loads(value)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field="query", message="query is invalid"
            ) from error
        if not isinstance(decoded, Mapping):
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field="query", message="query must be an object"
            )
        document = dict(cast(Mapping[str, object], decoded))
    else:
        document = dict(value)

    page = document.get("page")
    if set(document) != _QUERY_FIELDS or not isinstance(page, Mapping) or set(page) != {
        "size",
        "cursor",
    }:
        raise DynamicReplanningApplicationError(
            "INVALID_QUERY", field="query", message="query fields drifted"
        )
    if (
        document.get("replanning_query_version") != DYNAMIC_REPLANNING_QUERY_VERSION
        or document.get("api_contract_version") != DYNAMIC_REPLANNING_API_VERSION
        or document.get("canonicalization_version") != "canonical-json.v1"
        or document.get("query_kind") not in _QUERY_KINDS
        or document.get("query_kind") != query_kind
        or document.get("resource_id") != resource_id
        or document.get("data_plane") != "SIMULATION"
        or document.get("environment") not in {"DEVELOPMENT", "TEST", "BENCHMARK"}
        or document.get("production_binding") is not False
    ):
        raise DynamicReplanningApplicationError(
            "INVALID_QUERY", field="query", message="query route or boundary mismatch"
        )
    for field in ("planning_scope_id", "correlation_id"):
        value_at_field = document.get(field)
        if not isinstance(value_at_field, str) or _CANONICAL_ID.fullmatch(value_at_field) is None:
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field=field, message="must be canonical"
            )
    size = page.get("size")
    cursor = page.get("cursor")
    if (
        isinstance(size, bool)
        or not isinstance(size, int)
        or not 1 <= size <= 200
        or (
            cursor is not None
            and (
                not isinstance(cursor, str)
                or _CANONICAL_ID.fullmatch(cursor) is None
            )
        )
    ):
        raise DynamicReplanningApplicationError(
            "INVALID_QUERY", field="page", message="page is invalid"
        )
    optional_ids = {
        "authority_id": _CANONICAL_ID,
        "stream_id": _CANONICAL_ID,
        "stream_version": re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"),
        "attempt_id": _ATTEMPT_ID,
        "request_fingerprint": _FINGERPRINT,
        "report_fingerprint": _FINGERPRINT,
    }
    for field, pattern in optional_ids.items():
        item = document.get(field)
        if item is not None and (
            not isinstance(item, str) or pattern.fullmatch(item) is None
        ):
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field=field, message="query reference is invalid"
            )
    for field in ("from_position", "through_position"):
        item = document.get(field)
        if item is not None and (
            isinstance(item, bool) or not isinstance(item, int) or item < 1
        ):
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field=field, message="stream position is invalid"
            )

    if query_kind == "EXECUTION_EVENT":
        valid_kind = (
            resource_id is not None
            and _EVENT_ID.fullmatch(resource_id) is not None
            and all(
                document.get(field) is None
                for field in (
                    "authority_id",
                    "stream_id",
                    "stream_version",
                    "from_position",
                    "through_position",
                    "attempt_id",
                    "request_fingerprint",
                    "report_fingerprint",
                )
            )
        )
    elif query_kind == "EXECUTION_EVENT_STREAM":
        start = document.get("from_position")
        end = document.get("through_position")
        valid_kind = (
            resource_id is None
            and all(
                document.get(field) is not None
                for field in (
                    "authority_id",
                    "stream_id",
                    "stream_version",
                    "from_position",
                    "through_position",
                )
            )
            and isinstance(start, int)
            and not isinstance(start, bool)
            and isinstance(end, int)
            and not isinstance(end, bool)
            and start <= end
            and all(
                document.get(field) is None
                for field in (
                    "attempt_id",
                    "request_fingerprint",
                    "report_fingerprint",
                )
            )
        )
    elif query_kind == "REPLAN_REQUEST":
        valid_kind = (
            resource_id is not None
            and _REQUEST_ID.fullmatch(resource_id) is not None
            and document.get("request_fingerprint") is not None
            and all(
                document.get(field) is None
                for field in (
                    "authority_id",
                    "stream_id",
                    "stream_version",
                    "from_position",
                    "through_position",
                    "attempt_id",
                    "report_fingerprint",
                )
            )
        )
    elif query_kind == "REPLAN_RESULT":
        valid_kind = (
            resource_id is not None
            and _REQUEST_ID.fullmatch(resource_id) is not None
            and document.get("request_fingerprint") is not None
            and document.get("attempt_id") is not None
            and all(
                document.get(field) is None
                for field in (
                    "authority_id",
                    "stream_id",
                    "stream_version",
                    "from_position",
                    "through_position",
                    "report_fingerprint",
                )
            )
        )
    else:
        valid_kind = (
            resource_id is not None
            and _REPORT_ID.fullmatch(resource_id) is not None
            and document.get("request_fingerprint") is not None
            and document.get("attempt_id") is not None
            and document.get("report_fingerprint") is not None
            and all(
                document.get(field) is None
                for field in (
                    "authority_id",
                    "stream_id",
                    "stream_version",
                    "from_position",
                    "through_position",
                )
            )
        )
    if not valid_kind:
        raise DynamicReplanningApplicationError(
            "INVALID_QUERY", field="query_kind", message="query shape is invalid"
        )

    expected_fingerprint = contract_fingerprint(
        {key: item for key, item in document.items() if key != "query_fingerprint"}
    )
    if document.get("query_fingerprint") != expected_fingerprint:
        raise DynamicReplanningApplicationError(
            "INVALID_QUERY", field="query_fingerprint", message="fingerprint differs"
        )
    return document


def validate_response_envelope(
    value: Mapping[str, object],
    *,
    operation: DynamicReplanningOperation,
    resource_type: str,
    resource_id: str | None,
    correlation_id: str,
) -> dict[str, object]:
    try:
        envelope = DynamicReplanningResponseEnvelope.model_validate(dict(value))
    except (TypeError, ValueError) as error:
        raise DynamicReplanningApplicationError(
            "PERSISTENCE_FAILED",
            field="application_result",
            message="response envelope failed its transport contract",
        ) from error
    if (
        envelope.operation != operation.value
        or envelope.resource_type != resource_type
        or envelope.resource_id != resource_id
        or envelope.correlation_id != correlation_id
        or _CANONICAL_ID.fullmatch(envelope.resource_type) is None
        or _CANONICAL_ID.fullmatch(envelope.correlation_id) is None
    ):
        raise DynamicReplanningApplicationError(
            "PERSISTENCE_FAILED",
            field="application_result",
            message="response envelope differs from the request authority",
        )
    return cast(dict[str, object], envelope.model_dump(mode="json"))


__all__ = [
    "DYNAMIC_REPLANNING_ACTION_VERSION",
    "DYNAMIC_REPLANNING_API_VERSION",
    "DYNAMIC_REPLANNING_QUERY_VERSION",
    "DYNAMIC_REPLANNING_RESPONSE_VERSION",
    "DynamicReplanningApplicationError",
    "DynamicReplanningApplicationPort",
    "DynamicReplanningApplicationRequest",
    "DynamicReplanningOperation",
    "DynamicReplanningRequestContext",
    "DynamicReplanningResponseEnvelope",
    "ReplanAttemptActionDocument",
    "RoutedDynamicReplanningApplication",
    "UnavailableDynamicReplanningApplication",
    "idempotency_key_reference",
    "require_execution_event",
    "require_replan_action",
    "require_replan_request",
    "require_replanning_query",
    "validate_response_envelope",
]
