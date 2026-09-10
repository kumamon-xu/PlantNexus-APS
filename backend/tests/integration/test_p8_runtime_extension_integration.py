"""API/Worker composition parity and lineage integration for TASK-P8-13."""

from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
from typing import cast

from celery import Celery
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.api.app import create_app, create_runtime_app
from app.api.dependencies.authorization import PrincipalContext
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.extensions.contracts import RuntimeExtensionArtifact
from app.extensions.registry import LoadedRuntimeExtensionAdapter
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.planning_run_task import clear_planning_run_task_executor
from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError
from app.jobs.celery_app import create_runtime_celery_app
from app.runtime_composition import RuntimeProcess, compose_runtime
from backend.tests.p8_runtime_extension_support import runtime_extension_fixture
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    FixedRuntimeClock,
    RecordingCelery,
    command_context,
    dispatch_window,
    dispatched_message,
    ingress_context,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


def _database(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "runtime-extension.db"
    engine, _ = migrated_engine(path)
    engine.dispose()
    return path, f"sqlite:///{path.as_posix()}"


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


def _workspace_command(
    schedule: dict[str, object],
    *,
    command_type: str,
    capability: str,
    state: str,
    target: str,
    key: str,
    payload: dict[str, object],
) -> dict[str, object]:
    command: dict[str, object] = {
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
        "reason": f"Execute {command_type} in the P8 product integration check.",
        "correlation_id": f"correlation-{key}",
        "payload": payload,
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _command_headers(command: dict[str, object]) -> dict[str, str]:
    return {
        "Authorization": "Bearer p8-product-token",
        "Content-Type": "application/json",
        "Idempotency-Key": cast(str, command["idempotency_key"]),
        "X-Correlation-Id": cast(str, command["correlation_id"]),
    }


def test_api_worker_load_same_extension_set_and_preserve_full_solver_chain(
    tmp_path: Path,
) -> None:
    _, database_url = _database(tmp_path)
    fixture = runtime_extension_fixture(tmp_path, database_url=database_url)
    publisher = RecordingCelery()
    api = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("extension-dispatch-001"),
        extension_artifacts=(fixture.artifact,),
    )
    worker = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(),
        extension_artifacts=(fixture.artifact,),
    )
    try:
        assert api.descriptor.canonical_bytes == worker.descriptor.canonical_bytes
        assert api.extension_adapter.document["mode"] == "LOADED"
        assert worker.extension_adapter.extension_set_reference == (
            api.extension_adapter.extension_set_reference
        )
        assert api.descriptor.runtime_resolution["extension_sdk_version"] == "1.0.0"
        assert api.descriptor.runtime_resolution["developer_kit_version"] == "1.0.0"
        assert api.descriptor.runtime_resolution["developer_kit_fingerprint"] == (
            fixture.settings.developer_kit_fingerprint
        )
        assert api.descriptor.runtime_resolution["extension_set"] == (
            api.extension_adapter.extension_set_reference
        )
        assert "extension_registry" in api.probes
        api.probes["extension_registry"]()

        assert api.application is not None
        assert worker.worker is not None
        request = worker_request()
        api.application.submit_canonical(
            canonical_json_bytes(request),
            context=ingress_context(request, api.descriptor),
            dispatch_window=dispatch_window(),
        )
        message = dispatched_message(publisher.messages[0])
        result = worker.worker.execute(
            planning_run_id=cast(str, message["planning_run_id"]),
            work_item_id=cast(str, message["work_item_id"]),
            worker_id=cast(str, message["worker_id"]),
        )
        assert result.disposition.value == "COMPLETED"
        final = api.application.read_planning_run(
            cast(str, message["planning_run_id"]),
            context=command_context(request),
        )
        assert final.aggregate.document["state"] == "COMPLETED"
        assert final.aggregate.document["runtime_resolution"] == (
            api.descriptor.runtime_resolution
        )
        metrics = cast(
            LoadedRuntimeExtensionAdapter, worker.extension_adapter
        ).safe_metrics()
        contributions = metrics["contributions"]
        assert len(contributions) == len(worker.extension_adapter.contributions)
        assert all(row["call_count"] >= 1 for row in contributions)
        assert all(row["success_count"] >= 1 for row in contributions)
        assert all(
            row["last_input_fingerprint"].startswith("sha256:") for row in contributions
        )
        assert all(
            row["last_output_fingerprint"].startswith("sha256:")
            for row in contributions
        )
        assert metrics["payloads_recorded"] is False
    finally:
        worker.close()
        api.close()


def test_worker_rejects_different_extension_configuration_before_result(
    tmp_path: Path,
) -> None:
    _, database_url = _database(tmp_path)
    api_fixture = runtime_extension_fixture(
        tmp_path / "api",
        database_url=database_url,
        configuration_values={"mode": "API"},
    )
    worker_fixture = runtime_extension_fixture(
        tmp_path / "worker",
        database_url=database_url,
        configuration_values={"mode": "WORKER"},
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        api_fixture.settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("extension-mismatch-001"),
        extension_artifacts=(api_fixture.artifact,),
    )
    worker = compose_runtime(
        worker_fixture.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(),
        extension_artifacts=(worker_fixture.artifact,),
    )
    try:
        assert api.descriptor.fingerprint != worker.descriptor.fingerprint
        assert api.application is not None
        assert worker.worker is not None
        request = worker_request()
        api.application.submit_canonical(
            canonical_json_bytes(request),
            context=ingress_context(request, api.descriptor),
            dispatch_window=dispatch_window(),
        )
        message = dispatched_message(publisher.messages[0])
        with pytest.raises(PlanningRunWorkerError) as captured:
            worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=cast(str, message["worker_id"]),
            )
        assert captured.value.code.value == "RUNTIME_MISMATCH"
        with api.database.engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM planning_run_worker_results")
                )
                == 0
            )
    finally:
        worker.close()
        api.close()


def test_deployable_worker_accepts_explicit_startup_artifact_provider(
    tmp_path: Path,
) -> None:
    _, database_url = _database(tmp_path)
    fixture = runtime_extension_fixture(tmp_path, database_url=database_url)
    application = create_runtime_celery_app(
        fixture.settings,
        extension_artifacts=(fixture.artifact,),
    )
    composition = getattr(application, "plantnexus_runtime_composition")
    try:
        assert composition.extension_adapter.document["mode"] == "LOADED"
        assert composition.worker is not None
    finally:
        clear_planning_run_task_executor()
        composition.close()


def test_deployable_api_accepts_explicit_startup_artifact_provider(
    tmp_path: Path,
) -> None:
    _, database_url = _database(tmp_path)
    fixture = runtime_extension_fixture(tmp_path, database_url=database_url)
    application = create_runtime_app(
        fixture.settings,
        extension_artifacts=(fixture.artifact,),
    )
    with TestClient(application) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        descriptor = application.state.aps_runtime_descriptor
        assert descriptor.runtime_resolution["extension_sdk_version"] == "1.0.0"
        assert descriptor.runtime_resolution["extension_set"] == (
            fixture.load().extension_set_reference
        )


def test_deployable_api_and_worker_use_configured_startup_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database_url = _database(tmp_path)
    fixture = runtime_extension_fixture(tmp_path, database_url=database_url)
    module = ModuleType("p8_runtime_extension_test_provider")

    def provide(_: object) -> tuple[RuntimeExtensionArtifact, ...]:
        return (fixture.artifact,)

    module.provide = provide  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    settings = fixture.settings.model_copy(
        update={
            "runtime_extension_artifact_provider": (
                "p8_runtime_extension_test_provider:provide"
            )
        }
    )

    api = create_runtime_app(settings)
    with TestClient(api) as client:
        assert client.get("/health/live").status_code == 200
        api_descriptor = api.state.aps_runtime_descriptor
        assert api_descriptor.runtime_resolution["extension_set"] == (
            fixture.load().extension_set_reference
        )

    worker_app = create_runtime_celery_app(settings)
    worker = getattr(worker_app, "plantnexus_runtime_composition")
    try:
        assert (
            worker.descriptor.runtime_resolution["extension_set"]
            == (api_descriptor.runtime_resolution["extension_set"])
        )
    finally:
        clear_planning_run_task_executor()
        worker.close()


def test_authorized_headless_output_approve_publish_read_and_export(
    tmp_path: Path,
) -> None:
    _, database_url = _database(tmp_path)
    fixture = runtime_extension_fixture(tmp_path, database_url=database_url)
    publisher = RecordingCelery()
    api = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("extension-output-001"),
        extension_artifacts=(fixture.artifact,),
    )
    worker = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(),
        extension_artifacts=(fixture.artifact,),
    )
    try:
        assert api.application is not None
        assert api.planning_workspace_application is not None
        assert worker.worker is not None
        request = worker_request()
        api.application.submit_canonical(
            canonical_json_bytes(request),
            context=ingress_context(request, api.descriptor),
            dispatch_window=dispatch_window(),
        )
        message = dispatched_message(publisher.messages[0])
        worker.worker.execute(
            planning_run_id=cast(str, message["planning_run_id"]),
            work_item_id=cast(str, message["work_item_id"]),
            worker_id=cast(str, message["worker_id"]),
        )
        schedule_repository = SqlAlchemyScheduleVersionRepository(
            api.database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        )
        with api.database.engine.connect() as connection:
            schedule_id = cast(
                str,
                connection.scalar(
                    text("SELECT schedule_version_id FROM schedule_versions")
                ),
            )
        schedule = cast(dict[str, object], schedule_repository.get(schedule_id))
        application = create_app(
            fixture.settings,
            probes=api.probes,
            planning_workspace_application=api.planning_workspace_application,
            authorization_provider=_WorkspaceAuthorizationProvider(),
            runtime_application=api.application,
            runtime_descriptor=api.descriptor,
            runtime_http_context=api.http_context_adapter,
        )
        with TestClient(application) as client:
            unauthorized = client.get(f"/api/v1/schedule-versions/{schedule_id}")
            read_ready = client.get(
                f"/api/v1/schedule-versions/{schedule_id}",
                headers={"Authorization": "Bearer p8-product-token"},
            )
            approve = _workspace_command(
                schedule,
                command_type="APPROVE",
                capability="approve",
                state="READY_FOR_REVIEW",
                target="WORKSPACE_INTERNAL",
                key="p8-product-approve-0001",
                payload={},
            )
            approved = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/approve",
                content=canonical_json_bytes(approve),
                headers=_command_headers(approve),
            )
            schedule = cast(dict[str, object], schedule_repository.get(schedule_id))
            publish = _workspace_command(
                schedule,
                command_type="PUBLISH",
                capability="publish",
                state="APPROVED",
                target="SIMULATION_INTERNAL",
                key="p8-product-publish-0001",
                payload={"previous_current_version": None},
            )
            published = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/publish",
                content=canonical_json_bytes(publish),
                headers=_command_headers(publish),
            )
            schedule = cast(dict[str, object], schedule_repository.get(schedule_id))
            export = _workspace_command(
                schedule,
                command_type="REQUEST_EXPORT",
                capability="export",
                state="PUBLISHED",
                target="SIMULATION_INTERNAL",
                key="p8-product-export-0001",
                payload={"package_profile": "p3-standard-export.v1"},
            )
            exported = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/exports",
                content=canonical_json_bytes(export),
                headers=_command_headers(export),
            )
            export_id = exported.json().get("export_job_id")
            read_export = client.get(
                f"/api/v1/export-jobs/{export_id}",
                headers={"Authorization": "Bearer p8-product-token"},
            )
            replayed_export = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/exports",
                content=canonical_json_bytes(export),
                headers=_command_headers(export),
            )

        assert unauthorized.status_code == 401
        assert read_ready.status_code == 200
        assert read_ready.json()["state"] == "READY_FOR_REVIEW"
        assert approved.status_code == 200, approved.json()
        assert approved.json()["new_version"]["state"] == "APPROVED"
        assert published.status_code == 200
        assert published.json()["published_version"]["state"] == "PUBLISHED"
        assert exported.status_code == 202
        assert read_export.status_code == 200
        assert read_export.json()["state"] == "CREATED"
        assert replayed_export.status_code == 202
        assert replayed_export.json()["export_job_id"] == export_id
        with api.database.engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT count(*) FROM publication_results")) == 1
            )
            assert connection.scalar(text("SELECT count(*) FROM export_jobs")) == 1
    finally:
        worker.close()
        api.close()
