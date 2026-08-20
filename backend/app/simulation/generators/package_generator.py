"""Seven-layer synthetic generation ending at public Standard Import boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast

from app.data_validation import validate_import_package
from app.domain.contracts import ImportPackageDocumentV2, JsonValue
from app.importers import (
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)
from app.normalization import (
    COLLECTION_ID_FIELDS,
    FieldMapping,
    FieldTransform,
    MappingProfile,
    NormalizationError,
    NormalizationInput,
    RecordMapping,
    UnitConversionRegistry,
    normalize_import,
)
from app.simulation.generators.calendars import DeterministicCalendarGenerator
from app.simulation.generators.contracts import (
    CalendarGenerator,
    ExecutionStateGenerator,
    GeneratedRecordCollections,
    GeneratedScenarioPackage,
    GenerationContext,
    LockGenerator,
    MaterialGenerator,
    OrderGenerator,
    P1_GENERATION_MANIFEST_VERSION,
    P1_GENERATOR_VERSION,
    RoutingGenerator,
    SyntheticGenerationManifestDocument,
    SyntheticGeneratorError,
    SyntheticGeneratorErrorCode,
    TopologyGenerator,
    require_p1_generator_context,
)
from app.simulation.generators.determinism import (
    CANONICALIZATION_VERSION,
    SeedMaterial,
    canonical_json_bytes,
    synthetic_time_origin,
)
from app.simulation.generators.execution_states import (
    DeterministicExecutionStateGenerator,
)
from app.simulation.generators.locks import DeterministicLockGenerator
from app.simulation.generators.materials import DeterministicMaterialGenerator
from app.simulation.generators.orders import DeterministicOrderGenerator
from app.simulation.generators.package_contract import (
    validate_p1_generated_scenario_package,
)
from app.simulation.generators.routing import DeterministicRoutingGenerator
from app.simulation.generators.topology import DeterministicTopologyGenerator


P1_SOURCE_SYSTEM = "plantnexus-synthetic"
P1_MAPPING_PROFILE_ID = "P1-SYNTHETIC-SOURCE-MAPPING"
P1_MAPPING_PROFILE_VERSION = "1.0.0"
_SOURCE_RECORD_ID = "$source_record_id"

_ID_NAMESPACES: Mapping[str, str] = {
    "factory_id": "factory",
    "workshop_id": "workshop",
    "production_line_id": "production-line",
    "resource_group_id": "resource-group",
    "resource_id": "resource",
    "calendar_id": "calendar",
    "product_id": "product",
    "routing_version_id": "routing-version",
    "routing_operation_id": "routing-operation",
    "routing_precedence_edge_id": "routing-edge",
    "predecessor_routing_operation_id": "routing-operation",
    "successor_routing_operation_id": "routing-operation",
    "routing_resource_option_id": "routing-option",
    "demand_order_id": "demand-order",
    "production_order_id": "production-order",
    "production_lot_id": "production-lot",
    "execution_fact_id": "execution-fact",
    "lock_id": "operation-lock",
}


def _primary(field_name: str) -> FieldMapping:
    return FieldMapping(
        _SOURCE_RECORD_ID,
        field_name,
        FieldTransform.CANONICAL_ID,
        id_namespace=_ID_NAMESPACES[field_name],
    )


def _reference(field_name: str, *, required: bool = True) -> FieldMapping:
    return FieldMapping(
        field_name,
        field_name,
        FieldTransform.CANONICAL_ID,
        required=required,
        id_namespace=_ID_NAMESPACES[field_name],
    )


def _text(field_name: str, *, required: bool = True) -> FieldMapping:
    return FieldMapping(field_name, field_name, FieldTransform.TEXT, required=required)


def _utc(field_name: str, *, required: bool = True) -> FieldMapping:
    return FieldMapping(
        field_name, field_name, FieldTransform.UTC_INSTANT, required=required
    )


def _number(field_name: str, *, required: bool = True) -> FieldMapping:
    return FieldMapping(
        field_name, field_name, FieldTransform.POSITIVE_NUMBER, required=required
    )


def _text_list(field_name: str) -> FieldMapping:
    return FieldMapping(field_name, field_name, FieldTransform.SORTED_TEXT_LIST)


def _duration(
    field_name: str,
    unit_field: str,
    *,
    positive: bool = False,
    required: bool = True,
) -> FieldMapping:
    transform = (
        FieldTransform.POSITIVE_DURATION_SECONDS
        if positive
        else FieldTransform.NONNEGATIVE_DURATION_SECONDS
    )
    return FieldMapping(
        field_name,
        field_name,
        transform,
        required=required,
        unit_field=unit_field,
    )


def _mapping_records() -> tuple[RecordMapping, ...]:
    return (
        RecordMapping(
            "factories",
            "factories",
            (
                _primary("factory_id"),
                _text("factory_code"),
                _text("factory_timezone"),
            ),
        ),
        RecordMapping(
            "workshops",
            "workshops",
            (
                _primary("workshop_id"),
                _text("workshop_code"),
                _reference("factory_id"),
            ),
        ),
        RecordMapping(
            "production_lines",
            "production_lines",
            (
                _primary("production_line_id"),
                _text("production_line_code"),
                _reference("workshop_id"),
            ),
        ),
        RecordMapping(
            "resource_groups",
            "resource_groups",
            (
                _primary("resource_group_id"),
                _text("resource_group_code"),
                _reference("production_line_id"),
            ),
        ),
        RecordMapping(
            "resources",
            "resources",
            (
                _primary("resource_id"),
                _text("resource_code"),
                _text("resource_type"),
                _text("status"),
                _reference("resource_group_id"),
                _reference("calendar_id"),
                _text_list("capabilities"),
            ),
        ),
        RecordMapping(
            "calendars",
            "calendars",
            (
                _primary("calendar_id"),
                _text("timezone"),
                FieldMapping(
                    "unavailable_intervals",
                    "unavailable_intervals",
                    FieldTransform.UNAVAILABLE_INTERVALS,
                    id_namespace="calendar-interval",
                ),
            ),
        ),
        RecordMapping(
            "products",
            "products",
            (
                _primary("product_id"),
                _text("product_code"),
                _text("quantity_unit"),
            ),
        ),
        RecordMapping(
            "routing_versions",
            "routing_versions",
            (
                _primary("routing_version_id"),
                _text("routing_code"),
                _text("version"),
                _reference("product_id"),
            ),
        ),
        RecordMapping(
            "routing_operations",
            "routing_operations",
            (
                _primary("routing_operation_id"),
                _reference("routing_version_id"),
                _text("operation_code"),
                _text_list("required_capabilities"),
            ),
        ),
        RecordMapping(
            "routing_precedence_edges",
            "routing_precedence_edges",
            (
                _primary("routing_precedence_edge_id"),
                _reference("routing_version_id"),
                _reference("predecessor_routing_operation_id"),
                _reference("successor_routing_operation_id"),
                _duration("min_lag_seconds", "min_lag_unit"),
                _duration("transport_lag_seconds", "transport_lag_unit"),
                _duration(
                    "max_lag_seconds",
                    "max_lag_unit",
                    required=False,
                ),
            ),
        ),
        RecordMapping(
            "routing_resource_options",
            "routing_resource_options",
            (
                _primary("routing_resource_option_id"),
                _reference("routing_operation_id"),
                _reference("resource_id"),
                _text("quantity_unit"),
                _duration("setup_seconds", "setup_unit"),
                _duration("cycle_seconds_per_unit", "cycle_unit"),
                _duration(
                    "final_duration_seconds",
                    "final_duration_unit",
                    positive=True,
                ),
                _text("duration_source"),
                _text("duration_source_version"),
            ),
        ),
        RecordMapping(
            "demand_orders",
            "demand_orders",
            (
                _primary("demand_order_id"),
                _reference("product_id"),
                _number("quantity"),
                _text("quantity_unit"),
                _utc("due_at_utc"),
            ),
        ),
        RecordMapping(
            "production_orders",
            "production_orders",
            (
                _primary("production_order_id"),
                _reference("demand_order_id"),
                _reference("routing_version_id"),
                _number("quantity"),
                _text("quantity_unit"),
                _utc("release_at_utc"),
                _utc("material_ready_at_utc"),
            ),
        ),
        RecordMapping(
            "production_lots",
            "production_lots",
            (
                _primary("production_lot_id"),
                _reference("production_order_id"),
                _number("quantity"),
                _text("quantity_unit"),
            ),
        ),
        RecordMapping(
            "execution_facts",
            "execution_facts",
            (
                _primary("execution_fact_id"),
                _reference("production_lot_id"),
                _reference("routing_operation_id"),
                _text("status"),
                _utc("observed_at_utc"),
                _text("quantity_unit"),
                _reference("resource_id", required=False),
                _utc("actual_start_at_utc", required=False),
                _utc("actual_end_at_utc", required=False),
                _number("completed_quantity", required=False),
                _number("remaining_quantity", required=False),
                _duration(
                    "remaining_seconds",
                    "remaining_unit",
                    positive=True,
                    required=False,
                ),
            ),
        ),
        RecordMapping(
            "operation_locks",
            "operation_locks",
            (
                _primary("lock_id"),
                _reference("production_lot_id"),
                _reference("routing_operation_id"),
                _text("lock_type"),
                _reference("resource_id"),
                _utc("start_at_utc"),
                _utc("end_at_utc"),
            ),
        ),
    )


def p1_mapping_profile(context: GenerationContext) -> MappingProfile:
    """Return the exact source mapping selected by generator v1."""

    return MappingProfile(
        profile_id=P1_MAPPING_PROFILE_ID,
        profile_version=P1_MAPPING_PROFILE_VERSION,
        source_system=P1_SOURCE_SYSTEM,
        source_version=context.generator_version,
        unit_registry_version="unit-conversion-registry.v1",
        records=_mapping_records(),
    )


def _raw_rows(records: GeneratedRecordCollections) -> tuple[RawImportRow, ...]:
    rows: list[RawImportRow] = []
    position = 0
    for collection, id_field in COLLECTION_ID_FIELDS.items():
        for record in records.get(collection, ()):
            if not isinstance(record, Mapping):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    f"{collection} contains a non-object source record",
                )
            source_record_id = record.get(id_field)
            if not isinstance(source_record_id, str):
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.PACKAGE_INVALID,
                    f"{collection} record lacks {id_field}",
                )
            payload: dict[str, JsonValue] = {
                key: value for key, value in record.items() if key != id_field
            }
            outer = {
                "record_type": collection,
                "source_record_id": source_record_id,
                "payload_json": canonical_json_bytes(payload).decode("utf-8"),
            }
            raw_payload = canonical_json_bytes(outer)
            position += 1
            rows.append(
                RawImportRow(
                    row_identity=f"{collection}:{source_record_id}",
                    source_location=f"synthetic-records.jsonl:{position}",
                    raw_payload=raw_payload,
                )
            )
    return tuple(rows)


def _staged_batch(
    context: GenerationContext, records: GeneratedRecordCollections
) -> StagedImportBatch:
    rows = _raw_rows(records)
    content = b"\n".join(row.raw_payload for row in rows)
    digest = sha256(content).hexdigest()
    seed = SeedMaterial(context.seed, context.generator_id, context.generator_version)
    return StagedImportBatch(
        batch_id=f"synthetic-batch-{digest[:24]}",
        idempotency_key=f"synthetic-import-{digest}",
        source_system=P1_SOURCE_SYSTEM,
        source_version=context.generator_version,
        content_sha256=digest,
        source_name="synthetic-records.jsonl",
        media_type="application/x-ndjson",
        content_length_bytes=len(content),
        received_at=synthetic_time_origin(seed.child("timeline")),
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


@dataclass(frozen=True, slots=True)
class DeterministicSyntheticPackageGenerator:
    """Compose seven pure layers, normalize, validate, and return Import v2."""

    unit_registry: UnitConversionRegistry
    topology: TopologyGenerator = field(default_factory=DeterministicTopologyGenerator)
    routing: RoutingGenerator = field(default_factory=DeterministicRoutingGenerator)
    orders: OrderGenerator = field(default_factory=DeterministicOrderGenerator)
    calendars: CalendarGenerator = field(default_factory=DeterministicCalendarGenerator)
    materials: MaterialGenerator = field(default_factory=DeterministicMaterialGenerator)
    execution_states: ExecutionStateGenerator = field(
        default_factory=DeterministicExecutionStateGenerator
    )
    locks: LockGenerator = field(default_factory=DeterministicLockGenerator)

    @property
    def generator_version(self) -> str:
        return P1_GENERATOR_VERSION

    def generate(
        self,
        context: GenerationContext,
        *,
        generated_at: datetime | None = None,
    ) -> GeneratedScenarioPackage:
        require_p1_generator_context(context)
        for layer in (
            self.topology,
            self.routing,
            self.orders,
            self.calendars,
            self.materials,
            self.execution_states,
            self.locks,
        ):
            if layer.generator_version != context.generator_version:
                raise SyntheticGeneratorError(
                    SyntheticGeneratorErrorCode.GENERATOR_VERSION_MISMATCH,
                    "one generator layer does not match ScenarioSpec version",
                )

        records = self.topology.generate_topology(context)
        records = self.routing.generate_routings(context, records)
        records = self.orders.generate_orders(context, records)
        records = self.calendars.generate_calendars(context, records)
        records = self.materials.generate_material_readiness(context, records)
        records = self.execution_states.generate_execution_states(context, records)
        records = self.locks.generate_locks(context, records)
        batch = _staged_batch(context, records)
        try:
            normalized = normalize_import(
                (NormalizationInput(batch, p1_mapping_profile(context)),),
                unit_registry=self.unit_registry,
            )
        except NormalizationError as error:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.NORMALIZATION_REJECTED,
                f"generated source records failed normalization ({error.code.value})",
            ) from error

        quality = validate_import_package(normalized.document)
        if not quality.passed:
            raise SyntheticGeneratorError(
                SyntheticGeneratorErrorCode.DATA_VALIDATION_REJECTED,
                (
                    "generated canonical records failed data validation "
                    f"({quality.document['error_count']} errors)"
                ),
            )
        document = cast(ImportPackageDocumentV2, normalized.document)
        report = quality.document
        now = generated_at or datetime.now(UTC)
        generated_text = now.isoformat(timespec="seconds").replace("+00:00", "Z")
        manifest = cast(
            SyntheticGenerationManifestDocument,
            {
                "generation_manifest_version": P1_GENERATION_MANIFEST_VERSION,
                "synthetic": True,
                "target_environment": context.target.value,
                "scenario": {
                    "scenario_id": context.scenario_id,
                    "scenario_version": context.scenario_version,
                },
                "factory_profile": {
                    "profile_id": context.profile_id,
                    "profile_version": context.profile_version,
                },
                "generator": {
                    "generator_id": context.generator_id,
                    "generator_version": context.generator_version,
                },
                "seed": context.seed,
                "required_capabilities": [
                    capability.value for capability in context.required_capabilities
                ],
                "generated_at": generated_text,
                "canonicalization_version": CANONICALIZATION_VERSION,
                "normalization_rule_version": document["normalization_rule_version"],
                "unit_registry_version": normalized.unit_registry_version,
                "import_package": {
                    "import_package_version": "import-package.v2",
                    "schema_set_version": document["schema_set_version"],
                    "package_id": document["package_id"],
                },
                "import_quality_report": {
                    "report_version": report["report_version"],
                    "report_id": report["report_id"],
                    "status": report["status"],
                    "error_count": report["error_count"],
                },
                "dataset_hash": normalized.dataset_hash,
            },
        )
        generated = GeneratedScenarioPackage(
            import_package=document,
            manifest=manifest,
            canonical_dataset=normalized.canonical_bytes,
            dataset_hash=normalized.dataset_hash,
            quality_report=report,
        )
        validate_p1_generated_scenario_package(generated)
        return generated


__all__ = [
    "DeterministicSyntheticPackageGenerator",
    "P1_MAPPING_PROFILE_ID",
    "P1_MAPPING_PROFILE_VERSION",
    "P1_SOURCE_SYSTEM",
    "p1_mapping_profile",
]
