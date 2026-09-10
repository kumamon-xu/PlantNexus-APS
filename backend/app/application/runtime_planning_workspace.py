"""Deployable Simulation workspace composition for Headless Runtime output.

This façade binds the existing P3 approval, publication, read, and export
services.  Transport authentication remains server-supplied and the domain
services retain state, authorization, idempotency, and audit authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any, NoReturn, cast
from app.application.approval import ApprovalDecisionService
from app.application.export_jobs import ExportJobService
from app.application.publication import PublicationService
from app.domain.authorization import ApprovalDecisionContext
from app.domain.export_job import ExportJobContext, ExportJobRequest
from app.domain.publication import PublicationContext
from app.infrastructure.export_job_repository import SqlAlchemyExportJobRepository
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)


_SUPPORTED_OPERATIONS = frozenset(
    {
        "GET_SCHEDULE_VERSION",
        "APPROVE_SCHEDULE_VERSION",
        "PUBLISH_SCHEDULE_VERSION",
        "CREATE_EXPORT_JOB",
        "GET_EXPORT_JOB",
    }
)


class RuntimePlanningWorkspaceError(RuntimeError):
    def __init__(self, reason: str, *, field: str) -> None:
        self.reason = reason
        self.field = field
        super().__init__(f"{reason}: {field}")


def _error(reason: str, *, field: str) -> NoReturn:
    raise RuntimePlanningWorkspaceError(reason, field=field)


def _document(request: Any) -> Mapping[str, object]:
    if not isinstance(request.document, Mapping):
        _error("INVALID_REQUEST", field="document")
    return cast(Mapping[str, object], request.document)


def _in_scope(scope: frozenset[str], resource_id: str) -> bool:
    return "*" in scope or resource_id in scope


class RuntimePlanningWorkspaceApplication:
    """Narrow output façade; unsupported workspace operations stay unavailable."""

    def __init__(
        self,
        *,
        data_plane: str,
        schedule_repository: SqlAlchemyScheduleVersionRepository,
        publication_repository: SqlAlchemyPublicationRepository,
        export_job_repository: SqlAlchemyExportJobRepository,
        approval_service: ApprovalDecisionService,
        publication_service: PublicationService,
        export_service: ExportJobService,
    ) -> None:
        self._data_plane = data_plane
        self._schedules = schedule_repository
        self._publications = publication_repository
        self._exports = export_job_repository
        self._approval = approval_service
        self._publication = publication_service
        self._export = export_service

    @property
    def supported_operations(self) -> frozenset[str]:
        return _SUPPORTED_OPERATIONS

    @staticmethod
    def _resource_id(request: Any) -> str:
        if not isinstance(request.resource_id, str) or not request.resource_id:
            _error("INVALID_REQUEST", field="resource_id")
        return cast(str, request.resource_id)

    def _require_context(self, request: Any) -> None:
        context = request.context
        if (
            not context.authenticated
            or context.data_plane != self._data_plane
            or context.production_binding
        ):
            _error("AUTHORIZATION_DENIED", field="context")

    @staticmethod
    def _approval_context(
        request: Any,
        schedule_version_id: str,
    ) -> ApprovalDecisionContext:
        context = request.context
        return ApprovalDecisionContext(
            actor_ref=context.actor_ref,
            authenticated=context.authenticated,
            resolved_capabilities=context.resolved_capabilities,
            schedule_version_scope=frozenset({schedule_version_id}),
            auth_policy_version=context.auth_policy_version,
            production_binding=context.production_binding,
            occurred_at_utc=context.occurred_at_utc,
            code_commit=context.code_commit,
        )

    def _publication_context(
        self,
        request: Any,
        schedule_version_id: str,
    ) -> PublicationContext:
        schedule = self._schedules.get(schedule_version_id)
        if schedule is None:
            _error("SOURCE_NOT_FOUND", field="resource_id")
        decision = schedule.get("decision")
        parent = (
            decision.get("audit_event_id") if isinstance(decision, Mapping) else None
        )
        context = request.context
        return PublicationContext(
            actor_ref=context.actor_ref,
            authenticated=context.authenticated,
            resolved_capabilities=context.resolved_capabilities,
            schedule_version_scope=frozenset({schedule_version_id}),
            auth_policy_version=context.auth_policy_version,
            production_binding=context.production_binding,
            occurred_at_utc=context.occurred_at_utc,
            code_commit=context.code_commit,
            parent_audit_event_id=cast(str | None, parent),
        )

    @staticmethod
    def _export_context(
        request: Any,
        *,
        schedule_version_id: str,
        parent_audit_event_id: str,
    ) -> ExportJobContext:
        context = request.context
        return ExportJobContext(
            actor_ref=context.actor_ref,
            authenticated=context.authenticated,
            resolved_capabilities=context.resolved_capabilities,
            schedule_version_scope=frozenset({schedule_version_id}),
            export_job_scope=context.export_job_scope,
            auth_policy_version=context.auth_policy_version,
            production_binding=context.production_binding,
            occurred_at_utc=context.occurred_at_utc,
            code_commit=context.code_commit,
            parent_audit_event_id=parent_audit_event_id,
        )

    def _get_schedule(self, request: Any) -> Mapping[str, object]:
        schedule_id = self._resource_id(request)
        if not _in_scope(request.context.schedule_version_scope, schedule_id):
            _error("AUTHORIZATION_DENIED", field="schedule_version_scope")
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            _error("SOURCE_NOT_FOUND", field="resource_id")
        return cast(dict[str, object], schedule)

    def _approve(self, request: Any) -> Mapping[str, object]:
        schedule_id = self._resource_id(request)
        result = self._approval.execute(
            _document(request), self._approval_context(request, schedule_id)
        )
        return {**asdict(result), "exact_replay": result.exact_replay}

    def _publish(self, request: Any) -> Mapping[str, object]:
        schedule_id = self._resource_id(request)
        result = self._publication.execute(
            _document(request),
            self._publication_context(request, schedule_id),
        )
        return result.document

    def _create_export(self, request: Any) -> Mapping[str, object]:
        command = _document(request)
        schedule_id = self._resource_id(request)
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            _error("SOURCE_NOT_FOUND", field="resource_id")
        publication_evidence = schedule.get("publication")
        publication_id = (
            publication_evidence.get("publication_id")
            if isinstance(publication_evidence, Mapping)
            else None
        )
        if not isinstance(publication_id, str):
            _error("PUBLICATION_NOT_FOUND", field="schedule_version.publication")
        publication = self._publications.get(publication_id)
        if publication is None:
            _error("PUBLICATION_NOT_FOUND", field="schedule_version.publication")
        payload = command.get("payload")
        if (
            not isinstance(payload, Mapping)
            or payload.get("package_profile") != "p3-standard-export.v1"
        ):
            _error("INVALID_REQUEST", field="command.payload.package_profile")
        provenance = command.get("synthetic_provenance")
        if not isinstance(provenance, Mapping):
            _error("INVALID_REQUEST", field="command.synthetic_provenance")
        raw_key = request.context.idempotency_key
        if not isinstance(raw_key, str):
            _error("INVALID_REQUEST", field="idempotency_key")
        export_request = ExportJobRequest(
            schedule_version_id=schedule_id,
            expected_content_fingerprint=cast(
                str, command.get("expected_content_fingerprint")
            ),
            raw_idempotency_key=raw_key,
            reason=cast(str, command.get("reason")),
            correlation_id=request.context.correlation_id,
            environment=request.context.environment,
            synthetic_provenance=cast(Mapping[str, object], provenance),
            data_plane=request.context.data_plane,
            target=cast(str, command.get("target")),
        )
        result = self._export.create(
            export_request,
            self._export_context(
                request,
                schedule_version_id=schedule_id,
                parent_audit_event_id=cast(str, publication["audit_event_id"]),
            ),
            publication_result=publication,
        )
        return result.document

    def _get_export(self, request: Any) -> Mapping[str, object]:
        export_id = self._resource_id(request)
        if not _in_scope(request.context.export_job_scope, export_id):
            _error("AUTHORIZATION_DENIED", field="export_job_scope")
        record = self._exports.get(export_id)
        if record is None:
            _error("SOURCE_NOT_FOUND", field="resource_id")
        return record.document

    def execute(self, request: Any) -> Mapping[str, object]:
        self._require_context(request)
        handlers = {
            "GET_SCHEDULE_VERSION": self._get_schedule,
            "APPROVE_SCHEDULE_VERSION": self._approve,
            "PUBLISH_SCHEDULE_VERSION": self._publish,
            "CREATE_EXPORT_JOB": self._create_export,
            "GET_EXPORT_JOB": self._get_export,
        }
        operation = getattr(request.operation, "value", request.operation)
        handler = handlers.get(operation)
        if handler is None:
            _error("SERVICE_UNAVAILABLE", field="operation")
        return handler(request)


__all__ = ["RuntimePlanningWorkspaceApplication", "RuntimePlanningWorkspaceError"]
