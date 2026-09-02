"""Business Urgent Order command mapped to an additive Standard Import candidate."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.domain.types import format_utc_instant
from app.normalization import COLLECTION_ID_FIELDS, canonical_json_bytes

from .generator import DemoGeneratedBatch, DemoPackageGenerator


PriorityClass = Literal["NORMAL", "KEY", "URGENT"]
PRIORITY_WEIGHTS: Mapping[str, int] = {"NORMAL": 1, "KEY": 4, "URGENT": 12}


class UrgentOrderCommand(BaseModel):
    """Strict business request; event authority and identities are server-derived."""

    model_config = ConfigDict(extra="forbid", strict=True)

    command_version: Literal["cnc-demo-urgent-order-command.v1"]
    expected_run_id: str = Field(min_length=1, max_length=128)
    expected_base_version_id: str = Field(min_length=1, max_length=256)
    route_template_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=50)
    due_at_local: str = Field(min_length=19, max_length=32)
    priority_class: PriorityClass
    note: str | None = Field(default=None, max_length=200)


class UrgentOrderError(ValueError):
    def __init__(self, *, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True, slots=True)
class UrgentCandidate:
    command: UrgentOrderCommand
    command_fingerprint: str
    generated: DemoGeneratedBatch
    due_at_utc: str
    priority_weight: int
    demand_source_id: str
    production_order_source_id: str
    production_lot_source_id: str
    added_record_counts: Mapping[str, int]
    preserved_record_count: int


def command_fingerprint(command: UrgentOrderCommand) -> str:
    payload = canonical_json_bytes(command.model_dump(mode="json"))
    return f"sha256:{sha256(payload).hexdigest()}"


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise UrgentOrderError(field="simulation.anchor_at_utc", message="must be UTC")
    return parsed.astimezone(UTC)


def resolve_local_due(value: str, *, timezone_name: str) -> datetime:
    """Resolve one unambiguous wall-clock time and reject DST gaps/overlaps."""

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise UrgentOrderError(
            field="due_at_local", message="must be an ISO local date-time"
        ) from error
    if parsed.tzinfo is not None:
        raise UrgentOrderError(
            field="due_at_local", message="must not include an offset or timezone"
        )
    timezone = ZoneInfo(timezone_name)
    candidates: list[datetime] = []
    for fold in (0, 1):
        candidate = parsed.replace(tzinfo=timezone, fold=fold)
        round_trip = candidate.astimezone(UTC).astimezone(timezone)
        if round_trip.replace(tzinfo=None) == parsed:
            candidates.append(candidate)
    if not candidates:
        raise UrgentOrderError(
            field="due_at_local", message="falls in a nonexistent local-time interval"
        )
    offsets = {candidate.utcoffset() for candidate in candidates}
    if len(offsets) > 1:
        raise UrgentOrderError(
            field="due_at_local", message="is ambiguous in the factory timezone"
        )
    return candidates[0].astimezone(UTC)


def _stable_index(label: str, size: int) -> int:
    return int.from_bytes(sha256(label.encode("utf-8")).digest()[:8], "big") % size


def _record_id(record: Mapping[str, Any], collection: str) -> str:
    field = COLLECTION_ID_FIELDS[collection]
    value = record.get(field)
    if not isinstance(value, str):
        raise UrgentOrderError(
            field=f"candidate.{collection}", message=f"record lacks {field}"
        )
    return value


def _assert_additive(
    base: DemoGeneratedBatch,
    candidate: DemoGeneratedBatch,
    *,
    expected_added: Mapping[str, int],
) -> int:
    preserved = 0
    all_collections = set(base.records) | set(candidate.records)
    for collection in all_collections:
        original = tuple(base.records.get(collection, ()))
        revised = tuple(candidate.records.get(collection, ()))
        original_by_id = {
            _record_id(record, collection): canonical_json_bytes(record)
            for record in original
        }
        revised_by_id = {
            _record_id(record, collection): canonical_json_bytes(record)
            for record in revised
        }
        for identity, payload in original_by_id.items():
            if revised_by_id.get(identity) != payload:
                raise UrgentOrderError(
                    field=f"candidate.{collection}.{identity}",
                    message="existing source record changed",
                )
            preserved += 1
        observed_added = len(set(revised_by_id).difference(original_by_id))
        if observed_added != expected_added.get(collection, 0):
            raise UrgentOrderError(
                field=f"candidate.{collection}",
                message="additive record count differs from the route expansion",
            )
    return preserved


def prepare_urgent_candidate(
    base: DemoGeneratedBatch,
    command: UrgentOrderCommand,
) -> UrgentCandidate:
    """Expand one approved route into a complete additive import candidate."""

    generator = DemoPackageGenerator()
    if generator.assets.asset_digest != base.assets_digest:
        raise UrgentOrderError(
            field="assets_digest", message="Demo assets changed after run initialization"
        )
    templates = {
        str(item["template_id"]): item
        for item in generator.assets.route_templates["templates"]
    }
    template = templates.get(command.route_template_id)
    if template is None:
        raise UrgentOrderError(
            field="route_template_id", message="is not in the Demo route whitelist"
        )
    timezone_name = str(generator.assets.manifest["factory_timezone"])
    due = resolve_local_due(command.due_at_local, timezone_name=timezone_name)
    cutoff = _parse_utc(base.profile.anchor_at_utc)
    horizon_end = cutoff + timedelta(days=base.profile.horizon_days)
    if due <= cutoff or due > horizon_end:
        raise UrgentOrderError(
            field="due_at_local", message="must be after cutoff and within the horizon"
        )

    fingerprint = command_fingerprint(command)
    suffix = fingerprint.removeprefix("sha256:")[:20]
    product_id = f"product-cnc-urgent-{suffix}"
    routing_id = f"routing-version-cnc-urgent-{suffix}"
    demand_id = f"demand-order-cnc-urgent-{suffix}"
    order_id = f"production-order-cnc-urgent-{suffix}"
    lot_id = f"production-lot-cnc-urgent-{suffix}"

    records: dict[str, list[dict[str, Any]]] = {
        collection: [dict(record) for record in values]
        for collection, values in base.records.items()
    }
    resources_by_capability: dict[str, list[str]] = defaultdict(list)
    for resource in records["resources"]:
        for capability in cast(Sequence[object], resource["capabilities"]):
            resources_by_capability[str(capability)].append(str(resource["resource_id"]))

    additions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    additions["products"].append(
        {
            "product_id": product_id,
            "product_code": f"CNC-URGENT-{suffix.upper()}",
            "quantity_unit": "piece",
        }
    )
    additions["routing_versions"].append(
        {
            "routing_version_id": routing_id,
            "routing_code": f"{command.route_template_id}-URGENT-{suffix.upper()}",
            "version": "1.0.0",
            "product_id": product_id,
        }
    )
    duration_parameters = generator.assets.duration_parameters["parameters"]
    tick_seconds = int(generator.assets.duration_parameters["tick_seconds"])
    previous_operation_id: str | None = None
    previous_capability: str | None = None
    steps = cast(Sequence[Mapping[str, Any]], template["steps"])
    for raw_step in steps:
        step_index = int(raw_step["step_index"])
        operation_id = f"routing-operation-cnc-urgent-{suffix}-{step_index:02d}"
        capability = str(raw_step["required_capability"])
        additions["routing_operations"].append(
            {
                "routing_operation_id": operation_id,
                "routing_version_id": routing_id,
                "operation_code": f"{raw_step['operation_code']}-URGENT-{suffix.upper()}",
                "required_capabilities": [capability],
            }
        )
        if previous_operation_id is not None:
            additions["routing_precedence_edges"].append(
                {
                    "routing_precedence_edge_id": (
                        f"routing-edge-cnc-urgent-{suffix}-{step_index - 1:02d}"
                    ),
                    "routing_version_id": routing_id,
                    "predecessor_routing_operation_id": previous_operation_id,
                    "successor_routing_operation_id": operation_id,
                    "min_lag_seconds": 0,
                    "min_lag_unit": "s",
                    "transport_lag_seconds": (
                        300 if previous_capability != capability else 0
                    ),
                    "transport_lag_unit": "s",
                }
            )
        pool = sorted(resources_by_capability[capability])
        if not pool:
            raise UrgentOrderError(
                field=f"route_template_id.steps[{step_index}]",
                message="has no eligible Demo resource",
            )
        rotation = _stable_index(f"{fingerprint}:{operation_id}:pool", len(pool))
        pool = [*pool[rotation:], *pool[:rotation]]
        candidate_count = min(len(pool), 1 + _stable_index(f"{fingerprint}:{operation_id}", 3))
        parameters = cast(Mapping[str, object], duration_parameters[raw_step["duration_key"]])
        setup_seconds = int(cast(int, parameters["setup_seconds"]))
        cycle_seconds = int(cast(int, parameters["cycle_seconds_per_unit"]))
        base_duration = setup_seconds + cycle_seconds * command.quantity
        for candidate_index, resource_id in enumerate(pool[:candidate_count], start=1):
            variation = (-1, 0, 1)[
                _stable_index(f"{fingerprint}:{operation_id}:{resource_id}", 3)
            ]
            duration = max(tick_seconds, base_duration + variation * tick_seconds)
            duration = ((duration + tick_seconds - 1) // tick_seconds) * tick_seconds
            additions["routing_resource_options"].append(
                {
                    "routing_resource_option_id": (
                        f"routing-option-cnc-urgent-{suffix}-{step_index:02d}-{candidate_index:02d}"
                    ),
                    "routing_operation_id": operation_id,
                    "resource_id": resource_id,
                    "quantity_unit": "piece",
                    "setup_seconds": setup_seconds,
                    "setup_unit": "s",
                    "cycle_seconds_per_unit": cycle_seconds,
                    "cycle_unit": "s",
                    "final_duration_seconds": duration,
                    "final_duration_unit": "s",
                    "duration_source": "PLANTNEXUS-DEMO-URGENT-ROUTE-EXPANDER",
                    "duration_source_version": "1.0.0",
                }
            )
        previous_operation_id = operation_id
        previous_capability = capability

    additions["demand_orders"].append(
        {
            "demand_order_id": demand_id,
            "product_id": product_id,
            "quantity": command.quantity,
            "quantity_unit": "piece",
            "due_at_utc": format_utc_instant(due),
        }
    )
    additions["production_orders"].append(
        {
            "production_order_id": order_id,
            "demand_order_id": demand_id,
            "routing_version_id": routing_id,
            "quantity": command.quantity,
            "quantity_unit": "piece",
            "release_at_utc": base.profile.anchor_at_utc,
            "material_ready_at_utc": base.profile.anchor_at_utc,
        }
    )
    additions["production_lots"].append(
        {
            "production_lot_id": lot_id,
            "production_order_id": order_id,
            "quantity": command.quantity,
            "quantity_unit": "piece",
        }
    )
    for collection, values in additions.items():
        records[collection].extend(values)
    priorities = dict(base.priority_class_by_demand_source_id)
    priorities[demand_id] = command.priority_class
    candidate = generator.build_batch_from_records(
        profile=base.profile,
        context=base.context,
        records=records,
        priorities=priorities,
        source_name=f"cnc-demo-urgent-{suffix}.jsonl",
    )
    expected_added = {collection: len(values) for collection, values in additions.items()}
    preserved = _assert_additive(base, candidate, expected_added=expected_added)
    return UrgentCandidate(
        command=command,
        command_fingerprint=fingerprint,
        generated=candidate,
        due_at_utc=format_utc_instant(due),
        priority_weight=PRIORITY_WEIGHTS[command.priority_class],
        demand_source_id=demand_id,
        production_order_source_id=order_id,
        production_lot_source_id=lot_id,
        added_record_counts=dict(sorted(expected_added.items())),
        preserved_record_count=preserved,
    )


__all__ = [
    "PRIORITY_WEIGHTS",
    "UrgentCandidate",
    "UrgentOrderCommand",
    "UrgentOrderError",
    "command_fingerprint",
    "prepare_urgent_candidate",
    "resolve_local_due",
]
