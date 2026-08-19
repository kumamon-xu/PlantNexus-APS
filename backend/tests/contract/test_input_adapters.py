"""TEST-IMPORT-ADAPTER-001 contract and negative file-boundary evidence."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import openpyxl
from openpyxl import Workbook
from openpyxl.xml import DEFUSEDXML
import pytest

from app.importers import (
    AdapterErrorCode,
    InputAdapter,
    InputAdapterError,
    REFERENCE_FILE_ADAPTER_ID,
    REFERENCE_FILE_ADAPTER_VERSION,
    REFERENCE_HEADERS,
    REFERENCE_SHEET_NAME,
    ReferenceFileAdapter,
    ReferenceFileLimits,
    SourceFileManifest,
    StagingDataPlane,
    SyntheticImportProvenance,
)

TEST_ID = "TEST-IMPORT-ADAPTER-001"
RECEIVED = datetime(2026, 8, 19, 4, 0, tzinfo=UTC)
ROWS = (
    ("factory", "FACTORY-001", '{"factory_code":"SYNTHETIC"}'),
    ("resource", "RESOURCE-001", '{"resource_code":"SYNTHETIC-R1"}'),
)


def _provenance() -> SyntheticImportProvenance:
    return SyntheticImportProvenance(
        scenario_id="SIM-ADAPTER-001",
        scenario_version="1.0.0",
        seed=4104,
        factory_profile_id="PROFILE-ADAPTER-001",
        profile_version="1.0.0",
        generator_id="GENERATOR-ADAPTER-TEST",
        generator_version="1.0.0",
    )


def _source(
    relative_path: str,
    *,
    adapter_id: str = REFERENCE_FILE_ADAPTER_ID,
    adapter_version: str = REFERENCE_FILE_ADAPTER_VERSION,
    batch_id: str = "BATCH-ADAPTER-001",
    idempotency_key: str = "IDEMPOTENCY-ADAPTER-001",
) -> SourceFileManifest:
    return SourceFileManifest(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        relative_path=relative_path,
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        source_system="synthetic-reference-file",
        source_version="source.v1",
        received_at=RECEIVED,
        data_plane=StagingDataPlane.SIMULATION,
        synthetic_provenance=_provenance(),
    )


def _write_csv(
    path: Path,
    *,
    header: tuple[str, ...] = REFERENCE_HEADERS,
    rows: tuple[tuple[str, ...], ...] = ROWS,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(
            stream,
            delimiter=",",
            quotechar='"',
            lineterminator="\n",
            doublequote=True,
        )
        writer.writerow(header)
        writer.writerows(rows)


def _write_xlsx(
    path: Path,
    *,
    header: tuple[str, ...] = REFERENCE_HEADERS,
    rows: tuple[tuple[str | int, ...], ...] = ROWS,
    sheet_name: str = REFERENCE_SHEET_NAME,
    extra_sheet: bool = False,
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet_name
    worksheet.append(header)
    for row in rows:
        worksheet.append(row)
    if extra_sheet:
        workbook.create_sheet("extra")
    workbook.save(path)
    workbook.close()


def _add_archive_member(source: Path, target: Path, name: str, payload: bytes) -> None:
    with ZipFile(source) as original, ZipFile(
        target,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as mutated:
        for member in original.infolist():
            mutated.writestr(member, original.read(member))
        mutated.writestr(name, payload)


def _capture(
    adapter: ReferenceFileAdapter,
    root: Path,
    source: SourceFileManifest,
) -> InputAdapterError:
    with pytest.raises(InputAdapterError) as captured:
        adapter.prepare_batch(source_root=root, source=source)
    error = captured.value
    assert error.category == "DATA_ERROR"
    assert error.source_location
    assert error.expected_contract
    return error


def test_manifest_is_fixed_non_production_and_xml_parser_is_hardened() -> None:
    adapter = ReferenceFileAdapter()
    assert isinstance(adapter, InputAdapter)
    assert adapter.manifest.adapter_id == REFERENCE_FILE_ADAPTER_ID
    assert adapter.manifest.adapter_version == "1.0.0"
    assert adapter.manifest.staging_contract_version == "raw-staging.v1"
    assert adapter.manifest.production_binding is False
    assert adapter.manifest.accepted_extensions == (".csv", ".xlsx")
    assert adapter.manifest.reference_headers == REFERENCE_HEADERS
    assert adapter.manifest.reference_sheet_name == REFERENCE_SHEET_NAME
    assert openpyxl.__version__ == "3.1.5"
    assert DEFUSEDXML is True


def test_csv_and_xlsx_produce_equal_semantic_rows_and_truthful_file_provenance(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "records.csv"
    xlsx_path = tmp_path / "records.xlsx"
    _write_csv(csv_path)
    _write_xlsx(xlsx_path)
    adapter = ReferenceFileAdapter()

    csv_batch = adapter.prepare_batch(
        source_root=tmp_path,
        source=_source(csv_path.name, batch_id="BATCH-CSV"),
    )
    xlsx_batch = adapter.prepare_batch(
        source_root=tmp_path,
        source=_source(
            xlsx_path.name,
            batch_id="BATCH-XLSX",
            idempotency_key="IDEMPOTENCY-XLSX",
        ),
    )

    assert [row.row_identity for row in csv_batch.rows] == [
        row.row_identity for row in xlsx_batch.rows
    ]
    assert [row.raw_payload for row in csv_batch.rows] == [
        row.raw_payload for row in xlsx_batch.rows
    ]
    assert csv_batch.synthetic_provenance == xlsx_batch.synthetic_provenance
    assert csv_batch.source_system == xlsx_batch.source_system
    assert csv_batch.source_version == xlsx_batch.source_version
    assert csv_batch.data_plane is xlsx_batch.data_plane
    assert csv_batch.rows[0].source_location.startswith("csv:record=2")
    assert xlsx_batch.rows[0].source_location == "xlsx:sheet=records,row=2"
    assert csv_batch.content_sha256 == sha256(csv_path.read_bytes()).hexdigest()
    assert xlsx_batch.content_sha256 == sha256(xlsx_path.read_bytes()).hexdigest()
    assert csv_batch.content_sha256 != xlsx_batch.content_sha256
    assert csv_batch.media_type == "text/csv; charset=utf-8"
    assert xlsx_batch.media_type.endswith("spreadsheetml.sheet")
    assert json.loads(csv_batch.rows[0].raw_payload) == {
        "payload_json": ROWS[0][2],
        "record_type": ROWS[0][0],
        "source_record_id": ROWS[0][1],
    }


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            {"adapter_id": "some.production.adapter"},
            AdapterErrorCode.ADAPTER_ID_MISMATCH,
        ),
        (
            {"adapter_version": "2.0.0"},
            AdapterErrorCode.ADAPTER_VERSION_MISMATCH,
        ),
    ],
)
def test_adapter_identity_and_version_must_match_exactly(
    tmp_path: Path,
    mutation: dict[str, str],
    expected_code: AdapterErrorCode,
) -> None:
    path = tmp_path / "records.csv"
    _write_csv(path)
    error = _capture(
        ReferenceFileAdapter(),
        tmp_path,
        replace(_source(path.name), **mutation),
    )
    assert error.code is expected_code


@pytest.mark.parametrize("extension", [".xls", ".xlsm", ".txt", ".csv.exe"])
def test_legacy_macro_enabled_and_unknown_extensions_are_rejected(
    tmp_path: Path,
    extension: str,
) -> None:
    path = tmp_path / f"records{extension}"
    path.write_bytes(b"not executed")
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(path.name))
    assert error.code is AdapterErrorCode.UNSUPPORTED_FILE_FORMAT


def test_absolute_traversal_and_missing_paths_are_rejected_without_value_leak(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside-secret.csv"
    _write_csv(outside)

    traversal = _capture(
        ReferenceFileAdapter(),
        root,
        _source("../outside-secret.csv"),
    )
    assert traversal.code is AdapterErrorCode.UNSAFE_SOURCE_PATH
    assert "outside-secret" not in str(traversal)

    absolute = _capture(
        ReferenceFileAdapter(),
        root,
        _source(str(outside.resolve())),
    )
    assert absolute.code is AdapterErrorCode.UNSAFE_SOURCE_PATH

    missing = _capture(
        ReferenceFileAdapter(),
        root,
        _source("missing.csv"),
    )
    assert missing.code is AdapterErrorCode.SOURCE_NOT_FILE


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        (b"", AdapterErrorCode.MISSING_HEADER),
        ("record_type,source_record_id,payload_json\n".encode("utf-16"), AdapterErrorCode.INVALID_UTF8),
        (b"\xef\xbb\xbfrecord_type,source_record_id,payload_json\n", AdapterErrorCode.INVALID_UTF8),
        (b'record_type,source_record_id,payload_json\nfactory,F-1,"unterminated', AdapterErrorCode.MALFORMED_CSV),
    ],
)
def test_csv_encoding_bom_and_malformed_dialect_are_rejected(
    tmp_path: Path,
    content: bytes,
    expected_code: AdapterErrorCode,
) -> None:
    path = tmp_path / "records.csv"
    path.write_bytes(content)
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(path.name))
    assert error.code is expected_code


@pytest.mark.parametrize(
    ("header", "expected_code"),
    [
        (
            ("record_type", "source_record_id", "source_record_id"),
            AdapterErrorCode.DUPLICATE_HEADER,
        ),
        (
            ("record_type", "source_record_id", "unknown"),
            AdapterErrorCode.UNKNOWN_HEADER,
        ),
        (
            ("record_type", "source_record_id"),
            AdapterErrorCode.MISSING_HEADER,
        ),
        (
            ("source_record_id", "record_type", "payload_json"),
            AdapterErrorCode.INVALID_HEADER_ORDER,
        ),
        (
            ("record_type", "source_record_id", "payload_json", "extra"),
            AdapterErrorCode.COLUMN_LIMIT_EXCEEDED,
        ),
    ],
)
def test_unknown_missing_duplicate_reordered_and_excess_headers_are_rejected(
    tmp_path: Path,
    header: tuple[str, ...],
    expected_code: AdapterErrorCode,
) -> None:
    path = tmp_path / "records.csv"
    _write_csv(path, header=header, rows=())
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(path.name))
    assert error.code is expected_code


@pytest.mark.parametrize("formula", ["=1+1", "+cmd", "-2+3", "@SUM(A1:A2)"])
def test_csv_formula_like_cells_are_rejected(
    tmp_path: Path,
    formula: str,
) -> None:
    path = tmp_path / "records.csv"
    _write_csv(path, rows=(("factory", "FACTORY-001", formula),))
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(path.name))
    assert error.code is AdapterErrorCode.FORBIDDEN_FORMULA
    assert formula not in str(error)


def test_duplicate_record_and_bounded_file_row_and_cell_limits(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.csv"
    _write_csv(duplicate, rows=(ROWS[0], ROWS[0]))
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(duplicate.name))
    assert error.code is AdapterErrorCode.DUPLICATE_SOURCE_RECORD

    control = tmp_path / "control.csv"
    _write_csv(control, rows=(("factory", "F\n1", "{}"),))
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(control.name))
    assert error.code is AdapterErrorCode.INVALID_ROW

    row_limited = tmp_path / "row-limited.csv"
    _write_csv(row_limited)
    error = _capture(
        ReferenceFileAdapter(limits=ReferenceFileLimits(max_rows=1)),
        tmp_path,
        _source(row_limited.name),
    )
    assert error.code is AdapterErrorCode.ROW_LIMIT_EXCEEDED

    cell_limited = tmp_path / "cell-limited.csv"
    _write_csv(cell_limited, rows=(("factory", "F-1", "{}"),))
    error = _capture(
        ReferenceFileAdapter(limits=ReferenceFileLimits(max_cell_characters=1)),
        tmp_path,
        _source(cell_limited.name),
    )
    assert error.code is AdapterErrorCode.INVALID_ROW

    file_limited = tmp_path / "file-limited.csv"
    _write_csv(file_limited)
    error = _capture(
        ReferenceFileAdapter(limits=ReferenceFileLimits(max_file_size_bytes=32)),
        tmp_path,
        _source(file_limited.name),
    )
    assert error.code is AdapterErrorCode.FILE_SIZE_LIMIT_EXCEEDED


def test_xlsx_formula_non_text_sheet_and_shape_controls(tmp_path: Path) -> None:
    formula = tmp_path / "formula.xlsx"
    _write_xlsx(formula, rows=(("factory", "F-1", "=1+1"),))
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(formula.name))
    assert error.code is AdapterErrorCode.FORBIDDEN_FORMULA

    numeric = tmp_path / "numeric.xlsx"
    _write_xlsx(numeric, rows=(("factory", "F-1", 42),))
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(numeric.name))
    assert error.code is AdapterErrorCode.INVALID_CELL_TYPE

    wrong_sheet = tmp_path / "wrong-sheet.xlsx"
    _write_xlsx(wrong_sheet, sheet_name="Sheet1")
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(wrong_sheet.name))
    assert error.code is AdapterErrorCode.INVALID_SHEET

    extra_sheet = tmp_path / "extra-sheet.xlsx"
    _write_xlsx(extra_sheet, extra_sheet=True)
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(extra_sheet.name))
    assert error.code is AdapterErrorCode.SHEET_LIMIT_EXCEEDED

    extra_column = tmp_path / "extra-column.xlsx"
    _write_xlsx(
        extra_column,
        header=(*REFERENCE_HEADERS, "extra"),
        rows=(),
    )
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(extra_column.name))
    assert error.code is AdapterErrorCode.COLUMN_LIMIT_EXCEEDED


@pytest.mark.parametrize(
    ("member_name", "payload", "expected_code"),
    [
        ("xl/vbaProject.bin", b"synthetic-not-a-real-macro", AdapterErrorCode.FORBIDDEN_MACRO),
        (
            "xl/externalLinks/externalLink1.xml",
            b"<externalLink/>",
            AdapterErrorCode.FORBIDDEN_EXTERNAL_LINK,
        ),
        (
            "customXml/_rels/item1.xml.rels",
            b'<Relationships><Relationship TargetMode="External"/></Relationships>',
            AdapterErrorCode.FORBIDDEN_EXTERNAL_LINK,
        ),
        (
            "customXml/unsafe.xml",
            b'<!DOCTYPE x [<!ENTITY e "unsafe">]><x>&e;</x>',
            AdapterErrorCode.UNSAFE_ARCHIVE,
        ),
        ("../unsafe.xml", b"<unsafe/>", AdapterErrorCode.UNSAFE_ARCHIVE),
    ],
)
def test_macro_external_link_and_unsafe_xml_members_are_rejected(
    tmp_path: Path,
    member_name: str,
    payload: bytes,
    expected_code: AdapterErrorCode,
) -> None:
    base = tmp_path / "base.xlsx"
    mutated = tmp_path / "mutated.xlsx"
    _write_xlsx(base)
    _add_archive_member(base, mutated, member_name, payload)
    error = _capture(ReferenceFileAdapter(), tmp_path, _source(mutated.name))
    assert error.code is expected_code


def test_xlsx_archive_expansion_and_row_limits_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "records.xlsx"
    _write_xlsx(path)
    archive_error = _capture(
        ReferenceFileAdapter(
            limits=ReferenceFileLimits(max_archive_uncompressed_bytes=128)
        ),
        tmp_path,
        _source(path.name),
    )
    assert archive_error.code is AdapterErrorCode.UNSAFE_ARCHIVE

    row_error = _capture(
        ReferenceFileAdapter(limits=ReferenceFileLimits(max_rows=1)),
        tmp_path,
        _source(path.name),
    )
    assert row_error.code is AdapterErrorCode.ROW_LIMIT_EXCEEDED
