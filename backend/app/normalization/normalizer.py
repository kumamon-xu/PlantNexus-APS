"""Deterministic Raw Staging to canonical Import v2 normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import NoReturn
from urllib.parse import quote

from app.importers import StagingDataPlane, SyntheticImportProvenance

from .contracts import (
    COLLECTION_ID_FIELDS,
    COLLECTION_OPTIONAL_FIELDS,
    COLLECTION_REQUIRED_FIELDS,
    FieldMapping,
    FieldTransform,
    MappingProfile,
    NormalizationError,
    NormalizationErrorCode,
    NormalizationInput,
    NormalizationResult,
    RecordMapping,
)
from .ids import stable_canonical_id
from .time import normalize_utc_instant
from .units import UnitConversionRegistry

CANONICALIZATION_VERSION = "canonical-json.v1"
IMPORT_PACKAGE_VERSION = "import-package.v2"
IMPORT_DOCUMENT_SCHEMA_SET_VERSION = "2.0.0"
NORMALIZATION_CONTRACT_VERSION = "normalization.v1"
CURRENT_SCHEMA_SET_VERSION = "2.1.0"
_SOURCE_RECORD_ID = "$source_record_id"
_SEMANTIC_VERSION = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


class _DuplicateJsonKey(ValueError):
    pass


class _InvalidJsonConstant(ValueError):
    pass


def canonical_json_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize JSON-compatible values using the repository canonical form."""

    try:
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NormalizationError(
            NormalizationErrorCode.INVALID_VALUE,
            source_location="canonical-import",
            field="records",
            expected_contract="canonical-json.v1 JSON-compatible finite values",
            message="canonical serialization failed",
        ) from error


def normalize_import(
    inputs: Sequence[NormalizationInput],
    *,
    unit_registry: UnitConversionRegistry,
) -> NormalizationResult:
    """Normalize explicitly profiled staged batches without business validation."""

    normalized_inputs = tuple(inputs)
    if not normalized_inputs:
        _error(
            NormalizationErrorCode.MISSING_FIELD,
            source_location="normalization-input",
            field="inputs",
            expected_contract="at least one staged batch with an exact mapping profile",
            message="normalization input is empty",
        )
    if unit_registry.schema_set_version != CURRENT_SCHEMA_SET_VERSION:
        _error(
            NormalizationErrorCode.NORMALIZATION_VERSION_MISMATCH,
            source_location="unit-conversion-registry",
            field="schema_set_version",
            expected_contract=CURRENT_SCHEMA_SET_VERSION,
            message="unit registry is not part of the active additive schema set",
        )

    data_plane = normalized_inputs[0].batch.data_plane
    synthetic_provenance = normalized_inputs[0].batch.synthetic_provenance
    source_versions: dict[str, str] = {}
    source_profiles: dict[str, tuple[str, str]] = {}
    for item in normalized_inputs:
        _validate_profile(item.profile, unit_registry)
        batch = item.batch
        profile = item.profile
        if batch.data_plane is not data_plane:
            _error(
                NormalizationErrorCode.DATA_PLANE_MISMATCH,
                source_location="normalization-input",
                field="data_plane",
                expected_contract="one explicit data plane per canonical Import",
                message="normalization inputs mix data planes",
            )
        if batch.synthetic_provenance != synthetic_provenance:
            _error(
                NormalizationErrorCode.CONFLICTING_AUTHORITY,
                source_location="normalization-input",
                field="synthetic_provenance",
                expected_contract="identical provenance across simulation batches",
                message="normalization inputs carry conflicting synthetic provenance",
            )
        if (
            batch.source_system != profile.source_system
            or batch.source_version != profile.source_version
        ):
            _error(
                NormalizationErrorCode.PROFILE_SOURCE_MISMATCH,
                source_location=batch.source_name,
                field="source_system/source_version",
                expected_contract="batch source identity exactly matches mapping profile",
                message="the selected mapping profile does not match the staged batch",
            )
        previous_version = source_versions.get(batch.source_system)
        if previous_version is not None and previous_version != batch.source_version:
            _error(
                NormalizationErrorCode.CONFLICTING_AUTHORITY,
                source_location=batch.source_name,
                field="source_version",
                expected_contract="one source version per source system and Import package",
                message="one source system has conflicting versions",
            )
        profile_identity = (profile.profile_id, profile.profile_version)
        previous_profile = source_profiles.get(batch.source_system)
        if previous_profile is not None and previous_profile != profile_identity:
            _error(
                NormalizationErrorCode.CONFLICTING_AUTHORITY,
                source_location=batch.source_name,
                field="mapping_profile",
                expected_contract="one mapping profile version per source system",
                message="one source system has conflicting mapping profiles",
            )
        source_versions[batch.source_system] = batch.source_version
        source_profiles[batch.source_system] = profile_identity

    records: dict[str, list[dict[str, object]]] = {
        collection: [] for collection in COLLECTION_ID_FIELDS
    }
    seen_ids: dict[str, set[str]] = {
        collection: set() for collection in COLLECTION_ID_FIELDS
    }
    ordered_inputs = sorted(
        normalized_inputs,
        key=lambda item: (
            item.batch.source_system,
            item.batch.source_version,
            tuple(sorted(row.row_identity for row in item.batch.rows)),
        ),
    )
    for item in ordered_inputs:
        mappings = {mapping.record_type: mapping for mapping in item.profile.records}
        for row in sorted(item.batch.rows, key=lambda value: value.row_identity):
            outer = _decode_object(
                row.raw_payload,
                source_location=row.source_location,
                field="raw_payload",
            )
            if set(outer) != {"payload_json", "record_type", "source_record_id"}:
                _error(
                    NormalizationErrorCode.INVALID_RAW_ROW,
                    source_location=row.source_location,
                    field="raw_payload",
                    expected_contract=(
                        "exact ReferenceFileAdapter v1 record_type/source_record_id/"
                        "payload_json object"
                    ),
                    message="raw row fields do not match the reference transport contract",
                )
            record_type = _raw_text(
                outer["record_type"], row.source_location, "record_type"
            )
            source_record_id = _raw_text(
                outer["source_record_id"], row.source_location, "source_record_id"
            )
            payload_json = _raw_text(
                outer["payload_json"], row.source_location, "payload_json"
            )
            record_mapping = mappings.get(record_type)
            if record_mapping is None:
                _error(
                    NormalizationErrorCode.UNKNOWN_FIELD,
                    source_location=row.source_location,
                    field="record_type",
                    expected_contract="record type declared by the exact mapping profile",
                    message="record type is not mapped",
                )
            payload = _decode_object(
                payload_json,
                source_location=row.source_location,
                field="payload_json",
            )
            record = _normalize_record(
                payload=payload,
                source_record_id=source_record_id,
                source_system=item.batch.source_system,
                source_version=item.batch.source_version,
                source_location=row.source_location,
                mapping=record_mapping,
                unit_registry=unit_registry,
            )
            collection = record_mapping.collection
            id_field = COLLECTION_ID_FIELDS[collection]
            canonical_id = record[id_field]
            if not isinstance(canonical_id, str):
                raise AssertionError(
                    "validated canonical ID transform returned non-text"
                )
            if canonical_id in seen_ids[collection]:
                _error(
                    NormalizationErrorCode.DUPLICATE_CANONICAL_ID,
                    source_location=row.source_location,
                    field=id_field,
                    expected_contract="unique canonical ID within its collection",
                    message="canonical ID is duplicated",
                )
            seen_ids[collection].add(canonical_id)
            records[collection].append(record)

    for collection, id_field in COLLECTION_ID_FIELDS.items():
        records[collection].sort(key=lambda record: str(record[id_field]))

    canonical_records: dict[str, object] = {
        "canonical_records_version": "canonical-records.v1",
        **records,
    }
    ordered_profile_versions = tuple(
        f"{source_system}={profile_id}@{profile_version}"
        for source_system, (profile_id, profile_version) in sorted(
            source_profiles.items()
        )
    )
    encoded_profiles = ",".join(
        f"{quote(source_system, safe='-._~')}="
        f"{quote(profile_id, safe='-._~')}@{quote(profile_version, safe='-._~')}"
        for source_system, (profile_id, profile_version) in sorted(
            source_profiles.items()
        )
    )
    normalization_rule_version = (
        f"{NORMALIZATION_CONTRACT_VERSION}|mappings={encoded_profiles}|units="
        f"{quote(unit_registry.version, safe='-._~')}"
    )
    envelope: dict[str, object] = {
        "import_package_version": IMPORT_PACKAGE_VERSION,
        "schema_set_version": IMPORT_DOCUMENT_SCHEMA_SET_VERSION,
        "source_versions": dict(sorted(source_versions.items())),
        "normalization_rule_version": normalization_rule_version,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "synthetic": data_plane is StagingDataPlane.SIMULATION,
        "records": canonical_records,
    }
    if synthetic_provenance is not None:
        _validate_synthetic_provenance(synthetic_provenance)
        envelope["synthetic_provenance"] = _synthetic_projection(synthetic_provenance)
    package_basis = canonical_json_bytes(envelope)
    document = {
        **envelope,
        "package_id": f"import-{sha256(package_basis).hexdigest()}",
    }
    canonical_bytes = canonical_json_bytes(document)
    return NormalizationResult(
        document=document,
        canonical_bytes=canonical_bytes,
        dataset_hash=f"sha256:{sha256(canonical_bytes).hexdigest()}",
        source_batch_ids=tuple(
            sorted(item.batch.batch_id for item in normalized_inputs)
        ),
        mapping_profile_versions=ordered_profile_versions,
        unit_registry_version=unit_registry.version,
    )


def _validate_profile(
    profile: MappingProfile, unit_registry: UnitConversionRegistry
) -> None:
    for field in (
        "profile_id",
        "profile_version",
        "source_system",
        "source_version",
        "unit_registry_version",
        "mapping_contract_version",
    ):
        _profile_text(getattr(profile, field), field)
    if profile.mapping_contract_version != "mapping-profile.v1":
        _profile_error(
            "mapping_contract_version",
            "mapping profile contract version must be mapping-profile.v1",
        )
    if any(character.isspace() for character in profile.source_system):
        _profile_error(
            "source_system",
            "source system must be a whitespace-free canonical envelope key",
        )
    if profile.unit_registry_version != unit_registry.version:
        _error(
            NormalizationErrorCode.NORMALIZATION_VERSION_MISMATCH,
            source_location="mapping-profile",
            field="unit_registry_version",
            expected_contract=unit_registry.version,
            message="mapping profile selects a different unit registry version",
        )
    if not isinstance(profile.records, tuple) or not profile.records:
        _profile_error("records", "mapping profile must declare record mappings")
    record_types: set[str] = set()
    for record in profile.records:
        if not isinstance(record, RecordMapping):
            _profile_error("records", "record mappings must use RecordMapping")
        _profile_text(record.record_type, "record_type")
        if record.record_type in record_types:
            _profile_error("record_type", "record types must be unique")
        record_types.add(record.record_type)
        if record.collection not in COLLECTION_REQUIRED_FIELDS:
            _profile_error("collection", "canonical collection is unknown")
        if not isinstance(record.fields, tuple) or not record.fields:
            _profile_error("fields", "record mapping must declare fields")
        targets: set[str] = set()
        allowed = (
            COLLECTION_REQUIRED_FIELDS[record.collection]
            | COLLECTION_OPTIONAL_FIELDS[record.collection]
        )
        for mapping in record.fields:
            if not isinstance(mapping, FieldMapping):
                _profile_error("fields", "field mappings must use FieldMapping")
            _profile_text(mapping.source_field, "source_field")
            _profile_text(mapping.target_field, "target_field")
            if mapping.target_field == "source" or mapping.target_field not in allowed:
                _profile_error(
                    "target_field", "target is not allowed by the canonical collection"
                )
            if mapping.target_field in targets:
                _profile_error("target_field", "canonical targets must be unique")
            targets.add(mapping.target_field)
            if not isinstance(mapping.transform, FieldTransform):
                _profile_error("transform", "transform must be explicit and versioned")
            if not isinstance(mapping.required, bool):
                _profile_error("required", "required flag must be boolean")
            _validate_transform_compatibility(mapping)
        required = COLLECTION_REQUIRED_FIELDS[record.collection]
        if not required.issubset(targets):
            _profile_error(
                "fields", "mapping omits one or more required canonical fields"
            )
        for mapping in record.fields:
            if mapping.target_field in required and not mapping.required:
                _profile_error(
                    "required", "required canonical fields cannot use optional mapping"
                )


def _validate_transform_compatibility(mapping: FieldMapping) -> None:
    target = mapping.target_field
    if target.endswith("_id"):
        expected = FieldTransform.CANONICAL_ID
    elif target.endswith("_at_utc"):
        expected = FieldTransform.UTC_INSTANT
    elif target.endswith("_seconds"):
        expected = (
            FieldTransform.POSITIVE_DURATION_SECONDS
            if target in {"final_duration_seconds", "remaining_seconds"}
            else FieldTransform.NONNEGATIVE_DURATION_SECONDS
        )
    elif target in {"quantity", "completed_quantity", "remaining_quantity"}:
        expected = FieldTransform.POSITIVE_NUMBER
    elif target in {"capabilities", "required_capabilities"}:
        expected = FieldTransform.SORTED_TEXT_LIST
    elif target == "unavailable_intervals":
        expected = FieldTransform.UNAVAILABLE_INTERVALS
    else:
        expected = FieldTransform.TEXT
    if mapping.transform is not expected:
        _profile_error(
            "transform",
            f"{target} requires the {expected.value} transform",
        )
    if expected in {
        FieldTransform.CANONICAL_ID,
        FieldTransform.UNAVAILABLE_INTERVALS,
    }:
        if mapping.id_namespace is None:
            _profile_error("id_namespace", "ID transformation requires a namespace")
        _profile_text(mapping.id_namespace, "id_namespace")
        stable_canonical_id(
            mapping.id_namespace,
            "mapping-profile",
            "namespace-probe",
            source_location="mapping-profile",
        )
    elif mapping.id_namespace is not None:
        _profile_error("id_namespace", "non-ID transform forbids an ID namespace")
    if expected is FieldTransform.CANONICAL_ID:
        if mapping.id_source_system is not None:
            _profile_text(mapping.id_source_system, "id_source_system")
            if any(character.isspace() for character in mapping.id_source_system):
                _profile_error(
                    "id_source_system",
                    "ID source authority must be a whitespace-free canonical key",
                )
    elif mapping.id_source_system is not None:
        _profile_error(
            "id_source_system", "non-ID transform forbids an ID source authority"
        )
    if expected in {
        FieldTransform.NONNEGATIVE_DURATION_SECONDS,
        FieldTransform.POSITIVE_DURATION_SECONDS,
    }:
        if mapping.unit_field is None:
            _profile_error(
                "unit_field", "duration transformation requires a unit field"
            )
        _profile_text(mapping.unit_field, "unit_field")
    elif mapping.unit_field is not None:
        _profile_error("unit_field", "non-duration transform forbids a unit field")


def _normalize_record(
    *,
    payload: Mapping[str, object],
    source_record_id: str,
    source_system: str,
    source_version: str,
    source_location: str,
    mapping: RecordMapping,
    unit_registry: UnitConversionRegistry,
) -> dict[str, object]:
    allowed_source_fields = {
        field.source_field
        for field in mapping.fields
        if field.source_field != _SOURCE_RECORD_ID
    }
    allowed_source_fields.update(
        field.unit_field for field in mapping.fields if field.unit_field is not None
    )
    unknown = set(payload) - allowed_source_fields
    if unknown:
        _error(
            NormalizationErrorCode.UNKNOWN_FIELD,
            source_location=source_location,
            field="payload_json",
            expected_contract="only fields declared by the exact mapping profile",
            message="source payload contains an unmapped field",
        )
    record: dict[str, object] = {}
    for field_mapping in mapping.fields:
        if field_mapping.source_field == _SOURCE_RECORD_ID:
            raw_value: object = source_record_id
        elif field_mapping.source_field not in payload:
            unit_present = (
                field_mapping.unit_field is not None
                and field_mapping.unit_field in payload
            )
            if field_mapping.transform in {
                FieldTransform.NONNEGATIVE_DURATION_SECONDS,
                FieldTransform.POSITIVE_DURATION_SECONDS,
            } and (field_mapping.required or unit_present):
                _error(
                    NormalizationErrorCode.MISSING_DURATION,
                    source_location=source_location,
                    field=field_mapping.source_field,
                    expected_contract="explicit duration value and unit",
                    message="duration value is missing",
                )
            if field_mapping.required:
                _error(
                    NormalizationErrorCode.MISSING_FIELD,
                    source_location=source_location,
                    field=field_mapping.source_field,
                    expected_contract="required source field declared by mapping profile",
                    message="required source field is missing",
                )
            continue
        else:
            raw_value = payload[field_mapping.source_field]
        record[field_mapping.target_field] = _transform_value(
            value=raw_value,
            payload=payload,
            mapping=field_mapping,
            source_system=source_system,
            source_location=source_location,
            unit_registry=unit_registry,
        )
    required = COLLECTION_REQUIRED_FIELDS[mapping.collection]
    if not required.issubset(record):
        _error(
            NormalizationErrorCode.MISSING_FIELD,
            source_location=source_location,
            field=mapping.collection,
            expected_contract="all required canonical fields after mapping",
            message="canonical record is incomplete",
        )
    _validate_record_shape(record, mapping.collection, source_location)
    record["source"] = {
        "source_system": source_system,
        "source_version": source_version,
        "source_record_id": _canonical_source_record_id(
            source_record_id, source_location
        ),
    }
    return record


def _transform_value(
    *,
    value: object,
    payload: Mapping[str, object],
    mapping: FieldMapping,
    source_system: str,
    source_location: str,
    unit_registry: UnitConversionRegistry,
) -> object:
    transform = mapping.transform
    if transform is FieldTransform.TEXT:
        return _canonical_text(value, source_location, mapping.source_field)
    if transform is FieldTransform.CANONICAL_ID:
        return stable_canonical_id(
            mapping.id_namespace,
            mapping.id_source_system or source_system,
            value,
            source_location=source_location,
        )
    if transform is FieldTransform.UTC_INSTANT:
        return normalize_utc_instant(
            value,
            source_location=source_location,
            field=mapping.source_field,
        )
    if transform in {
        FieldTransform.NONNEGATIVE_DURATION_SECONDS,
        FieldTransform.POSITIVE_DURATION_SECONDS,
    }:
        unit = payload.get(mapping.unit_field) if mapping.unit_field else None
        return unit_registry.convert_duration(
            value,
            unit,
            source_location=source_location,
            field=mapping.source_field,
            allow_zero=transform is FieldTransform.NONNEGATIVE_DURATION_SECONDS,
        )
    if transform is FieldTransform.POSITIVE_NUMBER:
        return _positive_number(value, source_location, mapping.source_field)
    if transform is FieldTransform.SORTED_TEXT_LIST:
        return _sorted_text_list(value, source_location, mapping.source_field)
    if transform is FieldTransform.UNAVAILABLE_INTERVALS:
        return _unavailable_intervals(
            value,
            source_system=source_system,
            namespace=mapping.id_namespace,
            source_location=source_location,
            field=mapping.source_field,
        )
    raise AssertionError("mapping profile transform was validated")


def _unavailable_intervals(
    value: object,
    *,
    source_system: str,
    namespace: str | None,
    source_location: str,
    field: str,
) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _invalid_value(source_location, field, "unavailable intervals must be a list")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for position, interval in enumerate(value):
        if not isinstance(interval, Mapping) or set(interval) != {
            "interval_id",
            "start_at",
            "end_at",
            "reason",
        }:
            _invalid_value(
                source_location,
                f"{field}[{position}]",
                "interval fields must match the exact nested mapping contract",
            )
        interval_id = stable_canonical_id(
            namespace,
            source_system,
            interval["interval_id"],
            source_location=source_location,
        )
        if interval_id in seen_ids:
            _error(
                NormalizationErrorCode.DUPLICATE_CANONICAL_ID,
                source_location=source_location,
                field=f"{field}[{position}].interval_id",
                expected_contract="unique canonical interval ID",
                message="canonical interval ID is duplicated",
            )
        seen_ids.add(interval_id)
        normalized.append(
            {
                "interval_id": interval_id,
                "start_at_utc": normalize_utc_instant(
                    interval["start_at"],
                    source_location=source_location,
                    field=f"{field}[{position}].start_at",
                ),
                "end_at_utc": normalize_utc_instant(
                    interval["end_at"],
                    source_location=source_location,
                    field=f"{field}[{position}].end_at",
                ),
                "reason": _canonical_text(
                    interval["reason"], source_location, f"{field}[{position}].reason"
                ),
            }
        )
    normalized.sort(key=lambda item: str(item["interval_id"]))
    return normalized


def _positive_number(value: object, source_location: str, field: str) -> int | float:
    if isinstance(value, bool):
        _invalid_value(source_location, field, "quantity must be a positive number")
    if isinstance(value, int):
        if value <= 0:
            _invalid_value(source_location, field, "quantity must be positive")
        return value
    if isinstance(value, Decimal) and value.is_finite() and value > 0:
        converted = float(value)
        if Decimal(str(converted)) != value:
            _invalid_value(
                source_location,
                field,
                "quantity cannot be represented without canonical JSON rounding",
            )
        return converted
    _invalid_value(source_location, field, "quantity must be a finite positive number")


def _sorted_text_list(value: object, source_location: str, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _invalid_value(source_location, field, "value must be a non-empty text list")
    normalized = [
        _canonical_text(item, source_location, f"{field}[{position}]")
        for position, item in enumerate(value)
    ]
    if len(normalized) != len(set(normalized)):
        _invalid_value(source_location, field, "text list values must be unique")
    return sorted(normalized)


def _decode_object(
    value: bytes | str,
    *,
    source_location: str,
    field: str,
) -> dict[str, object]:
    try:
        text = value.decode("utf-8") if isinstance(value, bytes) else value
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=Decimal,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise NormalizationError(
            NormalizationErrorCode.INVALID_RAW_ROW,
            source_location=source_location,
            field=field,
            expected_contract="strict UTF-8 JSON object without duplicate keys or non-finite numbers",
            message="source JSON is invalid",
        ) from error
    if not isinstance(decoded, dict):
        _error(
            NormalizationErrorCode.INVALID_RAW_ROW,
            source_location=source_location,
            field=field,
            expected_contract="JSON object",
            message="source JSON root is not an object",
        )
    return decoded


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey
        result[key] = value
    return result


def _reject_constant(_value: str) -> NoReturn:
    raise _InvalidJsonConstant


def _raw_text(value: object, source_location: str, field: str) -> str:
    maximum = 1_048_576 if field == "payload_json" else 256
    controls_forbidden = field != "payload_json"
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > maximum
        or (
            controls_forbidden
            and any(ord(character) < 32 or ord(character) == 127 for character in value)
        )
    ):
        _error(
            NormalizationErrorCode.INVALID_RAW_ROW,
            source_location=source_location,
            field=field,
            expected_contract="non-empty reference transport text",
            message="reference transport field is invalid",
        )
    return value


def _canonical_source_record_id(value: str, source_location: str) -> str:
    if (
        len(value) > 256
        or any(character.isspace() for character in value)
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _invalid_value(
            source_location,
            "source_record_id",
            "source record ID must satisfy the canonical provenance identifier contract",
        )
    return value


def _validate_record_shape(
    record: Mapping[str, object], collection: str, source_location: str
) -> None:
    if collection == "operation_locks" and record.get("lock_type") not in {
        "HARD_LOCK",
        "SOFT_LOCK",
    }:
        _invalid_value(
            source_location,
            "lock_type",
            "lock type must be HARD_LOCK or SOFT_LOCK",
        )
    if collection != "execution_facts":
        return
    status = record.get("status")
    if status == "RUNNING":
        required = {
            "resource_id",
            "actual_start_at_utc",
            "remaining_quantity",
            "remaining_seconds",
        }
        forbidden = {"actual_end_at_utc", "completed_quantity"}
    elif status == "COMPLETED":
        required = {
            "resource_id",
            "actual_start_at_utc",
            "actual_end_at_utc",
            "completed_quantity",
        }
        forbidden = {"remaining_quantity", "remaining_seconds"}
    else:
        _invalid_value(
            source_location,
            "status",
            "execution fact status must be RUNNING or COMPLETED",
        )
    if not required.issubset(record) or forbidden.intersection(record):
        _invalid_value(
            source_location,
            "execution_facts",
            "execution fact fields do not match the status-specific canonical shape",
        )


def _canonical_text(value: object, source_location: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > 4096
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _invalid_value(
            source_location,
            field,
            "canonical text must be non-empty, bounded, and control-free",
        )
    return value


def _profile_text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > 256
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _profile_error(field, "mapping metadata must be non-empty bounded text")
    return value


def _profile_error(field: str, message: str) -> NoReturn:
    _error(
        NormalizationErrorCode.INVALID_MAPPING_PROFILE,
        source_location="mapping-profile",
        field=field,
        expected_contract="mapping-profile.v1 exact explicit contract",
        message=message,
    )


def _invalid_value(source_location: str, field: str, message: str) -> NoReturn:
    _error(
        NormalizationErrorCode.INVALID_VALUE,
        source_location=source_location,
        field=field,
        expected_contract="canonical field value required by mapping-profile.v1",
        message=message,
    )


def _validate_synthetic_provenance(provenance: SyntheticImportProvenance) -> None:
    for field in ("scenario_id", "factory_profile_id", "generator_id"):
        value = getattr(provenance, field)
        if (
            len(value) > 256
            or any(character.isspace() for character in value)
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            _invalid_value(
                "synthetic-provenance",
                field,
                "synthetic identifier must satisfy the canonical ID contract",
            )
    for field in ("scenario_version", "profile_version", "generator_version"):
        if _SEMANTIC_VERSION.fullmatch(getattr(provenance, field)) is None:
            _invalid_value(
                "synthetic-provenance",
                field,
                "synthetic asset version must be semantic version text",
            )
    if provenance.seed > 9_223_372_036_854_775_807:
        _invalid_value(
            "synthetic-provenance",
            "seed",
            "synthetic seed must fit the Import v2 int64 contract",
        )


def _synthetic_projection(provenance: SyntheticImportProvenance) -> dict[str, object]:
    return {
        "scenario_id": provenance.scenario_id,
        "scenario_version": provenance.scenario_version,
        "seed": provenance.seed,
        "factory_profile_id": provenance.factory_profile_id,
        "profile_version": provenance.profile_version,
        "generator_id": provenance.generator_id,
        "generator_version": provenance.generator_version,
    }


def _error(
    code: NormalizationErrorCode,
    *,
    source_location: str,
    field: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise NormalizationError(
        code,
        source_location=source_location,
        field=field,
        expected_contract=expected_contract,
        message=message,
    )


__all__ = [
    "CANONICALIZATION_VERSION",
    "CURRENT_SCHEMA_SET_VERSION",
    "IMPORT_DOCUMENT_SCHEMA_SET_VERSION",
    "IMPORT_PACKAGE_VERSION",
    "NORMALIZATION_CONTRACT_VERSION",
    "canonical_json_bytes",
    "normalize_import",
]
