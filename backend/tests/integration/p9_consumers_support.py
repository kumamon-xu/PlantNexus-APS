"""Formal Runtime request preparation, Worker execution and recovery."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast


from app.data_validation.canonical_ingress import canonical_fingerprint
from app.domain.execution_contracts import replan_request_fingerprint
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.planning.policy.freeze_window import simulation_replan_policy
from app.planning.problem.builder import build_planning_problem_v2
from app.planning.problem.freeze_projection import project_effective_locks
from backend.tests.integration import test_p9_events as event_support


def prepare_request(
    events: Any, base: Any, document: Any, application: Any
) -> dict[str, Any]:
    """Trusted server preparation after the consumer appends an event over HTTP."""
    runtime = events.runtime
    projected = event_support.project(events)
    policy = simulation_replan_policy()
    record = SqlAlchemyCanonicalIngressRepository(
        runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_by_planning_run_id(events.binding["base_planning_run_id"])
    assert record is not None
    plan = deepcopy(record.document["build_plan"])
    args = {
        k: plan[k]
        for k in (
            "priority_facts",
            "problem_builder_version",
            "tick_seconds",
            "horizon_end_utc",
        )
    }
    args["horizon_start_utc"] = projected.snapshot.document["cutoff_at_utc"]
    problem = build_planning_problem_v2(projected.snapshot, **args)
    freeze = project_effective_locks(
        snapshot=projected.snapshot, problem=problem, base_schedule=base, policy=policy
    ).document
    limits = (
        application.state.dynamic_replanning_application.replan.catalog.solve_limits
    )
    limits_ref = {
        k: limits[k]
        for k in (
            "solve_limits_version",
            "limits_id",
            "limits_revision",
            "max_wall_time_seconds",
            "max_workers",
            "random_seed",
        )
    }
    limits_ref["limits_fingerprint"] = canonical_fingerprint(limits)
    request_document = {
        "replan_request_version": "replan-request.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "factory_id": events.binding["factory_id"],
        "planning_scope_id": events.binding["planning_scope_id"],
        "base_schedule_version": {
            k: base[k]
            for k in (
                "schedule_version_version",
                "schedule_version_id",
                "state",
                "content_fingerprint",
            )
        },
        "base_snapshot": base["lineage"]["snapshot"],
        "base_problem": base["lineage"]["problem"],
        "new_snapshot": freeze["new_snapshot"],
        "new_problem": freeze["new_problem"],
        "new_snapshot_cutoff_at_utc": projected.snapshot.document["cutoff_at_utc"],
        "event_stream": {
            "authority": document["authority"],
            "source_stream": document["source_stream"],
            "from_position": 1,
            "through_position": 1,
            "event_ids": [e["event_id"] for e in [document]],
            "event_fingerprints": [e["event_fingerprint"] for e in [document]],
            "stream_fingerprint": projected.checkpoint.prefix_fingerprint,
            "fact_checkpoint": projected.checkpoint.fact_checkpoint.as_document(),
        },
        "trigger_event_ids": [document["event_id"]],
        "trigger_reason": "EXECUTION_FACT_CHANGED",
        "freeze_resolution": freeze["freeze_resolution"],
        "planning_policy": freeze["planning_policy"],
        "solve_limits": limits_ref,
        "synthetic": True,
        "synthetic_provenance": document["synthetic_provenance"],
        "production_binding": False,
        "requested_at_utc": "2026-09-06T01:02:00Z",
        "correlation_id": "correlation-p9-replan-001",
    }
    request_document["request_fingerprint"] = replan_request_fingerprint(
        request_document
    )
    request_document["request_id"] = (
        "replan-request-" + request_document["request_fingerprint"][7:]
    )
    return request_document


def execute_request(application: Any, settings: Any, attempt: Any) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess

    facade = application.state.dynamic_replanning_application.replan
    model = facade.runs.get(attempt["planning_run_id"])
    composition = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        clock=lambda: datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC),
    )
    try:
        result = cast(Any, composition.worker).execute(
            planning_run_id=attempt["planning_run_id"],
            work_item_id=model.work_items[0].document["work_item_id"],
            worker_id="p9-consumer-worker",
        )
        assert result.planning_run_state == "COMPLETED"
    finally:
        composition.close()


def second_version(runtime: Any) -> Any:
    """A second canonical solve supplies a compatible, independently persisted baseline."""
    from app.data_validation.canonical_ingress import request_fingerprint
    from app.runtime_composition import compose_runtime, RuntimeProcess
    from backend.tests.contract.p8_headless_http_support import create_headers
    from backend.tests.p8_runtime_support import FixedRuntimeClock
    from backend.tests.integration import test_p9_manual as manual
    from sqlalchemy import text

    document = manual.request_with_alternative_resource()
    document.update(
        request_id="REQUEST-P9-CONSUMER-SECOND",
        idempotency_key="p9-consumer-second-run",
        correlation_id="p9-consumer-second",
    )
    document["request_fingerprint"] = request_fingerprint(document)
    response = runtime.client.post(
        "/api/v1/planning-runs", json=document, headers=create_headers(document)
    )
    assert response.status_code == 202, response.text
    with runtime.db.connect() as connection:
        row = connection.execute(
            text(
                "SELECT planning_run_id, work_item_id FROM planning_run_work_items WHERE planning_run_id != :original"
            ),
            {"original": runtime.source["lineage"]["planning_run_id"]},
        ).one()
    worker = compose_runtime(
        runtime.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 10, tzinfo=UTC)),
    )
    try:
        assert worker.worker is not None
        assert (
            worker.worker.execute(
                planning_run_id=row.planning_run_id,
                work_item_id=row.work_item_id,
                worker_id="p9-consumer-second-worker",
            ).disposition.value
            == "COMPLETED"
        )
    finally:
        worker.close()
    with runtime.db.connect() as connection:
        identities = connection.scalars(
            text("SELECT schedule_version_id FROM schedule_versions")
        ).all()
    return runtime.schedules.get(
        next(
            identity
            for identity in identities
            if identity != runtime.source["schedule_version_id"]
        )
    )
