"""ReferenceFileAdapter v1: safe files to immutable Raw Staging batches."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.importers.adapter import (
    AdapterErrorCode,
    AdapterManifest,
    InputAdapterError,
    REFERENCE_HEADERS,
    REFERENCE_SHEET_NAME,
    ReferenceFileLimits,
    SourceFileManifest,
)
from app.importers.contracts import RawImportRow, StagedImportBatch
from app.importers.csv_reader import read_reference_csv
from app.importers.excel_reader import read_reference_xlsx
from app.importers.staging import build_staged_import_batch

REFERENCE_FILE_ADAPTER_ID = "plantnexus.reference-file"
REFERENCE_FILE_ADAPTER_VERSION = "1.0.0"
RAW_STAGING_CONTRACT_VERSION = "raw-staging.v1"

_MEDIA_TYPES = {
    ".csv": "text/csv; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _adapter_error(
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


class ReferenceFileAdapter:
    """A formal reference adapter, explicitly not a production-system binding."""

    def __init__(self, *, limits: ReferenceFileLimits | None = None) -> None:
        self._limits = limits or ReferenceFileLimits()
        self._manifest = AdapterManifest(
            adapter_id=REFERENCE_FILE_ADAPTER_ID,
            adapter_version=REFERENCE_FILE_ADAPTER_VERSION,
            staging_contract_version=RAW_STAGING_CONTRACT_VERSION,
            production_binding=False,
            accepted_extensions=tuple(_MEDIA_TYPES),
            capabilities=(
                "reference-format.v1",
                "csv.utf8-fixed-dialect",
                "xlsx.read-only",
                "active-content.reject",
                "raw-staging.opaque-rows",
            ),
            reference_headers=REFERENCE_HEADERS,
            reference_sheet_name=REFERENCE_SHEET_NAME,
            limits=self._limits,
        )

    @property
    def manifest(self) -> AdapterManifest:
        return self._manifest

    def _validate_source_manifest(self, source: SourceFileManifest) -> None:
        if source.adapter_id != self.manifest.adapter_id:
            raise _adapter_error(
                AdapterErrorCode.ADAPTER_ID_MISMATCH,
                location="manifest:adapter_id",
                expected=self.manifest.adapter_id,
                message="the source manifest targets a different adapter",
            )
        if source.adapter_version != self.manifest.adapter_version:
            raise _adapter_error(
                AdapterErrorCode.ADAPTER_VERSION_MISMATCH,
                location="manifest:adapter_version",
                expected=self.manifest.adapter_version,
                message="the source manifest version is not supported",
            )

    def _resolve_source(self, source_root: Path, relative_path: str) -> Path:
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in relative_path
            )
        ):
            raise _adapter_error(
                AdapterErrorCode.UNSAFE_SOURCE_PATH,
                location="manifest:relative_path",
                expected="a non-empty relative path without control characters",
                message="the source path is unsafe",
            )
        try:
            candidate = Path(relative_path)
            if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
                raise _adapter_error(
                    AdapterErrorCode.UNSAFE_SOURCE_PATH,
                    location="manifest:relative_path",
                    expected="a path contained by the configured source root",
                    message="absolute paths and traversal segments are forbidden",
                )
            resolved_root = source_root.resolve(strict=True)
            resolved = (resolved_root / candidate).resolve(strict=True)
        except InputAdapterError:
            raise
        except (OSError, RuntimeError, ValueError):
            raise _adapter_error(
                AdapterErrorCode.SOURCE_NOT_FILE,
                location="manifest:relative_path",
                expected="an existing readable source file",
                message="the source file cannot be resolved",
            ) from None
        if not resolved.is_relative_to(resolved_root):
            raise _adapter_error(
                AdapterErrorCode.UNSAFE_SOURCE_PATH,
                location="manifest:relative_path",
                expected="a path contained by the configured source root",
                message="the resolved source escapes the configured root",
            )
        if not resolved.is_file():
            raise _adapter_error(
                AdapterErrorCode.SOURCE_NOT_FILE,
                location="manifest:relative_path",
                expected="an existing regular source file",
                message="the source is not a regular file",
            )
        return resolved

    def _read_bounded(self, path: Path) -> bytes:
        try:
            with path.open("rb") as stream:
                content = stream.read(self._limits.max_file_size_bytes + 1)
        except OSError:
            raise _adapter_error(
                AdapterErrorCode.SOURCE_NOT_FILE,
                location="manifest:relative_path",
                expected="an existing readable source file",
                message="the source file cannot be read",
            ) from None
        if len(content) > self._limits.max_file_size_bytes:
            raise _adapter_error(
                AdapterErrorCode.FILE_SIZE_LIMIT_EXCEEDED,
                location="source:file",
                expected=f"at most {self._limits.max_file_size_bytes} bytes",
                message="the source exceeds the configured file-size limit",
            )
        return content

    def prepare_batch(
        self,
        *,
        source_root: Path,
        source: SourceFileManifest,
    ) -> StagedImportBatch:
        """Read one bounded file and prepare, but do not persist, a staging batch."""

        self._validate_source_manifest(source)
        path = self._resolve_source(source_root, source.relative_path)
        extension = path.suffix.casefold()
        if extension not in _MEDIA_TYPES:
            raise _adapter_error(
                AdapterErrorCode.UNSUPPORTED_FILE_FORMAT,
                location="source:extension",
                expected=".csv or .xlsx",
                message="the source file extension is not supported",
            )
        content = self._read_bounded(path)
        table = (
            read_reference_csv(content, limits=self._limits)
            if extension == ".csv"
            else read_reference_xlsx(content, limits=self._limits)
        )
        rows = tuple(
            RawImportRow(
                row_identity=record.row_identity,
                source_location=record.source_location,
                raw_payload=record.raw_payload,
            )
            for record in table.records
        )
        return build_staged_import_batch(
            batch_id=source.batch_id,
            idempotency_key=source.idempotency_key,
            source_system=source.source_system,
            source_version=source.source_version,
            content_sha256=sha256(content).hexdigest(),
            source_name=path.name,
            media_type=_MEDIA_TYPES[extension],
            content_length_bytes=len(content),
            received_at=source.received_at,
            data_plane=source.data_plane,
            rows=rows,
            synthetic_provenance=source.synthetic_provenance,
        )


__all__ = [
    "RAW_STAGING_CONTRACT_VERSION",
    "REFERENCE_FILE_ADAPTER_ID",
    "REFERENCE_FILE_ADAPTER_VERSION",
    "ReferenceFileAdapter",
]
