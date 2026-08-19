"""Deterministically expand validated canonical orders into operation instances."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from hashlib import sha256
from typing import NoReturn, cast

from app.domain.canonical_records import (
    CanonicalContractError,
    DemandOrderRecord,
    ExecutionFactRecord,
    ImportPackageDocumentV2,
    OperationInstanceDocument,
    OperationLockRecord,
    OperationPrecedenceEdgeDocument,
    OperationResourceOptionDocument,
    ProductionLotRecord,
    ProductionOrderRecord,
    RoutingOperationRecord,
    RoutingPrecedenceEdgeRecord,
    RoutingResourceOptionRecord,
    RoutingVersionRecord,
    SyntheticProvenance,
    validate_import_package_v2,
)
from app.domain.production import (
    EXPLICIT_LOTS_MODE,
    EXPANSION_CANONICALIZATION_VERSION,
    ORDER_EXPANSION_VERSION,
    OrderExpansionDocument,
    OrderExpansionError,
    OrderExpansionErrorCode,
    OrderExpansionImportReference,
    OrderExpansionQualityReference,
    OrderExpansionResult,
    canonical_expansion_bytes,
    stable_expansion_id,
)

_QUALITY_REPORT_VERSION = "import-quality-report.v1"
_QUALITY_SCHEMA_SET_VERSION = "2.2.0"
_QUALITY_RULE_VERSION = "data-quality-rules.v1"
_ERROR_REGISTRY_VERSION = "error-code-registry.v2"
_REPORT_CANONICALIZATION_VERSION = "canonical-json.v1"


def _reject(
    code: OrderExpansionErrorCode,
    *,
    field: str,
    entity_id: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise OrderExpansionError(
        code,
        field=field,
        entity_id=entity_id,
        expected_contract=expected_contract,
        message=message,
    )


def _quality_report_id(document: Mapping[str, object]) -> str:
    basis = {key: value for key, value in document.items() if key != "report_id"}
    digest = sha256(canonical_expansion_bytes(basis)).hexdigest()
    return f"import-quality-{digest}"


def _validate_quality_report(
    report: Mapping[str, object],
    import_document: ImportPackageDocumentV2,
) -> OrderExpansionQualityReference:
    expected_values: dict[str, object] = {
        "report_version": _QUALITY_REPORT_VERSION,
        "schema_set_version": _QUALITY_SCHEMA_SET_VERSION,
        "import_package_version": "import-package.v2",
        "package_id": import_document["package_id"],
        "data_quality_rule_version": _QUALITY_RULE_VERSION,
        "error_registry_version": _ERROR_REGISTRY_VERSION,
        "report_canonicalization_version": _REPORT_CANONICALIZATION_VERSION,
        "status": "PASS",
        "error_count": 0,
    }
    expected_fields = set(expected_values) | {"report_id", "errors"}
    if set(report) != expected_fields:
        _reject(
            OrderExpansionErrorCode.QUALITY_REPORT_MISMATCH,
            field="import_quality_report",
            entity_id=import_document["package_id"],
            expected_contract="exact import-quality-report.v1 field set",
            message="Quality report fields do not match the versioned contract",
        )
    error_count = report.get("error_count")
    if isinstance(error_count, bool) or error_count != 0:
        _reject(
            OrderExpansionErrorCode.QUALITY_REPORT_REQUIRED,
            field="import_quality_report.error_count",
            entity_id=import_document["package_id"],
            expected_contract="integer zero for a PASS report",
            message="Expansion cannot consume a report containing errors",
        )
    for field, expected in expected_values.items():
        if report.get(field) != expected:
            code = (
                OrderExpansionErrorCode.QUALITY_REPORT_REQUIRED
                if field in {"status", "error_count"}
                else OrderExpansionErrorCode.QUALITY_REPORT_MISMATCH
            )
            _reject(
                code,
                field=f"import_quality_report.{field}",
                entity_id=import_document["package_id"],
                expected_contract=repr(expected),
                message="A matching DataValidation PASS report is required",
            )
    errors = report.get("errors")
    if not isinstance(errors, list) or errors:
        _reject(
            OrderExpansionErrorCode.QUALITY_REPORT_REQUIRED,
            field="import_quality_report.errors",
            entity_id=import_document["package_id"],
            expected_contract="empty array for a PASS report",
            message="Expansion cannot consume a report containing errors",
        )
    report_id = report.get("report_id")
    if not isinstance(report_id, str) or report_id != _quality_report_id(report):
        _reject(
            OrderExpansionErrorCode.QUALITY_REPORT_MISMATCH,
            field="import_quality_report.report_id",
            entity_id=import_document["package_id"],
            expected_contract="content-derived import-quality-report.v1 ID",
            message="Quality report identity does not match its content",
        )
    return {
        "report_version": "import-quality-report.v1",
        "schema_set_version": "2.2.0",
        "report_id": report_id,
        "data_quality_rule_version": "data-quality-rules.v1",
        "error_registry_version": "error-code-registry.v2",
        "report_canonicalization_version": "canonical-json.v1",
        "status": "PASS",
    }


def _validate_canonical_input(document: ImportPackageDocumentV2) -> None:
    try:
        validate_import_package_v2(document)
    except KeyError as error:
        missing_field = str(error.args[0]) if error.args else "<unknown>"
        code = (
            OrderExpansionErrorCode.MISSING_DURATION
            if missing_field
            in {
                "setup_seconds",
                "cycle_seconds_per_unit",
                "final_duration_seconds",
                "duration_source",
                "duration_source_version",
            }
            else OrderExpansionErrorCode.INVALID_CANONICAL_INPUT
        )
        _reject(
            code,
            field=missing_field,
            entity_id=document.get("package_id", "<unknown>"),
            expected_contract="complete canonical-records.v1 input",
            message="Required canonical input is missing",
        )
    except (CanonicalContractError, IndexError, TypeError) as error:
        _reject(
            OrderExpansionErrorCode.INVALID_CANONICAL_INPUT,
            field=getattr(error, "field", "canonical_import"),
            entity_id=document.get("package_id", "<unknown>"),
            expected_contract="valid canonical Import v2",
            message=str(error),
        )


def _validate_fact_and_lock_lineage(
    *,
    lots: Mapping[str, ProductionLotRecord],
    orders: Mapping[str, ProductionOrderRecord],
    operations: Mapping[str, RoutingOperationRecord],
    facts: list[ExecutionFactRecord],
    locks: list[OperationLockRecord],
) -> tuple[
    dict[tuple[str, str], ExecutionFactRecord],
    dict[tuple[str, str], list[OperationLockRecord]],
]:
    facts_by_key: dict[tuple[str, str], ExecutionFactRecord] = {}
    for fact in facts:
        key = (fact["production_lot_id"], fact["routing_operation_id"])
        lot = lots[key[0]]
        order = orders[lot["production_order_id"]]
        operation = operations[key[1]]
        if operation["routing_version_id"] != order["routing_version_id"]:
            _reject(
                OrderExpansionErrorCode.INVALID_EXECUTION_FACT,
                field="routing_operation_id",
                entity_id=fact["execution_fact_id"],
                expected_contract="fact operation belongs to the lot order routing version",
                message="Execution fact lineage crosses routing versions",
            )
        if key in facts_by_key:
            _reject(
                OrderExpansionErrorCode.INVALID_EXECUTION_FACT,
                field="production_lot_id/routing_operation_id",
                entity_id=fact["execution_fact_id"],
                expected_contract="at most one current fact per lot operation",
                message="Multiple execution facts target the same operation instance",
            )
        facts_by_key[key] = fact

    locks_by_key: dict[tuple[str, str], list[OperationLockRecord]] = defaultdict(list)
    for lock in locks:
        key = (lock["production_lot_id"], lock["routing_operation_id"])
        lot = lots[key[0]]
        order = orders[lot["production_order_id"]]
        operation = operations[key[1]]
        if operation["routing_version_id"] != order["routing_version_id"]:
            _reject(
                OrderExpansionErrorCode.INVALID_OPERATION_LOCK,
                field="routing_operation_id",
                entity_id=lock["lock_id"],
                expected_contract="lock operation belongs to the lot order routing version",
                message="Operation lock lineage crosses routing versions",
            )
        locks_by_key[key].append(lock)
    return facts_by_key, dict(locks_by_key)


def _resource_option_document(
    option: RoutingResourceOptionRecord,
) -> OperationResourceOptionDocument:
    required = (
        "setup_seconds",
        "cycle_seconds_per_unit",
        "final_duration_seconds",
        "duration_source",
        "duration_source_version",
    )
    if any(field not in option for field in required):
        _reject(
            OrderExpansionErrorCode.MISSING_DURATION,
            field="routing_resource_option.duration",
            entity_id=option["routing_resource_option_id"],
            expected_contract="explicit setup/cycle/final duration and source version",
            message="Duration fallback is forbidden",
        )
    return {
        "routing_resource_option_id": option["routing_resource_option_id"],
        "resource_id": option["resource_id"],
        "setup_seconds": option["setup_seconds"],
        "cycle_seconds_per_unit": option["cycle_seconds_per_unit"],
        "final_duration_seconds": option["final_duration_seconds"],
        "duration_source": option["duration_source"],
        "source_version": option["duration_source_version"],
    }


def expand_orders(
    import_document: ImportPackageDocumentV2,
    quality_report: Mapping[str, object],
    *,
    expansion_version: str = ORDER_EXPANSION_VERSION,
    lot_mode: str = EXPLICIT_LOTS_MODE,
) -> OrderExpansionResult:
    """Expand explicit lots and routing DAGs after a matching quality PASS."""

    if expansion_version != ORDER_EXPANSION_VERSION:
        _reject(
            OrderExpansionErrorCode.EXPANSION_VERSION_MISMATCH,
            field="expansion_version",
            entity_id=expansion_version or "<missing>",
            expected_contract=ORDER_EXPANSION_VERSION,
            message="Historical expansion versions cannot be reinterpreted",
        )
    if lot_mode != EXPLICIT_LOTS_MODE:
        _reject(
            OrderExpansionErrorCode.UNSUPPORTED_SPLIT_MERGE,
            field="lot_mode",
            entity_id=lot_mode or "<missing>",
            expected_contract=EXPLICIT_LOTS_MODE,
            message="Automatic lot split/merge is unsupported in V1",
        )

    quality_reference = _validate_quality_report(quality_report, import_document)
    _validate_canonical_input(import_document)
    records = import_document["records"]

    demands: dict[str, DemandOrderRecord] = {
        record["demand_order_id"]: record for record in records["demand_orders"]
    }
    orders: dict[str, ProductionOrderRecord] = {
        record["production_order_id"]: record
        for record in records["production_orders"]
    }
    lots: dict[str, ProductionLotRecord] = {
        record["production_lot_id"]: record for record in records["production_lots"]
    }
    routes: dict[str, RoutingVersionRecord] = {
        record["routing_version_id"]: record for record in records["routing_versions"]
    }
    operations: dict[str, RoutingOperationRecord] = {
        record["routing_operation_id"]: record
        for record in records["routing_operations"]
    }

    lots_by_order: dict[str, list[ProductionLotRecord]] = defaultdict(list)
    for lot in lots.values():
        lots_by_order[lot["production_order_id"]].append(lot)
    operations_by_route: dict[str, list[RoutingOperationRecord]] = defaultdict(list)
    for operation in operations.values():
        operations_by_route[operation["routing_version_id"]].append(operation)
    edges_by_route: dict[str, list[RoutingPrecedenceEdgeRecord]] = defaultdict(list)
    for edge in records["routing_precedence_edges"]:
        edges_by_route[edge["routing_version_id"]].append(edge)
    options_by_operation: dict[str, list[RoutingResourceOptionRecord]] = defaultdict(list)
    for option in records["routing_resource_options"]:
        options_by_operation[option["routing_operation_id"]].append(option)

    facts_by_key, locks_by_key = _validate_fact_and_lock_lineage(
        lots=lots,
        orders=orders,
        operations=operations,
        facts=records["execution_facts"],
        locks=records["operation_locks"],
    )

    instances: list[OperationInstanceDocument] = []
    instance_id_by_lineage: dict[tuple[str, str], str] = {}
    derived_ids: set[str] = set()
    for order in sorted(orders.values(), key=lambda item: item["production_order_id"]):
        order_id = order["production_order_id"]
        order_lots = sorted(
            lots_by_order.get(order_id, []), key=lambda item: item["production_lot_id"]
        )
        if not order_lots:
            _reject(
                OrderExpansionErrorCode.MISSING_PRODUCTION_LOT,
                field="production_lots",
                entity_id=order_id,
                expected_contract="one or more explicit ProductionLot records",
                message="Lot sizing cannot be inferred by expansion",
            )
        route_id = order["routing_version_id"]
        route_operations = sorted(
            operations_by_route.get(route_id, []),
            key=lambda item: item["routing_operation_id"],
        )
        if route_id not in routes or not route_operations:
            _reject(
                OrderExpansionErrorCode.ROUTING_VERSION_MISMATCH,
                field="routing_version_id",
                entity_id=order_id,
                expected_contract="an explicit routing version with operations",
                message="Production order routing cannot be expanded",
            )
        demand = demands[order["demand_order_id"]]
        for lot in order_lots:
            lot_id = lot["production_lot_id"]
            for operation in route_operations:
                operation_id = operation["routing_operation_id"]
                source_options = sorted(
                    options_by_operation.get(operation_id, []),
                    key=lambda item: item["routing_resource_option_id"],
                )
                if not source_options:
                    _reject(
                        OrderExpansionErrorCode.MISSING_RESOURCE_OPTION,
                        field="routing_resource_options",
                        entity_id=operation_id,
                        expected_contract="at least one explicit candidate resource option",
                        message="Expansion cannot invent a candidate resource or duration",
                    )
                resource_options = [
                    _resource_option_document(option) for option in source_options
                ]
                instance_id = stable_expansion_id(
                    "operation-instance", expansion_version, lot_id, operation_id
                )
                if instance_id in derived_ids:
                    _reject(
                        OrderExpansionErrorCode.DUPLICATE_DERIVED_ID,
                        field="operation_instance_id",
                        entity_id=instance_id,
                        expected_contract="unique versioned lot/operation lineage",
                        message="Derived operation identity collided",
                    )
                derived_ids.add(instance_id)
                instance_id_by_lineage[(lot_id, operation_id)] = instance_id
                fact = facts_by_key.get((lot_id, operation_id))
                status = fact["status"] if fact is not None else "NOT_STARTED"
                instance: OperationInstanceDocument = {
                    "operation_instance_id": instance_id,
                    "demand_order_id": demand["demand_order_id"],
                    "production_order_id": order_id,
                    "production_lot_id": lot_id,
                    "routing_version_id": route_id,
                    "routing_operation_id": operation_id,
                    "status": status,
                    "quantity": lot["quantity"],
                    "quantity_unit": lot["quantity_unit"],
                    "due_at_utc": demand["due_at_utc"],
                    "release_at_utc": order["release_at_utc"],
                    "material_ready_at_utc": order["material_ready_at_utc"],
                    "required_capabilities": list(operation["required_capabilities"]),
                    "resource_options": resource_options,
                    "lock_ids": sorted(
                        lock["lock_id"]
                        for lock in locks_by_key.get((lot_id, operation_id), [])
                    ),
                }
                if fact is not None:
                    instance["execution_fact_id"] = fact["execution_fact_id"]
                instances.append(instance)

    expanded_edges: list[OperationPrecedenceEdgeDocument] = []
    edge_ids: set[str] = set()
    for order in sorted(orders.values(), key=lambda item: item["production_order_id"]):
        route_edges = sorted(
            edges_by_route.get(order["routing_version_id"], []),
            key=lambda item: item["routing_precedence_edge_id"],
        )
        for lot in sorted(
            lots_by_order[order["production_order_id"]],
            key=lambda item: item["production_lot_id"],
        ):
            lot_id = lot["production_lot_id"]
            for source_edge in route_edges:
                source_edge_id = source_edge["routing_precedence_edge_id"]
                predecessor_key = (
                    lot_id,
                    source_edge["predecessor_routing_operation_id"],
                )
                successor_key = (
                    lot_id,
                    source_edge["successor_routing_operation_id"],
                )
                if (
                    predecessor_key not in instance_id_by_lineage
                    or successor_key not in instance_id_by_lineage
                ):
                    _reject(
                        OrderExpansionErrorCode.ROUTING_VERSION_MISMATCH,
                        field="routing_precedence_edge_id",
                        entity_id=source_edge_id,
                        expected_contract="edge endpoints in the order routing version",
                        message="Routing edge cannot be mapped to operation instances",
                    )
                edge_id = stable_expansion_id(
                    "operation-precedence-edge",
                    expansion_version,
                    lot_id,
                    source_edge_id,
                )
                if edge_id in edge_ids:
                    _reject(
                        OrderExpansionErrorCode.DUPLICATE_DERIVED_ID,
                        field="operation_precedence_edge_id",
                        entity_id=edge_id,
                        expected_contract="unique versioned lot/routing-edge lineage",
                        message="Derived precedence identity collided",
                    )
                edge_ids.add(edge_id)
                expanded: OperationPrecedenceEdgeDocument = {
                    "operation_precedence_edge_id": edge_id,
                    "routing_precedence_edge_id": source_edge_id,
                    "predecessor_operation_instance_id": instance_id_by_lineage[
                        predecessor_key
                    ],
                    "successor_operation_instance_id": instance_id_by_lineage[
                        successor_key
                    ],
                    "min_lag_seconds": source_edge["min_lag_seconds"],
                    "transport_lag_seconds": source_edge["transport_lag_seconds"],
                }
                if "max_lag_seconds" in source_edge:
                    expanded["max_lag_seconds"] = source_edge["max_lag_seconds"]
                expanded_edges.append(expanded)

    import_reference: OrderExpansionImportReference = {
        "import_package_version": "import-package.v2",
        "schema_set_version": "2.0.0",
        "package_id": import_document["package_id"],
        "source_versions": dict(sorted(import_document["source_versions"].items())),
        "normalization_rule_version": import_document[
            "normalization_rule_version"
        ],
        "canonicalization_version": import_document["canonicalization_version"],
        "synthetic": import_document["synthetic"],
    }
    provenance = import_document.get("synthetic_provenance")
    if provenance is not None:
        import_reference["synthetic_provenance"] = cast(
            SyntheticProvenance, dict(provenance)
        )

    instances.sort(key=lambda item: item["operation_instance_id"])
    expanded_edges.sort(key=lambda item: item["operation_precedence_edge_id"])
    expansion_document: OrderExpansionDocument = {
        "expansion_version": "order-expansion.v1",
        "canonicalization_version": EXPANSION_CANONICALIZATION_VERSION,
        "import_package": import_reference,
        "import_quality_report": quality_reference,
        "operation_instances": instances,
        "operation_precedence_edges": expanded_edges,
    }
    canonical_bytes = canonical_expansion_bytes(
        cast(Mapping[str, object], expansion_document)
    )
    return OrderExpansionResult(
        document=expansion_document,
        canonical_bytes=canonical_bytes,
        expansion_hash=f"sha256:{sha256(canonical_bytes).hexdigest()}",
    )


__all__ = ["expand_orders"]
