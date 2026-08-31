"""TASK-P4-12 HTTP-only carrier and response contract tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.api.replanning_check import (
    build_replan_action,
    build_replanning_query,
    load_replanning_api_fixture,
)
from app.api.replanning_contracts import (
    DynamicReplanningApplicationError,
    DynamicReplanningOperation,
    idempotency_key_reference,
    require_execution_event,
    require_replan_action,
    require_replan_request,
    require_replanning_query,
    validate_response_envelope,
)


ROOT = Path(__file__).resolve().parents[3]


def test_p4_domain_carriers_are_consumed_without_a_second_schema() -> None:
    fixture = load_replanning_api_fixture(ROOT)
    event = require_execution_event(fixture["event"])
    request = require_replan_request(fixture["request"])

    assert event["execution_event_version"] == "execution-event.v1"
    assert request["replan_request_version"] == "replan-request.v1"

    with pytest.raises(DynamicReplanningApplicationError):
        require_execution_event(request)
    with pytest.raises(DynamicReplanningApplicationError):
        require_replan_request(event)


def test_replanning_query_is_exact_fingerprinted_and_route_bound() -> None:
    fixture = load_replanning_api_fixture(ROOT)
    event = fixture["event"]
    event_id = str(event["event_id"])
    query = build_replanning_query(
        query_kind="EXECUTION_EVENT",
        resource_id=event_id,
        planning_scope_id=str(event["planning_scope_id"]),
        correlation_id="correlation-p4-unit-query-001",
    )

    assert require_replanning_query(
        query, query_kind="EXECUTION_EVENT", resource_id=event_id
    ) == query

    unknown = deepcopy(query)
    unknown["unknown"] = True
    with pytest.raises(DynamicReplanningApplicationError):
        require_replanning_query(
            unknown, query_kind="EXECUTION_EVENT", resource_id=event_id
        )
    with pytest.raises(DynamicReplanningApplicationError):
        require_replanning_query(
            query, query_kind="REPLAN_REQUEST", resource_id=event_id
        )


def test_stream_query_requires_ordered_authority_window() -> None:
    fixture = load_replanning_api_fixture(ROOT)
    event = fixture["event"]
    authority = event["authority"]
    stream = event["source_stream"]
    assert isinstance(authority, dict)
    assert isinstance(stream, dict)
    query = build_replanning_query(
        query_kind="EXECUTION_EVENT_STREAM",
        resource_id=None,
        planning_scope_id=str(event["planning_scope_id"]),
        correlation_id="correlation-p4-unit-stream-001",
        authority_id=str(authority["authority_id"]),
        stream_id=str(stream["stream_id"]),
        stream_version=str(stream["stream_version"]),
        from_position=1,
        through_position=2,
    )
    assert require_replanning_query(
        query, query_kind="EXECUTION_EVENT_STREAM", resource_id=None
    ) == query

    reversed_window = deepcopy(query)
    reversed_window["from_position"] = 3
    with pytest.raises(DynamicReplanningApplicationError):
        require_replanning_query(
            reversed_window,
            query_kind="EXECUTION_EVENT_STREAM",
            resource_id=None,
        )


def test_cancel_retry_bind_attempt_state_and_hashed_idempotency() -> None:
    fixture = load_replanning_api_fixture(ROOT)
    request = fixture["request"]
    request_id = str(request["request_id"])
    request_fingerprint = str(request["request_fingerprint"])
    key = "p4-unit-cancel-key-0001"
    action = build_replan_action(
        action="CANCEL",
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        idempotency_key=key,
        correlation_id="correlation-p4-unit-cancel-001",
    )

    assert require_replan_action(
        action,
        action="CANCEL",
        request_id=request_id,
        key_reference=idempotency_key_reference(key),
    ) == action

    invalid_state = deepcopy(action)
    invalid_state["expected_planning_run_state"] = "COMPLETED"
    with pytest.raises(DynamicReplanningApplicationError):
        require_replan_action(
            invalid_state,
            action="CANCEL",
            request_id=request_id,
            key_reference=idempotency_key_reference(key),
        )
    with pytest.raises(DynamicReplanningApplicationError):
        require_replan_action(
            action,
            action="CANCEL",
            request_id=request_id,
            key_reference=idempotency_key_reference("different-key-value-0001"),
        )
    sensitive = deepcopy(action)
    sensitive["reason"] = "Bearer private-token-must-not-propagate"
    with pytest.raises(DynamicReplanningApplicationError):
        require_replan_action(
            sensitive,
            action="CANCEL",
            request_id=request_id,
            key_reference=idempotency_key_reference(key),
        )


def test_response_envelope_cannot_change_operation_resource_or_correlation() -> None:
    event_id = "execution-event-" + "a" * 64
    envelope: dict[str, object] = {
        "response_version": "dynamic-replanning-response.v1",
        "operation": "GET_EXECUTION_EVENT",
        "resource_type": "EXECUTION_EVENT",
        "resource_id": event_id,
        "result": {"execution_event_version": "execution-event.v1"},
        "replayed": False,
        "correlation_id": "correlation-p4-response-001",
    }
    assert validate_response_envelope(
        envelope,
        operation=DynamicReplanningOperation.GET_EXECUTION_EVENT,
        resource_type="EXECUTION_EVENT",
        resource_id=event_id,
        correlation_id="correlation-p4-response-001",
    ) == envelope

    mismatched = deepcopy(envelope)
    mismatched["operation"] = "GET_CHANGE_REPORT"
    with pytest.raises(DynamicReplanningApplicationError):
        validate_response_envelope(
            mismatched,
            operation=DynamicReplanningOperation.GET_EXECUTION_EVENT,
            resource_type="EXECUTION_EVENT",
            resource_id=event_id,
            correlation_id="correlation-p4-response-001",
        )
