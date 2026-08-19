"""Structured application logging, correlation context, and redaction."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any, TextIO

import structlog
from opentelemetry import trace
from pydantic import SecretStr
from structlog.typing import EventDict, WrappedLogger

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "databaseurl",
    "apikey",
    "password",
    "redisurl",
    "secret",
    "token",
)
_URL_CREDENTIAL = re.compile(
    r"([A-Za-z][A-Za-z0-9+.-]*://)([^/@:\s]+):([^/@\s]+)@"
)
_INLINE_SECRET = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)\s*[:=]\s*([^,;\s]+)"
)


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _sanitize_string(value: str) -> str:
    without_url_credentials = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", value)
    return _INLINE_SECRET.sub(r"\1=[REDACTED]", without_url_credentials)


def _redact_value(value: object) -> object:
    if isinstance(value, SecretStr):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(key) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    """Return a recursively redacted copy of a logging payload."""

    redacted = _redact_value(values)
    if not isinstance(redacted, dict):  # defensive: the public input is a mapping
        raise TypeError("redaction result must remain a mapping")
    return redacted


def add_otel_trace_context(
    _: WrappedLogger,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    """Add current OpenTelemetry IDs when a valid span is already active."""

    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict.setdefault("trace_id", f"{span_context.trace_id:032x}")
        event_dict.setdefault("span_id", f"{span_context.span_id:016x}")
    return event_dict


def redact_event(
    _: WrappedLogger,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    return redact_mapping(event_dict)


def configure_logging(
    log_level: str = "INFO",
    stream: TextIO | None = None,
    *,
    include_otel_context: bool = True,
) -> None:
    """Configure deterministic JSON application logs.

    Third-party server/worker log routing remains an adapter concern; all
    PlantNexus loggers obtained through :func:`get_logger` use this pipeline.
    """

    level = getattr(logging, log_level.upper(), logging.INFO)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if include_otel_context:
        processors.append(add_otel_trace_context)
    processors.extend(
        [
            redact_event,
            structlog.processors.JSONRenderer(sort_keys=True),
        ]
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=False,
    )


def bind_log_context(
    *,
    correlation_id: str,
    run_id: str | None = None,
    job_id: str | None = None,
) -> None:
    if not correlation_id:
        raise ValueError("correlation_id must not be empty")
    values: dict[str, str] = {"correlation_id": correlation_id}
    if run_id is not None:
        values["run_id"] = run_id
    if job_id is not None:
        values["job_id"] = job_id
    structlog.contextvars.bind_contextvars(**values)


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)


__all__ = [
    "add_otel_trace_context",
    "bind_log_context",
    "clear_log_context",
    "configure_logging",
    "get_logger",
    "redact_event",
    "redact_mapping",
]
