"""TEST-SCENARIO-REPLAY / TEST-SIM-ISOLATION for P1 canonical generation."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
import pytest
import yaml

from app.domain.capabilities import CapabilityContractError
from app.domain.canonical_records import (
    ImportPackageDocumentV2,
    validate_import_package_v2,
)
from app.normalization import UnitConversionRegistry
from app.simulation.generators.calendars import DeterministicCalendarGenerator
from app.simulation.generators.contracts import (
    GeneratedRecordCollections,
    GenerationContext,
    P1_GENERATOR_VERSION,
    SyntheticGenerationManifestDocument,
    SyntheticGeneratorError,
    SyntheticGeneratorErrorCode,
)
from app.simulation.generators.determinism import SeedMaterial
from app.simulation.generators.execution_states import (
    DeterministicExecutionStateGenerator,
)
from app.simulation.generators.locks import DeterministicLockGenerator
from app.simulation.generators.materials import DeterministicMaterialGenerator
from app.simulation.generators.orders import DeterministicOrderGenerator
from app.simulation.generators.package_contract import (
    validate_p1_generated_scenario_package,
)
from app.simulation.generators.package_generator import (
    DeterministicSyntheticPackageGenerator,
)
from app.simulation.generators.routing import DeterministicRoutingGenerator
from app.simulation.generators.topology import DeterministicTopologyGenerator
from app.simulation.profiles.contracts import (
    FactoryProfileDocument,
    validate_factory_profile_contract,
)
from app.simulation.scenarios.contracts import (
    ScenarioSpecDocument,
    SimulationContractCode,
    SimulationContractError,
    validate_scenario_spec_contract,
)


ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = ROOT / "fixtures" / "synthetic" / "SIM-P1-INGRESS-001"
PROFILE_SCHEMA = ROOT / "schemas" / "scenario" / "factory-profile.schema.json"
SCENARIO_SCHEMA = ROOT / "schemas" / "scenario" / "scenario-spec.schema.json"
UNIT_REGISTRY = ROOT / "schemas" / "rules" / "unit-conversion-registry.v1.yaml"


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _profile() -> FactoryProfileDocument:
    return cast(FactoryProfileDocument, _json(ASSET_ROOT / "factory-profile.json"))


def _scenario() -> ScenarioSpecDocument:
    return cast(ScenarioSpecDocument, _json(ASSET_ROOT / "scenario-spec.json"))


def _registry() -> UnitConversionRegistry:
    document = cast(
        dict[str, object], yaml.safe_load(UNIT_REGISTRY.read_text(encoding="utf-8"))
    )
    return UnitConversionRegistry.from_mapping(document)


def _context(
    *,
    profile: FactoryProfileDocument | None = None,
    scenario: ScenarioSpecDocument | None = None,
) -> GenerationContext:
    return GenerationContext.from_documents(
        profile=profile or _profile(),
        scenario=scenario or _scenario(),
        target="test",
    )


def _generator(
    **overrides: object,
) -> DeterministicSyntheticPackageGenerator:
    values: dict[str, object] = {"unit_registry": _registry(), **overrides}
    return DeterministicSyntheticPackageGenerator(**values)  # type: ignore[arg-type]


def test_p1_assets_satisfy_published_profile_and_scenario_contracts() -> None:
    profile = _profile()
    scenario = _scenario()
    Draft202012Validator(_json(PROFILE_SCHEMA)).validate(profile)
    Draft202012Validator(_json(SCENARIO_SCHEMA)).validate(scenario)
    validate_factory_profile_contract(profile)
    validate_scenario_spec_contract(scenario)
    context = _context(profile=profile, scenario=scenario)
    assert context.scale is not None
    assert context.scale.order_count == 2
    assert context.required_capabilities == tuple(
        sorted(context.required_capabilities, key=lambda value: value.value)
    )
    with pytest.raises(FrozenInstanceError):
        context.seed = 1  # type: ignore[misc]


def test_generator_produces_nonempty_valid_import_v2_and_quality_evidence() -> None:
    generated = _generator().generate(
        _context(), generated_at=datetime(2026, 8, 20, tzinfo=UTC)
    )
    document = cast(ImportPackageDocumentV2, generated.import_package)
    validate_import_package_v2(document)
    validate_p1_generated_scenario_package(generated)
    assert generated.quality_report is not None
    assert generated.quality_report["status"] == "PASS"
    assert generated.quality_report["error_count"] == 0
    assert document["import_package_version"] == "import-package.v2"
    assert document["synthetic"] is True
    assert set(document["records"]) == {
        "canonical_records_version",
        "factories",
        "workshops",
        "production_lines",
        "resource_groups",
        "resources",
        "calendars",
        "products",
        "routing_versions",
        "routing_operations",
        "routing_precedence_edges",
        "routing_resource_options",
        "demand_orders",
        "production_orders",
        "production_lots",
        "execution_facts",
        "operation_locks",
    }
    counts = {
        collection: len(values)
        for collection, values in document["records"].items()
        if isinstance(values, list)
    }
    assert counts == {
        "factories": 1,
        "workshops": 2,
        "production_lines": 2,
        "resource_groups": 2,
        "resources": 4,
        "calendars": 4,
        "products": 2,
        "routing_versions": 2,
        "routing_operations": 6,
        "routing_precedence_edges": 4,
        "routing_resource_options": 12,
        "demand_orders": 2,
        "production_orders": 2,
        "production_lots": 2,
        "execution_facts": 1,
        "operation_locks": 1,
    }
    assert all(count > 0 for count in counts.values())
    assert all(
        option["cycle_seconds_per_unit"] >= 0
        and isinstance(option["cycle_seconds_per_unit"], int)
        for option in document["records"]["routing_resource_options"]
    )


def test_same_inputs_replay_bytes_and_hash_while_generated_at_is_external() -> None:
    context = _context()
    generator = _generator()
    first = generator.generate(
        context, generated_at=datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    )
    replay = generator.generate(
        context, generated_at=datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    )
    first_manifest = cast(SyntheticGenerationManifestDocument, first.manifest)
    replay_manifest = cast(SyntheticGenerationManifestDocument, replay.manifest)
    assert first.canonical_dataset == replay.canonical_dataset
    assert first.dataset_hash == replay.dataset_hash
    assert first_manifest["generated_at"] != replay_manifest["generated_at"]
    assert first_manifest["dataset_hash"] == replay_manifest["dataset_hash"]


def test_seed_profile_and_generator_versions_are_not_ignored() -> None:
    baseline = _generator().generate(_context())

    seed_scenario = deepcopy(_scenario())
    seed_scenario["seed"] += 1
    seed_changed = _generator().generate(_context(scenario=seed_scenario))
    assert seed_changed.dataset_hash != baseline.dataset_hash

    profile = deepcopy(_profile())
    scenario = deepcopy(_scenario())
    profile["profile_version"] = "1.0.1"
    scenario["factory_profile"]["profile_version"] = "1.0.1"
    profile_changed = _generator().generate(
        _context(profile=profile, scenario=scenario)
    )
    assert profile_changed.dataset_hash != baseline.dataset_hash

    first_seed = SeedMaterial(
        20260820, "PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR", "1.0.0"
    )
    version_seed = SeedMaterial(
        20260820, "PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR", "1.0.1"
    )
    assert first_seed.derive_seed("version-sensitive") != version_seed.derive_seed(
        "version-sensitive"
    )
    version_scenario = deepcopy(_scenario())
    version_scenario["generator"]["generator_version"] = "1.0.1"
    with pytest.raises(SyntheticGeneratorError) as rejected:
        _generator().generate(_context(scenario=version_scenario))
    assert rejected.value.code is SyntheticGeneratorErrorCode.GENERATOR_VERSION_MISMATCH


def test_each_layer_is_pure_and_named_seed_order_independent() -> None:
    context = _context()
    topology = DeterministicTopologyGenerator()
    routing = DeterministicRoutingGenerator()
    orders = DeterministicOrderGenerator()
    calendars = DeterministicCalendarGenerator()
    materials = DeterministicMaterialGenerator()
    executions = DeterministicExecutionStateGenerator()
    locks = DeterministicLockGenerator()

    first_topology = topology.generate_topology(context)
    _ = (
        SeedMaterial(context.seed, context.generator_id, context.generator_version)
        .child("unrelated-test-stream")
        .derive_seed("noise")
    )
    assert topology.generate_topology(context) == first_topology
    routed = routing.generate_routings(context, first_topology)
    assert first_topology == topology.generate_topology(context)

    ordered_first = orders.generate_orders(context, routed)
    calendars_first = calendars.generate_calendars(context, routed)
    ordered_after = orders.generate_orders(context, calendars_first)
    calendars_after = calendars.generate_calendars(context, ordered_first)
    assert ordered_first["demand_orders"] == ordered_after["demand_orders"]
    assert calendars_first["calendars"] == calendars_after["calendars"]

    materialized = materials.generate_material_readiness(context, ordered_first)
    execution_first = executions.generate_execution_states(context, materialized)
    locks_first = locks.generate_locks(context, materialized)
    execution_after = executions.generate_execution_states(context, locks_first)
    locks_after = locks.generate_locks(context, execution_first)
    assert execution_first["execution_facts"] == execution_after["execution_facts"]
    assert locks_first["operation_locks"] == locks_after["operation_locks"]
    assert len(materialized["production_orders"]) == 2


def test_production_unsupported_mismatch_and_profile_shape_reject_explicitly() -> None:
    with pytest.raises(SimulationContractError) as production:
        GenerationContext.from_documents(
            profile=_profile(), scenario=_scenario(), target="production"
        )
    assert production.value.code is SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN

    unsupported = deepcopy(_scenario())
    unsupported["required_capabilities"] = ["SECONDARY_CAPACITY"]
    with pytest.raises(CapabilityContractError):
        _context(scenario=unsupported)

    mismatch = deepcopy(_scenario())
    mismatch["factory_profile"]["profile_id"] = "OTHER-PROFILE"
    with pytest.raises(SyntheticGeneratorError) as mismatched:
        _context(scenario=mismatch)
    assert (
        mismatched.value.code is SyntheticGeneratorErrorCode.PROFILE_SCENARIO_MISMATCH
    )

    unsupported_profile = deepcopy(_profile())
    unsupported_profile["resources"]["target_count"] = {
        "minimum": 1,
        "maximum": 1,
    }
    with pytest.raises(SyntheticGeneratorError) as shape:
        _context(profile=unsupported_profile)
    assert shape.value.code is SyntheticGeneratorErrorCode.UNSUPPORTED_PROFILE_SHAPE


class _InvalidReferenceLockGenerator:
    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_locks(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        del context
        return {
            **records,
            "operation_locks": (
                {
                    "lock_id": "invalid-lock",
                    "production_lot_id": "production-lot-001",
                    "routing_operation_id": "routing-operation-001-003",
                    "lock_type": "HARD_LOCK",
                    "resource_id": "missing-resource",
                    "start_at_utc": "2026-08-20T10:00:00Z",
                    "end_at_utc": "2026-08-20T11:00:00Z",
                },
            ),
        }


def test_generated_normalization_and_data_validation_failures_are_explicit() -> None:
    wrong_registry = replace(_registry(), version="unit-conversion-registry.invalid")
    with pytest.raises(SyntheticGeneratorError) as normalization:
        DeterministicSyntheticPackageGenerator(wrong_registry).generate(_context())
    assert (
        normalization.value.code is SyntheticGeneratorErrorCode.NORMALIZATION_REJECTED
    )

    with pytest.raises(SyntheticGeneratorError) as validation:
        _generator(locks=_InvalidReferenceLockGenerator()).generate(_context())
    assert validation.value.code is SyntheticGeneratorErrorCode.DATA_VALIDATION_REJECTED


def test_no_planning_or_solver_import() -> None:
    module_root = ROOT / "backend" / "app" / "simulation" / "generators"
    imported_modules: set[str] = set()
    for path in sorted(module_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.add(node.module)
    forbidden = (
        "app.application",
        "app.planning",
        "app.snapshots",
        "ortools",
        "sqlalchemy",
    )
    assert not {
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden
        )
    }
