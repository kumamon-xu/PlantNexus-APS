"""TEST-NORMALIZATION-001: deterministic P1 normalization evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.domain.canonical_records import (
    CanonicalContractError,
    ImportPackageDocumentV2,
    validate_import_package_v2,
)
from app.importers import (
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)
from app.importers.adapter import ReferenceRecord
from app.normalization import (
    FieldMapping,
    FieldTransform,
    MappingProfile,
    MAX_DURATION_SECONDS,
    NormalizationError,
    NormalizationErrorCode,
    NormalizationInput,
    RecordMapping,
    UnitConversionRegistry,
    canonical_json_bytes,
    normalize_import,
    normalize_utc_instant,
    stable_canonical_id,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
RULE_PATH = ROOT / "schemas" / "rules" / "unit-conversion-registry.v1.yaml"


FACTORY_MAPPING = RecordMapping(
    record_type="factory",
    collection="factories",
    fields=(
        FieldMapping(
            "$source_record_id",
            "factory_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="factory",
        ),
        FieldMapping("code", "factory_code", FieldTransform.TEXT),
        FieldMapping("timezone", "factory_timezone", FieldTransform.TEXT),
    ),
)
DEMAND_MAPPING = RecordMapping(
    record_type="demand_order",
    collection="demand_orders",
    fields=(
        FieldMapping(
            "$source_record_id",
            "demand_order_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="demand",
        ),
        FieldMapping(
            "product_ref",
            "product_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="product",
        ),
        FieldMapping("quantity", "quantity", FieldTransform.POSITIVE_NUMBER),
        FieldMapping("quantity_unit", "quantity_unit", FieldTransform.TEXT),
        FieldMapping("due_at", "due_at_utc", FieldTransform.UTC_INSTANT),
    ),
)
EDGE_MAPPING = RecordMapping(
    record_type="routing_edge",
    collection="routing_precedence_edges",
    fields=(
        FieldMapping(
            "$source_record_id",
            "routing_precedence_edge_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="routing-edge",
        ),
        FieldMapping(
            "routing_ref",
            "routing_version_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="routing",
        ),
        FieldMapping(
            "predecessor_ref",
            "predecessor_routing_operation_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="routing-operation",
        ),
        FieldMapping(
            "successor_ref",
            "successor_routing_operation_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="routing-operation",
        ),
        FieldMapping(
            "min_lag",
            "min_lag_seconds",
            FieldTransform.NONNEGATIVE_DURATION_SECONDS,
            unit_field="min_lag_unit",
        ),
        FieldMapping(
            "max_lag",
            "max_lag_seconds",
            FieldTransform.NONNEGATIVE_DURATION_SECONDS,
            required=False,
            unit_field="max_lag_unit",
        ),
        FieldMapping(
            "transport_lag",
            "transport_lag_seconds",
            FieldTransform.NONNEGATIVE_DURATION_SECONDS,
            unit_field="transport_lag_unit",
        ),
    ),
)
CALENDAR_MAPPING = RecordMapping(
    record_type="calendar",
    collection="calendars",
    fields=(
        FieldMapping(
            "$source_record_id",
            "calendar_id",
            FieldTransform.CANONICAL_ID,
            id_namespace="calendar",
        ),
        FieldMapping("timezone", "timezone", FieldTransform.TEXT),
        FieldMapping(
            "intervals",
            "unavailable_intervals",
            FieldTransform.UNAVAILABLE_INTERVALS,
            id_namespace="calendar-interval",
        ),
    ),
)


def registry() -> UnitConversionRegistry:
    document = cast(
        dict[str, object], yaml.safe_load(RULE_PATH.read_text(encoding="utf-8"))
    )
    return UnitConversionRegistry.from_mapping(document)


def profile(
    *records: RecordMapping,
    profile_version: str = "1.0.0",
    source_system: str = "reference",
    source_version: str = "1.0.0",
    unit_registry_version: str = "unit-conversion-registry.v1",
) -> MappingProfile:
    return MappingProfile(
        profile_id="reference-mapping",
        profile_version=profile_version,
        source_system=source_system,
        source_version=source_version,
        unit_registry_version=unit_registry_version,
        records=records or (FACTORY_MAPPING,),
    )


def reference_row(
    record_type: str,
    source_record_id: str,
    payload: dict[str, object],
    *,
    source_location: str = "reference.csv:2",
) -> RawImportRow:
    record = ReferenceRecord(
        record_type=record_type,
        source_record_id=source_record_id,
        payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        source_location=source_location,
    )
    return RawImportRow(
        row_identity=record.row_identity,
        source_location=source_location,
        raw_payload=record.raw_payload,
    )


def staged_batch(
    rows: tuple[RawImportRow, ...],
    *,
    batch_id: str = "BATCH-001",
    source_system: str = "reference",
    source_version: str = "1.0.0",
    received_at: datetime = datetime(2026, 8, 19, tzinfo=UTC),
    data_plane: StagingDataPlane = StagingDataPlane.PRODUCTION,
    provenance: SyntheticImportProvenance | None = None,
    content_token: bytes = b"transport-content-a",
) -> StagedImportBatch:
    return StagedImportBatch(
        batch_id=batch_id,
        idempotency_key=f"idempotency-{batch_id}",
        source_system=source_system,
        source_version=source_version,
        content_sha256=hashlib.sha256(content_token).hexdigest(),
        source_name=f"{batch_id}.csv",
        media_type="text/csv",
        content_length_bytes=len(content_token),
        received_at=received_at,
        data_plane=data_plane,
        rows=rows,
        synthetic_provenance=provenance,
    )


def import_validator() -> Draft202012Validator:
    registered = Registry()
    for filename in (
        "canonical-records.v1.schema.json",
        "import-package.v2.schema.json",
    ):
        schema = cast(
            dict[str, Any],
            json.loads((SCHEMA_ROOT / filename).read_text(encoding="utf-8")),
        )
        registered = registered.with_resource(
            schema["$id"], Resource.from_contents(schema)
        )
    import_schema = cast(
        dict[str, Any],
        json.loads(
            (SCHEMA_ROOT / "import-package.v2.schema.json").read_text(encoding="utf-8")
        ),
    )
    return Draft202012Validator(
        import_schema, registry=registered, format_checker=FormatChecker()
    )


def test_id_time_and_unit_primitives_are_deterministic_and_exact() -> None:
    identifier = stable_canonical_id("factory", "reference", "F-001")
    assert identifier == stable_canonical_id("factory", "reference", "F-001")
    assert identifier != stable_canonical_id("workshop", "reference", "F-001")
    assert identifier != stable_canonical_id("factory", "other", "F-001")
    assert " " not in identifier

    assert (
        normalize_utc_instant(
            "2026-08-19T08:15:30+08:00", source_location="row:1", field="due_at"
        )
        == "2026-08-19T00:15:30Z"
    )
    assert (
        normalize_utc_instant(
            "2026-11-01T01:30:00-04:00", source_location="row:1", field="due_at"
        )
        == "2026-11-01T05:30:00Z"
    )
    assert (
        normalize_utc_instant(
            "2026-11-01T01:30:00-05:00", source_location="row:1", field="due_at"
        )
        == "2026-11-01T06:30:00Z"
    )
    for invalid in (
        "2026-08-19T08:15:30",
        "2026-08-19T08:15:30.1Z",
        "2026-08-19",
        "2026-08-19T08:15:30-00:00",
    ):
        with pytest.raises(NormalizationError) as rejected:
            normalize_utc_instant(invalid, source_location="row:1", field="due_at")
        assert rejected.value.code is NormalizationErrorCode.INVALID_TIMEZONE

    unit_registry = registry()
    assert (
        unit_registry.convert_duration(
            4, "s", source_location="row:1", field="lag", allow_zero=True
        )
        == 4
    )
    assert (
        unit_registry.convert_duration(
            4, "min", source_location="row:1", field="lag", allow_zero=True
        )
        == 240
    )
    assert (
        unit_registry.convert_duration(
            4, "h", source_location="row:1", field="lag", allow_zero=True
        )
        == 14_400
    )


def test_normalizer_produces_schema_and_domain_valid_import_without_defaults() -> None:
    row = reference_row("factory", "F-001", {"code": "F001", "timezone": "UTC"})
    result = normalize_import(
        (NormalizationInput(staged_batch((row,)), profile(FACTORY_MAPPING)),),
        unit_registry=registry(),
    )

    import_validator().validate(result.document)
    validate_import_package_v2(cast(ImportPackageDocumentV2, result.document))
    assert result.document["schema_set_version"] == "2.0.0"
    assert result.document["synthetic"] is False
    assert "synthetic_provenance" not in result.document
    assert "reference-mapping@1.0.0" in cast(
        str, result.document["normalization_rule_version"]
    )
    assert (
        result.dataset_hash
        == f"sha256:{hashlib.sha256(result.canonical_bytes).hexdigest()}"
    )
    assert result.canonical_bytes == canonical_json_bytes(result.document)
    records = cast(dict[str, Any], result.document["records"])
    factory = records["factories"][0]
    assert factory["factory_id"] == stable_canonical_id("factory", "reference", "F-001")
    assert factory["source"]["source_record_id"] == "F-001"


def test_source_record_provenance_must_be_canonical_and_is_never_fabricated() -> None:
    row = reference_row("factory", "F 001", {"code": "F001", "timezone": "UTC"})
    with pytest.raises(NormalizationError) as rejected:
        normalize_import(
            (NormalizationInput(staged_batch((row,)), profile(FACTORY_MAPPING)),),
            unit_registry=registry(),
        )
    assert rejected.value.code is NormalizationErrorCode.INVALID_VALUE
    assert rejected.value.field == "source_record_id"


def test_replay_ignores_transport_volatility_and_source_row_order() -> None:
    first = reference_row(
        "factory", "F-002", {"code": "F002", "timezone": "UTC"}, source_location="a:2"
    )
    second = reference_row(
        "factory", "F-001", {"code": "F001", "timezone": "UTC"}, source_location="a:3"
    )
    replay_first = RawImportRow(first.row_identity, "b:99", first.raw_payload)
    replay_second = RawImportRow(second.row_identity, "b:98", second.raw_payload)
    left = normalize_import(
        (
            NormalizationInput(
                staged_batch((first, second), batch_id="BATCH-A"),
                profile(FACTORY_MAPPING),
            ),
        ),
        unit_registry=registry(),
    )
    right = normalize_import(
        (
            NormalizationInput(
                staged_batch(
                    (replay_second, replay_first),
                    batch_id="BATCH-B",
                    received_at=datetime(2027, 1, 1, tzinfo=UTC),
                    content_token=b"different-transport-file",
                ),
                profile(FACTORY_MAPPING),
            ),
        ),
        unit_registry=registry(),
    )

    assert left.canonical_bytes == right.canonical_bytes
    assert left.dataset_hash == right.dataset_hash
    assert left.document["package_id"] == right.document["package_id"]
    assert left.source_batch_ids != right.source_batch_ids
    factories = cast(dict[str, Any], left.document["records"])["factories"]
    assert [record["factory_id"] for record in factories] == sorted(
        record["factory_id"] for record in factories
    )


def test_mapping_profile_version_changes_bytes_and_hash() -> None:
    row = reference_row("factory", "F-001", {"code": "F001", "timezone": "UTC"})
    batch = staged_batch((row,))
    first = normalize_import(
        (NormalizationInput(batch, profile(FACTORY_MAPPING, profile_version="1.0.0")),),
        unit_registry=registry(),
    )
    second = normalize_import(
        (NormalizationInput(batch, profile(FACTORY_MAPPING, profile_version="1.1.0")),),
        unit_registry=registry(),
    )
    assert first.canonical_bytes != second.canonical_bytes
    assert first.dataset_hash != second.dataset_hash
    assert first.document["records"] == second.document["records"]


def test_mapping_can_name_a_cross_source_id_authority() -> None:
    product_reference = replace(
        DEMAND_MAPPING.fields[1], id_source_system="erp-authority"
    )
    cross_source_mapping = replace(
        DEMAND_MAPPING,
        fields=(
            DEMAND_MAPPING.fields[0],
            product_reference,
            *DEMAND_MAPPING.fields[2:],
        ),
    )
    row = reference_row(
        "demand_order",
        "D-001",
        {
            "product_ref": "P-001",
            "quantity": 1,
            "quantity_unit": "piece",
            "due_at": "2026-08-20T00:00:00Z",
        },
    )
    result = normalize_import(
        (NormalizationInput(staged_batch((row,)), profile(cross_source_mapping)),),
        unit_registry=registry(),
    )
    demand = cast(dict[str, Any], result.document["records"])["demand_orders"][0]
    assert demand["product_id"] == stable_canonical_id(
        "product", "erp-authority", "P-001"
    )


def test_record_mapping_normalizes_offsets_durations_and_nested_intervals() -> None:
    rows = (
        reference_row(
            "demand_order",
            "D-001",
            {
                "product_ref": "P-001",
                "quantity": 2.5,
                "quantity_unit": "piece",
                "due_at": "2026-08-19T08:00:00+08:00",
            },
        ),
        reference_row(
            "routing_edge",
            "E-001",
            {
                "routing_ref": "R-001",
                "predecessor_ref": "O-001",
                "successor_ref": "O-002",
                "min_lag": 2,
                "min_lag_unit": "min",
                "max_lag": 1,
                "max_lag_unit": "h",
                "transport_lag": 30,
                "transport_lag_unit": "s",
            },
        ),
        reference_row(
            "calendar",
            "C-001",
            {
                "timezone": "America/New_York",
                "intervals": [
                    {
                        "interval_id": "DOWN-B",
                        "start_at": "2026-11-01T01:30:00-05:00",
                        "end_at": "2026-11-01T02:00:00-05:00",
                        "reason": "maintenance",
                    },
                    {
                        "interval_id": "DOWN-A",
                        "start_at": "2026-11-01T01:30:00-04:00",
                        "end_at": "2026-11-01T02:00:00-04:00",
                        "reason": "inspection",
                    },
                ],
            },
        ),
    )
    result = normalize_import(
        (
            NormalizationInput(
                staged_batch(rows),
                profile(DEMAND_MAPPING, EDGE_MAPPING, CALENDAR_MAPPING),
            ),
        ),
        unit_registry=registry(),
    )
    import_validator().validate(result.document)
    records = cast(dict[str, Any], result.document["records"])
    assert records["demand_orders"][0]["due_at_utc"] == "2026-08-19T00:00:00Z"
    edge = records["routing_precedence_edges"][0]
    assert (
        edge["min_lag_seconds"],
        edge["max_lag_seconds"],
        edge["transport_lag_seconds"],
    ) == (
        120,
        3600,
        30,
    )
    intervals = records["calendars"][0]["unavailable_intervals"]
    assert [interval["interval_id"] for interval in intervals] == sorted(
        interval["interval_id"] for interval in intervals
    )
    assert {interval["start_at_utc"] for interval in intervals} == {
        "2026-11-01T05:30:00Z",
        "2026-11-01T06:30:00Z",
    }


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (
            {
                "routing_ref": "R-001",
                "predecessor_ref": "O-001",
                "successor_ref": "O-002",
                "min_lag_unit": "min",
                "transport_lag": 1,
                "transport_lag_unit": "s",
            },
            NormalizationErrorCode.MISSING_DURATION,
        ),
        (
            {
                "routing_ref": "R-001",
                "predecessor_ref": "O-001",
                "successor_ref": "O-002",
                "min_lag": 1,
                "min_lag_unit": "fortnight",
                "transport_lag": 1,
                "transport_lag_unit": "s",
            },
            NormalizationErrorCode.UNIT_CONVERSION_ERROR,
        ),
        (
            {
                "routing_ref": "R-001",
                "predecessor_ref": "O-001",
                "successor_ref": "O-002",
                "min_lag": MAX_DURATION_SECONDS + 1,
                "min_lag_unit": "s",
                "transport_lag": 1,
                "transport_lag_unit": "s",
            },
            NormalizationErrorCode.UNIT_CONVERSION_ERROR,
        ),
    ],
)
def test_normalizer_has_exact_duration_rejections(
    payload: dict[str, object], expected_code: NormalizationErrorCode
) -> None:
    row = reference_row("routing_edge", "E-001", payload)
    with pytest.raises(NormalizationError) as rejected:
        normalize_import(
            (NormalizationInput(staged_batch((row,)), profile(EDGE_MAPPING)),),
            unit_registry=registry(),
        )
    assert rejected.value.code is expected_code
    assert rejected.value.source_location == "reference.csv:2"


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"timezone": "UTC"}, NormalizationErrorCode.MISSING_FIELD),
        (
            {"code": "F001", "timezone": "UTC", "unexpected": "x"},
            NormalizationErrorCode.UNKNOWN_FIELD,
        ),
    ],
)
def test_missing_required_and_unmapped_source_fields_reject(
    payload: dict[str, object], expected_code: NormalizationErrorCode
) -> None:
    row = reference_row("factory", "F-001", payload)
    with pytest.raises(NormalizationError) as rejected:
        normalize_import(
            (NormalizationInput(staged_batch((row,)), profile(FACTORY_MAPPING)),),
            unit_registry=registry(),
        )
    assert rejected.value.code is expected_code


def test_duplicate_json_keys_and_duplicate_canonical_ids_reject() -> None:
    duplicate_payload = ReferenceRecord(
        record_type="factory",
        source_record_id="F-001",
        payload_json='{"code":"F001","code":"F002","timezone":"UTC"}',
        source_location="reference.csv:2",
    )
    malformed_row = RawImportRow(
        duplicate_payload.row_identity,
        duplicate_payload.source_location,
        duplicate_payload.raw_payload,
    )
    with pytest.raises(NormalizationError) as malformed:
        normalize_import(
            (
                NormalizationInput(
                    staged_batch((malformed_row,)), profile(FACTORY_MAPPING)
                ),
            ),
            unit_registry=registry(),
        )
    assert malformed.value.code is NormalizationErrorCode.INVALID_RAW_ROW

    row = reference_row("factory", "F-001", {"code": "F001", "timezone": "UTC"})
    with pytest.raises(NormalizationError) as duplicate:
        normalize_import(
            (
                NormalizationInput(
                    staged_batch((row,), batch_id="BATCH-A"), profile(FACTORY_MAPPING)
                ),
                NormalizationInput(
                    staged_batch((row,), batch_id="BATCH-B"), profile(FACTORY_MAPPING)
                ),
            ),
            unit_registry=registry(),
        )
    assert duplicate.value.code is NormalizationErrorCode.DUPLICATE_CANONICAL_ID


def test_source_profile_version_and_data_plane_conflicts_reject() -> None:
    row = reference_row("factory", "F-001", {"code": "F001", "timezone": "UTC"})
    mismatched = NormalizationInput(
        staged_batch((row,), source_version="2.0.0"), profile(FACTORY_MAPPING)
    )
    with pytest.raises(NormalizationError) as source_mismatch:
        normalize_import((mismatched,), unit_registry=registry())
    assert source_mismatch.value.code is NormalizationErrorCode.PROFILE_SOURCE_MISMATCH

    first = NormalizationInput(
        staged_batch((row,), batch_id="BATCH-A"), profile(FACTORY_MAPPING)
    )
    second = NormalizationInput(
        staged_batch((row,), batch_id="BATCH-B"),
        profile(FACTORY_MAPPING, profile_version="1.1.0"),
    )
    with pytest.raises(NormalizationError) as authority_conflict:
        normalize_import((first, second), unit_registry=registry())
    assert authority_conflict.value.code is NormalizationErrorCode.CONFLICTING_AUTHORITY

    synthetic = SyntheticImportProvenance(
        scenario_id="SCENARIO-001",
        scenario_version="1.0.0",
        seed=7,
        factory_profile_id="PROFILE-001",
        profile_version="1.0.0",
        generator_id="GENERATOR-001",
        generator_version="1.0.0",
    )
    simulation = NormalizationInput(
        staged_batch(
            (row,),
            batch_id="BATCH-SIM",
            data_plane=StagingDataPlane.SIMULATION,
            provenance=synthetic,
        ),
        profile(FACTORY_MAPPING),
    )
    with pytest.raises(NormalizationError) as plane_conflict:
        normalize_import((first, simulation), unit_registry=registry())
    assert plane_conflict.value.code is NormalizationErrorCode.DATA_PLANE_MISMATCH

    wrong_contract = replace(
        profile(FACTORY_MAPPING), mapping_contract_version="mapping-profile.v2"
    )
    with pytest.raises(NormalizationError) as contract_mismatch:
        normalize_import(
            (NormalizationInput(staged_batch((row,)), wrong_contract),),
            unit_registry=registry(),
        )
    assert (
        contract_mismatch.value.code is NormalizationErrorCode.INVALID_MAPPING_PROFILE
    )


def test_simulation_requires_and_emits_exact_staged_provenance() -> None:
    provenance = SyntheticImportProvenance(
        scenario_id="SCENARIO-001",
        scenario_version="1.0.0",
        seed=20260819,
        factory_profile_id="PROFILE-001",
        profile_version="1.0.0",
        generator_id="GENERATOR-001",
        generator_version="1.0.0",
    )
    row = reference_row("factory", "F-001", {"code": "F001", "timezone": "UTC"})
    result = normalize_import(
        (
            NormalizationInput(
                staged_batch(
                    (row,),
                    data_plane=StagingDataPlane.SIMULATION,
                    provenance=provenance,
                ),
                profile(FACTORY_MAPPING),
            ),
        ),
        unit_registry=registry(),
    )
    import_validator().validate(result.document)
    assert result.document["synthetic"] is True
    assert (
        result.document["synthetic_provenance"] == provenance.fingerprint_projection()
    )

    invalid_version = replace(provenance, scenario_version="latest")
    with pytest.raises(NormalizationError) as rejected:
        normalize_import(
            (
                NormalizationInput(
                    staged_batch(
                        (row,),
                        batch_id="BATCH-BAD-SIM",
                        data_plane=StagingDataPlane.SIMULATION,
                        provenance=invalid_version,
                    ),
                    profile(FACTORY_MAPPING),
                ),
            ),
            unit_registry=registry(),
        )
    assert rejected.value.code is NormalizationErrorCode.INVALID_VALUE
    assert rejected.value.source_location == "synthetic-provenance"


def test_cross_entity_validation_remains_a_later_pipeline_boundary() -> None:
    row = reference_row(
        "demand_order",
        "D-001",
        {
            "product_ref": "MISSING-PRODUCT",
            "quantity": 1,
            "quantity_unit": "piece",
            "due_at": "2026-08-20T00:00:00Z",
        },
    )
    result = normalize_import(
        (NormalizationInput(staged_batch((row,)), profile(DEMAND_MAPPING)),),
        unit_registry=registry(),
    )
    import_validator().validate(result.document)
    with pytest.raises(CanonicalContractError, match="unknown ID"):
        validate_import_package_v2(cast(ImportPackageDocumentV2, result.document))


def test_normalization_module_does_not_cross_later_task_boundaries() -> None:
    module_root = ROOT / "backend" / "app" / "normalization"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(module_root.glob("*.py"))
    ).lower()
    for forbidden in (
        "app.data_validation",
        "app.snapshots",
        "app.planning",
        "ortools",
        "cpmodel",
        "intervalvar",
    ):
        assert forbidden not in source
    assert "default_unit" not in source
