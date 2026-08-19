"""TEST-OBS-001 P0 structured logging and redaction evidence."""

from __future__ import annotations

import json
from io import StringIO

from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
    use_span,
)

from app.infrastructure.logging import (
    bind_log_context,
    clear_log_context,
    configure_logging,
    get_logger,
    redact_mapping,
)


def test_json_log_contains_context_and_recursively_redacts_secrets() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)
    clear_log_context()
    bind_log_context(
        correlation_id="corr-001",
        run_id="run-001",
        job_id="job-001",
    )
    try:
        get_logger("integration").info(
            "dependency_probe",
            database_url="postgresql://operator:do-not-leak@database/db",
            nested={
                "api_token": "do-not-leak",
                "message": "password=do-not-leak",
            },
        )
    finally:
        clear_log_context()

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "dependency_probe"
    assert payload["level"] == "info"
    assert payload["correlation_id"] == "corr-001"
    assert payload["run_id"] == "run-001"
    assert payload["job_id"] == "job-001"
    assert payload["database_url"] == "[REDACTED]"
    assert payload["nested"]["api_token"] == "[REDACTED]"
    assert payload["nested"]["message"] == "password=[REDACTED]"
    assert "do-not-leak" not in stream.getvalue()


def test_active_opentelemetry_context_is_added_without_exporter() -> None:
    stream = StringIO()
    configure_logging("INFO", stream)
    span_context = SpanContext(
        trace_id=int("1" * 32, 16),
        span_id=int("2" * 16, 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    with use_span(NonRecordingSpan(span_context), end_on_exit=False):
        get_logger("integration").info("trace_link")

    payload = json.loads(stream.getvalue())
    assert payload["trace_id"] == "1" * 32
    assert payload["span_id"] == "2" * 16


def test_opentelemetry_context_can_be_disabled_by_configuration() -> None:
    stream = StringIO()
    configure_logging("INFO", stream, include_otel_context=False)
    span_context = SpanContext(
        trace_id=int("3" * 32, 16),
        span_id=int("4" * 16, 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    with use_span(NonRecordingSpan(span_context), end_on_exit=False):
        get_logger("integration").info("trace_disabled")

    payload = json.loads(stream.getvalue())
    assert "trace_id" not in payload
    assert "span_id" not in payload


def test_redaction_handles_credentials_in_free_text_and_collections() -> None:
    redacted = redact_mapping(
        {
            "message": "connect redis://user:do-not-leak@redis/0 token=do-not-leak",
            "items": [{"authorization": "Bearer do-not-leak"}],
        }
    )
    serialized = json.dumps(redacted)
    assert "do-not-leak" not in serialized
    assert "redis://[REDACTED]@redis/0" in serialized
    assert redacted["items"] == [{"authorization": "[REDACTED]"}]
