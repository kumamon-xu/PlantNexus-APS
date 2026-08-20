"""Layered synthetic generator contracts with a Standard Import boundary.

No protocol returns a PlanningSnapshot, PlanningProblem, Solver object, or
persistence model. P1 generation configuration is copied into frozen values so
that mutable JSON asset dictionaries cannot influence a running layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol, Self, TypedDict

from app.domain.capabilities import CapabilityName, require_v1_capability_contract
from app.domain.contracts import (
    ImportPackageDocument,
    ImportPackageDocumentV2,
    ImportQualityReportDocument,
    JsonValue,
)
from app.simulation.profiles.contracts import (
    FactoryProfileContractError,
    FactoryProfileDocument,
    IntegerRangeDocument,
    RatioRangeDocument,
    validate_factory_profile_contract,
)
from app.simulation.scenarios.contracts import (
    ScenarioManifestDocument,
    ScenarioSpecDocument,
    SimulationContractError,
    SimulationTarget,
    require_identity,
    require_seed,
    require_semver,
    require_simulation_target,
    validate_scenario_spec_contract,
)


P1_GENERATOR_ID = "PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR"
P1_GENERATOR_VERSION = "1.0.0"
P1_GENERATION_MANIFEST_VERSION = "synthetic-generation-manifest.v1"

type GeneratedRecordCollections = Mapping[str, Sequence[Mapping[str, JsonValue]]]


class SyntheticGeneratorErrorCode(StrEnum):
    """Stable generator-local failures before Snapshot/Solver semantics exist."""

    INVALID_PROFILE = "INVALID_SYNTHETIC_PROFILE"
    INVALID_SCENARIO = "INVALID_SYNTHETIC_SCENARIO"
    PROFILE_SCENARIO_MISMATCH = "PROFILE_SCENARIO_MISMATCH"
    GENERATOR_VERSION_MISMATCH = "GENERATOR_VERSION_MISMATCH"
    UNSUPPORTED_PROFILE_SHAPE = "UNSUPPORTED_PROFILE_SHAPE"
    NORMALIZATION_REJECTED = "SYNTHETIC_NORMALIZATION_REJECTED"
    DATA_VALIDATION_REJECTED = "SYNTHETIC_DATA_VALIDATION_REJECTED"
    PACKAGE_INVALID = "SYNTHETIC_PACKAGE_INVALID"


class SyntheticGeneratorError(ValueError):
    """A deterministic, sanitized P1 generation failure."""

    category = "DATA_ERROR"

    def __init__(self, code: SyntheticGeneratorErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{self.category}/{code.value}: {message}")


@dataclass(frozen=True, slots=True)
class IntegerRange:
    minimum: int
    maximum: int


@dataclass(frozen=True, slots=True)
class RatioRange:
    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class FrozenFactoryProfile:
    """Immutable projection of all FactoryProfile values consumed by P1."""

    workshop_count: IntegerRange
    production_line_count: IntegerRange
    resource_count: IntegerRange
    resource_capabilities: tuple[str, ...]
    operation_count: IntegerRange
    candidate_resource_count: IntegerRange
    routing_depth: IntegerRange
    cross_workshop_ratio: RatioRange
    calendar_pattern_ids: tuple[str, ...]
    calendar_fragmentation_count: IntegerRange
    order_count: IntegerRange
    due_date_pressure_levels: tuple[str, ...]
    supported_capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FrozenScenarioComplexity:
    """Immutable ScenarioSpec complexity values used by deterministic layers."""

    factory_size: str
    routing_complexity: str
    candidate_resource_density: str
    bottleneck_level: str
    due_date_pressure: str
    calendar_fragmentation: str
    material_delay_ratio: float
    wip_ratio: float
    lock_ratio: float
    cross_workshop_ratio: float
    failure_frequency: str


@dataclass(frozen=True, slots=True)
class GenerationScale:
    """Named-seed selections made once from versioned Profile ranges."""

    workshop_count: int
    production_line_count: int
    resource_count: int
    operation_count: int
    candidate_resource_minimum: int
    candidate_resource_maximum: int
    routing_depth: int
    calendar_fragmentation_count: int
    order_count: int


class ImportPackageReferenceDocumentV2(TypedDict):
    import_package_version: str
    schema_set_version: str
    package_id: str


class QualityReportReferenceDocument(TypedDict):
    report_version: str
    report_id: str
    status: str
    error_count: int


class SyntheticGenerationManifestDocument(TypedDict):
    """Generator-local P1 manifest; published ScenarioManifest v1 stays unchanged."""

    generation_manifest_version: str
    synthetic: bool
    target_environment: str
    scenario: dict[str, str]
    factory_profile: dict[str, str]
    generator: dict[str, str]
    seed: int
    required_capabilities: list[str]
    generated_at: str
    canonicalization_version: str
    normalization_rule_version: str
    unit_registry_version: str
    import_package: ImportPackageReferenceDocumentV2
    import_quality_report: QualityReportReferenceDocument
    dataset_hash: str


@dataclass(frozen=True, slots=True)
class GenerationContext:
    """All immutable inputs that can influence a deterministic generation result."""

    scenario_id: str
    scenario_version: str
    profile_id: str
    profile_version: str
    generator_id: str
    generator_version: str
    seed: int
    target: SimulationTarget
    required_capabilities: tuple[CapabilityName, ...]
    profile: FrozenFactoryProfile | None = None
    complexity: FrozenScenarioComplexity | None = None
    scale: GenerationScale | None = None

    @classmethod
    def create(
        cls,
        *,
        scenario_id: str,
        scenario_version: str,
        profile_id: str,
        profile_version: str,
        generator_id: str,
        generator_version: str,
        seed: int,
        target: SimulationTarget | str,
        required_capabilities: Sequence[CapabilityName | str] = (),
    ) -> Self:
        """Validate isolation, versions, seed, and capability declarations."""

        capabilities = require_v1_capability_contract(required_capabilities)
        return cls(
            scenario_id=require_identity(scenario_id, "scenario_id"),
            scenario_version=require_semver(scenario_version, "scenario_version"),
            profile_id=require_identity(profile_id, "profile_id"),
            profile_version=require_semver(profile_version, "profile_version"),
            generator_id=require_identity(generator_id, "generator_id"),
            generator_version=require_semver(generator_version, "generator_version"),
            seed=require_seed(seed),
            target=require_simulation_target(target),
            required_capabilities=tuple(
                sorted(capabilities, key=lambda capability: capability.value)
            ),
        )

    @classmethod
    def from_documents(
        cls,
        *,
        profile: FactoryProfileDocument,
        scenario: ScenarioSpecDocument,
        target: SimulationTarget | str,
    ) -> Self:
        """Build a frozen P1 context from the published Profile/Scenario contracts."""

        try:
            validate_factory_profile_contract(profile)
        except (FactoryProfileContractError, KeyError, TypeError) as error:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.INVALID_PROFILE,
                "FactoryProfile failed its published v1 contract",
            ) from error
        try:
            validate_scenario_spec_contract(scenario)
        except (SimulationContractError, KeyError, TypeError) as error:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.INVALID_SCENARIO,
                "ScenarioSpec failed its published v1 contract",
            ) from error

        profile_ref = scenario["factory_profile"]
        if (
            profile_ref["profile_id"] != profile["profile_id"]
            or profile_ref["profile_version"] != profile["profile_version"]
        ):
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PROFILE_SCENARIO_MISMATCH,
                "ScenarioSpec does not reference the supplied FactoryProfile",
            )

        generator = scenario["generator"]
        base = cls.create(
            scenario_id=scenario["scenario_id"],
            scenario_version=scenario["scenario_version"],
            profile_id=profile["profile_id"],
            profile_version=profile["profile_version"],
            generator_id=generator["generator_id"],
            generator_version=generator["generator_version"],
            seed=scenario["seed"],
            target=target,
            required_capabilities=scenario["required_capabilities"],
        )
        profile_projection = _freeze_profile(profile)
        complexity = _freeze_complexity(scenario)
        _validate_profile_scenario_semantics(base, profile_projection, complexity)
        scale = _select_scale(base, profile_projection)
        _validate_scale(base, scale)
        return replace(
            base,
            profile=profile_projection,
            complexity=complexity,
            scale=scale,
        )

    def require_p1_configuration(
        self,
    ) -> tuple[FrozenFactoryProfile, FrozenScenarioComplexity, GenerationScale]:
        """Return P1 values or reject a P0 metadata-only context explicitly."""

        if self.profile is None or self.complexity is None or self.scale is None:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.INVALID_SCENARIO,
                "non-empty generation requires a Profile/Scenario document context",
            )
        return self.profile, self.complexity, self.scale


@dataclass(frozen=True, slots=True)
class GeneratedScenarioPackage:
    """Canonical dataset plus its non-hashed run manifest and quality evidence."""

    import_package: ImportPackageDocument | ImportPackageDocumentV2
    manifest: ScenarioManifestDocument | SyntheticGenerationManifestDocument
    canonical_dataset: bytes
    dataset_hash: str
    quality_report: ImportQualityReportDocument | None = None


def require_p1_generator_context(
    context: GenerationContext,
) -> tuple[FrozenFactoryProfile, FrozenScenarioComplexity, GenerationScale]:
    """Require the exact implemented generator identity before any layer runs."""

    if (
        context.generator_id != P1_GENERATOR_ID
        or context.generator_version != P1_GENERATOR_VERSION
    ):
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.GENERATOR_VERSION_MISMATCH,
            "context does not select the implemented P1 generator identity/version",
        )
    return context.require_p1_configuration()


def _integer_range(document: IntegerRangeDocument) -> IntegerRange:
    return IntegerRange(document["minimum"], document["maximum"])


def _ratio_range(document: RatioRangeDocument) -> RatioRange:
    return RatioRange(float(document["minimum"]), float(document["maximum"]))


def _freeze_profile(profile: FactoryProfileDocument) -> FrozenFactoryProfile:
    return FrozenFactoryProfile(
        workshop_count=_integer_range(profile["topology"]["workshop_count"]),
        production_line_count=_integer_range(
            profile["topology"]["production_line_count"]
        ),
        resource_count=_integer_range(profile["resources"]["target_count"]),
        resource_capabilities=tuple(sorted(profile["resources"]["capability_pool"])),
        operation_count=_integer_range(profile["routing"]["operation_count"]),
        candidate_resource_count=_integer_range(
            profile["routing"]["candidate_resource_count"]
        ),
        routing_depth=_integer_range(profile["routing"]["routing_depth"]),
        cross_workshop_ratio=_ratio_range(profile["routing"]["cross_workshop_ratio"]),
        calendar_pattern_ids=tuple(sorted(profile["calendar"]["pattern_ids"])),
        calendar_fragmentation_count=_integer_range(
            profile["calendar"]["fragmentation_count"]
        ),
        order_count=_integer_range(profile["orders"]["order_count"]),
        due_date_pressure_levels=tuple(
            sorted(profile["orders"]["due_date_pressure_levels"])
        ),
        supported_capabilities=tuple(sorted(profile["supported_capabilities"])),
    )


def _freeze_complexity(scenario: ScenarioSpecDocument) -> FrozenScenarioComplexity:
    complexity = scenario["complexity"]
    return FrozenScenarioComplexity(
        factory_size=complexity["factory_size"],
        routing_complexity=complexity["routing_complexity"],
        candidate_resource_density=complexity["candidate_resource_density"],
        bottleneck_level=complexity["bottleneck_level"],
        due_date_pressure=complexity["due_date_pressure"],
        calendar_fragmentation=complexity["calendar_fragmentation"],
        material_delay_ratio=float(complexity["material_delay_ratio"]),
        wip_ratio=float(complexity["wip_ratio"]),
        lock_ratio=float(complexity["lock_ratio"]),
        cross_workshop_ratio=float(complexity["cross_workshop_ratio"]),
        failure_frequency=complexity["failure_frequency"],
    )


def _validate_profile_scenario_semantics(
    context: GenerationContext,
    profile: FrozenFactoryProfile,
    complexity: FrozenScenarioComplexity,
) -> None:
    if not profile.resource_capabilities:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.UNSUPPORTED_PROFILE_SHAPE,
            "generator v1 requires a non-empty resource capability pool",
        )
    required = {capability.value for capability in context.required_capabilities}
    if not required.issubset(profile.supported_capabilities):
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PROFILE_SCENARIO_MISMATCH,
            "Scenario capabilities are not all supported by the supplied Profile",
        )
    if complexity.due_date_pressure not in profile.due_date_pressure_levels:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PROFILE_SCENARIO_MISMATCH,
            "Scenario due-date pressure is outside the Profile declaration",
        )
    ratio = complexity.cross_workshop_ratio
    if (
        not profile.cross_workshop_ratio.minimum
        <= ratio
        <= profile.cross_workshop_ratio.maximum
    ):
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PROFILE_SCENARIO_MISMATCH,
            "Scenario cross-workshop ratio is outside the Profile range",
        )


def _select_scale(
    context: GenerationContext, profile: FrozenFactoryProfile
) -> GenerationScale:
    from app.simulation.generators.determinism import SeedMaterial

    seed = SeedMaterial(
        root_seed=context.seed,
        generator_id=context.generator_id,
        generator_version=context.generator_version,
    ).child("profile-selection")
    resources = seed.deterministic_integer(
        profile.resource_count.minimum,
        profile.resource_count.maximum,
        "resource-count",
    )
    candidate_maximum = min(profile.candidate_resource_count.maximum, resources)
    return GenerationScale(
        workshop_count=seed.deterministic_integer(
            profile.workshop_count.minimum,
            profile.workshop_count.maximum,
            "workshop-count",
        ),
        production_line_count=seed.deterministic_integer(
            profile.production_line_count.minimum,
            profile.production_line_count.maximum,
            "production-line-count",
        ),
        resource_count=resources,
        operation_count=seed.deterministic_integer(
            profile.operation_count.minimum,
            profile.operation_count.maximum,
            "operation-count",
        ),
        candidate_resource_minimum=profile.candidate_resource_count.minimum,
        candidate_resource_maximum=candidate_maximum,
        routing_depth=seed.deterministic_integer(
            profile.routing_depth.minimum,
            profile.routing_depth.maximum,
            "routing-depth",
        ),
        calendar_fragmentation_count=seed.deterministic_integer(
            profile.calendar_fragmentation_count.minimum,
            profile.calendar_fragmentation_count.maximum,
            "calendar-fragmentation-count",
        ),
        order_count=seed.deterministic_integer(
            profile.order_count.minimum,
            profile.order_count.maximum,
            "order-count",
        ),
    )


def _validate_scale(context: GenerationContext, scale: GenerationScale) -> None:
    required = {capability.value for capability in context.required_capabilities}
    if scale.candidate_resource_minimum > scale.resource_count:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.UNSUPPORTED_PROFILE_SHAPE,
            "candidate-resource minimum exceeds the selected resource count",
        )
    if scale.routing_depth != scale.operation_count:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.UNSUPPORTED_PROFILE_SHAPE,
            "generator v1 requires routing_depth to equal operation_count",
        )
    if "ALTERNATIVE_RESOURCE" in required and scale.candidate_resource_maximum < 2:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.UNSUPPORTED_PROFILE_SHAPE,
            "ALTERNATIVE_RESOURCE requires at least two candidate resources",
        )
    if "SINGLE_FACTORY_MULTI_WORKSHOP" in required and scale.workshop_count < 2:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.UNSUPPORTED_PROFILE_SHAPE,
            "SINGLE_FACTORY_MULTI_WORKSHOP requires at least two workshops",
        )


class TopologyGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_topology(
        self, context: GenerationContext
    ) -> GeneratedRecordCollections: ...


class RoutingGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_routings(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections: ...


class OrderGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_orders(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections: ...


class CalendarGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_calendars(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections: ...


class MaterialGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_material_readiness(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections: ...


class ExecutionStateGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_execution_states(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections: ...


class LockGenerator(Protocol):
    @property
    def generator_version(self) -> str: ...

    def generate_locks(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections: ...


class SyntheticPackageGenerator(Protocol):
    """A full generator still terminates at Standard Import, never Problem."""

    @property
    def generator_version(self) -> str: ...

    def generate(self, context: GenerationContext) -> GeneratedScenarioPackage: ...


__all__ = [
    "CalendarGenerator",
    "ExecutionStateGenerator",
    "FrozenFactoryProfile",
    "FrozenScenarioComplexity",
    "GeneratedRecordCollections",
    "GeneratedScenarioPackage",
    "GenerationContext",
    "GenerationScale",
    "IntegerRange",
    "LockGenerator",
    "MaterialGenerator",
    "OrderGenerator",
    "P1_GENERATION_MANIFEST_VERSION",
    "P1_GENERATOR_ID",
    "P1_GENERATOR_VERSION",
    "QualityReportReferenceDocument",
    "RatioRange",
    "RoutingGenerator",
    "SyntheticGenerationManifestDocument",
    "SyntheticGeneratorError",
    "SyntheticGeneratorErrorCode",
    "SyntheticPackageGenerator",
    "TopologyGenerator",
    "require_p1_generator_context",
]
