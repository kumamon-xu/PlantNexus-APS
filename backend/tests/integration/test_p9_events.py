"""Formal Runtime event ingress, authority, durable replay and projection."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.app import create_runtime_app
from app.api.replanning_check import build_replanning_query
from app.api.replanning_contracts import DynamicReplanningRequestContext
from app.application.execution_fact_projection_check import (
    _event,
    _refresh_event_identity,
)
from app.domain.execution_fact_projection import (
    ProjectionScope,
    ExecutionFactProjectionError,
)
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.runtime_composition import compose_runtime, RuntimeProcess
from backend.tests.integration import test_p9_manual as support

runtime = support.runtime


@pytest.fixture
def events(runtime: Any, tmp_path: Path) -> Any:
    run = runtime.source["lineage"]["planning_run_id"]
    record = SqlAlchemyCanonicalIngressRepository(
        runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_by_planning_run_id(run)
    assert record is not None
    scope = record.document["effective_scope"]
    binding = {
        **{k: scope[k] for k in ("tenant_id", "factory_id", "planning_scope_id")},
        "authority_id": "authority-p9-events",
        "stream_id": "stream-p9-events",
        "stream_version": "1.0.0",
        "base_planning_run_id": run,
        "actor_refs": [runtime.identity.principal.actor_ref],
        "event_types": [
            "OPERATION_STARTED",
            "OPERATION_COMPLETED",
            "MACHINE_UNAVAILABLE",
            "MACHINE_RECOVERED",
            "MATERIAL_READY",
            "MATERIAL_DELAYED",
            "PROCESSING_DURATION_CHANGED",
            "PROCESSING_REMAINING_CHANGED",
            "URGENT_DEMAND_RECEIVED",
            "LOCK_CREATED",
            "LOCK_RELEASED",
        ],
        "authority_source": {
            "source_system": "p4-machine-check-source",
            "source_version": "1.0.0",
            "source_record_id": "stream-p9-events",
        },
        "urgent_import_runs": {},
    }
    config = tmp_path / "events.json"
    config.write_text(
        json.dumps({"version": "runtime-event-bindings.v1", "bindings": [binding]})
    )
    settings = runtime.settings.model_copy(
        update={"runtime_event_bindings_path": config}
    )
    runtime.identity.principal = replace(
        runtime.identity.principal,
        resolved_capabilities=frozenset({"event_ingest", "event_view"}),
        planning_scope_scope=frozenset({scope["planning_scope_id"]}),
    )
    application = create_runtime_app(settings, authorization_provider=runtime.identity)
    context = DynamicReplanningRequestContext(
        correlation_id="correlation-p9-projection",
        actor_ref=runtime.identity.principal.actor_ref,
        authenticated=True,
        resolved_capabilities=runtime.identity.principal.resolved_capabilities,
        planning_scope_scope=runtime.identity.principal.planning_scope_scope,
        auth_policy_version="p9-simulation-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-09-06T01:01:00Z",
        code_commit=settings.code_commit,
        data_plane="SIMULATION",
        environment="TEST",
    )
    with TestClient(application) as client:
        yield SimpleNamespace(
            runtime=runtime,
            client=client,
            facade=application.state.dynamic_replanning_application,
            settings=settings,
            binding=binding,
            base=record.snapshot,
            scope=ProjectionScope(
                **{
                    k: binding[k]
                    for k in (
                        "factory_id",
                        "planning_scope_id",
                        "authority_id",
                        "stream_id",
                        "stream_version",
                    )
                }
            ),
            context=context,
            config=config,
        )


def event(
    events: Any, position: int = 1, kind: str = "PROCESSING_DURATION_CHANGED"
) -> dict[str, Any]:
    instance = next(
        v
        for v in events.base.document["operation_instances"]
        if v["status"] == "NOT_STARTED"
    )
    operation = instance["operation_instance_id"]
    document = _event(
        events.scope,
        event_type=kind,
        payload={
            "operation_id": operation,
            "final_duration_seconds": 333 + position,
            "duration_source": "synthetic-observation",
            "source_version": "1.0.0",
        },
        references={("OPERATION", operation)},
        position=position,
    )
    return document


def append(events: Any, document: dict[str, Any], key: str | None = None) -> Any:
    return events.client.post(
        "/api/v1/execution-events",
        json=document,
        headers={
            "Authorization": "Bearer p9-test-token",
            "Idempotency-Key": key or f"p9-event-key-{document['source_position']:08}",
            "X-Correlation-Id": document["correlation_id"],
        },
    )


def project(events: Any, base: Any = None) -> Any:
    base = base or events.base
    return events.facade.project(
        context=events.context,
        planning_scope_id=events.scope.planning_scope_id,
        expected_snapshot_id=base.snapshot_id,
        expected_snapshot_hash=base.snapshot_hash,
    )


def counts(events: Any) -> tuple[int, ...]:
    with events.runtime.db.connect() as connection:
        return tuple(
            connection.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in (
                "execution_event_ledger",
                "replan_audit_records",
                "planning_snapshots",
                "replan_projection_checkpoints",
                "schedule_versions",
            )
        )


def test_public_append_get_list_and_restart_projection(events: Any) -> None:
    before = counts(events)
    document = event(events)
    response = append(events, document)
    assert response.status_code == 202, response.text
    assert response.json()["result"]["execution_event"] == document
    assert counts(events)[2:] == before[2:]
    assert append(events, document).json()["replayed"] is True
    assert counts(events) == (before[0] + 1, before[1] + 1, *before[2:])
    for kind, resource in (
        ("EXECUTION_EVENT", document["event_id"]),
        ("EXECUTION_EVENT_STREAM", None),
    ):
        extra: dict[str, Any] = (
            {
                k: getattr(events.scope, k)
                for k in ("authority_id", "stream_id", "stream_version")
            }
            | {"from_position": 1, "through_position": 10}
            if resource is None
            else {}
        )
        query = build_replanning_query(
            query_kind=kind,
            resource_id=resource,
            planning_scope_id=events.scope.planning_scope_id,
            correlation_id="p9-query-events",
            **extra,
        )
        reply = events.client.get(
            "/api/v1/execution-events" + ("/" + resource if resource else ""),
            params={"query": json.dumps(query)},
            headers={"Authorization": "Bearer p9-test-token"},
        )
        assert reply.status_code == 200, reply.text
        assert (
            reply.json()["result"]["execution_event"]
            if resource
            else reply.json()["result"]["events"][0]
        ) == document
    result = project(events)
    assert (
        result.snapshot != events.base and result.checkpoint.last_applied_position == 1
    )
    saved = counts(events)
    restart = compose_runtime(events.settings, process=RuntimeProcess.WORKER)
    try:
        assert restart.dynamic_replanning_application is not None
        replay = restart.dynamic_replanning_application.project(
            context=events.context,
            planning_scope_id=events.scope.planning_scope_id,
            expected_snapshot_id=events.base.snapshot_id,
            expected_snapshot_hash=events.base.snapshot_hash,
        )
        assert (
            replay.replayed
            and replay.snapshot.canonical_bytes == result.snapshot.canonical_bytes
        )
        assert counts(events) == saved
    finally:
        restart.close()
    assert (
        events.runtime.schedules.get(events.runtime.source["schedule_version_id"])
        == events.runtime.source
    )


def test_gap_then_fill_and_stale_base(events: Any) -> None:
    before = counts(events)
    assert append(events, event(events, 2)).status_code == 202
    with pytest.raises(ExecutionFactProjectionError):
        project(events)
    assert counts(events)[2:] == before[2:]
    assert append(events, event(events, 1)).status_code == 202
    result = project(events)
    assert result.checkpoint.last_applied_position == 2
    assert append(events, event(events, 3)).status_code == 202
    with pytest.raises(ExecutionFactProjectionError):
        project(events)
    updated = project(events, result.snapshot)
    assert updated.checkpoint.last_applied_position == 3


@pytest.mark.parametrize(
    "change", ["actor", "scope", "authority", "source", "type", "environment"]
)
def test_authority_denial_has_no_business_writes(events: Any, change: str) -> None:
    document = event(events)
    before = counts(events)
    if change == "actor":
        events.runtime.identity.principal = replace(
            events.runtime.identity.principal, actor_ref="actor:unbound"
        )
    elif change == "scope":
        events.runtime.identity.principal = replace(
            events.runtime.identity.principal, planning_scope_scope=frozenset({"other"})
        )
    elif change == "authority":
        document["authority"]["authority_id"] = "unbound"
    elif change == "source":
        document["authority"]["source"]["source_system"] = "unbound"
    elif change == "type":
        document["event_type"] = "UNSUPPORTED"
    else:
        document["environment"] = "BENCHMARK"
    _refresh_event_identity(document)
    response = append(events, document)
    assert response.status_code >= 400, response.text
    assert counts(events) == before


def test_conflicts_and_ingress_audit_rollback(
    events: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = event(events)
    assert append(events, document).status_code == 202
    baseline = counts(events)
    conflicting = event(events, 2)
    response = append(events, conflicting, key="p9-event-key-00000001")
    assert response.status_code == 409, response.text
    assert counts(events) == baseline
    conflicting = deepcopy(document)
    conflicting["payload"]["final_duration_seconds"] = 999
    _refresh_event_identity(conflicting)
    assert append(events, conflicting, key="different-key-000001").status_code == 409
    assert counts(events) == baseline

    def fail(*args: Any, **kwargs: Any) -> None:
        raise SQLAlchemyError("credential-do-not-leak")

    monkeypatch.setattr(
        "app.infrastructure.replan_repository.SqlAlchemyReplanAuditRepository.append_in_transaction",
        fail,
    )
    response = append(events, event(events, 2))
    assert response.status_code == 500 and "credential-do-not-leak" not in response.text
    assert counts(events) == baseline


def test_projection_cas_and_audit_failure_roll_back_snapshot(
    events: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert append(events, event(events)).status_code == 202
    before = counts(events)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise SQLAlchemyError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(
            "app.infrastructure.replan_repository.SqlAlchemyReplanAuditRepository.append_in_transaction",
            fail,
        )
        with pytest.raises(ExecutionFactProjectionError):
            project(events)
    assert counts(events) == before
    first = project(events)
    assert append(events, event(events, 2)).status_code == 202
    before = counts(events)
    with monkeypatch.context() as patch:
        patch.setattr(
            "app.infrastructure.replan_repository.SqlAlchemyProjectionCheckpointRepository.advance_in_transaction",
            fail,
        )
        with pytest.raises(ExecutionFactProjectionError):
            project(events, first.snapshot)
    assert counts(events) == before
    assert project(events, first.snapshot).checkpoint.last_applied_position == 2


def make_event(
    events: Any,
    kind: str,
    payload: dict[str, Any],
    refs: set[tuple[str, str]],
    position: int,
) -> dict[str, Any]:
    return _event(
        events.scope,
        event_type=kind,
        payload=payload,
        references=refs,
        position=position,
    )


def test_running_completed_and_remaining_facts_are_protected(events: Any) -> None:
    instance = next(
        v
        for v in events.base.document["operation_instances"]
        if v["status"] == "NOT_STARTED"
    )
    op = instance["operation_instance_id"]
    resource = instance["resource_options"][0]["resource_id"]
    start = "2026-08-20T00:00:00Z"
    started = make_event(
        events,
        "OPERATION_STARTED",
        {"operation_id": op, "resource_id": resource, "actual_start_at_utc": start},
        {("OPERATION", op), ("RESOURCE", resource)},
        1,
    )
    assert append(events, started).status_code == 202
    running = project(events)
    observed = next(
        v
        for v in running.snapshot.document["operation_instances"]
        if v["operation_instance_id"] == op
    )
    assert observed["status"] == "RUNNING"
    remaining = make_event(
        events,
        "PROCESSING_REMAINING_CHANGED",
        {
            "operation_id": op,
            "remaining_seconds": 120,
            "as_of_utc": started["occurred_at_utc"],
        },
        {("OPERATION", op)},
        2,
    )
    assert append(events, remaining).status_code == 202
    updated = project(events, running.snapshot)
    completed = make_event(
        events,
        "OPERATION_COMPLETED",
        {
            "operation_id": op,
            "resource_id": resource,
            "actual_start_at_utc": start,
            "actual_end_at_utc": remaining["occurred_at_utc"],
        },
        {("OPERATION", op), ("RESOURCE", resource)},
        3,
    )
    assert append(events, completed).status_code == 202
    final = project(events, updated.snapshot)
    assert (
        next(
            v
            for v in final.snapshot.document["operation_instances"]
            if v["operation_instance_id"] == op
        )["status"]
        == "COMPLETED"
    )
    regression = make_event(
        events,
        "OPERATION_STARTED",
        {"operation_id": op, "resource_id": resource, "actual_start_at_utc": start},
        {("OPERATION", op), ("RESOURCE", resource)},
        4,
    )
    assert append(events, regression).status_code == 202
    before = counts(events)
    with pytest.raises(ExecutionFactProjectionError, match="TERMINAL_REGRESSION"):
        project(events, final.snapshot)
    assert counts(events) == before


def test_machine_material_and_lock_event_sequence(events: Any) -> None:
    from app.application.execution_fact_projection_check import _policy_reference

    resource = "RESOURCE-002"
    instance = next(
        v
        for v in events.base.document["operation_instances"]
        if v["status"] == "NOT_STARTED"
        and any(o["resource_id"] == resource for o in v["resource_options"])
    )
    op = instance["operation_instance_id"]
    material = instance["production_order_id"]
    inputs = [
        (
            "MACHINE_UNAVAILABLE",
            {
                "resource_id": resource,
                "unavailable_from_utc": "2026-08-20T00:00:00Z",
                "unavailable_until_utc": None,
            },
            {("RESOURCE", resource)},
        ),
        (
            "MACHINE_RECOVERED",
            {"resource_id": resource, "available_from_utc": "2026-08-20T00:15:00Z"},
            {("RESOURCE", resource)},
        ),
        (
            "MATERIAL_DELAYED",
            {"material_id": material, "available_at_utc": "2026-08-21T00:00:00Z"},
            {("MATERIAL", material)},
        ),
        (
            "MATERIAL_READY",
            {"material_id": material, "available_at_utc": "2026-08-20T00:30:00Z"},
            {("MATERIAL", material)},
        ),
        (
            "LOCK_CREATED",
            {
                "lock_id": "LOCK-P9-EVENT",
                "operation_id": op,
                "lock_type": "SOFT",
                "resource_id": resource,
                "start_at_utc": "2026-08-21T00:00:00Z",
                "end_at_utc": "2026-08-21T01:00:00Z",
                "policy_reference": _policy_reference(),
            },
            {
                ("OPERATION", op),
                ("RESOURCE", resource),
                ("OPERATION_LOCK", "LOCK-P9-EVENT"),
            },
        ),
        (
            "LOCK_RELEASED",
            {
                "lock_id": "LOCK-P9-EVENT",
                "release_reason": "POLICY_REEVALUATION",
                "policy_reference": _policy_reference(),
            },
            {("OPERATION_LOCK", "LOCK-P9-EVENT")},
        ),
    ]
    base = events.base
    for pos, (kind, payload, refs) in enumerate(inputs, 1):
        response = append(events, make_event(events, kind, payload, refs, pos))
        assert response.status_code == 202, response.text
        base = project(events, base).snapshot
    assert (
        next(
            v
            for v in base.document["records"]["resources"]
            if v["resource_id"] == resource
        )["status"]
        == "AVAILABLE"
    )
    assert (
        next(
            v
            for v in base.document["records"]["production_orders"]
            if v["production_order_id"] == material
        )["material_ready_at_utc"]
        == "2026-08-20T00:30:00Z"
    )
    assert not any(
        v["lock_id"] == "LOCK-P9-EVENT"
        for v in base.document["records"]["operation_locks"]
    )


def test_timeline_cursor_binds_window_and_source(events: Any) -> None:
    from app.data_validation.canonical_ingress import canonical_fingerprint

    for pos in (1, 2, 3):
        assert append(events, event(events, pos)).status_code == 202
    query = build_replanning_query(
        query_kind="EXECUTION_EVENT_STREAM",
        resource_id=None,
        planning_scope_id=events.scope.planning_scope_id,
        correlation_id="p9-page",
        authority_id=events.scope.authority_id,
        stream_id=events.scope.stream_id,
        stream_version=events.scope.stream_version,
        from_position=1,
        through_position=10,
    )
    query["page"] = {"size": 1, "cursor": None}

    def read() -> Any:
        query["query_fingerprint"] = canonical_fingerprint(
            {k: v for k, v in query.items() if k != "query_fingerprint"}
        )
        return events.client.get(
            "/api/v1/execution-events",
            params={"query": json.dumps(query)},
            headers={"Authorization": "Bearer p9-test-token"},
        )

    response = read()
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["projection_fingerprint"] == canonical_fingerprint(
        {k: v for k, v in result.items() if k != "projection_fingerprint"}
    )
    query["page"]["cursor"] = result["next_cursor"]
    response = read()
    assert response.status_code == 200, response.text
    assert response.json()["result"]["events"][0]["source_position"] == 2
    assert append(events, event(events, 4)).status_code == 202
    assert read().status_code == 409


def test_urgent_demand_requires_durable_canonical_import(events: Any) -> None:
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
    urgent = make_event(
        events,
        "URGENT_DEMAND_RECEIVED",
        {
            "demand_order_id": demand["demand_order_id"],
            "quantity": demand["quantity"],
            "due_at_utc": demand["due_at_utc"],
            "priority_weight": 2,
            "priority_source": {
                "source_system": "p9-synthetic-policy",
                "source_version": "1.0.0",
                "source_record_id": "P9-URGENT",
            },
        },
        {("DEMAND_ORDER", demand["demand_order_id"])},
        1,
    )
    assert append(events, urgent).status_code == 202
    before = counts(events)
    with pytest.raises(Exception, match="urgent_import_runs"):
        project(events)
    assert counts(events) == before
    events.binding["urgent_import_runs"] = {urgent["event_id"]: urgent_run}
    events.config.write_text(
        json.dumps(
            {"version": "runtime-event-bindings.v1", "bindings": [events.binding]}
        )
    )
    runtime = compose_runtime(events.settings, process=RuntimeProcess.WORKER)
    try:
        events.facade = runtime.dynamic_replanning_application
        result = project(events)
        assert (
            len(result.snapshot.document["records"]["demand_orders"])
            == len(events.base.document["records"]["demand_orders"]) + 1
        )
        assert result.priority_facts[0].demand_order_id == demand["demand_order_id"]
        assert project(events).snapshot == result.snapshot
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "change", ["version", "extra", "duplicate", "actor", "type", "scope"]
)
def test_invalid_server_bindings_fail_startup(events: Any, change: str) -> None:
    from app.runtime_composition import RuntimeCompositionError

    config = {
        "version": "runtime-event-bindings.v1",
        "bindings": [deepcopy(events.binding)],
    }
    if change == "version":
        config["version"] = "unknown"
    elif change == "extra":
        config["bindings"][0]["private_snapshot"] = {}
    elif change == "duplicate":
        config["bindings"].append(deepcopy(events.binding))
    elif change == "actor":
        config["bindings"][0]["actor_refs"] = ["*"]
    elif change == "type":
        config["bindings"][0]["event_types"] = ["PARTIAL_COMPLETION"]
    else:
        config["bindings"][0]["tenant_id"] = "unregistered-tenant"
    events.config.write_text(json.dumps(config))
    with pytest.raises(RuntimeCompositionError, match="CONFIGURATION_INVALID"):
        compose_runtime(events.settings, process=RuntimeProcess.WORKER)


def test_unconfigured_and_cross_scope_queries_fail_closed(events: Any) -> None:
    from app.data_validation.canonical_ingress import canonical_fingerprint
    from app.application.runtime_dynamic_replanning import RuntimeEventError

    document = event(events)
    assert append(events, document).status_code == 202
    query = build_replanning_query(
        query_kind="EXECUTION_EVENT",
        resource_id=document["event_id"],
        planning_scope_id="different-scope",
        correlation_id="p9-cross-scope",
    )
    events.runtime.identity.principal = replace(
        events.runtime.identity.principal, planning_scope_scope=frozenset({"*"})
    )
    response = events.client.get(
        "/api/v1/execution-events/" + document["event_id"],
        params={"query": json.dumps(query)},
        headers={"Authorization": "Bearer p9-test-token"},
    )
    assert response.status_code == 503
    query["planning_scope_id"] = events.scope.planning_scope_id
    query["resource_id"] = "execution-event-" + "f" * 64
    query["query_fingerprint"] = canonical_fingerprint(
        {k: v for k, v in query.items() if k != "query_fingerprint"}
    )
    response = events.client.get(
        "/api/v1/execution-events/" + query["resource_id"],
        params={"query": json.dumps(query)},
        headers={"Authorization": "Bearer p9-test-token"},
    )
    assert response.status_code == 404
    before = counts(events)
    with pytest.raises(RuntimeEventError, match="AUTHORIZATION_DENIED"):
        events.facade.project(
            context=replace(
                events.context, resolved_capabilities=frozenset({"event_view"})
            ),
            planning_scope_id=events.scope.planning_scope_id,
            expected_snapshot_id=events.base.snapshot_id,
            expected_snapshot_hash=events.base.snapshot_hash,
        )
    assert counts(events) == before


def test_projected_snapshot_builds_new_problem_without_changing_original(
    events: Any,
) -> None:
    from app.planning.problem.builder import build_planning_problem_v2

    record = SqlAlchemyCanonicalIngressRepository(
        events.runtime.db, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_by_planning_run_id(events.binding["base_planning_run_id"])
    assert record is not None
    original = record.problem.canonical_bytes
    assert append(events, event(events)).status_code == 202
    projected = project(events)
    plan = record.document["build_plan"]
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
    new = build_planning_problem_v2(projected.snapshot, **arguments)
    replay = build_planning_problem_v2(project(events).snapshot, **arguments)
    assert new.problem_hash != record.problem.problem_hash
    assert new.canonical_bytes == replay.canonical_bytes
    assert new.document["snapshot_id"] == projected.snapshot.snapshot_id
    assert record.problem.canonical_bytes == original


def test_same_event_concurrent_append_has_one_logical_receipt(events: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    document = event(events)
    before = counts(events)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: append(events, document), range(2)))
    assert [r.status_code for r in responses] == [202, 202]
    assert sorted(r.json()["replayed"] for r in responses) == [False, True]
    assert counts(events) == (before[0] + 1, before[1] + 1, *before[2:])
