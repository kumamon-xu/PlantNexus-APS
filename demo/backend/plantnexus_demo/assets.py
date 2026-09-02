"""Strict loading and cross-file validation for the CNC demo asset pack."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class DemoAssetError(ValueError):
    """A versioned demo asset is missing, malformed, or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    name: str
    profile_id: str
    scenario_version: str
    seed: int
    anchor_at_utc: str
    horizon_days: int
    order_count: int
    route_length_counts: Mapping[int, int]
    operation_count: int
    resource_profile: str
    resource_count: int
    candidate_count_targets: Mapping[int, int]
    priority_class_counts: Mapping[str, int]
    material_delay_count: int
    completed_operation_count: int
    running_operation_count: int
    hard_lock_count: int
    soft_lock_count: int
    initial_solve_seconds: int
    replan_solve_seconds: int

    @property
    def active_operation_count(self) -> int:
        return self.operation_count - self.completed_operation_count


@dataclass(frozen=True, slots=True)
class DemoAssets:
    root: Path
    manifest: Mapping[str, Any]
    factory: Mapping[str, Any]
    resource_catalog: Mapping[str, Any]
    route_templates: Mapping[str, Any]
    duration_parameters: Mapping[str, Any]
    priority_policy: Mapping[str, Any]
    maintenance_plan: Mapping[str, Any]
    profiles: Mapping[str, BenchmarkProfile]
    asset_digest: str

    def profile(self, name: str) -> BenchmarkProfile:
        try:
            return self.profiles[name]
        except KeyError as error:
            raise DemoAssetError(f"unknown demo benchmark profile: {name}") from error


_MANIFEST_FIELDS = {
    "asset_pack_version",
    "asset_pack_id",
    "industry",
    "locale",
    "factory_timezone",
    "generator_id",
    "generator_version",
    "default_profile",
    "fixed_seed",
    "files",
    "file_sha256",
    "benchmark_profiles_sha256",
}
_PROFILE_FIELDS = {
    "profile_id",
    "scenario_version",
    "seed",
    "anchor_at_utc",
    "horizon_days",
    "order_count",
    "route_length_counts",
    "operation_count",
    "resource_profile",
    "resource_count",
    "candidate_count_targets",
    "priority_class_counts",
    "material_delay_count",
    "completed_operation_count",
    "running_operation_count",
    "hard_lock_count",
    "soft_lock_count",
    "initial_solve_seconds",
    "replan_solve_seconds",
}
_RESOURCE_FIELDS = {
    "resource_id",
    "resource_code",
    "resource_name_zh",
    "family",
    "resource_group_id",
    "capabilities",
}
_STEP_FIELDS = {
    "step_index",
    "operation_code",
    "operation_name_zh",
    "required_capability",
    "duration_key",
}
_FACTORY_FIELDS = {"factory_id", "factory_code", "factory_name_zh", "timezone"}
_WORKSHOP_FIELDS = {
    "workshop_id",
    "workshop_code",
    "workshop_name_zh",
    "production_line_id",
    "production_line_code",
}
_GROUP_FIELDS = {"resource_group_id", "resource_group_code", "production_line_id"}
_SHIFT_FIELDS = {"start", "end"}
_DURATION_FIELDS = {"setup_seconds", "cycle_seconds_per_unit"}


def _exact(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise DemoAssetError(
            f"{label} fields differ: missing={sorted(expected - observed)} "
            f"extra={sorted(observed - expected)}"
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DemoAssetError(f"{label} must be an object")
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DemoAssetError(f"{label} must be an array")
    return value


def _positive_int(value: object, label: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DemoAssetError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DemoAssetError(f"{label} must be non-empty text")
    return value


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DemoAssetError(f"cannot read strict JSON asset: {path}") from error
    return _mapping(value, path.name)


def _freeze_counts(
    value: object, label: str, *, numeric_keys: bool
) -> Mapping[Any, int]:
    raw = _mapping(value, label)
    result: dict[Any, int] = {}
    for key, count in raw.items():
        parsed_key: Any
        if numeric_keys:
            try:
                parsed_key = int(key)
            except (TypeError, ValueError) as error:
                raise DemoAssetError(f"{label} keys must be integers") from error
        else:
            parsed_key = _text(key, f"{label}.key")
        result[parsed_key] = _positive_int(count, f"{label}.{key}", allow_zero=True)
    return MappingProxyType(result)


def _parse_profile(name: str, raw: Mapping[str, Any]) -> BenchmarkProfile:
    _exact(raw, _PROFILE_FIELDS, f"profiles.{name}")
    return BenchmarkProfile(
        name=name,
        profile_id=_text(raw["profile_id"], f"profiles.{name}.profile_id"),
        scenario_version=_text(
            raw["scenario_version"], f"profiles.{name}.scenario_version"
        ),
        seed=_positive_int(raw["seed"], f"profiles.{name}.seed", allow_zero=True),
        anchor_at_utc=_text(
            raw["anchor_at_utc"], f"profiles.{name}.anchor_at_utc"
        ),
        horizon_days=_positive_int(
            raw["horizon_days"], f"profiles.{name}.horizon_days"
        ),
        order_count=_positive_int(
            raw["order_count"], f"profiles.{name}.order_count"
        ),
        route_length_counts=_freeze_counts(
            raw["route_length_counts"],
            f"profiles.{name}.route_length_counts",
            numeric_keys=True,
        ),
        operation_count=_positive_int(
            raw["operation_count"], f"profiles.{name}.operation_count"
        ),
        resource_profile=_text(
            raw["resource_profile"], f"profiles.{name}.resource_profile"
        ),
        resource_count=_positive_int(
            raw["resource_count"], f"profiles.{name}.resource_count"
        ),
        candidate_count_targets=_freeze_counts(
            raw["candidate_count_targets"],
            f"profiles.{name}.candidate_count_targets",
            numeric_keys=True,
        ),
        priority_class_counts=_freeze_counts(
            raw["priority_class_counts"],
            f"profiles.{name}.priority_class_counts",
            numeric_keys=False,
        ),
        material_delay_count=_positive_int(
            raw["material_delay_count"],
            f"profiles.{name}.material_delay_count",
            allow_zero=True,
        ),
        completed_operation_count=_positive_int(
            raw["completed_operation_count"],
            f"profiles.{name}.completed_operation_count",
            allow_zero=True,
        ),
        running_operation_count=_positive_int(
            raw["running_operation_count"],
            f"profiles.{name}.running_operation_count",
            allow_zero=True,
        ),
        hard_lock_count=_positive_int(
            raw["hard_lock_count"],
            f"profiles.{name}.hard_lock_count",
            allow_zero=True,
        ),
        soft_lock_count=_positive_int(
            raw["soft_lock_count"],
            f"profiles.{name}.soft_lock_count",
            allow_zero=True,
        ),
        initial_solve_seconds=_positive_int(
            raw["initial_solve_seconds"],
            f"profiles.{name}.initial_solve_seconds",
        ),
        replan_solve_seconds=_positive_int(
            raw["replan_solve_seconds"],
            f"profiles.{name}.replan_solve_seconds",
        ),
    )


def _validate_profiles(
    profiles: Mapping[str, BenchmarkProfile],
    resource_profiles: Mapping[str, Any],
    priority_classes: set[str],
) -> None:
    for name, profile in profiles.items():
        if sum(profile.route_length_counts.values()) != profile.order_count:
            raise DemoAssetError(f"profile {name} route counts do not equal order_count")
        weighted_operations = sum(
            length * count for length, count in profile.route_length_counts.items()
        )
        if weighted_operations != profile.operation_count:
            raise DemoAssetError(
                f"profile {name} route distribution does not equal operation_count"
            )
        if set(profile.candidate_count_targets) != {1, 2, 3}:
            raise DemoAssetError(f"profile {name} must define candidate counts 1, 2, 3")
        if sum(profile.candidate_count_targets.values()) != profile.operation_count:
            raise DemoAssetError(
                f"profile {name} candidate targets do not equal operation_count"
            )
        if set(profile.priority_class_counts) != priority_classes:
            raise DemoAssetError(f"profile {name} priority classes do not match policy")
        if sum(profile.priority_class_counts.values()) != profile.order_count:
            raise DemoAssetError(
                f"profile {name} priority counts do not equal order_count"
            )
        resource_ids = _sequence(
            resource_profiles.get(profile.resource_profile),
            f"profile_resource_ids.{profile.resource_profile}",
        )
        if len(resource_ids) != profile.resource_count:
            raise DemoAssetError(f"profile {name} resource count does not match catalog")
        if profile.completed_operation_count + profile.running_operation_count > profile.operation_count:
            raise DemoAssetError(f"profile {name} execution-state counts are impossible")


def load_demo_assets(root: Path | None = None) -> DemoAssets:
    """Load every selected JSON asset and fail closed on unknown fields or drift."""

    demo_root = Path(__file__).resolve().parents[2]
    asset_root = (demo_root / "data" / "cnc-showcase") if root is None else root
    manifest = _load_json(asset_root / "manifest.json")
    _exact(manifest, _MANIFEST_FIELDS, "manifest")
    if manifest["asset_pack_version"] != "cnc-demo-assets.v1":
        raise DemoAssetError("unsupported CNC demo asset pack version")

    declared_files = tuple(_sequence(manifest["files"], "manifest.files"))
    expected_files = (
        "factory-profile.json",
        "resource-catalog.json",
        "route-templates.json",
        "duration-parameters.json",
        "priority-policy.json",
        "maintenance-plan.json",
    )
    if declared_files != expected_files:
        raise DemoAssetError("manifest.files must be the exact ordered asset set")

    declared_digests = _mapping(manifest["file_sha256"], "manifest.file_sha256")
    if set(declared_digests) != set(declared_files):
        raise DemoAssetError("manifest.file_sha256 must cover the exact declared asset set")
    for name in declared_files:
        observed_digest = sha256((asset_root / name).read_bytes()).hexdigest()
        declared_digest = declared_digests[name]
        if (
            not isinstance(declared_digest, str)
            or len(declared_digest) != 64
            or any(character not in "0123456789abcdef" for character in declared_digest)
            or declared_digest != observed_digest
        ):
            raise DemoAssetError(f"asset digest mismatch: {name}")

    documents = {name: _load_json(asset_root / name) for name in declared_files}
    factory = documents["factory-profile.json"]
    catalog = documents["resource-catalog.json"]
    routes = documents["route-templates.json"]
    durations = documents["duration-parameters.json"]
    priority = documents["priority-policy.json"]
    maintenance = documents["maintenance-plan.json"]

    _exact(
        factory,
        {"factory_profile_version", "factory", "workshops", "resource_groups", "working_calendar"},
        "factory-profile",
    )
    _exact(catalog, {"resource_catalog_version", "profile_resource_ids", "resources"}, "resource-catalog")
    _exact(routes, {"route_template_version", "templates"}, "route-templates")
    _exact(durations, {"duration_parameter_version", "quantity_unit", "tick_seconds", "parameters", "resource_variation_steps", "minimum_final_duration_seconds"}, "duration-parameters")
    _exact(priority, {"priority_policy_version", "classes", "source_system", "source_version"}, "priority-policy")
    _exact(maintenance, {"maintenance_plan_version", "timezone", "events"}, "maintenance-plan")

    factory_record = _mapping(factory["factory"], "factory")
    _exact(factory_record, _FACTORY_FIELDS, "factory")
    factory_timezone = _text(factory_record["timezone"], "factory.timezone")
    if factory_timezone != manifest["factory_timezone"]:
        raise DemoAssetError("factory timezone differs from the asset manifest")
    try:
        timezone = ZoneInfo(factory_timezone)
    except ZoneInfoNotFoundError as error:
        raise DemoAssetError("factory timezone must be an IANA timezone") from error

    workshop_ids: set[str] = set()
    production_line_ids: set[str] = set()
    for index, raw_workshop in enumerate(_sequence(factory["workshops"], "workshops")):
        workshop = _mapping(raw_workshop, f"workshops[{index}]")
        _exact(workshop, _WORKSHOP_FIELDS, f"workshops[{index}]")
        workshop_id = _text(workshop["workshop_id"], f"workshops[{index}].workshop_id")
        line_id = _text(
            workshop["production_line_id"],
            f"workshops[{index}].production_line_id",
        )
        if workshop_id in workshop_ids or line_id in production_line_ids:
            raise DemoAssetError("workshop and production-line IDs must be unique")
        workshop_ids.add(workshop_id)
        production_line_ids.add(line_id)

    calendar = _mapping(factory["working_calendar"], "working_calendar")
    _exact(
        calendar,
        {"weekday_shift_local", "saturday_shift_local", "sunday_available"},
        "working_calendar",
    )
    if calendar["sunday_available"] is not False:
        raise DemoAssetError("v1 Demo calendar requires Sunday unavailable")
    for name in ("weekday_shift_local", "saturday_shift_local"):
        shift = _mapping(calendar[name], f"working_calendar.{name}")
        _exact(shift, _SHIFT_FIELDS, f"working_calendar.{name}")
        try:
            start = time.fromisoformat(_text(shift["start"], f"{name}.start"))
            end = time.fromisoformat(_text(shift["end"], f"{name}.end"))
        except ValueError as error:
            raise DemoAssetError(f"{name} must use ISO local times") from error
        if start >= end:
            raise DemoAssetError(f"{name} start must precede end")

    resources = _sequence(catalog["resources"], "resources")
    resource_ids: set[str] = set()
    group_ids: set[str] = set()
    for index, raw_group in enumerate(_sequence(factory["resource_groups"], "resource_groups")):
        group = _mapping(raw_group, f"resource_groups[{index}]")
        _exact(group, _GROUP_FIELDS, f"resource_groups[{index}]")
        group_id = _text(group["resource_group_id"], f"resource_groups[{index}].resource_group_id")
        if group_id in group_ids:
            raise DemoAssetError("resource group IDs must be unique")
        if group["production_line_id"] not in production_line_ids:
            raise DemoAssetError("resource group references an unknown production line")
        group_ids.add(group_id)
    for index, raw_resource in enumerate(resources):
        resource = _mapping(raw_resource, f"resources[{index}]")
        _exact(resource, _RESOURCE_FIELDS, f"resources[{index}]")
        resource_id = _text(resource["resource_id"], f"resources[{index}].resource_id")
        if resource_id in resource_ids:
            raise DemoAssetError(f"duplicate resource_id: {resource_id}")
        resource_ids.add(resource_id)
        if resource["resource_group_id"] not in group_ids:
            raise DemoAssetError(f"resource {resource_id} references an unknown group")
        capabilities = _sequence(resource["capabilities"], f"resources[{index}].capabilities")
        if (
            not capabilities
            or any(not isinstance(item, str) or not item for item in capabilities)
            or len(capabilities) != len(set(capabilities))
        ):
            raise DemoAssetError(f"resource {resource_id} has invalid capabilities")

    profile_resources = _mapping(catalog["profile_resource_ids"], "profile_resource_ids")
    for name, ids in profile_resources.items():
        selected = tuple(_sequence(ids, f"profile_resource_ids.{name}"))
        if len(selected) != len(set(selected)) or not set(selected).issubset(resource_ids):
            raise DemoAssetError(f"resource profile {name} is duplicated or unknown")

    tick_seconds = _positive_int(durations["tick_seconds"], "tick_seconds")
    minimum_duration = _positive_int(
        durations["minimum_final_duration_seconds"], "minimum_final_duration_seconds"
    )
    if minimum_duration % tick_seconds:
        raise DemoAssetError("minimum final duration must be tick-aligned")
    variations = _sequence(durations["resource_variation_steps"], "resource_variation_steps")
    if tuple(variations) != (-1, 0, 1):
        raise DemoAssetError("v1 resource variation steps must be exactly -1, 0, 1")
    parameters = _mapping(durations["parameters"], "duration parameters")
    for name, raw_parameter in parameters.items():
        parameter = _mapping(raw_parameter, f"parameters.{name}")
        _exact(parameter, _DURATION_FIELDS, f"parameters.{name}")
        setup = _positive_int(
            parameter["setup_seconds"], f"parameters.{name}.setup_seconds", allow_zero=True
        )
        cycle = _positive_int(
            parameter["cycle_seconds_per_unit"],
            f"parameters.{name}.cycle_seconds_per_unit",
        )
        if setup % tick_seconds or cycle % tick_seconds:
            raise DemoAssetError(f"duration parameter {name} must be tick-aligned")
    template_lengths: set[int] = set()
    for index, raw_template in enumerate(_sequence(routes["templates"], "templates")):
        template = _mapping(raw_template, f"templates[{index}]")
        _exact(template, {"template_id", "product_family_zh", "steps"}, f"templates[{index}]")
        steps = _sequence(template["steps"], f"templates[{index}].steps")
        template_lengths.add(len(steps))
        for step_index, raw_step in enumerate(steps, start=1):
            step = _mapping(raw_step, f"templates[{index}].steps[{step_index - 1}]")
            _exact(step, _STEP_FIELDS, f"templates[{index}].steps[{step_index - 1}]")
            if step["step_index"] != step_index:
                raise DemoAssetError("route step indexes must be contiguous and one-based")
            if step["duration_key"] not in parameters:
                raise DemoAssetError("route step references an unknown duration key")
    if template_lengths != {3, 4, 5, 6}:
        raise DemoAssetError("route template pack must contain lengths 3 through 6")

    classes = _sequence(priority["classes"], "priority classes")
    class_ids: set[str] = set()
    for index, raw_class in enumerate(classes):
        item = _mapping(raw_class, f"classes[{index}]")
        _exact(item, {"class_id", "label_zh", "priority_weight"}, f"classes[{index}]")
        class_ids.add(_text(item["class_id"], f"classes[{index}].class_id"))
        _positive_int(item["priority_weight"], f"classes[{index}].priority_weight")
    if len(class_ids) != len(classes):
        raise DemoAssetError("priority class IDs must be unique")

    if maintenance["timezone"] != factory_timezone:
        raise DemoAssetError("maintenance timezone differs from the factory timezone")
    maintenance_intervals: dict[str, list[tuple[datetime, datetime]]] = {}
    event_ids: set[str] = set()
    for index, raw_event in enumerate(_sequence(maintenance["events"], "maintenance events")):
        event = _mapping(raw_event, f"events[{index}]")
        _exact(event, {"event_id", "resource_id", "start_local", "end_local", "reason"}, f"events[{index}]")
        event_id = _text(event["event_id"], f"events[{index}].event_id")
        if event_id in event_ids:
            raise DemoAssetError("maintenance event IDs must be unique")
        event_ids.add(event_id)
        if event["resource_id"] not in resource_ids:
            raise DemoAssetError("maintenance event references an unknown resource")
        try:
            start = datetime.fromisoformat(
                _text(event["start_local"], f"events[{index}].start_local")
            )
            end = datetime.fromisoformat(
                _text(event["end_local"], f"events[{index}].end_local")
            )
        except ValueError as error:
            raise DemoAssetError("maintenance timestamps must be ISO instants") from error
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or start.utcoffset() != start.astimezone(timezone).utcoffset()
            or end.utcoffset() != end.astimezone(timezone).utcoffset()
            or start >= end
        ):
            raise DemoAssetError("maintenance interval timezone or ordering is invalid")
        epoch = datetime(1970, 1, 1, tzinfo=start.tzinfo)
        if (
            int((start - epoch).total_seconds()) % tick_seconds
            or int((end - epoch).total_seconds()) % tick_seconds
        ):
            raise DemoAssetError("maintenance intervals must be tick-aligned")
        intervals = maintenance_intervals.setdefault(str(event["resource_id"]), [])
        if any(start < existing_end and existing_start < end for existing_start, existing_end in intervals):
            raise DemoAssetError("maintenance intervals on one resource must not overlap")
        intervals.append((start, end))

    profile_path = demo_root / "benchmarks" / "profiles.json"
    if manifest["benchmark_profiles_sha256"] != sha256(profile_path.read_bytes()).hexdigest():
        raise DemoAssetError("benchmark profile digest differs from the asset manifest")
    profile_document = _load_json(profile_path)
    _exact(profile_document, {"benchmark_profile_set_version", "profiles"}, "benchmark profiles")
    if profile_document["benchmark_profile_set_version"] != "cnc-demo-benchmark-profiles.v1":
        raise DemoAssetError("unsupported CNC demo benchmark profile version")
    raw_profiles = _mapping(profile_document["profiles"], "profiles")
    profiles = MappingProxyType(
        {name: _parse_profile(name, _mapping(raw, f"profiles.{name}")) for name, raw in raw_profiles.items()}
    )
    _validate_profiles(profiles, profile_resources, class_ids)
    for name, profile in profiles.items():
        try:
            anchor = datetime.fromisoformat(profile.anchor_at_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise DemoAssetError(f"profile {name} anchor must be an ISO instant") from error
        if anchor.tzinfo is None or anchor.utcoffset() != timedelta(0):
            raise DemoAssetError(f"profile {name} anchor must be UTC")
        if int(anchor.timestamp()) % tick_seconds:
            raise DemoAssetError(f"profile {name} anchor must be tick-aligned")
    if manifest["default_profile"] not in profiles:
        raise DemoAssetError("manifest.default_profile is unknown")
    if any(profile.seed != manifest["fixed_seed"] for profile in profiles.values()):
        raise DemoAssetError("every v1 profile must preserve the fixed manifest seed")

    digest = sha256()
    for path in [asset_root / "manifest.json", *(asset_root / name for name in declared_files), profile_path]:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    return DemoAssets(
        root=asset_root,
        manifest=MappingProxyType(dict(manifest)),
        factory=MappingProxyType(dict(factory)),
        resource_catalog=MappingProxyType(dict(catalog)),
        route_templates=MappingProxyType(dict(routes)),
        duration_parameters=MappingProxyType(dict(durations)),
        priority_policy=MappingProxyType(dict(priority)),
        maintenance_plan=MappingProxyType(dict(maintenance)),
        profiles=profiles,
        asset_digest=digest.hexdigest(),
    )


__all__ = [
    "BenchmarkProfile",
    "DemoAssetError",
    "DemoAssets",
    "load_demo_assets",
]
