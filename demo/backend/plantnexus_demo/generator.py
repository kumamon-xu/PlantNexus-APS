"""Deterministic CNC source-data generation ending at Raw Staging."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from hashlib import sha256
import random
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.capabilities import CapabilityName
from app.domain.types import format_utc_instant
from app.importers import (
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)
from app.normalization import COLLECTION_ID_FIELDS, MappingProfile, canonical_json_bytes
from app.simulation.generators.contracts import GenerationContext
from app.simulation.generators.package_generator import p1_mapping_profile
from app.simulation.scenarios.contracts import SimulationTarget

from .assets import BenchmarkProfile, DemoAssets, load_demo_assets


SOURCE_SYSTEM = "plantnexus-synthetic"
GENERATOR_ID = "PLANTNEXUS-DEMO-CNC-IMPORT-GENERATOR"
GENERATOR_VERSION = "1.0.0"
PRIORITY_SOURCE_SYSTEM = "plantnexus-synthetic-policy"

type SourceRecord = dict[str, Any]
type RecordCollections = dict[str, tuple[SourceRecord, ...]]


@dataclass(frozen=True, slots=True)
class _OperationDescriptor:
    order_index: int
    step_index: int
    operation_id: str
    route_id: str
    required_capability: str
    duration_key: str


@dataclass(frozen=True, slots=True)
class DemoGeneratedBatch:
    profile: BenchmarkProfile
    assets_digest: str
    context: GenerationContext
    records: Mapping[str, tuple[SourceRecord, ...]]
    batch: StagedImportBatch
    mapping_profile: MappingProfile
    priority_class_by_demand_source_id: Mapping[str, str]


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"expected UTC timestamp, got {value}")
    return parsed.astimezone(UTC)


def _stable_index(seed: int, label: str, size: int) -> int:
    digest = sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def _rotated(values: Sequence[str], *, seed: int, label: str) -> list[str]:
    ordered = sorted(values)
    position = _stable_index(seed, label, len(ordered))
    return [*ordered[position:], *ordered[:position]]


def _route_lengths(profile: BenchmarkProfile) -> list[int]:
    counts = dict(profile.route_length_counts)
    prefix: list[int] = []
    if profile.running_operation_count:
        prefix.append(3)
        counts[3] -= 1
    preferred = (4, 5, 6)
    for position in range(max(0, profile.running_operation_count - len(prefix))):
        candidates = [length for length in preferred if counts.get(length, 0) > 0]
        if not candidates:
            candidates = [length for length, count in counts.items() if count > 0]
        chosen = candidates[position % len(candidates)]
        prefix.append(chosen)
        counts[chosen] -= 1
    remainder = [length for length, count in sorted(counts.items()) for _ in range(count)]
    random.Random(profile.seed + 101).shuffle(remainder)
    result = [*prefix, *remainder]
    if len(result) != profile.order_count:
        raise ValueError("route-length allocation drifted from the profile")
    return result


def _priority_classes(profile: BenchmarkProfile) -> list[str]:
    values = [
        class_id
        for class_id, count in sorted(profile.priority_class_counts.items())
        for _ in range(count)
    ]
    random.Random(profile.seed + 211).shuffle(values)
    return values


def _execution_plan(profile: BenchmarkProfile) -> tuple[dict[int, int], set[int]]:
    completed_by_order: dict[int, int] = {}
    running_orders = set(range(profile.running_operation_count))
    remaining = profile.completed_operation_count
    for order_index in sorted(running_orders):
        count = min(2, remaining)
        completed_by_order[order_index] = count
        remaining -= count
    order_index = profile.running_operation_count
    while remaining:
        completed_by_order[order_index] = 1
        order_index += 1
        remaining -= 1
    return completed_by_order, running_orders


def _selected_resources(assets: DemoAssets, profile: BenchmarkProfile) -> list[Mapping[str, Any]]:
    catalog = assets.resource_catalog
    selected_ids = set(catalog["profile_resource_ids"][profile.resource_profile])
    selected = [
        resource
        for resource in catalog["resources"]
        if resource["resource_id"] in selected_ids
    ]
    if len(selected) != profile.resource_count:
        raise ValueError("selected resource catalog does not match the profile")
    return selected


def _calendar_intervals(
    *,
    assets: DemoAssets,
    profile: BenchmarkProfile,
    resource_id: str,
) -> list[dict[str, Any]]:
    start_utc = _parse_utc(profile.anchor_at_utc)
    end_utc = start_utc + timedelta(days=profile.horizon_days)
    timezone = ZoneInfo(str(assets.manifest["factory_timezone"]))
    start_local = start_utc.astimezone(timezone)
    end_local = end_utc.astimezone(timezone)
    intervals: list[tuple[datetime, datetime, str, str]] = []
    current_date = start_local.date()
    last_date = end_local.date()
    index = 0
    while current_date <= last_date:
        day_start = datetime.combine(current_date, time.min, timezone)
        day_end = day_start + timedelta(days=1)
        weekday = current_date.weekday()
        if weekday < 5:
            available_start = datetime.combine(current_date, time(6), timezone)
            available_end = datetime.combine(current_date, time(22), timezone)
            unavailable = ((day_start, available_start), (available_end, day_end))
        elif weekday == 5:
            available_start = datetime.combine(current_date, time(8), timezone)
            available_end = datetime.combine(current_date, time(16), timezone)
            unavailable = ((day_start, available_start), (available_end, day_end))
        else:
            unavailable = ((day_start, day_end),)
        for raw_start, raw_end in unavailable:
            clipped_start = max(raw_start.astimezone(UTC), start_utc)
            clipped_end = min(raw_end.astimezone(UTC), end_utc)
            if clipped_start < clipped_end:
                index += 1
                intervals.append(
                    (
                        clipped_start,
                        clipped_end,
                        f"shift-{index:03d}",
                        "非工作时段",
                    )
                )
        current_date += timedelta(days=1)

    for event in assets.maintenance_plan["events"]:
        if event["resource_id"] != resource_id:
            continue
        event_start = datetime.fromisoformat(event["start_local"]).astimezone(UTC)
        event_end = datetime.fromisoformat(event["end_local"]).astimezone(UTC)
        clipped_start = max(event_start, start_utc)
        clipped_end = min(event_end, end_utc)
        if clipped_start < clipped_end:
            intervals.append(
                (
                    clipped_start,
                    clipped_end,
                    str(event["event_id"]).lower(),
                    str(event["reason"]),
                )
            )

    intervals.sort(key=lambda item: (item[0], item[1], item[2]))
    return [
        {
            "interval_id": f"calendar-interval-{resource_id}-{identity}",
            "start_at": format_utc_instant(start),
            "end_at": format_utc_instant(end),
            "reason": reason,
        }
        for start, end, identity, reason in intervals
    ]


def _raw_rows(records: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[RawImportRow, ...]:
    rows: list[RawImportRow] = []
    position = 0
    for collection, id_field in COLLECTION_ID_FIELDS.items():
        for record in records.get(collection, ()):
            source_record_id = record.get(id_field)
            if not isinstance(source_record_id, str):
                raise ValueError(f"{collection} record lacks {id_field}")
            payload = {key: value for key, value in record.items() if key != id_field}
            outer = {
                "record_type": collection,
                "source_record_id": source_record_id,
                "payload_json": canonical_json_bytes(payload).decode("utf-8"),
            }
            position += 1
            rows.append(
                RawImportRow(
                    row_identity=f"{collection}:{source_record_id}",
                    source_location=f"cnc-demo-records.jsonl:{position}",
                    raw_payload=canonical_json_bytes(outer),
                )
            )
    return tuple(rows)


class DemoPackageGenerator:
    """Generate deterministic industry data while preserving Standard Import."""

    def __init__(self, assets: DemoAssets | None = None) -> None:
        self.assets = load_demo_assets() if assets is None else assets

    def prepare_batch(self, profile_name: str = "showcase") -> DemoGeneratedBatch:
        profile = self.assets.profile(profile_name)
        context = GenerationContext.create(
            scenario_id=profile.profile_id,
            scenario_version=profile.scenario_version,
            profile_id="CNC-DEMO-FACTORY",
            profile_version="1.0.0",
            generator_id=GENERATOR_ID,
            generator_version=GENERATOR_VERSION,
            seed=profile.seed,
            target=SimulationTarget.BENCHMARK,
            required_capabilities=(
                CapabilityName.SINGLE_FACTORY_MULTI_WORKSHOP,
                CapabilityName.DAG_ROUTING,
                CapabilityName.ALTERNATIVE_RESOURCE,
                CapabilityName.MACHINE_CALENDAR,
                CapabilityName.RELEASE_AND_MATERIAL_GATE,
                CapabilityName.RUNNING_OPERATION,
                CapabilityName.HARD_SOFT_LOCK,
            ),
        )
        records, priorities = self._generate_records(profile)
        return self.build_batch_from_records(
            profile=profile,
            context=context,
            records=records,
            priorities=priorities,
        )

    def build_batch_from_records(
        self,
        *,
        profile: BenchmarkProfile,
        context: GenerationContext,
        records: Mapping[str, Sequence[Mapping[str, Any]]],
        priorities: Mapping[str, str],
        source_name: str = "cnc-demo-records.jsonl",
    ) -> DemoGeneratedBatch:
        """Build one immutable Standard Import batch from an additive record set."""

        frozen_records: RecordCollections = {
            collection: tuple(dict(record) for record in values)
            for collection, values in records.items()
        }
        rows = _raw_rows(frozen_records)
        content = b"\n".join(row.raw_payload for row in rows)
        digest = sha256(content).hexdigest()
        batch = StagedImportBatch(
            batch_id=f"cnc-demo-batch-{digest[:24]}",
            idempotency_key=f"cnc-demo-import-{digest}",
            source_system=SOURCE_SYSTEM,
            source_version=GENERATOR_VERSION,
            content_sha256=digest,
            source_name=source_name,
            media_type="application/x-ndjson",
            content_length_bytes=len(content),
            received_at=_parse_utc(profile.anchor_at_utc),
            data_plane=StagingDataPlane.SIMULATION,
            rows=rows,
            synthetic_provenance=SyntheticImportProvenance(
                scenario_id=context.scenario_id,
                scenario_version=context.scenario_version,
                seed=context.seed,
                factory_profile_id=context.profile_id,
                profile_version=context.profile_version,
                generator_id=context.generator_id,
                generator_version=context.generator_version,
            ),
        )
        mapping_profile = p1_mapping_profile(context)
        if mapping_profile.source_system != batch.source_system:
            raise ValueError("demo staging source and selected mapping profile differ")
        return DemoGeneratedBatch(
            profile=profile,
            assets_digest=self.assets.asset_digest,
            context=context,
            records=MappingProxyType(frozen_records),
            batch=batch,
            mapping_profile=mapping_profile,
            priority_class_by_demand_source_id=MappingProxyType(dict(priorities)),
        )

    def _generate_records(
        self, profile: BenchmarkProfile
    ) -> tuple[RecordCollections, dict[str, str]]:
        anchor = _parse_utc(profile.anchor_at_utc)
        selected_resources = _selected_resources(self.assets, profile)
        selected_resource_ids = {item["resource_id"] for item in selected_resources}
        route_lengths = _route_lengths(profile)
        priority_classes = _priority_classes(profile)
        completed_by_order, running_orders = _execution_plan(profile)
        historical_order_count = max(completed_by_order, default=-1) + 1
        lock_total = profile.hard_lock_count + profile.soft_lock_count
        locked_order_indices = set(
            range(historical_order_count, historical_order_count + lock_total)
        )

        delayed_candidates = [
            index
            for index in range(profile.order_count)
            if index not in completed_by_order and index not in locked_order_indices
        ]
        random.Random(profile.seed + 307).shuffle(delayed_candidates)
        delayed_orders = set(delayed_candidates[: profile.material_delay_count])

        factory_asset = self.assets.factory["factory"]
        factories: list[SourceRecord] = [
            {
                "factory_id": factory_asset["factory_id"],
                "factory_code": factory_asset["factory_code"],
                "factory_timezone": factory_asset["timezone"],
            }
        ]
        workshops: list[SourceRecord] = []
        production_lines: list[SourceRecord] = []
        for workshop in self.assets.factory["workshops"]:
            workshops.append(
                {
                    "workshop_id": workshop["workshop_id"],
                    "workshop_code": workshop["workshop_code"],
                    "factory_id": factory_asset["factory_id"],
                }
            )
            production_lines.append(
                {
                    "production_line_id": workshop["production_line_id"],
                    "production_line_code": workshop["production_line_code"],
                    "workshop_id": workshop["workshop_id"],
                }
            )
        resource_groups = [dict(item) for item in self.assets.factory["resource_groups"]]
        resources: list[SourceRecord] = []
        calendars: list[SourceRecord] = []
        for resource in selected_resources:
            resource_id = str(resource["resource_id"])
            calendar_id = f"calendar-{resource_id}"
            resources.append(
                {
                    "resource_id": resource_id,
                    "resource_code": resource["resource_code"],
                    "resource_type": "UNIT_CAPACITY_MACHINE",
                    "status": "ACTIVE",
                    "resource_group_id": resource["resource_group_id"],
                    "calendar_id": calendar_id,
                    "capabilities": list(resource["capabilities"]),
                }
            )
            calendars.append(
                {
                    "calendar_id": calendar_id,
                    "timezone": factory_asset["timezone"],
                    "unavailable_intervals": _calendar_intervals(
                        assets=self.assets,
                        profile=profile,
                        resource_id=resource_id,
                    ),
                }
            )

        templates = {
            len(template["steps"]): template
            for template in self.assets.route_templates["templates"]
        }
        products: list[SourceRecord] = []
        routing_versions: list[SourceRecord] = []
        operations: list[SourceRecord] = []
        edges: list[SourceRecord] = []
        descriptors: list[_OperationDescriptor] = []
        for order_index, route_length in enumerate(route_lengths):
            order_number = order_index + 1
            product_id = f"product-cnc-{order_number:03d}"
            route_id = f"routing-version-cnc-{order_number:03d}"
            template = templates[route_length]
            products.append(
                {
                    "product_id": product_id,
                    "product_code": f"CNC-PART-{order_number:03d}",
                    "quantity_unit": "piece",
                }
            )
            routing_versions.append(
                {
                    "routing_version_id": route_id,
                    "routing_code": f"CNC-ROUTE-{order_number:03d}",
                    "version": "1.0.0",
                    "product_id": product_id,
                }
            )
            previous_operation_id: str | None = None
            previous_capability: str | None = None
            for step in template["steps"]:
                step_index = int(step["step_index"])
                operation_id = f"routing-operation-cnc-{order_number:03d}-{step_index:02d}"
                capability = str(step["required_capability"])
                operations.append(
                    {
                        "routing_operation_id": operation_id,
                        "routing_version_id": route_id,
                        "operation_code": f"{step['operation_code']}-{order_number:03d}",
                        "required_capabilities": [capability],
                    }
                )
                descriptors.append(
                    _OperationDescriptor(
                        order_index=order_index,
                        step_index=step_index,
                        operation_id=operation_id,
                        route_id=route_id,
                        required_capability=capability,
                        duration_key=str(step["duration_key"]),
                    )
                )
                if previous_operation_id is not None:
                    cross_stage = previous_capability != capability
                    edges.append(
                        {
                            "routing_precedence_edge_id": f"routing-edge-cnc-{order_number:03d}-{step_index - 1:02d}",
                            "routing_version_id": route_id,
                            "predecessor_routing_operation_id": previous_operation_id,
                            "successor_routing_operation_id": operation_id,
                            "min_lag_seconds": 0,
                            "min_lag_unit": "s",
                            "transport_lag_seconds": 300 if cross_stage else 0,
                            "transport_lag_unit": "s",
                        }
                    )
                previous_operation_id = operation_id
                previous_capability = capability

        resources_by_capability: dict[str, list[str]] = defaultdict(list)
        for resource in resources:
            for capability in resource["capabilities"]:
                resources_by_capability[str(capability)].append(str(resource["resource_id"]))
        if any(not resources_by_capability[item.required_capability] for item in descriptors):
            raise ValueError("a route capability has no selected demo resource")

        descriptor_indices = list(range(len(descriptors)))
        eligible_three = [
            index
            for index in descriptor_indices
            if len(resources_by_capability[descriptors[index].required_capability]) >= 3
        ]
        random.Random(profile.seed + 401).shuffle(eligible_three)
        three_indices = set(eligible_three[: profile.candidate_count_targets[3]])
        if len(three_indices) != profile.candidate_count_targets[3]:
            raise ValueError("profile requests too many three-resource operations")
        one_required = {
            index
            for index in descriptor_indices
            if len(resources_by_capability[descriptors[index].required_capability]) == 1
        }
        if len(one_required) > profile.candidate_count_targets[1]:
            raise ValueError("profile has too few one-resource slots for its resource pools")
        one_candidates = [
            index
            for index in descriptor_indices
            if index not in three_indices and index not in one_required
        ]
        random.Random(profile.seed + 409).shuffle(one_candidates)
        one_indices = set(one_required)
        one_indices.update(
            one_candidates[: profile.candidate_count_targets[1] - len(one_required)]
        )
        candidate_count_by_index = {
            index: 3 if index in three_indices else 1 if index in one_indices else 2
            for index in descriptor_indices
        }
        observed_candidate_counts = defaultdict(int)
        for count in candidate_count_by_index.values():
            observed_candidate_counts[count] += 1
        if dict(observed_candidate_counts) != dict(profile.candidate_count_targets):
            raise ValueError("candidate-resource quota allocation drifted")

        running_descriptor_indices: dict[int, int] = {}
        for index, descriptor in enumerate(descriptors):
            completed_count = completed_by_order.get(descriptor.order_index, 0)
            if descriptor.order_index in running_orders and descriptor.step_index == completed_count + 1:
                running_descriptor_indices[descriptor.order_index] = index
        preferred_running_resource: dict[int, str] = {}
        used_running_resources: set[str] = set()
        for order_index in sorted(running_descriptor_indices):
            descriptor_index = running_descriptor_indices[order_index]
            descriptor = descriptors[descriptor_index]
            pool = _rotated(
                resources_by_capability[descriptor.required_capability],
                seed=profile.seed,
                label=f"running:{descriptor.operation_id}",
            )
            available = [resource_id for resource_id in pool if resource_id not in used_running_resources]
            if not available:
                raise ValueError("running-operation resources cannot be made unique")
            preferred_running_resource[descriptor_index] = available[0]
            used_running_resources.add(available[0])

        quantity_by_order = {
            index: 2 + _stable_index(profile.seed, f"quantity:{index}", 5)
            for index in range(profile.order_count)
        }
        duration_parameters = self.assets.duration_parameters["parameters"]
        tick_seconds = int(self.assets.duration_parameters["tick_seconds"])
        options: list[SourceRecord] = []
        options_by_operation: dict[str, list[SourceRecord]] = defaultdict(list)
        for descriptor_index, descriptor in enumerate(descriptors):
            pool = _rotated(
                resources_by_capability[descriptor.required_capability],
                seed=profile.seed,
                label=f"option-pool:{descriptor.operation_id}",
            )
            preferred = preferred_running_resource.get(descriptor_index)
            if preferred is not None:
                pool = [preferred, *(item for item in pool if item != preferred)]
            candidate_count = candidate_count_by_index[descriptor_index]
            parameter = duration_parameters[descriptor.duration_key]
            setup_seconds = int(parameter["setup_seconds"])
            cycle_seconds = int(parameter["cycle_seconds_per_unit"])
            base_duration = setup_seconds + cycle_seconds * quantity_by_order[descriptor.order_index]
            for candidate_index, resource_id in enumerate(pool[:candidate_count], start=1):
                variation_steps = (-1, 0, 1)[
                    _stable_index(
                        profile.seed,
                        f"duration:{descriptor.operation_id}:{resource_id}",
                        3,
                    )
                ]
                final_duration = max(tick_seconds, base_duration + variation_steps * tick_seconds)
                option: SourceRecord = {
                    "routing_resource_option_id": f"routing-option-cnc-{descriptor.order_index + 1:03d}-{descriptor.step_index:02d}-{candidate_index:02d}",
                    "routing_operation_id": descriptor.operation_id,
                    "resource_id": resource_id,
                    "quantity_unit": "piece",
                    "setup_seconds": setup_seconds,
                    "setup_unit": "s",
                    "cycle_seconds_per_unit": cycle_seconds,
                    "cycle_unit": "s",
                    "final_duration_seconds": final_duration,
                    "final_duration_unit": "s",
                    "duration_source": GENERATOR_ID,
                    "duration_source_version": GENERATOR_VERSION,
                }
                options.append(option)
                options_by_operation[descriptor.operation_id].append(option)

        priority_by_demand: dict[str, str] = {}
        demand_orders: list[SourceRecord] = []
        production_orders: list[SourceRecord] = []
        lots: list[SourceRecord] = []
        due_days = {"URGENT": 2, "KEY": 4, "NORMAL": 6}
        for order_index in range(profile.order_count):
            number = order_index + 1
            demand_id = f"demand-order-cnc-{number:03d}"
            order_id = f"production-order-cnc-{number:03d}"
            lot_id = f"production-lot-cnc-{number:03d}"
            priority_class = priority_classes[order_index]
            if order_index in completed_by_order:
                release = anchor - timedelta(days=1)
            elif order_index in locked_order_indices:
                release = anchor
            else:
                release = anchor + timedelta(minutes=(order_index % 16) * 30)
            material_ready = release
            if order_index in delayed_orders:
                material_ready += timedelta(hours=12 + (order_index % 4) * 6)
            due = anchor + timedelta(
                days=due_days[priority_class], hours=(order_index % 5) * 2
            )
            horizon_end = anchor + timedelta(days=profile.horizon_days)
            due = min(due, horizon_end - timedelta(hours=6))
            quantity = quantity_by_order[order_index]
            product_id = f"product-cnc-{number:03d}"
            route_id = f"routing-version-cnc-{number:03d}"
            demand_orders.append(
                {
                    "demand_order_id": demand_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "quantity_unit": "piece",
                    "due_at_utc": format_utc_instant(due),
                }
            )
            production_orders.append(
                {
                    "production_order_id": order_id,
                    "demand_order_id": demand_id,
                    "routing_version_id": route_id,
                    "quantity": quantity,
                    "quantity_unit": "piece",
                    "release_at_utc": format_utc_instant(release),
                    "material_ready_at_utc": format_utc_instant(material_ready),
                }
            )
            lots.append(
                {
                    "production_lot_id": lot_id,
                    "production_order_id": order_id,
                    "quantity": quantity,
                    "quantity_unit": "piece",
                }
            )
            priority_by_demand[demand_id] = priority_class

        execution_facts: list[SourceRecord] = []
        descriptor_by_order_step = {
            (descriptor.order_index, descriptor.step_index): descriptor
            for descriptor in descriptors
        }
        for order_index, completed_count in sorted(completed_by_order.items()):
            number = order_index + 1
            cursor = anchor - timedelta(hours=6)
            quantity = quantity_by_order[order_index]
            for step_index in range(1, completed_count + 1):
                descriptor = descriptor_by_order_step[(order_index, step_index)]
                option = options_by_operation[descriptor.operation_id][0]
                duration = timedelta(seconds=int(option["final_duration_seconds"]))
                actual_start = cursor
                actual_end = actual_start + duration
                execution_facts.append(
                    {
                        "execution_fact_id": f"execution-fact-cnc-{number:03d}-{step_index:02d}",
                        "production_lot_id": f"production-lot-cnc-{number:03d}",
                        "routing_operation_id": descriptor.operation_id,
                        "status": "COMPLETED",
                        "observed_at_utc": format_utc_instant(actual_end),
                        "quantity_unit": "piece",
                        "resource_id": option["resource_id"],
                        "actual_start_at_utc": format_utc_instant(actual_start),
                        "actual_end_at_utc": format_utc_instant(actual_end),
                        "completed_quantity": quantity,
                    }
                )
                cursor = actual_end + timedelta(minutes=15)
            if order_index in running_orders:
                step_index = completed_count + 1
                descriptor = descriptor_by_order_step[(order_index, step_index)]
                option = options_by_operation[descriptor.operation_id][0]
                duration_seconds = int(option["final_duration_seconds"])
                remaining_seconds = max(
                    tick_seconds,
                    ((duration_seconds + 2 * tick_seconds - 1) // (2 * tick_seconds))
                    * tick_seconds,
                )
                execution_facts.append(
                    {
                        "execution_fact_id": f"execution-fact-cnc-{number:03d}-{step_index:02d}",
                        "production_lot_id": f"production-lot-cnc-{number:03d}",
                        "routing_operation_id": descriptor.operation_id,
                        "status": "RUNNING",
                        "observed_at_utc": format_utc_instant(anchor),
                        "quantity_unit": "piece",
                        "resource_id": option["resource_id"],
                        "actual_start_at_utc": format_utc_instant(anchor - timedelta(hours=1)),
                        "remaining_quantity": max(1, quantity // 2),
                        "remaining_seconds": remaining_seconds,
                        "remaining_unit": "s",
                    }
                )

        operation_locks: list[SourceRecord] = []
        locked_orders = sorted(locked_order_indices)
        for lock_index, order_index in enumerate(locked_orders):
            number = order_index + 1
            descriptor = descriptor_by_order_step[(order_index, 1)]
            option = options_by_operation[descriptor.operation_id][0]
            if option["resource_id"] not in selected_resource_ids:
                raise ValueError("lock references an unselected resource")
            hard = lock_index < profile.hard_lock_count
            base_hours = 26 if hard else 50
            position = lock_index if hard else lock_index - profile.hard_lock_count
            start = anchor + timedelta(hours=base_hours + position * 2)
            end = start + timedelta(seconds=int(option["final_duration_seconds"]))
            operation_locks.append(
                {
                    "lock_id": f"operation-lock-cnc-{lock_index + 1:03d}",
                    "production_lot_id": f"production-lot-cnc-{number:03d}",
                    "routing_operation_id": descriptor.operation_id,
                    "lock_type": "HARD_LOCK" if hard else "SOFT_LOCK",
                    "resource_id": option["resource_id"],
                    "start_at_utc": format_utc_instant(start),
                    "end_at_utc": format_utc_instant(end),
                }
            )

        records: RecordCollections = {
            "factories": tuple(factories),
            "workshops": tuple(workshops),
            "production_lines": tuple(production_lines),
            "resource_groups": tuple(resource_groups),
            "resources": tuple(resources),
            "calendars": tuple(calendars),
            "products": tuple(products),
            "routing_versions": tuple(routing_versions),
            "routing_operations": tuple(operations),
            "routing_precedence_edges": tuple(edges),
            "routing_resource_options": tuple(options),
            "demand_orders": tuple(demand_orders),
            "production_orders": tuple(production_orders),
            "production_lots": tuple(lots),
            "execution_facts": tuple(execution_facts),
            "operation_locks": tuple(operation_locks),
        }
        return records, priority_by_demand


def source_record_counts(generated: DemoGeneratedBatch) -> dict[str, int]:
    return {collection: len(records) for collection, records in generated.records.items()}


__all__ = [
    "DemoGeneratedBatch",
    "DemoPackageGenerator",
    "GENERATOR_ID",
    "GENERATOR_VERSION",
    "PRIORITY_SOURCE_SYSTEM",
    "SOURCE_SYSTEM",
    "source_record_counts",
]
