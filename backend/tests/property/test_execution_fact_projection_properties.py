"""TEST-PROPERTY deterministic and fail-closed ExecutionEvent projection."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import cast

from hypothesis import given, seed, settings
from hypothesis import strategies as st
import pytest

from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.execution_contracts import execution_event_fingerprint
from app.domain.execution_fact_projection import (
    ExecutionFactProjectionError,
    ProjectionFailure,
    ProjectionScope,
    project_execution_event_batch,
)
from app.normalization.order_expansion import expand_orders
from app.snapshots import (
    ImmutablePlanningSnapshot,
    build_planning_snapshot,
    import_package_id_for,
)
from app.snapshots.projection import build_projected_snapshot

ROOT = Path(__file__).resolve().parents[3]
SCOPE = ProjectionScope(
    factory_id="FACTORY-001",
    planning_scope_id="scope-p4-projection-property",
    authority_id="authority-p4-projection-property",
    stream_id="stream-p4-projection-property",
    stream_version="1.0.0",
)


def _base_snapshot() -> ImmutablePlanningSnapshot:
    document = cast(
        ImportPackageDocumentV2,
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["records"]["execution_facts"] = []
    document["records"]["operation_locks"] = []
    document["package_id"] = import_package_id_for(document)
    quality = validate_import_package(document)
    expansion = expand_orders(document, quality.document)
    return build_planning_snapshot(
        document,
        quality.document,
        expansion,
        cutoff_at_utc="2026-08-20T00:00:00Z",
    )


def _event(
    operation_id: str,
    *,
    duration_seconds: int,
    position: int = 1,
) -> dict[str, object]:
    document: dict[str, object] = {
        "execution_event_version": "execution-event.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "event_id": "pending",
        "event_type": "PROCESSING_DURATION_CHANGED",
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
                "source_system": "property-source",
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
        "occurred_at_utc": "2026-08-20T00:01:00Z",
        "received_at_utc": "2026-08-20T00:01:01Z",
        "entity_refs": [{"entity_type": "OPERATION", "entity_id": operation_id}],
        "payload": {
            "kind": "PROCESSING_DURATION_CHANGED",
            "operation_id": operation_id,
            "final_duration_seconds": duration_seconds,
            "duration_source": "property-observation",
            "source_version": "1.0.0",
        },
        "synthetic": True,
        "synthetic_provenance": {
            "scenario_id": "scenario-p4-property",
            "scenario_version": "1.0.0",
            "factory_profile_id": "profile-p4-property",
            "profile_version": "1.0.0",
            "generator_id": "generator-p4-property",
            "generator_version": "1.0.0",
            "simulator_id": "simulator-p4-property",
            "simulator_version": "1.0.0",
            "seed": 20260827,
        },
        "production_binding": False,
        "correlation_id": f"correlation-property-{position}",
        "event_fingerprint": "pending",
    }
    _refresh_identity(document)
    return document


def _refresh_identity(document: dict[str, object]) -> None:
    fingerprint = execution_event_fingerprint(document)
    document["event_fingerprint"] = fingerprint
    document["event_id"] = "execution-event-" + fingerprint.removeprefix("sha256:")


@seed(2026082704)
@settings(max_examples=48, deadline=None)
@given(duration_seconds=st.integers(min_value=1, max_value=86_400))
def test_projection_replay_is_byte_exact_and_predecessor_is_immutable(
    duration_seconds: int,
) -> None:
    """TEST-IDEMPOTENCY / TEST-SNAPSHOT-REPLAY-001 generated evidence."""

    base = _base_snapshot()
    predecessor = base.canonical_bytes
    operation = base.document["operation_instances"][0]
    operation_id = operation["operation_instance_id"]
    event = _event(operation_id, duration_seconds=duration_seconds)

    first = project_execution_event_batch(
        base.document,
        full_prefix=(event,),
        after_position=0,
        scope=SCOPE,
    )
    replay = project_execution_event_batch(
        base.document,
        full_prefix=(deepcopy(event),),
        after_position=0,
        scope=SCOPE,
    )
    first_snapshot = build_projected_snapshot(first.document)
    replay_snapshot = build_projected_snapshot(replay.document)
    projected = next(
        item
        for item in first_snapshot.document["operation_instances"]
        if item["operation_instance_id"] == operation_id
    )

    assert base.canonical_bytes == predecessor
    assert first_snapshot.canonical_bytes == replay_snapshot.canonical_bytes
    assert first_snapshot.snapshot_hash == replay_snapshot.snapshot_hash
    assert first.stream_fingerprint == replay.stream_fingerprint
    assert all(
        option["final_duration_seconds"] == duration_seconds
        for option in projected["resource_options"]
    )


@seed(2026082705)
@settings(max_examples=32, deadline=None)
@given(mutation=st.sampled_from(("gap", "production", "authority", "received-before")))
def test_order_authority_and_plane_mutations_fail_without_snapshot_side_effect(
    mutation: str,
) -> None:
    """TEST-SIM-ISOLATION and ordered-prefix negative generated evidence."""

    base = _base_snapshot()
    predecessor = base.canonical_bytes
    operation_id = base.document["operation_instances"][0]["operation_instance_id"]
    event = _event(operation_id, duration_seconds=120)
    expected = ProjectionFailure.ORDERING_VIOLATION
    if mutation == "gap":
        event["source_position"] = 2
    elif mutation == "production":
        event["data_plane"] = "PRODUCTION"
        expected = ProjectionFailure.INVALID_EVENT
    elif mutation == "authority":
        cast(dict[str, object], event["authority"])["authority_id"] = "other"
        cast(dict[str, object], event["source_stream"])["authority_id"] = "other"
        expected = ProjectionFailure.AUTHORITY_MISMATCH
    else:
        event["received_at_utc"] = "2026-08-20T00:00:59Z"
        expected = ProjectionFailure.INVALID_EVENT
    _refresh_identity(event)

    with pytest.raises(ExecutionFactProjectionError) as rejected:
        project_execution_event_batch(
            base.document,
            full_prefix=(event,),
            after_position=0,
            scope=SCOPE,
        )

    assert rejected.value.reason is expected
    assert base.canonical_bytes == predecessor
