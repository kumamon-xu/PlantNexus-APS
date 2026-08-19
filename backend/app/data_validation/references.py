"""Canonical Import structure, identity, provenance, and lineage validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.canonical_records import COLLECTION_ID_FIELDS
from app.domain.errors import ProductErrorCodeV2
from app.domain.types import ContractValueError, canonical_id

from .contracts import IssueCollector, stable_fingerprint, stable_json_text


_IMPORT_FIELDS = {
    "import_package_version",
    "schema_set_version",
    "package_id",
    "source_versions",
    "normalization_rule_version",
    "canonicalization_version",
    "synthetic",
    "synthetic_provenance",
    "records",
}
_SYNTHETIC_FIELDS = {
    "scenario_id",
    "scenario_version",
    "seed",
    "factory_profile_id",
    "profile_version",
    "generator_id",
    "generator_version",
}
_SOURCE_FIELDS = {"source_system", "source_version", "source_record_id"}

REQUIRED_FIELDS: Mapping[str, frozenset[str]] = {
    "factories": frozenset(
        {"factory_id", "factory_code", "factory_timezone", "source"}
    ),
    "workshops": frozenset(
        {"workshop_id", "workshop_code", "factory_id", "source"}
    ),
    "production_lines": frozenset(
        {
            "production_line_id",
            "production_line_code",
            "workshop_id",
            "source",
        }
    ),
    "resource_groups": frozenset(
        {
            "resource_group_id",
            "resource_group_code",
            "production_line_id",
            "source",
        }
    ),
    "resources": frozenset(
        {
            "resource_id",
            "resource_code",
            "resource_type",
            "status",
            "resource_group_id",
            "calendar_id",
            "capabilities",
            "source",
        }
    ),
    "calendars": frozenset(
        {"calendar_id", "timezone", "unavailable_intervals", "source"}
    ),
    "products": frozenset(
        {"product_id", "product_code", "quantity_unit", "source"}
    ),
    "routing_versions": frozenset(
        {"routing_version_id", "routing_code", "version", "product_id", "source"}
    ),
    "routing_operations": frozenset(
        {
            "routing_operation_id",
            "routing_version_id",
            "operation_code",
            "required_capabilities",
            "source",
        }
    ),
    "routing_precedence_edges": frozenset(
        {
            "routing_precedence_edge_id",
            "routing_version_id",
            "predecessor_routing_operation_id",
            "successor_routing_operation_id",
            "min_lag_seconds",
            "transport_lag_seconds",
            "source",
        }
    ),
    "routing_resource_options": frozenset(
        {
            "routing_resource_option_id",
            "routing_operation_id",
            "resource_id",
            "quantity_unit",
            "setup_seconds",
            "cycle_seconds_per_unit",
            "final_duration_seconds",
            "duration_source",
            "duration_source_version",
            "source",
        }
    ),
    "demand_orders": frozenset(
        {
            "demand_order_id",
            "product_id",
            "quantity",
            "quantity_unit",
            "due_at_utc",
            "source",
        }
    ),
    "production_orders": frozenset(
        {
            "production_order_id",
            "demand_order_id",
            "routing_version_id",
            "quantity",
            "quantity_unit",
            "release_at_utc",
            "material_ready_at_utc",
            "source",
        }
    ),
    "production_lots": frozenset(
        {
            "production_lot_id",
            "production_order_id",
            "quantity",
            "quantity_unit",
            "source",
        }
    ),
    "execution_facts": frozenset(
        {
            "execution_fact_id",
            "production_lot_id",
            "routing_operation_id",
            "status",
            "observed_at_utc",
            "quantity_unit",
            "source",
        }
    ),
    "operation_locks": frozenset(
        {
            "lock_id",
            "production_lot_id",
            "routing_operation_id",
            "lock_type",
            "resource_id",
            "start_at_utc",
            "end_at_utc",
            "source",
        }
    ),
}

OPTIONAL_FIELDS: Mapping[str, frozenset[str]] = {
    **{collection: frozenset() for collection in REQUIRED_FIELDS},
    "routing_precedence_edges": frozenset({"max_lag_seconds"}),
    "execution_facts": frozenset(
        {
            "resource_id",
            "actual_start_at_utc",
            "actual_end_at_utc",
            "completed_quantity",
            "remaining_quantity",
            "remaining_seconds",
        }
    ),
}

ENTITY_TYPE_BY_COLLECTION: Mapping[str, str] = {
    "factories": "Factory",
    "workshops": "Workshop",
    "production_lines": "ProductionLine",
    "resource_groups": "ResourceGroup",
    "resources": "Resource",
    "calendars": "Calendar",
    "products": "Product",
    "routing_versions": "RoutingVersion",
    "routing_operations": "RoutingOperation",
    "routing_precedence_edges": "RoutingPrecedenceEdge",
    "routing_resource_options": "RoutingResourceOption",
    "demand_orders": "DemandOrder",
    "production_orders": "ProductionOrder",
    "production_lots": "ProductionLot",
    "execution_facts": "ExecutionFact",
    "operation_locks": "OperationLock",
}

_DURATION_REQUIRED_FIELDS = {
    "min_lag_seconds",
    "transport_lag_seconds",
    "setup_seconds",
    "cycle_seconds_per_unit",
    "final_duration_seconds",
    "duration_source",
    "duration_source_version",
}
_RESOURCE_REFERENCE_COLLECTIONS = {
    "routing_resource_options",
    "execution_facts",
    "operation_locks",
}

_REFERENCE_RULES = (
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
    ("execution_facts", "resource_id", "resources"),
    ("operation_locks", "production_lot_id", "production_lots"),
    ("operation_locks", "routing_operation_id", "routing_operations"),
    ("operation_locks", "resource_id", "resources"),
)


@dataclass(frozen=True)
class CanonicalView:
    """Stable, best-effort view of canonical collections for all validators."""

    package_id: str
    source_versions: Mapping[str, str]
    collections: Mapping[str, tuple[Mapping[str, object], ...]]
    indexes: Mapping[str, Mapping[str, Mapping[str, object]]]

    def records(self, collection: str) -> tuple[Mapping[str, object], ...]:
        return self.collections.get(collection, ())

    def get(self, collection: str, identifier: object) -> Mapping[str, object] | None:
        if not isinstance(identifier, str):
            return None
        return self.indexes.get(collection, {}).get(identifier)


def _valid_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        canonical_id(value)
    except ContractValueError:
        return None
    return value


def _safe_location_token(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 256:
        return None
    if any(character.isspace() or ord(character) < 32 for character in value):
        return None
    return value


def record_entity_id(collection: str, record: Mapping[str, object]) -> str:
    identifier = _valid_identifier(record.get(COLLECTION_ID_FIELDS[collection]))
    return identifier or f"unidentified-{stable_fingerprint(record)}"


def record_source_location(
    view: CanonicalView,
    collection: str,
    record: Mapping[str, object],
    field: str,
) -> str:
    source = record.get("source")
    if isinstance(source, Mapping):
        system = _safe_location_token(source.get("source_system"))
        version = _safe_location_token(source.get("source_version"))
        source_id = _safe_location_token(source.get("source_record_id"))
        if system is not None and version is not None and source_id is not None:
            return f"{system}@{version}:{source_id}#{collection}.{field}"
    return (
        f"canonical-import:{view.package_id}#{collection}/"
        f"{record_entity_id(collection, record)}/{field}"
    )


def add_record_issue(
    issues: IssueCollector,
    view: CanonicalView,
    collection: str,
    record: Mapping[str, object],
    code: ProductErrorCodeV2,
    *,
    field: str,
    observed_value: object,
    expected_contract: str,
    action: str,
    message: str,
) -> None:
    issues.add(
        code,
        entity_type=ENTITY_TYPE_BY_COLLECTION[collection],
        entity_id=record_entity_id(collection, record),
        field=field,
        observed_value=observed_value,
        expected_contract=expected_contract,
        source_location=record_source_location(view, collection, record, field),
        action=action,
        message=message,
    )


def _package_location(package_id: str, field: str) -> str:
    return f"canonical-import:{package_id}#{field}"


def _add_package_issue(
    issues: IssueCollector,
    package_id: str,
    code: ProductErrorCodeV2,
    *,
    field: str,
    observed_value: object,
    expected_contract: str,
    action: str,
    message: str,
) -> None:
    issues.add(
        code,
        entity_type="ImportPackage",
        entity_id=package_id,
        field=field,
        observed_value=observed_value,
        expected_contract=expected_contract,
        source_location=_package_location(package_id, field),
        action=action,
        message=message,
    )


def validate_structure_and_references(
    document: Mapping[str, object], issues: IssueCollector
) -> CanonicalView:
    """Build a stable view while collecting structural and reference issues."""

    package_id = _valid_identifier(document.get("package_id"))
    if package_id is None:
        package_id = f"invalid-import-{stable_fingerprint(document)}"
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="package_id",
            observed_value=document.get("package_id"),
            expected_contract="non-empty whitespace-free canonical package ID",
            action="provide the content-derived Import v2 package ID",
            message="Import package ID is missing or invalid",
        )

    unknown_root = sorted(set(document) - _IMPORT_FIELDS)
    if unknown_root:
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="<root>",
            observed_value=unknown_root,
            expected_contract="strict import-package.v2 root fields",
            action="remove fields not declared by import-package.v2",
            message="Import package contains unknown root fields",
        )
    for field, expected in (
        ("import_package_version", "import-package.v2"),
        ("schema_set_version", "2.0.0"),
    ):
        if document.get(field) != expected:
            _add_package_issue(
                issues,
                package_id,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field=field,
                observed_value=document.get(field),
                expected_contract=expected,
                action=f"select the explicit {expected} document contract",
                message=f"Import package {field} does not match the v2 contract",
            )
    for field in ("normalization_rule_version", "canonicalization_version"):
        value = document.get(field)
        if not isinstance(value, str) or not value:
            _add_package_issue(
                issues,
                package_id,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field=field,
                observed_value=value,
                expected_contract="non-empty explicit version identifier",
                action=f"provide the exact {field}",
                message=f"Import package {field} is missing or invalid",
            )

    source_versions_raw = document.get("source_versions")
    source_versions: dict[str, str] = {}
    if not isinstance(source_versions_raw, Mapping) or not source_versions_raw:
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="source_versions",
            observed_value=source_versions_raw,
            expected_contract="non-empty source-system to exact-version mapping",
            action="declare every canonical record source and exact version",
            message="Import package source versions are missing or invalid",
        )
    else:
        for system, version in sorted(
            source_versions_raw.items(), key=lambda item: str(item[0])
        ):
            if (
                _valid_identifier(system) is None
                or not isinstance(version, str)
                or not version
            ):
                _add_package_issue(
                    issues,
                    package_id,
                    ProductErrorCodeV2.INVALID_REFERENCE,
                    field="source_versions",
                    observed_value={str(system): version},
                    expected_contract="canonical source ID mapped to non-empty exact version",
                    action="repair the source/version declaration",
                    message="One source version declaration is invalid",
                )
                continue
            source_versions[system] = version

    _validate_synthetic_boundary(document, package_id, issues)

    records_root = document.get("records")
    if not isinstance(records_root, Mapping):
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="records",
            observed_value=records_root,
            expected_contract="canonical-records.v1 object",
            action="provide all canonical record collections",
            message="Canonical records payload is missing or invalid",
        )
        records_root = {}
    if records_root.get("canonical_records_version") != "canonical-records.v1":
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="records.canonical_records_version",
            observed_value=records_root.get("canonical_records_version"),
            expected_contract="canonical-records.v1",
            action="select the explicit canonical-records.v1 contract",
            message="Canonical records version is missing or invalid",
        )
    unknown_collections = sorted(
        set(records_root) - set(COLLECTION_ID_FIELDS) - {"canonical_records_version"}
    )
    if unknown_collections:
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="records",
            observed_value=unknown_collections,
            expected_contract="only canonical-records.v1 collections",
            action="remove undeclared canonical collections",
            message="Canonical records contain unknown collections",
        )

    collections: dict[str, tuple[Mapping[str, object], ...]] = {}
    for collection in COLLECTION_ID_FIELDS:
        raw_collection = records_root.get(collection)
        if not isinstance(raw_collection, list):
            _add_package_issue(
                issues,
                package_id,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field=f"records.{collection}",
                observed_value=raw_collection,
                expected_contract="explicit canonical-records.v1 array",
                action=f"provide the {collection} collection, using [] when empty",
                message=f"Canonical collection {collection} is missing or invalid",
            )
            collections[collection] = ()
            continue
        mapped_records: list[Mapping[str, object]] = []
        for raw_record in raw_collection:
            if isinstance(raw_record, Mapping):
                mapped_records.append(raw_record)
            else:
                _add_package_issue(
                    issues,
                    package_id,
                    ProductErrorCodeV2.INVALID_REFERENCE,
                    field=f"records.{collection}",
                    observed_value=raw_record,
                    expected_contract="canonical record object",
                    action="replace the non-object collection item",
                    message=f"Canonical collection {collection} contains a non-object",
                )
        mapped_records.sort(
            key=lambda record: (
                str(record.get(COLLECTION_ID_FIELDS[collection], "")),
                stable_json_text(record),
            )
        )
        collections[collection] = tuple(mapped_records)

    indexes: dict[str, dict[str, Mapping[str, object]]] = {
        collection: {} for collection in COLLECTION_ID_FIELDS
    }
    view = CanonicalView(package_id, source_versions, collections, indexes)
    for collection in COLLECTION_ID_FIELDS:
        id_field = COLLECTION_ID_FIELDS[collection]
        grouped: dict[str, list[Mapping[str, object]]] = {}
        for record in view.records(collection):
            _validate_record_shape(view, collection, record, issues)
            _validate_record_source(view, collection, record, issues)
            identifier = _valid_identifier(record.get(id_field))
            if identifier is None:
                add_record_issue(
                    issues,
                    view,
                    collection,
                    record,
                    ProductErrorCodeV2.INVALID_REFERENCE,
                    field=id_field,
                    observed_value=record.get(id_field),
                    expected_contract="non-empty whitespace-free canonical ID",
                    action=f"provide a valid unique {id_field}",
                    message=f"{ENTITY_TYPE_BY_COLLECTION[collection]} ID is invalid",
                )
                continue
            grouped.setdefault(identifier, []).append(record)
        for identifier, matching in sorted(grouped.items()):
            indexes[collection][identifier] = matching[0]
            if len(matching) > 1:
                add_record_issue(
                    issues,
                    view,
                    collection,
                    matching[0],
                    ProductErrorCodeV2.DUPLICATE_ID,
                    field=id_field,
                    observed_value={"id": identifier, "count": len(matching)},
                    expected_contract=f"unique {id_field} within {collection}",
                    action="deduplicate the authoritative canonical records",
                    message=f"Duplicate {ENTITY_TYPE_BY_COLLECTION[collection]} ID",
                )

    _validate_reference_rules(view, issues)
    _validate_lineage(view, issues)
    return view


def _validate_synthetic_boundary(
    document: Mapping[str, object], package_id: str, issues: IssueCollector
) -> None:
    synthetic = document.get("synthetic")
    provenance = document.get("synthetic_provenance")
    if not isinstance(synthetic, bool):
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="synthetic",
            observed_value=synthetic,
            expected_contract="explicit boolean data-plane marker",
            action="set synthetic explicitly from the staged data plane",
            message="Synthetic marker is missing or invalid",
        )
        return
    if synthetic and not isinstance(provenance, Mapping):
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.MISSING_SCENARIO_ID,
            field="synthetic_provenance",
            observed_value=provenance,
            expected_contract="complete synthetic provenance for synthetic imports",
            action="provide scenario/profile/generator versions and seed",
            message="Synthetic Import is missing provenance",
        )
        return
    if not synthetic and provenance is not None:
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.SYNTHETIC_REFERENCE_IN_PRODUCTION,
            field="synthetic_provenance",
            observed_value=provenance,
            expected_contract="Production Import contains no synthetic provenance",
            action="remove synthetic references or use the Simulation data plane",
            message="Production Import carries synthetic provenance",
        )
        return
    if not isinstance(provenance, Mapping):
        return
    unknown = sorted(set(provenance) - _SYNTHETIC_FIELDS)
    missing = sorted(_SYNTHETIC_FIELDS - set(provenance))
    if unknown or missing:
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.MISSING_SCENARIO_ID,
            field="synthetic_provenance",
            observed_value={"missing": missing, "unknown": unknown},
            expected_contract="exact complete Import v2 synthetic provenance fields",
            action="repair the versioned synthetic provenance",
            message="Synthetic provenance fields do not match the contract",
        )
    for field in _SYNTHETIC_FIELDS - {"seed"}:
        value = provenance.get(field)
        if not isinstance(value, str) or not value:
            _add_package_issue(
                issues,
                package_id,
                ProductErrorCodeV2.MISSING_SCENARIO_ID,
                field=f"synthetic_provenance.{field}",
                observed_value=value,
                expected_contract="non-empty versioned synthetic provenance value",
                action=f"provide {field}",
                message="Synthetic provenance value is missing or invalid",
            )
    seed = provenance.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**63 - 1:
        _add_package_issue(
            issues,
            package_id,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="synthetic_provenance.seed",
            observed_value=seed,
            expected_contract="non-negative signed 64-bit integer seed",
            action="provide the exact deterministic generator seed",
            message="Synthetic seed is invalid",
        )


def _missing_code(collection: str, field: str) -> ProductErrorCodeV2:
    if field in _DURATION_REQUIRED_FIELDS:
        return ProductErrorCodeV2.MISSING_DURATION
    if field == "quantity_unit":
        return ProductErrorCodeV2.UNIT_CONVERSION_ERROR
    if field == "resource_id" and collection in _RESOURCE_REFERENCE_COLLECTIONS:
        return ProductErrorCodeV2.MISSING_RESOURCE
    return ProductErrorCodeV2.INVALID_REFERENCE


def _validate_record_shape(
    view: CanonicalView,
    collection: str,
    record: Mapping[str, object],
    issues: IssueCollector,
) -> None:
    missing = sorted(REQUIRED_FIELDS[collection] - set(record))
    for field in missing:
        code = _missing_code(collection, field)
        add_record_issue(
            issues,
            view,
            collection,
            record,
            code,
            field=field,
            observed_value=None,
            expected_contract=f"required canonical-records.v1 field {field}",
            action=f"provide explicit {field}; no default is allowed",
            message=f"Required {ENTITY_TYPE_BY_COLLECTION[collection]} field is missing",
        )
    allowed = REQUIRED_FIELDS[collection] | OPTIONAL_FIELDS[collection]
    unknown = sorted(set(record) - allowed)
    if unknown:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="<record>",
            observed_value=unknown,
            expected_contract="strict canonical-records.v1 record fields",
            action="remove fields outside the versioned canonical contract",
            message=f"{ENTITY_TYPE_BY_COLLECTION[collection]} has unknown fields",
        )


def _validate_record_source(
    view: CanonicalView,
    collection: str,
    record: Mapping[str, object],
    issues: IssueCollector,
) -> None:
    source = record.get("source")
    if not isinstance(source, Mapping):
        if "source" in record:
            add_record_issue(
                issues,
                view,
                collection,
                record,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field="source",
                observed_value=source,
                expected_contract="canonical source reference object",
                action="provide source system/version/record ID",
                message="Canonical record source is invalid",
            )
        return
    unknown = sorted(set(source) - _SOURCE_FIELDS)
    missing = sorted(_SOURCE_FIELDS - set(source))
    if unknown or missing:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="source",
            observed_value={"missing": missing, "unknown": unknown},
            expected_contract="exact source_system/source_version/source_record_id object",
            action="repair canonical record provenance",
            message="Canonical record source fields are invalid",
        )
    system = _valid_identifier(source.get("source_system"))
    version = source.get("source_version")
    source_id = _valid_identifier(source.get("source_record_id"))
    if system is None or not isinstance(version, str) or not version or source_id is None:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="source",
            observed_value=source,
            expected_contract="valid canonical source identity and exact version",
            action="repair the source reference without inventing authority",
            message="Canonical record source values are invalid",
        )
        return
    if view.source_versions.get(system) != version:
        add_record_issue(
            issues,
            view,
            collection,
            record,
            ProductErrorCodeV2.INVALID_REFERENCE,
            field="source.source_version",
            observed_value={"source_system": system, "source_version": version},
            expected_contract="record source/version present in Import source_versions",
            action="align the record provenance and envelope source version",
            message="Canonical record source version is absent from the envelope",
        )


def _validate_reference_rules(view: CanonicalView, issues: IssueCollector) -> None:
    for collection, field, target in _REFERENCE_RULES:
        for record in view.records(collection):
            if field not in record:
                continue
            value = record.get(field)
            if _valid_identifier(value) is None or view.get(target, value) is None:
                code = (
                    ProductErrorCodeV2.MISSING_RESOURCE
                    if field == "resource_id"
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
                    expected_contract=f"reference to an existing {ENTITY_TYPE_BY_COLLECTION[target]}",
                    action=f"provide the referenced {target} record or correct {field}",
                    message=f"Canonical {field} reference cannot be resolved",
                )


def _validate_lineage(view: CanonicalView, issues: IssueCollector) -> None:
    for edge in view.records("routing_precedence_edges"):
        route_id = edge.get("routing_version_id")
        predecessor = view.get(
            "routing_operations", edge.get("predecessor_routing_operation_id")
        )
        successor = view.get(
            "routing_operations", edge.get("successor_routing_operation_id")
        )
        if predecessor is None or successor is None or view.get("routing_versions", route_id) is None:
            continue
        if (
            predecessor.get("routing_version_id") != route_id
            or successor.get("routing_version_id") != route_id
        ):
            add_record_issue(
                issues,
                view,
                "routing_precedence_edges",
                edge,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field="routing_version_id",
                observed_value={
                    "edge": route_id,
                    "predecessor": predecessor.get("routing_version_id"),
                    "successor": successor.get("routing_version_id"),
                },
                expected_contract="edge and both endpoints belong to one routing version",
                action="repair the routing-version lineage",
                message="Routing edge endpoints cross routing versions",
            )

    for order in view.records("production_orders"):
        demand = view.get("demand_orders", order.get("demand_order_id"))
        route = view.get("routing_versions", order.get("routing_version_id"))
        if demand is None or route is None:
            continue
        if demand.get("product_id") != route.get("product_id"):
            add_record_issue(
                issues,
                view,
                "production_orders",
                order,
                ProductErrorCodeV2.INVALID_REFERENCE,
                field="routing_version_id",
                observed_value={
                    "demand_product_id": demand.get("product_id"),
                    "routing_product_id": route.get("product_id"),
                },
                expected_contract="ProductionOrder routing product equals DemandOrder product",
                action="select the authoritative routing version for the demanded product",
                message="ProductionOrder routing lineage is inconsistent",
            )

    for collection in ("execution_facts", "operation_locks"):
        for record in view.records(collection):
            lot = view.get("production_lots", record.get("production_lot_id"))
            operation = view.get(
                "routing_operations", record.get("routing_operation_id")
            )
            if lot is None or operation is None:
                continue
            order = view.get("production_orders", lot.get("production_order_id"))
            if order is None:
                continue
            if operation.get("routing_version_id") != order.get("routing_version_id"):
                add_record_issue(
                    issues,
                    view,
                    collection,
                    record,
                    ProductErrorCodeV2.INVALID_REFERENCE,
                    field="routing_operation_id",
                    observed_value={
                        "operation_routing_version_id": operation.get(
                            "routing_version_id"
                        ),
                        "order_routing_version_id": order.get("routing_version_id"),
                    },
                    expected_contract="fact or lock operation belongs to the lot order routing",
                    action="repair the execution/lock lineage",
                    message=f"{ENTITY_TYPE_BY_COLLECTION[collection]} routing lineage is inconsistent",
                )


__all__ = [
    "CanonicalView",
    "ENTITY_TYPE_BY_COLLECTION",
    "OPTIONAL_FIELDS",
    "REQUIRED_FIELDS",
    "add_record_issue",
    "record_entity_id",
    "record_source_location",
    "validate_structure_and_references",
]
