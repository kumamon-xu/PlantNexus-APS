"""P9-05 deployed read and export boundaries over durable Runtime sources."""

from dataclasses import replace
import json
from typing import Any
from pathlib import Path
from datetime import datetime, UTC
from io import BytesIO, StringIO
from zipfile import ZipFile
import csv

import pytest

from app.domain.workspace import (
    build_workspace_query_request,
    version_reference,
    WorkspaceView,
)
from app.domain.workspace_contracts import workspace_fingerprint
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.runtime_composition import compose_runtime, RuntimeProcess
from backend.tests.integration import test_p9_manual as manual_support
from backend.tests.p8_runtime_support import FixedRuntimeClock
from backend.tests.integration.test_p9_manual import (
    counts,
    move,
    post,
    result_source,
    command,
)

runtime = manual_support.runtime


def test_celery_duplicate_delivery_is_requeued_until_lease_expiry() -> None:
    from celery import Celery
    from app.jobs.runtime_export_task import register_runtime_export_task, EXPORT_TASK
    from types import SimpleNamespace
    from typing import cast
    from app.jobs.runtime_export_task import RuntimeExports

    observed: list[Any] = []

    def execute(message: Any) -> dict[str, object]:
        observed.append(message)
        return {
            "disposition": "DUPLICATE_DELIVERY" if len(observed) == 1 else "EXPIRED"
        }

    application = Celery(
        "p9-export-delivery", broker="memory://", backend="cache+memory://"
    )
    try:
        register_runtime_export_task(
            application,
            cast(RuntimeExports, SimpleNamespace(execute=execute, lease_seconds=120)),
        )
        result = application.tasks[EXPORT_TASK].apply(args=({"fixture": "duplicate"},))
        assert result.get() == {"disposition": "EXPIRED"}
        assert len(observed) == 2
    finally:
        application.close()


@pytest.fixture(autouse=True)
def export_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = manual_support.runtime_settings
    root = tmp_path / "exports"
    root.mkdir()

    def settings(*args: Any, **kwargs: Any) -> Any:
        return original(*args, **kwargs).model_copy(
            update={
                "runtime_export_storage_root": root,
                "runtime_export_scenario_directory": root,
            }
        )

    monkeypatch.setattr(manual_support, "runtime_settings", settings)


def publish(runtime: Any) -> Any:
    approved = result_source(
        runtime,
        post(
            runtime, command(runtime.source, "APPROVE", key="p9-readmodel-approve-01")
        ),
    )
    response = post(
        runtime,
        command(
            approved,
            "PUBLISH",
            {"previous_current_version": None},
            key="p9-readmodel-publish-01",
        ),
    )
    assert response.status_code == 200, response.text
    return runtime.schedules.get(approved["schedule_version_id"])


def create_export(runtime: Any, published: Any) -> Any:
    # Explicit synthetic fixture manifest; Runtime never synthesizes missing evidence.
    from app.infrastructure.canonical_ingress_repository import (
        SqlAlchemyCanonicalIngressRepository,
    )
    from app.infrastructure.workspace_persistence import WorkspaceDataPlane

    record = SqlAlchemyCanonicalIngressRepository(
        runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_by_planning_run_id(published["lineage"]["planning_run_id"])
    assert record is not None
    snapshot, problem = record.snapshot.document, record.problem.document
    provenance = snapshot.get("synthetic_provenance")
    assert provenance is not None
    manifest = {
        "correctness_manifest_version": "p2-correctness-manifest.v1",
        "scenario": {
            "scenario_id": provenance["scenario_id"],
            "scenario_version": provenance["scenario_version"],
        },
        "factory_profile": {
            "profile_id": provenance["factory_profile_id"],
            "profile_version": provenance["profile_version"],
        },
        "assembler": {
            "generator_id": provenance["generator_id"],
            "generator_version": provenance["generator_version"],
        },
        "seed": provenance["seed"],
        "expected_artifacts": {
            "import_dataset_hash": snapshot["import_package"]["dataset_hash"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "problem_hash": problem["problem_hash"],
        },
    }
    (
        runtime.settings.runtime_export_scenario_directory
        / (problem["problem_hash"].removeprefix("sha256:") + ".json")
    ).write_text(json.dumps(manifest), encoding="utf-8")
    value = command(
        published,
        "REQUEST_EXPORT",
        {"package_profile": "p3-standard-export.v1"},
        key="p9-readmodel-export-01",
    )
    value.update(
        required_capability="export",
        target="SIMULATION_INTERNAL",
        idempotency_scope=f"SIMULATION/REQUEST_EXPORT/{published['schedule_version_id']}/SIMULATION_INTERNAL",
    )
    value["request_fingerprint"] = workspace_command_fingerprint(value)
    response = runtime.client.post(
        f"/api/v1/schedule-versions/{published['schedule_version_id']}/exports",
        json=value,
        headers={
            "Authorization": "Bearer p9-test-token",
            "Idempotency-Key": value["idempotency_key"],
            "X-Correlation-Id": value["correlation_id"],
        },
    )
    return response


def query(
    runtime: Any,
    view: str,
    *,
    source: Any = None,
    size: int = 100,
    cursor: str | None = None,
) -> Any:
    source = source or runtime.source
    document = build_workspace_query_request(
        view=WorkspaceView(view),
        data_plane="SIMULATION",
        environment=source["environment"],
        synthetic=True,
        synthetic_provenance=source["synthetic_provenance"],
        correlation_id="p9-read-query",
        schedule_version_reference=version_reference(source),
        page_size=size,
        cursor=cursor,
    )
    if view in {"DATA_HEALTH", "IMPORT_RUNS", "PLANNING_RUNS"}:
        path = "/api/v1/workspace/" + view.lower().replace("_", "-")
    elif view == "AUDIT":
        path = f"/api/v1/schedule-versions/{source['schedule_version_id']}/audit-events"
    else:
        path = f"/api/v1/schedule-versions/{source['schedule_version_id']}/workspace/{view}"
    return runtime.client.get(
        path,
        params={"query": json.dumps(document)},
        headers={
            "Authorization": "Bearer p9-test-token",
            "X-Correlation-Id": "p9-read-query",
        },
    )


@pytest.mark.parametrize(
    "view",
    [
        "DATA_HEALTH",
        "IMPORT_RUNS",
        "PLANNING_RUNS",
        "ORDERS",
        "OPERATIONS",
        "RESOURCES",
        "CALENDARS",
        "GANTT",
        "RESOURCE_LOAD",
        "KPI",
        "DIAGNOSTICS",
        "LOCKS",
        "AUDIT",
    ],
)
def test_runtime_read_views_are_consistent_and_read_only(
    runtime: Any, view: str
) -> None:
    before = counts(runtime)
    if view == "AUDIT":
        runtime.identity.principal = replace(
            runtime.identity.principal, resolved_capabilities=frozenset({"audit"})
        )
    response = query(runtime, view)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["document"]["result"]["found"] is True
    for item in result["items"]:
        assert item["payload_fingerprint"] == workspace_fingerprint(item["payload"])
    assert counts(runtime) == before


def test_runtime_export_worker_and_verified_download(runtime: Any) -> None:
    published = publish(runtime)
    created = create_export(runtime, published)
    assert created.status_code == 202, created.text
    job = created.json()
    assert job["state"] == "EXPORTING"
    worker = compose_runtime(
        runtime.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 1, 10, tzinfo=UTC)),
    )
    try:
        assert worker.export_worker is not None
        message = {
            "message_version": "runtime-export-message.v1",
            "export_job_id": job["export_job_id"],
            "attempt": job["attempt"],
            "lease_reference": job["lease_reference"],
        }
        result = worker.export_worker.execute(message)
        assert result == {"disposition": "EXPORTED"}, worker.export_worker.jobs.get(
            job["export_job_id"]
        ).document
        assert worker.export_worker.execute(message) == {
            "disposition": "STALE_DELIVERY"
        }
        response = runtime.client.get(
            f"/api/v1/export-jobs/{job['export_job_id']}/download",
            headers={
                "Authorization": "Bearer p9-test-token",
                "X-Correlation-Id": "p9-download",
            },
        )
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"PK")
        with ZipFile(BytesIO(response.content)) as archive:
            assert json.loads(archive.read("schedule_version.json")) == published
            kpi = json.loads(archive.read("kpi.json"))
            rows = list(
                csv.DictReader(StringIO(archive.read("resource_load.csv").decode()))
            )
            loads = query(runtime, "RESOURCE_LOAD", source=published)
            assert loads.status_code == 200, loads.text
            expected = {
                item["payload"]["resource_id"]: item["payload"]["planned_busy_seconds"]
                for item in loads.json()["items"]
            }
            assert {
                row["resource_id"]: int(row["planned_busy_seconds"]) for row in rows
            } == expected
            assert {
                row["resource_id"]: row["planned_busy_seconds"]
                for row in kpi["resources"]
            } == expected
            assert archive.read("standard_package.xlsx").startswith(b"PK")
        before = counts(runtime)
        runtime.identity.principal = replace(
            runtime.identity.principal, export_job_scope=frozenset()
        )
        assert (
            runtime.client.get(
                f"/api/v1/export-jobs/{job['export_job_id']}/download",
                headers={"Authorization": "Bearer p9-test-token"},
            ).status_code
            == 403
        )
        runtime.identity.principal = replace(
            runtime.identity.principal, export_job_scope=frozenset({"*"})
        )
        payload = next(
            runtime.settings.runtime_export_storage_root.rglob(
                "schedule_operations.csv"
            )
        )
        payload.write_bytes(payload.read_bytes() + b"tampered")
        rejected = runtime.client.get(
            f"/api/v1/export-jobs/{job['export_job_id']}/download",
            headers={"Authorization": "Bearer p9-test-token"},
        )
        assert rejected.status_code != 200
        assert counts(runtime) == before
    finally:
        worker.close()


def test_runtime_read_pagination_and_scope(runtime: Any) -> None:
    first = query(runtime, "OPERATIONS", size=1)
    assert first.status_code == 200, first.text
    cursor = first.json()["document"]["result"]["next_cursor"]
    assert cursor
    second = query(runtime, "OPERATIONS", size=1, cursor=cursor)
    assert second.status_code == 200, second.text
    assert first.json()["items"][0]["item_id"] != second.json()["items"][0]["item_id"]
    runtime.identity.principal = replace(
        runtime.identity.principal, schedule_version_scope=frozenset()
    )
    assert query(runtime, "OPERATIONS").status_code == 403
    runtime.identity.principal = replace(
        runtime.identity.principal, planning_run_scope=frozenset()
    )
    empty = query(runtime, "PLANNING_RUNS")
    assert empty.status_code == 200, empty.text
    assert empty.json()["items"] == []


def test_manual_source_mismatch_is_explicit_and_read_only(runtime: Any) -> None:
    moved = post(runtime, move(runtime.source))
    assert moved.status_code == 200, moved.text
    manual = result_source(runtime, moved)
    before = counts(runtime)
    response = query(runtime, "KPI", source=manual)
    assert response.status_code == 422, response.text
    assert counts(runtime) == before


def export_control(runtime: Any, job: Any, kind: str, key: str) -> Any:
    value = command(
        runtime.source, "REQUEST_EXPORT", {"expected_attempt": job["attempt"]}, key=key
    )
    value.update(
        command_type=kind,
        required_capability="export",
        target="SIMULATION_INTERNAL",
        source_id=job["export_job_id"],
        expected_state=job["state"],
        expected_content_fingerprint=job["schedule_version"]["content_fingerprint"],
        idempotency_scope=f"SIMULATION/{kind}/{job['export_job_id']}/SIMULATION_INTERNAL",
    )
    value["request_fingerprint"] = workspace_command_fingerprint(value)
    return runtime.client.post(
        f"/api/v1/export-jobs/{job['export_job_id']}/{'retry' if kind == 'RETRY_EXPORT' else 'cancel'}",
        json=value,
        headers={
            "Authorization": "Bearer p9-test-token",
            "Idempotency-Key": key,
            "X-Correlation-Id": value["correlation_id"],
        },
    )


def test_export_retry_cancel_replay_and_stale_delivery(
    runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = publish(runtime)
    # Fail the broker only after the original Solver delivery succeeded.
    original = manual_support.RecordingCelery.send_task

    def failed(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("credential-do-not-leak")

    monkeypatch.setattr(manual_support.RecordingCelery, "send_task", failed)
    response = create_export(runtime, published)
    assert response.status_code == 202, response.text
    failed_job = response.json()
    assert failed_job["state"] == "EXPORT_FAILED"
    monkeypatch.setattr(manual_support.RecordingCelery, "send_task", original)
    # A receipt append failure must roll the state CAS and lifecycle audit back.
    from app.infrastructure.audit_repository import SqlAlchemyAuditRepository

    append = SqlAlchemyAuditRepository.append_in_transaction

    def broken_receipt(self: Any, connection: Any, document: Any) -> Any:
        if str(document["audit_event_id"]).startswith("audit-export-command-"):
            raise RuntimeError("audit-secret-do-not-leak")
        return append(self, connection, document)

    before = counts(runtime)
    monkeypatch.setattr(
        SqlAlchemyAuditRepository, "append_in_transaction", broken_receipt
    )
    rejected = export_control(
        runtime, failed_job, "RETRY_EXPORT", "p9-export-retry-0001"
    )
    assert rejected.status_code == 500 and "audit-secret" not in rejected.text
    assert counts(runtime) == before
    current = runtime.client.get(
        f"/api/v1/export-jobs/{failed_job['export_job_id']}",
        headers={"Authorization": "Bearer p9-test-token"},
    )
    assert current.json()["state"] == "EXPORT_FAILED" and current.json()["attempt"] == 1
    monkeypatch.setattr(SqlAlchemyAuditRepository, "append_in_transaction", append)
    retried = export_control(
        runtime, failed_job, "RETRY_EXPORT", "p9-export-retry-0001"
    )
    assert retried.status_code == 202, retried.text
    job = retried.json()
    assert job["state"] == "EXPORTING" and job["attempt"] == 2
    replay = export_control(runtime, failed_job, "RETRY_EXPORT", "p9-export-retry-0001")
    assert replay.status_code == 202, replay.text
    assert replay.json()["attempt"] == 2
    stale = export_control(runtime, failed_job, "RETRY_EXPORT", "p9-export-retry-0002")
    assert stale.status_code == 409, stale.text
    cancelled = export_control(runtime, job, "CANCEL_EXPORT", "p9-export-cancel-001")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "CANCELLED"
    replay = export_control(runtime, job, "CANCEL_EXPORT", "p9-export-cancel-001")
    assert replay.status_code == 200, replay.text
    conflict = export_control(
        runtime, cancelled.json(), "CANCEL_EXPORT", "p9-export-cancel-001"
    )
    assert conflict.status_code == 409, conflict.text
    worker = compose_runtime(
        runtime.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 1, 10, tzinfo=UTC)),
    )
    try:
        assert worker.export_worker is not None
        assert worker.export_worker.execute(
            {
                "message_version": "runtime-export-message.v1",
                "export_job_id": job["export_job_id"],
                "attempt": job["attempt"],
                "lease_reference": job["lease_reference"],
            }
        ) == {"disposition": "STALE_DELIVERY"}
    finally:
        worker.close()


def test_get_version_preserves_document_and_filters_actions(runtime: Any) -> None:
    runtime.identity.principal = replace(
        runtime.identity.principal, resolved_capabilities=frozenset({"view"})
    )
    response = runtime.client.get(
        f"/api/v1/schedule-versions/{runtime.source['schedule_version_id']}",
        headers={"Authorization": "Bearer p9-test-token"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["schedule_version"] == runtime.source
    assert response.json()["allowed_actions"] == ["view"]
    result = query(runtime, "KPI")
    assert result.status_code == 200, result.text
    assert result.json()["document"]["result"]["allowed_actions"] == ["view"]


def test_export_duplicate_claim_expiry_and_explicit_retry(runtime: Any) -> None:
    published = publish(runtime)
    response = create_export(runtime, published)
    assert response.status_code == 202, response.text
    job = response.json()
    message = {
        "message_version": "runtime-export-message.v1",
        "export_job_id": job["export_job_id"],
        "attempt": job["attempt"],
        "lease_reference": job["lease_reference"],
    }
    marker = (
        runtime.settings.runtime_export_storage_root
        / f"{job['export_job_id']}-{job['attempt']}.claim"
    )
    marker.mkdir()
    worker = compose_runtime(
        runtime.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 1, 10, tzinfo=UTC)),
    )
    try:
        assert worker.export_worker is not None
        assert worker.export_worker.execute(message) == {
            "disposition": "DUPLICATE_DELIVERY"
        }
        worker.export_worker.clock = FixedRuntimeClock(
            datetime(2026, 9, 6, 1, 4, 0, tzinfo=UTC)
        )
        assert worker.export_worker.execute(message) == {"disposition": "EXPIRED"}
        failed = worker.export_worker.jobs.get(job["export_job_id"]).document
        runtime.app.state.planning_workspace_clock = lambda: "2026-09-06T01:04:01Z"
        retried = export_control(
            runtime, failed, "RETRY_EXPORT", "p9-expired-retry-0001"
        )
        assert retried.status_code == 202, retried.text
        assert retried.json()["attempt"] == 2
        assert marker.is_dir()
    finally:
        worker.close()


def test_pending_run_catalog_and_completed_version_comparison(runtime: Any) -> None:
    from app.data_validation.canonical_ingress import request_fingerprint
    from backend.tests.contract.p8_headless_http_support import create_headers
    from sqlalchemy import text

    request = manual_support.request_with_alternative_resource()
    request.update(
        request_id="REQUEST-P9-READ-SECOND",
        idempotency_key="p9-read-second-run-0001",
        correlation_id="p9-read-second-run",
    )
    request["request_fingerprint"] = request_fingerprint(request)
    response = runtime.client.post(
        "/api/v1/planning-runs", json=request, headers=create_headers(request)
    )
    assert response.status_code == 202, response.text
    for view in ("PLANNING_RUNS", "IMPORT_RUNS", "DATA_HEALTH"):
        response = query(runtime, view)
        assert response.status_code == 200, response.text
    pending = query(runtime, "PLANNING_RUNS").json()["items"]
    assert len(pending) == 2
    assert len({item["payload"]["state"] for item in pending}) == 2
    run_id = next(
        item["item_id"] for item in pending if item["payload"]["state"] != "COMPLETED"
    )
    read = runtime.client.get(
        f"/api/v1/planning-runs/{run_id}",
        headers={"Authorization": "Bearer p9-test-token"},
    )
    assert read.status_code == 200, read.text
    worker = compose_runtime(
        runtime.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 10, tzinfo=UTC)),
    )
    try:
        with runtime.db.connect() as connection:
            work_id = connection.scalar(
                text(
                    "SELECT work_item_id FROM planning_run_work_items WHERE planning_run_id = :run"
                ),
                {"run": run_id},
            )
        assert worker.worker is not None
        result = worker.worker.execute(
            planning_run_id=run_id,
            work_item_id=work_id,
            worker_id="worker:p9-read-second",
        )
        assert result.disposition.value == "COMPLETED"
        with runtime.db.connect() as connection:
            version_ids = connection.scalars(
                text("SELECT schedule_version_id FROM schedule_versions")
            ).all()
        compared = runtime.schedules.get(
            next(
                value
                for value in version_ids
                if value != runtime.source["schedule_version_id"]
            )
        )
        document = build_workspace_query_request(
            view=WorkspaceView.VERSION_COMPARISON,
            data_plane="SIMULATION",
            environment=runtime.source["environment"],
            synthetic=True,
            synthetic_provenance=runtime.source["synthetic_provenance"],
            correlation_id="p9-comparison",
            schedule_version_reference=version_reference(runtime.source),
        )
        headers = {
            "Authorization": "Bearer p9-test-token",
            "X-Correlation-Id": "p9-comparison",
            "X-Compared-Schedule-Version-Id": compared["schedule_version_id"],
            "X-Compared-State": compared["state"],
            "X-Compared-Content-Fingerprint": compared["content_fingerprint"],
        }
        before = counts(runtime)
        response = runtime.client.post(
            "/api/v1/schedule-version-comparisons", json=document, headers=headers
        )
        assert response.status_code == 200, response.text
        assert "comparison" in response.json()
        assert counts(runtime) == before
        headers["X-Compared-Content-Fingerprint"] = "sha256:" + "f" * 64
        assert (
            runtime.client.post(
                "/api/v1/schedule-version-comparisons", json=document, headers=headers
            ).status_code
            == 409
        )
    finally:
        worker.close()
