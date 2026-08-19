"""Generated and shrinkable invariants for TASK-P1-07 order expansion."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from hypothesis import given, seed, settings, strategies as st
import pytest

from app.data_validation import validate_import_package
from app.domain.canonical_records import COLLECTION_ID_FIELDS, ImportPackageDocumentV2
from app.domain.production import OrderExpansionError, OrderExpansionErrorCode
from app.normalization import expand_orders

ROOT = Path(__file__).resolve().parents[3]
HYPOTHESIS_REPLAY_SEED = 20260819
PROPERTY_EXAMPLES = 64

type MutableImport = dict[str, Any]


def _source(record_id: str) -> dict[str, str]:
    return {
        "source_system": "schema_sample",
        "source_version": "1.0.0",
        "source_record_id": record_id,
    }


def _base_import() -> MutableImport:
    return cast(
        MutableImport,
        json.loads(
            (
                ROOT
                / "schemas"
                / "samples"
                / "import-package.v2.synthetic.json"
            ).read_text(encoding="utf-8")
        ),
    )


def _generated_import(
    *,
    lot_quantities: list[int],
    candidate_counts: tuple[int, int, int, int],
    fact_states: tuple[str, str, str, str],
    lock_flags: tuple[bool, bool, bool, bool],
    scenario_seed: int,
) -> MutableImport:
    document = _base_import()
    document["package_id"] = f"IMPORT-P1-07-PROPERTY-{scenario_seed}"
    document["synthetic_provenance"]["seed"] = scenario_seed
    document["synthetic_provenance"]["scenario_id"] = "P1-07-PROPERTY"
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
            "min_lag_seconds": edge_number - 1,
            "max_lag_seconds": 3600 + edge_number,
            "transport_lag_seconds": transport,
            "source": _source(f"SRC-ROUTING-EDGE-{edge_number:03d}"),
        }
        for edge_number, predecessor, successor, transport in edge_specs
    ]

    options: list[dict[str, object]] = []
    option_number = 0
    for operation_number, candidate_count in enumerate(candidate_counts, 1):
        for candidate_number in range(candidate_count):
            option_number += 1
            resource_number = 1 + ((operation_number + candidate_number) % 2)
            options.append(
                {
                    "routing_resource_option_id": (
                        f"ROUTING-OPTION-{option_number:03d}"
                    ),
                    "routing_operation_id": f"ROUTING-OP-{operation_number:03d}",
                    "resource_id": f"RESOURCE-{resource_number:03d}",
                    "quantity_unit": "piece",
                    "setup_seconds": 30 * operation_number,
                    "cycle_seconds_per_unit": 5 + candidate_number,
                    "final_duration_seconds": (
                        120 + 20 * operation_number + 10 * candidate_number
                    ),
                    "duration_source": "p1_07_property_explicit",
                    "duration_source_version": "1.0.0",
                    "source": _source(f"SRC-ROUTING-OPTION-{option_number:03d}"),
                }
            )
    records["routing_resource_options"] = options

    total_quantity = sum(lot_quantities)
    records["demand_orders"][0]["quantity"] = total_quantity
    records["production_orders"][0]["quantity"] = total_quantity
    records["production_lots"] = [
        {
            "production_lot_id": f"LOT-{number:03d}",
            "production_order_id": "PRODUCTION-ORDER-001",
            "quantity": quantity,
            "quantity_unit": "piece",
            "source": _source(f"SRC-LOT-{number:03d}"),
        }
        for number, quantity in enumerate(lot_quantities, 1)
    ]

    first_lot_id = records["production_lots"][0]["production_lot_id"]
    execution_facts: list[dict[str, object]] = []
    operation_locks: list[dict[str, object]] = []
    for operation_number, state in enumerate(fact_states, 1):
        operation_id = f"ROUTING-OP-{operation_number:03d}"
        if state == "RUNNING":
            execution_facts.append(
                {
                    "execution_fact_id": f"EXECUTION-FACT-{operation_number:03d}",
                    "production_lot_id": first_lot_id,
                    "routing_operation_id": operation_id,
                    "status": "RUNNING",
                    "observed_at_utc": "2026-08-19T00:00:00Z",
                    "resource_id": f"RESOURCE-{1 + (operation_number % 2):03d}",
                    "actual_start_at_utc": "2026-08-18T23:55:00Z",
                    "remaining_quantity": lot_quantities[0],
                    "quantity_unit": "piece",
                    "remaining_seconds": 60 + operation_number,
                    "source": _source(
                        f"SRC-EXECUTION-FACT-{operation_number:03d}"
                    ),
                }
            )
        elif state == "COMPLETED":
            execution_facts.append(
                {
                    "execution_fact_id": f"EXECUTION-FACT-{operation_number:03d}",
                    "production_lot_id": first_lot_id,
                    "routing_operation_id": operation_id,
                    "status": "COMPLETED",
                    "observed_at_utc": "2026-08-19T00:00:00Z",
                    "resource_id": f"RESOURCE-{1 + (operation_number % 2):03d}",
                    "actual_start_at_utc": "2026-08-18T22:00:00Z",
                    "actual_end_at_utc": "2026-08-18T23:00:00Z",
                    "completed_quantity": lot_quantities[0],
                    "quantity_unit": "piece",
                    "source": _source(
                        f"SRC-EXECUTION-FACT-{operation_number:03d}"
                    ),
                }
            )
        if lock_flags[operation_number - 1]:
            operation_locks.append(
                {
                    "lock_id": f"LOCK-{operation_number:03d}",
                    "production_lot_id": first_lot_id,
                    "routing_operation_id": operation_id,
                    "lock_type": (
                        "HARD_LOCK" if operation_number % 2 else "SOFT_LOCK"
                    ),
                    "resource_id": f"RESOURCE-{1 + (operation_number % 2):03d}",
                    "start_at_utc": "2026-08-19T00:00:00Z",
                    "end_at_utc": "2026-08-19T00:05:00Z",
                    "source": _source(f"SRC-LOCK-{operation_number:03d}"),
                }
            )
    records["execution_facts"] = execution_facts
    records["operation_locks"] = operation_locks
    return document


def _pass_report(document: MutableImport) -> Mapping[str, object]:
    result = validate_import_package(cast(Mapping[str, object], document))
    assert result.passed, result.document
    return cast(Mapping[str, object], result.document)


def _expand(document: MutableImport, report: Mapping[str, object]):
    return expand_orders(cast(ImportPackageDocumentV2, document), report)


@seed(HYPOTHESIS_REPLAY_SEED)
@settings(max_examples=PROPERTY_EXAMPLES, deadline=None)
@given(
    lot_quantities=st.lists(
        st.integers(min_value=1, max_value=50), min_size=1, max_size=3
    ),
    candidate_counts=st.tuples(
        st.just(2),
        st.integers(min_value=1, max_value=2),
        st.integers(min_value=1, max_value=2),
        st.integers(min_value=1, max_value=2),
    ),
    fact_states=st.tuples(
        *(st.sampled_from(("NONE", "RUNNING", "COMPLETED")) for _ in range(4))
    ),
    lock_flags=st.tuples(*(st.booleans() for _ in range(4))),
    scenario_seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_generated_branch_merge_expansion_is_replay_stable_and_lossless(
    lot_quantities: list[int],
    candidate_counts: tuple[int, int, int, int],
    fact_states: tuple[str, str, str, str],
    lock_flags: tuple[bool, bool, bool, bool],
    scenario_seed: int,
) -> None:
    document = _generated_import(
        lot_quantities=lot_quantities,
        candidate_counts=candidate_counts,
        fact_states=fact_states,
        lock_flags=lock_flags,
        scenario_seed=scenario_seed,
    )
    original = deepcopy(document)
    report = _pass_report(document)

    first = _expand(document, report)
    replay = _expand(document, report)
    reordered = deepcopy(document)
    for collection in COLLECTION_ID_FIELDS:
        reordered["records"][collection].reverse()
    reordered_result = _expand(reordered, _pass_report(reordered))

    assert document == original
    assert first.canonical_bytes == replay.canonical_bytes
    assert first.canonical_bytes == reordered_result.canonical_bytes
    assert first.expansion_hash == replay.expansion_hash
    assert first.expansion_hash == reordered_result.expansion_hash
    assert first.expansion_hash == f"sha256:{sha256(first.canonical_bytes).hexdigest()}"
    assert first.document["import_package"]["synthetic"] is True
    assert first.document["import_package"].get("synthetic_provenance", {}).get(
        "seed"
    ) == scenario_seed

    instances = first.document["operation_instances"]
    edges = first.document["operation_precedence_edges"]
    assert len(instances) == len(lot_quantities) * 4
    assert len(edges) == len(lot_quantities) * 4
    assert len({item["operation_instance_id"] for item in instances}) == len(instances)
    assert len({item["operation_precedence_edge_id"] for item in edges}) == len(edges)
    assert all(item["resource_options"] for item in instances)
    assert all(
        option["final_duration_seconds"] > 0
        and option["duration_source"] == "p1_07_property_explicit"
        and option["source_version"] == "1.0.0"
        for item in instances
        for option in item["resource_options"]
    )

    instance_by_id = {
        item["operation_instance_id"]: item for item in first.document["operation_instances"]
    }
    assert all(
        instance_by_id[edge["predecessor_operation_instance_id"]][
            "production_lot_id"
        ]
        == instance_by_id[edge["successor_operation_instance_id"]][
            "production_lot_id"
        ]
        for edge in edges
    )
    assert sorted(edge["transport_lag_seconds"] for edge in edges) == sorted(
        [0, 0, 300, 300] * len(lot_quantities)
    )
    for lot_number in range(1, len(lot_quantities) + 1):
        lot_id = f"LOT-{lot_number:03d}"
        for operation_number, candidate_count in enumerate(candidate_counts, 1):
            instance = next(
                item
                for item in instances
                if item["production_lot_id"] == lot_id
                and item["routing_operation_id"]
                == f"ROUTING-OP-{operation_number:03d}"
            )
            assert len(instance["resource_options"]) == candidate_count


@seed(HYPOTHESIS_REPLAY_SEED + 1)
@settings(max_examples=24, deadline=None)
@given(
    target_operation=st.integers(min_value=1, max_value=4),
    lot_quantities=st.lists(
        st.integers(min_value=1, max_value=20), min_size=1, max_size=3
    ),
)
def test_generated_missing_candidate_shrinks_to_exact_rejection(
    target_operation: int,
    lot_quantities: list[int],
) -> None:
    document = _generated_import(
        lot_quantities=lot_quantities,
        candidate_counts=(2, 1, 1, 1),
        fact_states=("NONE", "NONE", "NONE", "NONE"),
        lock_flags=(False, False, False, False),
        scenario_seed=target_operation,
    )
    report = _pass_report(document)
    operation_id = f"ROUTING-OP-{target_operation:03d}"
    document["records"]["routing_resource_options"] = [
        option
        for option in document["records"]["routing_resource_options"]
        if option["routing_operation_id"] != operation_id
    ]

    with pytest.raises(OrderExpansionError) as rejected:
        _expand(document, report)

    assert rejected.value.code is OrderExpansionErrorCode.MISSING_RESOURCE_OPTION
    assert rejected.value.entity_id == operation_id
