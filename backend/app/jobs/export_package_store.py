"""Root-confined local adapter for verified internal Simulation export packages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import cast

from app.application.export_downloads import VerifiedExportPackagePort
from app.exporters.standard_package import (
    MAX_STANDARD_EXPORT_MANIFEST_BYTES,
    StandardExportError,
    archive_standard_export_package,
    load_standard_export_package,
    standard_export_bytes_fingerprint,
)
from app.exporters.change_report_package import (
    archive_change_report_export_package,
    change_report_export_bytes_fingerprint,
    load_change_report_export_package,
)


_EXPORT_JOB_ID = re.compile(r"export-job-[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class StoredVerifiedExportPackage:
    content: bytes
    package_id: str
    manifest_fingerprint: str
    storage_reference: str
    archive_fingerprint: str
    manifest: dict[str, object]


def export_attempt_destination(
    storage_root: Path,
    *,
    export_job_id: str,
    attempt: int,
) -> Path:
    """Resolve the only accepted flat directory identity without accepting a path."""

    root = storage_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("storage_root must be an existing directory")
    if _EXPORT_JOB_ID.fullmatch(export_job_id) is None:
        raise ValueError("export_job_id is invalid")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    destination = (root / f"{export_job_id}-attempt-{attempt}").resolve()
    if destination.parent != root:
        raise ValueError("ExportJob storage identity escaped configured root")
    return destination


class LocalExportPackageStore:
    """Read-only adapter; package bytes remain authoritative only after verification."""

    def __init__(self, storage_root: Path) -> None:
        root = storage_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("storage_root must be an existing directory")
        self._storage_root = root

    def load(self, *, export_job_id: str, attempt: int) -> VerifiedExportPackagePort:
        destination = export_attempt_destination(
            self._storage_root,
            export_job_id=export_job_id,
            attempt=attempt,
        )
        if destination.is_symlink():
            raise ValueError("export package directory cannot be a symlink")
        try:
            manifest_path = destination / "manifest.json"
            if (
                manifest_path.is_symlink()
                or not manifest_path.is_file()
                or manifest_path.stat().st_size < 1
                or manifest_path.stat().st_size > MAX_STANDARD_EXPORT_MANIFEST_BYTES
            ):
                raise ValueError("export manifest is missing or unsafe")
            manifest = json.loads(manifest_path.read_bytes())
            version = manifest.get("export_manifest_version") if isinstance(manifest, dict) else None
            if version == "export-manifest.v3":
                package = load_change_report_export_package(destination)
                archive = archive_change_report_export_package(package)
                archive_fingerprint = change_report_export_bytes_fingerprint(archive)
            elif version == "export-manifest.v2":
                package = load_standard_export_package(destination)
                archive = archive_standard_export_package(package)
                archive_fingerprint = standard_export_bytes_fingerprint(archive)
            else:
                raise ValueError("unsupported export manifest version")
        except StandardExportError as error:
            raise ValueError("export package failed verification") from error
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("export package failed verification") from error
        return StoredVerifiedExportPackage(
            content=archive,
            package_id=package.package_id,
            manifest_fingerprint=package.manifest_fingerprint,
            storage_reference=package.storage_reference,
            archive_fingerprint=archive_fingerprint,
            manifest=cast(dict[str, object], package.manifest),
        )


__all__ = [
    "LocalExportPackageStore",
    "StoredVerifiedExportPackage",
    "export_attempt_destination",
]
