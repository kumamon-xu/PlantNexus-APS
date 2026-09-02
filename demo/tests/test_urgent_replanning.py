"""DEMO-URGENT/REPLAN: additive ingress, event projection, and v2 DRAFT."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.replan_repository import SqlAlchemyReplanLineageRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.domain.execution_fact_projection import ProjectionScope
from app.normalization import canonical_json_bytes
from app.snapshots import SnapshotDataPlane

from plantnexus_demo.generator import DemoPackageGenerator
from plantnexus_demo.ingress import DemoIngressPipeline
from plantnexus_demo.orchestration import (
    BaselineActivationService,
    DemoOperationError,
    InitialPlanningOrchestrator,
    ResetOrchestrator,
)
from plantnexus_demo.persistence import (
    ControlStore,
    DemoRuntimePaths,
    RunDatabase,
    fingerprint,
    key_reference,
)
from plantnexus_demo.replanning import UrgentReplanOrchestrator, build_urgent_event
from plantnexus_demo.urgent import (
    UrgentOrderCommand,
    UrgentOrderError,
    prepare_urgent_candidate,
    resolve_local_due,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _command(run_id: str, version_id: str) -> UrgentOrderCommand:
    return UrgentOrderCommand(
        command_version="cnc-demo-urgent-order-command.v1",
        expected_run_id=run_id,
        expected_base_version_id=version_id,
        route_template_id="CNC-ROUTE-4",
        quantity=4,
        due_at_local="2026-09-09T18:00:00",
        priority_class="URGENT",
        note="演示加急法兰",
    )


def _published(tmp_path: Path) -> tuple[DemoRuntimePaths, ControlStore, str, str, str]:
    paths = DemoRuntimePaths(tmp_path / "runtime-urgent")
    control = ControlStore(paths)
    run_id = "run-demo-urgent-001"
    ResetOrchestrator(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    ).execute(
        run_id=run_id,
        profile_name="smoke",
        expected_active_run_id=None,
        created_at_utc="2026-09-02T10:00:00Z",
    )
    request = fingerprint(
        {"request_version": "cnc-demo-initial-plan-request.v1", "run_id": run_id}
    )
    planned = InitialPlanningOrchestrator(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    ).execute(
        run_id=run_id,
        request_fingerprint=request,
        idempotency_key_reference=key_reference("demo-urgent-initial-plan-key-0001"),
        correlation_id="correlation-demo-urgent-initial",
        occurred_at_utc="2026-09-02T10:01:00Z",
    )
    BaselineActivationService(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    ).execute(
        expected_run_id=run_id,
        schedule_version_id=planned.schedule_version_id,
        content_fingerprint=planned.content_fingerprint,
        expected_state_revision=planned.state_revision,
        confirmation="ACTIVATE_SIMULATION_BASELINE",
        idempotency_key_reference=key_reference("demo-urgent-activate-key-0001"),
        correlation_id="correlation-demo-urgent-activate",
        occurred_at_utc="2026-09-02T10:02:00Z",
    )
    return (
        paths,
        control,
        run_id,
        planned.schedule_version_id,
        planned.content_fingerprint,
    )


def test_urgent_candidate_is_additive_and_event_excludes_demo_only_fields() -> None:
    base = DemoPackageGenerator().prepare_batch("smoke")
    command = _command("run-unit", "schedule-unit")
    urgent = prepare_urgent_candidate(base, command)

    for collection, records in base.records.items():
        assert [canonical_json_bytes(record) for record in records] == [
            canonical_json_bytes(record)
            for record in urgent.generated.records[collection][: len(records)]
        ]
    assert urgent.added_record_counts["demand_orders"] == 1
    assert urgent.added_record_counts["routing_operations"] == 4
    assert urgent.preserved_record_count == sum(
        len(value) for value in base.records.values()
    )

    ingress = DemoIngressPipeline().run(urgent.generated)
    normalized = cast(Mapping[str, object], ingress.normalization.document)
    normalized_records = cast(Mapping[str, object], normalized["records"])
    demand = next(
        value
        for value in cast(
            Sequence[Mapping[str, object]], normalized_records["demand_orders"]
        )
        if cast(Mapping[str, object], value["source"])["source_record_id"]
        == urgent.demand_source_id
    )
    scope = ProjectionScope(
        factory_id=ingress.snapshot.document["records"]["factories"][0]["factory_id"],
        planning_scope_id="cnc-demo-unit-scope",
        authority_id="cnc-demo-unit-authority",
        stream_id="cnc-demo-unit-stream",
        stream_version="1.0.0",
    )
    event = build_urgent_event(
        scope=scope,
        snapshot=ingress.snapshot,
        candidate=urgent,
        demand_order_id=cast(str, demand["demand_order_id"]),
    )
    assert event["event_type"] == "URGENT_DEMAND_RECEIVED"
    payload = cast(Mapping[str, object], event["payload"])
    assert "route_template_id" not in payload
    assert "note" not in payload
    assert set(payload) == {
        "kind",
        "demand_order_id",
        "quantity",
        "due_at_utc",
        "priority_weight",
        "priority_source",
    }


def test_urgent_command_and_local_time_fail_closed() -> None:
    base = DemoPackageGenerator().prepare_batch("smoke")
    with pytest.raises(ValidationError):
        UrgentOrderCommand.model_validate(
            _command("run", "version").model_dump() | {"quantity": True}
        )
    with pytest.raises(UrgentOrderError, match="route_template_id"):
        prepare_urgent_candidate(
            base,
            _command("run", "version").model_copy(
                update={"route_template_id": "CNC-ROUTE-NOT-APPROVED"}
            ),
        )
    with pytest.raises(UrgentOrderError, match="must not include an offset"):
        prepare_urgent_candidate(
            base,
            _command("run", "version").model_copy(
                update={"due_at_local": "2026-09-09T18:00:00+08:00"}
            ),
        )
    with pytest.raises(UrgentOrderError, match="within the horizon"):
        prepare_urgent_candidate(
            base,
            _command("run", "version").model_copy(
                update={"due_at_local": "2026-10-09T18:00:00"}
            ),
        )
    with pytest.raises(UrgentOrderError, match="nonexistent"):
        resolve_local_due("2026-03-08T02:30:00", timezone_name="America/New_York")
    with pytest.raises(UrgentOrderError, match="ambiguous"):
        resolve_local_due("2026-11-01T01:30:00", timezone_name="America/New_York")


def test_stale_base_fails_before_formal_write_then_replan_creates_draft(
    tmp_path: Path,
) -> None:
    paths, control, run_id, base_version_id, base_fingerprint = _published(tmp_path)
    orchestrator = UrgentReplanOrchestrator(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    )
    stale = _command(run_id, "schedule-version-stale")
    with pytest.raises(DemoOperationError, match="STALE_BASE_VERSION"):
        orchestrator.execute(
            command=stale,
            idempotency_key_reference=key_reference("demo-urgent-stale-key-0001"),
            correlation_id="correlation-demo-urgent-stale",
            occurred_at_utc="2026-09-02T10:03:00Z",
        )

    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(run_id),
    )
    try:
        with database.engine.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM execution_event_ledger"
                ).scalar_one()
                == 0
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM replan_requests"
                ).scalar_one()
                == 0
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM replan_attempts"
                ).scalar_one()
                == 0
            )
    finally:
        database.close()

    command = _command(run_id, base_version_id)
    key = key_reference("demo-urgent-replan-key-0001")
    first = orchestrator.execute(
        command=command,
        idempotency_key_reference=key,
        correlation_id="correlation-demo-urgent-replan",
        occurred_at_utc="2026-09-02T10:04:00Z",
    )
    replay = orchestrator.execute(
        command=command,
        idempotency_key_reference=key,
        correlation_id="correlation-demo-urgent-replan-replay",
        occurred_at_utc="2026-09-02T10:05:00Z",
    )

    assert first.schedule_state == "DRAFT"
    assert first.validation_status == "PASS"
    assert first.solver_status in {"OPTIMAL", "FEASIBLE"}
    assert first.added_operations == 4
    assert replay.document | {"exact_replay": False} == first.document
    assert replay.exact_replay is True

    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(run_id),
    )
    try:
        plane = WorkspaceDataPlane.SIMULATION
        current = SqlAlchemyPublicationRepository(
            database.engine, data_plane=plane
        ).get_current(target="SIMULATION_INTERNAL")
        assert current is not None
        assert current.schedule_version_id == base_version_id
        assert current.content_fingerprint == base_fingerprint
        draft = SqlAlchemyScheduleVersionRepository(
            database.engine, data_plane=plane
        ).get(first.schedule_version_id)
        assert draft is not None
        assert draft["schedule_version_version"] == "schedule-version.v2"
        assert draft["state"] == "DRAFT"
        base_schedule = SqlAlchemyScheduleVersionRepository(
            database.engine, data_plane=plane
        ).get(base_version_id)
        assert base_schedule is not None
        base_snapshot_reference = cast(
            Mapping[str, object],
            cast(Mapping[str, object], base_schedule["lineage"])["snapshot"],
        )
        snapshot_repository = SqlAlchemySnapshotRepository(
            database.engine, data_plane=SnapshotDataPlane.SIMULATION
        )
        base_snapshot = snapshot_repository.get_by_id(
            cast(str, base_snapshot_reference["artifact_id"])
        )
        new_snapshot = snapshot_repository.get_by_id(first.snapshot_id)
        assert base_snapshot is not None and new_snapshot is not None
        base_completed = {
            item["operation_instance_id"]: canonical_json_bytes(item)
            for item in base_snapshot.document["operation_instances"]
            if item["status"] == "COMPLETED"
        }
        new_completed = {
            item["operation_instance_id"]: canonical_json_bytes(item)
            for item in new_snapshot.document["operation_instances"]
            if item["status"] == "COMPLETED"
        }
        assert new_completed == base_completed
        applied = SqlAlchemyReplanLineageRepository(
            database.engine, data_plane=plane
        ).get_applied_result_for_attempt(first.attempt_id)
        assert applied is not None
        fact_evidence = cast(
            Mapping[str, object], applied.validation_report["fact_lock_evidence"]
        )
        assert fact_evidence["running_fact_count"] == 3
        assert fact_evidence["explicit_hard_lock_count"] == 1
        assert cast(int, fact_evidence["freeze_derived_hard_lock_count"]) >= 1
        assert applied.change_report["operation_universe_count"] == 106
        operations = cast(
            Sequence[Mapping[str, object]], applied.change_report["operations"]
        )
        assert (
            sum(
                operation["classification"] == "ADDED"
                for operation in operations
            )
            == 4
        )
        event = SqlAlchemyExecutionEventRepository(
            database.engine, data_plane=plane
        ).get(first.event_id)
        assert event is not None
        event_payload = cast(Mapping[str, object], event["payload"])
        assert "route_template_id" not in event_payload
        assert "note" not in event_payload
        with database.engine.connect() as connection:
            counts = {
                table: connection.exec_driver_sql(
                    f"SELECT COUNT(*) FROM {table}"
                ).scalar_one()
                for table in (
                    "execution_event_ledger",
                    "replan_projection_checkpoints",
                    "replan_requests",
                    "replan_attempts",
                    "replan_results",
                )
            }
            audit_row = connection.exec_driver_sql(
                "SELECT result_reference_json FROM demo_command_audit "
                "WHERE command_type = 'URGENT_ORDER_REPLAN'"
            ).first()
        assert audit_row is not None
        audit = json.loads(bytes(audit_row[0]).decode("utf-8"))
        assert audit["command"]["route_template_id"] == "CNC-ROUTE-4"
        assert audit["command"]["note"] == "演示加急法兰"
        assert counts == {
            "execution_event_ledger": 1,
            "replan_projection_checkpoints": 1,
            "replan_requests": 1,
            "replan_attempts": 1,
            "replan_results": 1,
        }
    finally:
        database.close()
