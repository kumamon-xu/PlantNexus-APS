"""Strict transport contracts for the P8 Headless PlanningRun HTTP surface."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Annotated, Any, Literal, cast
from uuid import uuid4

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.data_validation.canonical_ingress import (
    CanonicalIngressContractError,
    parse_strict_json,
)


type JsonObject = dict[str, Any]

HEADLESS_HTTP_VERSION = "headless-http.v1"
MAX_CANONICAL_REQUEST_BYTES = 8 * 1024 * 1024
MAX_ACTION_REQUEST_BYTES = 16 * 1024
MAX_JSON_DEPTH = 64
MAX_CANONICAL_RECORDS = 100_000

_CANONICAL_ID = re.compile(r"[^\s\x00-\x1f\x7f]{1,256}")
_HTTP_CORRELATION_ID = re.compile(r"[!-~]{1,256}")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{16,128}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_SAFE_REASON_PATTERN = r"[^\x00-\x1f\x7f]{1,512}"
_SAFE_POINTER = re.compile(r"/[^\x00-\x1f\x7f]{0,511}")
_SECRET_TEXT = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|password\s*=|token\s*=|"
    r"secret\s*=|cookie\s*=|postgres(?:ql)?://|redis://)"
)


@dataclass(frozen=True, slots=True)
class _ErrorSpec:
    category: str
    stage: str
    retryability: str
    action: str
    message: str
    expected_contract: str


_ERROR_SPECS: dict[str, _ErrorSpec] = {
    "MALFORMED_JSON": _ErrorSpec(
        "CONTRACT_ERROR",
        "TRANSPORT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The request is not a strict UTF-8 JSON object.",
        "strict UTF-8 JSON object",
    ),
    "DUPLICATE_JSON_KEY": _ErrorSpec(
        "CONTRACT_ERROR",
        "TRANSPORT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "Duplicate JSON object member names are forbidden.",
        "unique JSON object member names",
    ),
    "NON_FINITE_NUMBER": _ErrorSpec(
        "CONTRACT_ERROR",
        "TRANSPORT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "Non-finite JSON numbers are forbidden.",
        "finite JSON numbers",
    ),
    "UNSUPPORTED_MEDIA_TYPE": _ErrorSpec(
        "CONTRACT_ERROR",
        "TRANSPORT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "This operation accepts only unencoded application/json.",
        "application/json; charset=utf-8 without Content-Encoding",
    ),
    "PAYLOAD_LIMIT_EXCEEDED": _ErrorSpec(
        "CONTRACT_ERROR",
        "TRANSPORT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The request exceeds the published Headless transport envelope.",
        "P8-07 bounded HTTP payload envelope",
    ),
    "UNKNOWN_CONTRACT_VERSION": _ErrorSpec(
        "CONTRACT_ERROR",
        "CONTRACT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "A request contract version is not supported.",
        "published Headless v1 machine contract",
    ),
    "CONTRACT_VIOLATION": _ErrorSpec(
        "CONTRACT_ERROR",
        "CONTRACT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The request violates the published Headless contract.",
        "published Headless v1 machine contract",
    ),
    "SCOPE_MISMATCH": _ErrorSpec(
        "SCOPE_ERROR",
        "AUTHORIZATION",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The requested business scope is not authorized by this Runtime.",
        "server-resolved effective scope",
    ),
    "DATA_PLANE_MISMATCH": _ErrorSpec(
        "SCOPE_ERROR",
        "AUTHORIZATION",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The requested data plane or environment is unavailable.",
        "configured Runtime data plane and environment",
    ),
    "AUTHORITY_CONFLICT": _ErrorSpec(
        "AUTHORITY_ERROR",
        "CONTRACT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "Canonical source authority is not authorized by this Runtime.",
        "server-authorized authority and mapping references",
    ),
    "LINEAGE_INVALID": _ErrorSpec(
        "AUTHORITY_ERROR",
        "CONTRACT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "Canonical lineage is invalid or unavailable.",
        "content-derived immutable Headless lineage",
    ),
    "IDEMPOTENCY_CONFLICT": _ErrorSpec(
        "CONFLICT",
        "IDEMPOTENCY",
        "NOT_RETRYABLE",
        "READ_CURRENT_STATE",
        "The idempotency key is bound to a different command.",
        "same scope and key bound to the original command",
    ),
    "INVALID_REFERENCE": _ErrorSpec(
        "DATA_ERROR",
        "CONTRACT",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "A referenced PlanningRun or planning input is unavailable.",
        "existing authorized Headless reference",
    ),
    "INVALID_STATE_TRANSITION": _ErrorSpec(
        "DATA_ERROR",
        "STATE",
        "NOT_RETRYABLE",
        "READ_CURRENT_STATE",
        "The command is not valid for the current PlanningRun state.",
        "current planning-run.v1 revision, state and fingerprint",
    ),
    "RUNTIME_RESOLUTION_FAILED": _ErrorSpec(
        "SYSTEM_ERROR",
        "RUNTIME_RESOLUTION",
        "RETRY_AFTER_OPERATOR_ACTION",
        "CONTACT_OPERATOR",
        "The Runtime could not provide its pinned component resolution.",
        "valid server-owned runtime-resolution.v1",
    ),
    "EXTENSION_SET_MISMATCH": _ErrorSpec(
        "SYSTEM_ERROR",
        "RUNTIME_RESOLUTION",
        "RETRY_AFTER_OPERATOR_ACTION",
        "CONTACT_OPERATOR",
        "The configured Extension set differs from the pinned Runtime.",
        "server-owned pinned Extension set",
    ),
    "DATA_VALIDATION_FAILED": _ErrorSpec(
        "DATA_ERROR",
        "DATA_VALIDATION",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "Canonical planning data did not pass Data Validation.",
        "zero-error PASS import-quality-report.v1",
    ),
    "MODEL_INVALID": _ErrorSpec(
        "MODEL_INVALID",
        "PROBLEM_BUILD",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "Canonical data could not produce a valid planning model.",
        "planning-problem.v2 build contract",
    ),
    "INFEASIBLE": _ErrorSpec(
        "INFEASIBLE",
        "SOLVER",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The validated planning model is infeasible.",
        "solver-report.v2 terminal evidence",
    ),
    "NO_SOLUTION_WITHIN_LIMIT": _ErrorSpec(
        "NO_SOLUTION_WITHIN_LIMIT",
        "SOLVER",
        "RETRY_AFTER_OPERATOR_ACTION",
        "CONTACT_OPERATOR",
        "No solution was proven within the configured solve limit.",
        "server-owned solve-limits.v1",
    ),
    "SCHEDULE_VALIDATION_FAILED": _ErrorSpec(
        "VALIDATION_FAILED",
        "VALIDATION",
        "NOT_RETRYABLE",
        "FIX_REQUEST",
        "The candidate schedule did not pass formal validation.",
        "PASS validation-report.v2",
    ),
    "RUN_CANCELLED": _ErrorSpec(
        "CANCELLED",
        "STATE",
        "NOT_RETRYABLE",
        "READ_CURRENT_STATE",
        "The PlanningRun was cancelled by an authorized command.",
        "planning-run.v1 cancellation evidence",
    ),
    "SYSTEM_ERROR": _ErrorSpec(
        "SYSTEM_ERROR",
        "SYSTEM",
        "RETRY_SAME_REQUEST",
        "RETRY_SAME_IDEMPOTENCY_KEY",
        "The Runtime could not complete the request safely.",
        "atomic durable Runtime operation",
    ),
}

_DEFAULT_STATUS: dict[str, int] = {
    "MALFORMED_JSON": 400,
    "DUPLICATE_JSON_KEY": 400,
    "NON_FINITE_NUMBER": 400,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "PAYLOAD_LIMIT_EXCEEDED": 413,
    "UNKNOWN_CONTRACT_VERSION": 400,
    "CONTRACT_VIOLATION": 422,
    "SCOPE_MISMATCH": 403,
    "DATA_PLANE_MISMATCH": 403,
    "AUTHORITY_CONFLICT": 403,
    "LINEAGE_INVALID": 422,
    "IDEMPOTENCY_CONFLICT": 409,
    "INVALID_REFERENCE": 404,
    "INVALID_STATE_TRANSITION": 409,
    "RUNTIME_RESOLUTION_FAILED": 503,
    "EXTENSION_SET_MISMATCH": 503,
    "DATA_VALIDATION_FAILED": 422,
    "MODEL_INVALID": 422,
    "INFEASIBLE": 409,
    "NO_SOLUTION_WITHIN_LIMIT": 409,
    "SCHEDULE_VALIDATION_FAILED": 409,
    "RUN_CANCELLED": 409,
    "SYSTEM_ERROR": 500,
}


class PlanningRunCancelAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action_version: Literal["planning-run-cancel-action.v1"]
    expected_revision: Annotated[int, Field(ge=1)]
    expected_state: Annotated[str, Field(min_length=1, max_length=64)]
    expected_run_fingerprint: Annotated[str, Field(pattern=_FINGERPRINT.pattern)]
    reason: Annotated[str, Field(pattern=_SAFE_REASON_PATTERN)]

    @field_validator("reason")
    @classmethod
    def require_non_whitespace_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must contain a non-whitespace character")
        if _SECRET_TEXT.search(value) is not None:
            raise ValueError("reason must not contain credential-like material")
        return value


class PlanningRunRetryAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action_version: Literal["planning-run-retry-action.v1"]
    expected_revision: Annotated[int, Field(ge=1)]
    expected_state: Annotated[str, Field(min_length=1, max_length=64)]
    expected_run_fingerprint: Annotated[str, Field(pattern=_FINGERPRINT.pattern)]
    failed_attempt_id: Annotated[str, Field(min_length=1, max_length=256)]
    failed_attempt_number: Annotated[int, Field(ge=1)]
    reason: Annotated[str, Field(pattern=_SAFE_REASON_PATTERN)]

    @field_validator("reason")
    @classmethod
    def require_non_whitespace_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must contain a non-whitespace character")
        if _SECRET_TEXT.search(value) is not None:
            raise ValueError("reason must not contain credential-like material")
        return value


class HeadlessHttpError(Exception):
    """One sanitized public Headless error and its HTTP mapping."""

    def __init__(self, status_code: int, document: JsonObject) -> None:
        self.status_code = status_code
        self.document = document
        super().__init__(cast(str, document["code"]))

    @property
    def headers(self) -> dict[str, str]:
        headers = response_headers(cast(str, self.document["correlation_id"]))
        if self.status_code == 503:
            headers["Retry-After"] = "5"
        return headers


def new_correlation_id() -> str:
    return f"correlation-headless-{uuid4().hex}"


def correlation_id(
    request: Request, document: Mapping[str, object] | None = None
) -> str:
    raw_header = request.headers.get("X-Correlation-Id")
    raw_document = document.get("correlation_id") if document is not None else None
    candidate = raw_header or (raw_document if isinstance(raw_document, str) else None)
    if candidate is None:
        return new_correlation_id()
    if _HTTP_CORRELATION_ID.fullmatch(candidate) is None:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=new_correlation_id(),
            pointer="/correlation_id",
        )
    if (
        raw_header is not None
        and isinstance(raw_document, str)
        and raw_header != raw_document
    ):
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=candidate,
            pointer="/correlation_id",
        )
    return candidate


def response_headers(correlation: str) -> dict[str, str]:
    if _HTTP_CORRELATION_ID.fullmatch(correlation) is None:
        correlation = new_correlation_id()
    return {
        "Cache-Control": "no-store",
        "X-APS-API-Version": HEADLESS_HTTP_VERSION,
        "X-Correlation-Id": correlation,
    }


def headless_error_document(
    code: str,
    *,
    correlation_id: str,
    pointer: str | None = None,
    entity_reference: str | None = None,
) -> JsonObject:
    spec = _ERROR_SPECS.get(code, _ERROR_SPECS["SYSTEM_ERROR"])
    normalized_code = code if code in _ERROR_SPECS else "SYSTEM_ERROR"
    safe_correlation_id = (
        correlation_id
        if _HTTP_CORRELATION_ID.fullmatch(correlation_id) is not None
        else new_correlation_id()
    )
    safe_pointer = (
        pointer
        if isinstance(pointer, str) and _SAFE_POINTER.fullmatch(pointer) is not None
        else None
    )
    safe_entity_reference = (
        entity_reference
        if isinstance(entity_reference, str)
        and _CANONICAL_ID.fullmatch(entity_reference) is not None
        else None
    )
    return {
        "error_version": "headless-error.v1",
        "namespace": "HEADLESS_RUNTIME",
        "registry_version": "headless-error-code-registry.v1",
        "category": spec.category,
        "code": normalized_code,
        "stage": spec.stage,
        "message": spec.message,
        "pointer": safe_pointer,
        "entity_reference": safe_entity_reference,
        "expected_contract": spec.expected_contract,
        "correlation_id": safe_correlation_id,
        "retryability": spec.retryability,
        "action": spec.action,
    }


def public_headless_error(
    code: str,
    *,
    correlation_id: str,
    pointer: str | None = None,
    entity_reference: str | None = None,
    status_code: int | None = None,
) -> HeadlessHttpError:
    normalized = code if code in _ERROR_SPECS else "SYSTEM_ERROR"
    return HeadlessHttpError(
        status_code or _DEFAULT_STATUS[normalized],
        headless_error_document(
            normalized,
            correlation_id=correlation_id,
            pointer=pointer,
            entity_reference=entity_reference,
        ),
    )


def headless_status(code: str) -> int:
    """Return the frozen default HTTP status for one registry code."""

    return _DEFAULT_STATUS.get(code, _DEFAULT_STATUS["SYSTEM_ERROR"])


def from_contract_error(
    error: CanonicalIngressContractError,
    *,
    correlation_id: str,
) -> HeadlessHttpError:
    return public_headless_error(
        error.code.value,
        correlation_id=correlation_id,
        pointer=error.pointer,
    )


def _require_json_media_type(request: Request, correlation: str) -> None:
    content_encoding = request.headers.get("Content-Encoding")
    if content_encoding is not None:
        raise public_headless_error(
            "UNSUPPORTED_MEDIA_TYPE",
            correlation_id=correlation,
            pointer="/headers/Content-Encoding",
        )
    raw_content_type = request.headers.get("Content-Type", "")
    parts = [part.strip() for part in raw_content_type.split(";")]
    if not parts or parts[0].lower() != "application/json":
        raise public_headless_error(
            "UNSUPPORTED_MEDIA_TYPE",
            correlation_id=correlation,
            pointer="/headers/Content-Type",
        )
    parameters = parts[1:]
    if len(parameters) > 1 or (
        parameters and parameters[0].lower().replace(" ", "") != "charset=utf-8"
    ):
        raise public_headless_error(
            "UNSUPPORTED_MEDIA_TYPE",
            correlation_id=correlation,
            pointer="/headers/Content-Type",
        )


async def read_strict_json(
    request: Request,
    *,
    max_bytes: int,
    correlation: str,
) -> tuple[bytes, JsonObject]:
    """Read one bounded, unencoded UTF-8 JSON object without duplicate keys."""

    _require_json_media_type(request, correlation)
    raw_length = request.headers.get("Content-Length")
    if raw_length is not None:
        if not raw_length.isascii() or not raw_length.isdecimal():
            raise public_headless_error(
                "MALFORMED_JSON",
                correlation_id=correlation,
                pointer="/headers/Content-Length",
            )
        if int(raw_length) > max_bytes:
            raise public_headless_error(
                "PAYLOAD_LIMIT_EXCEEDED",
                correlation_id=correlation,
                pointer="/headers/Content-Length",
            )
    received = bytearray()
    try:
        async for chunk in request.stream():
            if len(received) + len(chunk) > max_bytes:
                raise public_headless_error(
                    "PAYLOAD_LIMIT_EXCEEDED",
                    correlation_id=correlation,
                    pointer="/",
                )
            received.extend(chunk)
    except HeadlessHttpError:
        raise
    except Exception:
        raise public_headless_error(
            "MALFORMED_JSON",
            correlation_id=correlation,
            pointer="/",
        ) from None
    raw = bytes(received)
    try:
        return raw, parse_strict_json(raw)
    except CanonicalIngressContractError as error:
        raise from_contract_error(error, correlation_id=correlation) from None


def _json_depth(value: object) -> int:
    maximum = 0
    pending: list[tuple[object, int]] = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        maximum = max(maximum, depth)
        if maximum > MAX_JSON_DEPTH:
            return maximum
        if isinstance(current, Mapping):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
    return maximum


def require_canonical_envelope(
    document: Mapping[str, object], correlation: str
) -> None:
    if _json_depth(document) > MAX_JSON_DEPTH:
        raise public_headless_error(
            "PAYLOAD_LIMIT_EXCEEDED",
            correlation_id=correlation,
            pointer="/",
        )
    payload = document.get("payload")
    records = payload.get("records") if isinstance(payload, Mapping) else None
    if isinstance(records, Mapping):
        count = sum(len(value) for value in records.values() if isinstance(value, list))
        if count > MAX_CANONICAL_RECORDS:
            raise public_headless_error(
                "PAYLOAD_LIMIT_EXCEEDED",
                correlation_id=correlation,
                pointer="/payload/records",
            )


def require_idempotency_key(
    request: Request,
    *,
    correlation: str,
    document: Mapping[str, object] | None = None,
) -> str:
    key = request.headers.get("Idempotency-Key")
    if key is None or _IDEMPOTENCY_KEY.fullmatch(key) is None:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/headers/Idempotency-Key",
        )
    if document is not None and document.get("idempotency_key") != key:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/idempotency_key",
        )
    return key


def require_cancel_action(
    document: Mapping[str, object], correlation: str
) -> PlanningRunCancelAction:
    try:
        return PlanningRunCancelAction.model_validate(document)
    except ValidationError:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/",
        ) from None


def require_retry_action(
    document: Mapping[str, object], correlation: str
) -> PlanningRunRetryAction:
    try:
        return PlanningRunRetryAction.model_validate(document)
    except ValidationError:
        raise public_headless_error(
            "CONTRACT_VIOLATION",
            correlation_id=correlation,
            pointer="/",
        ) from None


__all__ = [
    "HEADLESS_HTTP_VERSION",
    "MAX_ACTION_REQUEST_BYTES",
    "MAX_CANONICAL_RECORDS",
    "MAX_CANONICAL_REQUEST_BYTES",
    "MAX_JSON_DEPTH",
    "HeadlessHttpError",
    "PlanningRunCancelAction",
    "PlanningRunRetryAction",
    "correlation_id",
    "from_contract_error",
    "headless_error_document",
    "headless_status",
    "new_correlation_id",
    "public_headless_error",
    "read_strict_json",
    "require_cancel_action",
    "require_canonical_envelope",
    "require_idempotency_key",
    "require_retry_action",
    "response_headers",
]
