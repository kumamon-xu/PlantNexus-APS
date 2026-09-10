"""TASK-P8-18 Runtime Extension and Headless output corrective evidence.

This checker is intentionally narrower than the P8-19 requalification Gate.
It exercises the two frozen synthetic Enterprise Extensions through the real
API/Worker/Core/formal-Validator product path, proves authorized output, and
consumes the non-Production deployment/recovery drill. It does not declare the
P8 phase Gate READY.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Never, cast
import xml.etree.ElementTree as ET

from celery import Celery
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from aps_extension_sdk import ContributionManifest
from aps_extension_tooling.conformance import (
    CONFORMANCE_KEY_ID,
    ConformanceResult,
    conform_extension_set,
    conform_project,
)
from app.api.app import create_app
from app.api.dependencies.authorization import PrincipalContext
from app.application.host_authorization import HostAuthorizationAdapter
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
    request_fingerprint,
)
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.extensions.contracts import RuntimeExtensionError
from app.extensions.registry import LoadedRuntimeExtensionAdapter
from app.infrastructure.host_authorization_audit_repository import (
    SqlAlchemyHostAuthorizationAuditRepository,
)
from app.infrastructure.config import Settings
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError
from app.snapshots.canonical import import_package_id_for
from app.runtime_composition import (
    RuntimeComposition,
    RuntimeProcess,
    compose_runtime,
)
from backend.tests.contract.p8_headless_http_support import (
    HEADLESS_NOW,
    StaticAuthorizationProvider,
    authorization_policy,
    canonical_request,
    create_headers,
    run_headers,
)
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    FixedRuntimeClock,
    RecordingCelery,
    dispatched_message,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-18"
TEST_ID = "TEST-P8-EXTENSION-PRODUCT-INTEGRATION-001"
DIFF_BASE = "b80f44be094aaf5b673481dde9d81867ef49a11d"
SEED = 81620260909
DEVELOPER_KIT_VERSION = "1.0.0"
DEVELOPER_KIT_FINGERPRINT = (
    "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361"
)
P8_15_PROVIDER_RUN_ID = 34320622291
P8_15_REQUIRED_VALIDATE_JOB_ID = 102368573448
MAXIMUM_CORRECTIVE_RUNTIME_MS = 120_000
MAXIMUM_SINGLE_CHAIN_MS = 30_000
MINIMUM_TARGETED_TESTS = 283
_CONFORMANCE_KEY_TEXT = "P8-14-conformance-only-HMAC-key-not-for-production-v1"
_POINT_METHODS = {
    "CONSTRAINT": "invoke_constraints",
    "OBJECTIVE": "invoke_objectives",
    "PLANNING_RULE": "invoke_planning_rules",
    "PLUGIN_REGISTRY": "invoke_plugin_registry",
    "REPLAN_POLICY": "invoke_replan_policy",
    "VALIDATION_RULE": "invoke_validation_rules",
}
_EXTENSIONS: tuple[JsonObject, JsonObject] = (
    {
        "extension_id": "com.example.aps.alpha",
        "path": "examples/enterprise-extensions/alpha-resource-tag",
        "artifact_digest": (
            "sha256:b436aeabfe97943a69d73fe8238439641e72a8300503e5fb02aac7591c0fddea"
        ),
        "manifest_fingerprint": (
            "sha256:778ec6c56d08814f8c3d924061a71fdcf6ed306322abc09f0406e704c5b59754"
        ),
    },
    {
        "extension_id": "com.example.aps.beta",
        "path": "examples/enterprise-extensions/beta-priority-policy",
        "artifact_digest": (
            "sha256:b9b286befe1a3e0076fb96500172605b2c3259c5735d04239927219804674ae4"
        ),
        "manifest_fingerprint": (
            "sha256:0051184d253afca8313b1964cf3c1c42aadebcf399c39af56f6b48cb5e7aac12"
        ),
    },
)
_BLOCKERS = (
    "P8-GATE-BLOCKER-EXTENSION-EXECUTION-001",
    "P8-GATE-BLOCKER-KIT-RUNTIME-PROVENANCE-002",
    "P8-GATE-BLOCKER-HEADLESS-OUTPUT-003",
    "P8-GATE-BLOCKER-EXTENSION-DEPLOYMENT-004",
)


class CorrectiveEvidenceError(RuntimeError):
    """Stable payload-free P8-18 evidence failure."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.safe_message = message
        super().__init__(f"{code}: {field}: {message}")


def _fail(code: str, *, field: str, message: str) -> Never:
    raise CorrectiveEvidenceError(code, field=field, message=message)


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    head = result.stdout.strip()
    ancestor = subprocess.run(
        ("git", "merge-base", "--is-ancestor", DIFF_BASE, head),
        cwd=root,
        capture_output=True,
        check=False,
    )
    if (
        result.returncode != 0
        or len(head) != 40
        or any(character not in "0123456789abcdef" for character in head)
        or ancestor.returncode != 0
    ):
        _fail(
            "CORRECTIVE_PROVENANCE_INVALID",
            field="git_head",
            message="corrective HEAD does not descend from the frozen Diff base",
        )
    return head


def _read_json(path: Path, *, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CorrectiveEvidenceError(
            "CORRECTIVE_INPUT_UNAVAILABLE",
            field=field,
            message="required corrective input is unavailable",
        ) from error
    if not isinstance(value, dict):
        _fail(
            "CORRECTIVE_INPUT_INVALID",
            field=field,
            message="required corrective input must be a JSON object",
        )
    return cast(JsonObject, value)


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(document) + b"\n")
    temporary.replace(path)


def _fingerprinted(document: JsonObject) -> JsonObject:
    projection = dict(document)
    projection.pop("report_fingerprint", None)
    document["report_fingerprint"] = canonical_fingerprint(projection)
    return document


def _targeted_suite(path: Path) -> JsonObject:
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as error:
        raise CorrectiveEvidenceError(
            "CORRECTIVE_SUITE_INVALID",
            field="targeted_junit",
            message="targeted P8 JUnit evidence is unavailable",
        ) from error
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))

    def total(name: str) -> int:
        try:
            return sum(int(float(suite.attrib.get(name, "0"))) for suite in suites)
        except ValueError:
            _fail(
                "CORRECTIVE_SUITE_INVALID",
                field="targeted_junit",
                message="targeted P8 JUnit counters are invalid",
            )

    summary = {
        "tests": total("tests"),
        "failures": total("failures"),
        "errors": total("errors"),
        "skipped": total("skipped"),
        "minimum_tests": MINIMUM_TARGETED_TESTS,
    }
    if (
        not suites
        or summary["tests"] < MINIMUM_TARGETED_TESTS
        or summary["failures"]
        or summary["errors"]
        or summary["skipped"]
    ):
        _fail(
            "CORRECTIVE_SUITE_FAILED",
            field="targeted_junit",
            message="targeted P8 suite failed or missed its frozen minimum",
        )
    return {**summary, "status": "PASS"}


class _WorkspaceAuthorizationProvider:
    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        if bearer_token != "p8-product-token":
            return None
        return PrincipalContext(
            actor_ref="actor:p8-product-integration",
            resolved_capabilities=frozenset({"view", "approve", "publish", "export"}),
            planning_run_scope=frozenset({"*"}),
            schedule_version_scope=frozenset({"*"}),
            export_job_scope=frozenset({"*"}),
            auth_policy_version="simulation-p8-product-policy.v1",
        )


def _extension_facts(
    extension_id: str, *, qualified: bool = True, request_replan: bool = False
) -> JsonObject:
    return {
        "extension_facts_version": "runtime-extension-facts.v1",
        "resource_attributes": (
            {"RESOURCE-001": {"tags": ["alpha-qualified"]}}
            if extension_id.endswith(".alpha") and qualified
            else {}
        ),
        "operation_attributes": {},
        "events": ["synthetic.disruption"] if request_replan else [],
        "publication_authority_reference": "authority.p8.corrective.synthetic",
    }


def _settings(
    directory: Path,
    *,
    database_url: str,
    catalog_path: Path,
    code_commit: str,
    extension_id: str,
    qualified: bool = True,
    request_replan: bool = False,
):
    directory.mkdir(parents=True, exist_ok=True)
    base = runtime_settings(
        directory,
        database_url=database_url,
        extension_facts=_extension_facts(
            extension_id,
            qualified=qualified,
            request_replan=request_replan,
        ),
    )
    return base.model_copy(
        update={
            "code_commit": code_commit,
            "developer_kit_version": DEVELOPER_KIT_VERSION,
            "developer_kit_fingerprint": DEVELOPER_KIT_FINGERPRINT,
            "runtime_extension_catalog_path": catalog_path,
            "runtime_extension_verification_key_id": CONFORMANCE_KEY_ID,
            "runtime_extension_verification_key": SecretStr(_CONFORMANCE_KEY_TEXT),
        }
    )


def _workspace_command(
    schedule: Mapping[str, object],
    *,
    command_type: str,
    capability: str,
    state: str,
    target: str,
    key: str,
    payload: Mapping[str, object],
) -> JsonObject:
    command: JsonObject = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": capability,
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/{command_type}/{schedule['schedule_version_id']}/{target}"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": schedule["schedule_version_id"],
        "expected_state": state,
        "expected_content_fingerprint": schedule["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": schedule["environment"],
        "synthetic": True,
        "synthetic_provenance": schedule["synthetic_provenance"],
        "target": target,
        "reason": f"Execute {command_type} in the P8-18 corrective check.",
        "correlation_id": f"correlation-{key}",
        "payload": dict(payload),
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _command_headers(command: Mapping[str, object]) -> dict[str, str]:
    return {
        "Authorization": "Bearer p8-product-token",
        "Content-Type": "application/json",
        "Idempotency-Key": cast(str, command["idempotency_key"]),
        "X-Correlation-Id": cast(str, command["correlation_id"]),
    }


def _host_app(settings: Settings, composition: RuntimeComposition) -> FastAPI:
    if (
        composition.application is None
        or composition.planning_workspace_application is None
    ):
        _fail(
            "CORRECTIVE_RUNTIME_INVALID",
            field="api_composition",
            message="required Runtime application ports are unavailable",
        )
    host_adapter = HostAuthorizationAdapter(
        provider=StaticAuthorizationProvider(),
        policy=authorization_policy(),
        audit_sink=SqlAlchemyHostAuthorizationAuditRepository(
            composition.database.engine, data_plane="SIMULATION"
        ),
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
    )
    return create_app(
        settings,
        probes=composition.probes,
        planning_workspace_application=composition.planning_workspace_application,
        authorization_provider=_WorkspaceAuthorizationProvider(),
        runtime_application=composition.application,
        runtime_descriptor=composition.descriptor,
        runtime_http_context=composition.http_context_adapter,
        host_authorization_adapter=host_adapter,
        headless_clock=lambda: HEADLESS_NOW,
    )


def _metrics(composition: RuntimeComposition) -> JsonObject:
    adapter = composition.extension_adapter
    if not isinstance(adapter, LoadedRuntimeExtensionAdapter):
        _fail(
            "CORRECTIVE_EXTENSION_NOT_LOADED",
            field="extension_adapter",
            message="Runtime did not load the selected Extension",
        )
    return adapter.safe_metrics()


def _database_counts(composition: RuntimeComposition) -> JsonObject:
    with composition.database.engine.connect() as connection:
        return {
            "canonical_ingress_records": int(
                connection.scalar(
                    text("SELECT count(*) FROM canonical_ingress_records")
                )
                or 0
            ),
            "planning_runs": int(
                connection.scalar(text("SELECT count(*) FROM planning_runs")) or 0
            ),
            "planning_run_worker_results": int(
                connection.scalar(
                    text("SELECT count(*) FROM planning_run_worker_results")
                )
                or 0
            ),
            "schedule_versions": int(
                connection.scalar(text("SELECT count(*) FROM schedule_versions")) or 0
            ),
            "publication_results": int(
                connection.scalar(text("SELECT count(*) FROM publication_results")) or 0
            ),
            "export_jobs": int(
                connection.scalar(text("SELECT count(*) FROM export_jobs")) or 0
            ),
        }


def _run_chain(
    base: Path,
    *,
    result: ConformanceResult,
    code_commit: str,
) -> JsonObject:
    started = perf_counter()
    extension_id = result.project.project_id
    slug = extension_id.rsplit(".", maxsplit=1)[-1]
    catalog_directory = base / f"{slug}-catalog"
    _, conformance = conform_extension_set(
        (result,), runtime_directory=catalog_directory
    )
    database_path = base / f"{slug}.db"
    engine, _ = migrated_engine(database_path)
    engine.dispose()
    settings = _settings(
        base / f"{slug}-settings",
        database_url=f"sqlite:///{database_path.as_posix()}",
        catalog_path=catalog_directory / "runtime-extension-catalog.json",
        code_commit=code_commit,
        extension_id=extension_id,
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory(f"p8-18-{slug}-dispatch"),
        extension_artifacts=(result.artifact,),
    )
    worker = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 5, tzinfo=UTC)),
        extension_artifacts=(result.artifact,),
    )
    try:
        if api.descriptor.canonical_bytes != worker.descriptor.canonical_bytes:
            _fail(
                "CORRECTIVE_RUNTIME_MISMATCH",
                field=extension_id,
                message="API and Worker descriptors differ before execution",
            )
        application = _host_app(settings, api)
        request = canonical_request()
        request_bytes = canonical_json_bytes(request)
        before = _metrics(worker)
        with TestClient(application) as client:
            unauthorized_create_headers = create_headers(request)
            unauthorized_create_headers.pop("Authorization")
            unauthorized_create = client.post(
                "/api/v1/planning-runs",
                content=request_bytes,
                headers=unauthorized_create_headers,
            )
            created = client.post(
                "/api/v1/planning-runs",
                content=request_bytes,
                headers=create_headers(request),
            )
            replayed = client.post(
                "/api/v1/planning-runs",
                content=request_bytes,
                headers=create_headers(request),
            )
            if created.status_code != 202 or len(publisher.messages) != 1:
                _fail(
                    "CORRECTIVE_CHAIN_FAILED",
                    field=f"{extension_id}.create",
                    message="canonical request was not dispatched exactly once",
                )
            message = dispatched_message(publisher.messages[0])
            if worker.worker is None:
                _fail(
                    "CORRECTIVE_RUNTIME_INVALID",
                    field=f"{extension_id}.worker",
                    message="Solver Worker port is unavailable",
                )
            execution = worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=cast(str, message["worker_id"]),
            )
            replay_execution = worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=f"worker:p8-18-{slug}-replay",
            )
            planning_run_id = cast(str, message["planning_run_id"])
            result_response = client.get(
                f"/api/v1/planning-runs/{planning_run_id}/result",
                headers=run_headers(correlation_id=f"CORRELATION-P8-18-{slug.upper()}"),
            )
            with api.database.engine.connect() as connection:
                schedule_id = cast(
                    str,
                    connection.scalar(
                        text("SELECT schedule_version_id FROM schedule_versions")
                    ),
                )
            repository = SqlAlchemyScheduleVersionRepository(
                api.database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            schedule = cast(JsonObject, repository.get(schedule_id))
            unauthorized_read = client.get(f"/api/v1/schedule-versions/{schedule_id}")
            ready_read = client.get(
                f"/api/v1/schedule-versions/{schedule_id}",
                headers={"Authorization": "Bearer p8-product-token"},
            )
            approve = _workspace_command(
                schedule,
                command_type="APPROVE",
                capability="approve",
                state="READY_FOR_REVIEW",
                target="WORKSPACE_INTERNAL",
                key=f"p8-18-{slug}-approve-0001",
                payload={},
            )
            approved = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/approve",
                content=canonical_json_bytes(approve),
                headers=_command_headers(approve),
            )
            schedule = cast(JsonObject, repository.get(schedule_id))
            publish = _workspace_command(
                schedule,
                command_type="PUBLISH",
                capability="publish",
                state="APPROVED",
                target="SIMULATION_INTERNAL",
                key=f"p8-18-{slug}-publish-0001",
                payload={"previous_current_version": None},
            )
            published = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/publish",
                content=canonical_json_bytes(publish),
                headers=_command_headers(publish),
            )
            schedule = cast(JsonObject, repository.get(schedule_id))
            export = _workspace_command(
                schedule,
                command_type="REQUEST_EXPORT",
                capability="export",
                state="PUBLISHED",
                target="SIMULATION_INTERNAL",
                key=f"p8-18-{slug}-export-0001",
                payload={"package_profile": "p3-standard-export.v1"},
            )
            exported = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/exports",
                content=canonical_json_bytes(export),
                headers=_command_headers(export),
            )
            export_id = exported.json().get("export_job_id")
            export_read = client.get(
                f"/api/v1/export-jobs/{export_id}",
                headers={"Authorization": "Bearer p8-product-token"},
            )
            export_replay = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/exports",
                content=canonical_json_bytes(export),
                headers=_command_headers(export),
            )
            published_read = client.get(
                f"/api/v1/schedule-versions/{schedule_id}",
                headers={"Authorization": "Bearer p8-product-token"},
            )
        after = _metrics(worker)
        rows = cast(list[JsonObject], after["contributions"])
        selected = {
            contribution.contribution_id: contribution.extension_point.value
            for contribution in cast(
                tuple[ContributionManifest, ...], worker.extension_adapter.contributions
            )
        }
        observed = {cast(str, row["contribution_id"]): row for row in rows}
        all_invoked = set(observed) == set(selected) and all(
            row.get("call_count", 0) >= 1
            and row.get("success_count", 0) >= 1
            and isinstance(row.get("last_input_fingerprint"), str)
            and isinstance(row.get("last_output_fingerprint"), str)
            for row in observed.values()
        )
        counts = _database_counts(api)
        statuses = {
            "unauthorized_create": unauthorized_create.status_code,
            "created": created.status_code,
            "replayed": replayed.status_code,
            "result": result_response.status_code,
            "unauthorized_schedule_read": unauthorized_read.status_code,
            "ready_schedule_read": ready_read.status_code,
            "approved": approved.status_code,
            "published": published.status_code,
            "export_created": exported.status_code,
            "export_read": export_read.status_code,
            "export_replay": export_replay.status_code,
            "published_schedule_read": published_read.status_code,
        }
        passed = (
            statuses
            == {
                "unauthorized_create": 401,
                "created": 202,
                "replayed": 202,
                "result": 200,
                "unauthorized_schedule_read": 401,
                "ready_schedule_read": 200,
                "approved": 200,
                "published": 200,
                "export_created": 202,
                "export_read": 200,
                "export_replay": 202,
                "published_schedule_read": 200,
            }
            and replayed.json().get("idempotency", {}).get("outcome") == "REPLAYED"
            and execution.disposition.value == "COMPLETED"
            and replay_execution.disposition.value == "EXACT_REPLAY"
            and ready_read.json().get("state") == "READY_FOR_REVIEW"
            and published_read.json().get("state") == "PUBLISHED"
            and export_replay.json().get("export_job_id") == export_id
            and counts
            == {
                "canonical_ingress_records": 1,
                "planning_runs": 1,
                "planning_run_worker_results": 1,
                "schedule_versions": 1,
                "publication_results": 1,
                "export_jobs": 1,
            }
            and all_invoked
            and after["payloads_recorded"] is False
            and after["exception_details_recorded"] is False
            and after["unhealthy_contribution_ids"] == []
        )
        elapsed_ms = round((perf_counter() - started) * 1_000, 3)
        if not passed or elapsed_ms > MAXIMUM_SINGLE_CHAIN_MS:
            _fail(
                "CORRECTIVE_CHAIN_FAILED",
                field=extension_id,
                message="Extension product or authorized output chain failed closed",
            )
        resolution = api.descriptor.runtime_resolution
        if (
            resolution["developer_kit_version"] != DEVELOPER_KIT_VERSION
            or resolution["developer_kit_fingerprint"] != DEVELOPER_KIT_FINGERPRINT
        ):
            _fail(
                "CORRECTIVE_KIT_MISMATCH",
                field=extension_id,
                message="Runtime did not bind the exact verified Developer Kit",
            )
        return {
            "extension_id": extension_id,
            "artifact_digest": result.report["artifact_digest"],
            "manifest_fingerprint": result.project.manifest.manifest_fingerprint,
            "conformance_status": conformance["status"],
            "selected_contributions": selected,
            "metrics_before": before,
            "metrics_after": after,
            "all_selected_contributions_invoked": all_invoked,
            "runtime_resolution": resolution,
            "http_statuses": statuses,
            "output": {
                "schedule_version_id": schedule_id,
                "final_schedule_state": published_read.json()["state"],
                "export_job_id": export_id,
                "publication_count": counts["publication_results"],
                "export_count": counts["export_jobs"],
                "idempotent_export_replay": True,
            },
            "durability": counts,
            "result_fingerprint": canonical_fingerprint(result_response.json()),
            "elapsed_ms": elapsed_ms,
            "status": "PASS",
        }
    finally:
        worker.close()
        api.close()


def _negative_extension(
    base: Path,
    *,
    result: ConformanceResult,
    code_commit: str,
    qualified: bool,
    request_replan: bool,
    expected_code: str,
    canonical_resource_id: str | None = None,
) -> JsonObject:
    extension_id = result.project.project_id
    slug = extension_id.rsplit(".", maxsplit=1)[-1]
    catalog_directory = base / f"negative-{slug}-catalog"
    conform_extension_set((result,), runtime_directory=catalog_directory)
    database_path = base / f"negative-{slug}.db"
    engine, _ = migrated_engine(database_path)
    engine.dispose()
    settings = _settings(
        base / f"negative-{slug}-settings",
        database_url=f"sqlite:///{database_path.as_posix()}",
        catalog_path=catalog_directory / "runtime-extension-catalog.json",
        code_commit=code_commit,
        extension_id=extension_id,
        qualified=qualified,
        request_replan=request_replan,
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory(f"p8-18-negative-{slug}"),
        extension_artifacts=(result.artifact,),
    )
    worker = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 5, tzinfo=UTC)),
        extension_artifacts=(result.artifact,),
    )
    observed_code: str | None = None
    try:
        application = _host_app(settings, api)
        request = canonical_request()
        if canonical_resource_id is not None:
            payload = cast(JsonObject, request["payload"])

            def replace_resource_id(value: object) -> object:
                if value == "RESOURCE-001":
                    return canonical_resource_id
                if isinstance(value, dict):
                    return {
                        key: replace_resource_id(item) for key, item in value.items()
                    }
                if isinstance(value, list):
                    return [replace_resource_id(item) for item in value]
                return value

            request["payload"] = cast(JsonObject, replace_resource_id(payload))
            payload = cast(JsonObject, request["payload"])
            payload["package_id"] = import_package_id_for(payload)
            request["payload_fingerprint"] = canonical_fingerprint(payload)
            request["request_fingerprint"] = request_fingerprint(request)
        with TestClient(application) as client:
            created = client.post(
                "/api/v1/planning-runs",
                content=canonical_json_bytes(request),
                headers=create_headers(request),
            )
        if created.status_code != 202 or worker.worker is None:
            _fail(
                "CORRECTIVE_NEGATIVE_FAILED",
                field=extension_id,
                message="negative Extension fixture could not be dispatched",
            )
        message = dispatched_message(publisher.messages[0])
        try:
            worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=cast(str, message["worker_id"]),
            )
        except PlanningRunWorkerError as error:
            if isinstance(error.__cause__, RuntimeExtensionError):
                observed_code = error.__cause__.code
            public_worker_code = error.code.value
            public_worker_field = error.field
        else:
            public_worker_code = None
            public_worker_field = None
        with api.database.engine.connect() as connection:
            schedule_count = int(
                connection.scalar(text("SELECT count(*) FROM schedule_versions")) or 0
            )
            run_state = connection.scalar(text("SELECT state FROM planning_runs"))
        if (
            observed_code != expected_code
            or public_worker_code != "EXECUTION_FAILED"
            or public_worker_field != "runtime_extension"
            or schedule_count != 0
            or run_state != "FAILED"
        ):
            _fail(
                "CORRECTIVE_NEGATIVE_FAILED",
                field=extension_id,
                message="Extension violation did not fail before ScheduleVersion creation",
            )
        return {
            "extension_id": extension_id,
            "extension_error_code": observed_code,
            "worker_error_code": public_worker_code,
            "worker_error_field": public_worker_field,
            "planning_run_state": run_state,
            "schedule_version_count": schedule_count,
            "partial_success": False,
            "status": "PASS",
        }
    finally:
        worker.close()
        api.close()


def _kit_mismatch(
    base: Path, *, result: ConformanceResult, code_commit: str
) -> JsonObject:
    catalog_directory = base / "kit-mismatch-catalog"
    conform_extension_set((result,), runtime_directory=catalog_directory)
    database_path = base / "kit-mismatch.db"
    engine, _ = migrated_engine(database_path)
    engine.dispose()
    correct = _settings(
        base / "kit-mismatch-api",
        database_url=f"sqlite:///{database_path.as_posix()}",
        catalog_path=catalog_directory / "runtime-extension-catalog.json",
        code_commit=code_commit,
        extension_id=result.project.project_id,
    )
    mismatched = correct.model_copy(
        update={"developer_kit_fingerprint": "sha256:" + "f" * 64}
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        correct,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("p8-18-kit-mismatch"),
        extension_artifacts=(result.artifact,),
    )
    worker = compose_runtime(
        mismatched,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 5, tzinfo=UTC)),
        extension_artifacts=(result.artifact,),
    )
    error_code: str | None = None
    try:
        application = _host_app(correct, api)
        request = canonical_request()
        with TestClient(application) as client:
            created = client.post(
                "/api/v1/planning-runs",
                content=canonical_json_bytes(request),
                headers=create_headers(request),
            )
        if created.status_code != 202 or worker.worker is None:
            _fail(
                "CORRECTIVE_NEGATIVE_FAILED",
                field="developer_kit",
                message="Kit mismatch fixture could not be dispatched",
            )
        message = dispatched_message(publisher.messages[0])
        try:
            worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=cast(str, message["worker_id"]),
            )
        except PlanningRunWorkerError as error:
            error_code = error.code.value
        with api.database.engine.connect() as connection:
            worker_result_count = int(
                connection.scalar(
                    text("SELECT count(*) FROM planning_run_worker_results")
                )
                or 0
            )
        if error_code != "RUNTIME_MISMATCH" or worker_result_count != 0:
            _fail(
                "CORRECTIVE_NEGATIVE_FAILED",
                field="developer_kit",
                message="API/Worker Kit mismatch did not fail before result creation",
            )
        return {
            "error_code": error_code,
            "worker_result_count": worker_result_count,
            "partial_success": False,
            "status": "PASS",
        }
    finally:
        worker.close()
        api.close()


def _source_audit(root: Path) -> JsonObject:
    sites: list[JsonObject] = []
    forbidden_business_literals: list[str] = []
    reverse_imports: list[str] = []
    for path in sorted((root / "backend/app").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        if relative != "backend/app/extensions/registry.py":
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in set(_POINT_METHODS.values())
                ):
                    sites.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "method": node.func.attr,
                        }
                    )
        if "com.example.aps.alpha" in source or "com.example.aps.beta" in source:
            forbidden_business_literals.append(relative)
        if relative.startswith(("backend/app/domain/", "backend/app/planning/")):
            for node in ast.walk(tree):
                module_names: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    module_names = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    module_names = (node.module,)
                if any(
                    name.startswith(("app.extensions", "aps_extension_sdk"))
                    for name in module_names
                ):
                    reverse_imports.append(
                        f"{relative}:{getattr(node, 'lineno', 0)}"
                    )
    observed_methods = sorted({cast(str, site["method"]) for site in sites})
    sdk_diff = subprocess.run(
        ("git", "diff", "--name-only", DIFF_BASE, "--", "backend/aps_extension_sdk"),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout.strip()
    if (
        observed_methods != sorted(_POINT_METHODS.values())
        or forbidden_business_literals
        or reverse_imports
        or sdk_diff
    ):
        _fail(
            "CORRECTIVE_SOURCE_AUDIT_FAILED",
            field="source_boundary",
            message="Runtime call sites crossed the Core, SDK, or enterprise boundary",
        )
    return {
        "product_call_sites": sites,
        "observed_methods": observed_methods,
        "enterprise_business_literals_in_runtime": forbidden_business_literals,
        "core_reverse_imports": reverse_imports,
        "sdk_v1_changed": False,
        "status": "PASS",
    }


def _deployment_inputs(
    deployment_path: Path, recovery_path: Path, *, code_commit: str
) -> JsonObject:
    deployment = _read_json(deployment_path, field="operations_deployment")
    recovery = _read_json(recovery_path, field="operations_recovery")
    identity = deployment.get("extension_identity")
    rollback = recovery.get("rollback")
    if (
        deployment.get("report_version") != "p8-operations-deployment-report.v1"
        or recovery.get("report_version") != "p8-operations-recovery-report.v1"
        or deployment.get("status") != "PASS"
        or recovery.get("status") != "PASS"
        or deployment.get("execution") != "DOCKER_COMPOSE_TARGET"
        or recovery.get("execution") != "DOCKER_COMPOSE_TARGET"
        or deployment.get("evidence_commit") != code_commit
        or recovery.get("evidence_commit") != code_commit
        or not isinstance(identity, Mapping)
        or identity.get("extension_ids") != ["com.example.aps.alpha"]
        or identity.get("developer_kit_fingerprint") != DEVELOPER_KIT_FINGERPRINT
        or recovery.get("extension_identity_at_backup_point") != identity
        or recovery.get("extension_identity_after_restore") != identity
        or not isinstance(rollback, Mapping)
        or rollback.get("extension_identity_match") is not True
        or rollback.get("extension_identity") != identity
    ):
        _fail(
            "CORRECTIVE_DEPLOYMENT_FAILED",
            field="operations",
            message="target deployment/recovery Extension identity is not exact",
        )
    return {
        "target": deployment["target"],
        "extension_identity": dict(identity),
        "candidate_api_worker_match": (
            deployment.get("runtime_descriptor", {}).get("composition_fingerprint")
            == deployment.get("worker_runtime_descriptor", {}).get(
                "composition_fingerprint"
            )
        ),
        "backup_restore_status": recovery["backup_restore"]["status"],
        "restore_identity_match": True,
        "rollback_identity_match": True,
        "production_recovery_claimed": False,
        "status": "PASS",
    }


def _base(report_version: str, *, code_commit: str) -> JsonObject:
    return {
        "report_version": report_version,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "seed": SEED,
        "status": "PASS",
        "production_ready": False,
    }


def run(args: argparse.Namespace) -> tuple[JsonObject, ...]:
    started = perf_counter()
    root = args.root.resolve()
    code_commit = _git_head(root)
    suite = _targeted_suite(args.junit.resolve())
    source_audit = _source_audit(root)
    results: list[ConformanceResult] = []
    for expected in _EXTENSIONS:
        result = conform_project(
            root / cast(str, expected["path"]),
            repository_root=root,
            clean_install=False,
        )
        if (
            result.project.project_id != expected["extension_id"]
            or result.report["artifact_digest"] != expected["artifact_digest"]
            or result.project.manifest.manifest_fingerprint
            != expected["manifest_fingerprint"]
        ):
            _fail(
                "CORRECTIVE_EXTENSION_IDENTITY_MISMATCH",
                field=cast(str, expected["extension_id"]),
                message="Enterprise Extension differs from the frozen P8-15 input",
            )
        results.append(result)
    with TemporaryDirectory(prefix="plantnexus-p8-18-") as temporary:
        base = Path(temporary)
        chains = [
            _run_chain(base, result=result, code_commit=code_commit)
            for result in results
        ]
        negative_alpha = _negative_extension(
            base,
            result=results[0],
            code_commit=code_commit,
            qualified=False,
            request_replan=False,
            expected_code="EXTENSION_VALIDATION_FAILED",
            canonical_resource_id="resource-001",
        )
        negative_beta = _negative_extension(
            base,
            result=results[1],
            code_commit=code_commit,
            qualified=True,
            request_replan=True,
            expected_code="EXTENSION_REPLAN_REQUIRED",
        )
        kit_mismatch = _kit_mismatch(base, result=results[0], code_commit=code_commit)
    deployment = _deployment_inputs(
        args.operations_deployment.resolve(),
        args.operations_recovery.resolve(),
        code_commit=code_commit,
    )
    point_coverage = sorted(
        {
            point
            for chain in chains
            for point in cast(
                Mapping[str, str], chain["selected_contributions"]
            ).values()
        }
    )
    if point_coverage != sorted(_POINT_METHODS):
        _fail(
            "CORRECTIVE_POINT_COVERAGE_FAILED",
            field="extension_points",
            message="the six Extension points were not covered by product execution",
        )
    elapsed_ms = round((perf_counter() - started) * 1_000, 3)
    maximum_chain_ms = max(cast(float, chain["elapsed_ms"]) for chain in chains)
    if (
        elapsed_ms > MAXIMUM_CORRECTIVE_RUNTIME_MS
        or maximum_chain_ms > MAXIMUM_SINGLE_CHAIN_MS
    ):
        _fail(
            "CORRECTIVE_THRESHOLD_FAILED",
            field="elapsed_ms",
            message="synthetic corrective evidence exceeded its frozen engineering limit",
        )

    invocation = _base(
        "p8-runtime-extension-product-invocation-report.v1",
        code_commit=code_commit,
    )
    invocation.update(
        {
            "extension_point_coverage": point_coverage,
            "product_call_methods": sorted(_POINT_METHODS.values()),
            "chains": chains,
            "source_audit": source_audit,
            "negative_validation": negative_alpha,
            "negative_replan": negative_beta,
            "payloads_recorded": False,
        }
    )
    kit = _base("p8-runtime-developer-kit-binding-report.v1", code_commit=code_commit)
    kit.update(
        {
            "developer_kit_version": DEVELOPER_KIT_VERSION,
            "developer_kit_fingerprint": DEVELOPER_KIT_FINGERPRINT,
            "provider_baseline": {
                "task_id": "TASK-P8-15",
                "provider_run_id": P8_15_PROVIDER_RUN_ID,
                "required_validate_job_id": P8_15_REQUIRED_VALIDATE_JOB_ID,
            },
            "runtime_bindings": [chain["runtime_resolution"] for chain in chains],
            "api_worker_mismatch_negative": kit_mismatch,
            "automatic_upgrade": False,
        }
    )
    output = _base("p8-headless-output-corrective-report.v1", code_commit=code_commit)
    output.update(
        {
            "chains": [
                {
                    "extension_id": chain["extension_id"],
                    "http_statuses": chain["http_statuses"],
                    "output": chain["output"],
                }
                for chain in chains
            ],
            "authorization_default_deny": True,
            "explicit_approve_publish_export": True,
            "automatic_publication": False,
            "idempotent_export": True,
        }
    )
    deployment_report = _base(
        "p8-extension-deployment-recovery-corrective-report.v1",
        code_commit=code_commit,
    )
    deployment_report.update(deployment)
    security = _base(
        "p8-runtime-product-corrective-security-report.v1",
        code_commit=code_commit,
    )
    security.update(
        {
            "authorization_default_deny": True,
            "extension_validation_failure": negative_alpha,
            "extension_replan_failure": negative_beta,
            "kit_mismatch_failure": kit_mismatch,
            "core_reverse_import_count": 0,
            "enterprise_branch_count": 0,
            "payload_or_secret_in_metrics": False,
        }
    )
    benchmark = _base(
        "p8-runtime-product-corrective-benchmark-report.v1",
        code_commit=code_commit,
    )
    benchmark.update(
        {
            "targeted_suite": suite,
            "elapsed_ms": elapsed_ms,
            "maximum_chain_ms": maximum_chain_ms,
            "thresholds": {
                "maximum_corrective_runtime_ms": MAXIMUM_CORRECTIVE_RUNTIME_MS,
                "maximum_single_chain_ms": MAXIMUM_SINGLE_CHAIN_MS,
                "minimum_targeted_tests": MINIMUM_TARGETED_TESTS,
            },
            "production_sla_claimed": False,
        }
    )
    subreports = (invocation, kit, output, deployment_report, security, benchmark)
    for report in subreports:
        _fingerprinted(report)
    report_references = {
        cast(str, report["report_version"]): report["report_fingerprint"]
        for report in subreports
    }
    blocker_evidence = {
        _BLOCKERS[0]: invocation["report_fingerprint"],
        _BLOCKERS[1]: kit["report_fingerprint"],
        _BLOCKERS[2]: output["report_fingerprint"],
        _BLOCKERS[3]: deployment_report["report_fingerprint"],
    }
    blocker = _base("p8-runtime-product-corrective-report.v1", code_commit=code_commit)
    blocker.update(
        {
            "validation_profile": "HIGH_RISK",
            "closed_blockers": [
                {
                    "blocker_id": blocker_id,
                    "status": "PASS",
                    "evidence_fingerprint": blocker_evidence[blocker_id],
                    "historical_p8_16_verdict_changed": False,
                }
                for blocker_id in _BLOCKERS
            ],
            "blocker_count": len(_BLOCKERS),
            "pass_count": len(_BLOCKERS),
            "reports": report_references,
            "scope": {
                "canonical_json_only": True,
                "demo_included": False,
                "real_data": False,
                "third_party_connectors": False,
                "p7_reality_calibration": False,
                "production_authorized": False,
                "p8_19_executed": False,
            },
            "next": {
                "eligible_to_request": "TASK-P8-19",
                "automatic_start": False,
                "p8_exit_authorized": False,
            },
        }
    )
    _fingerprinted(blocker)
    return (blocker, invocation, kit, output, deployment_report, security, benchmark)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--operations-deployment", type=Path, required=True)
    parser.add_argument("--operations-recovery", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--invocation-report", type=Path, required=True)
    parser.add_argument("--kit-report", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--deployment-report", type=Path, required=True)
    parser.add_argument("--security-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = (
        args.report,
        args.invocation_report,
        args.kit_report,
        args.output_report,
        args.deployment_report,
        args.security_report,
        args.benchmark_report,
    )
    try:
        reports = run(args)
        for path, report in zip(paths, reports, strict=True):
            _write_json(path.resolve(), report)
    except Exception as error:  # noqa: BLE001 - CLI emits only a stable safe failure
        code = getattr(error, "code", "CORRECTIVE_RUNTIME_FAILED")
        failure = {
            "report_version": "p8-runtime-product-corrective-report.v1",
            "task_id": TASK_ID,
            "test_id": TEST_ID,
            "diff_base": DIFF_BASE,
            "status": "FAIL",
            "error": {
                "code": code,
                "message": "P8-18 corrective evidence failed closed",
            },
            "production_ready": False,
        }
        _write_json(args.report.resolve(), failure)
        print(f"FAIL {TASK_ID}: {code}")
        return 1
    print(
        "PASS TASK-P8-18 corrective evidence: "
        "blockers=4 extensions=2 extension_points=6"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
