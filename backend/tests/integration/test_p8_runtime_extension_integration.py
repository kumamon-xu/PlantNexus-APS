"""API/Worker composition parity and lineage integration for TASK-P8-13."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from celery import Celery
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.api.app import create_runtime_app
from app.data_validation.canonical_ingress import canonical_json_bytes
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
            assert connection.scalar(text("SELECT count(*) FROM planning_run_worker_results")) == 0
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
