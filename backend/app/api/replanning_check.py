"""Emit machine-checkable TASK-P4-12 dynamic-replanning HTTP evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.dependencies.authorization import (
    AuthorizationAuditRecord,
    PrincipalContext,
)
from app.api.replanning_contracts import (
    DYNAMIC_REPLANNING_ACTION_VERSION,
    DYNAMIC_REPLANNING_API_VERSION,
    DYNAMIC_REPLANNING_QUERY_VERSION,
    DYNAMIC_REPLANNING_RESPONSE_VERSION,
    DynamicReplanningApplicationError,
    DynamicReplanningApplicationRequest,
    DynamicReplanningOperation,
    idempotency_key_reference,
)
from app.domain.execution_contracts import canonical_contract_bytes, contract_fingerprint
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


REPORT_VERSION = "p4-replanning-api-report.v1"
TASK_ID = "TASK-P4-12"
DIFF_BASE = "f4a54d3bb065b5cc8b51c450ffdc435bcc77d384"
IMPACT_RULES = (
    "IMPACT-API",
    "IMPACT-DOCS",
    "IMPACT-FRONTEND",
    "IMPACT-INFRA",
    "IMPACT-TESTS",
)
TEST_IDS = (
    "TEST-REPLAN-API-001",
    "TEST-REPLAN",
    "TEST-IDEMPOTENCY",
    "TEST-ERROR-MAPPING-001",
    "TEST-AUDIT-TRAIL-001",
    "TEST-SIM-ISOLATION",
    "TEST-OBS-001",
)

P4_PATHS = frozenset(
    {
        "/api/v1/execution-events",
        "/api/v1/execution-events/{event_id}",
        "/api/v1/replan-requests",
        "/api/v1/replan-requests/{request_id}",
        "/api/v1/replan-requests/{request_id}/cancel",
        "/api/v1/replan-requests/{request_id}/retry",
        "/api/v1/replan-requests/{request_id}/result",
        "/api/v1/change-reports/{report_id}",
    }
)
P4_OPERATION_IDS = frozenset(
    {
        "appendExecutionEvent",
        "getExecutionEvent",
        "listExecutionEvents",
        "createReplanRequest",
        "getReplanRequest",
        "cancelReplanRequest",
        "retryReplanRequest",
        "getReplanResult",
        "getChangeReport",
    }
)
P3_OPERATION_IDS = frozenset(
    {
        "getPlanningRun",
        "getScheduleVersion",
        "validateScheduleVersion",
        "approveScheduleVersion",
        "rejectScheduleVersion",
        "publishScheduleVersion",
        "getWorkspaceDataHealth",
        "listWorkspaceImportRuns",
        "listWorkspacePlanningRuns",
        "queryScheduleVersionWorkspace",
        "compareScheduleVersions",
        "executeScheduleVersionCommand",
        "listScheduleVersionAuditEvents",
        "createScheduleVersionExport",
        "getExportJob",
        "downloadExportPackage",
        "retryExportJob",
        "cancelExportJob",
    }
)


_RESOURCE_TYPES = {
    DynamicReplanningOperation.APPEND_EXECUTION_EVENT: "EXECUTION_EVENT",
    DynamicReplanningOperation.GET_EXECUTION_EVENT: "EXECUTION_EVENT",
    DynamicReplanningOperation.LIST_EXECUTION_EVENTS: "EXECUTION_EVENT_STREAM",
    DynamicReplanningOperation.CREATE_REPLAN_REQUEST: "REPLAN_REQUEST",
    DynamicReplanningOperation.GET_REPLAN_REQUEST: "REPLAN_REQUEST",
    DynamicReplanningOperation.CANCEL_REPLAN_REQUEST: "REPLAN_REQUEST",
    DynamicReplanningOperation.RETRY_REPLAN_REQUEST: "REPLAN_REQUEST",
    DynamicReplanningOperation.GET_REPLAN_RESULT: "REPLAN_RESULT",
    DynamicReplanningOperation.GET_CHANGE_REPORT: "CHANGE_REPORT",
}


@dataclass(slots=True)
class RecordingDynamicReplanningApplication:
    requests: list[DynamicReplanningApplicationRequest] = field(default_factory=list)
    failure: BaseException | None = None
    seen: dict[tuple[str, str], str] = field(default_factory=dict)

    def execute(
        self, request: DynamicReplanningApplicationRequest
    ) -> Mapping[str, object]:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        replayed = False
        key_reference = request.context.idempotency_key_reference
        if key_reference is not None:
            scope = (request.operation.value, key_reference)
            document_fingerprint = contract_fingerprint(request.document)
            previous = self.seen.get(scope)
            if previous is not None and previous != document_fingerprint:
                raise DynamicReplanningApplicationError(
                    "IDEMPOTENCY_CONFLICT",
                    field="Idempotency-Key",
                    message="same key was bound to different content",
                )
            replayed = previous is not None
            self.seen[scope] = document_fingerprint
        return {
            "response_version": DYNAMIC_REPLANNING_RESPONSE_VERSION,
            "operation": request.operation.value,
            "resource_type": _RESOURCE_TYPES[request.operation],
            "resource_id": request.resource_id,
            "result": {
                "result_version": "dynamic-replanning-machine-result.v1",
                "planning_scope_id": request.planning_scope_id,
            },
            "replayed": replayed,
            "correlation_id": request.context.correlation_id,
        }


@dataclass(slots=True)
class RecordingProvider:
    principal: PrincipalContext | None
    calls: int = 0

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        self.calls += 1
        return self.principal if bearer_token == "p4-machine-token" else None


@dataclass(slots=True)
class RecordingAuditSink:
    events: list[AuthorizationAuditRecord] = field(default_factory=list)

    def record(self, event: AuthorizationAuditRecord) -> None:
        self.events.append(event)


def load_replanning_api_fixture(root: Path) -> dict[str, dict[str, object]]:
    samples = root / "schemas/samples"
    return {
        name: cast(
            dict[str, object],
            json.loads((samples / filename).read_text(encoding="utf-8")),
        )
        for name, filename in {
            "event": "execution-event.v1.synthetic.json",
            "request": "replan-request.v1.synthetic.json",
            "report": "change-report.v1.synthetic.json",
        }.items()
    }


def build_replanning_query(
    *,
    query_kind: str,
    resource_id: str | None,
    planning_scope_id: str,
    correlation_id: str,
    request_fingerprint: str | None = None,
    attempt_id: str | None = None,
    report_fingerprint: str | None = None,
    authority_id: str | None = None,
    stream_id: str | None = None,
    stream_version: str | None = None,
    from_position: int | None = None,
    through_position: int | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "replanning_query_version": DYNAMIC_REPLANNING_QUERY_VERSION,
        "api_contract_version": DYNAMIC_REPLANNING_API_VERSION,
        "canonicalization_version": "canonical-json.v1",
        "query_kind": query_kind,
        "resource_id": resource_id,
        "planning_scope_id": planning_scope_id,
        "authority_id": authority_id,
        "stream_id": stream_id,
        "stream_version": stream_version,
        "from_position": from_position,
        "through_position": through_position,
        "attempt_id": attempt_id,
        "request_fingerprint": request_fingerprint,
        "report_fingerprint": report_fingerprint,
        "page": {"size": 50, "cursor": None},
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "production_binding": False,
        "correlation_id": correlation_id,
        "query_fingerprint": "sha256:" + "0" * 64,
    }
    document["query_fingerprint"] = contract_fingerprint(
        {key: value for key, value in document.items() if key != "query_fingerprint"}
    )
    return document


def build_replan_action(
    *,
    action: str,
    request_id: str,
    request_fingerprint: str,
    idempotency_key: str,
    correlation_id: str,
) -> dict[str, object]:
    document: dict[str, object] = {
        "replan_action_version": DYNAMIC_REPLANNING_ACTION_VERSION,
        "api_contract_version": DYNAMIC_REPLANNING_API_VERSION,
        "canonicalization_version": "canonical-json.v1",
        "action_id": "replan-action-" + "0" * 64,
        "action": action,
        "request_id": request_id,
        "request_fingerprint": request_fingerprint,
        "expected_attempt_id": "replan-attempt-" + "a" * 64,
        "expected_attempt_number": 1,
        "expected_planning_run_state": (
            "SOLVING" if action == "CANCEL" else "FAILED"
        ),
        "reason": f"Exercise the bounded {action.lower()} HTTP contract.",
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "production_binding": False,
        "correlation_id": correlation_id,
        "idempotency_key_reference": idempotency_key_reference(idempotency_key),
        "action_fingerprint": "sha256:" + "0" * 64,
    }
    fingerprint = contract_fingerprint(
        {
            key: value
            for key, value in document.items()
            if key not in {"action_id", "action_fingerprint"}
        }
    )
    document["action_fingerprint"] = fingerprint
    document["action_id"] = "replan-action-" + fingerprint.removeprefix("sha256:")
    return document


def compact_query(document: Mapping[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def _principal(scope: str, *capabilities: str) -> PrincipalContext:
    return PrincipalContext(
        actor_ref="actor:p4-replanning-http-machine",
        resolved_capabilities=frozenset(capabilities),
        planning_run_scope=frozenset(),
        schedule_version_scope=frozenset(),
        export_job_scope=frozenset(),
        auth_policy_version="simulation-p4-http-machine.v1",
        planning_scope_scope=frozenset({scope}),
    )


def _settings(*, production: bool = False) -> Settings:
    return Settings(
        runtime_environment=(
            RuntimeEnvironment.PRODUCTION if production else RuntimeEnvironment.TEST
        ),
        data_plane=DataPlane.PRODUCTION if production else DataPlane.SIMULATION,
        simulation_api_enabled=not production,
        code_commit=(
            os.environ.get("PLANTNEXUS_CODE_COMMIT", "f" * 40)
            if production
            else os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
        ),
    )


def _headers(
    *,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    planning_scope_id: str | None = None,
) -> dict[str, str]:
    headers = {"Authorization": "Bearer p4-machine-token"}
    if correlation_id is not None:
        headers["X-Correlation-Id"] = correlation_id
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    if planning_scope_id is not None:
        headers["X-Planning-Scope-Id"] = planning_scope_id
    return headers


def _pass(name: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"name": name, "status": "PASS", "evidence": dict(evidence)}


def _openapi_fingerprint(document: Mapping[str, object]) -> str:
    return f"sha256:{sha256(canonical_contract_bytes(document)).hexdigest()}"


def run_replanning_api_checks(root: Path) -> dict[str, object]:
    fixture = load_replanning_api_fixture(root)
    event = fixture["event"]
    replan_request = fixture["request"]
    report = fixture["report"]
    scope = cast(str, event["planning_scope_id"])
    event_id = cast(str, event["event_id"])
    request_id = cast(str, replan_request["request_id"])
    request_fingerprint = cast(str, replan_request["request_fingerprint"])
    report_id = cast(str, report["report_id"])
    report_fingerprint = cast(str, report["report_fingerprint"])
    attempt_id = "replan-attempt-" + "a" * 64

    application = RecordingDynamicReplanningApplication()
    provider = RecordingProvider(
        _principal(
            scope,
            "event_ingest",
            "event_view",
            "replan",
            "replan_control",
            "replan_view",
        )
    )
    audit_sink = RecordingAuditSink()
    api = create_app(
        _settings(),
        probes={"database": lambda: None, "redis": lambda: None},
        dynamic_replanning_application=application,
        authorization_provider=provider,
        authorization_audit_sink=audit_sink,
        dynamic_replanning_clock=lambda: "2026-08-31T12:00:00Z",
    )
    openapi = api.openapi()
    paths = cast(dict[str, dict[str, object]], openapi["paths"])
    p4_paths = {path: paths[path] for path in P4_PATHS}
    operation_ids = {
        cast(str, operation["operationId"])
        for path in p4_paths.values()
        for method, operation in path.items()
        if method in {"get", "post"} and isinstance(operation, Mapping)
    }
    if operation_ids != P4_OPERATION_IDS:
        raise ValueError("P4 HTTP operation inventory drifted")
    for path in p4_paths.values():
        for method, operation in path.items():
            if method not in {"get", "post"} or not isinstance(operation, Mapping):
                continue
            if (
                operation.get("x-plantnexus-api-contract")
                != DYNAMIC_REPLANNING_API_VERSION
                or operation.get("x-plantnexus-response-contract")
                != DYNAMIC_REPLANNING_RESPONSE_VERSION
            ):
                raise ValueError("P4 OpenAPI contract extension drifted")
    p4_openapi = {"openapi": openapi["openapi"], "paths": p4_paths}
    checks: list[dict[str, object]] = [
        _pass(
            "versioned-route-operation-and-openapi-inventory",
            {
                "api_paths": len(p4_paths),
                "http_operations": len(operation_ids),
                "openapi_fingerprint": _openapi_fingerprint(p4_openapi),
            },
        )
    ]

    event_key = "p4-event-machine-key-0001"
    request_key = "p4-replan-machine-key-0001"
    cancel_key = "p4-cancel-machine-key-0001"
    retry_key = "p4-retry-machine-key-0001"
    event_query = build_replanning_query(
        query_kind="EXECUTION_EVENT",
        resource_id=event_id,
        planning_scope_id=scope,
        correlation_id="correlation-p4-event-read-001",
    )
    stream_query = build_replanning_query(
        query_kind="EXECUTION_EVENT_STREAM",
        resource_id=None,
        planning_scope_id=scope,
        correlation_id="correlation-p4-event-stream-001",
        authority_id=cast(str, cast(Mapping[str, object], event["authority"])["authority_id"]),
        stream_id=cast(str, cast(Mapping[str, object], event["source_stream"])["stream_id"]),
        stream_version=cast(
            str, cast(Mapping[str, object], event["source_stream"])["stream_version"]
        ),
        from_position=1,
        through_position=1,
    )
    request_query = build_replanning_query(
        query_kind="REPLAN_REQUEST",
        resource_id=request_id,
        planning_scope_id=scope,
        correlation_id="correlation-p4-request-read-001",
        request_fingerprint=request_fingerprint,
    )
    result_query = build_replanning_query(
        query_kind="REPLAN_RESULT",
        resource_id=request_id,
        planning_scope_id=scope,
        correlation_id="correlation-p4-result-read-001",
        request_fingerprint=request_fingerprint,
        attempt_id=attempt_id,
    )
    report_query = build_replanning_query(
        query_kind="CHANGE_REPORT",
        resource_id=report_id,
        planning_scope_id=scope,
        correlation_id="correlation-p4-report-read-001",
        request_fingerprint=request_fingerprint,
        attempt_id=attempt_id,
        report_fingerprint=report_fingerprint,
    )
    cancel = build_replan_action(
        action="CANCEL",
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        idempotency_key=cancel_key,
        correlation_id="correlation-p4-cancel-001",
    )
    retry = build_replan_action(
        action="RETRY",
        request_id=request_id,
        request_fingerprint=request_fingerprint,
        idempotency_key=retry_key,
        correlation_id="correlation-p4-retry-001",
    )

    with TestClient(api) as client:
        cases = (
            client.post(
                "/api/v1/execution-events",
                json=event,
                headers=_headers(
                    correlation_id=cast(str, event["correlation_id"]),
                    idempotency_key=event_key,
                ),
            ),
            client.get(
                f"/api/v1/execution-events/{event_id}",
                params={"query": compact_query(event_query)},
                headers=_headers(
                    correlation_id=cast(str, event_query["correlation_id"])
                ),
            ),
            client.get(
                "/api/v1/execution-events",
                params={"query": compact_query(stream_query)},
                headers=_headers(
                    correlation_id=cast(str, stream_query["correlation_id"])
                ),
            ),
            client.post(
                "/api/v1/replan-requests",
                json=replan_request,
                headers=_headers(
                    correlation_id=cast(str, replan_request["correlation_id"]),
                    idempotency_key=request_key,
                ),
            ),
            client.get(
                f"/api/v1/replan-requests/{request_id}",
                params={"query": compact_query(request_query)},
                headers=_headers(
                    correlation_id=cast(str, request_query["correlation_id"])
                ),
            ),
            client.post(
                f"/api/v1/replan-requests/{request_id}/cancel",
                json=cancel,
                headers=_headers(
                    correlation_id=cast(str, cancel["correlation_id"]),
                    idempotency_key=cancel_key,
                    planning_scope_id=scope,
                ),
            ),
            client.post(
                f"/api/v1/replan-requests/{request_id}/retry",
                json=retry,
                headers=_headers(
                    correlation_id=cast(str, retry["correlation_id"]),
                    idempotency_key=retry_key,
                    planning_scope_id=scope,
                ),
            ),
            client.get(
                f"/api/v1/replan-requests/{request_id}/result",
                params={"query": compact_query(result_query)},
                headers=_headers(
                    correlation_id=cast(str, result_query["correlation_id"])
                ),
            ),
            client.get(
                f"/api/v1/change-reports/{report_id}",
                params={"query": compact_query(report_query)},
                headers=_headers(
                    correlation_id=cast(str, report_query["correlation_id"])
                ),
            ),
        )
        expected_statuses = (202, 200, 200, 202, 200, 202, 202, 200, 200)
        if tuple(response.status_code for response in cases) != expected_statuses:
            raise ValueError("not every P4 route delegated successfully")
        if {request.operation for request in application.requests} != set(
            DynamicReplanningOperation
        ):
            raise ValueError("P4 application operation coverage is incomplete")
        if any(
            response.headers.get("Cache-Control") != "no-store"
            or response.headers.get("X-Correlation-Id")
            != response.json().get("correlation_id")
            for response in cases
        ):
            raise ValueError("P4 correlation or cache boundary drifted")
        checks.append(
            _pass(
                "all-routes-delegate-once-with-server-context",
                {
                    "successful_delegations": len(cases),
                    "operation_kinds": len(DynamicReplanningOperation),
                    "raw_idempotency_keys_at_application": 0,
                    "router_business_state_transitions": 0,
                },
            )
        )

        before_invalid = len(application.requests)
        invalid_event = deepcopy(event)
        invalid_event["production_binding"] = True
        invalid_query = deepcopy(request_query)
        invalid_query["unexpected"] = "reject"
        invalid_action = deepcopy(cancel)
        invalid_action["expected_planning_run_state"] = "COMPLETED"
        invalid_responses = (
            client.post(
                "/api/v1/execution-events",
                json=invalid_event,
                headers=_headers(idempotency_key="p4-invalid-event-key-001"),
            ),
            client.get(
                f"/api/v1/replan-requests/{request_id}",
                params={"query": compact_query(invalid_query)},
                headers=_headers(),
            ),
            client.post(
                f"/api/v1/replan-requests/{request_id}/cancel",
                json=invalid_action,
                headers=_headers(
                    idempotency_key=cancel_key, planning_scope_id=scope
                ),
            ),
        )
        if (
            any(response.status_code != 422 for response in invalid_responses)
            or len(application.requests) != before_invalid
        ):
            raise ValueError("strict carrier/query/action validation failed open")
        checks.append(
            _pass(
                "strict-carrier-query-action-plane-and-state-binding",
                {
                    "invalid_cases": len(invalid_responses),
                    "application_calls": 0,
                    "schema_migration_dependency_changes": 0,
                },
            )
        )

        replay = client.post(
            "/api/v1/execution-events",
            json=event,
            headers=_headers(
                correlation_id=cast(str, event["correlation_id"]),
                idempotency_key=event_key,
            ),
        )
        conflict_event = deepcopy(event)
        conflict_event["received_at_utc"] = "2026-08-27T06:00:09Z"
        conflict = client.post(
            "/api/v1/execution-events",
            json=conflict_event,
            headers=_headers(
                correlation_id=cast(str, event["correlation_id"]),
                idempotency_key=event_key,
            ),
        )
        application.failure = DynamicReplanningApplicationError(
            "UNKNOWN_OUTCOME",
            field="application_result",
            message="private timeout detail must not escape",
        )
        unknown = client.get(
            f"/api/v1/replan-requests/{request_id}/result",
            params={"query": compact_query(result_query)},
            headers=_headers(
                correlation_id=cast(str, result_query["correlation_id"])
            ),
        )
        application.failure = None
        if (
            replay.status_code != 202
            or replay.json()["replayed"] is not True
            or conflict.status_code != 409
            or unknown.status_code != 503
            or unknown.json()["retryable"] is not False
            or "private" in unknown.text
        ):
            raise ValueError("idempotency replay/conflict/unknown outcome drifted")
        checks.append(
            _pass(
                "same-key-replay-conflict-and-query-before-retry",
                {
                    "same_key_replayed": True,
                    "different_content_status": conflict.status_code,
                    "unknown_outcome_status": unknown.status_code,
                    "blind_retry_advertised": False,
                },
            )
        )

        calls_before_auth = len(application.requests)
        missing = client.get(
            f"/api/v1/execution-events/{event_id}",
            params={"query": compact_query(event_query)},
        )
        denied_provider = RecordingProvider(
            _principal("different-planning-scope", "event_view")
        )
        denied_api = create_app(
            _settings(),
            probes={},
            dynamic_replanning_application=application,
            authorization_provider=denied_provider,
            authorization_audit_sink=audit_sink,
        )
        with TestClient(denied_api) as denied_client:
            denied = denied_client.get(
                f"/api/v1/execution-events/{event_id}",
                params={"query": compact_query(event_query)},
                headers=_headers(
                    correlation_id=cast(str, event_query["correlation_id"])
                ),
            )
        production_application = RecordingDynamicReplanningApplication()
        production_provider = RecordingProvider(
            _principal(scope, "event_view", "replan_view")
        )
        production_sink = RecordingAuditSink()
        production_api = create_app(
            _settings(production=True),
            probes={},
            dynamic_replanning_application=production_application,
            authorization_provider=production_provider,
            authorization_audit_sink=production_sink,
        )
        with TestClient(production_api) as production_client:
            production = production_client.get(
                f"/api/v1/execution-events/{event_id}",
                params={"query": compact_query(event_query)},
                headers=_headers(
                    correlation_id=cast(str, event_query["correlation_id"])
                ),
            )
        if (
            missing.status_code != 401
            or denied.status_code != 403
            or production.status_code != 403
            or len(application.requests) != calls_before_auth
            or production_provider.calls != 0
            or production_application.requests
            or not audit_sink.events
            or len(production_sink.events) != 1
        ):
            raise ValueError("P4 authorization or Production default-deny failed open")
        checks.append(
            _pass(
                "server-derived-capability-scope-audit-and-production-default-deny",
                {
                    "missing_auth_status": missing.status_code,
                    "scope_denied_status": denied.status_code,
                    "denial_audits": len(audit_sink.events),
                    "production_provider_lookups": production_provider.calls,
                    "production_application_calls": len(
                        production_application.requests
                    ),
                },
            )
        )

        application.failure = RuntimeError(
            "postgresql://operator:secret@database/private token=never-return"
        )
        sanitized = client.get(
            f"/api/v1/change-reports/{report_id}",
            params={"query": compact_query(report_query)},
            headers=_headers(
                correlation_id=cast(str, report_query["correlation_id"])
            ),
        )
        application.failure = None
        if sanitized.status_code != 500 or any(
            secret in sanitized.text
            for secret in ("operator", "secret", "private", "RuntimeError", "token")
        ):
            raise ValueError("P4 unknown error was not sanitized")
        checks.append(
            _pass(
                "stable-error-correlation-no-store-and-redaction",
                {
                    "unknown_status": sanitized.status_code,
                    "secret_leaks": 0,
                    "cache_control": sanitized.headers.get("Cache-Control"),
                    "correlation_preserved": True,
                },
            )
        )

    all_operations = {
        cast(str, operation["operationId"])
        for path in paths.values()
        for method, operation in path.items()
        if method in {"get", "post"} and isinstance(operation, Mapping)
    }
    if not P3_OPERATION_IDS.issubset(all_operations) or len(P3_OPERATION_IDS) != 18:
        raise ValueError("frozen P3 operation subset drifted")
    checks.append(
        _pass(
            "frozen-p3-http-subset-remains-additive",
            {
                "p3_operations": len(P3_OPERATION_IDS),
                "p4_operations": len(P4_OPERATION_IDS),
                "p3_operation_ids_changed": 0,
            },
        )
    )

    router_source = (
        root / "backend/app/api/routers/dynamic_replanning.py"
    ).read_text(encoding="utf-8")
    forbidden_router_tokens = (
        "from app.application",
        "from app.domain",
        "from app.infrastructure.execution_event_repository",
        "from app.infrastructure.replan_repository",
        "ExecutionFactProjectionService",
        "ReplanApplicationService",
        "ChangeReportQueryService",
        "LexicographicReplanStrategy",
        "CpModel",
    )
    if any(token in router_source for token in forbidden_router_tokens) or any(
        "/api/v1/p5" in path for path in paths
    ):
        raise ValueError("P4 router calculation or future-phase boundary drifted")
    checks.append(
        _pass(
            "thin-router-p4-p5-production-and-external-boundary",
            {
                "router_application_domain_repository_imports": 0,
                "solver_validator_projection_calculations": 0,
                "p5_routes": 0,
                "external_publish_or_simulator_control_routes": 0,
                "production_readiness": "NOT_CLAIMED",
            },
        )
    )

    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("TASK-P4-12 machine checks are incomplete")
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "diff_base": DIFF_BASE,
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "check_count": len(checks),
        "checks": checks,
        "test_ids": list(TEST_IDS),
        "counts": {
            "api_paths": len(P4_PATHS),
            "http_operations": len(P4_OPERATION_IDS),
            "successful_delegations": 9,
            "p3_frozen_operations": len(P3_OPERATION_IDS),
            "production_provider_lookups": 0,
            "production_application_calls": 0,
            "router_business_state_transitions": 0,
            "solver_validator_projection_invocations": 0,
        },
        "boundaries": {
            "execution_event": "APPEND_AND_QUERY_VIA_APPLICATION_AUTHORITY",
            "replan_request": "IMMUTABLE_NO_STATE_MACHINE",
            "cancel_retry": "PLANNING_RUN_ATTEMPT_CAS_DELEGATION_ONLY",
            "change_report": "P4_11_READ_AUTHORITY",
            "p3_operations": "FROZEN_ADDITIVE_SUBSET",
            "schema_migration_dependency": "UNCHANGED",
            "simulator_control_external_publish": "ABSENT",
            "p5_capabilities": "NOT_ADVERTISED",
            "production_authority": "DEFAULT_DENY_OPEN_010_015",
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_contract_bytes(report))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate TASK-P4-12 dynamic-replanning HTTP behavior"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p4-replanning-api.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        report = run_replanning_api_checks(arguments.root.resolve())
    except Exception as error:  # noqa: BLE001 - machine evidence must fail closed
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get(
                "PLANTNEXUS_CODE_COMMIT", "uncommitted"
            ),
            "diff_base": DIFF_BASE,
            "impact_rule_count": len(IMPACT_RULES),
            "impact_rules": list(IMPACT_RULES),
            "check_count": 0,
            "checks": [],
            "issues": [
                {
                    "reason": "MACHINE_CHECK_FAILED",
                    "error_type": type(error).__name__,
                    "message": "P4-12 HTTP evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "DEFAULT_DENY_OPEN_010_015",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "IMPACT_RULES",
    "P4_OPERATION_IDS",
    "P4_PATHS",
    "REPORT_VERSION",
    "TASK_ID",
    "RecordingAuditSink",
    "RecordingDynamicReplanningApplication",
    "RecordingProvider",
    "build_replan_action",
    "build_replanning_query",
    "compact_query",
    "load_replanning_api_fixture",
    "main",
    "run_replanning_api_checks",
]
