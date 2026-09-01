"""Emit machine-checkable TASK-P4-04 event-to-fact projection evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from alembic import command
from alembic.config import Config
import yaml

from app.application.execution_fact_projection import ExecutionFactProjectionService
from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.execution_contracts import execution_event_fingerprint
from app.domain.execution_fact_projection import (
    BASE_SNAPSHOT_SOURCE,
    EVENT_AUTHORITY_SOURCE,
    EVENT_STREAM_SOURCE,
    ExecutionFactProjectionError,
    ProjectionFailure,
    ProjectionScope,
    project_execution_event_batch,
)
from app.importers import RawImportRow, StagedImportBatch
from app.importers.urgent_demand import UrgentDemandImport
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
    import_package_id_for,
)
from app.snapshots.projection import build_projected_snapshot

_SQLALCHEMY = import_module("sqlalchemy")
create_engine = cast(Any, getattr(_SQLALCHEMY, "create_engine"))
text = cast(Any, getattr(_SQLALCHEMY, "text"))
SqlAlchemySnapshotRepository = cast(
    Any,
    getattr(
        import_module("app.infrastructure.snapshot_repository"),
        "SqlAlchemySnapshotRepository",
    ),
)

REPORT_VERSION = "p4-execution-fact-projection-report.v1"
TASK_ID = "TASK-P4-04"
DIFF_BASE = "3563bb236ce7b2c01794485110d4945a6e265105"

EVENT_TYPES = (
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
)
_FROZEN_SHA256 = {
    "schemas/json/execution-event.schema.json": (
        "90e62fce67b28baf1ba7f2a5e987702437828affce5d94911d9cc6ac55f73d8e"
    ),
    "schemas/json/planning-snapshot.v2.schema.json": (
        "d30ed42f8e5d1b497e2c41aec8bd840c1530e8a16c8594e22ed8db2dbc676a09"
    ),
    "schemas/json/import-package.v2.schema.json": (
        "166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56"
    ),
    "backend/migrations/versions/0005_replan_event_persistence.py": (
        "6b667137e477ce5665eace79dfc250e14b79663b1f181e9f59e6618ba6335342"
    ),
    "schemas/rules/state-machines.v1.yaml": (
        "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7"
    ),
    "pyproject.toml": (
        "327b705255dc9792139aa690351601a1e6a6cba019920142adfa656d6902fe5e"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}
_P6_SCHEMA_METADATA_PYPROJECT_SHA256 = (
    "c39c0ade6061de9a986eb0e5a3e2d8b568ccb37c7f7bf64242698af782b6c937"
)
_CUTOFF = "2026-08-20T00:00:00Z"


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _timestamp(minute: int) -> str:
    return (
        (datetime(2026, 8, 20, tzinfo=UTC) + timedelta(minutes=minute))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _sample_base(root: Path) -> ImmutablePlanningSnapshot:
    document = cast(
        ImportPackageDocumentV2,
        json.loads(
            (root / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["records"]["execution_facts"] = []
    document["records"]["operation_locks"] = []
    document["package_id"] = import_package_id_for(document)
    quality = validate_import_package(document)
    if not quality.passed:
        raise ValueError("sample base failed Data Validation")
    expansion = expand_orders(document, quality.document)
    return build_planning_snapshot(
        document,
        quality.document,
        expansion,
        cutoff_at_utc=_CUTOFF,
    )


def _scope(snapshot: ImmutablePlanningSnapshot, suffix: str) -> ProjectionScope:
    factory_id = snapshot.document["records"]["factories"][0]["factory_id"]
    return ProjectionScope(
        factory_id=factory_id,
        planning_scope_id=f"scope-p4-check-{suffix}",
        authority_id=f"authority-p4-check-{suffix}",
        stream_id=f"stream-p4-check-{suffix}",
        stream_version="1.0.0",
    )


def _event(
    scope: ProjectionScope,
    *,
    event_type: str,
    payload: dict[str, object],
    references: set[tuple[str, str]],
    position: int,
) -> dict[str, object]:
    occurred = _timestamp(position * 10)
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
                "source_system": "p4-machine-check-source",
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
        "occurred_at_utc": occurred,
        "received_at_utc": occurred,
        "entity_refs": [
            {"entity_type": entity_type, "entity_id": entity_id}
            for entity_type, entity_id in sorted(references)
        ],
        "payload": {"kind": event_type, **payload},
        "synthetic": True,
        "synthetic_provenance": {
            "scenario_id": "scenario-p4-machine-check",
            "scenario_version": "1.0.0",
            "factory_profile_id": "profile-p4-machine-check",
            "profile_version": "1.0.0",
            "generator_id": "generator-p4-machine-check",
            "generator_version": "1.0.0",
            "simulator_id": "simulator-p4-machine-check",
            "simulator_version": "1.0.0",
            "seed": 20260827,
        },
        "production_binding": False,
        "correlation_id": f"correlation-p4-machine-{position}",
        "event_fingerprint": "pending",
    }
    _refresh_event_identity(document)
    return document


def _refresh_event_identity(document: dict[str, object]) -> None:
    fingerprint = execution_event_fingerprint(document)
    document["event_fingerprint"] = fingerprint
    document["event_id"] = "execution-event-" + fingerprint.removeprefix("sha256:")


def _policy_reference() -> dict[str, str]:
    return {
        "document_version": "planning-policy.v2",
        "artifact_id": "policy-p4-machine-check",
        "fingerprint": f"sha256:{'a' * 64}",
    }


def _urgent_candidate(
    base: ImmutablePlanningSnapshot,
) -> tuple[ImmutablePlanningSnapshot, str]:
    candidate = cast(dict[str, object], deepcopy(base.document))
    records = cast(dict[str, list[dict[str, object]]], candidate["records"])
    source = deepcopy(records["demand_orders"][0]["source"])
    demand_id = "DEMAND-P4-MACHINE-URGENT-001"
    records["demand_orders"].append(
        {
            "demand_order_id": demand_id,
            "product_id": "PRODUCT-001",
            "quantity": 4,
            "quantity_unit": "piece",
            "due_at_utc": _timestamp(120),
            "source": source,
        }
    )
    records["production_orders"].append(
        {
            "production_order_id": "PRODUCTION-ORDER-P4-MACHINE-URGENT-001",
            "demand_order_id": demand_id,
            "routing_version_id": "ROUTING-001-V1",
            "quantity": 4,
            "quantity_unit": "piece",
            "release_at_utc": _timestamp(1),
            "material_ready_at_utc": _timestamp(1),
            "source": deepcopy(source),
        }
    )
    records["production_lots"].append(
        {
            "production_lot_id": "LOT-P4-MACHINE-URGENT-001",
            "production_order_id": "PRODUCTION-ORDER-P4-MACHINE-URGENT-001",
            "quantity": 4,
            "quantity_unit": "piece",
            "source": deepcopy(source),
        }
    )
    import_document = cast(
        ImportPackageDocumentV2,
        {
            "import_package_version": "import-package.v2",
            "schema_set_version": "2.0.0",
            "package_id": "pending",
            "source_versions": candidate["source_versions"],
            "normalization_rule_version": candidate["normalization_rule_version"],
            "canonicalization_version": candidate["canonicalization_version"],
            "synthetic": candidate["synthetic"],
            "synthetic_provenance": candidate["synthetic_provenance"],
            "records": records,
        },
    )
    import_document["package_id"] = import_package_id_for(import_document)
    quality = validate_import_package(import_document)
    if not quality.passed:
        raise ValueError("urgent candidate failed Data Validation")
    expansion = expand_orders(import_document, quality.document)
    return (
        build_planning_snapshot(
            import_document,
            quality.document,
            expansion,
            cutoff_at_utc=_timestamp(10),
        ),
        demand_id,
    )


def _all_event_projection_check(root: Path) -> dict[str, object]:
    base = _sample_base(root)
    predecessor = base.canonical_bytes
    scope = _scope(base, "all-events")
    candidate, demand_id = _urgent_candidate(base)
    first = next(
        item
        for item in base.document["operation_instances"]
        if item["routing_operation_id"] == "ROUTING-OP-001"
    )
    second = next(
        item
        for item in base.document["operation_instances"]
        if item["routing_operation_id"] == "ROUTING-OP-002"
    )
    first_id = first["operation_instance_id"]
    second_id = second["operation_instance_id"]
    first_resource = first["resource_options"][0]["resource_id"]
    second_resource = second["resource_options"][0]["resource_id"]
    start = _timestamp(15)
    lock_id = "LOCK-P4-MACHINE-001"
    events = (
        _event(
            scope,
            event_type="URGENT_DEMAND_RECEIVED",
            payload={
                "demand_order_id": demand_id,
                "quantity": 4,
                "due_at_utc": _timestamp(120),
                "priority_weight": 9,
                "priority_source": {
                    "source_system": "priority-machine-check",
                    "source_version": "1.0.0",
                    "source_record_id": "priority-p4-machine-001",
                },
            },
            references={("DEMAND_ORDER", demand_id)},
            position=1,
        ),
        _event(
            scope,
            event_type="OPERATION_STARTED",
            payload={
                "operation_id": first_id,
                "resource_id": first_resource,
                "actual_start_at_utc": start,
            },
            references={("OPERATION", first_id), ("RESOURCE", first_resource)},
            position=2,
        ),
        _event(
            scope,
            event_type="PROCESSING_REMAINING_CHANGED",
            payload={
                "operation_id": first_id,
                "remaining_seconds": 120,
                "as_of_utc": _timestamp(25),
            },
            references={("OPERATION", first_id)},
            position=3,
        ),
        _event(
            scope,
            event_type="OPERATION_COMPLETED",
            payload={
                "operation_id": first_id,
                "resource_id": first_resource,
                "actual_start_at_utc": start,
                "actual_end_at_utc": _timestamp(35),
            },
            references={("OPERATION", first_id), ("RESOURCE", first_resource)},
            position=4,
        ),
        _event(
            scope,
            event_type="MACHINE_UNAVAILABLE",
            payload={
                "resource_id": second_resource,
                "unavailable_from_utc": _timestamp(45),
                "unavailable_until_utc": None,
            },
            references={("RESOURCE", second_resource)},
            position=5,
        ),
        _event(
            scope,
            event_type="MACHINE_RECOVERED",
            payload={
                "resource_id": second_resource,
                "available_from_utc": _timestamp(55),
            },
            references={("RESOURCE", second_resource)},
            position=6,
        ),
        _event(
            scope,
            event_type="MATERIAL_DELAYED",
            payload={
                "material_id": "PRODUCTION-ORDER-001",
                "available_at_utc": _timestamp(100),
            },
            references={("MATERIAL", "PRODUCTION-ORDER-001")},
            position=7,
        ),
        _event(
            scope,
            event_type="MATERIAL_READY",
            payload={
                "material_id": "PRODUCTION-ORDER-001",
                "available_at_utc": _timestamp(75),
            },
            references={("MATERIAL", "PRODUCTION-ORDER-001")},
            position=8,
        ),
        _event(
            scope,
            event_type="PROCESSING_DURATION_CHANGED",
            payload={
                "operation_id": second_id,
                "final_duration_seconds": 333,
                "duration_source": "machine-check-observation",
                "source_version": "1.0.0",
            },
            references={("OPERATION", second_id)},
            position=9,
        ),
        _event(
            scope,
            event_type="LOCK_CREATED",
            payload={
                "lock_id": lock_id,
                "operation_id": second_id,
                "lock_type": "SOFT",
                "resource_id": second_resource,
                "start_at_utc": _timestamp(105),
                "end_at_utc": _timestamp(115),
                "policy_reference": _policy_reference(),
            },
            references={
                ("OPERATION", second_id),
                ("RESOURCE", second_resource),
                ("OPERATION_LOCK", lock_id),
            },
            position=10,
        ),
        _event(
            scope,
            event_type="LOCK_RELEASED",
            payload={
                "lock_id": lock_id,
                "release_reason": "POLICY_REEVALUATION",
                "policy_reference": _policy_reference(),
            },
            references={("OPERATION_LOCK", lock_id)},
            position=11,
        ),
    )
    urgent_snapshots = {cast(str, events[0]["event_id"]): candidate.document}
    projected = project_execution_event_batch(
        base.document,
        full_prefix=events,
        after_position=0,
        scope=scope,
        urgent_snapshots=urgent_snapshots,
    )
    replay = project_execution_event_batch(
        base.document,
        full_prefix=deepcopy(events),
        after_position=0,
        scope=scope,
        urgent_snapshots=urgent_snapshots,
    )
    snapshot = build_projected_snapshot(projected.document)
    replay_snapshot = build_projected_snapshot(replay.document)
    observed_types = {cast(str, event["event_type"]) for event in events}
    if observed_types != set(EVENT_TYPES):
        raise ValueError("approved ExecutionEvent type coverage is incomplete")
    completed = next(
        item
        for item in snapshot.document["operation_instances"]
        if item["operation_instance_id"] == first_id
    )
    if (
        snapshot != replay_snapshot
        or base.canonical_bytes != predecessor
        or completed["status"] != "COMPLETED"
        or snapshot.document["records"]["operation_locks"]
        or snapshot.document["entity_counts"]["demand_orders"] != 2
        or len(projected.priority_facts) != 1
    ):
        raise ValueError("event projection replay or fact result is incomplete")
    versions = snapshot.document["source_versions"]
    for source in (
        BASE_SNAPSHOT_SOURCE,
        EVENT_AUTHORITY_SOURCE,
        EVENT_STREAM_SOURCE,
    ):
        if source not in versions:
            raise ValueError("Snapshot projection lineage is incomplete")
    return {
        "event_types": list(EVENT_TYPES),
        "event_count": len(events),
        "from_position": projected.from_position,
        "through_position": projected.through_position,
        "priority_fact_count": len(projected.priority_facts),
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": snapshot.snapshot_hash,
        "predecessor_immutable": True,
        "byte_exact_replay": True,
    }


def _expect_failure(reason: ProjectionFailure, operation: Callable[[], object]) -> None:
    try:
        operation()
    except ExecutionFactProjectionError as error:
        if error.reason is reason:
            return
        raise ValueError(
            f"expected {reason.value}, observed {error.reason.value}"
        ) from error
    raise ValueError(f"expected {reason.value} rejection")


def _rejection_check(root: Path) -> dict[str, object]:
    base = _sample_base(root)
    predecessor = base.canonical_bytes
    scope = _scope(base, "rejections")
    operation = base.document["operation_instances"][0]
    operation_id = operation["operation_instance_id"]
    resource_id = operation["resource_options"][0]["resource_id"]
    gap = _event(
        scope,
        event_type="PROCESSING_DURATION_CHANGED",
        payload={
            "operation_id": operation_id,
            "final_duration_seconds": 120,
            "duration_source": "machine-check",
            "source_version": "1.0.0",
        },
        references={("OPERATION", operation_id)},
        position=2,
    )
    _expect_failure(
        ProjectionFailure.ORDERING_VIOLATION,
        lambda: project_execution_event_batch(
            base.document, full_prefix=(gap,), after_position=0, scope=scope
        ),
    )
    invalid_reference = _event(
        scope,
        event_type="OPERATION_STARTED",
        payload={
            "operation_id": "missing-operation",
            "resource_id": resource_id,
            "actual_start_at_utc": _timestamp(5),
        },
        references={("OPERATION", "missing-operation"), ("RESOURCE", resource_id)},
        position=1,
    )
    _expect_failure(
        ProjectionFailure.INVALID_REFERENCE,
        lambda: project_execution_event_batch(
            base.document,
            full_prefix=(invalid_reference,),
            after_position=0,
            scope=scope,
        ),
    )
    completion = _event(
        scope,
        event_type="OPERATION_COMPLETED",
        payload={
            "operation_id": operation_id,
            "resource_id": resource_id,
            "actual_start_at_utc": _timestamp(1),
            "actual_end_at_utc": _timestamp(5),
        },
        references={("OPERATION", operation_id), ("RESOURCE", resource_id)},
        position=1,
    )
    restart = _event(
        scope,
        event_type="OPERATION_STARTED",
        payload={
            "operation_id": operation_id,
            "resource_id": resource_id,
            "actual_start_at_utc": _timestamp(15),
        },
        references={("OPERATION", operation_id), ("RESOURCE", resource_id)},
        position=2,
    )
    _expect_failure(
        ProjectionFailure.TERMINAL_REGRESSION,
        lambda: project_execution_event_batch(
            base.document,
            full_prefix=(completion, restart),
            after_position=0,
            scope=scope,
        ),
    )
    cross_plane = deepcopy(gap)
    cross_plane["source_position"] = 1
    cross_plane["data_plane"] = "PRODUCTION"
    _refresh_event_identity(cross_plane)
    _expect_failure(
        ProjectionFailure.INVALID_EVENT,
        lambda: project_execution_event_batch(
            base.document,
            full_prefix=(cross_plane,),
            after_position=0,
            scope=scope,
        ),
    )
    if base.canonical_bytes != predecessor:
        raise ValueError("rejected projection mutated its predecessor")
    return {
        "gap_or_late": 1,
        "invalid_reference": 1,
        "terminal_regression": 1,
        "cross_plane": 1,
        "failed_projection_side_effects": 0,
    }


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _generation_context(root: Path) -> GenerationContext:
    scenario_root = root / "fixtures/synthetic/SIM-P1-INGRESS-001"
    return GenerationContext.from_documents(
        profile=cast(
            FactoryProfileDocument, _json(scenario_root / "factory-profile.json")
        ),
        scenario=cast(
            ScenarioSpecDocument, _json(scenario_root / "scenario-spec.json")
        ),
        target="test",
    )


def _unit_registry(root: Path) -> UnitConversionRegistry:
    document = cast(
        dict[str, object],
        yaml.safe_load(
            (root / "schemas/rules/unit-conversion-registry.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    return UnitConversionRegistry.from_mapping(document)


def _generated_base(
    root: Path,
) -> tuple[
    UnitConversionRegistry,
    GenerationContext,
    StagedImportBatch,
    ImmutablePlanningSnapshot,
]:
    registry = _unit_registry(root)
    context = _generation_context(root)
    batch = DeterministicSyntheticPackageGenerator(registry).prepare_batch(context)
    normalization = normalize_import(
        (NormalizationInput(batch, p1_mapping_profile(context)),),
        unit_registry=registry,
    )
    document = cast(ImportPackageDocumentV2, normalization.document)
    quality = validate_import_package(document)
    if not quality.passed:
        raise ValueError("generated base failed Data Validation")
    expansion = expand_orders(document, quality.document)
    snapshot = build_planning_snapshot(
        document,
        quality.document,
        expansion,
        cutoff_at_utc="2026-11-06T12:00:00Z",
    )
    return registry, context, batch, snapshot


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
    raw_payload = json.dumps(
        {
            "payload_json": payload_json,
            "record_type": record_type,
            "source_record_id": source_record_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return RawImportRow(
        row_identity=f"{record_type}:{source_record_id}",
        source_location=f"synthetic-records.jsonl:{position}",
        raw_payload=raw_payload,
    )


def _urgent_batch(batch: StagedImportBatch) -> StagedImportBatch:
    position = len(batch.rows)
    rows = batch.rows + (
        _raw_row(
            "demand_orders",
            "demand-order-urgent-machine-001",
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
            "production-order-urgent-machine-001",
            {
                "demand_order_id": "demand-order-urgent-machine-001",
                "routing_version_id": "routing-version-001",
                "quantity": 4,
                "quantity_unit": "piece",
                "release_at_utc": "2026-11-06T12:00:00Z",
                "material_ready_at_utc": "2026-11-06T12:00:00Z",
            },
            position=position + 2,
        ),
        _raw_row(
            "production_lots",
            "production-lot-urgent-machine-001",
            {
                "production_order_id": "production-order-urgent-machine-001",
                "quantity": 4,
                "quantity_unit": "piece",
            },
            position=position + 3,
        ),
    )
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


def _alembic_config(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option("script_location", str(root / "backend/migrations"))
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


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
            "duration_source": "machine-check-observation",
            "source_version": "1.0.0",
        },
        references={("OPERATION", operation_id)},
        position=position,
    )


def _persist_base(engine: Any, snapshot: ImmutablePlanningSnapshot) -> None:
    SqlAlchemySnapshotRepository(engine, data_plane=SnapshotDataPlane.SIMULATION).put(
        snapshot
    )


def _service(
    engine: Any,
    *,
    scope: ProjectionScope,
    unit_registry: UnitConversionRegistry,
) -> ExecutionFactProjectionService:
    adapters = cast(Any, import_module("app.infrastructure"))

    def checkpoint_factory(
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
    ) -> Any:
        return adapters.ProjectionCheckpoint(
            factory_id=factory_id,
            planning_scope_id=planning_scope_id,
            authority_id=authority_id,
            stream_id=stream_id,
            stream_version=stream_version,
            last_applied_position=last_applied_position,
            prefix_fingerprint=prefix_fingerprint,
            fact_checkpoint=adapters.ArtifactReference(
                document_version=fact_document_version,
                artifact_id=fact_artifact_id,
                fingerprint=fact_fingerprint,
            ),
            updated_at_utc=updated_at_utc,
        )

    def audit_factory(
        *,
        action: str,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: str,
        idempotency_scope: str,
        idempotency_key_reference: str,
        request_fingerprint: str | None,
        occurred_at_utc: str,
    ) -> Any:
        return adapters.build_replan_audit_record(
            action=adapters.ReplanAuditAction(action),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            correlation_id=correlation_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_reference=idempotency_key_reference,
            request_fingerprint=request_fingerprint,
            occurred_at_utc=occurred_at_utc,
        )

    return ExecutionFactProjectionService(
        transaction_factory=engine.begin,
        scope=scope,
        events=adapters.SqlAlchemyExecutionEventRepository(
            engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
        ),
        checkpoints=adapters.SqlAlchemyProjectionCheckpointRepository(
            engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
        ),
        audits=adapters.SqlAlchemyReplanAuditRepository(
            engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
        ),
        snapshots=SqlAlchemySnapshotRepository(
            engine, data_plane=SnapshotDataPlane.SIMULATION
        ),
        checkpoint_factory=checkpoint_factory,
        audit_factory=audit_factory,
        persistence_error_types=(
            adapters.WorkspacePersistenceError,
            _SQLALCHEMY.exc.SQLAlchemyError,
            SnapshotError,
        ),
        unit_registry=unit_registry,
    )


def _durability_checks(root: Path) -> dict[str, dict[str, object]]:
    with TemporaryDirectory(prefix="plantnexus-p4-fact-projection-") as directory:
        database_path = Path(directory) / "projection.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = _alembic_config(root, database_url)
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            registry, context, batch, base = _generated_base(root)
            _persist_base(engine, base)
            scope = _scope(base, "durable")
            service = _service(engine, scope=scope, unit_registry=registry)
            event = _duration_event(base, scope)
            ingress = service.ingest_event(event)
            ingress_replay = service.ingest_event(event)
            committed = service.project_available(base)
            lost_response_replay = service.project_available(base)
            current_replay = service.project_available(committed.snapshot)
            if (
                ingress.replayed
                or not ingress_replay.replayed
                or committed.replayed
                or not lost_response_replay.replayed
                or not current_replay.replayed
                or lost_response_replay.snapshot != committed.snapshot
            ):
                raise ValueError("durable exact replay contract failed")
            with engine.connect() as connection:
                event_audit_count = cast(
                    int,
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM replan_audit_records "
                            "WHERE aggregate_type = :aggregate_type "
                            "AND aggregate_id = :aggregate_id"
                        ),
                        {
                            "aggregate_type": "EXECUTION_EVENT",
                            "aggregate_id": cast(str, event["event_id"]),
                        },
                    ),
                )
            if event_audit_count != 1:
                raise ValueError("ExecutionEvent audit replay duplicated a record")

            urgent_batch = _urgent_batch(batch)
            urgent_input = NormalizationInput(urgent_batch, p1_mapping_profile(context))
            candidate = normalize_import((urgent_input,), unit_registry=registry)
            demand = next(
                item
                for item in cast(ImportPackageDocumentV2, candidate.document)[
                    "records"
                ]["demand_orders"]
                if item["source"]["source_record_id"]
                == "demand-order-urgent-machine-001"
            )
            demand_id = demand["demand_order_id"]
            urgent_scope = _scope(base, "standard-urgent")
            urgent_event = _event(
                urgent_scope,
                event_type="URGENT_DEMAND_RECEIVED",
                payload={
                    "demand_order_id": demand_id,
                    "quantity": 4,
                    "due_at_utc": "2026-11-07T12:00:00Z",
                    "priority_weight": 9,
                    "priority_source": {
                        "source_system": "machine-priority-source",
                        "source_version": "1.0.0",
                        "source_record_id": "priority-machine-urgent-001",
                    },
                },
                references={("DEMAND_ORDER", demand_id)},
                position=1,
            )
            urgent_import = UrgentDemandImport(
                event_id=cast(str, urgent_event["event_id"]),
                inputs=(urgent_input,),
            )
            urgent_service = _service(
                engine, scope=urgent_scope, unit_registry=registry
            )
            urgent_service.ingest_event(urgent_event)
            urgent_committed = urgent_service.project_available(
                base,
                urgent_imports={cast(str, urgent_event["event_id"]): urgent_import},
            )
            urgent_replay = urgent_service.project_available(
                base,
                urgent_imports={cast(str, urgent_event["event_id"]): urgent_import},
            )
            if (
                urgent_committed.snapshot.document["entity_counts"]["demand_orders"]
                != 3
                or len(urgent_committed.priority_facts) != 1
                or not urgent_replay.replayed
            ):
                raise ValueError("standard Urgent Demand projection failed")

            rollback_scope = _scope(base, "rollback")
            rollback_service = _service(
                engine, scope=rollback_scope, unit_registry=registry
            )
            rollback_event = _duration_event(base, rollback_scope)
            rollback_service.ingest_event(rollback_event)
            with engine.connect() as connection:
                snapshots_before = cast(
                    int,
                    connection.scalar(text("SELECT count(*) FROM planning_snapshots")),
                )
                checkpoints_before = cast(
                    int,
                    connection.scalar(
                        text("SELECT count(*) FROM replan_projection_checkpoints")
                    ),
                )
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TRIGGER fail_projection_audit
                        BEFORE INSERT ON replan_audit_records
                        WHEN NEW.action = 'PROJECTION_CHECKPOINT_COMMITTED'
                        BEGIN
                            SELECT RAISE(ABORT, 'injected projection failure');
                        END
                        """
                    )
                )
            _expect_failure(
                ProjectionFailure.PERSISTENCE_FAILED,
                lambda: rollback_service.project_available(base),
            )
            with engine.connect() as connection:
                snapshots_after = cast(
                    int,
                    connection.scalar(text("SELECT count(*) FROM planning_snapshots")),
                )
                checkpoints_after = cast(
                    int,
                    connection.scalar(
                        text("SELECT count(*) FROM replan_projection_checkpoints")
                    ),
                )
                durable_events = cast(
                    int,
                    connection.scalar(
                        text("SELECT count(*) FROM execution_event_ledger")
                    ),
                )
            if (
                snapshots_after != snapshots_before
                or checkpoints_after != checkpoints_before
                or durable_events != 3
            ):
                raise ValueError("projection transaction left a partial result")
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")

    return {
        "ingress": {
            "event_append": 1,
            "event_exact_replay": 1,
            "audit_rows": event_audit_count,
            "event_update_or_delete": "NOT_USED",
        },
        "projection": {
            "snapshot_commits": 2,
            "checkpoint_position": committed.checkpoint.last_applied_position,
            "checkpoint_state_revision": committed.checkpoint_state_revision,
            "lost_response_exact_replay": 1,
            "current_snapshot_exact_replay": 1,
        },
        "urgent": {
            "raw_staging_inputs": len(urgent_import.inputs),
            "normalization": "PASS",
            "data_validation": "PASS",
            "order_expansion": "PASS",
            "planning_snapshot": "PASS",
            "priority_facts": len(urgent_committed.priority_facts),
            "private_canonical_shortcut": "NONE",
        },
        "atomicity": {
            "injected_failure": "PROJECTION_AUDIT_INSERT",
            "partial_snapshots": snapshots_after - snapshots_before,
            "partial_checkpoints": checkpoints_after - checkpoints_before,
            "ingress_events_retained": durable_events,
            "external_side_effects": 0,
        },
    }


def _frozen_input_check(root: Path) -> dict[str, object]:
    observed = {
        path: sha256((root / path).read_bytes()).hexdigest() for path in _FROZEN_SHA256
    }
    frozen_observed = dict(observed)
    pyproject_digest = frozen_observed.pop("pyproject.toml")
    frozen_expected = dict(_FROZEN_SHA256)
    p4_pyproject_digest = frozen_expected.pop("pyproject.toml")
    if frozen_observed != frozen_expected or pyproject_digest not in {
        p4_pyproject_digest,
        _P6_SCHEMA_METADATA_PYPROJECT_SHA256,
    }:
        raise ValueError("frozen Schema/migration/dependency input changed")
    return {
        "artifact_count": len(observed),
        "sha256": observed,
        "schema_changes": "NONE",
        "migration_changes": "NONE",
        "dependency_changes": "NONE",
    }


def _boundary_check(root: Path) -> dict[str, object]:
    sources = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (
            "backend/app/domain/execution_fact_projection.py",
            "backend/app/application/execution_fact_projection.py",
            "backend/app/importers/urgent_demand.py",
            "backend/app/snapshots/projection.py",
        )
    )
    forbidden_imports = (
        "app.planning.backends",
        "app.planning.validation",
        "app.simulation.execution",
        "app.api",
        "app.exporters",
        "app.infrastructure",
        "sqlalchemy",
    )
    if any(value in sources for value in forbidden_imports):
        raise ValueError("projection crossed a deferred capability boundary")
    return {
        "data_plane": "SIMULATION_ONLY",
        "event_ingress_transaction": "LEDGER_PLUS_AUDIT",
        "projection_transaction": "SNAPSHOT_PLUS_CHECKPOINT_PLUS_AUDIT",
        "schedule_version_state_transition": "NONE",
        "replan_request": "NOT_CREATED",
        "freeze_window": "NOT_DECIDED",
        "obj_002_stability": "NOT_IMPLEMENTED",
        "solver_validator_change_report_simulator": "NOT_CALLED",
        "p5_capabilities": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }


def run_projection_checks(root: Path) -> dict[str, object]:
    frozen = _frozen_input_check(root)
    projection = _all_event_projection_check(root)
    rejections = _rejection_check(root)
    durable = _durability_checks(root)
    boundaries = _boundary_check(root)
    checks = [
        _pass("frozen-schema-migration-state-and-dependencies", frozen),
        _pass("all-approved-event-types-to-canonical-facts", projection),
        _pass("event-order-reference-terminal-and-plane-rejections", rejections),
        _pass("ledger-and-audit-ingress-exact-replay", durable["ingress"]),
        _pass("immutable-snapshot-checkpoint-and-replay", durable["projection"]),
        _pass("urgent-demand-standard-import-validation-expansion", durable["urgent"]),
        _pass("projection-failure-atomicity", durable["atomicity"]),
        _pass("p4-p5-production-capability-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "diff_base": DIFF_BASE,
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "counts": {
            "event_types": len(EVENT_TYPES),
            "positive_event_vectors": projection["event_count"],
            "negative_vectors": 4,
            "standard_urgent_imports": 1,
            "durable_event_rows": durable["atomicity"]["ingress_events_retained"],
            "committed_projection_snapshots": 2,
            "atomic_rollback_cases": 1,
            "machine_checks": len(checks),
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_projection_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "error_type": type(error).__name__,
            "error_message": "execution fact projection evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DIFF_BASE", "REPORT_VERSION", "main", "run_projection_checks"]
