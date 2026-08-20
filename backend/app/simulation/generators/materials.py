"""Pure deterministic material-readiness augmentation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

from app.domain.contracts import JsonValue
from app.domain.types import ContractValueError, parse_utc_instant
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
)


@dataclass(frozen=True, slots=True)
class DeterministicMaterialGenerator:
    """Delay a deterministic quota of orders according to ScenarioSpec ratio."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_material_readiness(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        _, complexity, scale = require_p1_generator_context(context)
        source_orders = tuple(records.get("production_orders", ()))
        if len(source_orders) != scale.order_count:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                "material layer requires the complete production-order collection",
            )
        seed = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        ).child("materials")
        delayed = seed.selected_positions(
            len(source_orders), complexity.material_delay_ratio, "delayed-orders"
        )
        orders: list[dict[str, JsonValue]] = []
        for index, source_order in enumerate(source_orders):
            if not isinstance(source_order, Mapping):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production-order source record must be a JSON object",
                )
            release_text = source_order.get("release_at_utc")
            if not isinstance(release_text, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production-order source record lacks release_at_utc",
                )
            try:
                release = parse_utc_instant(release_text)
            except ContractValueError as error:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production-order release time is invalid",
                ) from error
            ready = release + (
                timedelta(minutes=90) if index in delayed else timedelta()
            )
            updated = dict(source_order)
            updated["material_ready_at_utc"] = format_synthetic_utc(ready)
            orders.append(updated)
        return {**records, "production_orders": tuple(orders)}


__all__ = ["DeterministicMaterialGenerator"]
