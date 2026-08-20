"""Pure deterministic product, routing DAG, and resource-option generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts import JsonValue
from app.simulation.generators.contracts import (
    GeneratedRecordCollections,
    GenerationContext,
    P1_GENERATOR_VERSION,
    SyntheticGeneratorError,
    SyntheticGeneratorErrorCode,
    require_p1_generator_context,
)
from app.simulation.generators.determinism import SeedMaterial


def _record_id(record: object, field: str) -> str:
    if not isinstance(record, dict) or not isinstance(record.get(field), str):
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PACKAGE_INVALID,
            f"upstream generated collection is missing {field}",
        )
    return record[field]


@dataclass(frozen=True, slots=True)
class DeterministicRoutingGenerator:
    """Create one chain DAG per Profile-sized synthetic demand lineage."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_routings(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        profile, complexity, scale = require_p1_generator_context(context)
        seed = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        ).child("routing")
        resources = tuple(records.get("resources", ()))
        if len(resources) != scale.resource_count:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                "routing layer requires the complete generated resource collection",
            )
        resource_ids = tuple(_record_id(record, "resource_id") for record in resources)

        products: list[dict[str, JsonValue]] = []
        routing_versions: list[dict[str, JsonValue]] = []
        operations: list[dict[str, JsonValue]] = []
        edges: list[dict[str, JsonValue]] = []
        options: list[dict[str, JsonValue]] = []
        edge_count = scale.order_count * max(scale.operation_count - 1, 0)
        cross_workshop_edges = seed.selected_positions(
            edge_count, complexity.cross_workshop_ratio, "cross-workshop-edges"
        )
        edge_position = 0

        for route_index in range(scale.order_count):
            product_id = f"product-{route_index + 1:03d}"
            route_id = f"routing-version-{route_index + 1:03d}"
            products.append(
                {
                    "product_id": product_id,
                    "product_code": f"SYNTHETIC-PRODUCT-{route_index + 1:03d}",
                    "quantity_unit": "piece",
                }
            )
            routing_versions.append(
                {
                    "routing_version_id": route_id,
                    "routing_code": f"SYNTHETIC-ROUTING-{route_index + 1:03d}",
                    "version": "1.0.0",
                    "product_id": product_id,
                }
            )
            for operation_index in range(scale.operation_count):
                operation_id = (
                    f"routing-operation-{route_index + 1:03d}-{operation_index + 1:03d}"
                )
                capability_index = seed.deterministic_index(
                    len(profile.resource_capabilities),
                    "operation-capability",
                    index=route_index * scale.operation_count + operation_index,
                )
                operations.append(
                    {
                        "routing_operation_id": operation_id,
                        "routing_version_id": route_id,
                        "operation_code": (
                            f"SYNTHETIC-OP-{route_index + 1:03d}-"
                            f"{operation_index + 1:03d}"
                        ),
                        "required_capabilities": [
                            profile.resource_capabilities[capability_index]
                        ],
                    }
                )

                option_index = route_index * scale.operation_count + operation_index
                candidate_count = seed.deterministic_integer(
                    scale.candidate_resource_minimum,
                    scale.candidate_resource_maximum,
                    "candidate-count",
                    index=option_index,
                )
                resource_order = seed.child(
                    f"operation-{option_index + 1:06d}"
                ).deterministic_order(len(resource_ids), "candidate-order")
                for candidate_index, resource_position in enumerate(
                    resource_order[:candidate_count]
                ):
                    setup_seconds = 300 * seed.deterministic_integer(
                        0,
                        2,
                        "setup-steps",
                        index=option_index * len(resource_ids) + candidate_index,
                    )
                    cycle_seconds = 300 * seed.deterministic_integer(
                        1,
                        3,
                        "cycle-steps",
                        index=option_index * len(resource_ids) + candidate_index,
                    )
                    options.append(
                        {
                            "routing_resource_option_id": (
                                f"routing-option-{route_index + 1:03d}-"
                                f"{operation_index + 1:03d}-"
                                f"{candidate_index + 1:03d}"
                            ),
                            "routing_operation_id": operation_id,
                            "resource_id": resource_ids[resource_position],
                            "quantity_unit": "piece",
                            "setup_seconds": setup_seconds,
                            "setup_unit": "s",
                            "cycle_seconds_per_unit": cycle_seconds,
                            "cycle_unit": "s",
                            "final_duration_seconds": setup_seconds + cycle_seconds,
                            "final_duration_unit": "s",
                            "duration_source": context.generator_id,
                            "duration_source_version": context.generator_version,
                        }
                    )

                if operation_index == 0:
                    continue
                predecessor_id = (
                    f"routing-operation-{route_index + 1:03d}-{operation_index:03d}"
                )
                transport_seconds = 600 if edge_position in cross_workshop_edges else 0
                edges.append(
                    {
                        "routing_precedence_edge_id": (
                            f"routing-edge-{route_index + 1:03d}-{operation_index:03d}"
                        ),
                        "routing_version_id": route_id,
                        "predecessor_routing_operation_id": predecessor_id,
                        "successor_routing_operation_id": operation_id,
                        "min_lag_seconds": 0,
                        "min_lag_unit": "s",
                        "transport_lag_seconds": transport_seconds,
                        "transport_lag_unit": "s",
                    }
                )
                edge_position += 1

        return {
            **records,
            "products": tuple(products),
            "routing_versions": tuple(routing_versions),
            "routing_operations": tuple(operations),
            "routing_precedence_edges": tuple(edges),
            "routing_resource_options": tuple(options),
        }


__all__ = ["DeterministicRoutingGenerator"]
