"""Replay TASK-P2-09 correctness assets through the formal P1/P2 boundaries.

The fixture-local assembler expands small, reviewable blueprints into source
records.  Every case then enters Raw Staging and the public normalization,
quality, expansion, Snapshot, Problem, Strategy, and Validator boundaries.  It
never constructs a PlanningProblem or a CP-SAT model directly.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, cast

import yaml

from app.data_validation import (
    DATA_QUALITY_RULE_VERSION,
    validate_import_package,
)
from app.domain.production import ORDER_EXPANSION_VERSION
from app.domain.types import format_utc_instant, parse_utc_instant
from app.importers import (
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)
from app.normalization import (
    COLLECTION_ID_FIELDS,
    NORMALIZATION_CONTRACT_VERSION,
    NormalizationInput,
    UnitConversionRegistry,
    expand_orders,
    normalize_import,
)
from app.planning.backends.cp_sat import BACKEND_VERSION, ORTOOLS_VERSION
from app.planning.policy import (
    SIMULATION_DELIVERY_POLICY_ID,
    SIMULATION_DELIVERY_POLICY_REVISION,
    SIMULATION_DELIVERY_SOURCE_SYSTEM,
    SIMULATION_DELIVERY_SOURCE_VERSION,
    simulation_delivery_policy,
    simulation_solve_limits,
)
from app.planning.problem import (
    PLANNING_PROBLEM_VERSION_V2,
    PROBLEM_BUILDER_VERSION_V2,
    PlanningProblemDocumentV2,
    build_planning_problem_v2,
)
from app.planning.problem.hashing import problem_v2_hash_for
from app.planning.strategies import GlobalCpSatStrategy
from app.planning.validation import validate_problem_schedule
from app.simulation.generators import p1_mapping_profile
from app.simulation.generators.contracts import GenerationContext
from app.simulation.profiles.contracts import (
    FactoryProfileDocument,
    validate_factory_profile_contract,
)
from app.simulation.scenarios.contracts import (
    ScenarioSpecDocument,
    validate_scenario_spec_contract,
)
from app.snapshots import SNAPSHOT_VERSION, build_planning_snapshot


REPORT_VERSION = "p2-correctness-report.v1"
CATALOG_VERSION = "p2-correctness-catalog.v1"
BLUEPRINT_VERSION = "p2-correctness-blueprint.v1"
BLUEPRINT_SET_VERSION = "p2-correctness-blueprint-set.v1"
MANIFEST_VERSION = "p2-correctness-manifest.v1"
EXPECTED_VERSION = "p2-correctness-expected.v1"
ASSEMBLER_ID = "PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER"
ASSEMBLER_VERSION = "1.0.0"
TASK_ID = "TASK-P2-09"
CONSTRAINT_IDS = tuple(f"C-{index:03d}" for index in range(1, 12))
SCENARIO_IDS = (
    "P2-GOLDEN-JSSP",
    "P2-GOLDEN-FJSP",
    "P2-CROSS-WORKSHOP",
    "P2-CALENDAR",
    "P2-MATERIAL-DELAY",
    "P2-RUNNING",
    "P2-HARD-LOCK",
)

type JsonObject = dict[str, Any]

_PIPELINE_VERSIONS = {
    "mapping_profile": "P1-SYNTHETIC-SOURCE-MAPPING@1.0.0",
    "unit_registry": "unit-conversion-registry.v1",
    "normalization": NORMALIZATION_CONTRACT_VERSION,
    "import_package": "import-package.v2",
    "data_quality_rules": DATA_QUALITY_RULE_VERSION,
    "expansion": ORDER_EXPANSION_VERSION,
    "snapshot": SNAPSHOT_VERSION,
    "problem": PLANNING_PROBLEM_VERSION_V2,
    "problem_builder": PROBLEM_BUILDER_VERSION_V2,
}
_POLICY_IDENTITY = {
    "policy_id": SIMULATION_DELIVERY_POLICY_ID,
    "policy_revision": SIMULATION_DELIVERY_POLICY_REVISION,
    "source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
    "source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
}
_SOLVER_IDENTITY = {
    "backend_version": BACKEND_VERSION,
    "solver_version": ORTOOLS_VERSION,
}
_FROZEN_FILES = {
    "schemas/scenario/factory-profile.schema.json": (
        "79c0ee97e73cefa99908655e415480d82cbd606e0cdb9954c7b544398ab45f10"
    ),
    "schemas/scenario/scenario-spec.schema.json": (
        "391d5b02a4b7f536d9b7b33e1c4d42c522e53182df593c953b11a54db7baff50"
    ),
    "schemas/scenario/scenario-manifest.schema.json": (
        "67ba4835bf8cc8583d56c8086c51c947e54c5e8bec2312468bb210bf0d9507ef"
    ),
    "schemas/json/planning-problem.v2.schema.json": (
        "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8"
    ),
    "schemas/json/planning-solution.schema.json": (
        "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4"
    ),
    "schemas/rules/constraint-rule-sheet.v1.yaml": (
        "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2"
    ),
    "backend/app/planning/problem/builder.py": (
        "c96a55a8d59da785a0109d83a75fbd2df2e2bfcccf234c07581019033af0f291"
    ),
    "backend/app/planning/problem/hashing.py": (
        "ec2b98ed59ed8b5a4d4588254e2a49d9b9c7df1c2b666f78f00104c39cc76b4e"
    ),
    "backend/app/planning/strategies/global_cp_sat.py": (
        "c3c5f057b7f87fb732fb75bf10bed61a533915f3b0a25724af8b24c1ddc84133"
    ),
    "backend/app/planning/validation/problem_schedule_validator.py": (
        "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f"
    ),
    "backend/app/planning/policy/delivery.py": (
        "437e4876e1876d7fb80e81e537e2c531080d6f34ceb0b1ed0e3f0f5844a9b558"
    ),
    "backend/app/simulation/generators/package_generator.py": (
        "44c9cf4bce6e836c2c9c1a47d3cd086171a91dddbec1bf69a456cc0581a7c370"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}
_HISTORICAL_ASSET_ROOTS = (
    "fixtures/deterministic/SIM-MINIMAL-001",
    "fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS",
    "fixtures/synthetic/SIM-P1-INGRESS-001",
)
_HISTORICAL_ASSET_MANIFEST_DIGEST = (
    "cab42c498ad74607d8e7bb172b6daf3f320626eb0e08b2d155e1b31cb8b45df4"
)


@dataclass(frozen=True, slots=True)
class CorrectnessCase:
    """One immutable Profile/Scenario/blueprint/manifest/expected bundle."""

    profile: JsonObject
    scenario: JsonObject
    blueprint: JsonObject
    manifest: JsonObject
    expected: JsonObject
    asset_paths: tuple[Path, ...]

    @property
    def scenario_id(self) -> str:
        return cast(str, self.scenario["scenario_id"])


@dataclass(frozen=True, slots=True)
class CorrectnessReplay:
    """Artifacts emitted by one complete formal correctness replay."""

    case: CorrectnessCase
    import_document: JsonObject
    import_dataset_hash: str
    quality_report: JsonObject
    expansion_document: JsonObject
    snapshot_document: JsonObject
    snapshot_hash: str
    problem: JsonObject
    solution: JsonObject
    solver_report: JsonObject
    validation_report: JsonObject
    operation_ids: Mapping[str, str]
    operation_labels: Mapping[str, str]
    resource_ids: Mapping[str, str]
    resource_codes: Mapping[str, str]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _object_digest(value: object) -> str:
    return _digest(_canonical_bytes(value))


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"correctness asset must be a JSON object: {path}")
    return cast(JsonObject, value)


def _standalone_case(path: Path) -> CorrectnessCase:
    asset_paths = tuple(
        path / name
        for name in (
            "factory-profile.json",
            "scenario-spec.json",
            "scenario-blueprint.json",
            "correctness-manifest.json",
            "expected-outcome.json",
            "calculation-note.md",
        )
    )
    return CorrectnessCase(
        profile=_load_json(asset_paths[0]),
        scenario=_load_json(asset_paths[1]),
        blueprint=_load_json(asset_paths[2]),
        manifest=_load_json(asset_paths[3]),
        expected=_load_json(asset_paths[4]),
        asset_paths=asset_paths,
    )


def load_correctness_cases(root: Path) -> tuple[CorrectnessCase, ...]:
    """Load the two standalone Goldens and five catalog matrix cases."""

    deterministic = root / "fixtures" / "deterministic"
    cases = [
        _standalone_case(deterministic / "P2-GOLDEN-JSSP"),
        _standalone_case(deterministic / "P2-GOLDEN-FJSP"),
    ]
    matrix_root = root / "fixtures" / "synthetic" / "P2-CORRECTNESS-MATRIX"
    profile_path = matrix_root / "factory-profile.json"
    catalog_path = matrix_root / "scenario-catalog.json"
    blueprints_path = matrix_root / "scenario-blueprints.json"
    note_path = matrix_root / "calculation-note.md"
    profile = _load_json(profile_path)
    catalog = _load_json(catalog_path)
    blueprint_set = _load_json(blueprints_path)
    if catalog.get("catalog_version") != CATALOG_VERSION:
        raise ValueError("P2 correctness catalog version mismatch")
    if blueprint_set.get("blueprint_set_version") != BLUEPRINT_SET_VERSION:
        raise ValueError("P2 correctness blueprint-set version mismatch")
    profile_ref = {
        "profile_id": profile.get("profile_id"),
        "profile_version": profile.get("profile_version"),
    }
    assembler_ref = {
        "generator_id": ASSEMBLER_ID,
        "generator_version": ASSEMBLER_VERSION,
    }
    if (
        catalog.get("factory_profile") != profile_ref
        or catalog.get("assembler") != assembler_ref
        or catalog.get("pipeline") != _PIPELINE_VERSIONS
        or catalog.get("policy") != _POLICY_IDENTITY
        or catalog.get("solver") != _SOLVER_IDENTITY
    ):
        raise ValueError("P2 correctness catalog provenance mismatch")
    blueprints = {
        cast(str, blueprint["scenario_id"]): cast(JsonObject, blueprint)
        for blueprint in cast(list[JsonObject], blueprint_set.get("scenarios"))
    }
    for entry in cast(list[JsonObject], catalog.get("scenarios")):
        scenario = cast(JsonObject, entry["scenario_spec"])
        scenario_id = cast(str, scenario["scenario_id"])
        cases.append(
            CorrectnessCase(
                profile=profile,
                scenario=scenario,
                blueprint=blueprints[scenario_id],
                manifest={
                    **cast(JsonObject, entry["correctness_manifest"]),
                    "factory_profile": profile_ref,
                    "assembler": assembler_ref,
                    "pipeline": _PIPELINE_VERSIONS,
                    "policy": _POLICY_IDENTITY,
                    "solver": _SOLVER_IDENTITY,
                },
                expected=cast(JsonObject, entry["expected_outcome"]),
                asset_paths=(profile_path, catalog_path, blueprints_path, note_path),
            )
        )
    by_id = {case.scenario_id: case for case in cases}
    if set(by_id) != set(SCENARIO_IDS) or len(cases) != len(SCENARIO_IDS):
        raise ValueError("P2 correctness catalog must contain exactly seven cases")
    return tuple(by_id[scenario_id] for scenario_id in SCENARIO_IDS)


def _require_int(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or cast(int, value) < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return cast(int, value)


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise ValueError(f"{field} must be non-empty whitespace-free text")
    return value


def _validate_blueprint(blueprint: JsonObject) -> None:
    required = {
        "blueprint_version",
        "scenario_id",
        "cutoff_at_utc",
        "tick_seconds",
        "horizon_ticks",
        "resources",
        "jobs",
    }
    if set(blueprint) != required or blueprint["blueprint_version"] != BLUEPRINT_VERSION:
        raise ValueError("correctness blueprint fields/version mismatch")
    parse_utc_instant(cast(str, blueprint["cutoff_at_utc"]))
    _require_int(blueprint["tick_seconds"], "tick_seconds", minimum=1)
    _require_int(blueprint["horizon_ticks"], "horizon_ticks", minimum=1)
    resources = cast(list[JsonObject], blueprint["resources"])
    jobs = cast(list[JsonObject], blueprint["jobs"])
    if not resources or not jobs:
        raise ValueError("correctness blueprint requires resources and jobs")
    resource_codes: set[str] = set()
    for resource in resources:
        code = _require_text(resource.get("resource_code"), "resource_code")
        _require_text(resource.get("workshop_code"), "workshop_code")
        if code in resource_codes:
            raise ValueError("resource_code must be unique")
        resource_codes.add(code)
        for interval in cast(list[JsonObject], resource.get("unavailable")):
            start = _require_int(interval.get("start_tick"), "start_tick")
            end = _require_int(interval.get("end_tick"), "end_tick", minimum=1)
            if start >= end:
                raise ValueError("calendar interval must be positive")
    job_codes: set[str] = set()
    for job in jobs:
        job_code = _require_text(job.get("job_code"), "job_code")
        if job_code in job_codes:
            raise ValueError("job_code must be unique")
        job_codes.add(job_code)
        _require_int(job.get("priority_weight"), "priority_weight", minimum=1)
        _require_int(job.get("due_tick"), "due_tick")
        _require_int(job.get("release_tick"), "release_tick")
        _require_int(job.get("material_ready_tick"), "material_ready_tick")
        operations = cast(list[JsonObject], job.get("operations"))
        operation_codes: set[str] = set()
        for operation in operations:
            operation_code = _require_text(
                operation.get("operation_code"), "operation_code"
            )
            if operation_code in operation_codes:
                raise ValueError("operation_code must be unique within a job")
            operation_codes.add(operation_code)
            candidates = cast(list[JsonObject], operation.get("candidates"))
            if not candidates:
                raise ValueError("every operation requires at least one candidate")
            for candidate in candidates:
                if candidate.get("resource_code") not in resource_codes:
                    raise ValueError("candidate references an unknown resource")
                _require_int(candidate.get("duration_ticks"), "duration_ticks", minimum=1)
        for edge in cast(list[JsonObject], job.get("edges")):
            if edge.get("predecessor") not in operation_codes or edge.get(
                "successor"
            ) not in operation_codes:
                raise ValueError("edge references an unknown operation")
            _require_int(edge.get("min_lag_ticks"), "min_lag_ticks")
            _require_int(edge.get("transport_lag_ticks"), "transport_lag_ticks")
        for fact in cast(list[JsonObject], job.get("execution_facts")):
            if fact.get("operation_code") not in operation_codes:
                raise ValueError("execution fact references an unknown operation")
            if fact.get("status") != "RUNNING":
                raise ValueError("P2 correctness blueprint only supports RUNNING facts")
            if fact.get("resource_code") not in resource_codes:
                raise ValueError("execution fact references an unknown resource")
            _require_int(fact.get("remaining_ticks"), "remaining_ticks", minimum=1)
        for lock in cast(list[JsonObject], job.get("locks")):
            if lock.get("operation_code") not in operation_codes:
                raise ValueError("lock references an unknown operation")
            if lock.get("lock_type") not in {"HARD_LOCK", "SOFT_LOCK"}:
                raise ValueError("lock_type is unsupported")
            if lock.get("resource_code") not in resource_codes:
                raise ValueError("lock references an unknown resource")
            start = _require_int(lock.get("start_tick"), "lock.start_tick")
            end = _require_int(lock.get("end_tick"), "lock.end_tick", minimum=1)
            if start >= end:
                raise ValueError("lock interval must be positive")


def validate_correctness_case(
    case: CorrectnessCase, *, verify_manifest_hashes: bool = True
) -> None:
    """Validate fixture-local versions, references, semantics, and hashes."""

    validate_factory_profile_contract(cast(FactoryProfileDocument, case.profile))
    validate_scenario_spec_contract(cast(ScenarioSpecDocument, case.scenario))
    _validate_blueprint(case.blueprint)
    scenario_id = case.scenario_id
    if case.blueprint["scenario_id"] != scenario_id:
        raise ValueError("blueprint scenario reference mismatch")
    if case.scenario["generator"] != {
        "generator_id": ASSEMBLER_ID,
        "generator_version": ASSEMBLER_VERSION,
    }:
        raise ValueError("ScenarioSpec does not select the P2 correctness assembler")
    profile_ref = {
        "profile_id": case.profile["profile_id"],
        "profile_version": case.profile["profile_version"],
    }
    if case.scenario["factory_profile"] != profile_ref:
        raise ValueError("ScenarioSpec/Profile reference mismatch")
    manifest = case.manifest
    if manifest.get("correctness_manifest_version") != MANIFEST_VERSION:
        raise ValueError("correctness manifest version mismatch")
    manifest_scenario = cast(JsonObject, manifest.get("scenario"))
    if manifest_scenario != {
        "scenario_id": scenario_id,
        "scenario_version": case.scenario["scenario_version"],
    }:
        raise ValueError("correctness manifest Scenario reference mismatch")
    if manifest.get("seed") != case.scenario["seed"]:
        raise ValueError("correctness manifest seed mismatch")
    if (
        manifest.get("factory_profile") != profile_ref
        or manifest.get("assembler")
        != {
            "generator_id": ASSEMBLER_ID,
            "generator_version": ASSEMBLER_VERSION,
        }
        or manifest.get("pipeline") != _PIPELINE_VERSIONS
        or manifest.get("policy") != _POLICY_IDENTITY
        or manifest.get("solver") != _SOLVER_IDENTITY
    ):
        raise ValueError("correctness manifest provenance mismatch")
    expected = case.expected
    if (
        expected.get("expected_outcome_version") != EXPECTED_VERSION
        or expected.get("scenario_id") != scenario_id
    ):
        raise ValueError("correctness expected outcome version/reference mismatch")
    expected_behavior = cast(JsonObject, case.scenario["expected_behavior"])
    if (
        expected.get("solver_status")
        not in cast(list[str], expected_behavior["allowed_results"])
        or expected.get("validator_status")
        != expected_behavior["validator_status"]
    ):
        raise ValueError("correctness expected outcome violates ScenarioSpec")
    positive_constraint_ids = cast(list[str], expected.get("positive_constraint_ids"))
    if (
        not positive_constraint_ids
        or len(positive_constraint_ids) != len(set(positive_constraint_ids))
        or not set(positive_constraint_ids).issubset(CONSTRAINT_IDS)
    ):
        raise ValueError("correctness positive constraint coverage is invalid")
    if verify_manifest_hashes:
        observed_hashes = {
            "factory_profile": _object_digest(case.profile),
            "scenario_spec": _object_digest(case.scenario),
            "scenario_blueprint": _object_digest(case.blueprint),
            "expected_outcome": _object_digest(case.expected),
        }
        if manifest.get("asset_hashes") != observed_hashes:
            raise ValueError(f"correctness asset hash drift: {scenario_id}")


def _instant(blueprint: JsonObject, tick: int) -> str:
    cutoff = parse_utc_instant(cast(str, blueprint["cutoff_at_utc"]))
    seconds = cast(int, blueprint["tick_seconds"]) * tick
    return format_utc_instant(cutoff + timedelta(seconds=seconds))


def _slug(value: str) -> str:
    return value.lower().replace("_", "-")


def _source_records(blueprint: JsonObject) -> JsonObject:
    """Expand a blueprint into source-shaped records without canonical IDs."""

    tick_seconds = cast(int, blueprint["tick_seconds"])
    resources = sorted(
        cast(list[JsonObject], blueprint["resources"]),
        key=lambda item: cast(str, item["resource_code"]),
    )
    jobs = sorted(
        cast(list[JsonObject], blueprint["jobs"]),
        key=lambda item: cast(str, item["job_code"]),
    )
    workshops = sorted({cast(str, resource["workshop_code"]) for resource in resources})
    records: JsonObject = {collection: [] for collection in COLLECTION_ID_FIELDS}
    cast(list[JsonObject], records["factories"]).append(
        {
            "factory_id": "p2-factory-001",
            "factory_code": "P2-F001",
            "factory_timezone": "UTC",
        }
    )
    for workshop_code in workshops:
        suffix = _slug(workshop_code)
        cast(list[JsonObject], records["workshops"]).append(
            {
                "workshop_id": f"p2-workshop-{suffix}",
                "workshop_code": workshop_code,
                "factory_id": "p2-factory-001",
            }
        )
        cast(list[JsonObject], records["production_lines"]).append(
            {
                "production_line_id": f"p2-line-{suffix}",
                "production_line_code": f"LINE-{workshop_code}",
                "workshop_id": f"p2-workshop-{suffix}",
            }
        )
        cast(list[JsonObject], records["resource_groups"]).append(
            {
                "resource_group_id": f"p2-group-{suffix}",
                "resource_group_code": f"GROUP-{workshop_code}",
                "production_line_id": f"p2-line-{suffix}",
            }
        )
    for resource in resources:
        resource_code = cast(str, resource["resource_code"])
        workshop_code = cast(str, resource["workshop_code"])
        resource_suffix = _slug(resource_code)
        workshop_suffix = _slug(workshop_code)
        calendar_id = f"p2-calendar-{resource_suffix}"
        cast(list[JsonObject], records["resources"]).append(
            {
                "resource_id": f"p2-resource-{resource_suffix}",
                "resource_code": resource_code,
                "resource_type": "MACHINE",
                "status": "AVAILABLE",
                "resource_group_id": f"p2-group-{workshop_suffix}",
                "calendar_id": calendar_id,
                "capabilities": ["P2_PROCESS"],
            }
        )
        intervals = [
            {
                "interval_id": f"p2-calendar-{resource_suffix}-{_slug(cast(str, interval['interval_code']))}",
                "start_at": _instant(blueprint, cast(int, interval["start_tick"])),
                "end_at": _instant(blueprint, cast(int, interval["end_tick"])),
                "reason": cast(str, interval["reason"]),
            }
            for interval in cast(list[JsonObject], resource["unavailable"])
        ]
        cast(list[JsonObject], records["calendars"]).append(
            {
                "calendar_id": calendar_id,
                "timezone": "UTC",
                "unavailable_intervals": intervals,
            }
        )
    for job in jobs:
        job_code = cast(str, job["job_code"])
        job_suffix = _slug(job_code)
        product_id = f"p2-product-{job_suffix}"
        routing_id = f"p2-routing-{job_suffix}"
        demand_id = f"p2-demand-{job_suffix}"
        order_id = f"p2-order-{job_suffix}"
        lot_id = f"p2-lot-{job_suffix}"
        cast(list[JsonObject], records["products"]).append(
            {
                "product_id": product_id,
                "product_code": f"PRODUCT-{job_code}",
                "quantity_unit": "piece",
            }
        )
        cast(list[JsonObject], records["routing_versions"]).append(
            {
                "routing_version_id": routing_id,
                "routing_code": f"ROUTING-{job_code}",
                "version": "1.0.0",
                "product_id": product_id,
            }
        )
        operations = sorted(
            cast(list[JsonObject], job["operations"]),
            key=lambda item: cast(str, item["operation_code"]),
        )
        for operation in operations:
            operation_code = cast(str, operation["operation_code"])
            operation_suffix = _slug(operation_code)
            routing_operation_id = f"p2-routing-operation-{job_suffix}-{operation_suffix}"
            cast(list[JsonObject], records["routing_operations"]).append(
                {
                    "routing_operation_id": routing_operation_id,
                    "routing_version_id": routing_id,
                    "operation_code": f"{job_code}/{operation_code}",
                    "required_capabilities": ["P2_PROCESS"],
                }
            )
            candidates = sorted(
                cast(list[JsonObject], operation["candidates"]),
                key=lambda item: cast(str, item["resource_code"]),
            )
            for candidate in candidates:
                resource_code = cast(str, candidate["resource_code"])
                duration_seconds = cast(int, candidate["duration_ticks"]) * tick_seconds
                cast(list[JsonObject], records["routing_resource_options"]).append(
                    {
                        "routing_resource_option_id": (
                            f"p2-option-{job_suffix}-{operation_suffix}-{_slug(resource_code)}"
                        ),
                        "routing_operation_id": routing_operation_id,
                        "resource_id": f"p2-resource-{_slug(resource_code)}",
                        "quantity_unit": "piece",
                        "setup_seconds": 0,
                        "setup_unit": "s",
                        "cycle_seconds_per_unit": duration_seconds,
                        "cycle_unit": "s",
                        "final_duration_seconds": duration_seconds,
                        "final_duration_unit": "s",
                        "duration_source": "p2-correctness-blueprint",
                        "duration_source_version": ASSEMBLER_VERSION,
                    }
                )
        for position, edge in enumerate(cast(list[JsonObject], job["edges"]), start=1):
            predecessor = _slug(cast(str, edge["predecessor"]))
            successor = _slug(cast(str, edge["successor"]))
            record: JsonObject = {
                "routing_precedence_edge_id": f"p2-edge-{job_suffix}-{position:03d}",
                "routing_version_id": routing_id,
                "predecessor_routing_operation_id": f"p2-routing-operation-{job_suffix}-{predecessor}",
                "successor_routing_operation_id": f"p2-routing-operation-{job_suffix}-{successor}",
                "min_lag_seconds": cast(int, edge["min_lag_ticks"]) * tick_seconds,
                "min_lag_unit": "s",
                "transport_lag_seconds": cast(int, edge["transport_lag_ticks"])
                * tick_seconds,
                "transport_lag_unit": "s",
            }
            if "max_lag_ticks" in edge:
                record["max_lag_seconds"] = cast(int, edge["max_lag_ticks"]) * tick_seconds
                record["max_lag_unit"] = "s"
            cast(list[JsonObject], records["routing_precedence_edges"]).append(record)
        cast(list[JsonObject], records["demand_orders"]).append(
            {
                "demand_order_id": demand_id,
                "product_id": product_id,
                "quantity": 1,
                "quantity_unit": "piece",
                "due_at_utc": _instant(blueprint, cast(int, job["due_tick"])),
            }
        )
        cast(list[JsonObject], records["production_orders"]).append(
            {
                "production_order_id": order_id,
                "demand_order_id": demand_id,
                "routing_version_id": routing_id,
                "quantity": 1,
                "quantity_unit": "piece",
                "release_at_utc": _instant(blueprint, cast(int, job["release_tick"])),
                "material_ready_at_utc": _instant(
                    blueprint, cast(int, job["material_ready_tick"])
                ),
            }
        )
        cast(list[JsonObject], records["production_lots"]).append(
            {
                "production_lot_id": lot_id,
                "production_order_id": order_id,
                "quantity": 1,
                "quantity_unit": "piece",
            }
        )
        for position, fact in enumerate(
            cast(list[JsonObject], job["execution_facts"]), start=1
        ):
            operation_suffix = _slug(cast(str, fact["operation_code"]))
            cast(list[JsonObject], records["execution_facts"]).append(
                {
                    "execution_fact_id": f"p2-fact-{job_suffix}-{position:03d}",
                    "production_lot_id": lot_id,
                    "routing_operation_id": f"p2-routing-operation-{job_suffix}-{operation_suffix}",
                    "status": "RUNNING",
                    "observed_at_utc": cast(str, blueprint["cutoff_at_utc"]),
                    "resource_id": f"p2-resource-{_slug(cast(str, fact['resource_code']))}",
                    "actual_start_at_utc": _instant(
                        blueprint, cast(int, fact["actual_start_tick"])
                    ),
                    "remaining_quantity": 1,
                    "quantity_unit": "piece",
                    "remaining_seconds": cast(int, fact["remaining_ticks"])
                    * tick_seconds,
                    "remaining_unit": "s",
                }
            )
        for position, lock in enumerate(cast(list[JsonObject], job["locks"]), start=1):
            operation_suffix = _slug(cast(str, lock["operation_code"]))
            cast(list[JsonObject], records["operation_locks"]).append(
                {
                    "lock_id": f"p2-lock-{job_suffix}-{position:03d}",
                    "production_lot_id": lot_id,
                    "routing_operation_id": f"p2-routing-operation-{job_suffix}-{operation_suffix}",
                    "lock_type": lock["lock_type"],
                    "resource_id": f"p2-resource-{_slug(cast(str, lock['resource_code']))}",
                    "start_at_utc": _instant(blueprint, cast(int, lock["start_tick"])),
                    "end_at_utc": _instant(blueprint, cast(int, lock["end_tick"])),
                }
            )
    return records


def _raw_rows(records: JsonObject, *, reverse_rows: bool) -> tuple[RawImportRow, ...]:
    rows: list[RawImportRow] = []
    position = 0
    for collection, id_field in COLLECTION_ID_FIELDS.items():
        values = sorted(
            cast(list[JsonObject], records[collection]),
            key=lambda item: cast(str, item[id_field]),
        )
        for record in values:
            source_record_id = cast(str, record[id_field])
            payload: JsonObject = {
                key: value for key, value in record.items() if key != id_field
            }
            outer = {
                "record_type": collection,
                "source_record_id": source_record_id,
                "payload_json": _canonical_bytes(payload).decode("utf-8"),
            }
            position += 1
            rows.append(
                RawImportRow(
                    row_identity=f"{collection}:{source_record_id}",
                    source_location=f"p2-correctness.jsonl:{position}",
                    raw_payload=_canonical_bytes(outer),
                )
            )
    if reverse_rows:
        rows.reverse()
    return tuple(rows)


def _context(case: CorrectnessCase) -> GenerationContext:
    return GenerationContext.create(
        scenario_id=case.scenario_id,
        scenario_version=cast(str, case.scenario["scenario_version"]),
        profile_id=cast(str, case.profile["profile_id"]),
        profile_version=cast(str, case.profile["profile_version"]),
        generator_id=ASSEMBLER_ID,
        generator_version=ASSEMBLER_VERSION,
        seed=cast(int, case.scenario["seed"]),
        target="test",
        required_capabilities=cast(list[str], case.scenario["required_capabilities"]),
    )


def _staged_batch(case: CorrectnessCase, *, reverse_rows: bool) -> StagedImportBatch:
    rows = _raw_rows(_source_records(case.blueprint), reverse_rows=reverse_rows)
    content = b"\n".join(row.raw_payload for row in rows)
    digest = sha256(content).hexdigest()
    return StagedImportBatch(
        batch_id=f"p2-correctness-{digest[:24]}",
        idempotency_key=f"p2-correctness-{digest}",
        source_system="plantnexus-synthetic",
        source_version=ASSEMBLER_VERSION,
        content_sha256=digest,
        source_name="p2-correctness.jsonl",
        media_type="application/x-ndjson",
        content_length_bytes=len(content),
        received_at=parse_utc_instant(cast(str, case.blueprint["cutoff_at_utc"])),
        data_plane=StagingDataPlane.SIMULATION,
        rows=rows,
        synthetic_provenance=SyntheticImportProvenance(
            scenario_id=case.scenario_id,
            scenario_version=cast(str, case.scenario["scenario_version"]),
            seed=cast(int, case.scenario["seed"]),
            factory_profile_id=cast(str, case.profile["profile_id"]),
            profile_version=cast(str, case.profile["profile_version"]),
            generator_id=ASSEMBLER_ID,
            generator_version=ASSEMBLER_VERSION,
        ),
    )


def _unit_registry(root: Path) -> UnitConversionRegistry:
    value = yaml.safe_load(
        (root / "schemas/rules/unit-conversion-registry.v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    return UnitConversionRegistry.from_mapping(cast(dict[str, object], value))


def _priority_facts(import_document: JsonObject, blueprint: JsonObject) -> JsonObject:
    priorities = {
        f"p2-demand-{_slug(cast(str, job['job_code']))}": (
            cast(int, job["priority_weight"]),
            cast(str, job["job_code"]),
        )
        for job in cast(list[JsonObject], blueprint["jobs"])
    }
    output: JsonObject = {}
    records = cast(JsonObject, import_document["records"])
    for demand in cast(list[JsonObject], records["demand_orders"]):
        source = cast(JsonObject, demand["source"])
        source_record_id = cast(str, source["source_record_id"])
        weight, job_code = priorities[source_record_id]
        output[cast(str, demand["demand_order_id"])] = {
            "priority_weight": weight,
            "source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
            "source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
            "source_record_id": f"P2-PRIORITY-{job_code}",
        }
    return output


def _identity_maps(
    import_document: JsonObject, expansion_document: JsonObject, problem: JsonObject
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    records = cast(JsonObject, import_document["records"])
    demand_jobs: dict[str, str] = {}
    for demand in cast(list[JsonObject], records["demand_orders"]):
        source_id = cast(str, cast(JsonObject, demand["source"])["source_record_id"])
        demand_jobs[cast(str, demand["demand_order_id"])] = source_id.removeprefix(
            "p2-demand-"
        ).upper()
    operation_codes = {
        cast(str, operation["routing_operation_id"]): cast(
            str, operation["operation_code"]
        )
        for operation in cast(list[JsonObject], records["routing_operations"])
    }
    operation_ids: dict[str, str] = {}
    operation_labels: dict[str, str] = {}
    for operation in cast(list[JsonObject], expansion_document["operation_instances"]):
        label = operation_codes[cast(str, operation["routing_operation_id"])]
        operation_id = cast(str, operation["operation_instance_id"])
        expected_job = demand_jobs[cast(str, operation["demand_order_id"])]
        if label.split("/", maxsplit=1)[0] != expected_job:
            raise ValueError("expanded operation/demand lineage mismatch")
        operation_ids[label] = operation_id
        operation_labels[operation_id] = label
    resource_ids = {
        cast(str, resource["resource_code"]): cast(str, resource["resource_id"])
        for resource in cast(list[JsonObject], problem["resources"])
    }
    resource_codes = {value: key for key, value in resource_ids.items()}
    return operation_ids, operation_labels, resource_ids, resource_codes


def execute_correctness_case(
    case: CorrectnessCase,
    *,
    root: Path,
    reverse_rows: bool = False,
    verify_manifest_hashes: bool = True,
) -> CorrectnessReplay:
    """Run one asset through every formal boundary and return the artifacts."""

    validate_correctness_case(case, verify_manifest_hashes=verify_manifest_hashes)
    context = _context(case)
    registry = _unit_registry(root)
    batch = _staged_batch(case, reverse_rows=reverse_rows)
    normalization = normalize_import(
        (NormalizationInput(batch, p1_mapping_profile(context)),),
        unit_registry=registry,
    )
    import_document = cast(JsonObject, normalization.document)
    quality = validate_import_package(cast(Any, import_document))
    if not quality.passed:
        raise ValueError(f"correctness source package failed quality: {case.scenario_id}")
    expansion = expand_orders(cast(Any, import_document), quality.document)
    snapshot = build_planning_snapshot(
        cast(Any, import_document),
        quality.document,
        expansion,
        cutoff_at_utc=cast(str, case.blueprint["cutoff_at_utc"]),
    )
    horizon_end = _instant(case.blueprint, cast(int, case.blueprint["horizon_ticks"]))
    problem_value = build_planning_problem_v2(
        snapshot,
        priority_facts=cast(Any, _priority_facts(import_document, case.blueprint)),
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=cast(int, case.blueprint["tick_seconds"]),
        horizon_start_utc=cast(str, case.blueprint["cutoff_at_utc"]),
        horizon_end_utc=horizon_end,
    )
    problem = cast(JsonObject, problem_value.document)
    limits = simulation_solve_limits(
        limits_id=f"LIMITS-{case.scenario_id}",
        limits_revision="1.0.0",
        source_record_id=f"LIMITS-{case.scenario_id}",
        max_wall_time_seconds=5.0,
        max_workers=1,
        random_seed=cast(int, case.scenario["seed"]),
    )
    result = GlobalCpSatStrategy().solve(
        cast(PlanningProblemDocumentV2, problem),
        simulation_delivery_policy(),
        limits,
        planning_run_id=(
            f"RUN-{case.scenario_id}-{'REVERSED' if reverse_rows else 'PRIMARY'}"
        ),
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
    )
    if result.validation_report is None:
        raise ValueError("correctness strategy candidate lacks formal Validator evidence")
    operation_ids, operation_labels, resource_ids, resource_codes = _identity_maps(
        import_document, cast(JsonObject, expansion.document), problem
    )
    return CorrectnessReplay(
        case=case,
        import_document=import_document,
        import_dataset_hash=normalization.dataset_hash,
        quality_report=cast(JsonObject, quality.document),
        expansion_document=cast(JsonObject, expansion.document),
        snapshot_document=cast(JsonObject, snapshot.document),
        snapshot_hash=snapshot.snapshot_hash,
        problem=problem,
        solution=cast(JsonObject, result.solution),
        solver_report=cast(JsonObject, result.solver_report),
        validation_report=cast(JsonObject, result.validation_report),
        operation_ids=operation_ids,
        operation_labels=operation_labels,
        resource_ids=resource_ids,
        resource_codes=resource_codes,
    )


def assignment_projection(replay: CorrectnessReplay) -> list[JsonObject]:
    """Return stable business labels for schedule assertions and reports."""

    values: list[JsonObject] = []
    for assignment in cast(list[JsonObject], replay.solution["assignments"]):
        label = replay.operation_labels[cast(str, assignment["operation_id"])]
        job_code, operation_code = label.split("/", maxsplit=1)
        values.append(
            {
                "job_code": job_code,
                "operation_code": operation_code,
                "resource_code": replay.resource_codes[
                    cast(str, assignment["resource_id"])
                ],
                "start_tick": assignment["start_tick"],
                "end_tick": assignment["end_tick"],
            }
        )
    values.sort(key=lambda item: (item["job_code"], item["operation_code"]))
    return values


def verify_correctness_replay(
    replay: CorrectnessReplay, *, verify_artifact_hashes: bool = True
) -> None:
    """Compare formal output with immutable asset expectations."""

    expected = replay.case.expected
    stage = cast(list[JsonObject], replay.solution["objective_stage_results"])[0]
    actual = {
        "solver_status": replay.solution["solver_status"],
        "validator_status": replay.validation_report["status"],
        "objective_value": stage["objective_value"],
        "best_bound": stage["best_bound"],
        "relative_gap": stage["relative_gap"],
        "assignments": assignment_projection(replay),
    }
    expected_projection = {
        key: expected[key]
        for key in (
            "solver_status",
            "validator_status",
            "objective_value",
            "best_bound",
            "relative_gap",
            "assignments",
        )
    }
    if actual != expected_projection:
        raise ValueError(
            f"correctness expected outcome mismatch for {replay.case.scenario_id}: {actual}"
        )
    if verify_artifact_hashes:
        artifacts = {
            "import_dataset_hash": replay.import_dataset_hash,
            "snapshot_hash": replay.snapshot_hash,
            "problem_hash": replay.problem["problem_hash"],
        }
        if replay.case.manifest.get("expected_artifacts") != artifacts:
            raise ValueError(
                f"correctness replay hash drift: {replay.case.scenario_id}"
            )


def _assignment_for(solution: JsonObject, operation_id: str) -> JsonObject:
    matches = [
        assignment
        for assignment in cast(list[JsonObject], solution["assignments"])
        if assignment["operation_id"] == operation_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one assignment for {operation_id}")
    return matches[0]


def _set_interval(
    assignment: JsonObject,
    problem: JsonObject,
    *,
    start_tick: int,
    end_tick: int,
    duration_seconds: int,
) -> None:
    horizon_start = parse_utc_instant(cast(str, problem["horizon_start_utc"]))
    tick_seconds = cast(int, problem["tick_seconds"])
    assignment.update(
        {
            "start_tick": start_tick,
            "end_tick": end_tick,
            "duration_ticks": end_tick - start_tick,
            "start_at_utc": format_utc_instant(
                horizon_start + timedelta(seconds=start_tick * tick_seconds)
            ),
            "end_at_utc": format_utc_instant(
                horizon_start + timedelta(seconds=end_tick * tick_seconds)
            ),
            "duration_seconds": duration_seconds,
        }
    )


def _refresh_problem_reference(problem: JsonObject, solution: JsonObject) -> None:
    problem["problem_hash"] = problem_v2_hash_for(problem)
    reference = cast(JsonObject, solution["problem"])
    for field in (
        "problem_version",
        "problem_builder_version",
        "problem_hash_projection_version",
        "problem_hash",
        "snapshot_id",
        "tick_seconds",
        "horizon_start_utc",
        "horizon_end_utc",
    ):
        reference[field] = problem[field]


def _edge_between(problem: JsonObject, predecessor: str, successor: str) -> JsonObject:
    matches = [
        edge
        for edge in cast(list[JsonObject], problem["precedence_edges"])
        if edge["predecessor_operation_id"] == predecessor
        and edge["successor_operation_id"] == successor
    ]
    if len(matches) != 1:
        raise ValueError("expected one precedence edge for mutation")
    return matches[0]


def materialize_constraint_mutation(
    replay: CorrectnessReplay, constraint_id: str
) -> tuple[JsonObject, JsonObject]:
    """Apply one formula-free field mutation to a Solver-produced candidate."""

    problem = deepcopy(replay.problem)
    solution = deepcopy(replay.solution)
    operation = replay.operation_ids
    resource = replay.resource_ids
    if constraint_id == "C-001":
        target = operation["J1/O1"]
        solution["assignments"] = [
            value
            for value in cast(list[JsonObject], solution["assignments"])
            if value["operation_id"] != target
        ]
    elif constraint_id == "C-002":
        edge = _edge_between(problem, operation["J1/O1"], operation["J1/O2"])
        edge["min_lag_seconds"] = 60
        _refresh_problem_reference(problem, solution)
    elif constraint_id == "C-003":
        _assignment_for(solution, operation["J1/O1"])["resource_id"] = (
            "p2-unknown-resource"
        )
    elif constraint_id == "C-004":
        assignment = _assignment_for(solution, operation["J2/O1"])
        assignment["resource_id"] = resource["R1"]
        _set_interval(
            assignment, problem, start_tick=0, end_tick=2, duration_seconds=120
        )
    elif constraint_id == "C-005":
        _set_interval(
            _assignment_for(solution, operation["J1/O1"]),
            problem,
            start_tick=0,
            end_tick=2,
            duration_seconds=120,
        )
    elif constraint_id == "C-006":
        _set_interval(
            _assignment_for(solution, operation["J1/O1"]),
            problem,
            start_tick=1,
            end_tick=2,
            duration_seconds=60,
        )
    elif constraint_id == "C-007":
        _assignment_for(solution, operation["J1/O1"])["resource_id"] = resource["R2"]
    elif constraint_id == "C-008":
        assignment = _assignment_for(solution, operation["J1/O1"])
        assignment["resource_id"] = resource["R2"]
        _set_interval(
            assignment, problem, start_tick=1, end_tick=2, duration_seconds=60
        )
    elif constraint_id == "C-009":
        edge = _edge_between(problem, operation["J1/O1"], operation["J1/O2"])
        edge["transport_lag_seconds"] = 180
        _refresh_problem_reference(problem, solution)
    elif constraint_id == "C-010":
        _set_interval(
            _assignment_for(solution, operation["J1/O1"]),
            problem,
            start_tick=0,
            end_tick=2,
            duration_seconds=120,
        )
    elif constraint_id == "C-011":
        _set_interval(
            _assignment_for(solution, operation["J1/O1"]),
            problem,
            start_tick=5,
            end_tick=6,
            duration_seconds=60,
        )
    else:
        raise ValueError(f"unsupported constraint mutation {constraint_id}")
    cast(list[JsonObject], solution["assignments"]).sort(
        key=lambda item: cast(str, item["operation_id"])
    )
    return problem, solution


def _mutation_replays(replays: Mapping[str, CorrectnessReplay]) -> list[JsonObject]:
    sources = {
        "C-001": "P2-GOLDEN-JSSP",
        "C-002": "P2-GOLDEN-JSSP",
        "C-003": "P2-GOLDEN-JSSP",
        "C-004": "P2-GOLDEN-FJSP",
        "C-005": "P2-CALENDAR",
        "C-006": "P2-MATERIAL-DELAY",
        "C-007": "P2-RUNNING",
        "C-008": "P2-HARD-LOCK",
        "C-009": "P2-CROSS-WORKSHOP",
        "C-010": "P2-GOLDEN-FJSP",
        "C-011": "P2-MATERIAL-DELAY",
    }
    evidence: list[JsonObject] = []
    for constraint_id in CONSTRAINT_IDS:
        replay = replays[sources[constraint_id]]
        problem, solution = materialize_constraint_mutation(replay, constraint_id)
        first = validate_problem_schedule(problem, solution)
        second = validate_problem_schedule(problem, solution)
        observed = tuple(
            cast(str, violation["constraint_id"])
            for violation in cast(list[JsonObject], first["violations"])
        )
        if first != second or first["status"] != "FAIL" or observed != (constraint_id,):
            raise ValueError(
                f"P2 mutation {constraint_id} expected exact failure, got {observed}"
            )
        evidence.append(
            {
                "constraint_id": constraint_id,
                "scenario_id": replay.case.scenario_id,
                "status": first["status"],
                "hard_violation_count": first["hard_violation_count"],
                "deterministic_replay": True,
            }
        )
    return evidence


def _historical_asset_manifest(root: Path) -> JsonObject:
    lines: list[str] = []
    files: list[JsonObject] = []
    for relative_root in _HISTORICAL_ASSET_ROOTS:
        for path in sorted((root / relative_root).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            digest = sha256(path.read_bytes()).hexdigest()
            lines.append(f"{relative} {digest}")
            files.append({"path": relative, "sha256": digest})
    manifest_digest = sha256("\n".join(lines).encode("utf-8")).hexdigest()
    if manifest_digest != _HISTORICAL_ASSET_MANIFEST_DIGEST:
        raise ValueError("P0/P1 immutable correctness asset manifest drifted")
    return {
        "file_count": len(files),
        "manifest_sha256": manifest_digest,
        "files": files,
    }


def _frozen_fingerprints(root: Path) -> JsonObject:
    evidence: JsonObject = {}
    for relative, expected in _FROZEN_FILES.items():
        observed = sha256((root / relative).read_bytes()).hexdigest()
        if observed != expected:
            raise ValueError(f"frozen TASK-P2-09 input changed: {relative}")
        evidence[relative] = {"sha256": observed}
    return evidence


def _asset_file_hashes(root: Path, cases: Sequence[CorrectnessCase]) -> list[JsonObject]:
    paths = sorted({path.resolve() for case in cases for path in case.asset_paths})
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in paths
    ]


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def run_correctness_checks(root: Path) -> JsonObject:
    """Run all seven scenarios, reordering properties, and exact mutations."""

    cases = load_correctness_cases(root)
    fingerprints = _frozen_fingerprints(root)
    historical_assets = _historical_asset_manifest(root)
    primary: dict[str, CorrectnessReplay] = {}
    scenario_evidence: list[JsonObject] = []
    property_evidence: list[JsonObject] = []
    positive_coverage: set[str] = set()
    for case in cases:
        replay = execute_correctness_case(case, root=root)
        verify_correctness_replay(replay)
        primary[case.scenario_id] = replay
        positive_coverage.update(cast(list[str], case.expected["positive_constraint_ids"]))
        stage = cast(list[JsonObject], replay.solution["objective_stage_results"])[0]
        scenario_evidence.append(
            {
                "scenario_id": case.scenario_id,
                "scenario_version": case.scenario["scenario_version"],
                "profile_id": case.profile["profile_id"],
                "profile_version": case.profile["profile_version"],
                "seed": case.scenario["seed"],
                "import_dataset_hash": replay.import_dataset_hash,
                "snapshot_hash": replay.snapshot_hash,
                "problem_hash": replay.problem["problem_hash"],
                "solver_status": replay.solution["solver_status"],
                "objective_value": stage["objective_value"],
                "best_bound": stage["best_bound"],
                "relative_gap": stage["relative_gap"],
                "validator_status": replay.validation_report["status"],
                "hard_violation_count": replay.validation_report[
                    "hard_violation_count"
                ],
                "assignment_count": len(
                    cast(list[JsonObject], replay.solution["assignments"])
                ),
                "assignments": assignment_projection(replay),
                "model_metrics": replay.solver_report["model_metrics"],
            }
        )
        reversed_replay = execute_correctness_case(
            case, root=root, reverse_rows=True
        )
        verify_correctness_replay(reversed_replay)
        if (
            replay.import_dataset_hash != reversed_replay.import_dataset_hash
            or replay.snapshot_hash != reversed_replay.snapshot_hash
            or replay.problem["problem_hash"] != reversed_replay.problem["problem_hash"]
            or assignment_projection(replay) != assignment_projection(reversed_replay)
            or replay.validation_report != reversed_replay.validation_report
        ):
            raise ValueError(f"source ordering changed replay: {case.scenario_id}")
        property_evidence.append(
            {
                "scenario_id": case.scenario_id,
                "source_row_reordering": "IDENTICAL_BUSINESS_ARTIFACTS",
                "solver_candidate_validator_pass": True,
                "problem_hash": replay.problem["problem_hash"],
            }
        )
    if positive_coverage != set(CONSTRAINT_IDS):
        raise ValueError("positive correctness catalog does not cover C-001 through C-011")
    mutations = _mutation_replays(primary)
    checks = [
        _pass(
            "frozen-schema-problem-strategy-validator-policy-generator-and-lock",
            fingerprints,
        ),
        _pass("p0-p1-immutable-asset-manifest", historical_assets),
        _pass(
            "seven-versioned-profile-scenario-blueprint-manifest-assets",
            {
                "scenario_ids": list(SCENARIO_IDS),
                "asset_files": _asset_file_hashes(root, cases),
            },
        ),
        _pass("formal-ingress-snapshot-problem-replay", scenario_evidence),
        _pass(
            "golden-jssp-fjsp-manual-optimum-and-validator",
            scenario_evidence[:2],
        ),
        _pass("five-scenario-correctness-matrix", scenario_evidence[2:]),
        _pass("solver-generated-property-and-reordering-replay", property_evidence),
        _pass("formula-free-exact-c001-c011-validator-mutations", mutations),
    ]
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "scenario_cases": len(cases),
            "golden_cases": 2,
            "matrix_cases": 5,
            "solver_candidates": len(cases),
            "independent_validator_passes": len(cases),
            "property_replays": len(property_evidence),
            "mutation_cases": len(mutations),
            "constraints_positive_covered": len(positive_coverage),
            "constraints_negative_covered": len(mutations),
        },
        "versions": {
            "catalog": CATALOG_VERSION,
            "blueprint": BLUEPRINT_VERSION,
            "manifest": MANIFEST_VERSION,
            "expected": EXPECTED_VERSION,
            "assembler": f"{ASSEMBLER_ID}@{ASSEMBLER_VERSION}",
            "policy": (
                f"{SIMULATION_DELIVERY_POLICY_ID}@"
                f"{SIMULATION_DELIVERY_POLICY_REVISION}"
            ),
            "backend": BACKEND_VERSION,
            "solver": ORTOOLS_VERSION,
            **_PIPELINE_VERSIONS,
        },
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "formal_path": (
                "RAW_STAGING_TO_IMPORT_V2_TO_QUALITY_TO_EXPANSION_TO_"
                "SNAPSHOT_V2_TO_PROBLEM_V2_TO_GLOBAL_STRATEGY_TO_VALIDATOR"
            ),
            "direct_problem_or_cp_model_construction": "NONE",
            "schema_contract_changes": "NONE",
            "planning_solver_validator_semantic_changes": "NONE",
            "dependency_changes": "NONE",
            "performance_baseline": "NONE_NO_XS_S_M",
            "production_authority": "NOT_CLAIMED",
            "reference_export_benchmark": "NOT_IMPLEMENTED_BY_TASK",
            "p2_10_plus_or_p3": "NOT_STARTED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    report = run_correctness_checks(arguments.root.resolve())
    _write_report(arguments.report, report)
    print(
        f"{report['status']} P2 correctness: "
        f"scenarios={report['counts']['scenario_cases']} "
        f"mutations={report['counts']['mutation_cases']} "
        f"checks={report['check_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ASSEMBLER_ID",
    "ASSEMBLER_VERSION",
    "BLUEPRINT_VERSION",
    "CATALOG_VERSION",
    "CONSTRAINT_IDS",
    "CorrectnessCase",
    "CorrectnessReplay",
    "EXPECTED_VERSION",
    "MANIFEST_VERSION",
    "REPORT_VERSION",
    "SCENARIO_IDS",
    "assignment_projection",
    "execute_correctness_case",
    "load_correctness_cases",
    "main",
    "materialize_constraint_mutation",
    "run_correctness_checks",
    "validate_correctness_case",
    "verify_correctness_replay",
]
