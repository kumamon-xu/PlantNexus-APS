"""Synchronous internal worker composition for the P4 ChangeReport package."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.application.export_jobs import ExportJobService, ExportJobServiceResult
from app.domain.export_job import ExportJobContext, audit_event_id
from app.exporters.change_report_package import (
    ChangeReportExportPackage,
    build_change_report_export_package,
    write_change_report_export_package,
)
from app.exporters.standard_package import StandardExportPackage
from app.jobs.export_package_store import export_attempt_destination


@dataclass(frozen=True, slots=True)
class ChangeReportExportWorkerResult:
    job: ExportJobServiceResult
    package: ChangeReportExportPackage
    destination: Path


class InternalChangeReportExportJobWorker:
    """Claim, materialize, and complete v3 without publish or external I/O."""

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
        p3_package: StandardExportPackage,
        schedule_version: Mapping[str, object],
        publication_result: Mapping[str, object],
        change_report: Mapping[str, object],
        solver_report: Mapping[str, object],
        validation_report: Mapping[str, object],
        kpi: Mapping[str, object],
        correlation_id: str,
    ) -> ChangeReportExportWorkerResult:
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
            if claimed.document.get("export_job_version") != "export-job.v3":
                raise RuntimeError("claimed ExportJob is not the P4 v3 carrier")
            package = build_change_report_export_package(
                p3_package=p3_package,
                schedule_version=schedule_version,
                publication_result=publication_result,
                export_job=claimed.document,
                change_report=change_report,
                solver_report=solver_report,
                validation_report=validation_report,
                kpi=kpi,
                create_audit_event_id=audit_event_id(export_job_id, "CREATE", 0),
                attempt_audit_event_id=claimed.audit_event_id,
                completion_audit_event_id=completion_event_id,
                correlation_id=correlation_id,
                generated_at_utc=terminal_context.occurred_at_utc,
            )
            destination = export_attempt_destination(
                self._storage_root,
                export_job_id=export_job_id,
                attempt=attempt,
            )
            write_change_report_export_package(package, destination)
            completed = self._service.complete(
                export_job_id,
                terminal_context,
                expected_lease_reference=lease_reference,
                artifact_manifest={
                    "export_manifest_version": "export-manifest.v3",
                    "package_id": package.package_id,
                    "manifest_fingerprint": package.manifest_fingerprint,
                    "storage_reference": package.storage_reference,
                },
            )
            return ChangeReportExportWorkerResult(completed, package, destination)
        except Exception:
            self._service.fail(
                export_job_id,
                terminal_context,
                expected_lease_reference=lease_reference,
                error_message="P4 ChangeReport package materialization failed.",
            )
            raise


__all__ = [
    "ChangeReportExportWorkerResult",
    "InternalChangeReportExportJobWorker",
]
