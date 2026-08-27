"""TEST-EXECUTION-FACT-PROJECTION-001 pure P4 projection evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import cast

import pytest

from app.data_validation import validate_import_package
from app.domain.canonical_records import (
    ImportPackageDocumentV2,
    OperationInstanceDocument,
)
from app.domain.execution_contracts import execution_event_fingerprint
from app.domain.execution_fact_projection import (
    ExecutionFactProjectionError,
    ProjectionFailure,
    ProjectionScope,
    project_execution_event_batch,
    validate_execution_event,
)
from app.normalization.order_expansion import expand_orders
from app.snapshots import build_planning_snapshot, import_package_id_for
from app.snapshots.contracts import ImmutablePlanningSnapshot
from app.snapshots.projection import build_projected_snapshot

ROOT = Path(__file__).resolve().parents[3]
SCOPE = ProjectionScope(
    factory_id="FACTORY-001",
    planning_scope_id="scope-p4-projection-001",
    authority_id="authority-p4-projection-001",
    stream_id="stream-p4-projection-001",
    stream_version="1.0.0",
)
BASE_CUTOFF = "2026-08-20T00:00:00Z"


def _base_snapshot() -> ImmutablePlanningSnapshot:
    document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    records = cast(dict[str, object], document["records"])
    records["execution_facts"] = []
    records["operation_locks"] = []
    document["package_id"] = import_package_id_for(document)
    import_document = cast(ImportPackageDocumentV2, document)
    quality = validate_import_package(import_document)
    expansion = expand_orders(
        import_document,
        quality.document,
    )
    return build_planning_snapshot(
        document,
        quality.document,
        expansion,
        cutoff_at_utc=BASE_CUTOFF,
    )


def _timestamp(minute: int) -> str:
    return (
        (datetime(2026, 8, 20, 0, 0, tzinfo=UTC) + timedelta(minutes=minute))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _event(
    event_type: str,
    payload: dict[str, object],
    *,
    position: int,
    references: set[tuple[str, str]],
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
        "factory_id": SCOPE.factory_id,
        "planning_scope_id": SCOPE.planning_scope_id,
        "authority": {
            "authority_version": "execution-event-authority.v1",
            "authority_id": SCOPE.authority_id,
            "authority_scope": (
                f"SIMULATION/{SCOPE.factory_id}/{SCOPE.planning_scope_id}"
            ),
            "source": {
                "source_system": "test-execution-source",
                "source_version": "1.0.0",
                "source_record_id": SCOPE.stream_id,
            },
            "decision": "AUTHORIZED_SIMULATION_SOURCE",
            "production_binding": False,
        },
        "source_stream": {
            "stream_id": SCOPE.stream_id,
            "stream_version": SCOPE.stream_version,
            "authority_id": SCOPE.authority_id,
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
            "scenario_id": "scenario-p4-projection",
            "scenario_version": "1.0.0",
            "factory_profile_id": "profile-p4-projection",
            "profile_version": "1.0.0",
            "generator_id": "generator-p4-projection",
            "generator_version": "1.0.0",
            "simulator_id": "simulator-p4-projection",
            "simulator_version": "1.0.0",
            "seed": 20260827,
        },
        "production_binding": False,
        "correlation_id": f"correlation-{position:03d}",
        "event_fingerprint": "pending",
    }
    fingerprint = execution_event_fingerprint(document)
    document["event_fingerprint"] = fingerprint
    document["event_id"] = f"execution-event-{fingerprint.removeprefix('sha256:')}"
    return document


def _instance(
    snapshot: ImmutablePlanningSnapshot, routing_operation_id: str
) -> OperationInstanceDocument:
    document = snapshot.document
    return next(
        item
        for item in document["operation_instances"]
        if item["routing_operation_id"] == routing_operation_id
    )


def _policy_reference() -> dict[str, str]:
    return {
        "document_version": "planning-policy.v2",
        "artifact_id": "policy-p4-projection",
        "fingerprint": f"sha256:{'a' * 64}",
    }


def test_operation_lifecycle_is_deterministic_and_keeps_predecessor_immutable() -> None:
    base = _base_snapshot()
    base_bytes = base.canonical_bytes  # type: ignore[attr-defined]
    operation = _instance(base, "ROUTING-OP-001")
    operation_id = cast(str, operation["operation_instance_id"])
    resource_id = "RESOURCE-001"
    start = _timestamp(5)
    events = (
        _event(
            "OPERATION_STARTED",
            {
                "operation_id": operation_id,
                "resource_id": resource_id,
                "actual_start_at_utc": start,
            },
            position=1,
            references={("OPERATION", operation_id), ("RESOURCE", resource_id)},
        ),
        _event(
            "PROCESSING_REMAINING_CHANGED",
            {
                "operation_id": operation_id,
                "remaining_seconds": 120,
                "as_of_utc": _timestamp(15),
            },
            position=2,
            references={("OPERATION", operation_id)},
        ),
        _event(
            "OPERATION_COMPLETED",
            {
                "operation_id": operation_id,
                "resource_id": resource_id,
                "actual_start_at_utc": start,
                "actual_end_at_utc": _timestamp(25),
            },
            position=3,
            references={("OPERATION", operation_id), ("RESOURCE", resource_id)},
        ),
    )
    first = project_execution_event_batch(
        base.document,  # type: ignore[attr-defined]
        full_prefix=events,
        after_position=0,
        scope=SCOPE,
    )
    second = project_execution_event_batch(
        base.document,  # type: ignore[attr-defined]
        full_prefix=events,
        after_position=0,
        scope=SCOPE,
    )
    first_snapshot = build_projected_snapshot(first.document)
    second_snapshot = build_projected_snapshot(second.document)

    projected = _instance(first_snapshot, "ROUTING-OP-001")
    fact_id = cast(str, projected.get("execution_fact_id"))
    fact = next(
        item
        for item in first_snapshot.document["records"]["execution_facts"]
        if item["execution_fact_id"] == fact_id
    )
    assert projected["status"] == "COMPLETED"
    assert fact.get("actual_end_at_utc") == _timestamp(25)
    assert first_snapshot == second_snapshot
    assert first.stream_fingerprint == second.stream_fingerprint
    assert base.canonical_bytes == base_bytes  # type: ignore[attr-defined]
    assert base.snapshot_hash != first_snapshot.snapshot_hash  # type: ignore[attr-defined]


def test_machine_material_duration_and_lock_events_project_exact_facts() -> None:
    base = _base_snapshot()
    operation = _instance(base, "ROUTING-OP-002")
    operation_id = cast(str, operation["operation_instance_id"])
    lock_id = "LOCK-P4-EVENT-001"
    events = (
        _event(
            "MACHINE_UNAVAILABLE",
            {
                "resource_id": "RESOURCE-001",
                "unavailable_from_utc": _timestamp(9),
                "unavailable_until_utc": None,
            },
            position=1,
            references={("RESOURCE", "RESOURCE-001")},
        ),
        _event(
            "MACHINE_RECOVERED",
            {
                "resource_id": "RESOURCE-001",
                "available_from_utc": _timestamp(19),
            },
            position=2,
            references={("RESOURCE", "RESOURCE-001")},
        ),
        _event(
            "MATERIAL_DELAYED",
            {
                "material_id": "PRODUCTION-ORDER-001",
                "available_at_utc": _timestamp(50),
            },
            position=3,
            references={("MATERIAL", "PRODUCTION-ORDER-001")},
        ),
        _event(
            "MATERIAL_READY",
            {
                "material_id": "PRODUCTION-ORDER-001",
                "available_at_utc": _timestamp(35),
            },
            position=4,
            references={("MATERIAL", "PRODUCTION-ORDER-001")},
        ),
        _event(
            "PROCESSING_DURATION_CHANGED",
            {
                "operation_id": operation_id,
                "final_duration_seconds": 333,
                "duration_source": "event-observation",
                "source_version": "1.0.0",
            },
            position=5,
            references={("OPERATION", operation_id)},
        ),
        _event(
            "LOCK_CREATED",
            {
                "lock_id": lock_id,
                "operation_id": operation_id,
                "lock_type": "SOFT",
                "resource_id": "RESOURCE-001",
                "start_at_utc": _timestamp(55),
                "end_at_utc": _timestamp(65),
                "policy_reference": _policy_reference(),
            },
            position=6,
            references={
                ("OPERATION", operation_id),
                ("RESOURCE", "RESOURCE-001"),
                ("OPERATION_LOCK", lock_id),
            },
        ),
        _event(
            "LOCK_RELEASED",
            {
                "lock_id": lock_id,
                "release_reason": "POLICY_REEVALUATION",
                "policy_reference": _policy_reference(),
            },
            position=7,
            references={("OPERATION_LOCK", lock_id)},
        ),
    )
    projected = project_execution_event_batch(
        base.document,  # type: ignore[attr-defined]
        full_prefix=events,
        after_position=0,
        scope=SCOPE,
    )
    snapshot = build_projected_snapshot(projected.document)
    records = snapshot.document["records"]
    resource = records["resources"][0]
    calendar = records["calendars"][0]
    order = records["production_orders"][0]
    option = next(
        value
        for value in records["routing_resource_options"]
        if value["routing_operation_id"] == "ROUTING-OP-002"
    )

    assert resource["status"] == "AVAILABLE"
    assert any(
        interval["start_at_utc"] == _timestamp(9)
        and interval["end_at_utc"] == _timestamp(19)
        for interval in calendar["unavailable_intervals"]
    )
    assert order["material_ready_at_utc"] == _timestamp(35)
    assert option["final_duration_seconds"] == 333
    assert records["operation_locks"] == []
    assert _instance(snapshot, "ROUTING-OP-002")["lock_ids"] == []


def test_urgent_candidate_adds_only_standard_import_demand_lineage() -> None:
    base = _base_snapshot()
    urgent_import = cast(dict[str, object], deepcopy(base.document))  # type: ignore[attr-defined]
    records = cast(dict[str, list[dict[str, object]]], urgent_import["records"])
    source = deepcopy(records["demand_orders"][0]["source"])
    records["demand_orders"].append(
        {
            "demand_order_id": "DEMAND-URGENT-001",
            "product_id": "PRODUCT-001",
            "quantity": 4,
            "quantity_unit": "piece",
            "due_at_utc": _timestamp(120),
            "source": source,
        }
    )
    records["production_orders"].append(
        {
            "production_order_id": "PRODUCTION-ORDER-URGENT-001",
            "demand_order_id": "DEMAND-URGENT-001",
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
            "production_lot_id": "LOT-URGENT-001",
            "production_order_id": "PRODUCTION-ORDER-URGENT-001",
            "quantity": 4,
            "quantity_unit": "piece",
            "source": deepcopy(source),
        }
    )
    # Rebuild the exact standard Import/Validation/Expansion/Snapshot chain.
    import_document = {
        "import_package_version": "import-package.v2",
        "schema_set_version": "2.0.0",
        "package_id": "pending",
        "source_versions": urgent_import["source_versions"],
        "normalization_rule_version": urgent_import["normalization_rule_version"],
        "canonicalization_version": urgent_import["canonicalization_version"],
        "synthetic": urgent_import["synthetic"],
        "synthetic_provenance": urgent_import["synthetic_provenance"],
        "records": records,
    }
    import_document["package_id"] = import_package_id_for(import_document)
    typed_import_document = cast(ImportPackageDocumentV2, import_document)
    quality = validate_import_package(typed_import_document)
    expansion = expand_orders(
        typed_import_document,
        quality.document,
    )
    candidate = build_planning_snapshot(
        import_document,
        quality.document,
        expansion,
        cutoff_at_utc=_timestamp(10),
    )
    event = _event(
        "URGENT_DEMAND_RECEIVED",
        {
            "demand_order_id": "DEMAND-URGENT-001",
            "quantity": 4,
            "due_at_utc": _timestamp(120),
            "priority_weight": 9,
            "priority_source": {
                "source_system": "urgent-priority-source",
                "source_version": "1.0.0",
                "source_record_id": "priority-urgent-001",
            },
        },
        position=1,
        references={("DEMAND_ORDER", "DEMAND-URGENT-001")},
    )
    projected = project_execution_event_batch(
        base.document,  # type: ignore[attr-defined]
        full_prefix=(event,),
        after_position=0,
        scope=SCOPE,
        urgent_snapshots={cast(str, event["event_id"]): candidate.document},
    )
    snapshot = build_projected_snapshot(projected.document)

    assert snapshot.document["entity_counts"]["demand_orders"] == 2
    assert projected.priority_facts[0].priority_weight == 9
    assert projected.priority_facts[0].demand_order_id == "DEMAND-URGENT-001"


def test_gap_terminal_regression_and_missing_urgent_import_fail_closed() -> None:
    base = _base_snapshot()
    operation = _instance(base, "ROUTING-OP-001")
    operation_id = cast(str, operation["operation_instance_id"])
    gap = _event(
        "OPERATION_STARTED",
        {
            "operation_id": operation_id,
            "resource_id": "RESOURCE-001",
            "actual_start_at_utc": _timestamp(5),
        },
        position=2,
        references={("OPERATION", operation_id), ("RESOURCE", "RESOURCE-001")},
    )
    with pytest.raises(ExecutionFactProjectionError) as ordering:
        project_execution_event_batch(
            base.document,  # type: ignore[attr-defined]
            full_prefix=(gap,),
            after_position=0,
            scope=SCOPE,
        )
    assert ordering.value.reason is ProjectionFailure.ORDERING_VIOLATION

    urgent = _event(
        "URGENT_DEMAND_RECEIVED",
        {
            "demand_order_id": "DEMAND-MISSING",
            "quantity": 1,
            "due_at_utc": _timestamp(120),
            "priority_weight": 1,
            "priority_source": {
                "source_system": "priority",
                "source_version": "1.0.0",
                "source_record_id": "priority-missing",
            },
        },
        position=1,
        references={("DEMAND_ORDER", "DEMAND-MISSING")},
    )
    validate_execution_event(urgent, scope=SCOPE)
    with pytest.raises(ExecutionFactProjectionError) as missing:
        project_execution_event_batch(
            base.document,  # type: ignore[attr-defined]
            full_prefix=(urgent,),
            after_position=0,
            scope=SCOPE,
        )
    assert missing.value.reason is ProjectionFailure.URGENT_IMPORT_REQUIRED
