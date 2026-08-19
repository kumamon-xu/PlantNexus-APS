"""Unit evidence for TASK-P1-07 deterministic order expansion."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.data_validation import validate_import_package
from app.domain.canonical_records import (
    COLLECTION_ID_FIELDS,
    ImportPackageDocumentV2,
    PlanningSnapshotDocumentV2,
    validate_planning_snapshot_v2,
)
from app.domain.production import (
    ORDER_EXPANSION_VERSION,
    SPLIT_MERGE_CAPABILITY,
    OrderExpansionError,
    OrderExpansionErrorCode,
    OrderExpansionResult,
    stable_expansion_id,
)
from app.normalization import expand_orders

ROOT = Path(__file__).resolve().parents[3]


type MutableImport = dict[str, Any]


def _load_import() -> MutableImport:
    return cast(
        MutableImport,
        json.loads(
        (ROOT / "schemas" / "samples" / "import-package.v2.synthetic.json").read_text(
            encoding="utf-8"
        )
        ),
    )


def _pass_report(document: MutableImport) -> Mapping[str, object]:
    result = validate_import_package(cast(Mapping[str, object], document))
    assert result.passed, result.document
    return cast(Mapping[str, object], result.document)


def _source(record_id: str) -> dict[str, str]:
    return {
        "source_system": "schema_sample",
        "source_version": "1.0.0",
        "source_record_id": record_id,
    }


def _branch_merge_import() -> MutableImport:
    document = _load_import()
    records = document["records"]
    records["workshops"].append(
        {
            "workshop_id": "WORKSHOP-002",
            "workshop_code": "W002",
            "factory_id": "FACTORY-001",
            "source": _source("SRC-WORKSHOP-002"),
        }
    )
    records["production_lines"].append(
        {
            "production_line_id": "LINE-002",
            "production_line_code": "L002",
            "workshop_id": "WORKSHOP-002",
            "source": _source("SRC-LINE-002"),
        }
    )
    records["resource_groups"].append(
        {
            "resource_group_id": "GROUP-002",
            "resource_group_code": "G002",
            "production_line_id": "LINE-002",
            "source": _source("SRC-GROUP-002"),
        }
    )
    records["calendars"].append(
        {
            "calendar_id": "CALENDAR-002",
            "timezone": "Asia/Hong_Kong",
            "unavailable_intervals": [],
            "source": _source("SRC-CALENDAR-002"),
        }
    )
    records["resources"].append(
        {
            "resource_id": "RESOURCE-002",
            "resource_code": "R002",
            "resource_type": "MACHINE",
            "status": "AVAILABLE",
            "resource_group_id": "GROUP-002",
            "calendar_id": "CALENDAR-002",
            "capabilities": ["CUTTING"],
            "source": _source("SRC-RESOURCE-002"),
        }
    )
    records["routing_operations"] = [
        {
            "routing_operation_id": f"ROUTING-OP-{number:03d}",
            "routing_version_id": "ROUTING-001-V1",
            "operation_code": code,
            "required_capabilities": ["CUTTING"],
            "source": _source(f"SRC-ROUTING-OP-{number:03d}"),
        }
        for number, code in enumerate(("START", "LEFT", "RIGHT", "MERGE"), 1)
    ]
    edge_specs = (
        (1, 1, 2, 0),
        (2, 1, 3, 300),
        (3, 2, 4, 0),
        (4, 3, 4, 300),
    )
    records["routing_precedence_edges"] = [
        {
            "routing_precedence_edge_id": f"ROUTING-EDGE-{edge_number:03d}",
            "routing_version_id": "ROUTING-001-V1",
            "predecessor_routing_operation_id": f"ROUTING-OP-{predecessor:03d}",
            "successor_routing_operation_id": f"ROUTING-OP-{successor:03d}",
            "min_lag_seconds": 0,
            "max_lag_seconds": 3600,
            "transport_lag_seconds": transport,
            "source": _source(f"SRC-ROUTING-EDGE-{edge_number:03d}"),
        }
        for edge_number, predecessor, successor, transport in edge_specs
    ]
    option_specs = (
        (1, 1, 1, 420),
        (2, 1, 2, 390),
        (3, 2, 1, 300),
        (4, 3, 2, 330),
        (5, 4, 1, 240),
    )
    records["routing_resource_options"] = [
        {
            "routing_resource_option_id": f"ROUTING-OPTION-{option_number:03d}",
            "routing_operation_id": f"ROUTING-OP-{operation_number:03d}",
            "resource_id": f"RESOURCE-{resource_number:03d}",
            "quantity_unit": "piece",
            "setup_seconds": 60,
            "cycle_seconds_per_unit": 20,
            "final_duration_seconds": duration,
            "duration_source": "schema_sample_explicit_duration",
            "duration_source_version": "1.0.0",
            "source": _source(f"SRC-ROUTING-OPTION-{option_number:03d}"),
        }
        for option_number, operation_number, resource_number, duration in option_specs
    ]
    return document


def _snapshot_for(
    source: MutableImport,
    expansion: OrderExpansionResult,
) -> PlanningSnapshotDocumentV2:
    records = source["records"]
    counts = {
        collection: len(cast(list[object], records[collection]))
        for collection in COLLECTION_ID_FIELDS
    }
    counts["operation_instances"] = len(expansion.document["operation_instances"])
    counts["operation_precedence_edges"] = len(
        expansion.document["operation_precedence_edges"]
    )
    import_bytes = json.dumps(
        source,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    snapshot: dict[str, object] = {
        "snapshot_version": "planning-snapshot.v2",
        "schema_set_version": "2.0.0",
        "snapshot_id": "SNAPSHOT-P1-07-UNIT",
        "cutoff_at_utc": "2026-08-19T00:00:00Z",
        "source_versions": dict(source["source_versions"]),
        "rule_version": "data-quality-rules.v1",
        "normalization_rule_version": source["normalization_rule_version"],
        "expansion_version": ORDER_EXPANSION_VERSION,
        "canonicalization_version": "canonical-json.v1",
        "import_package": {
            "import_package_version": "import-package.v2",
            "package_id": source["package_id"],
            "dataset_hash": f"sha256:{sha256(import_bytes).hexdigest()}",
        },
        "import_quality_report": {
            "report_version": "import-quality-report.v1",
            "report_id": expansion.document["import_quality_report"]["report_id"],
            "status": "PASS",
        },
        "snapshot_hash": f"sha256:{'1' * 64}",
        "entity_counts": counts,
        "synthetic": source["synthetic"],
        "records": records,
        "operation_instances": expansion.document["operation_instances"],
        "operation_precedence_edges": expansion.document[
            "operation_precedence_edges"
        ],
        "synthetic_provenance": source["synthetic_provenance"],
    }
    return cast(PlanningSnapshotDocumentV2, snapshot)


def _expand(
    document: MutableImport,
    report: Mapping[str, object],
    *,
    expansion_version: str = ORDER_EXPANSION_VERSION,
    lot_mode: str = "EXPLICIT_LOTS",
) -> OrderExpansionResult:
    return expand_orders(
        cast(ImportPackageDocumentV2, document),
        report,
        expansion_version=expansion_version,
        lot_mode=lot_mode,
    )


def test_expands_serial_route_with_exact_lineage_fact_lock_and_candidates() -> None:
    document = _load_import()
    original = deepcopy(document)
    report = _pass_report(document)

    first = _expand(document, report)
    second = _expand(document, report)

    assert document == original
    assert first == second
    assert first.canonical_bytes == second.canonical_bytes
    assert first.expansion_hash == f"sha256:{sha256(first.canonical_bytes).hexdigest()}"
    assert first.document["expansion_version"] == ORDER_EXPANSION_VERSION
    assert first.document["import_package"]["package_id"] == document["package_id"]
    assert first.document["import_package"].get("synthetic_provenance") == document[
        "synthetic_provenance"
    ]

    instances = {
        instance["routing_operation_id"]: instance
        for instance in first.document["operation_instances"]
    }
    running = instances["ROUTING-OP-001"]
    waiting = instances["ROUTING-OP-002"]
    assert running["operation_instance_id"] == stable_expansion_id(
        "operation-instance", ORDER_EXPANSION_VERSION, "LOT-001", "ROUTING-OP-001"
    )
    assert running["status"] == "RUNNING"
    assert running.get("execution_fact_id") == "EXECUTION-FACT-001"
    assert running["lock_ids"] == ["LOCK-001"]
    assert running["quantity"] == 10
    assert running["due_at_utc"] == "2026-08-20T00:00:00Z"
    assert running["release_at_utc"] == "2026-08-18T00:00:00Z"
    assert running["material_ready_at_utc"] == "2026-08-18T00:00:00Z"
    assert running["resource_options"] == [
        {
            "routing_resource_option_id": "ROUTING-OPTION-001",
            "resource_id": "RESOURCE-001",
            "setup_seconds": 120,
            "cycle_seconds_per_unit": 30,
            "final_duration_seconds": 420,
            "duration_source": "schema_sample_explicit_duration",
            "source_version": "1.0.0",
        }
    ]
    assert waiting["status"] == "NOT_STARTED"
    assert "execution_fact_id" not in waiting
    assert len(first.document["operation_precedence_edges"]) == 1
    assert first.document["operation_precedence_edges"][0][
        "routing_precedence_edge_id"
    ] == "ROUTING-EDGE-001"
    validate_planning_snapshot_v2(_snapshot_for(document, first))


def test_parallel_merge_cross_workshop_and_candidate_order_are_stable() -> None:
    document = _branch_merge_import()
    report = _pass_report(document)
    expected = _expand(document, report)

    reordered = deepcopy(document)
    for collection in COLLECTION_ID_FIELDS:
        reordered["records"][collection].reverse()
    observed = _expand(reordered, _pass_report(reordered))

    assert observed.canonical_bytes == expected.canonical_bytes
    assert observed.expansion_hash == expected.expansion_hash
    assert len(expected.document["operation_instances"]) == 4
    assert len(expected.document["operation_precedence_edges"]) == 4
    start = next(
        instance
        for instance in expected.document["operation_instances"]
        if instance["routing_operation_id"] == "ROUTING-OP-001"
    )
    assert [
        option["routing_resource_option_id"] for option in start["resource_options"]
    ] == ["ROUTING-OPTION-001", "ROUTING-OPTION-002"]
    assert {option["resource_id"] for option in start["resource_options"]} == {
        "RESOURCE-001",
        "RESOURCE-002",
    }
    assert sorted(
        edge["transport_lag_seconds"]
        for edge in expected.document["operation_precedence_edges"]
    ) == [0, 0, 300, 300]
    validate_planning_snapshot_v2(_snapshot_for(document, expected))


def test_explicit_multiple_lots_and_completed_fact_are_retained_without_new_lots() -> None:
    document = _load_import()
    records = document["records"]
    records["production_lots"][0]["quantity"] = 6
    records["production_lots"].append(
        {
            "production_lot_id": "LOT-002",
            "production_order_id": "PRODUCTION-ORDER-001",
            "quantity": 4,
            "quantity_unit": "piece",
            "source": _source("SRC-LOT-002"),
        }
    )
    records["execution_facts"].append(
        {
            "execution_fact_id": "EXECUTION-FACT-002",
            "production_lot_id": "LOT-002",
            "routing_operation_id": "ROUTING-OP-001",
            "status": "COMPLETED",
            "observed_at_utc": "2026-08-19T00:00:00Z",
            "resource_id": "RESOURCE-001",
            "actual_start_at_utc": "2026-08-18T22:00:00Z",
            "actual_end_at_utc": "2026-08-18T23:00:00Z",
            "completed_quantity": 4,
            "quantity_unit": "piece",
            "source": _source("SRC-EXECUTION-FACT-002"),
        }
    )

    expansion = _expand(document, _pass_report(document))

    assert {instance["production_lot_id"] for instance in expansion.document["operation_instances"]} == {
        "LOT-001",
        "LOT-002",
    }
    assert len(expansion.document["operation_instances"]) == 4
    assert len(expansion.document["operation_precedence_edges"]) == 2
    completed = next(
        instance
        for instance in expansion.document["operation_instances"]
        if instance["production_lot_id"] == "LOT-002"
        and instance["routing_operation_id"] == "ROUTING-OP-001"
    )
    assert completed["status"] == "COMPLETED"
    assert completed.get("execution_fact_id") == "EXECUTION-FACT-002"
    assert completed["quantity"] == 4
    validate_planning_snapshot_v2(_snapshot_for(document, expansion))


def test_requires_a_matching_content_derived_pass_report() -> None:
    document = _load_import()
    report = dict(_pass_report(document))
    report["status"] = "FAIL"

    with pytest.raises(OrderExpansionError) as rejected:
        _expand(document, report)
    assert rejected.value.code is OrderExpansionErrorCode.QUALITY_REPORT_REQUIRED
    assert rejected.value.category == "DATA_ERROR"

    mismatched = dict(_pass_report(document))
    mismatched["package_id"] = "OTHER-PACKAGE"
    with pytest.raises(OrderExpansionError) as rejected_mismatch:
        _expand(document, mismatched)
    assert (
        rejected_mismatch.value.code
        is OrderExpansionErrorCode.QUALITY_REPORT_MISMATCH
    )

    false_count = dict(_pass_report(document))
    false_count["error_count"] = False
    with pytest.raises(OrderExpansionError) as rejected_count:
        _expand(document, false_count)
    assert rejected_count.value.code is OrderExpansionErrorCode.QUALITY_REPORT_REQUIRED

    extra_field = dict(_pass_report(document))
    extra_field["unexpected"] = "not-part-of-v1"
    with pytest.raises(OrderExpansionError) as rejected_field:
        _expand(document, extra_field)
    assert rejected_field.value.code is OrderExpansionErrorCode.QUALITY_REPORT_MISMATCH


def test_missing_explicit_lot_is_rejected_without_automatic_splitting() -> None:
    document = _load_import()
    report = _pass_report(document)
    document["records"]["production_lots"] = []
    document["records"]["execution_facts"] = []
    document["records"]["operation_locks"] = []

    with pytest.raises(OrderExpansionError) as rejected:
        _expand(document, report)

    assert rejected.value.code is OrderExpansionErrorCode.MISSING_PRODUCTION_LOT
    assert "cannot be inferred" in rejected.value.message


def test_missing_option_or_duration_is_rejected_without_fallback() -> None:
    no_option = _load_import()
    report = _pass_report(no_option)
    no_option["records"]["routing_resource_options"] = []
    with pytest.raises(OrderExpansionError) as missing_option:
        _expand(no_option, report)
    assert (
        missing_option.value.code is OrderExpansionErrorCode.MISSING_RESOURCE_OPTION
    )

    no_duration = _load_import()
    duration_report = _pass_report(no_duration)
    del no_duration["records"]["routing_resource_options"][0][
        "final_duration_seconds"
    ]
    with pytest.raises(OrderExpansionError) as missing_duration:
        _expand(no_duration, duration_report)
    assert missing_duration.value.code is OrderExpansionErrorCode.MISSING_DURATION


def test_route_fact_and_split_merge_rejections_are_explicit() -> None:
    route_mismatch = _load_import()
    route_report = _pass_report(route_mismatch)
    route_mismatch["records"]["routing_versions"].append(
        {
            "routing_version_id": "ROUTING-EMPTY-V1",
            "routing_code": "ROUTING-EMPTY",
            "version": "1.0.0",
            "product_id": "PRODUCT-001",
            "source": _source("SRC-ROUTING-EMPTY-V1"),
        }
    )
    route_mismatch["records"]["production_orders"][0][
        "routing_version_id"
    ] = "ROUTING-EMPTY-V1"
    route_mismatch["records"]["execution_facts"] = []
    route_mismatch["records"]["operation_locks"] = []
    with pytest.raises(OrderExpansionError) as missing_route:
        _expand(route_mismatch, route_report)
    assert missing_route.value.code is OrderExpansionErrorCode.ROUTING_VERSION_MISMATCH

    duplicate_fact = _load_import()
    fact_report = _pass_report(duplicate_fact)
    second_fact = deepcopy(duplicate_fact["records"]["execution_facts"][0])
    second_fact["execution_fact_id"] = "EXECUTION-FACT-002"
    second_fact["source"] = _source("SRC-EXECUTION-FACT-002")
    duplicate_fact["records"]["execution_facts"].append(second_fact)
    with pytest.raises(OrderExpansionError) as invalid_fact:
        _expand(duplicate_fact, fact_report)
    assert invalid_fact.value.code is OrderExpansionErrorCode.INVALID_EXECUTION_FACT

    valid = _load_import()
    valid_report = _pass_report(valid)
    with pytest.raises(OrderExpansionError) as unsupported:
        _expand(valid, valid_report, lot_mode=SPLIT_MERGE_CAPABILITY)
    assert unsupported.value.code is OrderExpansionErrorCode.UNSUPPORTED_SPLIT_MERGE
    assert unsupported.value.category == "UNSUPPORTED_CAPABILITY"

    with pytest.raises(OrderExpansionError) as wrong_version:
        _expand(valid, valid_report, expansion_version="order-expansion.v2")
    assert (
        wrong_version.value.code
        is OrderExpansionErrorCode.EXPANSION_VERSION_MISMATCH
    )
