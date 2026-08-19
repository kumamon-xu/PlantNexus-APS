"""Pure JSON-compatible P1 canonical import and Snapshot v2 contracts.

The types and prechecks in this module are authority-neutral. They validate
explicit values and references only; they do not parse source files, normalize
units, invent lots or durations, build Snapshots, or perform Solver work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from typing import Literal, NoReturn, NotRequired, TypedDict, cast

from app.domain.errors import ProductErrorCode
from app.domain.types import (
    ContractValueError,
    canonical_id,
    parse_utc_instant,
    require_duration_seconds,
)


class SourceReference(TypedDict):
    source_system: str
    source_version: str
    source_record_id: str


class UnavailableIntervalRecord(TypedDict):
    interval_id: str
    start_at_utc: str
    end_at_utc: str
    reason: str


class FactoryRecord(TypedDict):
    factory_id: str
    factory_code: str
    factory_timezone: str
    source: SourceReference


class WorkshopRecord(TypedDict):
    workshop_id: str
    workshop_code: str
    factory_id: str
    source: SourceReference


class ProductionLineRecord(TypedDict):
    production_line_id: str
    production_line_code: str
    workshop_id: str
    source: SourceReference


class ResourceGroupRecord(TypedDict):
    resource_group_id: str
    resource_group_code: str
    production_line_id: str
    source: SourceReference


class ResourceRecord(TypedDict):
    resource_id: str
    resource_code: str
    resource_type: str
    status: str
    resource_group_id: str
    calendar_id: str
    capabilities: list[str]
    source: SourceReference


class CalendarRecord(TypedDict):
    calendar_id: str
    timezone: str
    unavailable_intervals: list[UnavailableIntervalRecord]
    source: SourceReference


class ProductRecord(TypedDict):
    product_id: str
    product_code: str
    quantity_unit: str
    source: SourceReference


class RoutingVersionRecord(TypedDict):
    routing_version_id: str
    routing_code: str
    version: str
    product_id: str
    source: SourceReference


class RoutingOperationRecord(TypedDict):
    routing_operation_id: str
    routing_version_id: str
    operation_code: str
    required_capabilities: list[str]
    source: SourceReference


class RoutingPrecedenceEdgeRecord(TypedDict):
    routing_precedence_edge_id: str
    routing_version_id: str
    predecessor_routing_operation_id: str
    successor_routing_operation_id: str
    min_lag_seconds: int
    transport_lag_seconds: int
    source: SourceReference
    max_lag_seconds: NotRequired[int]


class RoutingResourceOptionRecord(TypedDict):
    routing_resource_option_id: str
    routing_operation_id: str
    resource_id: str
    quantity_unit: str
    setup_seconds: int
    cycle_seconds_per_unit: int
    final_duration_seconds: int
    duration_source: str
    duration_source_version: str
    source: SourceReference


class DemandOrderRecord(TypedDict):
    demand_order_id: str
    product_id: str
    quantity: int | float
    quantity_unit: str
    due_at_utc: str
    source: SourceReference


class ProductionOrderRecord(TypedDict):
    production_order_id: str
    demand_order_id: str
    routing_version_id: str
    quantity: int | float
    quantity_unit: str
    release_at_utc: str
    material_ready_at_utc: str
    source: SourceReference


class ProductionLotRecord(TypedDict):
    production_lot_id: str
    production_order_id: str
    quantity: int | float
    quantity_unit: str
    source: SourceReference


class ExecutionFactRecord(TypedDict):
    execution_fact_id: str
    production_lot_id: str
    routing_operation_id: str
    status: Literal["RUNNING", "COMPLETED"]
    observed_at_utc: str
    quantity_unit: str
    source: SourceReference
    resource_id: NotRequired[str]
    actual_start_at_utc: NotRequired[str]
    actual_end_at_utc: NotRequired[str]
    completed_quantity: NotRequired[int | float]
    remaining_quantity: NotRequired[int | float]
    remaining_seconds: NotRequired[int]


class OperationLockRecord(TypedDict):
    lock_id: str
    production_lot_id: str
    routing_operation_id: str
    lock_type: Literal["HARD_LOCK", "SOFT_LOCK"]
    resource_id: str
    start_at_utc: str
    end_at_utc: str
    source: SourceReference


class CanonicalRecordsDocument(TypedDict):
    canonical_records_version: Literal["canonical-records.v1"]
    factories: list[FactoryRecord]
    workshops: list[WorkshopRecord]
    production_lines: list[ProductionLineRecord]
    resource_groups: list[ResourceGroupRecord]
    resources: list[ResourceRecord]
    calendars: list[CalendarRecord]
    products: list[ProductRecord]
    routing_versions: list[RoutingVersionRecord]
    routing_operations: list[RoutingOperationRecord]
    routing_precedence_edges: list[RoutingPrecedenceEdgeRecord]
    routing_resource_options: list[RoutingResourceOptionRecord]
    demand_orders: list[DemandOrderRecord]
    production_orders: list[ProductionOrderRecord]
    production_lots: list[ProductionLotRecord]
    execution_facts: list[ExecutionFactRecord]
    operation_locks: list[OperationLockRecord]


class SyntheticProvenance(TypedDict):
    scenario_id: str
    scenario_version: str
    seed: int
    factory_profile_id: str
    profile_version: str
    generator_id: str
    generator_version: str


class ImportPackageDocumentV2(TypedDict):
    import_package_version: Literal["import-package.v2"]
    schema_set_version: Literal["2.0.0"]
    package_id: str
    source_versions: dict[str, str]
    normalization_rule_version: str
    canonicalization_version: str
    synthetic: bool
    records: CanonicalRecordsDocument
    synthetic_provenance: NotRequired[SyntheticProvenance]


class OperationResourceOptionDocument(TypedDict):
    routing_resource_option_id: str
    resource_id: str
    setup_seconds: int
    cycle_seconds_per_unit: int
    final_duration_seconds: int
    duration_source: str
    source_version: str


class OperationInstanceDocument(TypedDict):
    operation_instance_id: str
    demand_order_id: str
    production_order_id: str
    production_lot_id: str
    routing_version_id: str
    routing_operation_id: str
    status: Literal["NOT_STARTED", "RUNNING", "COMPLETED"]
    quantity: int | float
    quantity_unit: str
    due_at_utc: str
    release_at_utc: str
    material_ready_at_utc: str
    required_capabilities: list[str]
    resource_options: list[OperationResourceOptionDocument]
    lock_ids: list[str]
    execution_fact_id: NotRequired[str]


class OperationPrecedenceEdgeDocument(TypedDict):
    operation_precedence_edge_id: str
    routing_precedence_edge_id: str
    predecessor_operation_instance_id: str
    successor_operation_instance_id: str
    min_lag_seconds: int
    transport_lag_seconds: int
    max_lag_seconds: NotRequired[int]


class ImportPackageReference(TypedDict):
    import_package_version: Literal["import-package.v2"]
    package_id: str
    dataset_hash: str


class ImportQualityReportReference(TypedDict):
    report_version: Literal["import-quality-report.v1"]
    report_id: str
    status: Literal["PASS"]


class PlanningSnapshotDocumentV2(TypedDict):
    snapshot_version: Literal["planning-snapshot.v2"]
    schema_set_version: Literal["2.0.0"]
    snapshot_id: str
    cutoff_at_utc: str
    source_versions: dict[str, str]
    rule_version: str
    normalization_rule_version: str
    expansion_version: str
    canonicalization_version: str
    import_package: ImportPackageReference
    import_quality_report: ImportQualityReportReference
    snapshot_hash: str
    entity_counts: dict[str, int]
    synthetic: bool
    records: CanonicalRecordsDocument
    operation_instances: list[OperationInstanceDocument]
    operation_precedence_edges: list[OperationPrecedenceEdgeDocument]
    synthetic_provenance: NotRequired[SyntheticProvenance]


class CanonicalContractError(ValueError):
    """One deterministic rejection from the P1 canonical contract precheck."""

    def __init__(self, code: ProductErrorCode, field: str, message: str) -> None:
        self.code = code.value
        self.field = field
        self.message = message
        super().__init__(f"{code.value} at {field}: {message}")


type Record = Mapping[str, object]

COLLECTION_ID_FIELDS: Mapping[str, str] = {
    "factories": "factory_id",
    "workshops": "workshop_id",
    "production_lines": "production_line_id",
    "resource_groups": "resource_group_id",
    "resources": "resource_id",
    "calendars": "calendar_id",
    "products": "product_id",
    "routing_versions": "routing_version_id",
    "routing_operations": "routing_operation_id",
    "routing_precedence_edges": "routing_precedence_edge_id",
    "routing_resource_options": "routing_resource_option_id",
    "demand_orders": "demand_order_id",
    "production_orders": "production_order_id",
    "production_lots": "production_lot_id",
    "execution_facts": "execution_fact_id",
    "operation_locks": "lock_id",
}


def _fail(code: ProductErrorCode, field: str, message: str) -> NoReturn:
    raise CanonicalContractError(code, field, message)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(
            ProductErrorCode.INVALID_REFERENCE,
            field,
            "value must be a non-empty string",
        )
    return value


def _identifier(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        canonical_id(text)
    except ContractValueError as error:
        _fail(ProductErrorCode.INVALID_REFERENCE, field, str(error))
    return text


def _utc(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        return parse_utc_instant(text)
    except ContractValueError as error:
        _fail(ProductErrorCode.INVALID_TIME, field, str(error))


def _duration(value: object, field: str, *, positive: bool = False) -> int:
    try:
        return int(require_duration_seconds(cast(int, value), allow_zero=not positive))
    except ContractValueError as error:
        _fail(ProductErrorCode.INVALID_DURATION, field, str(error))


def _quantity(value: object, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
        or (isinstance(value, float) and not isfinite(value))
    ):
        _fail(
            ProductErrorCode.INVALID_REFERENCE,
            field,
            "quantity must be a positive number",
        )
    return float(value)


def _records(document: CanonicalRecordsDocument, collection: str) -> Sequence[Record]:
    value = cast(Mapping[str, object], document)[collection]
    return cast(Sequence[Record], value)


def _validate_source_versions(source_versions: Mapping[str, str]) -> None:
    if not source_versions:
        _fail(
            ProductErrorCode.INVALID_REFERENCE,
            "source_versions",
            "at least one source/version is required",
        )
    for system, version in source_versions.items():
        _identifier(system, "source_versions.<source_system>")
        _text(version, f"source_versions.{system}")


def _indexes(document: CanonicalRecordsDocument) -> dict[str, dict[str, Record]]:
    indexes: dict[str, dict[str, Record]] = {}
    for collection, id_field in COLLECTION_ID_FIELDS.items():
        index: dict[str, Record] = {}
        for position, record in enumerate(_records(document, collection)):
            record_id = _identifier(
                record[id_field], f"{collection}[{position}].{id_field}"
            )
            if record_id in index:
                _fail(
                    ProductErrorCode.DUPLICATE_ID, f"{collection}.{id_field}", record_id
                )
            index[record_id] = record
        indexes[collection] = index
    return indexes


def _require_reference(
    record: Record,
    field: str,
    target: Mapping[str, Record],
    path: str,
) -> str:
    value = _identifier(record[field], f"{path}.{field}")
    if value not in target:
        _fail(
            ProductErrorCode.INVALID_REFERENCE, f"{path}.{field}", f"unknown ID {value}"
        )
    return value


def _validate_synthetic_boundary(
    synthetic: bool,
    provenance: SyntheticProvenance | None,
    field: str,
) -> None:
    if synthetic and provenance is None:
        _fail(
            ProductErrorCode.MISSING_SCENARIO_ID,
            field,
            "synthetic document requires complete synthetic provenance",
        )
    if not synthetic and provenance is not None:
        _fail(
            ProductErrorCode.SYNTHETIC_REFERENCE_IN_PRODUCTION,
            field,
            "Production document must not carry synthetic provenance",
        )
    if provenance is not None:
        _identifier(provenance["scenario_id"], f"{field}.scenario_id")
        _text(provenance["scenario_version"], f"{field}.scenario_version")
        _identifier(provenance["factory_profile_id"], f"{field}.factory_profile_id")
        _text(provenance["profile_version"], f"{field}.profile_version")
        _identifier(provenance["generator_id"], f"{field}.generator_id")
        _text(provenance["generator_version"], f"{field}.generator_version")
        if (
            isinstance(provenance["seed"], bool)
            or provenance["seed"] < 0
            or provenance["seed"] > 9223372036854775807
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{field}.seed",
                "seed must be non-negative",
            )


def validate_canonical_records(
    document: CanonicalRecordsDocument,
    *,
    source_versions: Mapping[str, str] | None = None,
) -> None:
    """Validate stable IDs, lineage references, units, UTC values and durations."""

    if document["canonical_records_version"] != "canonical-records.v1":
        _fail(
            ProductErrorCode.INVALID_REFERENCE,
            "canonical_records_version",
            "expected canonical-records.v1",
        )
    indexes = _indexes(document)

    for collection in COLLECTION_ID_FIELDS:
        for position, record in enumerate(_records(document, collection)):
            source = cast(SourceReference, record["source"])
            path = f"{collection}[{position}].source"
            system = _identifier(source["source_system"], f"{path}.source_system")
            version = _text(source["source_version"], f"{path}.source_version")
            _identifier(source["source_record_id"], f"{path}.source_record_id")
            if source_versions is not None and source_versions.get(system) != version:
                _fail(
                    ProductErrorCode.INVALID_REFERENCE,
                    path,
                    "record source/version is absent from envelope source_versions",
                )

    reference_rules = (
        ("workshops", "factory_id", "factories"),
        ("production_lines", "workshop_id", "workshops"),
        ("resource_groups", "production_line_id", "production_lines"),
        ("resources", "resource_group_id", "resource_groups"),
        ("resources", "calendar_id", "calendars"),
        ("routing_versions", "product_id", "products"),
        ("routing_operations", "routing_version_id", "routing_versions"),
        ("routing_precedence_edges", "routing_version_id", "routing_versions"),
        (
            "routing_precedence_edges",
            "predecessor_routing_operation_id",
            "routing_operations",
        ),
        (
            "routing_precedence_edges",
            "successor_routing_operation_id",
            "routing_operations",
        ),
        ("routing_resource_options", "routing_operation_id", "routing_operations"),
        ("routing_resource_options", "resource_id", "resources"),
        ("demand_orders", "product_id", "products"),
        ("production_orders", "demand_order_id", "demand_orders"),
        ("production_orders", "routing_version_id", "routing_versions"),
        ("production_lots", "production_order_id", "production_orders"),
        ("execution_facts", "production_lot_id", "production_lots"),
        ("execution_facts", "routing_operation_id", "routing_operations"),
        ("operation_locks", "production_lot_id", "production_lots"),
        ("operation_locks", "routing_operation_id", "routing_operations"),
        ("operation_locks", "resource_id", "resources"),
    )
    for collection, field, target in reference_rules:
        for position, record in enumerate(_records(document, collection)):
            _require_reference(
                record, field, indexes[target], f"{collection}[{position}]"
            )

    for position, resource in enumerate(document["resources"]):
        capabilities = resource["capabilities"]
        if len(capabilities) != len(set(capabilities)):
            _fail(
                ProductErrorCode.DUPLICATE_CAPABILITY,
                f"resources[{position}].capabilities",
                "duplicates",
            )
        for capability_index, capability in enumerate(capabilities):
            _text(capability, f"resources[{position}].capabilities[{capability_index}]")

    for calendar_index, calendar in enumerate(document["calendars"]):
        interval_ids: set[str] = set()
        for interval_index, interval in enumerate(calendar["unavailable_intervals"]):
            path = (
                f"calendars[{calendar_index}].unavailable_intervals[{interval_index}]"
            )
            interval_id = _identifier(interval["interval_id"], f"{path}.interval_id")
            if interval_id in interval_ids:
                _fail(ProductErrorCode.DUPLICATE_ID, f"{path}.interval_id", interval_id)
            interval_ids.add(interval_id)
            start = _utc(interval["start_at_utc"], f"{path}.start_at_utc")
            end = _utc(interval["end_at_utc"], f"{path}.end_at_utc")
            if start >= end:
                _fail(
                    ProductErrorCode.INVALID_TIME_RANGE,
                    f"{path}.end_at_utc",
                    "end must follow start",
                )

    product_units = {
        record["product_id"]: record["quantity_unit"] for record in document["products"]
    }
    route_products = {
        record["routing_version_id"]: record["product_id"]
        for record in document["routing_versions"]
    }
    operation_routes = {
        record["routing_operation_id"]: record["routing_version_id"]
        for record in document["routing_operations"]
    }
    demand_products = {
        record["demand_order_id"]: record["product_id"]
        for record in document["demand_orders"]
    }
    demand_units = {
        record["demand_order_id"]: record["quantity_unit"]
        for record in document["demand_orders"]
    }
    order_units = {
        record["production_order_id"]: record["quantity_unit"]
        for record in document["production_orders"]
    }
    lot_units = {
        record["production_lot_id"]: record["quantity_unit"]
        for record in document["production_lots"]
    }

    for position, edge in enumerate(document["routing_precedence_edges"]):
        path = f"routing_precedence_edges[{position}]"
        predecessor = edge["predecessor_routing_operation_id"]
        successor = edge["successor_routing_operation_id"]
        if predecessor == successor:
            _fail(ProductErrorCode.INVALID_REFERENCE, path, "self edge is invalid")
        route = edge["routing_version_id"]
        if (
            operation_routes[predecessor] != route
            or operation_routes[successor] != route
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "edge endpoints must belong to routing version",
            )
        minimum = _duration(edge["min_lag_seconds"], f"{path}.min_lag_seconds")
        _duration(edge["transport_lag_seconds"], f"{path}.transport_lag_seconds")
        maximum = edge.get("max_lag_seconds")
        if (
            maximum is not None
            and _duration(maximum, f"{path}.max_lag_seconds") < minimum
        ):
            _fail(
                ProductErrorCode.INVALID_LAG_RANGE,
                f"{path}.max_lag_seconds",
                "maximum is below minimum",
            )

    for position, option in enumerate(document["routing_resource_options"]):
        path = f"routing_resource_options[{position}]"
        operation_id = option["routing_operation_id"]
        product_id = route_products[operation_routes[operation_id]]
        _text(option["quantity_unit"], f"{path}.quantity_unit")
        if option["quantity_unit"] != product_units[product_id]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.quantity_unit",
                "unit differs from product",
            )
        _duration(option["setup_seconds"], f"{path}.setup_seconds")
        _duration(option["cycle_seconds_per_unit"], f"{path}.cycle_seconds_per_unit")
        _duration(
            option["final_duration_seconds"],
            f"{path}.final_duration_seconds",
            positive=True,
        )
        _text(option["duration_source"], f"{path}.duration_source")
        _text(option["duration_source_version"], f"{path}.duration_source_version")

    for position, demand in enumerate(document["demand_orders"]):
        path = f"demand_orders[{position}]"
        _quantity(demand["quantity"], f"{path}.quantity")
        _utc(demand["due_at_utc"], f"{path}.due_at_utc")
        if demand["quantity_unit"] != product_units[demand["product_id"]]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.quantity_unit",
                "unit differs from product",
            )

    for position, order in enumerate(document["production_orders"]):
        path = f"production_orders[{position}]"
        _quantity(order["quantity"], f"{path}.quantity")
        _utc(order["release_at_utc"], f"{path}.release_at_utc")
        _utc(order["material_ready_at_utc"], f"{path}.material_ready_at_utc")
        demand_id = order["demand_order_id"]
        if order["quantity_unit"] != demand_units[demand_id]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.quantity_unit",
                "unit differs from demand",
            )
        if route_products[order["routing_version_id"]] != demand_products[demand_id]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.routing_version_id",
                "routing product differs from demand",
            )

    for position, lot in enumerate(document["production_lots"]):
        path = f"production_lots[{position}]"
        _quantity(lot["quantity"], f"{path}.quantity")
        if lot["quantity_unit"] != order_units[lot["production_order_id"]]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.quantity_unit",
                "unit differs from production order",
            )

    for position, fact in enumerate(document["execution_facts"]):
        path = f"execution_facts[{position}]"
        _utc(fact["observed_at_utc"], f"{path}.observed_at_utc")
        if fact["quantity_unit"] != lot_units[fact["production_lot_id"]]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.quantity_unit",
                "unit differs from production lot",
            )
        if fact["status"] == "RUNNING":
            required_fields = {
                "resource_id",
                "actual_start_at_utc",
                "remaining_quantity",
                "remaining_seconds",
            }
            forbidden_fields = {"actual_end_at_utc", "completed_quantity"}
        else:
            required_fields = {
                "resource_id",
                "actual_start_at_utc",
                "actual_end_at_utc",
                "completed_quantity",
            }
            forbidden_fields = {"remaining_quantity", "remaining_seconds"}
        missing_fields = sorted(field for field in required_fields if field not in fact)
        present_forbidden = sorted(field for field in forbidden_fields if field in fact)
        if missing_fields or present_forbidden:
            _fail(
                ProductErrorCode.MISSING_RUNNING_FACT,
                path,
                f"status fields mismatch; missing={missing_fields}, forbidden={present_forbidden}",
            )
        resource_id = fact.get("resource_id")
        if resource_id is not None and resource_id not in indexes["resources"]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.resource_id",
                f"unknown ID {resource_id}",
            )
        start_text = fact.get("actual_start_at_utc")
        end_text = fact.get("actual_end_at_utc")
        start = (
            _utc(start_text, f"{path}.actual_start_at_utc")
            if start_text is not None
            else None
        )
        end = (
            _utc(end_text, f"{path}.actual_end_at_utc")
            if end_text is not None
            else None
        )
        if start is not None and end is not None and start >= end:
            _fail(
                ProductErrorCode.INVALID_TIME_RANGE,
                f"{path}.actual_end_at_utc",
                "end must follow start",
            )
        if "completed_quantity" in fact:
            _quantity(fact["completed_quantity"], f"{path}.completed_quantity")
        if "remaining_quantity" in fact:
            _quantity(fact["remaining_quantity"], f"{path}.remaining_quantity")
        if "remaining_seconds" in fact:
            _duration(
                fact["remaining_seconds"], f"{path}.remaining_seconds", positive=True
            )

    for position, lock in enumerate(document["operation_locks"]):
        path = f"operation_locks[{position}]"
        start = _utc(lock["start_at_utc"], f"{path}.start_at_utc")
        end = _utc(lock["end_at_utc"], f"{path}.end_at_utc")
        if start >= end:
            _fail(
                ProductErrorCode.INVALID_TIME_RANGE,
                f"{path}.end_at_utc",
                "end must follow start",
            )


def validate_import_package_v2(document: ImportPackageDocumentV2) -> None:
    """Run pure envelope and canonical-record prechecks for Standard Import v2."""

    if (
        document["import_package_version"] != "import-package.v2"
        or document["schema_set_version"] != "2.0.0"
    ):
        _fail(
            ProductErrorCode.INVALID_REFERENCE,
            "import_package_version",
            "expected v2 / schema set 2.0.0",
        )
    _identifier(document["package_id"], "package_id")
    _validate_source_versions(document["source_versions"])
    _text(document["normalization_rule_version"], "normalization_rule_version")
    _text(document["canonicalization_version"], "canonicalization_version")
    _validate_synthetic_boundary(
        document["synthetic"],
        document.get("synthetic_provenance"),
        "synthetic_provenance",
    )
    validate_canonical_records(
        document["records"], source_versions=document["source_versions"]
    )


def validate_planning_snapshot_v2(document: PlanningSnapshotDocumentV2) -> None:
    """Run pure Snapshot v2 reference/count checks without building or hashing it."""

    if (
        document["snapshot_version"] != "planning-snapshot.v2"
        or document["schema_set_version"] != "2.0.0"
    ):
        _fail(
            ProductErrorCode.INVALID_REFERENCE,
            "snapshot_version",
            "expected v2 / schema set 2.0.0",
        )
    _identifier(document["snapshot_id"], "snapshot_id")
    _utc(document["cutoff_at_utc"], "cutoff_at_utc")
    _validate_source_versions(document["source_versions"])
    _validate_synthetic_boundary(
        document["synthetic"],
        document.get("synthetic_provenance"),
        "synthetic_provenance",
    )
    validate_canonical_records(
        document["records"], source_versions=document["source_versions"]
    )

    expected_counts = {
        collection: len(_records(document["records"], collection))
        for collection in COLLECTION_ID_FIELDS
    }
    expected_counts["operation_instances"] = len(document["operation_instances"])
    expected_counts["operation_precedence_edges"] = len(
        document["operation_precedence_edges"]
    )
    if document["entity_counts"] != expected_counts:
        _fail(
            ProductErrorCode.INVALID_ENTITY_COUNT,
            "entity_counts",
            "counts must exactly match Snapshot payload",
        )

    indexes = _indexes(document["records"])
    instance_ids: dict[str, OperationInstanceDocument] = {}
    for position, instance in enumerate(document["operation_instances"]):
        path = f"operation_instances[{position}]"
        instance_id = _identifier(
            instance["operation_instance_id"], f"{path}.operation_instance_id"
        )
        if instance_id in instance_ids:
            _fail(
                ProductErrorCode.DUPLICATE_ID,
                f"{path}.operation_instance_id",
                instance_id,
            )
        instance_ids[instance_id] = instance
        for field, collection in (
            ("demand_order_id", "demand_orders"),
            ("production_order_id", "production_orders"),
            ("production_lot_id", "production_lots"),
            ("routing_version_id", "routing_versions"),
            ("routing_operation_id", "routing_operations"),
        ):
            value = instance[field]
            if value not in indexes[collection]:
                _fail(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{path}.{field}",
                    f"unknown ID {value}",
                )
        _quantity(instance["quantity"], f"{path}.quantity")
        for field in ("due_at_utc", "release_at_utc", "material_ready_at_utc"):
            _utc(instance[field], f"{path}.{field}")

        lot = cast(
            ProductionLotRecord,
            indexes["production_lots"][instance["production_lot_id"]],
        )
        order = cast(
            ProductionOrderRecord,
            indexes["production_orders"][instance["production_order_id"]],
        )
        demand = cast(
            DemandOrderRecord, indexes["demand_orders"][instance["demand_order_id"]]
        )
        operation = cast(
            RoutingOperationRecord,
            indexes["routing_operations"][instance["routing_operation_id"]],
        )
        if (
            lot["production_order_id"] != instance["production_order_id"]
            or order["demand_order_id"] != instance["demand_order_id"]
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "order/lot lineage is inconsistent",
            )
        if (
            order["routing_version_id"] != instance["routing_version_id"]
            or operation["routing_version_id"] != instance["routing_version_id"]
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "routing lineage is inconsistent",
            )
        if (
            instance["quantity_unit"] != lot["quantity_unit"]
            or instance["due_at_utc"] != demand["due_at_utc"]
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "expanded unit/due value differs from source",
            )
        if (
            instance["release_at_utc"] != order["release_at_utc"]
            or instance["material_ready_at_utc"] != order["material_ready_at_utc"]
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "expanded release/material gate differs from source",
            )
        if instance["required_capabilities"] != operation["required_capabilities"]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.required_capabilities",
                "differs from routing operation",
            )

        if not instance["resource_options"]:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.resource_options",
                "at least one explicit candidate is required",
            )
        option_ids: set[str] = set()
        for option_index, option in enumerate(instance["resource_options"]):
            option_path = f"{path}.resource_options[{option_index}]"
            option_id = option["routing_resource_option_id"]
            if option_id in option_ids:
                _fail(
                    ProductErrorCode.DUPLICATE_ID,
                    f"{option_path}.routing_resource_option_id",
                    option_id,
                )
            option_ids.add(option_id)
            canonical = cast(
                RoutingResourceOptionRecord | None,
                indexes["routing_resource_options"].get(option_id),
            )
            if (
                canonical is None
                or canonical["routing_operation_id"] != instance["routing_operation_id"]
            ):
                _fail(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{option_path}.routing_resource_option_id",
                    "option is absent or belongs to another operation",
                )
            expected = (
                canonical["resource_id"],
                canonical["setup_seconds"],
                canonical["cycle_seconds_per_unit"],
                canonical["final_duration_seconds"],
                canonical["duration_source"],
                canonical["duration_source_version"],
            )
            observed = (
                option["resource_id"],
                option["setup_seconds"],
                option["cycle_seconds_per_unit"],
                option["final_duration_seconds"],
                option["duration_source"],
                option["source_version"],
            )
            if observed != expected:
                _fail(
                    ProductErrorCode.INVALID_REFERENCE,
                    option_path,
                    "expanded option differs from canonical source",
                )

        fact_id = instance.get("execution_fact_id")
        if instance["status"] == "NOT_STARTED" and fact_id is not None:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.execution_fact_id",
                "NOT_STARTED must not reference a fact",
            )
        if instance["status"] != "NOT_STARTED":
            fact = indexes["execution_facts"].get(fact_id or "")
            if (
                fact is None
                or fact["production_lot_id"] != instance["production_lot_id"]
                or fact["routing_operation_id"] != instance["routing_operation_id"]
            ):
                _fail(
                    ProductErrorCode.MISSING_RUNNING_FACT,
                    f"{path}.execution_fact_id",
                    "fact is absent or has different lineage",
                )
            if fact["status"] != instance["status"]:
                _fail(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{path}.execution_fact_id",
                    "operation status differs from execution fact",
                )
        if len(instance["lock_ids"]) != len(set(instance["lock_ids"])):
            _fail(
                ProductErrorCode.DUPLICATE_ID,
                f"{path}.lock_ids",
                "lock IDs must be unique",
            )
        for lock_id in instance["lock_ids"]:
            lock = indexes["operation_locks"].get(lock_id)
            if (
                lock is None
                or lock["production_lot_id"] != instance["production_lot_id"]
                or lock["routing_operation_id"] != instance["routing_operation_id"]
            ):
                _fail(
                    ProductErrorCode.INVALID_REFERENCE,
                    f"{path}.lock_ids",
                    f"invalid lock {lock_id}",
                )

    edge_ids: set[str] = set()
    for position, edge in enumerate(document["operation_precedence_edges"]):
        path = f"operation_precedence_edges[{position}]"
        edge_id = _identifier(
            edge["operation_precedence_edge_id"], f"{path}.operation_precedence_edge_id"
        )
        if edge_id in edge_ids:
            _fail(
                ProductErrorCode.DUPLICATE_ID,
                f"{path}.operation_precedence_edge_id",
                edge_id,
            )
        edge_ids.add(edge_id)
        predecessor = edge["predecessor_operation_instance_id"]
        successor = edge["successor_operation_instance_id"]
        if (
            predecessor not in instance_ids
            or successor not in instance_ids
            or predecessor == successor
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "edge endpoints are absent or identical",
            )
        routing_edge = indexes["routing_precedence_edges"].get(
            edge["routing_precedence_edge_id"]
        )
        if routing_edge is None:
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                f"{path}.routing_precedence_edge_id",
                "unknown routing edge",
            )
        if (
            instance_ids[predecessor]["routing_operation_id"]
            != routing_edge["predecessor_routing_operation_id"]
            or instance_ids[successor]["routing_operation_id"]
            != routing_edge["successor_routing_operation_id"]
        ):
            _fail(
                ProductErrorCode.INVALID_REFERENCE,
                path,
                "expanded edge differs from routing edge",
            )
        expected_lags = (
            routing_edge["min_lag_seconds"],
            routing_edge.get("max_lag_seconds"),
            routing_edge["transport_lag_seconds"],
        )
        observed_lags = (
            edge["min_lag_seconds"],
            edge.get("max_lag_seconds"),
            edge["transport_lag_seconds"],
        )
        if observed_lags != expected_lags:
            _fail(
                ProductErrorCode.INVALID_LAG_RANGE,
                path,
                "expanded lags differ from routing edge",
            )


__all__ = [
    "COLLECTION_ID_FIELDS",
    "CanonicalContractError",
    "CanonicalRecordsDocument",
    "ImportPackageDocumentV2",
    "OperationInstanceDocument",
    "OperationPrecedenceEdgeDocument",
    "OperationResourceOptionDocument",
    "PlanningSnapshotDocumentV2",
    "SourceReference",
    "SyntheticProvenance",
    "validate_canonical_records",
    "validate_import_package_v2",
    "validate_planning_snapshot_v2",
]
