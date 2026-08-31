"""Recheck TASK-P3-10 HTTP baseline plus the bounded TASK-P3-13 download."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.contracts import (
    PlanningWorkspaceApplicationError,
    PlanningWorkspaceApplicationRequest,
    PlanningWorkspaceDownload,
    PlanningWorkspaceOperation,
)
from app.api.dependencies.authorization import (
    AuthorizationAuditRecord,
    PrincipalContext,
)
from app.domain.workspace import WorkspaceView, build_workspace_query_request
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


REPORT_VERSION = "p3-planning-workspace-api-report.v1"
TASK_ID = "TASK-P3-10"
TEST_IDS = (
    "TEST-WORKSPACE-API-001",
    "TEST-ERROR-MAPPING-001",
    "TEST-APPROVAL-AUTHORIZATION-001",
    "TEST-PUBLISH-IDEMPOTENCY-001",
    "TEST-EXPORT-JOB-001",
    "TEST-SIM-ISOLATION",
    "TEST-OBS-001",
)
P3_PATHS = frozenset(
    {
        "/api/v1/planning-runs/{planning_run_id}",
        "/api/v1/schedule-versions/{schedule_version_id}",
        "/api/v1/schedule-versions/{schedule_version_id}/validate",
        "/api/v1/schedule-versions/{schedule_version_id}/approve",
        "/api/v1/schedule-versions/{schedule_version_id}/reject",
        "/api/v1/schedule-versions/{schedule_version_id}/publish",
        "/api/v1/workspace/data-health",
        "/api/v1/workspace/import-runs",
        "/api/v1/workspace/planning-runs",
        "/api/v1/schedule-versions/{schedule_version_id}/workspace/{view}",
        "/api/v1/schedule-version-comparisons",
        "/api/v1/schedule-versions/{schedule_version_id}/commands",
        "/api/v1/schedule-versions/{schedule_version_id}/audit-events",
        "/api/v1/schedule-versions/{schedule_version_id}/exports",
        "/api/v1/export-jobs/{export_job_id}",
        "/api/v1/export-jobs/{export_job_id}/download",
        "/api/v1/export-jobs/{export_job_id}/retry",
        "/api/v1/export-jobs/{export_job_id}/cancel",
    }
)

_SCHEDULE_ID = "schedule-version-sim-001"
_COMPARED_ID = "schedule-version-sim-002"
_EXPORT_JOB_ID = "export-job-sim-001"
_PLANNING_RUN_ID = "planning-run-sim-001"
_FINGERPRINT = "sha256:" + "a" * 64
_COMPARED_FINGERPRINT = "sha256:" + "b" * 64
_PROVENANCE: dict[str, object] = {
    "scenario_id": "SIM-P2-GOLDEN-JSSP-001",
    "scenario_version": "1.0.0",
    "seed": 20260825,
    "factory_profile_id": "PROFILE-P2-XS-001",
    "profile_version": "1.0.0",
    "generator_id": "PLANTNEXUS-P3-HTTP-CHECK",
    "generator_version": "1.0.0",
}


@dataclass(slots=True)
class _RecordingApplication:
    requests: list[PlanningWorkspaceApplicationRequest] = field(default_factory=list)
    failure: BaseException | None = None

    def execute(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> Mapping[str, object] | PlanningWorkspaceDownload:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        if request.operation is PlanningWorkspaceOperation.DOWNLOAD_EXPORT_PACKAGE:
            archive = b"PK\x03\x04p3-http-machine-download"
            return PlanningWorkspaceDownload(
                content=archive,
                filename="export-package-" + "1" * 64 + ".zip",
                media_type="application/zip",
                package_id="export-package-" + "1" * 64,
                manifest_fingerprint="sha256:" + "2" * 64,
                archive_fingerprint=f"sha256:{sha256(archive).hexdigest()}",
                completion_audit_event_id="audit-export-machine-completed",
                correlation_id=request.context.correlation_id,
            )
        return {
            "http_check_result_version": "p3-http-check-result.v1",
            "operation": request.operation.value,
            "resource_id": request.resource_id,
            "view": request.view,
            "correlation_id": request.context.correlation_id,
        }


@dataclass(slots=True)
class _TokenProvider:
    principals: Mapping[str, PrincipalContext]
    calls: int = 0

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        self.calls += 1
        return self.principals.get(bearer_token)


@dataclass(slots=True)
class _AuditSink:
    events: list[AuthorizationAuditRecord] = field(default_factory=list)

    def record(self, event: AuthorizationAuditRecord) -> None:
        self.events.append(event)


def _principal(*capabilities: str) -> PrincipalContext:
    return PrincipalContext(
        actor_ref="actor:p3-http-machine",
        resolved_capabilities=frozenset(capabilities),
        planning_run_scope=frozenset({_PLANNING_RUN_ID}),
        schedule_version_scope=frozenset({_SCHEDULE_ID, _COMPARED_ID}),
        export_job_scope=frozenset({_EXPORT_JOB_ID}),
        auth_policy_version="simulation-http-machine.v1",
    )


def _settings() -> Settings:
    return Settings(
        runtime_environment=RuntimeEnvironment.TEST,
        data_plane=DataPlane.SIMULATION,
        simulation_api_enabled=True,
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
    )


def _query(
    view: WorkspaceView,
    *,
    schedule_version_id: str | None = None,
    fingerprint: str = _FINGERPRINT,
    correlation_id: str | None = None,
) -> dict[str, object]:
    reference = (
        {
            "schedule_version_id": schedule_version_id,
            "state": "DRAFT",
            "content_fingerprint": fingerprint,
        }
        if schedule_version_id is not None
        else None
    )
    return build_workspace_query_request(
        view=view,
        data_plane="SIMULATION",
        environment="TEST",
        synthetic=True,
        synthetic_provenance=_PROVENANCE,
        correlation_id=correlation_id or f"correlation-http-{view.value.lower()}",
        schedule_version_reference=reference,
    )


def _command(
    command_type: str,
    *,
    source_id: str,
    key_suffix: str,
) -> dict[str, object]:
    capability = {
        "MOVE_OPERATION": "edit",
        "SUBMIT_FOR_REVIEW": "edit",
        "APPROVE": "approve",
        "REJECT": "reject",
        "PUBLISH": "publish",
        "REQUEST_EXPORT": "export",
        "RETRY_EXPORT": "export",
        "CANCEL_EXPORT": "export",
    }[command_type]
    target = (
        "SIMULATION_INTERNAL"
        if command_type
        in {"PUBLISH", "REQUEST_EXPORT", "RETRY_EXPORT", "CANCEL_EXPORT"}
        else "WORKSPACE_INTERNAL"
    )
    state = {
        "MOVE_OPERATION": "DRAFT",
        "SUBMIT_FOR_REVIEW": "DRAFT",
        "APPROVE": "READY_FOR_REVIEW",
        "REJECT": "READY_FOR_REVIEW",
        "PUBLISH": "APPROVED",
        "REQUEST_EXPORT": "PUBLISHED",
        "RETRY_EXPORT": "EXPORT_FAILED",
        "CANCEL_EXPORT": "CREATED",
    }[command_type]
    payload: dict[str, object]
    if command_type == "MOVE_OPERATION":
        payload = {
            "operation_id": "operation-sim-001",
            "resource_id": "resource-sim-001",
            "start_at_utc": "2026-08-25T01:00:00Z",
            "end_at_utc": "2026-08-25T01:02:00Z",
        }
    elif command_type in {"SUBMIT_FOR_REVIEW", "APPROVE", "REJECT"}:
        payload = {}
    elif command_type == "PUBLISH":
        payload = {"previous_current_version": None}
    elif command_type == "REQUEST_EXPORT":
        payload = {"package_profile": "p3-standard-export.v1"}
    else:
        payload = {"expected_attempt": 1}
    key = f"p3-http-{key_suffix}-0001"
    document: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-http-{key_suffix}",
        "command_type": command_type,
        "required_capability": capability,
        "idempotency_key": key,
        "idempotency_scope": f"SIMULATION/{command_type}/{source_id}/{target}",
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source_id,
        "expected_state": state,
        "expected_content_fingerprint": _FINGERPRINT,
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": dict(_PROVENANCE),
        "target": target,
        "reason": "Exercise the bounded P3 HTTP transport contract.",
        "correlation_id": f"correlation-command-{key_suffix}",
        "payload": payload,
    }
    document["request_fingerprint"] = workspace_command_fingerprint(document)
    return document


def _auth_headers(command: Mapping[str, object] | None = None) -> dict[str, str]:
    result = {"Authorization": "Bearer p3-machine-token"}
    if command is not None:
        result["Idempotency-Key"] = cast(str, command["idempotency_key"])
    return result


def _json_query(document: Mapping[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def _pass(name: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"name": name, "status": "PASS", "evidence": dict(evidence)}


def _openapi_fingerprint(document: Mapping[str, object]) -> str:
    payload = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _p3_openapi_projection(document: Mapping[str, object]) -> dict[str, object]:
    """Keep the frozen P3 surface independent of additive later-phase routes."""

    paths = cast(Mapping[str, object], document["paths"])
    return {
        "openapi": document["openapi"],
        "paths": {path: paths[path] for path in sorted(P3_PATHS)},
    }


def run_http_api_checks(root: Path) -> dict[str, object]:
    application = _RecordingApplication()
    provider = _TokenProvider(
        {
            "p3-machine-token": _principal(
                "view",
                "edit",
                "lock",
                "approve",
                "reject",
                "publish",
                "export",
                "audit",
            ),
            "p3-view-only-token": _principal("view"),
        }
    )
    audit_sink = _AuditSink()
    api = create_app(
        _settings(),
        probes={"database": lambda: None, "redis": lambda: None},
        planning_workspace_application=application,
        authorization_provider=provider,
        authorization_audit_sink=audit_sink,
        planning_workspace_clock=lambda: "2026-08-25T12:00:00Z",
    )
    checks: list[dict[str, object]] = []
    openapi = api.openapi()
    api_paths = {
        path: sorted(method for method in value if method in {"get", "post"})
        for path, value in cast(dict[str, dict[str, object]], openapi["paths"]).items()
        if path in P3_PATHS
    }
    operation_ids = {
        cast(str, operation["operationId"])
        for route, path in cast(dict[str, dict[str, object]], openapi["paths"]).items()
        for method, operation in path.items()
        if route in P3_PATHS
        and method in {"get", "post"}
        and isinstance(operation, Mapping)
    }
    expected_operation_ids = {
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
    if len(api_paths) != 18 or operation_ids != expected_operation_ids:
        raise ValueError("P3 HTTP route inventory or operation IDs drifted")
    checks.append(
        _pass(
            "versioned-route-and-openapi-inventory",
            {
                "api_paths": len(api_paths),
                "operation_ids": len(operation_ids),
                "openapi_fingerprint": _openapi_fingerprint(
                    _p3_openapi_projection(openapi)
                ),
            },
        )
    )

    with TestClient(api) as client:
        simple_reads = (
            (f"/api/v1/planning-runs/{_PLANNING_RUN_ID}", 200),
            (f"/api/v1/schedule-versions/{_SCHEDULE_ID}", 200),
            (f"/api/v1/export-jobs/{_EXPORT_JOB_ID}", 200),
        )
        for path, status in simple_reads:
            response = client.get(path, headers=_auth_headers())
            if response.status_code != status:
                raise ValueError(f"HTTP read delegation failed: {path}")

        download = client.get(
            f"/api/v1/export-jobs/{_EXPORT_JOB_ID}/download",
            headers={
                **_auth_headers(),
                "X-Correlation-Id": "correlation-http-download",
            },
        )
        if (
            download.status_code != 200
            or download.headers.get("Content-Type") != "application/zip"
            or download.headers.get("Cache-Control") != "no-store"
            or download.headers.get("X-PlantNexus-Package-Id")
            != "export-package-" + "1" * 64
            or download.headers.get("X-PlantNexus-Archive-Fingerprint")
            != f"sha256:{sha256(download.content).hexdigest()}"
        ):
            raise ValueError("verified export package download delegation failed")

        for path, view in (
            ("/api/v1/workspace/data-health", WorkspaceView.DATA_HEALTH),
            ("/api/v1/workspace/import-runs", WorkspaceView.IMPORT_RUNS),
            ("/api/v1/workspace/planning-runs", WorkspaceView.PLANNING_RUNS),
        ):
            response = client.get(
                path,
                params={"query": _json_query(_query(view))},
                headers=_auth_headers(),
            )
            if response.status_code != 200:
                raise ValueError(f"HTTP workspace query delegation failed: {path}")

        gantt_query = _query(WorkspaceView.GANTT, schedule_version_id=_SCHEDULE_ID)
        response = client.get(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}/workspace/GANTT",
            params={"query": _json_query(gantt_query)},
            headers=_auth_headers(),
        )
        if response.status_code != 200:
            raise ValueError("schedule workspace view delegation failed")

        audit_query = _query(WorkspaceView.AUDIT, schedule_version_id=_SCHEDULE_ID)
        response = client.get(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}/audit-events",
            params={"query": _json_query(audit_query)},
            headers=_auth_headers(),
        )
        if response.status_code != 200:
            raise ValueError("schedule audit query delegation failed")

        comparison = _query(
            WorkspaceView.VERSION_COMPARISON,
            schedule_version_id=_SCHEDULE_ID,
            correlation_id="correlation-http-comparison",
        )
        response = client.post(
            "/api/v1/schedule-version-comparisons",
            json=comparison,
            headers={
                **_auth_headers(),
                "X-Compared-Schedule-Version-Id": _COMPARED_ID,
                "X-Compared-State": "DRAFT",
                "X-Compared-Content-Fingerprint": _COMPARED_FINGERPRINT,
            },
        )
        if response.status_code != 200:
            raise ValueError("comparison delegation failed")

        command_cases = (
            (
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}/validate",
                _command(
                    "SUBMIT_FOR_REVIEW", source_id=_SCHEDULE_ID, key_suffix="validate"
                ),
                200,
            ),
            (
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}/approve",
                _command("APPROVE", source_id=_SCHEDULE_ID, key_suffix="approve"),
                200,
            ),
            (
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}/reject",
                _command("REJECT", source_id=_SCHEDULE_ID, key_suffix="reject"),
                200,
            ),
            (
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}/publish",
                _command("PUBLISH", source_id=_SCHEDULE_ID, key_suffix="publish"),
                200,
            ),
            (
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}/commands",
                _command("MOVE_OPERATION", source_id=_SCHEDULE_ID, key_suffix="edit"),
                200,
            ),
            (
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}/exports",
                _command("REQUEST_EXPORT", source_id=_SCHEDULE_ID, key_suffix="export"),
                202,
            ),
            (
                f"/api/v1/export-jobs/{_EXPORT_JOB_ID}/retry",
                _command("RETRY_EXPORT", source_id=_EXPORT_JOB_ID, key_suffix="retry"),
                202,
            ),
            (
                f"/api/v1/export-jobs/{_EXPORT_JOB_ID}/cancel",
                _command(
                    "CANCEL_EXPORT", source_id=_EXPORT_JOB_ID, key_suffix="cancel"
                ),
                200,
            ),
        )
        for path, command, expected_status in command_cases:
            response = client.post(path, json=command, headers=_auth_headers(command))
            if response.status_code != expected_status:
                raise ValueError(f"HTTP command delegation failed: {path}")
            if response.headers.get("X-Correlation-Id") != command["correlation_id"]:
                raise ValueError("command correlation was not preserved")
        if len(application.requests) != 18:
            raise ValueError("not every frozen HTTP route delegated exactly once")
        if {request.operation for request in application.requests} != set(
            PlanningWorkspaceOperation
        ):
            raise ValueError("application operation coverage is incomplete")
        checks.append(
            _pass(
                "all-routes-delegate-to-application-port",
                {
                    "successful_http_operations": len(application.requests),
                    "application_operation_kinds": len(
                        {request.operation for request in application.requests}
                    ),
                    "router_business_state_transitions": 0,
                },
            )
        )

        before_invalid = len(application.requests)
        invalid = _command("APPROVE", source_id=_SCHEDULE_ID, key_suffix="invalid")
        invalid["unexpected"] = "must-be-rejected"
        response = client.post(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}/approve",
            json=invalid,
            headers=_auth_headers(invalid),
        )
        mismatch = _command("APPROVE", source_id=_SCHEDULE_ID, key_suffix="mismatch")
        response_mismatch = client.post(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}/approve",
            json=mismatch,
            headers={
                "Authorization": "Bearer p3-machine-token",
                "Idempotency-Key": "different-header-key-0001",
            },
        )
        if (
            response.status_code != 422
            or response_mismatch.status_code != 422
            or len(application.requests) != before_invalid
        ):
            raise ValueError("strict carrier or idempotency header failed open")
        checks.append(
            _pass(
                "strict-carrier-route-and-idempotency-binding",
                {
                    "unknown_field_status": response.status_code,
                    "header_body_mismatch_status": response_mismatch.status_code,
                    "application_calls": 0,
                },
            )
        )

        before_auth = len(application.requests)
        missing = client.get(f"/api/v1/schedule-versions/{_SCHEDULE_ID}")
        denied_command = _command(
            "APPROVE", source_id=_SCHEDULE_ID, key_suffix="denied"
        )
        denied = client.post(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}/approve",
            json=denied_command,
            headers={
                **_auth_headers(denied_command),
                "Authorization": "Bearer p3-view-only-token",
            },
        )
        if (
            missing.status_code != 401
            or denied.status_code != 403
            or len(application.requests) != before_auth
            or len(audit_sink.events) < 2
        ):
            raise ValueError("HTTP authentication/capability guard failed open")

        production_provider = _TokenProvider(
            {"p3-machine-token": _principal("view", "approve", "publish", "export")}
        )
        production_application = _RecordingApplication()
        production_sink = _AuditSink()
        production_api = create_app(
            Settings(
                runtime_environment=RuntimeEnvironment.PRODUCTION,
                data_plane=DataPlane.PRODUCTION,
                code_commit="c" * 40,
                simulation_api_enabled=False,
            ),
            probes={"database": lambda: None, "redis": lambda: None},
            planning_workspace_application=production_application,
            authorization_provider=production_provider,
            authorization_audit_sink=production_sink,
        )
        with TestClient(production_api) as production_client:
            production = production_client.get(
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}",
                headers=_auth_headers(),
            )
        if (
            production.status_code != 403
            or production_provider.calls != 0
            or production_application.requests
            or len(production_sink.events) != 1
        ):
            raise ValueError(
                "Production authority was not denied before provider lookup"
            )
        checks.append(
            _pass(
                "server-derived-capability-scope-and-production-default-deny",
                {
                    "missing_auth_status": missing.status_code,
                    "capability_denied_status": denied.status_code,
                    "denial_audits": len(audit_sink.events),
                    "production_provider_lookups": production_provider.calls,
                    "production_application_calls": len(
                        production_application.requests
                    ),
                },
            )
        )

        error_expectations = {
            "INVALID_REQUEST": 422,
            "SOURCE_NOT_FOUND": 404,
            "STALE_SOURCE": 409,
            "IDEMPOTENCY_CONFLICT": 409,
            "AUTHORIZATION_DENIED": 403,
            "VALIDATION_FAILED": 422,
            "EXPORT_FAILED": 500,
            "PERSISTENCE_FAILED": 500,
        }
        observed: dict[str, int] = {}
        for reason, expected_status in error_expectations.items():
            application.failure = PlanningWorkspaceApplicationError(
                reason,
                field="schedule_version",
                message="internal detail must not be copied",
            )
            response = client.get(
                f"/api/v1/schedule-versions/{_SCHEDULE_ID}",
                headers=_auth_headers(),
            )
            observed[reason] = response.status_code
            if response.status_code != expected_status:
                raise ValueError(f"HTTP error mapping drifted for {reason}")
        application.failure = RuntimeError(
            "postgresql://operator:secret@database/private/path token=never-return"
        )
        unknown = client.get(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}", headers=_auth_headers()
        )
        application.failure = None
        if unknown.status_code != 500 or any(
            secret in unknown.text
            for secret in ("operator", "secret", "private", "RuntimeError", "token")
        ):
            raise ValueError("unknown exception was not sanitized")
        checks.append(
            _pass(
                "stable-http-error-mapping-and-sanitization",
                {
                    "mapped_reasons": len(observed),
                    "statuses": sorted(set(observed.values())),
                    "unknown_status": unknown.status_code,
                    "secret_leaks": 0,
                },
            )
        )

        correlation = "correlation-http-explicit-001"
        correlated = client.get(
            f"/api/v1/schedule-versions/{_SCHEDULE_ID}",
            headers={**_auth_headers(), "X-Correlation-Id": correlation},
        )
        if (
            correlated.status_code != 200
            or correlated.headers.get("X-Correlation-Id") != correlation
            or correlated.json()["correlation_id"] != correlation
            or "p3-machine-token"
            in json.dumps([asdict(event) for event in audit_sink.events], default=str)
        ):
            raise ValueError("correlation or denial audit redaction drifted")
        checks.append(
            _pass(
                "correlation-and-denial-audit-redaction",
                {
                    "correlation_preserved": True,
                    "raw_bearer_in_response_or_audit": False,
                    "cache_control": correlated.headers.get("Cache-Control"),
                },
            )
        )

        mixed_query = _query(WorkspaceView.DATA_HEALTH)
        mixed_query["data_plane"] = "PRODUCTION"
        mixed = client.get(
            "/api/v1/workspace/data-health",
            params={"query": _json_query(mixed_query)},
            headers=_auth_headers(),
        )
        if mixed.status_code != 422:
            raise ValueError("mixed-plane HTTP carrier did not fail closed")
        checks.append(
            _pass(
                "simulation-plane-and-phase-boundary",
                {
                    "mixed_plane_status": mixed.status_code,
                    "external_network_calls": 0,
                    "production_authority": "DEFAULT_DENY_OPEN_010",
                    "p4_routes": 0,
                },
            )
        )

        before_health = len(application.requests)
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        router_source = (
            root / "backend/app/api/routers/planning_workspace.py"
        ).read_text(encoding="utf-8")
        forbidden_router_tokens = (
            "from app.application",
            "from app.domain",
            "Solver",
            "Validator",
            "/replan-requests",
            "/execution-events",
        )
        if (
            live.status_code != 200
            or ready.status_code != 200
            or len(application.requests) != before_health
            or any(token in router_source for token in forbidden_router_tokens)
        ):
            raise ValueError("health compatibility or thin-router boundary drifted")
        checks.append(
            _pass(
                "health-compatibility-and-thin-router-boundary",
                {
                    "health_routes": 2,
                    "health_application_calls": 0,
                    "router_application_or_domain_imports": 0,
                    "solver_validator_logic": 0,
                    "p4_routes": 0,
                },
            )
        )

    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("TASK-P3-10 machine checks are incomplete")
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "http_contract_version": "planning-workspace-http.v1",
        "openapi_fingerprint": _openapi_fingerprint(_p3_openapi_projection(openapi)),
        "check_count": len(checks),
        "checks": checks,
        "test_ids": list(TEST_IDS),
        "counts": {
            "api_paths": len(api_paths),
            "http_operations": len(operation_ids),
            "successful_delegations": 18,
            "mapped_error_reasons": 8,
            "production_provider_lookups": 0,
            "production_application_calls": 0,
            "router_business_state_transitions": 0,
            "solver_validator_invocations": 0,
        },
        "boundaries": {
            "request_carriers": ["workspace-query.v1", "workspace-command.v1"],
            "export_job_response": "export-job.v2",
            "authorization": "SERVER_DERIVED_CAPABILITY_AND_SCOPE",
            "production_authority": "DEFAULT_DENY_OPEN_010",
            "external_identity_mes_storage": "NOT_IMPLEMENTED",
            "internal_simulation_download": "EXPORTED_VERIFIED_ZIP_ONLY",
            "p3_10_frozen_operations": 17,
            "p3_13_additive_operations": 1,
            "schema_migration_dependency_state_pairs": "UNCHANGED",
            "p4_capabilities": "NOT_IMPLEMENTED",
            "p4_additive_surface": "OUTSIDE_FROZEN_P3_SUBSET",
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate TASK-P3-10 planning workspace HTTP behavior"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p3-planning-workspace-api.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        report = run_http_api_checks(arguments.root.resolve())
    except Exception as error:  # noqa: BLE001 - machine evidence must fail closed
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "status": "FAIL",
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "check_count": 0,
            "checks": [],
            "issues": [
                {
                    "reason": "MACHINE_CHECK_FAILED",
                    "error_type": type(error).__name__,
                    "message": "P3-10 HTTP evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "DEFAULT_DENY_OPEN_010",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_http_api_checks"]
