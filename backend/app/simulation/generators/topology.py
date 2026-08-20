"""Pure deterministic topology and resource source-record generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts import JsonValue
from app.simulation.generators.contracts import (
    GeneratedRecordCollections,
    GenerationContext,
    P1_GENERATOR_VERSION,
    require_p1_generator_context,
)
from app.simulation.generators.determinism import SeedMaterial


@dataclass(frozen=True, slots=True)
class DeterministicTopologyGenerator:
    """Create one factory plus Profile-sized workshop/resource topology."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_topology(
        self, context: GenerationContext
    ) -> GeneratedRecordCollections:
        profile, _, scale = require_p1_generator_context(context)
        seed = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        ).child("topology")

        factories: list[dict[str, JsonValue]] = [
            {
                "factory_id": "factory-001",
                "factory_code": "SYNTHETIC-FACTORY-001",
                "factory_timezone": "UTC",
            }
        ]
        workshops: list[dict[str, JsonValue]] = [
            {
                "workshop_id": f"workshop-{index + 1:03d}",
                "workshop_code": f"SYNTHETIC-WORKSHOP-{index + 1:03d}",
                "factory_id": "factory-001",
            }
            for index in range(scale.workshop_count)
        ]

        workshop_order = seed.deterministic_order(
            scale.workshop_count, "line-workshop-order"
        )
        production_lines: list[dict[str, JsonValue]] = []
        resource_groups: list[dict[str, JsonValue]] = []
        for index in range(scale.production_line_count):
            line_id = f"production-line-{index + 1:03d}"
            workshop_index = workshop_order[index % len(workshop_order)]
            production_lines.append(
                {
                    "production_line_id": line_id,
                    "production_line_code": (
                        f"SYNTHETIC-PRODUCTION-LINE-{index + 1:03d}"
                    ),
                    "workshop_id": f"workshop-{workshop_index + 1:03d}",
                }
            )
            resource_groups.append(
                {
                    "resource_group_id": f"resource-group-{index + 1:03d}",
                    "resource_group_code": (
                        f"SYNTHETIC-RESOURCE-GROUP-{index + 1:03d}"
                    ),
                    "production_line_id": line_id,
                }
            )

        group_order = seed.deterministic_order(
            scale.production_line_count, "resource-group-order"
        )
        capabilities: list[JsonValue] = list(profile.resource_capabilities)
        resources: list[dict[str, JsonValue]] = []
        for index in range(scale.resource_count):
            group_index = group_order[index % len(group_order)]
            resources.append(
                {
                    "resource_id": f"resource-{index + 1:03d}",
                    "resource_code": f"SYNTHETIC-RESOURCE-{index + 1:03d}",
                    "resource_type": "UNIT_CAPACITY_MACHINE",
                    "status": "ACTIVE",
                    "resource_group_id": f"resource-group-{group_index + 1:03d}",
                    "calendar_id": f"calendar-resource-{index + 1:03d}",
                    "capabilities": capabilities.copy(),
                }
            )

        return {
            "factories": tuple(factories),
            "workshops": tuple(workshops),
            "production_lines": tuple(production_lines),
            "resource_groups": tuple(resource_groups),
            "resources": tuple(resources),
        }


__all__ = ["DeterministicTopologyGenerator"]
