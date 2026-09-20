"""Formal Runtime request preparation, Worker execution and recovery."""

from dataclasses import replace
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import json

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.api.app import create_runtime_app
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
from backend.tests.integration import test_p9_manual as support

runtime = support.runtime
events = event_support.events


@pytest.fixture
def replans(events: Any, tmp_path: Path, request: pytest.FixtureRequest) -> Any:
    runtime = events.runtime
    runtime.identity.principal = replace(
        runtime.identity.principal,
        resolved_capabilities=frozenset({"view", "edit", "approve", "publish"}),
    )
    approved = support.result_source(
        runtime, support.post(runtime, support.command(runtime.source, "APPROVE"))
    )
    response = support.post(
        runtime,
        support.command(
            approved,
            "PUBLISH",
            {"previous_current_version": None},
            key="p9-replan-publish-001",
        ),
    )
    assert response.status_code == 200, response.text
    base = runtime.schedules.get(approved["schedule_version_id"])
    runtime.identity.principal = replace(
        runtime.identity.principal,
        resolved_capabilities=frozenset(
            {
                "event_ingest",
                "event_view",
                "replan",
                "replan_view",
                "replan_control",
                "approve",
                "publish",
                "view",
                "edit",
                "lock",
            }
        ),
    )
    prior = events.base
    urgent = None
    if getattr(request, "param", False):
        urgent = prepare_canonical_urgent(events, prior)
        projected_app = create_runtime_app(
            events.settings, authorization_provider=runtime.identity
        )
        events.facade = projected_app.state.dynamic_replanning_application
        prior = event_support.project(events).snapshot
    document = event_support.event(events, 2 if urgent is not None else 1)
    document["occurred_at_utc"] = events.base.document["cutoff_at_utc"]
    document["received_at_utc"] = document["occurred_at_utc"]
    selected = max(
        base["content"]["assignments"], key=lambda item: item["start_at_utc"]
    )
    operation = selected["operation_id"]
    document["payload"]["operation_id"] = operation
    document["payload"]["final_duration_seconds"] = selected["duration_ticks"] * 60 - 1
    assert document["payload"]["final_duration_seconds"] > selected["duration_seconds"]
    document["entity_refs"] = [{"entity_type": "OPERATION", "entity_id": operation}]
    event_support._refresh_event_identity(document)
    response = event_support.append(events, document)
    assert response.status_code == 202, response.text
    projected = event_support.project(events, prior)
    policy = simulation_replan_policy()
    path = tmp_path / "replan-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    settings = events.settings.model_copy(update={"runtime_replan_policy_path": path})
    application = create_runtime_app(settings, authorization_provider=runtime.identity)
    application.state.dynamic_replanning_clock = lambda: "2026-09-06T01:02:00Z"
    application.state.planning_workspace_clock = lambda: "2026-09-06T01:03:00Z"
    record = SqlAlchemyCanonicalIngressRepository(
        runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_by_planning_run_id(events.binding["base_planning_run_id"])
    assert record is not None
    plan = deepcopy(record.document["build_plan"])
    if urgent is not None:
        payload = urgent["payload"]
        plan["priority_facts"][payload["demand_order_id"]] = {
            "priority_weight": payload["priority_weight"],
            **payload["priority_source"],
        }
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
            "through_position": 2 if urgent is not None else 1,
            "event_ids": [
                e["event_id"]
                for e in ([urgent, document] if urgent is not None else [document])
            ],
            "event_fingerprints": [
                e["event_fingerprint"]
                for e in ([urgent, document] if urgent is not None else [document])
            ],
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
    with TestClient(application) as client:
        yield SimpleNamespace(
            events=events,
            runtime=runtime,
            client=client,
            request=request_document,
            settings=settings,
            application=application,
            facade=application.state.dynamic_replanning_application.replan,
        )


def create(
    replans: Any, document: Any = None, key: str = "p9-replan-create-key-001"
) -> Any:
    document = document or replans.request
    return replans.client.post(
        "/api/v1/replan-requests",
        json=document,
        headers={
            "Authorization": "Bearer p9-test-token",
            "Idempotency-Key": key,
            "X-Correlation-Id": document["correlation_id"],
        },
    )


def test_api_queues_without_solver_and_replays(replans: Any) -> None:
    response = create(replans)
    assert response.status_code == 202, response.text
    result = response.json()["result"]
    assert result["attempt"]["state"] == "CREATED"
    assert create(replans).json()["replayed"] is True
    with replans.runtime.db.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM planning_runs WHERE replan_request_id IS NOT NULL"
                )
            )
            == 1
        )
        assert (
            connection.scalar(text("SELECT count(*) FROM runtime_replan_checkpoints"))
            == 0
        )
        assert connection.scalar(text("SELECT count(*) FROM replan_results")) == 0


def test_worker_creates_one_draft_and_replays(replans: Any) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess

    response = create(replans)
    assert response.status_code == 202, response.text
    attempt = response.json()["result"]["attempt"]
    run_id = attempt["planning_run_id"]
    model = replans.facade.runs.get(run_id)
    composition = compose_runtime(
        replans.settings,
        process=RuntimeProcess.WORKER,
        clock=lambda: datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC),
    )
    try:
        result = cast(Any, composition.worker).execute(
            planning_run_id=run_id,
            work_item_id=model.work_items[0].document["work_item_id"],
            worker_id="p9-replan-worker",
        )
        assert result.planning_run_state == "COMPLETED"
        assert result.checkpoint_replayed is False
        replay = cast(Any, composition.worker).execute(
            planning_run_id=run_id,
            work_item_id=model.work_items[0].document["work_item_id"],
            worker_id="p9-replan-worker-replay",
        )
        assert replay.planning_run_state == "COMPLETED"
        assert replay.checkpoint_replayed is True
    finally:
        composition.close()
    applied = replans.facade.lineage.get_applied_result_for_attempt(
        attempt["attempt_id"]
    )
    schedule = replans.facade.schedules.get(
        applied.change_report["new_schedule_version"]["schedule_version_id"]
    )
    assert schedule["state"] == "DRAFT"
    assert applied.validation_report["status"] == "PASS"
    replans.runtime.identity.principal = replace(
        replans.runtime.identity.principal,
        resolved_capabilities=frozenset({"view", "edit", "approve", "publish"}),
    )
    workspace = SimpleNamespace(client=replans.client)
    ready_response = support.post(
        workspace,
        support.command(schedule, "SUBMIT_FOR_REVIEW", key="p9-replan-review-001"),
    )
    assert ready_response.status_code == 200, ready_response.text
    ready = replans.facade.schedules.get(schedule["schedule_version_id"])
    approved_response = support.post(
        workspace, support.command(ready, "APPROVE", key="p9-replan-approve-001")
    )
    assert approved_response.status_code == 200, approved_response.text
    approved = replans.facade.schedules.get(schedule["schedule_version_id"])
    previous = replans.facade.schedules.get(
        replans.request["base_schedule_version"]["schedule_version_id"]
    )
    published_response = support.post(
        workspace,
        support.command(
            approved,
            "PUBLISH",
            {
                "previous_current_version": {
                    k: previous[k]
                    for k in ("schedule_version_id", "state", "content_fingerprint")
                }
            },
            key="p9-replan-publish-002",
        ),
    )
    assert published_response.status_code == 200, published_response.text
    assert (
        replans.facade.schedules.get(schedule["schedule_version_id"])["state"]
        == "PUBLISHED"
    )
    with replans.runtime.db.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM replan_results")) == 1
        assert (
            connection.scalar(text("SELECT count(*) FROM runtime_replan_checkpoints"))
            == 1
        )


def control(replans: Any, attempt: Any, action: str, key: str) -> Any:
    from app.api.replanning_check import build_replan_action

    document = build_replan_action(
        action=action,
        request_id=replans.request["request_id"],
        request_fingerprint=replans.request["request_fingerprint"],
        idempotency_key=key,
        correlation_id="correlation-" + key,
    )
    document.update(
        expected_attempt_id=attempt["attempt_id"],
        expected_attempt_number=attempt["attempt_number"],
        expected_planning_run_state=attempt["state"],
    )
    document["action_fingerprint"] = canonical_fingerprint(
        {
            k: v
            for k, v in document.items()
            if k not in {"action_id", "action_fingerprint"}
        }
    )
    document["action_id"] = "replan-action-" + document["action_fingerprint"][7:]
    return replans.client.post(
        f"/api/v1/replan-requests/{document['request_id']}/{action.lower()}",
        json=document,
        headers={
            "Authorization": "Bearer p9-test-token",
            "Idempotency-Key": key,
            "X-Correlation-Id": document["correlation_id"],
            "X-Planning-Scope-Id": replans.request["planning_scope_id"],
        },
    )


def test_cancel_replay_retry_keeps_old_run_terminal(replans: Any) -> None:
    attempt = create(replans).json()["result"]["attempt"]
    cancelled = control(replans, attempt, "CANCEL", "p9-cancel-key-001")
    assert cancelled.status_code == 202, cancelled.text
    assert cancelled.json()["result"]["attempt"]["state"] == "CANCELLED"
    replay = control(replans, attempt, "CANCEL", "p9-cancel-key-001")
    assert replay.status_code == 202 and replay.json()["replayed"], replay.text
    retry = control(
        replans, cancelled.json()["result"]["attempt"], "RETRY", "p9-retry-key-001"
    )
    assert retry.status_code == 202, retry.text
    assert retry.json()["result"]["attempt"]["attempt_number"] == 2
    assert (
        retry.json()["result"]["attempt"]["planning_run_id"]
        != attempt["planning_run_id"]
    )
    assert (
        replans.facade.runs.get(attempt["planning_run_id"]).aggregate.document["state"]
        == "CANCELLED"
    )


@pytest.mark.parametrize("crash_stage", ["checkpoint", "result_commit"])
def test_checkpoint_crash_recovery_never_resolves(
    replans: Any, monkeypatch: pytest.MonkeyPatch, crash_stage: str
) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess
    from app.planning.strategies.lexicographic_replan import LexicographicReplanStrategy

    attempt = create(replans).json()["result"]["attempt"]
    run_id = attempt["planning_run_id"]
    work = replans.facade.runs.get(run_id).work_items[0].document
    current = [datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC)]
    composition = compose_runtime(
        replans.settings, process=RuntimeProcess.WORKER, clock=lambda: current[0]
    )
    original = cast(Any, composition.worker)._checkpoints.put

    def crash(document: Any) -> Any:
        original(document)
        raise RuntimeError("simulated crash after durable solve")

    if crash_stage == "checkpoint":
        monkeypatch.setattr(cast(Any, composition.worker)._checkpoints, "put", crash)
    else:

        def crash_completion(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("simulated crash after result commit")

        monkeypatch.setattr(
            cast(Any, composition.worker)._worker_repository,
            "complete",
            crash_completion,
        )
    try:
        with pytest.raises(RuntimeError, match="simulated crash"):
            cast(Any, composition.worker).execute(
                planning_run_id=run_id,
                work_item_id=work["work_item_id"],
                worker_id="p9-crashed-worker",
            )
    finally:
        composition.close()
    current[0] += timedelta(seconds=replans.settings.job_lease_seconds + 1)

    def no_solve(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Recovery called Solver")

    monkeypatch.setattr(LexicographicReplanStrategy, "solve", no_solve)
    restarted = compose_runtime(
        replans.settings, process=RuntimeProcess.WORKER, clock=lambda: current[0]
    )
    try:
        recovered = cast(Any, restarted.worker).recover_expired(
            recovery_worker_id="p9-recovery-worker"
        )
        assert len(recovered) == 1
        assert recovered[0].planning_run_id == run_id
        assert recovered[0].action == "TERMINAL_ACK"
        assert (
            replans.facade.runs.get(run_id).aggregate.document["state"] == "COMPLETED"
        )
    finally:
        restarted.close()


@pytest.mark.parametrize("mode", ["timeout", "cancelled", "stale_fact", "lease_busy"])
def test_worker_rejects_obsolete_or_unowned_work(
    replans: Any, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess
    from app.domain.types import parse_utc_instant
    from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError

    attempt = create(replans).json()["result"]["attempt"]
    work = replans.facade.runs.get(attempt["planning_run_id"]).work_items[0].document
    now = datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC)
    if mode == "timeout":
        now = parse_utc_instant(work["timeout_at_utc"]) + timedelta(seconds=1)
    if mode == "cancelled":
        assert (
            control(replans, attempt, "CANCEL", "p9-before-worker-cancel").status_code
            == 202
        )
    if mode == "stale_fact":
        document = event_support.event(replans.events, 2)
        document["occurred_at_utc"] = replans.events.base.document["cutoff_at_utc"]
        document["received_at_utc"] = document["occurred_at_utc"]
        event_support._refresh_event_identity(document)
        assert event_support.append(replans.events, document).status_code == 202
        base = replans.events.facade._snapshots.get_by_id(
            replans.request["new_snapshot"]["artifact_id"]
        )
        event_support.project(replans.events, base)
    composition = compose_runtime(
        replans.settings, process=RuntimeProcess.WORKER, clock=lambda: now
    )
    worker = cast(Any, composition.worker)
    try:
        if mode == "lease_busy":
            job = worker._worker_repository.ensure_job(work, now=now).record
            worker._worker_repository.claim(
                job.job_id, worker_id="p9-owned", now=now, lease_seconds=60
            )
            with pytest.raises(PlanningRunWorkerError) as rejected:
                worker.execute(
                    planning_run_id=attempt["planning_run_id"],
                    work_item_id=work["work_item_id"],
                    worker_id="p9-owned",
                )
            assert rejected.value.code.value == "LEASE_BUSY"
            assert (
                worker._worker_repository.get_job(job.job_id).status.value == "RUNNING"
            )
        else:
            outcome = worker.execute(
                planning_run_id=attempt["planning_run_id"],
                work_item_id=work["work_item_id"],
                worker_id="p9-boundary",
            )
            assert outcome.planning_run_state == (
                "CANCELLED" if mode == "cancelled" else "FAILED"
            )
    finally:
        composition.close()
    with replans.runtime.db.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM replan_results")) == 0
        assert (
            connection.scalar(text("SELECT count(*) FROM runtime_replan_checkpoints"))
            == 0
        )


def test_new_schema_samples_reject_static_alias_and_unknown_fields() -> None:
    from app.data_validation.canonical_ingress import FrozenSchemaCatalog
    from backend.tests.p8_solver_worker_support import ROOT

    root = ROOT
    schemas = FrozenSchemaCatalog.from_directory(root / "schemas" / "json")
    for name, urn, field, old in (
        (
            "kpi.v3.synthetic.json",
            "urn:plantnexus:aps:schema:kpi:v3",
            "kpi_version",
            "kpi.v2",
        ),
        (
            "planning-run.v2.created.synthetic.json",
            "urn:plantnexus:aps:schema:planning-run:v2",
            "planning_run_version",
            "planning-run.v1",
        ),
    ):
        document = json.loads(
            (root / "schemas" / "samples" / name).read_text(encoding="utf-8")
        )
        schemas.validate(urn, document)
        for changed in ({**document, field: old}, {**document, "unregistered": True}):
            with pytest.raises(ValueError):
                schemas.validate(urn, changed)


def test_populated_replan_history_refuses_downgrade(replans: Any) -> None:
    from alembic import command
    from backend.tests.p8_solver_worker_support import alembic_configuration

    assert create(replans).status_code == 202
    with replans.runtime.db.connect() as connection:
        original = list(
            connection.execute(
                text(
                    "SELECT current_run_json FROM planning_runs ORDER BY planning_run_id"
                )
            ).scalars()
        )
    with pytest.raises(RuntimeError, match="history exists"):
        command.downgrade(
            alembic_configuration(str(replans.runtime.db.url)),
            "0009_host_authorization_audit",
        )
    with replans.runtime.db.connect() as connection:
        assert (
            list(
                connection.execute(
                    text(
                        "SELECT current_run_json FROM planning_runs ORDER BY planning_run_id"
                    )
                ).scalars()
            )
            == original
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def query(replans: Any, kind: str, attempt: Any, report: Any = None) -> Any:
    from app.api.replanning_check import build_replanning_query

    identity = replans.request["request_id"] if report is None else report["report_id"]
    document = build_replanning_query(
        query_kind=kind,
        resource_id=identity,
        planning_scope_id=replans.request["planning_scope_id"],
        correlation_id="p9-replan-query",
        request_fingerprint=replans.request["request_fingerprint"],
        attempt_id=None if kind == "REPLAN_REQUEST" else attempt["attempt_id"],
        report_fingerprint=None if report is None else report["report_fingerprint"],
    )
    path = (
        f"/api/v1/change-reports/{identity}"
        if report is not None
        else f"/api/v1/replan-requests/{identity}"
        + ("/result" if kind == "REPLAN_RESULT" else "")
    )
    return replans.client.get(
        path,
        params={"query": json.dumps(document)},
        headers={"Authorization": "Bearer p9-test-token"},
    )


def test_read_controls_and_dispatch_failure_are_durable(
    replans: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(work: Any) -> Any:
        raise RuntimeError("synthetic broker unavailable")

    monkeypatch.setattr(replans.facade.dispatcher, "dispatch", fail)
    accepted = create(replans)
    assert accepted.status_code == 202, accepted.text
    attempt = accepted.json()["result"]["attempt"]
    assert attempt["state"] == "FAILED"
    assert create(replans).json()["replayed"] is True
    response = query(replans, "REPLAN_RESULT", attempt)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["new_schedule_version"] is None
    assert response.json()["result"]["planning_run_state"] == "FAILED"
    assert query(replans, "REPLAN_REQUEST", attempt).status_code == 200


def test_cancel_after_checkpoint_prevents_result(
    replans: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess

    accepted = create(replans)
    attempt = accepted.json()["result"]["attempt"]
    composition = compose_runtime(
        replans.settings,
        process=RuntimeProcess.WORKER,
        clock=lambda: datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC),
    )
    worker = cast(Any, composition.worker)
    original = worker._checkpoints.put

    def cancel(document: Any) -> Any:
        stored = original(document)
        replans.application.state.dynamic_replanning_clock = (
            lambda: "2026-09-06T01:02:01Z"
        )
        response = control(
            replans,
            {**attempt, "state": "SOLVING"},
            "CANCEL",
            "p9-cancel-before-commit",
        )
        assert response.status_code == 202, response.text
        return stored

    monkeypatch.setattr(worker._checkpoints, "put", cancel)
    work = replans.facade.runs.get(attempt["planning_run_id"]).work_items[0].document
    try:
        outcome = worker.execute(
            planning_run_id=attempt["planning_run_id"],
            work_item_id=work["work_item_id"],
            worker_id="p9-cancel-race",
        )
        assert outcome.planning_run_state == "CANCELLED"
    finally:
        composition.close()
    with replans.runtime.db.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM replan_results")) == 0
        assert (
            connection.scalar(text("SELECT count(*) FROM runtime_replan_checkpoints"))
            == 1
        )


def request_for_checkpoint(replans: Any, base: Any, projected: Any) -> dict[str, Any]:
    events = replans.events
    record = SqlAlchemyCanonicalIngressRepository(
        replans.runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_by_planning_run_id(events.binding["base_planning_run_id"])
    assert record is not None
    plan = deepcopy(record.document["build_plan"])
    ledger = events.facade._events.list_stream(
        **{
            k: events.binding[k]
            for k in ("authority_id", "stream_id", "stream_version")
        }
    )
    for event in ledger:
        if event["event_type"] == "URGENT_DEMAND_RECEIVED":
            payload = event["payload"]
            plan["priority_facts"][payload["demand_order_id"]] = {
                "priority_weight": payload["priority_weight"],
                **payload["priority_source"],
            }
    arguments = {
        k: plan[k]
        for k in (
            "priority_facts",
            "problem_builder_version",
            "tick_seconds",
            "horizon_end_utc",
        )
    }
    arguments["horizon_start_utc"] = projected.snapshot.document["cutoff_at_utc"]
    problem = build_planning_problem_v2(projected.snapshot, **arguments)
    projection = project_effective_locks(
        snapshot=projected.snapshot,
        problem=problem,
        base_schedule=base,
        policy=simulation_replan_policy(),
    ).document
    document = deepcopy(replans.request)
    document.update(
        base_schedule_version={
            k: base[k]
            for k in (
                "schedule_version_version",
                "schedule_version_id",
                "state",
                "content_fingerprint",
            )
        },
        base_snapshot=base["lineage"][
            "new_snapshot"
            if base["schedule_version_version"] == "schedule-version.v2"
            else "snapshot"
        ],
        base_problem=base["lineage"][
            "new_problem"
            if base["schedule_version_version"] == "schedule-version.v2"
            else "problem"
        ],
        new_snapshot=projection["new_snapshot"],
        new_problem=projection["new_problem"],
        freeze_resolution=projection["freeze_resolution"],
        new_snapshot_cutoff_at_utc=projected.snapshot.document["cutoff_at_utc"],
        trigger_event_ids=[ledger[-1]["event_id"]],
    )
    document["event_stream"].update(
        through_position=len(ledger),
        event_ids=[e["event_id"] for e in ledger],
        event_fingerprints=[e["event_fingerprint"] for e in ledger],
        stream_fingerprint=projected.checkpoint.prefix_fingerprint,
        fact_checkpoint=projected.checkpoint.fact_checkpoint.as_document(),
    )
    document["request_fingerprint"] = replan_request_fingerprint(document)
    document["request_id"] = "replan-request-" + document["request_fingerprint"][7:]
    return document


def execute_and_publish(
    replans: Any, document: Any, sequence: int, *, expected: str = "COMPLETED"
) -> Any:
    from app.runtime_composition import compose_runtime, RuntimeProcess

    replans.request = document
    replans.runtime.identity.principal = replace(
        replans.runtime.identity.principal,
        resolved_capabilities=frozenset(
            {"event_ingest", "event_view", "replan", "replan_view", "replan_control"}
        ),
    )
    response = create(replans, document, key=f"p9-continuous-create-{sequence:03d}")
    assert response.status_code == 202, response.text
    attempt = response.json()["result"]["attempt"]
    work = replans.facade.runs.get(attempt["planning_run_id"]).work_items[0].document
    composition = compose_runtime(
        replans.settings,
        process=RuntimeProcess.WORKER,
        clock=lambda: datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC),
    )
    try:
        outcome = cast(Any, composition.worker).execute(
            planning_run_id=attempt["planning_run_id"],
            work_item_id=work["work_item_id"],
            worker_id=f"continuous-worker-{sequence}",
        )
        assert outcome.planning_run_state == expected
    finally:
        composition.close()
    reply = query(replans, "REPLAN_RESULT", attempt)
    assert reply.status_code == 200, reply.text
    if expected != "COMPLETED":
        assert reply.json()["result"]["new_schedule_version"] is None
        return None
    applied = replans.facade.lineage.get_applied_result_for_attempt(
        attempt["attempt_id"]
    )
    report_reply = query(replans, "CHANGE_REPORT", attempt, applied.change_report)
    assert report_reply.status_code == 200, report_reply.text
    assert report_reply.json()["result"]["report"] == applied.change_report
    schedule = replans.facade.schedules.get(
        applied.change_report["new_schedule_version"]["schedule_version_id"]
    )
    replans.runtime.identity.principal = replace(
        replans.runtime.identity.principal,
        resolved_capabilities=frozenset({"view", "edit", "approve", "publish"}),
    )
    workspace = SimpleNamespace(client=replans.client)
    for kind in ("SUBMIT_FOR_REVIEW", "APPROVE", "PUBLISH"):
        payload = None
        if kind == "PUBLISH":
            previous = replans.facade.schedules.get(
                document["base_schedule_version"]["schedule_version_id"]
            )
            payload = {
                "previous_current_version": {
                    k: previous[k]
                    for k in ("schedule_version_id", "state", "content_fingerprint")
                }
            }
        response = support.post(
            workspace,
            support.command(
                schedule, kind, payload, key=f"p9-sequence-{sequence}-{kind}"
            ),
        )
        assert response.status_code == 200, response.text
        schedule = replans.facade.schedules.get(schedule["schedule_version_id"])
    replans.runtime.identity.principal = replace(
        replans.runtime.identity.principal,
        resolved_capabilities=frozenset(
            {"event_ingest", "event_view", "replan", "replan_view", "replan_control"}
        ),
    )
    return schedule


@pytest.mark.parametrize("replans", [True], indirect=True)
def test_continuous_duration_machine_material_progress_replanning(replans: Any) -> None:
    base = execute_and_publish(replans, replans.request, 1)
    snapshot = replans.events.facade._snapshots.get_by_id(
        replans.request["new_snapshot"]["artifact_id"]
    )
    first = min(base["content"]["assignments"], key=lambda a: a["start_at_utc"])
    operation, resource = first["operation_id"], first["resource_id"]
    instance = next(
        v
        for v in snapshot.document["operation_instances"]
        if v["operation_instance_id"] == operation
    )
    running_fact = next(
        v
        for v in snapshot.document["records"]["execution_facts"]
        if v["execution_fact_id"] == instance["execution_fact_id"]
    )
    material = next(
        v["production_order_id"]
        for v in snapshot.document["operation_instances"]
        if v["operation_instance_id"] == operation
    )
    cutoff = snapshot.document["cutoff_at_utc"]
    early_completion = (
        (
            datetime.fromisoformat(first["end_at_utc"].replace("Z", "+00:00"))
            - timedelta(minutes=1)
        )
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    assert cutoff < early_completion < first["end_at_utc"]
    steps = [
        (
            "MACHINE_UNAVAILABLE",
            {
                "resource_id": "RESOURCE-002",
                "unavailable_from_utc": cutoff,
                "unavailable_until_utc": None,
            },
            {("RESOURCE", "RESOURCE-002")},
            cutoff,
            "COMPLETED",
        ),
        (
            "MATERIAL_DELAYED",
            {"material_id": material, "available_at_utc": "2026-08-20T01:00:00Z"},
            {("MATERIAL", material)},
            cutoff,
            "INFEASIBLE",
        ),
        (
            "MATERIAL_READY",
            {"material_id": material, "available_at_utc": cutoff},
            {("MATERIAL", material)},
            cutoff,
            "COMPLETED",
        ),
        (
            "PROCESSING_REMAINING_CHANGED",
            {
                "operation_id": operation,
                "remaining_seconds": first["duration_seconds"],
                "as_of_utc": cutoff,
            },
            {("OPERATION", operation)},
            cutoff,
            "COMPLETED",
        ),
        (
            "OPERATION_COMPLETED",
            {
                "operation_id": operation,
                "resource_id": resource,
                "actual_start_at_utc": running_fact["actual_start_at_utc"],
                "actual_end_at_utc": early_completion,
            },
            {("OPERATION", operation), ("RESOURCE", resource)},
            early_completion,
            "COMPLETED",
        ),
    ]
    for position, (kind, payload, refs, occurred, expected) in enumerate(steps, 3):
        event = event_support.make_event(replans.events, kind, payload, refs, position)
        event.update(occurred_at_utc=occurred, received_at_utc=occurred)
        event_support._refresh_event_identity(event)
        assert event_support.append(replans.events, event).status_code == 202
        projected = event_support.project(replans.events, snapshot)
        document = request_for_checkpoint(replans, base, projected)
        produced = execute_and_publish(replans, document, position, expected=expected)
        if produced is not None:
            base = produced
        snapshot = projected.snapshot
    assert operation not in {a["operation_id"] for a in base["content"]["assignments"]}
    urgent_operations = {
        v["operation_instance_id"]
        for v in snapshot.document["operation_instances"]
        if v["production_lot_id"] == "LOT-P9-URGENT"
    }
    assert urgent_operations
    assert urgent_operations <= {
        a["operation_id"] for a in base["content"]["assignments"]
    }


def prepare_canonical_urgent(events: Any, snapshot: Any) -> Any:
    from backend.tests.contract.p8_headless_http_support import (
        StaticAuthorizationProvider,
        authorization_policy,
        create_headers,
        HEADLESS_NOW,
    )
    from app.data_validation.canonical_ingress import (
        canonical_fingerprint,
        request_fingerprint,
    )
    from app.snapshots import import_package_id_for

    document = support.request_with_alternative_resource()
    document["payload"]["records"] = deepcopy(snapshot.document["records"])
    document.update(
        request_id="REQUEST-P9-URGENT",
        correlation_id="CORRELATION-P9-URGENT",
        idempotency_key="p9-urgent-canonical-0001",
    )
    records = document["payload"]["records"]
    demand = deepcopy(records["demand_orders"][0])
    demand["demand_order_id"] = "DEMAND-P9-URGENT"
    order = deepcopy(records["production_orders"][0])
    order.update(
        production_order_id="ORDER-P9-URGENT", demand_order_id=demand["demand_order_id"]
    )
    lot = deepcopy(records["production_lots"][0])
    lot.update(
        production_lot_id="LOT-P9-URGENT",
        production_order_id=order["production_order_id"],
    )
    records["demand_orders"].append(demand)
    records["production_orders"].append(order)
    records["production_lots"].append(lot)
    document["payload"]["package_id"] = import_package_id_for(document["payload"])
    document["payload_fingerprint"] = canonical_fingerprint(document["payload"])
    document["request_fingerprint"] = request_fingerprint(document)
    policy_path = events.settings.runtime_http_policy_path
    policy = json.loads(policy_path.read_text())
    policy["scopes"][0]["build_plan"]["priority_facts"][demand["demand_order_id"]] = (
        deepcopy(policy["scopes"][0]["build_plan"]["priority_facts"]["DEMAND-001"])
    )
    policy_path.write_text(json.dumps(policy))
    application = create_runtime_app(
        events.settings,
        host_identity_provider=StaticAuthorizationProvider(),
        host_authorization_policy=authorization_policy(),
    )
    application.state.headless_clock = lambda: HEADLESS_NOW
    with TestClient(application) as client:
        reply = client.post(
            "/api/v1/planning-runs", json=document, headers=create_headers(document)
        )
        assert reply.status_code == 202, reply.text
    repo = SqlAlchemyCanonicalIngressRepository(
        events.runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    )
    urgent_run = next(
        run
        for run in repo.list_planning_run_ids()
        if run != events.binding["base_planning_run_id"]
    )
    urgent = event_support.make_event(
        events,
        "URGENT_DEMAND_RECEIVED",
        {
            "demand_order_id": demand["demand_order_id"],
            "quantity": demand["quantity"],
            "due_at_utc": demand["due_at_utc"],
            "priority_weight": 2,
            "priority_source": {
                "source_system": "plantnexus-synthetic-policy",
                "source_version": "1.0.0",
                "source_record_id": "P9-URGENT",
            },
        },
        {("DEMAND_ORDER", demand["demand_order_id"])},
        1,
    )
    urgent.update(
        occurred_at_utc=snapshot.document["cutoff_at_utc"],
        received_at_utc=snapshot.document["cutoff_at_utc"],
    )
    event_support._refresh_event_identity(urgent)
    assert event_support.append(events, urgent).status_code == 202
    events.binding["urgent_import_runs"] = {urgent["event_id"]: urgent_run}
    events.config.write_text(
        json.dumps(
            {"version": "runtime-event-bindings.v1", "bindings": [events.binding]}
        )
    )
    return urgent


@pytest.mark.parametrize("lock_type", ["HARD", "SOFT"])
def test_replan_preserves_explicit_lock_and_reports_stability(
    replans: Any, lock_type: str
) -> None:
    from app.application.execution_fact_projection_check import _policy_reference

    base = execute_and_publish(replans, replans.request, 1)
    snapshot = replans.events.facade._snapshots.get_by_id(
        replans.request["new_snapshot"]["artifact_id"]
    )
    pending = {
        v["operation_instance_id"]
        for v in snapshot.document["operation_instances"]
        if v["status"] == "NOT_STARTED"
    }
    assignment = max(
        (a for a in base["content"]["assignments"] if a["operation_id"] in pending),
        key=lambda a: a["start_at_utc"],
    )
    lock_id = "LOCK-P9-REPLAN-" + lock_type
    event = event_support.make_event(
        replans.events,
        "LOCK_CREATED",
        {
            "lock_id": lock_id,
            "operation_id": assignment["operation_id"],
            "lock_type": lock_type,
            "resource_id": assignment["resource_id"],
            "start_at_utc": assignment["start_at_utc"],
            "end_at_utc": assignment["end_at_utc"],
            "policy_reference": _policy_reference(),
        },
        {
            ("OPERATION", assignment["operation_id"]),
            ("RESOURCE", assignment["resource_id"]),
            ("OPERATION_LOCK", lock_id),
        },
        2,
    )
    event.update(
        occurred_at_utc=snapshot.document["cutoff_at_utc"],
        received_at_utc=snapshot.document["cutoff_at_utc"],
    )
    event_support._refresh_event_identity(event)
    response = event_support.append(replans.events, event)
    assert response.status_code == 202, response.text
    projected = event_support.project(replans.events, snapshot)
    document = request_for_checkpoint(replans, base, projected)
    published = execute_and_publish(replans, document, 2)
    actual = next(
        a
        for a in published["content"]["assignments"]
        if a["operation_id"] == assignment["operation_id"]
    )
    assert {k: actual[k] for k in ("resource_id", "start_at_utc", "end_at_utc")} == {
        k: assignment[k] for k in ("resource_id", "start_at_utc", "end_at_utc")
    }
    assert any(lock["lock_id"] == lock_id for lock in published["content"]["locks"])


def test_concurrent_create_has_one_attempt(replans: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: create(replans), range(2)))
    assert [r.status_code for r in responses] == [202, 202]
    assert responses[0].json()["result"] == responses[1].json()["result"]
    with replans.runtime.db.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM planning_runs WHERE replan_request_id IS NOT NULL"
                )
            )
            == 1
        )


def test_manual_lock_baseline_is_inherited(replans: Any) -> None:
    replans.runtime.identity.principal = replace(
        replans.runtime.identity.principal,
        resolved_capabilities=frozenset({"view", "edit", "lock", "approve", "publish"}),
    )
    original = replans.facade.schedules.get(
        replans.request["base_schedule_version"]["schedule_version_id"]
    )
    assignment = original["content"]["assignments"][-1]
    lock = {
        k: assignment[k]
        for k in ("operation_id", "resource_id", "start_at_utc", "end_at_utc")
    }
    lock.update(lock_id="LOCK-P9-MANUAL-BASE", lock_type="HARD")
    workspace = SimpleNamespace(client=replans.client)
    reply = support.post(
        workspace,
        support.command(
            original, "SET_LOCK", {"lock": lock}, key="p9-replan-manual-lock"
        ),
    )
    assert reply.status_code == 200, reply.text
    source = support.result_source(replans.runtime, reply)
    for kind in ("SUBMIT_FOR_REVIEW", "APPROVE", "PUBLISH"):
        payload = (
            {
                "previous_current_version": {
                    k: original[k]
                    for k in ("schedule_version_id", "state", "content_fingerprint")
                }
            }
            if kind == "PUBLISH"
            else {}
        )
        reply = support.post(
            workspace,
            support.command(source, kind, payload, key="p9-manual-base-" + kind),
        )
        assert reply.status_code == 200, reply.text
        source = replans.facade.schedules.get(source["schedule_version_id"])
    snapshot = replans.facade.events._snapshots.get_by_id(
        replans.request["new_snapshot"]["artifact_id"]
    )
    projected = event_support.project(replans.events, snapshot)
    document = request_for_checkpoint(replans, source, projected)
    replans.runtime.identity.principal = replace(
        replans.runtime.identity.principal,
        resolved_capabilities=frozenset(
            {"event_ingest", "event_view", "replan", "replan_view", "replan_control"}
        ),
    )
    refused = create(replans, document)
    assert refused.status_code == 422, refused.text
    assert refused.json()["details"]["field"] == "base.locks.fact_projection"
    from app.application.execution_fact_projection_check import _policy_reference

    event = event_support.make_event(
        replans.events,
        "LOCK_CREATED",
        {**lock, "policy_reference": _policy_reference()},
        {
            ("OPERATION", lock["operation_id"]),
            ("RESOURCE", lock["resource_id"]),
            ("OPERATION_LOCK", lock["lock_id"]),
        },
        2,
    )
    event.update(
        occurred_at_utc=snapshot.document["cutoff_at_utc"],
        received_at_utc=snapshot.document["cutoff_at_utc"],
    )
    event_support._refresh_event_identity(event)
    assert event_support.append(replans.events, event).status_code == 202
    projected = event_support.project(replans.events, snapshot)
    document = request_for_checkpoint(replans, source, projected)
    published = execute_and_publish(replans, document, 1)
    assert any(
        item["lock_id"] == lock["lock_id"] for item in published["content"]["locks"]
    )


def test_checkpoint_guards_and_kpi_input_integrity(replans: Any) -> None:
    from sqlalchemy.exc import SQLAlchemyError
    from app.infrastructure.runtime_replan_repository import ReplanCheckpointRepository
    from app.planning.reporting.replan_kpi import build_replan_kpi

    execute_and_publish(replans, replans.request, 1)
    with replans.runtime.db.connect() as connection:
        work_id = connection.scalar(
            text("SELECT work_item_id FROM runtime_replan_checkpoints")
        )
    repository = ReplanCheckpointRepository(replans.runtime.db)
    checkpoint = repository.get(work_id)
    for statement in (
        "UPDATE runtime_replan_checkpoints SET document_sha256='tampered'",
        "DELETE FROM runtime_replan_checkpoints",
    ):
        with pytest.raises(SQLAlchemyError):
            with replans.runtime.db.begin() as connection:
                connection.execute(text(statement))
    assert repository.get(work_id) == checkpoint
    frozen = replans.facade.runs.get(
        checkpoint["planning_run_id"]
    ).aggregate.prepared_artifacts["runtime_replan"]
    for field in ("snapshot", "problem"):
        changed = deepcopy(frozen[field])
        changed["snapshot_id"] = "snapshot-tampered"
        with pytest.raises(ValueError):
            build_replan_kpi(
                snapshot=changed if field == "snapshot" else frozen["snapshot"],
                problem=changed if field == "problem" else frozen["problem"],
                report=checkpoint["solver_report"],
            )


def test_timeout_crash_finishes_same_failed_run(
    replans: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess
    from app.domain.types import parse_utc_instant

    attempt = create(replans).json()["result"]["attempt"]
    run_id = attempt["planning_run_id"]
    work = replans.facade.runs.get(run_id).work_items[0].document
    now = parse_utc_instant(work["timeout_at_utc"]) + timedelta(seconds=1)
    composition = compose_runtime(
        replans.settings, process=RuntimeProcess.WORKER, clock=lambda: now
    )
    worker = cast(Any, composition.worker)
    original = worker._transition

    def crash(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated timeout interruption")

    monkeypatch.setattr(worker, "_transition", crash)
    try:
        with pytest.raises(RuntimeError, match="timeout interruption"):
            worker.execute(
                planning_run_id=run_id,
                work_item_id=work["work_item_id"],
                worker_id="p9-timeout-crash",
            )
        monkeypatch.setattr(worker, "_transition", original)
        result = worker.execute(
            planning_run_id=run_id,
            work_item_id=work["work_item_id"],
            worker_id="p9-timeout-replay",
        )
        assert result.planning_run_state == "FAILED"
        assert len(replans.facade.runs.get(run_id).attempts) == 1
    finally:
        composition.close()


def test_extension_failure_is_durable_and_has_no_candidate(
    replans: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.runtime_composition import compose_runtime, RuntimeProcess
    from app.extensions.contracts import RuntimeExtensionError
    from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError

    attempt = create(replans).json()["result"]["attempt"]
    run_id = attempt["planning_run_id"]
    work = replans.facade.runs.get(run_id).work_items[0].document
    composition = compose_runtime(
        replans.settings,
        process=RuntimeProcess.WORKER,
        clock=lambda: datetime(2026, 9, 6, 1, 2, 1, tzinfo=UTC),
    )
    worker = cast(Any, composition.worker)

    def reject(**kwargs: Any) -> None:
        raise RuntimeExtensionError(
            "EXTENSION_VALIDATION_FAILED",
            field="extension",
            message="Synthetic extension rejection",
        )

    monkeypatch.setattr(worker, "_invoke_extension_before_solve", reject)
    try:
        with pytest.raises(
            PlanningRunWorkerError, match="Runtime Extension execution failed closed"
        ):
            worker.execute(
                planning_run_id=run_id,
                work_item_id=work["work_item_id"],
                worker_id="p9-extension-reject",
            )
        replay = worker.execute(
            planning_run_id=run_id,
            work_item_id=work["work_item_id"],
            worker_id="p9-extension-replay",
        )
        assert replay.planning_run_state == "FAILED"
    finally:
        composition.close()
    with replans.runtime.db.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM replan_results")) == 0
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM engineering_job_records WHERE failure_code='EXTENSION_VALIDATION_FAILED'"
                )
            )
            == 1
        )
