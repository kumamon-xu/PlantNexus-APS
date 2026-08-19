"""Versioned input-adapter contracts and strict reference-table semantics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.importers.contracts import (
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)

REFERENCE_HEADERS = ("record_type", "source_record_id", "payload_json")
REFERENCE_SHEET_NAME = "records"
_FORMULA_PREFIXES = ("=", "+", "-", "@")


class AdapterErrorCode(StrEnum):
    """Stable DATA_ERROR codes for the bounded external-file boundary."""

    ADAPTER_ID_MISMATCH = "ADAPTER_ID_MISMATCH"
    ADAPTER_VERSION_MISMATCH = "ADAPTER_VERSION_MISMATCH"
    UNSAFE_SOURCE_PATH = "UNSAFE_SOURCE_PATH"
    SOURCE_NOT_FILE = "SOURCE_NOT_FILE"
    UNSUPPORTED_FILE_FORMAT = "UNSUPPORTED_FILE_FORMAT"
    FILE_SIZE_LIMIT_EXCEEDED = "FILE_SIZE_LIMIT_EXCEEDED"
    INVALID_UTF8 = "INVALID_UTF8"
    MALFORMED_CSV = "MALFORMED_CSV"
    INVALID_WORKBOOK = "INVALID_WORKBOOK"
    UNSAFE_ARCHIVE = "UNSAFE_ARCHIVE"
    FORBIDDEN_MACRO = "FORBIDDEN_MACRO"
    FORBIDDEN_EXTERNAL_LINK = "FORBIDDEN_EXTERNAL_LINK"
    FORBIDDEN_FORMULA = "FORBIDDEN_FORMULA"
    SHEET_LIMIT_EXCEEDED = "SHEET_LIMIT_EXCEEDED"
    INVALID_SHEET = "INVALID_SHEET"
    ROW_LIMIT_EXCEEDED = "ROW_LIMIT_EXCEEDED"
    COLUMN_LIMIT_EXCEEDED = "COLUMN_LIMIT_EXCEEDED"
    DUPLICATE_HEADER = "DUPLICATE_HEADER"
    UNKNOWN_HEADER = "UNKNOWN_HEADER"
    MISSING_HEADER = "MISSING_HEADER"
    INVALID_HEADER_ORDER = "INVALID_HEADER_ORDER"
    INVALID_CELL_TYPE = "INVALID_CELL_TYPE"
    INVALID_ROW = "INVALID_ROW"
    DUPLICATE_SOURCE_RECORD = "DUPLICATE_SOURCE_RECORD"


class InputAdapterError(ValueError):
    """Sanitized source rejection with a stable product error category."""

    category = "DATA_ERROR"

    def __init__(
        self,
        code: AdapterErrorCode,
        *,
        source_location: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.code = code
        self.source_location = source_location
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(
            f"{self.category}/{code.value} at {source_location}: {message}"
        )


@dataclass(frozen=True)
class ReferenceFileLimits:
    """Reference-only defensive limits; they are not production capacity claims."""

    max_file_size_bytes: int = 4 * 1024 * 1024
    max_rows: int = 10_000
    max_columns: int = len(REFERENCE_HEADERS)
    max_cell_characters: int = 262_144
    max_sheets: int = 1
    max_archive_members: int = 512
    max_archive_uncompressed_bytes: int = 32 * 1024 * 1024

    def __post_init__(self) -> None:
        values = (
            self.max_file_size_bytes,
            self.max_rows,
            self.max_columns,
            self.max_cell_characters,
            self.max_sheets,
            self.max_archive_members,
            self.max_archive_uncompressed_bytes,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("reference file limits must be positive integers")
        if self.max_columns < len(REFERENCE_HEADERS):
            raise ValueError("max_columns cannot be smaller than the reference header")


@dataclass(frozen=True)
class AdapterManifest:
    """Version and capability declaration for an input adapter implementation."""

    adapter_id: str
    adapter_version: str
    staging_contract_version: str
    production_binding: bool
    accepted_extensions: tuple[str, ...]
    capabilities: tuple[str, ...]
    reference_headers: tuple[str, ...]
    reference_sheet_name: str
    limits: ReferenceFileLimits


@dataclass(frozen=True)
class SourceFileManifest:
    """Caller-supplied source identity; no ERP/MES/WMS/CAM mapping is implied."""

    adapter_id: str
    adapter_version: str
    relative_path: str
    batch_id: str
    idempotency_key: str
    source_system: str
    source_version: str
    received_at: datetime
    data_plane: StagingDataPlane
    synthetic_provenance: SyntheticImportProvenance | None = None


@dataclass(frozen=True)
class SourceCellRow:
    """A source row after safe transport decoding but before field semantics."""

    source_location: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceRecord:
    """The three transport fields defined by ReferenceFileAdapter v1."""

    record_type: str
    source_record_id: str
    payload_json: str
    source_location: str

    @property
    def row_identity(self) -> str:
        projection = json.dumps(
            [self.record_type, self.source_record_id],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"reference:{sha256(projection).hexdigest()}"

    @property
    def raw_payload(self) -> bytes:
        return json.dumps(
            {
                "payload_json": self.payload_json,
                "record_type": self.record_type,
                "source_record_id": self.source_record_id,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


@dataclass(frozen=True)
class ReferenceTable:
    """Format-neutral rows shared by the CSV and XLSX readers."""

    records: tuple[ReferenceRecord, ...]


@runtime_checkable
class InputAdapter(Protocol):
    """An adapter prepares the immutable Raw Staging contract only."""

    @property
    def manifest(self) -> AdapterManifest: ...

    def prepare_batch(
        self,
        *,
        source_root: Path,
        source: SourceFileManifest,
    ) -> StagedImportBatch: ...


def _error(
    code: AdapterErrorCode,
    *,
    source_location: str,
    expected_contract: str,
    message: str,
) -> InputAdapterError:
    return InputAdapterError(
        code,
        source_location=source_location,
        expected_contract=expected_contract,
        message=message,
    )


def _validate_header(header: SourceCellRow | None, limits: ReferenceFileLimits) -> None:
    expected = ",".join(REFERENCE_HEADERS)
    if header is None:
        raise _error(
            AdapterErrorCode.MISSING_HEADER,
            source_location="header",
            expected_contract=expected,
            message="the required reference header is missing",
        )
    values = header.values
    if len(values) > limits.max_columns:
        raise _error(
            AdapterErrorCode.COLUMN_LIMIT_EXCEEDED,
            source_location=header.source_location,
            expected_contract=f"at most {limits.max_columns} columns",
            message="the source exceeds the configured column limit",
        )
    if len(values) != len(set(values)):
        raise _error(
            AdapterErrorCode.DUPLICATE_HEADER,
            source_location=header.source_location,
            expected_contract=expected,
            message="header names must be unique",
        )
    unknown = set(values) - set(REFERENCE_HEADERS)
    if unknown:
        raise _error(
            AdapterErrorCode.UNKNOWN_HEADER,
            source_location=header.source_location,
            expected_contract=expected,
            message="unknown reference header fields are forbidden",
        )
    missing = set(REFERENCE_HEADERS) - set(values)
    if missing:
        raise _error(
            AdapterErrorCode.MISSING_HEADER,
            source_location=header.source_location,
            expected_contract=expected,
            message="one or more required reference header fields are missing",
        )
    if values != REFERENCE_HEADERS:
        raise _error(
            AdapterErrorCode.INVALID_HEADER_ORDER,
            source_location=header.source_location,
            expected_contract=expected,
            message="reference header fields must use the versioned order",
        )


def _has_formula_prefix(value: str) -> bool:
    return value.lstrip().startswith(_FORMULA_PREFIXES)


def _validate_transport_text(
    value: str,
    *,
    field: str,
    location: str,
    maximum: int,
) -> None:
    if not value or not value.strip() or len(value) > maximum:
        raise _error(
            AdapterErrorCode.INVALID_ROW,
            source_location=location,
            expected_contract=f"non-empty {field} with at most {maximum} characters",
            message=f"{field} does not satisfy the reference transport contract",
        )
    if "\x00" in value:
        raise _error(
            AdapterErrorCode.INVALID_ROW,
            source_location=location,
            expected_contract=f"{field} without NUL characters",
            message=f"{field} contains a forbidden control character",
        )
    if field != "payload_json" and any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise _error(
            AdapterErrorCode.INVALID_ROW,
            source_location=location,
            expected_contract=f"{field} without control characters",
            message=f"{field} contains a forbidden control character",
        )
    if _has_formula_prefix(value):
        raise _error(
            AdapterErrorCode.FORBIDDEN_FORMULA,
            source_location=location,
            expected_contract="literal text, never a spreadsheet formula",
            message="formula-like cell content is forbidden",
        )


def validate_reference_table(
    *,
    header: SourceCellRow | None,
    rows: Iterable[SourceCellRow],
    limits: ReferenceFileLimits,
) -> ReferenceTable:
    """Validate only transport shape and return format-neutral opaque records."""

    _validate_header(header, limits)
    records: list[ReferenceRecord] = []
    identities: set[tuple[str, str]] = set()
    for row_number, row in enumerate(rows, start=1):
        if row_number > limits.max_rows:
            raise _error(
                AdapterErrorCode.ROW_LIMIT_EXCEEDED,
                source_location=row.source_location,
                expected_contract=f"at most {limits.max_rows} data rows",
                message="the source exceeds the configured row limit",
            )
        if len(row.values) > limits.max_columns:
            raise _error(
                AdapterErrorCode.COLUMN_LIMIT_EXCEEDED,
                source_location=row.source_location,
                expected_contract=f"exactly {len(REFERENCE_HEADERS)} columns",
                message="the source exceeds the configured column limit",
            )
        if len(row.values) != len(REFERENCE_HEADERS):
            raise _error(
                AdapterErrorCode.INVALID_ROW,
                source_location=row.source_location,
                expected_contract=f"exactly {len(REFERENCE_HEADERS)} columns",
                message="a reference row has the wrong number of columns",
            )
        record_type, source_record_id, payload_json = row.values
        _validate_transport_text(
            record_type,
            field="record_type",
            location=row.source_location,
            maximum=256,
        )
        _validate_transport_text(
            source_record_id,
            field="source_record_id",
            location=row.source_location,
            maximum=256,
        )
        _validate_transport_text(
            payload_json,
            field="payload_json",
            location=row.source_location,
            maximum=limits.max_cell_characters,
        )
        identity = (record_type, source_record_id)
        if identity in identities:
            raise _error(
                AdapterErrorCode.DUPLICATE_SOURCE_RECORD,
                source_location=row.source_location,
                expected_contract="unique record_type/source_record_id pairs",
                message="the source repeats a reference record identity",
            )
        identities.add(identity)
        records.append(
            ReferenceRecord(
                record_type=record_type,
                source_record_id=source_record_id,
                payload_json=payload_json,
                source_location=row.source_location,
            )
        )
    return ReferenceTable(records=tuple(records))


__all__ = [
    "AdapterErrorCode",
    "AdapterManifest",
    "InputAdapter",
    "InputAdapterError",
    "REFERENCE_HEADERS",
    "REFERENCE_SHEET_NAME",
    "ReferenceFileLimits",
    "ReferenceRecord",
    "ReferenceTable",
    "SourceCellRow",
    "SourceFileManifest",
    "validate_reference_table",
]
