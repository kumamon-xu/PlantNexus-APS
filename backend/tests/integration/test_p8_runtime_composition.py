"""Integration evidence for TEST-P8-APPLICATION-COMPOSITION-001."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from celery import Celery
from fastapi.testclient import TestClient

from app.api.app import create_runtime_app
from app.application.runtime_composition_check import run_checks
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.jobs.celery_app import create_runtime_celery_app
from app.jobs.planning_run_task import (
    PLANNING_RUN_SOLVER_MESSAGE_VERSION,
    PLANNING_RUN_SOLVER_TASK,
    clear_planning_run_task_executor,
)
from app.runtime_composition import RuntimeProcess, compose_runtime
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    FixedRuntimeClock,
    RecordingCelery,
    command_context,
    dispatch_window,
    dispatched_message,
    ingress_context,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


def _migrated_settings(tmp_path: Path):
    database_path = tmp_path / "runtime.db"
    seed_engine, _ = migrated_engine(database_path)
    seed_engine.dispose()
    database_url = f"sqlite:///{database_path.as_posix()}"
    return runtime_settings(tmp_path, database_url=database_url)


def test_runtime_composition_machine_report_is_complete() -> None:
    root = Path(__file__).resolve().parents[3]
    report, manifest = run_checks(root)
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P8-06"
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert manifest["status"] == "PASS"
    assert manifest["issues"] == []
    assert len(manifest["processes"]) == 2


def test_api_and_worker_share_one_descriptor_and_complete_real_chain(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    publisher = RecordingCelery()
    api = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("runtime-dispatch-001"),
    )
    worker = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(),
    )
    try:
        assert api.application is not None
        assert api.worker is None
        assert worker.application is None
        assert worker.worker is not None
        assert api.descriptor.canonical_bytes == worker.descriptor.canonical_bytes
        assert api.descriptor.fingerprint == worker.descriptor.fingerprint
        assert api.descriptor.document["extension_adapter"] == {
            "adapter_version": "runtime-extension-adapter.v1",
            "configuration_fingerprint": api.descriptor.document[
                "extension_adapter"
            ]["configuration_fingerprint"],
            "extensions": [],
            "load_policy": "DISABLED_UNTIL_P8_13",
            "mode": "EMPTY",
        }

        request = worker_request()
        submitted = api.application.submit_canonical(
            canonical_json_bytes(request),
            context=ingress_context(request, api.descriptor),
            dispatch_window=dispatch_window(),
        )
        assert submitted.ingress is not None
        assert submitted.ingress.result["disposition"] == "ACCEPTED"
        assert submitted.planning_run is not None
        assert submitted.planning_run.attempts[-1].document["status"] == "QUEUED"
        assert submitted.dispatch is not None
        assert len(publisher.messages) == 1
        message = dispatched_message(publisher.messages[0])
        assert message == {
            "message_version": PLANNING_RUN_SOLVER_MESSAGE_VERSION,
            "planning_run_id": submitted.planning_run.aggregate.document[
                "planning_run_id"
            ],
            "work_item_id": submitted.planning_run.work_items[-1].document[
                "work_item_id"
            ],
            "worker_id": "worker:runtime-dispatch-001",
        }

        execution = worker.worker.execute(
            planning_run_id=cast(str, message["planning_run_id"]),
            work_item_id=cast(str, message["work_item_id"]),
            worker_id=cast(str, message["worker_id"]),
        )
        assert execution.disposition.value == "COMPLETED"
        final = api.application.read_planning_run(
            cast(str, message["planning_run_id"]),
            context=command_context(request),
        )
        assert final.aggregate.document["state"] == "COMPLETED"
        assert final.aggregate.document["artifacts"]["schedule_version"] is not None
    finally:
        worker.close()
        api.close()


def test_deployable_api_entrypoint_attaches_runtime_and_headless_routes(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    application = create_runtime_app(settings)
    with TestClient(application) as client:
        live = client.get("/health/live")
        route_paths = {
            getattr(route, "path", None) for route in application.routes
        }
        assert live.status_code == 200
        assert application.state.aps_runtime_application is not None
        assert application.state.aps_runtime_descriptor is not None
        assert application.state.aps_runtime_http_context is not None
        assert len(
            {path for path in route_paths if str(path).startswith("/api/v1/")}
        ) == 31


def test_deployable_worker_entrypoint_binds_real_executor(tmp_path: Path) -> None:
    settings = _migrated_settings(tmp_path)
    application = create_runtime_celery_app(settings)
    composition = cast(
        Any, getattr(application, "plantnexus_runtime_composition")
    )
    try:
        assert PLANNING_RUN_SOLVER_TASK in application.tasks
        assert composition.process is RuntimeProcess.WORKER
        assert composition.worker is not None
        assert composition.application is None
        assert composition.safe_manifest()["secrets_embedded"] is False
    finally:
        clear_planning_run_task_executor()
        composition.close()
