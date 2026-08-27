"""TASK-P4-04 durable ingress, projection, replay, and rollback evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import yaml

from app.application.execution_fact_projection import ExecutionFactProjectionService
from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.execution_contracts import execution_event_fingerprint
from app.domain.execution_fact_projection import (
    BASE_SNAPSHOT_SOURCE,
    EVENT_STREAM_SOURCE,
    ExecutionFactProjectionError,
    ProjectionFailure,
    ProjectionScope,
)
from app.importers import RawImportRow, StagedImportBatch
from app.importers.urgent_demand import UrgentDemandImport
from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.replan_persistence import (
    ArtifactReference,
    ProjectionCheckpoint,
    ReplanAuditAction,
    ReplanAuditRecord,
    build_replan_audit_record,
)
from app.infrastructure.replan_repository import (
    SqlAlchemyProjectionCheckpointRepository,
    SqlAlchemyReplanAuditRepository,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import (
    WorkspaceDataPlane,
    WorkspacePersistenceError,
)
from app.normalization import (
    NormalizationInput,
    UnitConversionRegistry,
    expand_orders,
    normalize_import,
)
from app.simulation.generators import (
    DeterministicSyntheticPackageGenerator,
    GenerationContext,
    p1_mapping_profile,
)
from app.simulation.profiles.contracts import FactoryProfileDocument
from app.simulation.scenarios.contracts import ScenarioSpecDocument
from app.snapshots import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    build_planning_snapshot,
)

ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "fixtures/synthetic/SIM-P1-INGRESS-001"
CUTOFF = "2026-11-06T12:00:00Z"


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(ROOT / "backend/migrations"))
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    database_path = tmp_path / "p4-execution-fact-projection.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "head")
    database = create_engine(database_url)
    try:
        yield database
    finally:
        database.dispose()
        command.downgrade(configuration, "base")


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _generation_context() -> GenerationContext:
    return GenerationContext.from_documents(
        profile=cast(
            FactoryProfileDocument, _json(SCENARIO_ROOT / "factory-profile.json")
        ),
        scenario=cast(
            ScenarioSpecDocument, _json(SCENARIO_ROOT / "scenario-spec.json")
        ),
        target="test",
    )


def _unit_registry() -> UnitConversionRegistry:
    document = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / "schemas/rules/unit-conversion-registry.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    return UnitConversionRegistry.from_mapping(document)


def _standard_base() -> tuple[
    UnitConversionRegistry,
    GenerationContext,
    StagedImportBatch,
    ImmutablePlanningSnapshot,
]:
    registry = _unit_registry()
    context = _generation_context()
    batch = DeterministicSyntheticPackageGenerator(registry).prepare_batch(context)
    normalization = normalize_import(
        (NormalizationInput(batch, p1_mapping_profile(context)),),
        unit_registry=registry,
    )
    document = cast(ImportPackageDocumentV2, normalization.document)
    quality = validate_import_package(document)
    assert quality.passed
    expansion = expand_orders(document, quality.document)
    snapshot = build_planning_snapshot(
        document,
        quality.document,
        expansion,
        cutoff_at_utc=CUTOFF,
    )
    return registry, context, batch, snapshot


def _scope(snapshot: ImmutablePlanningSnapshot, suffix: str) -> ProjectionScope:
    factory_id = snapshot.document["records"]["factories"][0]["factory_id"]
    return ProjectionScope(
        factory_id=factory_id,
        planning_scope_id=f"scope-p4-projection-{suffix}",
        authority_id=f"authority-p4-projection-{suffix}",
        stream_id=f"stream-p4-projection-{suffix}",
        stream_version="1.0.0",
    )


def _checkpoint(
    *,
    factory_id: str,
    planning_scope_id: str,
    authority_id: str,
    stream_id: str,
    stream_version: str,
    last_applied_position: int,
    prefix_fingerprint: str,
    fact_document_version: str,
    fact_artifact_id: str,
    fact_fingerprint: str,
    updated_at_utc: str,
) -> ProjectionCheckpoint:
    return ProjectionCheckpoint(
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        authority_id=authority_id,
        stream_id=stream_id,
        stream_version=stream_version,
        last_applied_position=last_applied_position,
        prefix_fingerprint=prefix_fingerprint,
        fact_checkpoint=ArtifactReference(
            document_version=fact_document_version,
            artifact_id=fact_artifact_id,
            fingerprint=fact_fingerprint,
        ),
        updated_at_utc=updated_at_utc,
    )


def _audit(
    *,
    action: str,
    aggregate_type: str,
    aggregate_id: str,
    correlation_id: str,
    idempotency_scope: str,
    idempotency_key_reference: str,
    request_fingerprint: str | None,
    occurred_at_utc: str,
) -> ReplanAuditRecord:
    return build_replan_audit_record(
        action=ReplanAuditAction(action),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        correlation_id=correlation_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_reference=idempotency_key_reference,
        request_fingerprint=request_fingerprint,
        occurred_at_utc=occurred_at_utc,
    )


def _service(
    engine: Engine,
    *,
    scope: ProjectionScope,
    unit_registry: UnitConversionRegistry,
) -> ExecutionFactProjectionService:
    return ExecutionFactProjectionService(
        transaction_factory=engine.begin,
        scope=scope,
        events=SqlAlchemyExecutionEventRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
        checkpoints=SqlAlchemyProjectionCheckpointRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
        audits=SqlAlchemyReplanAuditRepository(
            engine, data_plane=WorkspaceDataPlane.SIMULATION
        ),
        snapshots=SqlAlchemySnapshotRepository(
            engine, data_plane=SnapshotDataPlane.SIMULATION
        ),
        checkpoint_factory=_checkpoint,
        audit_factory=_audit,
        persistence_error_types=(
            WorkspacePersistenceError,
            SQLAlchemyError,
            SnapshotError,
        ),
        unit_registry=unit_registry,
    )


def _event(
    scope: ProjectionScope,
    *,
    event_type: str,
    payload: dict[str, object],
    references: set[tuple[str, str]],
    position: int,
    occurred_at_utc: str = "2026-11-06T12:01:00Z",
) -> dict[str, object]:
    document: dict[str, object] = {
        "execution_event_version": "execution-event.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "event_id": "pending",
        "event_type": event_type,
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "factory_id": scope.factory_id,
        "planning_scope_id": scope.planning_scope_id,
        "authority": {
            "authority_version": "execution-event-authority.v1",
            "authority_id": scope.authority_id,
            "authority_scope": (
                f"SIMULATION/{scope.factory_id}/{scope.planning_scope_id}"
            ),
            "source": {
                "source_system": "integration-execution-source",
                "source_version": "1.0.0",
                "source_record_id": scope.stream_id,
            },
            "decision": "AUTHORIZED_SIMULATION_SOURCE",
            "production_binding": False,
        },
        "source_stream": {
            "stream_id": scope.stream_id,
            "stream_version": scope.stream_version,
            "authority_id": scope.authority_id,
        },
        "source_position": position,
        "occurred_at_utc": occurred_at_utc,
        "received_at_utc": occurred_at_utc,
        "entity_refs": [
            {"entity_type": entity_type, "entity_id": entity_id}
            for entity_type, entity_id in sorted(references)
        ],
        "payload": {"kind": event_type, **payload},
        "synthetic": True,
        "synthetic_provenance": {
            "scenario_id": "scenario-p4-projection-integration",
            "scenario_version": "1.0.0",
            "factory_profile_id": "profile-p4-projection-integration",
            "profile_version": "1.0.0",
            "generator_id": "generator-p4-projection-integration",
            "generator_version": "1.0.0",
            "simulator_id": "simulator-p4-projection-integration",
            "simulator_version": "1.0.0",
            "seed": 20260827,
        },
        "production_binding": False,
        "correlation_id": f"correlation-p4-projection-{position}",
        "event_fingerprint": "pending",
    }
    fingerprint = execution_event_fingerprint(document)
    document["event_fingerprint"] = fingerprint
    document["event_id"] = "execution-event-" + fingerprint.removeprefix("sha256:")
    return document


def _duration_event(
    snapshot: ImmutablePlanningSnapshot,
    scope: ProjectionScope,
    *,
    position: int = 1,
) -> dict[str, object]:
    instance = next(
        item
        for item in snapshot.document["operation_instances"]
        if item["status"] != "COMPLETED"
    )
    operation_id = instance["operation_instance_id"]
    return _event(
        scope,
        event_type="PROCESSING_DURATION_CHANGED",
        payload={
            "operation_id": operation_id,
            "final_duration_seconds": 333,
            "duration_source": "integration-observation",
            "source_version": "1.0.0",
        },
        references={("OPERATION", operation_id)},
        position=position,
    )


def _persist_base(engine: Engine, snapshot: ImmutablePlanningSnapshot) -> None:
    result = SqlAlchemySnapshotRepository(
        engine, data_plane=SnapshotDataPlane.SIMULATION
    ).put(snapshot)
    assert result.replayed is False


def _raw_row(
    record_type: str,
    source_record_id: str,
    payload: dict[str, object],
    *,
    position: int,
) -> RawImportRow:
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    outer = {
        "payload_json": payload_json,
        "record_type": record_type,
        "source_record_id": source_record_id,
    }
    raw_payload = json.dumps(
        outer, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return RawImportRow(
        row_identity=f"{record_type}:{source_record_id}",
        source_location=f"synthetic-records.jsonl:{position}",
        raw_payload=raw_payload,
    )


def _urgent_batch(batch: StagedImportBatch) -> StagedImportBatch:
    position = len(batch.rows)
    added = (
        _raw_row(
            "demand_orders",
            "demand-order-urgent-001",
            {
                "product_id": "product-001",
                "quantity": 4,
                "quantity_unit": "piece",
                "due_at_utc": "2026-11-07T12:00:00Z",
            },
            position=position + 1,
        ),
        _raw_row(
            "production_orders",
            "production-order-urgent-001",
            {
                "demand_order_id": "demand-order-urgent-001",
                "routing_version_id": "routing-version-001",
                "quantity": 4,
                "quantity_unit": "piece",
                "release_at_utc": CUTOFF,
                "material_ready_at_utc": CUTOFF,
            },
            position=position + 2,
        ),
        _raw_row(
            "production_lots",
            "production-lot-urgent-001",
            {
                "production_order_id": "production-order-urgent-001",
                "quantity": 4,
                "quantity_unit": "piece",
            },
            position=position + 3,
        ),
    )
    rows = batch.rows + added
    content = b"\n".join(row.raw_payload for row in rows)
    digest = sha256(content).hexdigest()
    return replace(
        batch,
        batch_id=f"synthetic-batch-{digest[:24]}",
        idempotency_key=f"synthetic-import-{digest}",
        content_sha256=digest,
        content_length_bytes=len(content),
        rows=rows,
    )


def test_ingress_projection_and_checkpoint_replay_are_durable(engine: Engine) -> None:
    """TEST-EXECUTION-FACT-PROJECTION-001 and TEST-IDEMPOTENCY."""

    registry, _, _, base = _standard_base()
    scope = _scope(base, "durable")
    _persist_base(engine, base)
    service = _service(engine, scope=scope, unit_registry=registry)
    event = _duration_event(base, scope)

    first_ingress = service.ingest_event(event)
    replay_ingress = service.ingest_event(event)
    assert first_ingress.replayed is False
    assert replay_ingress.replayed is True
    assert replay_ingress.audit_replayed is True

    committed = service.project_available(base)
    lost_response_replay = service.project_available(base)
    replay = service.project_available(committed.snapshot)
    assert committed.replayed is False
    assert committed.checkpoint.last_applied_position == 1
    assert committed.event_ids == (event["event_id"],)
    assert lost_response_replay.replayed is True
    assert lost_response_replay.snapshot == committed.snapshot
    assert replay.replayed is True and replay.event_ids == ()
    assert committed.snapshot.document["source_versions"][BASE_SNAPSHOT_SOURCE] == (
        base.snapshot_hash
    )
    assert EVENT_STREAM_SOURCE in committed.snapshot.document["source_versions"]

    second_event = _duration_event(committed.snapshot, scope, position=2)
    service.ingest_event(second_event)
    second_committed = service.project_available(committed.snapshot)
    second_lost_response_replay = service.project_available(committed.snapshot)
    second_current_replay = service.project_available(second_committed.snapshot)
    assert second_committed.checkpoint.last_applied_position == 2
    assert second_committed.checkpoint_state_revision == 1
    assert second_committed.event_ids == (second_event["event_id"],)
    assert second_lost_response_replay.replayed is True
    assert second_lost_response_replay.snapshot == second_committed.snapshot
    assert second_current_replay.replayed is True
    assert second_current_replay.event_ids == ()

    stored = SqlAlchemySnapshotRepository(
        engine, data_plane=SnapshotDataPlane.SIMULATION
    ).get_by_id(second_committed.snapshot.snapshot_id)
    assert stored == second_committed.snapshot
    event_audits = SqlAlchemyReplanAuditRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).list_for_aggregate(
        aggregate_type="EXECUTION_EVENT", aggregate_id=cast(str, event["event_id"])
    )
    assert len(event_audits) == 1


def test_gap_rejection_keeps_ledger_but_creates_no_partial_projection(
    engine: Engine,
) -> None:
    registry, _, _, base = _standard_base()
    scope = _scope(base, "gap")
    _persist_base(engine, base)
    service = _service(engine, scope=scope, unit_registry=registry)
    event = _duration_event(base, scope, position=2)
    service.ingest_event(event)

    with pytest.raises(ExecutionFactProjectionError) as rejected:
        service.project_available(base)
    assert rejected.value.reason is ProjectionFailure.ORDERING_VIOLATION
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM planning_snapshots")) == 1
        assert (
            connection.scalar(
                text("SELECT count(*) FROM replan_projection_checkpoints")
            )
            == 0
        )
        assert (
            connection.scalar(text("SELECT count(*) FROM execution_event_ledger")) == 1
        )


def test_projection_audit_failure_rolls_back_snapshot_and_checkpoint(
    engine: Engine,
) -> None:
    registry, _, _, base = _standard_base()
    scope = _scope(base, "rollback")
    _persist_base(engine, base)
    service = _service(engine, scope=scope, unit_registry=registry)
    event = _duration_event(base, scope)
    service.ingest_event(event)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TRIGGER fail_projection_audit
                BEFORE INSERT ON replan_audit_records
                WHEN NEW.action = 'PROJECTION_CHECKPOINT_COMMITTED'
                BEGIN
                    SELECT RAISE(ABORT, 'injected projection audit failure');
                END
                """
            )
        )

    with pytest.raises(ExecutionFactProjectionError) as rejected:
        service.project_available(base)
    assert rejected.value.reason is ProjectionFailure.PERSISTENCE_FAILED
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM planning_snapshots")) == 1
        assert (
            connection.scalar(
                text("SELECT count(*) FROM replan_projection_checkpoints")
            )
            == 0
        )
        assert (
            connection.scalar(text("SELECT count(*) FROM execution_event_ledger")) == 1
        )


def test_urgent_demand_uses_complete_standard_ingress_before_projection(
    engine: Engine,
) -> None:
    """Urgent Demand cannot inject a private canonical or Snapshot shortcut."""

    registry, context, batch, base = _standard_base()
    urgent_batch = _urgent_batch(batch)
    normalization_input = NormalizationInput(urgent_batch, p1_mapping_profile(context))
    candidate = normalize_import((normalization_input,), unit_registry=registry)
    demand = next(
        item
        for item in cast(ImportPackageDocumentV2, candidate.document)["records"][
            "demand_orders"
        ]
        if item["source"]["source_record_id"] == "demand-order-urgent-001"
    )
    demand_id = demand["demand_order_id"]
    scope = _scope(base, "urgent")
    event = _event(
        scope,
        event_type="URGENT_DEMAND_RECEIVED",
        payload={
            "demand_order_id": demand_id,
            "quantity": 4,
            "due_at_utc": "2026-11-07T12:00:00Z",
            "priority_weight": 9,
            "priority_source": {
                "source_system": "urgent-priority-source",
                "source_version": "1.0.0",
                "source_record_id": "priority-urgent-001",
            },
        },
        references={("DEMAND_ORDER", demand_id)},
        position=1,
    )
    urgent_import = UrgentDemandImport(
        event_id=cast(str, event["event_id"]), inputs=(normalization_input,)
    )
    _persist_base(engine, base)
    service = _service(engine, scope=scope, unit_registry=registry)
    service.ingest_event(event)

    committed = service.project_available(
        base,
        urgent_imports={cast(str, event["event_id"]): urgent_import},
    )

    assert committed.snapshot.document["entity_counts"]["demand_orders"] == 3
    assert committed.priority_facts[0].demand_order_id == demand_id
    assert committed.priority_facts[0].priority_weight == 9
