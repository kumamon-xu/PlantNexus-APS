"""P0 Simulation contract evidence for TASK-P0-05.

TEST-SCENARIO-REPLAY and TEST-SIM-ISOLATION intentionally use an empty
Standard Import package; SIM-MINIMAL-001 belongs to TASK-P0-06.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from app.domain.capabilities import CapabilityContractError
from app.domain.errors import ProductErrorCode
from app.simulation.generators.contract_check import run_contract_checks
from app.simulation.generators.contracts import GenerationContext
from app.simulation.generators.determinism import (
    DeterminismContractError,
    SeedMaterial,
    canonical_json_bytes,
)
from app.simulation.generators.package_contract import (
    build_empty_import_package,
    validate_generated_scenario_package,
)
from app.simulation.profiles.contracts import (
    FactoryProfileContractError,
    FactoryProfileDocument,
    validate_factory_profile_contract,
)
from app.simulation.scenarios.contracts import (
    ScenarioManifestDocument,
    ScenarioSpecDocument,
    SimulationContractCode,
    SimulationContractError,
    validate_scenario_manifest_contract,
    validate_scenario_spec_contract,
)


TEST_IDS = ("TEST-SCENARIO-REPLAY", "TEST-SIM-ISOLATION")
ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "schemas" / "scenario"
JSON_SCHEMA_ROOT = ROOT / "schemas" / "json"


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(load_json(path), format_checker=FormatChecker())


def context(**overrides: object) -> GenerationContext:
    values: dict[str, Any] = {
        "scenario_id": "SCHEMA-SCENARIO-P0-05",
        "scenario_version": "1.0.0",
        "profile_id": "SCHEMA-PROFILE-P0-05",
        "profile_version": "1.0.0",
        "generator_id": "P0-EMPTY-IMPORT-GENERATOR",
        "generator_version": "1.0.0",
        "seed": 20260819,
        "target": "test",
        "required_capabilities": ("DAG_ROUTING", "MACHINE_CALENDAR"),
    }
    values.update(overrides)
    return GenerationContext.create(**values)


def walk_json(value: Any):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def test_simulation_schemas_and_samples_are_valid_strict_v1_contracts() -> None:
    pairs = (
        ("factory-profile.schema.json", "factory-profile.synthetic.json"),
        ("scenario-spec.schema.json", "scenario-spec.synthetic.json"),
        ("scenario-manifest.schema.json", "scenario-manifest.synthetic.json"),
    )
    schema_ids: set[str] = set()
    for schema_name, sample_name in pairs:
        schema = load_json(SCENARIO_ROOT / schema_name)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] not in schema_ids
        schema_ids.add(schema["$id"])
        assert all("default" not in node for node in walk_json(schema))

        sample = load_json(SCENARIO_ROOT / sample_name)
        validator(SCENARIO_ROOT / schema_name).validate(sample)
        assert json.loads(canonical_json_bytes(sample)) == sample

    profile = cast(
        FactoryProfileDocument,
        load_json(SCENARIO_ROOT / "factory-profile.synthetic.json"),
    )
    scenario = cast(
        ScenarioSpecDocument,
        load_json(SCENARIO_ROOT / "scenario-spec.synthetic.json"),
    )
    manifest = cast(
        ScenarioManifestDocument,
        load_json(SCENARIO_ROOT / "scenario-manifest.synthetic.json"),
    )
    validate_factory_profile_contract(profile)
    validate_scenario_spec_contract(scenario)
    validate_scenario_manifest_contract(manifest)


def test_schema_rejects_missing_seed_wrong_versions_unknown_fields_and_production() -> None:
    scenario_validator = validator(SCENARIO_ROOT / "scenario-spec.schema.json")
    scenario = load_json(SCENARIO_ROOT / "scenario-spec.synthetic.json")
    missing_seed = copy.deepcopy(scenario)
    missing_seed.pop("seed")
    with pytest.raises(ValidationError):
        scenario_validator.validate(missing_seed)

    negative_seed = copy.deepcopy(scenario)
    negative_seed["seed"] = -1
    with pytest.raises(ValidationError):
        scenario_validator.validate(negative_seed)

    wrong_version = copy.deepcopy(scenario)
    wrong_version["scenario_contract_version"] = "scenario-spec.v2"
    with pytest.raises(ValidationError):
        scenario_validator.validate(wrong_version)

    unknown_field = copy.deepcopy(scenario)
    unknown_field["production_default"] = True
    with pytest.raises(ValidationError):
        scenario_validator.validate(unknown_field)

    scenario_as_production = copy.deepcopy(scenario)
    scenario_as_production["synthetic_only"] = False
    with pytest.raises(ValidationError):
        scenario_validator.validate(scenario_as_production)

    manifest_validator = validator(SCENARIO_ROOT / "scenario-manifest.schema.json")
    manifest = load_json(SCENARIO_ROOT / "scenario-manifest.synthetic.json")
    production_manifest = copy.deepcopy(manifest)
    production_manifest["target_environment"] = "production"
    with pytest.raises(ValidationError):
        manifest_validator.validate(production_manifest)


def test_profile_semantic_precheck_rejects_inverted_range() -> None:
    profile = cast(
        FactoryProfileDocument,
        load_json(SCENARIO_ROOT / "factory-profile.synthetic.json"),
    )
    invalid = copy.deepcopy(profile)
    invalid["routing"]["operation_count"] = {"minimum": 2, "maximum": 1}
    with pytest.raises(FactoryProfileContractError, match="minimum <= maximum"):
        validate_factory_profile_contract(invalid)


def test_same_context_replays_same_canonical_import_and_hash() -> None:
    first = build_empty_import_package(
        context(), generated_at=datetime(2026, 8, 19, 0, 0, tzinfo=UTC)
    )
    replay = build_empty_import_package(
        context(), generated_at=datetime(2026, 8, 19, 1, 0, tzinfo=UTC)
    )

    assert first.import_package == replay.import_package
    assert first.canonical_dataset == replay.canonical_dataset
    assert first.dataset_hash == replay.dataset_hash
    assert first.manifest["generated_at"] != replay.manifest["generated_at"]
    assert first.import_package["records"] == {}
    assert first.import_package["import_package_version"] == "import-package.v1"
    validator(JSON_SCHEMA_ROOT / "import-package.schema.json").validate(
        first.import_package
    )
    validate_generated_scenario_package(first)


def test_manifest_sample_is_the_replayable_empty_package_provenance() -> None:
    generated = build_empty_import_package(
        context(), generated_at=datetime(2026, 8, 19, 0, 0, tzinfo=UTC)
    )
    sample = load_json(SCENARIO_ROOT / "scenario-manifest.synthetic.json")
    assert generated.manifest == sample


def test_seed_or_generator_version_changes_provenance_and_hash() -> None:
    baseline = build_empty_import_package(context())
    changed_seed = build_empty_import_package(context(seed=20260820))
    changed_version = build_empty_import_package(context(generator_version="1.0.1"))

    assert baseline.dataset_hash != changed_seed.dataset_hash
    assert baseline.dataset_hash != changed_version.dataset_hash
    assert changed_seed.manifest["seed"] == 20260820
    assert changed_version.manifest["generator"]["generator_version"] == "1.0.1"


def test_capability_set_order_is_canonicalized_before_hashing() -> None:
    forward = build_empty_import_package(
        context(required_capabilities=("DAG_ROUTING", "MACHINE_CALENDAR"))
    )
    reversed_declaration = build_empty_import_package(
        context(required_capabilities=("MACHINE_CALENDAR", "DAG_ROUTING"))
    )
    assert forward.import_package == reversed_declaration.import_package
    assert forward.dataset_hash == reversed_declaration.dataset_hash
    assert forward.manifest["required_capabilities"] == [
        "DAG_ROUTING",
        "MACHINE_CALENDAR",
    ]


def test_named_layer_seed_is_repeatable_and_call_order_independent() -> None:
    seed = SeedMaterial(
        root_seed=20260819,
        generator_id="P0-EMPTY-IMPORT-GENERATOR",
        generator_version="1.0.0",
    )
    topology = seed.child("topology")
    first = topology.derive_seed("resource", index=3)
    _ = seed.child("orders").derive_seed("order", index=200)
    replay = seed.child("topology").derive_seed("resource", index=3)
    other_layer = seed.child("calendar").derive_seed("resource", index=3)

    assert first == replay
    assert first != other_layer
    assert topology.deterministic_index(7, "resource", index=3) < 7
    with pytest.raises(DeterminismContractError):
        topology.deterministic_index(0, "resource")


def test_production_unknown_duplicate_and_unsupported_requests_fail_explicitly() -> None:
    with pytest.raises(SimulationContractError) as production:
        context(target="production")
    assert production.value.code is SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN

    with pytest.raises(CapabilityContractError) as unsupported:
        context(required_capabilities=("SECONDARY_CAPACITY",))
    assert unsupported.value.code is ProductErrorCode.UNSUPPORTED_CAPABILITY

    with pytest.raises(CapabilityContractError) as unknown:
        context(required_capabilities=("UNREGISTERED_CAPABILITY",))
    assert unknown.value.code is ProductErrorCode.INVALID_CAPABILITY_DECLARATION

    with pytest.raises(CapabilityContractError) as duplicate:
        context(required_capabilities=("DAG_ROUTING", "DAG_ROUTING"))
    assert duplicate.value.code is ProductErrorCode.DUPLICATE_CAPABILITY


def test_generator_protocol_boundary_does_not_import_planning_or_solver() -> None:
    source_root = ROOT / "backend" / "app" / "simulation" / "generators"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in source_root.glob("*.py")
    ).lower()
    assert "from app.planning" not in source
    assert "import app.planning" not in source
    assert "ortools" not in source
    assert "cpmodel" not in source
    assert "intervalvar" not in source

    report = run_contract_checks()
    assert report["result"] == "PASS"
    report_test_ids = report["test_ids"]
    assert isinstance(report_test_ids, list)
    assert tuple(report_test_ids) == TEST_IDS
    assert report["record_collections"] == 0
    assert report["issues"] == []
