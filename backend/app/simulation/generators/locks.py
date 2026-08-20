"""Pure deterministic operation-lock source-record generation."""

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
class DeterministicLockGenerator:
    """Emit one HARD/SOFT lock for the ScenarioSpec lock quota."""

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate_locks(
        self,
        context: GenerationContext,
        records: GeneratedRecordCollections,
    ) -> GeneratedRecordCollections:
        _, complexity, scale = require_p1_generator_context(context)
        lots = tuple(records.get("production_lots", ()))
        if len(lots) != scale.order_count:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                "lock layer requires the complete production-lot collection",
            )
        seed = SeedMaterial(
            context.seed, context.generator_id, context.generator_version
        ).child("locks")
        locked_positions = seed.selected_positions(
            len(lots), complexity.lock_ratio, "locked-lots"
        )
        orders: dict[str, Mapping[str, JsonValue]] = {}
        for order in records.get("production_orders", ()):
            if not isinstance(order, Mapping) or not isinstance(
                order.get("production_order_id"), str
            ):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production order lacks production_order_id",
                )
            orders[str(order["production_order_id"])] = order
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

        locks: list[dict[str, JsonValue]] = []
        for index in sorted(locked_positions):
            lot = lots[index]
            if not isinstance(lot, Mapping):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production lot must be a JSON object",
                )
            lot_id = lot.get("production_lot_id")
            order_id = lot.get("production_order_id")
            if not isinstance(lot_id, str) or not isinstance(order_id, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "production lot lineage is invalid",
                )
            order = orders.get(order_id)
            if order is None or not isinstance(order.get("routing_version_id"), str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "locked lot has no generated route",
                )
            route_operations = sorted(
                operations_by_route.get(str(order["routing_version_id"]), ()),
                key=lambda value: str(value.get("routing_operation_id", "")),
            )
            if not route_operations:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "locked lot has no generated routing operation",
                )
            operation_id = route_operations[-1].get("routing_operation_id")
            if not isinstance(operation_id, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "lock operation identity is invalid",
                )
            options = sorted(
                options_by_operation.get(operation_id, ()),
                key=lambda value: str(value.get("routing_resource_option_id", "")),
            )
            if not options or not isinstance(options[0].get("resource_id"), str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "locked operation has no valid resource option",
                )
            ready_text = order.get("material_ready_at_utc")
            if not isinstance(ready_text, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "locked order lacks material-ready time",
                )
            try:
                ready = parse_utc_instant(ready_text)
            except ContractValueError as error:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    "locked order material-ready time is invalid",
                ) from error
            start = ready + timedelta(hours=2)
            locks.append(
                {
                    "lock_id": f"operation-lock-{index + 1:03d}",
                    "production_lot_id": lot_id,
                    "routing_operation_id": operation_id,
                    "lock_type": (
                        "HARD_LOCK"
                        if seed.deterministic_index(2, "lock-type", index=index) == 0
                        else "SOFT_LOCK"
                    ),
                    "resource_id": str(options[0]["resource_id"]),
                    "start_at_utc": format_synthetic_utc(start),
                    "end_at_utc": format_synthetic_utc(start + timedelta(minutes=60)),
                }
            )
        return {**records, "operation_locks": tuple(locks)}


__all__ = ["DeterministicLockGenerator"]
