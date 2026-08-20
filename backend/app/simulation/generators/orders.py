"""Pure deterministic demand, production-order, and lot generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.domain.contracts import JsonValue
from app.simulation.generators.contracts import (
    GeneratedRecordCollections,
    GenerationContext,
    P1_GENERATOR_VERSION,
    SyntheticGeneratorError,
    SyntheticGeneratorErrorCode,
    require_p1_generator_context,
)
from app.simulation.generators.determinism import (
    SeedMaterial,
    format_synthetic_utc,
    synthetic_time_origin,
)


_DUE_HOURS_BY_PRESSURE = {"high": 6, "medium": 12, "low": 24}


@dataclass(frozen=True, slots=True)
class DeterministicOrderGenerator:
    """Create one demand/order/lot lineage for every generated route."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_orders(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        _, complexity, scale = require_p1_generator_context(context)
        routes = tuple(records.get("routing_versions", ()))
        if len(routes) != scale.order_count:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                "order layer requires one generated route per selected order",
            )
        seed_root = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        )
        seed = seed_root.child("orders")
        origin = synthetic_time_origin(seed_root.child("timeline"))
        due_hours = _DUE_HOURS_BY_PRESSURE[complexity.due_date_pressure]

        demands: list[dict[str, JsonValue]] = []
        orders: list[dict[str, JsonValue]] = []
        lots: list[dict[str, JsonValue]] = []
        for index, route in enumerate(routes):
            if not isinstance(route, dict):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "generated route records must be JSON objects",
                )
            product_id = route.get("product_id")
            route_id = route.get("routing_version_id")
            if not isinstance(product_id, str) or not isinstance(route_id, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "generated route record lacks product/routing identity",
                )
            demand_id = f"demand-order-{index + 1:03d}"
            order_id = f"production-order-{index + 1:03d}"
            quantity = 10 * seed.deterministic_integer(
                1, 5, "order-quantity-steps", index=index
            )
            release = origin + timedelta(hours=index * 2)
            due = release + timedelta(hours=due_hours)
            demands.append(
                {
                    "demand_order_id": demand_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "quantity_unit": "piece",
                    "due_at_utc": format_synthetic_utc(due),
                }
            )
            orders.append(
                {
                    "production_order_id": order_id,
                    "demand_order_id": demand_id,
                    "routing_version_id": route_id,
                    "quantity": quantity,
                    "quantity_unit": "piece",
                    "release_at_utc": format_synthetic_utc(release),
                    "material_ready_at_utc": format_synthetic_utc(release),
                }
            )
            lots.append(
                {
                    "production_lot_id": f"production-lot-{index + 1:03d}",
                    "production_order_id": order_id,
                    "quantity": quantity,
                    "quantity_unit": "piece",
                }
            )

        return {
            **records,
            "demand_orders": tuple(demands),
            "production_orders": tuple(orders),
            "production_lots": tuple(lots),
        }


__all__ = ["DeterministicOrderGenerator"]
