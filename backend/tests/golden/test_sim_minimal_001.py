"""Independent P0 Golden evidence for SIM-MINIMAL-001.

TEST-GOLDEN-FJSP and TEST-SCENARIO-REPLAY cover the committed positive
fixture.  Positive slices of TEST-CALENDAR, TEST-MATERIAL,
TEST-CROSS-WORKSHOP, and TEST-MAX-LAG are computed directly here.  This file
is intentionally not a reusable ScheduleValidator; negative mutations remain
TASK-P0-07 work.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from app.domain.types import duration_to_ticks, format_utc_instant, parse_utc_instant
from app.simulation.generators.determinism import (
    canonical_json_bytes,
    dataset_sha256,
)
from app.simulation.scenarios.golden_fixture import (
    CONSTRAINT_IDS,
    load_golden_fixture,
    run_replay_checks,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "fixtures" / "deterministic" / "SIM-MINIMAL-001"
SCENARIO_SCHEMA_ROOT = ROOT / "schemas" / "scenario"
JSON_SCHEMA_ROOT = ROOT / "schemas" / "json"
RULE_SHEET_PATH = ROOT / "schemas" / "rules" / "constraint-rule-sheet.v1.yaml"
SIM_ASSUMPTION_PATH = ROOT / "docs" / "governance" / "sim-assumption-register.md"

type JsonObject = dict[str, Any]


def load_json(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(JsonObject, value)


def schema_validator(path: Path) -> Draft202012Validator:
    schema = load_json(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def records(package: JsonObject, collection: str) -> list[JsonObject]:
    record_collections = cast(dict[str, list[JsonObject]], package["records"])
    return record_collections[collection]


def assignment_map(schedule: JsonObject) -> dict[str, JsonObject]:
    assignments = cast(list[JsonObject], schedule["assignments"])
    return {str(value["operation_id"]): value for value in assignments}


def tick_for(value: str, horizon_start: datetime, tick_seconds: int) -> int:
    delta_seconds = int((parse_utc_instant(value) - horizon_start).total_seconds())
    assert delta_seconds % tick_seconds == 0
    return delta_seconds // tick_seconds


def test_versioned_artifacts_pass_schemas_and_replay_non_empty_import() -> None:
    bundle = load_golden_fixture(FIXTURE_ROOT)
    schema_validator(SCENARIO_SCHEMA_ROOT / "factory-profile.schema.json").validate(
        bundle.factory_profile
    )
    schema_validator(SCENARIO_SCHEMA_ROOT / "scenario-spec.schema.json").validate(
        bundle.scenario_spec
    )
    schema_validator(SCENARIO_SCHEMA_ROOT / "scenario-manifest.schema.json").validate(
        bundle.scenario_manifest
    )
    schema_validator(JSON_SCHEMA_ROOT / "import-package.schema.json").validate(
        bundle.import_package
    )

    report = run_replay_checks(FIXTURE_ROOT)
    assert report["result"] == "PASS"
    assert report["issues"] == []
    assert report["dataset_hash"] == (
        "sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10"
    )
    assert report["record_collection_count"] == 10
    assert report["record_count"] == 15
    assert report["assignment_count"] == 3

    canonical = canonical_json_bytes(bundle.import_package)
    round_trip = json.loads(canonical)
    assert round_trip == bundle.import_package
    assert dataset_sha256(canonical) == bundle.scenario_manifest["dataset_hash"]
    assert canonical_json_bytes(round_trip) == canonical


def test_fixture_dimensions_profile_ranges_and_assumptions_are_traceable() -> None:
    bundle = load_golden_fixture(FIXTURE_ROOT)
    package = bundle.import_package
    profile = bundle.factory_profile
    scenario = bundle.scenario_spec

    workshops = records(package, "workshops")
    production_lines = records(package, "production_lines")
    resource_documents = records(package, "resources")
    operations = records(package, "operation_instances")
    edges = records(package, "precedence_edges")
    unavailable = records(package, "resource_unavailable_intervals")

    assert len(workshops) == 2
    assert len(production_lines) == 2
    assert len(resource_documents) == 3
    assert len(operations) == 3
    assert len(records(package, "orders")) == 1
    assert len(unavailable) == 1
    assert all(resource["capacity"] == 1 for resource in resource_documents)
    assert max(len(cast(list[object], operation["resource_options"])) for operation in operations) == 2
    assert sum(bool(edge["cross_workshop"]) for edge in edges) == 1

    assert profile["topology"]["workshop_count"] == {"minimum": 2, "maximum": 2}
    assert profile["topology"]["production_line_count"] == {
        "minimum": 2,
        "maximum": 2,
    }
    assert profile["resources"]["target_count"] == {"minimum": 3, "maximum": 3}
    assert profile["routing"]["operation_count"] == {"minimum": 3, "maximum": 3}
    assert profile["routing"]["cross_workshop_ratio"] == {
        "minimum": 0.5,
        "maximum": 0.5,
    }
    assert scenario["complexity"]["cross_workshop_ratio"] == 0.5

    delayed = sum(
        parse_utc_instant(str(operation["material_ready_at_utc"]))
        > parse_utc_instant(str(operation["release_at_utc"]))
        for operation in operations
    )
    assert delayed / len(operations) == pytest.approx(
        scenario["complexity"]["material_delay_ratio"]
    )

    metadata = records(package, "fixture_metadata")[0]
    assumption_ids = cast(list[str], metadata["assumption_ids"])
    assert assumption_ids == [
        "SIM-ASSUMPTION-006",
        "SIM-ASSUMPTION-007",
        "SIM-ASSUMPTION-008",
        "SIM-ASSUMPTION-009",
    ]
    note = (FIXTURE_ROOT / "calculation-note.md").read_text(encoding="utf-8")
    for assumption_id in assumption_ids:
        assert assumption_id in note

    # The fixture note is the public provenance contract. Internal workspaces
    # retain an additional governance register, so cross-check it when present
    # without making a public checkout depend on non-published process records.
    if SIM_ASSUMPTION_PATH.is_file():
        register = SIM_ASSUMPTION_PATH.read_text(encoding="utf-8")
        for assumption_id in assumption_ids:
            assert assumption_id in register


def test_golden_schedule_independently_satisfies_c001_through_c011() -> None:
    bundle = load_golden_fixture(FIXTURE_ROOT)
    package = bundle.import_package
    schedule = bundle.golden_schedule
    operations = records(package, "operation_instances")
    edges = records(package, "precedence_edges")
    unavailable = records(package, "resource_unavailable_intervals")
    assignments = cast(list[JsonObject], schedule["assignments"])
    by_operation = assignment_map(schedule)
    tick_seconds = int(schedule["tick_seconds"])
    horizon_start = parse_utc_instant(str(schedule["horizon_start_utc"]))
    horizon_end = parse_utc_instant(str(schedule["horizon_end_utc"]))
    horizon_ticks = int((horizon_end - horizon_start).total_seconds()) // tick_seconds

    assignment_counts = Counter(str(item["operation_id"]) for item in assignments)
    unfinished_ids = {
        str(operation["operation_id"])
        for operation in operations
        if operation["status"] in {"NOT_STARTED", "RUNNING"}
    }
    c001 = set(assignment_counts) == unfinished_ids and all(
        assignment_counts[operation_id] == 1 for operation_id in unfinished_ids
    )

    observed_lags: dict[str, int] = {}
    for edge in edges:
        predecessor = by_operation[str(edge["predecessor_operation_id"])]
        successor = by_operation[str(edge["successor_operation_id"])]
        observed_lags[str(edge["edge_id"])] = (
            int(successor["start_tick"]) - int(predecessor["end_tick"])
        ) * tick_seconds
    c002 = bool(edges) and all(
        int(edge["min_lag_seconds"]) <= observed_lags[str(edge["edge_id"])]
        <= int(edge["max_lag_seconds"])
        for edge in edges
    )

    operation_by_id = {str(value["operation_id"]): value for value in operations}
    c003 = all(
        str(assignment["resource_id"])
        in {
            str(option["resource_id"])
            for option in cast(
                list[JsonObject],
                operation_by_id[str(assignment["operation_id"])]["resource_options"],
            )
        }
        for assignment in assignments
    )

    intervals_by_resource: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)
    for assignment in assignments:
        intervals_by_resource[str(assignment["resource_id"])].append(
            (int(assignment["start_tick"]), int(assignment["end_tick"]))
        )
    same_resource_pairs = [
        pair
        for intervals in intervals_by_resource.values()
        for pair in combinations(intervals, 2)
    ]
    c004 = bool(same_resource_pairs) and all(
        first[1] <= second[0] or second[1] <= first[0]
        for first, second in same_resource_pairs
    )

    unavailable_ticks = [
        (
            str(value["resource_id"]),
            tick_for(str(value["start_utc"]), horizon_start, tick_seconds),
            tick_for(str(value["end_utc"]), horizon_start, tick_seconds),
        )
        for value in unavailable
    ]
    c005 = bool(unavailable_ticks) and all(
        not (
            str(assignment["resource_id"]) == resource_id
            and int(assignment["start_tick"]) < unavailable_end
            and unavailable_start < int(assignment["end_tick"])
        )
        for assignment in assignments
        for resource_id, unavailable_start, unavailable_end in unavailable_ticks
    )

    c006 = all(
        horizon_start
        + timedelta(seconds=int(by_operation[str(operation["operation_id"])]["start_tick"]) * tick_seconds)
        >= parse_utc_instant(str(operation["release_at_utc"]))
        and horizon_start
        + timedelta(seconds=int(by_operation[str(operation["operation_id"])]["start_tick"]) * tick_seconds)
        >= parse_utc_instant(str(operation["material_ready_at_utc"]))
        for operation in operations
    )

    execution_facts = records(package, "execution_facts")
    c007: bool | None = None if not execution_facts else False
    assert all(operation["status"] == "NOT_STARTED" for operation in operations)
    lock_documents = records(package, "locks")
    c008: bool | None = None if not lock_documents else False

    cross_workshop_edges = [edge for edge in edges if edge["cross_workshop"] is True]
    c009 = bool(cross_workshop_edges) and all(
        observed_lags[str(edge["edge_id"])] >= int(edge["transport_lag_seconds"])
        for edge in cross_workshop_edges
    )

    c010 = all(
        int(assignment["end_tick"]) - int(assignment["start_tick"])
        == duration_to_ticks(
            int(
                next(
                    option["final_duration_seconds"]
                    for option in cast(
                        list[JsonObject],
                        operation_by_id[str(assignment["operation_id"])][
                            "resource_options"
                        ],
                    )
                    if option["resource_id"] == assignment["resource_id"]
                )
            ),
            tick_seconds,
        )
        for assignment in assignments
    )
    c011 = all(
        0 <= int(assignment["start_tick"]) < int(assignment["end_tick"]) <= horizon_ticks
        for assignment in assignments
    )

    independently_computed: dict[str, bool | None] = {
        "C-001": c001,
        "C-002": c002,
        "C-003": c003,
        "C-004": c004,
        "C-005": c005,
        "C-006": c006,
        "C-007": c007,
        "C-008": c008,
        "C-009": c009,
        "C-010": c010,
        "C-011": c011,
    }
    assert tuple(independently_computed) == CONSTRAINT_IDS
    assert all(value is True for value in independently_computed.values() if value is not None)
    assert {key for key, value in independently_computed.items() if value is None} == {
        "C-007",
        "C-008",
    }

    rule_sheet = cast(JsonObject, yaml.safe_load(RULE_SHEET_PATH.read_text(encoding="utf-8")))
    assert rule_sheet["rule_sheet_version"] == "constraint-rule-sheet.v1"
    assert tuple(
        str(rule["constraint_id"])
        for rule in cast(list[JsonObject], rule_sheet["active_rules"])
    ) == CONSTRAINT_IDS

    expected_checks = cast(list[JsonObject], bundle.expected_validation["checks"])
    expected_by_id = {str(value["constraint_id"]): value for value in expected_checks}
    for constraint_id, result in independently_computed.items():
        if result is None:
            assert expected_by_id[constraint_id]["applicability"] == "NOT_APPLICABLE"
            assert expected_by_id[constraint_id]["result"] == "NOT_APPLICABLE"
        else:
            assert expected_by_id[constraint_id]["applicability"] == "APPLICABLE"
            assert expected_by_id[constraint_id]["result"] == "PASS"
    assert bundle.expected_validation["status"] == "PASS"
    assert bundle.expected_validation["hard_violation_count"] == 0


def test_expected_kpis_and_fixture_objective_are_recomputed_from_facts() -> None:
    bundle = load_golden_fixture(FIXTURE_ROOT)
    package = bundle.import_package
    schedule = bundle.golden_schedule
    expected = bundle.expected_kpis
    assignments = cast(list[JsonObject], schedule["assignments"])
    tick_seconds = int(schedule["tick_seconds"])
    horizon_start = parse_utc_instant(str(schedule["horizon_start_utc"]))
    horizon_end = parse_utc_instant(str(schedule["horizon_end_utc"]))
    horizon_seconds = int((horizon_end - horizon_start).total_seconds())
    completion_tick = max(int(value["end_tick"]) for value in assignments)
    completion = horizon_start + timedelta(seconds=completion_tick * tick_seconds)
    order = records(package, "orders")[0]
    due = parse_utc_instant(str(order["due_at_utc"]))
    tardiness_seconds = max(0, int((completion - due).total_seconds()))

    expected_delivery = cast(JsonObject, expected["delivery"])
    assert expected_delivery == {
        "completion_at_utc": format_utc_instant(completion),
        "due_at_utc": format_utc_instant(due),
        "on_time_order_ratio": 1 if tardiness_seconds == 0 else 0,
        "total_tardiness_seconds": tardiness_seconds,
        "weighted_tardiness": tardiness_seconds * int(order["tardiness_weight"]),
        "late_order_count": 0 if tardiness_seconds == 0 else 1,
    }
    expected_planning = cast(JsonObject, expected["planning"])
    assert expected_planning == {
        "makespan_seconds": completion_tick * tick_seconds,
        "scheduled_operation_count": len(assignments),
        "unscheduled_operation_count": 0,
    }

    busy_by_resource: Counter[str] = Counter()
    for assignment in assignments:
        busy_by_resource[str(assignment["resource_id"])] += (
            int(assignment["end_tick"]) - int(assignment["start_tick"])
        ) * tick_seconds
    unavailable_by_resource: Counter[str] = Counter()
    for interval in records(package, "resource_unavailable_intervals"):
        unavailable_by_resource[str(interval["resource_id"])] += int(
            (
                parse_utc_instant(str(interval["end_utc"]))
                - parse_utc_instant(str(interval["start_utc"]))
            ).total_seconds()
        )
    expected_resources = {
        str(value["resource_id"]): value
        for value in cast(list[JsonObject], expected["resources"])
    }
    for resource in records(package, "resources"):
        resource_id = str(resource["resource_id"])
        available = horizon_seconds - unavailable_by_resource[resource_id]
        busy = busy_by_resource[resource_id]
        actual = expected_resources[resource_id]
        assert actual["available_seconds"] == available
        assert actual["planned_busy_seconds"] == busy
        assert actual["utilization"] == pytest.approx(busy / available)

    operations = {
        str(value["operation_id"]): value
        for value in records(package, "operation_instances")
    }
    edges = records(package, "precedence_edges")
    fastest_cut_ticks = sum(
        min(
            duration_to_ticks(int(option["final_duration_seconds"]), tick_seconds)
            for option in cast(list[JsonObject], operations[operation_id]["resource_options"])
        )
        for operation_id in ("OP-CUT-001", "OP-CUT-002")
    )
    cross_edge = next(edge for edge in edges if edge["cross_workshop"] is True)
    earliest_heat_start = fastest_cut_ticks + duration_to_ticks(
        int(cross_edge["transport_lag_seconds"]), tick_seconds
    )
    maintenance = records(package, "resource_unavailable_intervals")[0]
    maintenance_end = tick_for(
        str(maintenance["end_utc"]), horizon_start, tick_seconds
    )
    earliest_heat_start = max(earliest_heat_start, maintenance_end)
    heat_duration = duration_to_ticks(
        int(
            cast(list[JsonObject], operations["OP-HEAT-001"]["resource_options"])[0][
                "final_duration_seconds"
            ]
        ),
        tick_seconds,
    )
    assert earliest_heat_start + heat_duration == completion_tick == 12
    assert tardiness_seconds == 0


def test_replay_loader_remains_outside_solver_and_validator_evaluator() -> None:
    source = (
        ROOT / "backend" / "app" / "simulation" / "scenarios" / "golden_fixture.py"
    ).read_text(encoding="utf-8").lower()
    assert "from app.planning" not in source
    assert "import app.planning" not in source
    assert "ortools" not in source
    assert "cpmodel" not in source
    assert "intervalvar" not in source
    assert "validate_schedule" not in source
    assert "evaluate_constraint" not in source
