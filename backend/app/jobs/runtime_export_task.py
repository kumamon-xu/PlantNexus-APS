"""Durable Runtime export delivery: server-owned sources and attempt identities."""

from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
import re
from typing import Any

from app.application.export_jobs import ExportJobServiceResult
from app.application.export_downloads import ExportPackageDownloadService
from app.domain.export_job import ExportJobContext
from app.domain.types import parse_utc_instant
from app.data_validation.canonical_ingress import parse_strict_json
from app.exporters.package import build_internal_export_package
from app.jobs.export_job import InternalExportJobWorker
from app.jobs.export_package_store import LocalExportPackageStore

EXPORT_TASK = "plantnexus.export.materialize.v1"


class RuntimeExports:
    def __init__(
        self,
        *,
        service: Any,
        jobs: Any,
        schedules: Any,
        publications: Any,
        sources: Any,
        root: Path,
        clock: Any,
        code_commit: str,
        lease_seconds: int,
        publisher: Any = None,
        scenario_directory: Path | None = None,
    ) -> None:
        self.service, self.jobs, self.schedules, self.publications = (
            service,
            jobs,
            schedules,
            publications,
        )
        self.sources, self.root, self.clock = sources, root.resolve(strict=True), clock
        self.code_commit, self.lease_seconds, self.publisher = (
            code_commit,
            lease_seconds,
            publisher,
        )
        self.worker = InternalExportJobWorker(service=service, storage_root=self.root)
        self.scenario_directory = (
            scenario_directory.resolve(strict=True) if scenario_directory else None
        )
        self.downloads = ExportPackageDownloadService(
            export_job_repository=jobs,
            package_store=LocalExportPackageStore(storage_root=self.root),
        )

    def package(self, version: Any) -> Any:
        from app.application.runtime_planning_workspace import (
            RuntimePlanningWorkspaceError,
        )

        sources = self.sources(version["lineage"]["planning_run_id"], version)
        fingerprint = sources.problem["problem_hash"]
        if (
            self.scenario_directory is None
            or not isinstance(fingerprint, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint) is None
        ):
            raise RuntimePlanningWorkspaceError(
                "MIXED_LINEAGE", field="export.scenario_manifest"
            )
        path = self.scenario_directory / (fingerprint.removeprefix("sha256:") + ".json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
            raise RuntimePlanningWorkspaceError(
                "MIXED_LINEAGE", field="export.scenario_manifest"
            )
        manifest = parse_strict_json(path.read_bytes())
        documents = asdict(sources)
        documents.pop("kpi")
        return build_internal_export_package(**documents, scenario_manifest=manifest)

    def context(self, job: Any, *, request: Any = None) -> ExportJobContext:
        if request is not None:
            context = request.context
            return ExportJobContext(
                context.actor_ref,
                context.authenticated,
                context.resolved_capabilities,
                context.schedule_version_scope,
                frozenset(
                    {request.resource_id if job is None else job["export_job_id"]}
                )
                if "*" in context.export_job_scope
                else context.export_job_scope,
                context.auth_policy_version,
                context.production_binding,
                context.occurred_at_utc,
                context.code_commit,
            )
        return ExportJobContext(
            "actor:runtime-export-worker",
            True,
            frozenset({"export"}),
            frozenset({job["schedule_version"]["schedule_version_id"]}),
            frozenset({job["export_job_id"]}),
            "runtime-export-worker.v1",
            False,
            self.clock().isoformat(timespec="seconds").replace("+00:00", "Z"),
            self.code_commit,
        )

    def dispatch(
        self, job: Any, context: ExportJobContext, *, command: Any = None
    ) -> Any:
        job_id = job["export_job_id"]
        if command is None:
            context = replace(context, export_job_scope=frozenset({job_id}))
        if job["state"] == "CREATED" or command is not None:
            claimed = self.service.claim(
                job_id,
                context,
                owner_reference="runtime-export",
                lease_expires_at_utc=parse_utc_instant(context.occurred_at_utc)
                + timedelta(seconds=self.lease_seconds),
                command=command,
            )
            job = claimed.document
        if job["state"] != "EXPORTING":
            return job
        message = {
            "message_version": "runtime-export-message.v1",
            "export_job_id": job_id,
            "attempt": job["attempt"],
            "lease_reference": job["lease_reference"],
        }
        try:
            self.publisher.send_task(
                EXPORT_TASK, args=(message,), task_id=f"{job_id}-{job['attempt']}"
            )
        except Exception:
            # Unknown acknowledgement is safe: the delayed task cannot use the retired lease.
            job = self.service.fail(
                job_id,
                context,
                expected_lease_reference=job["lease_reference"],
                error_message="Export dispatch failed.",
            ).document
        return job

    def control(self, request: Any) -> Any:
        from app.application.runtime_planning_workspace import (
            RuntimePlanningWorkspaceError,
        )

        scope = request.context.export_job_scope
        if request.document.get("idempotency_key") != request.context.idempotency_key:
            raise RuntimePlanningWorkspaceError(
                "INVALID_REQUEST", field="idempotency_key"
            )
        if "export" not in request.context.resolved_capabilities or not (
            "*" in scope or request.resource_id in scope
        ):
            raise RuntimePlanningWorkspaceError(
                "AUTHORIZATION_DENIED", field="export_job_scope"
            )
        stored = self.jobs.get(request.resource_id)
        if stored is None:
            raise RuntimePlanningWorkspaceError(
                "SOURCE_NOT_FOUND", field="export_job_id"
            )
        job = stored.document
        context = self.context(job, request=request)
        if request.document["command_type"] == "RETRY_EXPORT":
            version = self.schedules.get(job["schedule_version"]["schedule_version_id"])
            self.package(version)
            return self.dispatch(job, context, command=request.document)
        return self.service.cancel(
            request.resource_id,
            context,
            expected_lease_reference=job["lease_reference"],
            expired_recovery=True,
            command=request.document,
        ).document

    def download(self, request: Any) -> Any:
        return self.downloads.download(
            request.resource_id,
            self.context(None, request=request),
            correlation_id=request.context.correlation_id,
        )

    def execute(self, message: Any) -> dict[str, object]:
        if (
            not isinstance(message, dict)
            or set(message)
            != {"message_version", "export_job_id", "attempt", "lease_reference"}
            or message["message_version"] != "runtime-export-message.v1"
            or not isinstance(message["export_job_id"], str)
            or re.fullmatch(r"export-job-[0-9a-f]{64}", message["export_job_id"])
            is None
            or type(message["attempt"]) is not int
            or message["attempt"] < 1
            or not isinstance(message["lease_reference"], str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", message["lease_reference"]) is None
        ):
            raise ValueError("Invalid Runtime export message")
        stored = self.jobs.get(message["export_job_id"])
        if stored is None:
            raise ValueError("Unknown Runtime export identity")
        job = stored.document
        if job["state"] != "EXPORTING" or any(
            job[key] != message[key] for key in ("attempt", "lease_reference")
        ):
            return {"disposition": "STALE_DELIVERY"}
        context = self.context(job)
        if (
            stored.lease_expires_at_utc is None
            or parse_utc_instant(context.occurred_at_utc) >= stored.lease_expires_at_utc
        ):
            self.service.fail(
                job["export_job_id"],
                context,
                expected_lease_reference=job["lease_reference"],
                error_message="Export lease expired.",
                expired_recovery=True,
            )
            return {"disposition": "EXPIRED"}
        # One immutable attempt directory is shared by API/Workers. A crash leaves
        # its claim marker; expiry retires that attempt before an explicit retry.
        marker = self.root / f"{job['export_job_id']}-{job['attempt']}.claim"
        try:
            marker.mkdir()
        except FileExistsError:
            return {"disposition": "DUPLICATE_DELIVERY"}
        except OSError:
            self.service.fail(
                job["export_job_id"],
                context,
                expected_lease_reference=job["lease_reference"],
                error_message="Export storage is unavailable.",
            )
            return {"disposition": "EXPORT_FAILED"}
        try:
            version = self.schedules.get(job["schedule_version"]["schedule_version_id"])
            publication = self.publications.get(
                version["publication"]["publication_id"]
            )
            package = self.package(version)
            claimed = ExportJobServiceResult(
                job, stored.state_revision, job["latest_audit_event_id"], False
            )
            result = self.worker.run_claimed(
                claimed=claimed,
                terminal_context=self.context(job),
                p2_package=package,
                schedule_version=version,
                publication_result=publication,
                correlation_id=job["export_job_id"],
            )
            return {"disposition": result.job.document["state"]}
        except Exception:
            latest = self.jobs.get(job["export_job_id"])
            if (
                latest is not None
                and latest.document["state"] == "EXPORTING"
                and latest.document["lease_reference"] == job["lease_reference"]
            ):
                self.service.fail(
                    job["export_job_id"],
                    self.context(job),
                    expected_lease_reference=job["lease_reference"],
                    error_message="Export source or materialization failed.",
                    expired_recovery=True,
                )
            return {"disposition": "EXPORT_FAILED"}


def register_runtime_export_task(application: Any, executor: RuntimeExports) -> None:
    @application.task(name=EXPORT_TASK)
    def materialize(message: Any) -> dict[str, object]:
        return executor.execute(message)
