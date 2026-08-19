"""Strict UTF-8 CSV transport reader for ReferenceFileAdapter v1."""

from __future__ import annotations

from collections.abc import Iterator
import codecs
import csv
from io import StringIO

from app.importers.adapter import (
    AdapterErrorCode,
    InputAdapterError,
    ReferenceFileLimits,
    ReferenceTable,
    SourceCellRow,
    validate_reference_table,
)


def _csv_error(
    code: AdapterErrorCode,
    *,
    location: str,
    expected: str,
    message: str,
) -> InputAdapterError:
    return InputAdapterError(
        code,
        source_location=location,
        expected_contract=expected,
        message=message,
    )


def read_reference_csv(
    content: bytes,
    *,
    limits: ReferenceFileLimits,
) -> ReferenceTable:
    """Decode the fixed CSV dialect without sniffing or implicit transcoding."""

    if content.startswith(codecs.BOM_UTF8):
        raise _csv_error(
            AdapterErrorCode.INVALID_UTF8,
            location="csv:bytes=0",
            expected="UTF-8 without a byte-order mark",
            message="a UTF-8 byte-order mark is not part of the reference format",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _csv_error(
            AdapterErrorCode.INVALID_UTF8,
            location="csv:bytes",
            expected="strict UTF-8",
            message="the CSV source is not valid UTF-8",
        ) from None
    if "\x00" in text:
        raise _csv_error(
            AdapterErrorCode.INVALID_UTF8,
            location="csv:bytes",
            expected="UTF-8 text without NUL characters",
            message="the CSV source contains a forbidden NUL character",
        )

    reader = csv.reader(
        StringIO(text, newline=""),
        delimiter=",",
        quotechar='"',
        doublequote=True,
        escapechar=None,
        skipinitialspace=False,
        strict=True,
    )
    try:
        header_values = next(reader, None)
        header = (
            SourceCellRow(source_location="csv:record=1", values=tuple(header_values))
            if header_values is not None
            else None
        )

        def rows() -> Iterator[SourceCellRow]:
            previous_line = reader.line_num
            for record_number, values in enumerate(reader, start=2):
                first_line = previous_line + 1
                last_line = reader.line_num
                previous_line = last_line
                physical = (
                    str(first_line)
                    if first_line == last_line
                    else f"{first_line}-{last_line}"
                )
                yield SourceCellRow(
                    source_location=(
                        f"csv:record={record_number},physical-lines={physical}"
                    ),
                    values=tuple(values),
                )

        return validate_reference_table(header=header, rows=rows(), limits=limits)
    except InputAdapterError:
        raise
    except csv.Error:
        raise _csv_error(
            AdapterErrorCode.MALFORMED_CSV,
            location=f"csv:physical-line={reader.line_num}",
            expected="comma delimiter, double-quote escaping, strict CSV records",
            message="the CSV source does not satisfy the fixed dialect",
        ) from None


__all__ = ["read_reference_csv"]
