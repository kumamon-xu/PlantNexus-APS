"""Thin synchronous worker composition for the internal P3 export job."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.application.export_jobs import ExportJobService, ExportJobServiceResult
from app.domain.export_job import ExportJobContext, audit_event_id
from app.exporters.package import InternalExportPackage
from app.exporters.standard_package import (
    StandardExportPackage,
    build_standard_export_package,
    write_standard_export_package,
)


@dataclass(frozen=True, slots=True)
class ExportWorkerResult:
    job: ExportJobServiceResult
    package: StandardExportPackage
    destination: Path


class InternalExportJobWorker:
    """Claim, materialize, and complete without calling publish or external I/O."""

    def __init__(self, *, service: ExportJobService, storage_root: Path) -> None:
        root = storage_root.resolve()
        if not root.is_dir():
            raise ValueError("storage_root must be an existing directory")
        self._service = service
        self._storage_root = root

    def run(
        self,
        *,
        export_job_id: str,
        claim_context: ExportJobContext,
        terminal_context: ExportJobContext,
        owner_reference: str,
        lease_expires_at_utc: datetime,
        p2_package: InternalExportPackage,
        schedule_version: Mapping[str, object],
        publication_result: Mapping[str, object],
        correlation_id: str,
    ) -> ExportWorkerResult:
        claimed = self._service.claim(
            export_job_id,
            claim_context,
            owner_reference=owner_reference,
            lease_expires_at_utc=lease_expires_at_utc,
        )
        lease_reference = claimed.document.get("lease_reference")
        attempt = claimed.document.get("attempt")
        if not isinstance(lease_reference, str) or not isinstance(attempt, int):
            raise RuntimeError("claimed ExportJob lacks lease/attempt")
        completion_event_id = audit_event_id(export_job_id, "COMPLETED", attempt)
        try:
            package = build_standard_export_package(
                p2_package=p2_package,
                schedule_version=schedule_version,
                publication_result=publication_result,
                export_job=claimed.document,
                create_audit_event_id=audit_event_id(export_job_id, "CREATE", 0),
                attempt_audit_event_id=claimed.audit_event_id,
                completion_audit_event_id=completion_event_id,
                correlation_id=correlation_id,
                generated_at_utc=terminal_context.occurred_at_utc,
            )
            destination = (
                self._storage_root / f"{export_job_id}-attempt-{attempt}"
            ).resolve()
            if destination.parent != self._storage_root:
                raise RuntimeError("ExportJob storage identity escaped configured root")
            write_standard_export_package(package, destination)
            completed = self._service.complete(
                export_job_id,
                terminal_context,
                expected_lease_reference=lease_reference,
                artifact_manifest={
                    "export_manifest_version": "export-manifest.v2",
                    "package_id": package.package_id,
                    "manifest_fingerprint": package.manifest_fingerprint,
                    "storage_reference": package.storage_reference,
                },
            )
            return ExportWorkerResult(completed, package, destination)
        except Exception:
            self._service.fail(
                export_job_id,
                terminal_context,
                expected_lease_reference=lease_reference,
                error_message="Export package materialization failed.",
            )
            raise


__all__ = ["ExportWorkerResult", "InternalExportJobWorker"]
