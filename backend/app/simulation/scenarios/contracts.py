"""Pure ScenarioSpec v1, manifest v1, and environment isolation contracts."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal, NotRequired, TypedDict

from app.domain.capabilities import CapabilityName
from app.domain.types import ContractValueError, canonical_id, parse_utc_instant


MAX_SEED = (1 << 63) - 1
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_DATASET_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SimulationContractCode(StrEnum):
    INVALID_IDENTITY = "INVALID_SIMULATION_IDENTITY"
    INVALID_VERSION = "INVALID_SIMULATION_VERSION"
    INVALID_SEED = "INVALID_SIMULATION_SEED"
    INVALID_PROVENANCE = "INVALID_SIMULATION_PROVENANCE"
    INVALID_TARGET_ENVIRONMENT = "INVALID_SIMULATION_TARGET"
    PRODUCTION_TARGET_FORBIDDEN = "SYNTHETIC_REFERENCE_IN_PRODUCTION"


class SimulationContractError(ValueError):
    """A Simulation contract fails with a stable, testable error code."""

    def __init__(self, code: SimulationContractCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")


class SimulationTarget(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    BENCHMARK = "benchmark"


class FactoryProfileReferenceDocument(TypedDict):
    profile_id: str
    profile_version: str


class ScenarioReferenceDocument(TypedDict):
    scenario_id: str
    scenario_version: str


class GeneratorReferenceDocument(TypedDict):
    generator_id: str
    generator_version: str


class ComplexityDocument(TypedDict):
    factory_size: Literal["XS", "S", "M", "L", "XL"]
    routing_complexity: Literal["low", "medium", "high"]
    candidate_resource_density: Literal["sparse", "medium", "dense"]
    bottleneck_level: Literal["low", "medium", "high"]
    due_date_pressure: Literal["low", "medium", "high"]
    calendar_fragmentation: Literal["low", "medium", "high"]
    material_delay_ratio: float
    wip_ratio: float
    lock_ratio: float
    cross_workshop_ratio: float
    failure_frequency: Literal["none", "low", "medium", "high"]


type ScenarioResult = Literal[
    "OPTIMAL",
    "FEASIBLE",
    "INFEASIBLE",
    "NO_SOLUTION_WITHIN_LIMIT",
    "MODEL_INVALID",
    "DATA_REJECTED",
    "VALIDATION_FAILED",
    "CANCELLED",
    "FAILED",
    "UNSUPPORTED_CAPABILITY",
]


class ExpectedBehaviorDocument(TypedDict):
    allowed_results: list[ScenarioResult]
    validator_status: NotRequired[Literal["PASS", "FAIL"]]


class ScenarioSpecDocument(TypedDict):
    scenario_contract_version: Literal["scenario-spec.v1"]
    scenario_id: str
    scenario_version: str
    synthetic_only: Literal[True]
    factory_profile: FactoryProfileReferenceDocument
    generator: GeneratorReferenceDocument
    seed: int
    required_capabilities: list[str]
    complexity: ComplexityDocument
    expected_behavior: ExpectedBehaviorDocument


class ImportPackageReferenceDocument(TypedDict):
    import_package_version: Literal["import-package.v1"]
    package_id: str


class ScenarioManifestDocument(TypedDict):
    scenario_manifest_version: Literal["scenario-manifest.v1"]
    synthetic: Literal[True]
    target_environment: Literal["development", "test", "benchmark"]
    scenario: ScenarioReferenceDocument
    factory_profile: FactoryProfileReferenceDocument
    generator: GeneratorReferenceDocument
    seed: int
    required_capabilities: list[str]
    generated_at: str
    canonicalization_version: Literal["canonical-json.v1"]
    import_package: ImportPackageReferenceDocument
    dataset_hash: str


def require_semver(value: str, location: str) -> str:
    if not isinstance(value, str) or _SEMVER_RE.fullmatch(value) is None:
        raise SimulationContractError(
            SimulationContractCode.INVALID_VERSION,
            f"{location} must be semantic version text",
        )
    return value


def require_identity(value: str, location: str) -> str:
    try:
        return str(canonical_id(value))
    except ContractValueError as error:
        raise SimulationContractError(
            SimulationContractCode.INVALID_IDENTITY,
            f"{location}: {error}",
        ) from error


def require_seed(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SEED:
        raise SimulationContractError(
            SimulationContractCode.INVALID_SEED,
            f"seed must be an integer from 0 through {MAX_SEED}",
        )
    return value


def require_simulation_target(value: SimulationTarget | str) -> SimulationTarget:
    raw_value = str(value)
    if raw_value == "production":
        raise SimulationContractError(
            SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN,
            "synthetic generation cannot target Production",
        )
    try:
        return SimulationTarget(raw_value)
    except ValueError as error:
        raise SimulationContractError(
            SimulationContractCode.INVALID_TARGET_ENVIRONMENT,
            f"unknown target environment: {raw_value}",
        ) from error


def _require_capability_declarations(values: list[str]) -> tuple[CapabilityName, ...]:
    if len(values) != len(set(values)):
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "required_capabilities contains duplicates",
        )
    try:
        return tuple(CapabilityName(value) for value in values)
    except ValueError as error:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "required_capabilities contains an unregistered capability",
        ) from error


def validate_scenario_spec_contract(scenario: ScenarioSpecDocument) -> None:
    if scenario["scenario_contract_version"] != "scenario-spec.v1":
        raise SimulationContractError(
            SimulationContractCode.INVALID_VERSION,
            "unexpected ScenarioSpec contract version",
        )
    if scenario["synthetic_only"] is not True:
        raise SimulationContractError(
            SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN,
            "ScenarioSpec must be synthetic_only=true",
        )
    require_identity(scenario["scenario_id"], "scenario_id")
    require_semver(scenario["scenario_version"], "scenario_version")
    require_identity(scenario["factory_profile"]["profile_id"], "profile_id")
    require_semver(
        scenario["factory_profile"]["profile_version"], "profile_version"
    )
    require_identity(scenario["generator"]["generator_id"], "generator_id")
    require_semver(
        scenario["generator"]["generator_version"], "generator_version"
    )
    require_seed(scenario["seed"])
    _require_capability_declarations(scenario["required_capabilities"])
    ratios = {
        "material_delay_ratio": scenario["complexity"]["material_delay_ratio"],
        "wip_ratio": scenario["complexity"]["wip_ratio"],
        "lock_ratio": scenario["complexity"]["lock_ratio"],
        "cross_workshop_ratio": scenario["complexity"]["cross_workshop_ratio"],
    }
    for name, value in ratios.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise SimulationContractError(
                SimulationContractCode.INVALID_PROVENANCE,
                f"complexity.{name} must be between 0 and 1",
            )
    results = scenario["expected_behavior"]["allowed_results"]
    if not results or len(results) != len(set(results)):
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "expected allowed_results must be non-empty and unique",
        )


def validate_scenario_manifest_contract(manifest: ScenarioManifestDocument) -> None:
    if manifest["scenario_manifest_version"] != "scenario-manifest.v1":
        raise SimulationContractError(
            SimulationContractCode.INVALID_VERSION,
            "unexpected ScenarioManifest contract version",
        )
    if manifest["synthetic"] is not True:
        raise SimulationContractError(
            SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN,
            "ScenarioManifest must be synthetic=true",
        )
    require_simulation_target(manifest["target_environment"])
    require_identity(manifest["scenario"]["scenario_id"], "scenario_id")
    require_semver(manifest["scenario"]["scenario_version"], "scenario_version")
    require_identity(manifest["factory_profile"]["profile_id"], "profile_id")
    require_semver(
        manifest["factory_profile"]["profile_version"], "profile_version"
    )
    require_identity(manifest["generator"]["generator_id"], "generator_id")
    require_semver(
        manifest["generator"]["generator_version"], "generator_version"
    )
    require_seed(manifest["seed"])
    _require_capability_declarations(manifest["required_capabilities"])
    try:
        parse_utc_instant(manifest["generated_at"])
    except ContractValueError as error:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            str(error),
        ) from error
    if manifest["canonicalization_version"] != "canonical-json.v1":
        raise SimulationContractError(
            SimulationContractCode.INVALID_VERSION,
            "unexpected canonicalization version",
        )
    if manifest["import_package"]["import_package_version"] != "import-package.v1":
        raise SimulationContractError(
            SimulationContractCode.INVALID_VERSION,
            "unexpected import package version",
        )
    require_identity(manifest["import_package"]["package_id"], "package_id")
    if _DATASET_HASH_RE.fullmatch(manifest["dataset_hash"]) is None:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "dataset_hash must be lowercase sha256:<64 hex>",
        )


__all__ = [
    "MAX_SEED",
    "ScenarioManifestDocument",
    "ScenarioSpecDocument",
    "SimulationContractCode",
    "SimulationContractError",
    "SimulationTarget",
    "require_identity",
    "require_seed",
    "require_semver",
    "require_simulation_target",
    "validate_scenario_manifest_contract",
    "validate_scenario_spec_contract",
]
