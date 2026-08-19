"""Raw Staging contracts and the bounded ReferenceFileAdapter v1 boundary."""

from .adapter import (
    AdapterErrorCode,
    AdapterManifest,
    InputAdapter,
    InputAdapterError,
    REFERENCE_HEADERS,
    REFERENCE_SHEET_NAME,
    ReferenceFileLimits,
    SourceFileManifest,
)

from .contracts import (
    ImportStagingError,
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    StagingErrorCode,
    StagingWriteResult,
    SyntheticImportProvenance,
)
from .repository import ImportStagingRepository
from .reference_file_adapter import (
    RAW_STAGING_CONTRACT_VERSION,
    REFERENCE_FILE_ADAPTER_ID,
    REFERENCE_FILE_ADAPTER_VERSION,
    ReferenceFileAdapter,
)
from .staging import build_staged_import_batch

__all__ = [
    "AdapterErrorCode",
    "AdapterManifest",
    "ImportStagingError",
    "ImportStagingRepository",
    "InputAdapter",
    "InputAdapterError",
    "RAW_STAGING_CONTRACT_VERSION",
    "REFERENCE_FILE_ADAPTER_ID",
    "REFERENCE_FILE_ADAPTER_VERSION",
    "REFERENCE_HEADERS",
    "REFERENCE_SHEET_NAME",
    "RawImportRow",
    "ReferenceFileAdapter",
    "ReferenceFileLimits",
    "SourceFileManifest",
    "StagedImportBatch",
    "StagingDataPlane",
    "StagingErrorCode",
    "StagingWriteResult",
    "SyntheticImportProvenance",
    "build_staged_import_batch",
]
