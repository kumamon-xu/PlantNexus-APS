"""Layered synthetic generator protocols with a Standard Import output boundary.

No protocol returns a PlanningProblem, Solver object, or persistence model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, Self

from app.domain.capabilities import CapabilityName, require_v1_capability_contract
from app.domain.contracts import ImportPackageDocument, JsonValue
from app.simulation.scenarios.contracts import (
    ScenarioManifestDocument,
    SimulationTarget,
    require_identity,
    require_seed,
    require_semver,
    require_simulation_target,
)


type GeneratedRecordCollections = Mapping[
    str, Sequence[Mapping[str, JsonValue]]
]


@dataclass(frozen=True, slots=True)
class GenerationContext:
    """All inputs that can influence a deterministic generation result."""

    scenario_id: str
    scenario_version: str
    profile_id: str
    profile_version: str
    generator_id: str
    generator_version: str
    seed: int
    target: SimulationTarget
    required_capabilities: tuple[CapabilityName, ...]

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


@dataclass(frozen=True, slots=True)
class GeneratedScenarioPackage:
    """Canonical dataset plus its non-hashed run manifest."""

    import_package: ImportPackageDocument
    manifest: ScenarioManifestDocument
    canonical_dataset: bytes
    dataset_hash: str


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
    "GeneratedRecordCollections",
    "GeneratedScenarioPackage",
    "GenerationContext",
    "LockGenerator",
    "MaterialGenerator",
    "OrderGenerator",
    "RoutingGenerator",
    "SyntheticPackageGenerator",
    "TopologyGenerator",
]
