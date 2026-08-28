"""Authorized retrieval of one verified internal Simulation export package."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Protocol, cast

from app.domain.export_job import (
    ExportJobContext,
    ExportJobError,
    ExportJobFailure,
    reject_export_job,
    require_job_authorization,
)
from app.domain.workspace_contracts import require_workspace_document
from app.domain.execution_contracts import require_p4_document

_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")


class StoredDownloadExportJobPort(Protocol):
    document: dict[str, object]


class DownloadExportJobRepositoryPort(Protocol):
    def get(self, export_job_id: str) -> StoredDownloadExportJobPort | None: ...


class VerifiedExportPackagePort(Protocol):
    @property
    def content(self) -> bytes: ...

    @property
    def package_id(self) -> str: ...

    @property
    def manifest_fingerprint(self) -> str: ...

    @property
    def storage_reference(self) -> str: ...

    @property
    def archive_fingerprint(self) -> str: ...

    @property
    def manifest(self) -> Mapping[str, object]: ...


class ExportPackageStorePort(Protocol):
    def load(
        self, *, export_job_id: str, attempt: int
    ) -> VerifiedExportPackagePort: ...


@dataclass(frozen=True, slots=True)
class ExportPackageDownloadResult:
    content: bytes
    filename: str
    media_type: str
    export_job_id: str
    attempt: int
    package_id: str
    manifest_fingerprint: str
    archive_fingerprint: str
    completion_audit_event_id: str
    correlation_id: str


def _artifact(document: Mapping[str, object]) -> Mapping[str, object]:
    value = document.get("artifact_manifest")
    if not isinstance(value, Mapping) or set(value) != {
        "export_manifest_version",
        "package_id",
        "manifest_fingerprint",
        "storage_reference",
    }:
        reject_export_job(ExportJobFailure.EXPORT_FAILED, "artifact_manifest")
    return cast(Mapping[str, object], value)


class ExportPackageDownloadService:
    """Authorize before lookup, then verify DB, directory, manifest, and ZIP bytes."""

    def __init__(
        self,
        *,
        export_job_repository: DownloadExportJobRepositoryPort,
        package_store: ExportPackageStorePort,
    ) -> None:
        self._jobs = export_job_repository
        self._packages = package_store

    def download(
        self,
        export_job_id: str,
        context: ExportJobContext,
        *,
        correlation_id: str,
    ) -> ExportPackageDownloadResult:
        require_job_authorization(export_job_id, context)
        try:
            stored = self._jobs.get(export_job_id)
        except ExportJobError:
            raise
        except Exception as error:
            raise ExportJobError(
                ExportJobFailure.PERSISTENCE_FAILED,
                field="export_job_repository",
            ) from error
        if stored is None:
            reject_export_job(ExportJobFailure.SOURCE_NOT_FOUND, "export_job_id")
        document = stored.document
        try:
            contract = (
                require_p4_document(document)
                if document.get("export_job_version") == "export-job.v3"
                else require_workspace_document(document)
            )
        except (TypeError, ValueError) as error:
            raise ExportJobError(
                ExportJobFailure.EXPORT_FAILED,
                field="export_job",
            ) from error
        if contract not in {"export-job.v2", "export-job.v3"}:
            reject_export_job(ExportJobFailure.EXPORT_FAILED, "export_job_version")
        expected_manifest_version = (
            "export-manifest.v3" if contract == "export-job.v3" else "export-manifest.v2"
        )
        if (
            document.get("state") != "EXPORTED"
            or document.get("data_plane") != "SIMULATION"
            or document.get("target") != "SIMULATION_INTERNAL"
        ):
            reject_export_job(ExportJobFailure.STATE_CONFLICT, "state/plane/target")
        attempt = document.get("attempt")
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            reject_export_job(ExportJobFailure.EXPORT_FAILED, "attempt")
        artifact = _artifact(document)
        job_schedule = document.get("schedule_version")
        if not isinstance(job_schedule, Mapping):
            reject_export_job(ExportJobFailure.EXPORT_FAILED, "schedule_version")
        manifest_fingerprint = artifact.get("manifest_fingerprint")
        storage_reference = artifact.get("storage_reference")
        if (
            artifact.get("export_manifest_version") != expected_manifest_version
            or not isinstance(artifact.get("package_id"), str)
            or not isinstance(manifest_fingerprint, str)
            or _FINGERPRINT.fullmatch(manifest_fingerprint) is None
            or not isinstance(storage_reference, str)
            or _FINGERPRINT.fullmatch(storage_reference) is None
        ):
            reject_export_job(ExportJobFailure.EXPORT_FAILED, "artifact_manifest")
        try:
            package = self._packages.load(
                export_job_id=export_job_id,
                attempt=attempt,
            )
            manifest = package.manifest
            manifest_job = manifest.get("export_job")
            manifest_schedule = manifest.get("schedule_version")
            audit_lineage = manifest.get("audit_lineage")
            archive = package.content
            if not isinstance(archive, bytes):
                reject_export_job(ExportJobFailure.EXPORT_FAILED, "archive_content")
            computed_archive_fingerprint = f"sha256:{sha256(archive).hexdigest()}"
            if not isinstance(manifest_job, Mapping):
                reject_export_job(ExportJobFailure.EXPORT_FAILED, "manifest.export_job")
            if not isinstance(manifest_schedule, Mapping) or not isinstance(
                audit_lineage, Mapping
            ):
                reject_export_job(
                    ExportJobFailure.EXPORT_FAILED,
                    "manifest.schedule_version/audit_lineage",
                )
            if (
                package.package_id != artifact["package_id"]
                or package.manifest_fingerprint != artifact["manifest_fingerprint"]
                or package.storage_reference != artifact["storage_reference"]
                or not isinstance(package.archive_fingerprint, str)
                or _FINGERPRINT.fullmatch(package.archive_fingerprint) is None
                or package.archive_fingerprint != computed_archive_fingerprint
                or manifest.get("target") != "SIMULATION_INTERNAL"
                or manifest.get("export_manifest_version") != expected_manifest_version
                or manifest_job.get("export_job_version") != contract
                or manifest.get("synthetic") is not True
                or manifest_job.get("export_job_id") != export_job_id
                or manifest_job.get("attempt") != attempt
                or manifest_job.get("state_at_materialization") != "EXPORTING"
                or dict(manifest_schedule) != dict(job_schedule)
                or manifest.get("synthetic_provenance")
                != document.get("synthetic_provenance")
                or audit_lineage.get("completion_audit_event_id")
                != document.get("latest_audit_event_id")
                or (
                    contract == "export-job.v3"
                    and manifest.get("change_report") != document.get("change_report")
                )
            ):
                reject_export_job(ExportJobFailure.EXPORT_FAILED, "artifact_lineage")
        except ExportJobError:
            raise
        except (OSError, ValueError) as error:
            raise ExportJobError(
                ExportJobFailure.EXPORT_FAILED,
                field="artifact_package",
            ) from error
        completion_audit = document.get("latest_audit_event_id")
        if not isinstance(completion_audit, str) or not completion_audit:
            reject_export_job(ExportJobFailure.EXPORT_FAILED, "latest_audit_event_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            reject_export_job(ExportJobFailure.INVALID_REQUEST, "correlation_id")
        return ExportPackageDownloadResult(
            content=archive,
            filename=f"{package.package_id}.zip",
            media_type="application/zip",
            export_job_id=export_job_id,
            attempt=attempt,
            package_id=package.package_id,
            manifest_fingerprint=package.manifest_fingerprint,
            archive_fingerprint=package.archive_fingerprint,
            completion_audit_event_id=completion_audit,
            correlation_id=correlation_id,
        )


__all__ = [
    "ExportPackageDownloadResult",
    "ExportPackageDownloadService",
    "VerifiedExportPackagePort",
]
