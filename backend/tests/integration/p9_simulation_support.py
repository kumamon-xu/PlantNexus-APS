"""P9 measurement harness: real TCP, isolated Redis and the formal Worker.

Test identity and a fixed authority clock are explicit; no business application,
Solver, Validator, persistence or broker is replaced.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
import sys
import traceback
from pathlib import Path
from time import perf_counter, sleep
from types import SimpleNamespace
from typing import Any, cast

from celery.contrib.testing.worker import start_worker
import httpx
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from app.api.app import create_runtime_app
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    request_fingerprint,
)
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.celery_app import create_celery_app
from app.jobs.planning_run_task import clear_planning_run_task_executor
from app.jobs.runtime_export_task import register_runtime_export_task
from app.planning.policy import simulation_solve_limits
from app.planning.validation.problem_schedule_validator import ProblemScheduleValidator
from app.runtime_composition import compose_runtime, RuntimeProcess
from app.simulation.baselines.reference_schedulers import schedule_all_references
from app.simulation.benchmarks.runner import _complexity_metrics
from backend.tests.contract.p8_headless_http_support import (
    StaticAuthorizationProvider,
    authorization_policy,
    create_headers,
    HEADLESS_NOW,
)
from backend.tests.integration.test_p9_consumers import serve
from backend.tests.integration.test_p9_manual import (
    WorkspaceIdentity,
    command,
    post,
    result_source,
)
from backend.tests.integration.test_p9_readmodel import create_export
from backend.tests.p8_runtime_support import runtime_settings, FixedRuntimeClock
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


def process_peak_rss_mb() -> float:
    """OS high-water RSS includes native Solver memory; not tracemalloc alone."""
    if sys.platform != "win32":
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / (1024 * 1024 if sys.platform == "darwin" else 1024)
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_rss",
                "rss",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
            )
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = wintypes.HANDLE
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if not query(current(), ctypes.byref(counters), counters.cb):
        raise OSError("P9_RSS_MEASUREMENT_FAILED")
    return counters.peak_rss / (1024 * 1024)


def measure(
    root: Path,
    directory: Path,
    generated: dict[str, Any],
    broker: str,
    code_commit: str,
    repetitions: int = 4,
) -> list[dict[str, Any]]:
    directory.mkdir(parents=True, exist_ok=False)
    engine, _ = migrated_engine(directory / "runtime.db")
    url = str(engine.url)
    engine.dispose()
    settings = runtime_settings(directory, database_url=url)
    assert settings.runtime_solve_limits_path is not None
    assert settings.runtime_http_policy_path is not None
    limits = simulation_solve_limits(
        limits_id="LIMITS-P9-SIMULATION",
        limits_revision="1.0.0",
        source_record_id="P9-SIMULATION-LIMITS",
        max_wall_time_seconds=generated["profile"]["max_wall_time_seconds"],
        max_workers=1,
        random_seed=generated["seed"],
    )
    settings.runtime_solve_limits_path.write_text(json.dumps(limits), encoding="utf-8")
    request = worker_request()
    request["payload"] = generated["package"]
    request["payload_fingerprint"] = generated["input_fingerprint"]
    factory = request["payload"]["records"]["factories"][0]["factory_id"]
    request["requested_scope"]["factory_id"] = factory
    request["planning_inputs"]["solve_limits"] = {
        "document_version": limits["solve_limits_version"],
        "artifact_id": limits["limits_id"],
        "fingerprint": canonical_fingerprint(limits),
    }
    source_versions = request["payload"]["source_versions"]
    authority = request["source_authority"]
    mapping = authority["mapping_provenance"][0]
    binding = authority["bindings"][0]
    authority["bindings"] = [
        {
            **binding,
            "source_system": source,
            "source_version": version,
            "canonical_collections": sorted(
                k
                for k, records in request["payload"]["records"].items()
                if isinstance(records, list) and records
            ),
        }
        for source, version in source_versions.items()
    ]
    authority["mapping_provenance"] = [
        {**mapping, "source_system": source, "source_version": version}
        for source, version in source_versions.items()
    ]
    http_policy = json.loads(
        settings.runtime_http_policy_path.read_text(encoding="utf-8")
    )
    scope = http_policy["scopes"][0]
    scope["factory_id"] = factory
    scope["build_plan"] = generated["build_plan"]
    settings.runtime_http_policy_path.write_text(
        json.dumps(http_policy), encoding="utf-8"
    )
    exports = directory / "exports"
    exports.mkdir()
    settings = settings.model_copy(
        update={
            "code_commit": code_commit,
            "celery_broker_url": SecretStr(broker + "/1"),
            "celery_result_backend_url": SecretStr(broker + "/2"),
            "runtime_export_storage_root": exports,
            "runtime_export_scenario_directory": exports,
        }
    )
    policy = authorization_policy(
        scopes=(
            (
                request["requested_scope"]["tenant_id"],
                factory,
                request["requested_scope"]["planning_scope_id"],
            ),
        )
    )
    app = create_runtime_app(
        settings,
        authorization_provider=WorkspaceIdentity(),
        host_identity_provider=StaticAuthorizationProvider(),
        host_authorization_policy=policy,
    )
    app.state.headless_clock = lambda: HEADLESS_NOW
    app.state.planning_workspace_clock = lambda: "2026-09-06T01:01:00Z"
    worker = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 10, tzinfo=UTC)),
    )
    assert worker.worker is not None and worker.export_worker is not None
    # Observe exceptions swallowed by the export task's public error boundary.
    # Delegate unchanged to the real materializer; only failed runs write a trace.
    materializer = cast(Any, worker.export_worker.worker)
    run_claimed = materializer.run_claimed

    def observed_materialization(*args: Any, **kwargs: Any) -> Any:
        try:
            return run_claimed(*args, **kwargs)
        except Exception:
            with (directory / "export-failure.log").open("a", encoding="utf-8") as log:
                traceback.print_exc(file=log)
            raise

    materializer.run_claimed = observed_materialization
    celery = create_celery_app(settings, executor=worker.worker)
    register_runtime_export_task(celery, worker.export_worker)
    db = create_engine(url)
    schedules = SqlAlchemyScheduleVersionRepository(
        db, data_plane=WorkspaceDataPlane.SIMULATION
    )
    ingress = SqlAlchemyCanonicalIngressRepository(
        db, data_plane=WorkspaceDataPlane.SIMULATION
    )
    samples = []
    try:
        with (
            serve(app) as base_url,
            cast(Any, start_worker)(
                celery,
                pool="solo",
                concurrency=1,
                perform_ping_check=False,
                shutdown_timeout=15,
            ),
        ):
            with httpx.Client(base_url=base_url, timeout=30) as client:
                previous = None
                for index in range(repetitions):
                    document = deepcopy(request)
                    label = f"{generated['scenario_id']}-{index}"
                    document.update(
                        request_id=label,
                        correlation_id=label,
                        idempotency_key=f"p9-qualification-{label}",
                    )
                    document["request_fingerprint"] = request_fingerprint(document)
                    started = perf_counter()
                    accepted = client.post(
                        "/api/v1/planning-runs",
                        json=document,
                        headers=create_headers(document),
                    )
                    if accepted.status_code != 202:
                        raise AssertionError(accepted.text)
                    ingress_seconds = perf_counter() - started
                    run_id = accepted.json()["accepted"]["planning_run"][
                        "planning_run_id"
                    ]
                    checkpoint = None
                    version_id = None
                    deadline = perf_counter() + 45
                    while perf_counter() < deadline:
                        with db.connect() as connection:
                            raw = connection.scalar(
                                text(
                                    "SELECT result_json FROM planning_run_worker_results WHERE planning_run_id=:id"
                                ),
                                {"id": run_id},
                            )
                            versions = [
                                json.loads(value)
                                for value in connection.scalars(
                                    text("SELECT document_json FROM schedule_versions")
                                )
                            ]
                            version_id = next(
                                (
                                    v["schedule_version_id"]
                                    for v in versions
                                    if v["lineage"]["planning_run_id"] == run_id
                                ),
                                None,
                            )
                        if raw and (
                            version_id
                            or json.loads(raw)["outcome_state"] != "COMPLETED"
                        ):
                            checkpoint = json.loads(raw)
                            break
                        sleep(0.02)
                    if checkpoint is None:
                        raise AssertionError(f"P9_RUNTIME_NOT_COMPLETED: {run_id}")
                    if "expected_terminal" in generated:
                        assert (
                            checkpoint["outcome_state"]
                            == generated["expected_terminal"]
                        ), checkpoint
                        assert version_id is None
                        assert checkpoint["documents"][
                            "planning_solution"
                        ] is None or not checkpoint["documents"][
                            "planning_solution"
                        ].get("assignments")
                        return [
                            {
                                "scenario_id": generated["scenario_id"],
                                "status": checkpoint["outcome_state"],
                                "candidate_count": 0,
                                "input_fingerprint": generated["input_fingerprint"],
                                "checkpoint": checkpoint,
                                "elapsed_seconds": perf_counter() - started,
                            }
                        ]
                    assert version_id is not None
                    record = ingress.get_by_planning_run_id(run_id)
                    assert record is not None
                    problem = record.problem.document
                    documents = checkpoint["documents"]
                    solution, solver, validation = (
                        documents[k]
                        for k in (
                            "planning_solution",
                            "solver_report",
                            "validation_report",
                        )
                    )
                    assert validation["status"] == "PASS"
                    runtime = SimpleNamespace(
                        client=client, db=db, schedules=schedules, settings=settings
                    )
                    source = schedules.get(version_id)
                    assert source is not None
                    approved = result_source(
                        runtime,
                        post(
                            runtime, command(source, "APPROVE", key=label + "-approve")
                        ),
                    )
                    publication = post(
                        runtime,
                        command(
                            approved,
                            "PUBLISH",
                            {"previous_current_version": previous},
                            key=label + "-publish",
                        ),
                    )
                    assert publication.status_code == 200, publication.text
                    published = schedules.get(version_id)
                    assert published is not None
                    previous = {
                        k: published[k]
                        for k in ("schedule_version_id", "state", "content_fingerprint")
                    }
                    export_started = perf_counter()
                    created = create_export(runtime, published)
                    assert created.status_code == 202, created.text
                    job_id = created.json()["export_job_id"]
                    deadline = perf_counter() + 45
                    downloaded = None
                    while perf_counter() < deadline:
                        downloaded = client.get(
                            f"/api/v1/export-jobs/{job_id}/download",
                            headers={"Authorization": "Bearer p9-test-token"},
                        )
                        if downloaded.status_code == 200:
                            break
                        sleep(0.02)
                    assert downloaded is not None and downloaded.status_code == 200, (
                        downloaded.text if downloaded is not None else "NO_RESPONSE"
                    )
                    export_seconds = perf_counter() - export_started
                    end_to_end_seconds = perf_counter() - started
                    # Independently corrupt a returned candidate; never call Solver builders.
                    illegal = deepcopy(solution)
                    illegal["assignments"][0]["resource_id"] = "P9-NONEXISTENT-RESOURCE"
                    rejected = False
                    rejection_evidence = None
                    try:
                        rejection_evidence = ProblemScheduleValidator().validate(
                            problem, illegal
                        )
                        rejected = rejection_evidence["status"] != "PASS"
                    except ValueError as error:
                        rejected = True
                        rejection_evidence = {
                            "error_type": type(error).__name__,
                            "message": str(error),
                        }
                    assert rejected
                    references = list(schedule_all_references(problem))
                    timings = solver["timings"]
                    measurements = {
                        k: timings[k]
                        for k in (
                            "model_build_seconds",
                            "first_feasible_seconds",
                            "solve_seconds",
                            "validation_seconds",
                        )
                    }
                    measurements.update(
                        ingress_seconds=ingress_seconds,
                        export_seconds=export_seconds,
                        end_to_end_seconds=end_to_end_seconds,
                        memory_peak_mb=solver["memory_peak_mb"],
                        process_peak_rss_mb=process_peak_rss_mb(),
                    )
                    sample = {
                        "scenario_id": generated["scenario_id"],
                        "seed": generated["seed"],
                        "index": index,
                        "input_fingerprint": generated["input_fingerprint"],
                        "snapshot_hash": record.snapshot.snapshot_hash,
                        "problem_hash": problem["problem_hash"],
                        "runtime_resolution": record.document["runtime_resolution"],
                        "solver_report": solver,
                        "validation_report": validation,
                        "quality": solution["objective_stage_results"],
                        "references": references,
                        "measurements": measurements,
                        "status": solution["solver_status"],
                        "complexity": _complexity_metrics(
                            cast(
                                Any,
                                SimpleNamespace(
                                    problem=problem,
                                    snapshot_document=record.snapshot.document,
                                ),
                            ),
                            SimpleNamespace(solution=solution),
                        ),
                        "invalid_candidate_rejected": rejected,
                        "invalid_candidate_evidence": rejection_evidence,
                        "export_bytes": len(downloaded.content),
                    }
                    (directory / f"sample-{index}.json").write_text(
                        json.dumps(sample, indent=2), encoding="utf-8"
                    )
                    samples.append(sample)
    finally:
        celery.close()
        worker.close()
        db.dispose()
        clear_planning_run_task_executor()
    return samples
