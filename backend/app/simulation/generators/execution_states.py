"""Pure deterministic current-execution source-record generation."""

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


def _object_map(
    records: GeneratedRecordCollections, collection: str, identity: str
) -> dict[str, Mapping[str, JsonValue]]:
    result: dict[str, Mapping[str, JsonValue]] = {}
    for record in records.get(collection, ()):
        if not isinstance(record, Mapping) or not isinstance(record.get(identity), str):
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                f"{collection} source record lacks {identity}",
            )
        result[str(record[identity])] = record
    return result


@dataclass(frozen=True, slots=True)
class DeterministicExecutionStateGenerator:
    """Emit RUNNING facts for the ScenarioSpec WIP quota only."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_execution_states(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        _, complexity, scale = require_p1_generator_context(context)
        lots = tuple(records.get("production_lots", ()))
        if len(lots) != scale.order_count:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                "execution layer requires the complete production-lot collection",
            )
        seed = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        ).child("execution-states")
        running_positions = seed.selected_positions(
            len(lots), complexity.wip_ratio, "running-lots"
        )
        orders = _object_map(records, "production_orders", "production_order_id")
        operations_by_route: dict[str, list[Mapping[str, JsonValue]]] = {}
        for operation in records.get("routing_operations", ()):
            if not isinstance(operation, Mapping) or not isinstance(
                operation.get("routing_version_id"), str
            ):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "routing operation lacks routing_version_id",
                )
            operations_by_route.setdefault(
                str(operation["routing_version_id"]), []
            ).append(operation)
        options_by_operation: dict[str, list[Mapping[str, JsonValue]]] = {}
        for option in records.get("routing_resource_options", ()):
            if not isinstance(option, Mapping) or not isinstance(
                option.get("routing_operation_id"), str
            ):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "routing option lacks routing_operation_id",
                )
            options_by_operation.setdefault(
                str(option["routing_operation_id"]), []
            ).append(option)

        facts: list[dict[str, JsonValue]] = []
        for index in sorted(running_positions):
            lot = lots[index]
            if not isinstance(lot, Mapping):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production-lot source record must be a JSON object",
                )
            order_id = lot.get("production_order_id")
            lot_id = lot.get("production_lot_id")
            quantity = lot.get("quantity")
            if (
                not isinstance(order_id, str)
                or not isinstance(lot_id, str)
                or isinstance(quantity, bool)
                or not isinstance(quantity, (int, float))
            ):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production-lot lineage or quantity is invalid",
                )
            order = orders.get(order_id)
            if order is None or not isinstance(order.get("routing_version_id"), str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production order lacks its generated routing version",
                )
            route_id = str(order["routing_version_id"])
            route_operations = sorted(
                operations_by_route.get(route_id, ()),
                key=lambda value: str(value.get("routing_operation_id", "")),
            )
            if not route_operations:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "running lot has no generated routing operation",
                )
            operation_id = route_operations[0].get("routing_operation_id")
            if not isinstance(operation_id, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "generated routing operation identity is invalid",
                )
            route_options = sorted(
                options_by_operation.get(operation_id, ()),
                key=lambda value: str(value.get("routing_resource_option_id", "")),
            )
            if not route_options:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "running operation has no generated resource option",
                )
            option = route_options[0]
            resource_id = option.get("resource_id")
            remaining_seconds = option.get("final_duration_seconds")
            material_ready_text = order.get("material_ready_at_utc")
            if (
                not isinstance(resource_id, str)
                or isinstance(remaining_seconds, bool)
                or not isinstance(remaining_seconds, int)
                or not isinstance(material_ready_text, str)
            ):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "running operation source values are invalid",
                )
            try:
                material_ready = parse_utc_instant(material_ready_text)
            except ContractValueError as error:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "material-ready time is invalid",
                ) from error
            actual_start = material_ready + timedelta(minutes=30)
            observed = actual_start + timedelta(minutes=15)
            remaining_quantity = max(1, int(quantity) // 2)
            facts.append(
                {
                    "execution_fact_id": f"execution-fact-{index + 1:03d}",
                    "production_lot_id": lot_id,
                    "routing_operation_id": operation_id,
                    "status": "RUNNING",
                    "observed_at_utc": format_synthetic_utc(observed),
                    "quantity_unit": "piece",
                    "resource_id": resource_id,
                    "actual_start_at_utc": format_synthetic_utc(actual_start),
                    "remaining_quantity": remaining_quantity,
                    "remaining_seconds": remaining_seconds,
                    "remaining_unit": "s",
                }
            )
        return {**records, "execution_facts": tuple(facts)}


__all__ = ["DeterministicExecutionStateGenerator"]
