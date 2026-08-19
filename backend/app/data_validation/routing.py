"""Routing DAG, time, duration, unit, calendar, and fact validation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite

from app.domain.errors import ProductErrorCodeV2
from app.domain.types import ContractValueError, canonical_id, parse_utc_instant

from .contracts import IssueCollector, stable_fingerprint
from .references import CanonicalView, add_record_issue


_TEXT_FIELDS: Mapping[str, tuple[str, ...]] = {
    "factories": ("factory_code", "factory_timezone"),
    "workshops": ("workshop_code",),
    "production_lines": ("production_line_code",),
    "resource_groups": ("resource_group_code",),
    "resources": ("resource_code", "resource_type", "status"),
    "calendars": ("timezone",),
    "products": ("product_code", "quantity_unit"),
    "routing_versions": ("routing_code", "version"),
    "routing_operations": ("operation_code",),
}
_UNIT_COLLECTIONS = (
    "products",
    "routing_resource_options",
    "demand_orders",
    "production_orders",
    "production_lots",
    "execution_facts",
)


def validate_routing_and_values(view: CanonicalView, issues: IssueCollector) -> None:
    """Collect deterministic semantic issues without constructing schedule objects."""

    _validate_text_and_units(view, issues)
    _validate_quantities(view, issues)
    _validate_calendar_intervals(view, issues)
    _validate_routing_options(view, issues)
    _validate_routing_edges(view, issues)
    _validate_order_times(view, issues)
    _validate_execution_facts(view, issues)
    _validate_operation_locks(view, issues)
    _validate_unit_lineage(view, issues)
    _validate_route_dags(view, issues)


def _validate_text_and_units(view: CanonicalView, issues: IssueCollector) -> None:
    for collection, fields in _TEXT_FIELDS.items():
        for record in view.records(collection):
            for field in fields:
                if field not in record:
                    continue
                value = record.get(field)
                if not isinstance(value, str) or not value.strip():
                    code = (
                        ProductErrorCodeV2.UNIT_CONVERSION_ERROR
                        if field == "quantity_unit"
                        else ProductErrorCodeV2.INVALID_REFERENCE
                    )
                    add_record_issue(
                        issues,
                        view,
                        collection,
                        record,
                        code,
                        field=field,
                        observed_value=value,
                        expected_contract="non-empty explicit canonical text",
                        action=f"provide an authoritative {field} value",
                        message=f"Canonical {field} is invalid",
                    )
    for collection in _UNIT_COLLECTIONS:
        if collection == "products":
            continue
        for record in view.records(collection):
            if "quantity_unit" not in record:
                continue
            unit = record.get("quantity_unit")
            if not isinstance(unit, str) or not unit.strip():
                add_record_issue(
                    issues,
                    view,
                    collection,
                    record,
                    ProductErrorCodeV2.UNIT_CONVERSION_ERROR,
                    field="quantity_unit",
                    observed_value=unit,
                    expected_contract="non-empty explicit canonical quantity unit",
                    action="provide the normalized unit; no default is allowed",
                    message="Canonical quantity unit is invalid",
                )


def _validate_quantities(view: CanonicalView, issues: IssueCollector) -> None:
    for collection in (
        "demand_orders",
        "production_orders",
        "production_lots",
    ):
        for record in view.records(collection):
            _positive_quantity(view, issues, collection, record, "quantity")


def _positive_quantity(
    view: CanonicalView,
    issues: IssueCollector,
    collection: str,
    record: Mapping[str, object],
    field: str,
) -> float | None:
    if field not in record:
        return None
    value = record.get(field)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
        or (isinstance(value, float) and not isfinite(value))
    ):
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_ENTITY_COUNT,
            field=field,
            observed_value=value,
            expected_contract="finite positive canonical quantity",
            action="provide the explicit positive quantity from its authority",
            message="Canonical quantity is invalid",
        )
        return None
    return float(value)


def _duration(
    view: CanonicalView,
    issues: IssueCollector,
    collection: str,
    record: Mapping[str, object],
    field: str,
    *,
    positive: bool = False,
) -> int | None:
    if field not in record:
        return None
    value = record.get(field)
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_DURATION,
            field=field,
            observed_value=value,
            expected_contract=(
                "positive integer seconds" if positive else "non-negative integer seconds"
            ),
            action="repair the explicit duration without rounding or defaulting",
            message="Canonical duration is invalid",
        )
        return None
    return value


def _utc(
    view: CanonicalView,
    issues: IssueCollector,
    collection: str,
    record: Mapping[str, object],
    field: str,
) -> datetime | None:
    if field not in record:
        return None
    value = record.get(field)
    if not isinstance(value, str):
        parsed = None
    else:
        try:
            parsed = parse_utc_instant(value)
        except ContractValueError:
            parsed = None
    if parsed is None:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_TIME,
            field=field,
            observed_value=value,
            expected_contract="RFC 3339 UTC instant ending in Z",
            action="normalize the authoritative instant before validation",
            message="Canonical time value is invalid",
        )
    return parsed


def _validate_calendar_intervals(view: CanonicalView, issues: IssueCollector) -> None:
    for calendar in view.records("calendars"):
        raw_intervals = calendar.get("unavailable_intervals")
        if not isinstance(raw_intervals, list):
            if "unavailable_intervals" in calendar:
                add_record_issue(
                    issues,
                    view,
                    "calendars",
                    calendar,
                    ProductErrorCodeV2.INVALID_TIME_RANGE,
                    field="unavailable_intervals",
                    observed_value=raw_intervals,
                    expected_contract="explicit array of unavailable intervals",
                    action="provide a valid interval array, using [] when empty",
                    message="Calendar unavailable intervals are invalid",
                )
            continue
        normalized: list[tuple[datetime, datetime, str]] = []
        seen_ids: set[str] = set()
        ordered = sorted(raw_intervals, key=lambda item: stable_fingerprint(item))
        for raw_interval in ordered:
            if not isinstance(raw_interval, Mapping):
                add_record_issue(
                    issues,
                    view,
                    "calendars",
                    calendar,
                    ProductErrorCodeV2.INVALID_TIME_RANGE,
                    field="unavailable_intervals",
                    observed_value=raw_interval,
                    expected_contract="calendar interval object",
                    action="replace the invalid interval item",
                    message="Calendar contains a non-object interval",
                )
                continue
            interval_id_value = raw_interval.get("interval_id")
            try:
                interval_id = (
                    str(canonical_id(interval_id_value))
                    if isinstance(interval_id_value, str)
                    else None
                )
            except ContractValueError:
                interval_id = None
            interval_token = interval_id or f"interval-{stable_fingerprint(raw_interval)}"
            exact_fields = {"interval_id", "start_at_utc", "end_at_utc", "reason"}
            if set(raw_interval) != exact_fields:
                add_record_issue(
                    issues,
                    view,
                    "calendars",
                    calendar,
                    ProductErrorCodeV2.INVALID_TIME_RANGE,
                    field=f"unavailable_intervals.{interval_token}",
                    observed_value={
                        "missing": sorted(exact_fields - set(raw_interval)),
                        "unknown": sorted(set(raw_interval) - exact_fields),
                    },
                    expected_contract="exact interval_id/start/end/reason fields",
                    action="repair the strict calendar interval shape",
                    message="Calendar interval fields are invalid",
                )
            if interval_id is None:
                add_record_issue(
                    issues,
                    view,
                    "calendars",
                    calendar,
                    ProductErrorCodeV2.INVALID_REFERENCE,
                    field=f"unavailable_intervals.{interval_token}.interval_id",
                    observed_value=interval_id_value,
                    expected_contract="canonical interval ID unique within the calendar",
                    action="provide a stable valid interval ID",
                    message="Calendar interval ID is invalid",
                )
            elif interval_id in seen_ids:
                add_record_issue(
                    issues,
                    view,
                    "calendars",
                    calendar,
                    ProductErrorCodeV2.DUPLICATE_ID,
                    field=f"unavailable_intervals.{interval_id}.interval_id",
                    observed_value=interval_id,
                    expected_contract="unique interval ID within one calendar",
                    action="deduplicate calendar intervals",
                    message="Calendar interval ID is duplicated",
                )
            else:
                seen_ids.add(interval_id)
            start = _nested_utc(
                view,
                issues,
                calendar,
                interval_token,
                raw_interval,
                "start_at_utc",
            )
            end = _nested_utc(
                view,
                issues,
                calendar,
                interval_token,
                raw_interval,
                "end_at_utc",
            )
            if start is not None and end is not None:
                if start >= end:
                    add_record_issue(
                        issues,
                        view,
                        "calendars",
                        calendar,
                        ProductErrorCodeV2.INVALID_TIME_RANGE,
                        field=f"unavailable_intervals.{interval_token}.end_at_utc",
                        observed_value={
                            "start_at_utc": raw_interval.get("start_at_utc"),
                            "end_at_utc": raw_interval.get("end_at_utc"),
                        },
                        expected_contract="calendar interval end strictly follows start",
                        action="repair the explicit unavailable interval range",
                        message="Calendar interval range is not increasing",
                    )
                else:
                    normalized.append((start, end, interval_token))
        normalized.sort(key=lambda item: (item[0], item[1], item[2]))
        active: tuple[datetime, datetime, str] | None = None
        for interval in normalized:
            if active is not None and interval[0] < active[1]:
                add_record_issue(
                    issues,
                    view,
                    "calendars",
                    calendar,
                    ProductErrorCodeV2.INVALID_TIME_RANGE,
                    field="unavailable_intervals",
                    observed_value={"overlap": sorted([active[2], interval[2]])},
                    expected_contract="non-overlapping explicit unavailable intervals",
                    action="merge or disambiguate overlapping authoritative intervals",
                    message="Calendar unavailable intervals overlap",
                )
            if active is None or interval[1] > active[1]:
                active = interval


def _nested_utc(
    view: CanonicalView,
    issues: IssueCollector,
    calendar: Mapping[str, object],
    interval_token: str,
    interval: Mapping[str, object],
    field: str,
) -> datetime | None:
    value = interval.get(field)
    if not isinstance(value, str):
        parsed = None
    else:
        try:
            parsed = parse_utc_instant(value)
        except ContractValueError:
            parsed = None
    if parsed is None:
        add_record_issue(
            issues,
            view,
            "calendars",
            calendar,
            ProductErrorCodeV2.INVALID_TIME,
            field=f"unavailable_intervals.{interval_token}.{field}",
            observed_value=value,
            expected_contract="RFC 3339 UTC instant ending in Z",
            action="normalize the calendar instant before validation",
            message="Calendar interval time is missing or invalid",
        )
    return parsed


def _validate_routing_options(view: CanonicalView, issues: IssueCollector) -> None:
    logical_options: dict[tuple[object, object], list[Mapping[str, object]]] = {}
    for option in view.records("routing_resource_options"):
        for field, positive in (
            ("setup_seconds", False),
            ("cycle_seconds_per_unit", False),
            ("final_duration_seconds", True),
        ):
            _duration(
                view,
                issues,
                "routing_resource_options",
                option,
                field,
                positive=positive,
            )
        for field in ("duration_source", "duration_source_version"):
            if field not in option:
                continue
            value = option.get(field)
            if not isinstance(value, str) or not value.strip():
                add_record_issue(
                    issues,
                    view,
                    "routing_resource_options",
                    option,
                    ProductErrorCodeV2.MISSING_DURATION,
                    field=field,
                    observed_value=value,
                    expected_contract="non-empty versioned duration provenance",
                    action="provide the authoritative duration source and exact version",
                    message="Resource option duration provenance is missing",
                )
        key = (option.get("routing_operation_id"), option.get("resource_id"))
        logical_options.setdefault(key, []).append(option)
    for key, matching in sorted(logical_options.items(), key=lambda item: str(item[0])):
        if len(matching) < 2:
            continue
        add_record_issue(
            issues,
            view,
            "routing_resource_options",
            matching[0],
            ProductErrorCodeV2.DUPLICATE_ID,
            field="routing_operation_id/resource_id",
            observed_value={"pair": list(key), "count": len(matching)},
            expected_contract="at most one option per routing operation and resource",
            action="deduplicate the logical resource option",
            message="Routing operation/resource option is duplicated",
        )


def _validate_routing_edges(view: CanonicalView, issues: IssueCollector) -> None:
    logical_edges: dict[tuple[object, object, object], list[Mapping[str, object]]] = {}
    for edge in view.records("routing_precedence_edges"):
        minimum = _duration(
            view,
            issues,
            "routing_precedence_edges",
            edge,
            "min_lag_seconds",
        )
        _duration(
            view,
            issues,
            "routing_precedence_edges",
            edge,
            "transport_lag_seconds",
        )
        maximum = (
            _duration(
                view,
                issues,
                "routing_precedence_edges",
                edge,
                "max_lag_seconds",
            )
            if "max_lag_seconds" in edge
            else None
        )
        if minimum is not None and maximum is not None and maximum < minimum:
            add_record_issue(
                issues,
                view,
                "routing_precedence_edges",
                edge,
                ProductErrorCodeV2.INVALID_LAG_RANGE,
                field="max_lag_seconds",
                observed_value={"minimum": minimum, "maximum": maximum},
                expected_contract="max_lag_seconds >= min_lag_seconds",
                action="repair the explicit routing lag bounds",
                message="Routing maximum lag is below its minimum lag",
            )
        key = (
            edge.get("routing_version_id"),
            edge.get("predecessor_routing_operation_id"),
            edge.get("successor_routing_operation_id"),
        )
        logical_edges.setdefault(key, []).append(edge)
    for key, matching in sorted(logical_edges.items(), key=lambda item: str(item[0])):
        if len(matching) < 2:
            continue
        add_record_issue(
            issues,
            view,
            "routing_precedence_edges",
            matching[0],
            ProductErrorCodeV2.DUPLICATE_ID,
            field="routing_version_id/predecessor/successor",
            observed_value={"edge": list(key), "count": len(matching)},
            expected_contract="one logical directed edge per routing version",
            action="deduplicate the routing edge",
            message="Logical routing precedence edge is duplicated",
        )


def _validate_order_times(view: CanonicalView, issues: IssueCollector) -> None:
    for demand in view.records("demand_orders"):
        _utc(view, issues, "demand_orders", demand, "due_at_utc")
    for order in view.records("production_orders"):
        _utc(view, issues, "production_orders", order, "release_at_utc")
        _utc(view, issues, "production_orders", order, "material_ready_at_utc")


def _validate_execution_facts(view: CanonicalView, issues: IssueCollector) -> None:
    logical: dict[tuple[object, object], list[Mapping[str, object]]] = {}
    for fact in view.records("execution_facts"):
        status = fact.get("status")
        _utc(view, issues, "execution_facts", fact, "observed_at_utc")
        start = _utc(
            view, issues, "execution_facts", fact, "actual_start_at_utc"
        )
        end = _utc(view, issues, "execution_facts", fact, "actual_end_at_utc")
        if start is not None and end is not None and start >= end:
            add_record_issue(
                issues,
                view,
                "execution_facts",
                fact,
                ProductErrorCodeV2.INVALID_TIME_RANGE,
                field="actual_end_at_utc",
                observed_value={
                    "actual_start_at_utc": fact.get("actual_start_at_utc"),
                    "actual_end_at_utc": fact.get("actual_end_at_utc"),
                },
                expected_contract="execution end strictly follows start",
                action="repair the authoritative execution interval",
                message="Execution fact interval is not increasing",
            )
        if status == "RUNNING":
            required = {
                "resource_id",
                "actual_start_at_utc",
                "remaining_quantity",
                "remaining_seconds",
            }
            forbidden = {"actual_end_at_utc", "completed_quantity"}
            _positive_quantity(
                view, issues, "execution_facts", fact, "remaining_quantity"
            )
            _duration(
                view,
                issues,
                "execution_facts",
                fact,
                "remaining_seconds",
                positive=True,
            )
        elif status == "COMPLETED":
            required = {
                "resource_id",
                "actual_start_at_utc",
                "actual_end_at_utc",
                "completed_quantity",
            }
            forbidden = {"remaining_quantity", "remaining_seconds"}
            _positive_quantity(
                view, issues, "execution_facts", fact, "completed_quantity"
            )
        else:
            required = set()
            forbidden = set()
            add_record_issue(
                issues,
                view,
                "execution_facts",
                fact,
                ProductErrorCodeV2.MISSING_RUNNING_FACT,
                field="status",
                observed_value=status,
                expected_contract="RUNNING or COMPLETED execution fact status",
                action="provide a valid explicit execution status",
                message="Execution fact status is invalid",
            )
        for field in sorted(required - set(fact)):
            code = (
                ProductErrorCodeV2.MISSING_DURATION
                if field == "remaining_seconds"
                else ProductErrorCodeV2.MISSING_RUNNING_FACT
            )
            add_record_issue(
                issues,
                view,
                "execution_facts",
                fact,
                code,
                field=field,
                observed_value=None,
                expected_contract=f"{status} execution fact requires {field}",
                action=f"provide the authoritative {field}",
                message="Execution fact is incomplete for its status",
            )
        present_forbidden = sorted(forbidden & set(fact))
        if present_forbidden:
            add_record_issue(
                issues,
                view,
                "execution_facts",
                fact,
                ProductErrorCodeV2.MISSING_RUNNING_FACT,
                field="status-specific fields",
                observed_value=present_forbidden,
                expected_contract=f"fields allowed for {status} execution facts",
                action="remove fields that conflict with the execution status",
                message="Execution fact carries fields forbidden by its status",
            )
        key = (fact.get("production_lot_id"), fact.get("routing_operation_id"))
        logical.setdefault(key, []).append(fact)
    for key, matching in sorted(logical.items(), key=lambda item: str(item[0])):
        if len(matching) < 2:
            continue
        add_record_issue(
            issues,
            view,
            "execution_facts",
            matching[0],
            ProductErrorCodeV2.DUPLICATE_ID,
            field="production_lot_id/routing_operation_id",
            observed_value={"pair": list(key), "count": len(matching)},
            expected_contract="at most one current fact per lot and routing operation",
            action="resolve duplicate current execution facts",
            message="Execution fact lineage is duplicated",
        )


def _validate_operation_locks(view: CanonicalView, issues: IssueCollector) -> None:
    logical: dict[tuple[object, object, object], list[Mapping[str, object]]] = {}
    for lock in view.records("operation_locks"):
        lock_type = lock.get("lock_type")
        if lock_type not in {"HARD_LOCK", "SOFT_LOCK"}:
            add_record_issue(
                issues,
                view,
                "operation_locks",
                lock,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field="lock_type",
                observed_value=lock_type,
                expected_contract="HARD_LOCK or SOFT_LOCK",
                action="provide the explicit supported lock type",
                message="Operation lock type is invalid",
            )
        start = _utc(view, issues, "operation_locks", lock, "start_at_utc")
        end = _utc(view, issues, "operation_locks", lock, "end_at_utc")
        if start is not None and end is not None and start >= end:
            add_record_issue(
                issues,
                view,
                "operation_locks",
                lock,
                ProductErrorCodeV2.INVALID_TIME_RANGE,
                field="end_at_utc",
                observed_value={
                    "start_at_utc": lock.get("start_at_utc"),
                    "end_at_utc": lock.get("end_at_utc"),
                },
                expected_contract="lock end strictly follows start",
                action="repair the authoritative lock interval",
                message="Operation lock interval is not increasing",
            )
        key = (
            lock.get("production_lot_id"),
            lock.get("routing_operation_id"),
            lock_type,
        )
        logical.setdefault(key, []).append(lock)
    for key, matching in sorted(logical.items(), key=lambda item: str(item[0])):
        if len(matching) < 2:
            continue
        add_record_issue(
            issues,
            view,
            "operation_locks",
            matching[0],
            ProductErrorCodeV2.DUPLICATE_ID,
            field="production_lot_id/routing_operation_id/lock_type",
            observed_value={"lock": list(key), "count": len(matching)},
            expected_contract="at most one lock of each type per lot operation",
            action="resolve duplicate operation locks",
            message="Logical operation lock is duplicated",
        )


def _validate_unit_lineage(view: CanonicalView, issues: IssueCollector) -> None:
    for demand in view.records("demand_orders"):
        product = view.get("products", demand.get("product_id"))
        if product is not None:
            _same_unit(view, issues, "demand_orders", demand, product.get("quantity_unit"))
    for order in view.records("production_orders"):
        demand = view.get("demand_orders", order.get("demand_order_id"))
        if demand is not None:
            _same_unit(view, issues, "production_orders", order, demand.get("quantity_unit"))
    for lot in view.records("production_lots"):
        order = view.get("production_orders", lot.get("production_order_id"))
        if order is not None:
            _same_unit(view, issues, "production_lots", lot, order.get("quantity_unit"))
    for fact in view.records("execution_facts"):
        lot = view.get("production_lots", fact.get("production_lot_id"))
        if lot is not None:
            _same_unit(view, issues, "execution_facts", fact, lot.get("quantity_unit"))
    for option in view.records("routing_resource_options"):
        operation = view.get("routing_operations", option.get("routing_operation_id"))
        if operation is None:
            continue
        route = view.get("routing_versions", operation.get("routing_version_id"))
        if route is None:
            continue
        product = view.get("products", route.get("product_id"))
        if product is not None:
            _same_unit(
                view,
                issues,
                "routing_resource_options",
                option,
                product.get("quantity_unit"),
            )


def _same_unit(
    view: CanonicalView,
    issues: IssueCollector,
    collection: str,
    record: Mapping[str, object],
    expected: object,
) -> None:
    observed = record.get("quantity_unit")
    if (
        not isinstance(observed, str)
        or not observed
        or not isinstance(expected, str)
        or not expected
    ):
        return
    if observed != expected:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.UNIT_CONVERSION_ERROR,
            field="quantity_unit",
            observed_value={"observed": observed, "expected": expected},
            expected_contract="quantity unit exactly matches its canonical lineage authority",
            action="apply an explicit versioned unit conversion before validation",
            message="Canonical quantity unit is inconsistent with its lineage",
        )


def _validate_route_dags(view: CanonicalView, issues: IssueCollector) -> None:
    operations_by_route: dict[str, set[str]] = {}
    for operation in view.records("routing_operations"):
        route_id = operation.get("routing_version_id")
        operation_id = operation.get("routing_operation_id")
        if isinstance(route_id, str) and isinstance(operation_id, str):
            if view.get("routing_versions", route_id) is not None:
                operations_by_route.setdefault(route_id, set()).add(operation_id)
    edges_by_route: dict[str, set[tuple[str, str]]] = {}
    for edge in view.records("routing_precedence_edges"):
        route_id = edge.get("routing_version_id")
        predecessor = edge.get("predecessor_routing_operation_id")
        successor = edge.get("successor_routing_operation_id")
        if not all(isinstance(value, str) for value in (route_id, predecessor, successor)):
            continue
        route_text = str(route_id)
        predecessor_text = str(predecessor)
        successor_text = str(successor)
        nodes = operations_by_route.get(route_text)
        if nodes is None or predecessor_text not in nodes or successor_text not in nodes:
            continue
        edges_by_route.setdefault(route_text, set()).add(
            (predecessor_text, successor_text)
        )
    for route_id, nodes in sorted(operations_by_route.items()):
        route = view.get("routing_versions", route_id)
        if route is None:
            continue
        edges = edges_by_route.get(route_id, set())
        adjacency = {node: set() for node in nodes}
        for predecessor, successor in edges:
            adjacency[predecessor].add(successor)
        for component in _cyclic_components(nodes, adjacency):
            add_record_issue(
                issues,
                view,
                "routing_versions",
                route,
                ProductErrorCodeV2.ROUTE_CYCLE,
                field="routing_precedence_edges",
                observed_value={
                    "routing_version_id": route_id,
                    "cycle_operation_ids": list(component),
                },
                expected_contract="directed acyclic graph per routing version",
                action="remove or redirect at least one edge in the reported cycle",
                message="Routing version contains a directed cycle",
            )


def _cyclic_components(
    nodes: set[str], adjacency: Mapping[str, set[str]]
) -> tuple[tuple[str, ...], ...]:
    finish_order: list[str] = []
    visited: set[str] = set()
    for root in sorted(nodes):
        if root in visited:
            continue
        stack: list[tuple[str, bool]] = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                finish_order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            for neighbor in sorted(adjacency.get(node, set()), reverse=True):
                if neighbor not in visited:
                    stack.append((neighbor, False))
    transpose = {node: set() for node in nodes}
    for predecessor, successors in adjacency.items():
        for successor in successors:
            transpose[successor].add(predecessor)
    assigned: set[str] = set()
    cyclic: list[tuple[str, ...]] = []
    for root in reversed(finish_order):
        if root in assigned:
            continue
        component: list[str] = []
        component_stack = [root]
        assigned.add(root)
        while component_stack:
            node = component_stack.pop()
            component.append(node)
            for neighbor in sorted(transpose.get(node, set()), reverse=True):
                if neighbor not in assigned:
                    assigned.add(neighbor)
                    component_stack.append(neighbor)
        ordered = tuple(sorted(component))
        if not ordered:
            continue
        first = component[0]
        if len(ordered) > 1 or first in adjacency.get(first, set()):
            cyclic.append(ordered)
    return tuple(sorted(cyclic))


__all__ = ["validate_routing_and_values"]
