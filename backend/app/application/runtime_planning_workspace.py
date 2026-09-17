"""Deployable Simulation workspace composition for Headless Runtime control.

This façade binds the existing P3 manual, approval, publication, read, and export
services.  Transport authentication remains server-supplied and the domain
services retain state, authorization, idempotency, and audit authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
from typing import Any, NoReturn, Protocol, cast

from app.application.approval import ApprovalDecisionService
from app.application.candidate_admission import CandidateAdmissionError
from app.application.schedule_commands import ScheduleCommandService
from app.application.export_jobs import ExportJobService
from app.application.publication import PublicationService
from app.domain.authorization import ApprovalDecisionContext
from app.domain.export_job import ExportJobContext, ExportJobRequest
from app.domain.publication import PublicationContext
from app.domain.schedule_commands import ScheduleCommandContext
from app.extensions.contracts import RuntimeExtensionError


_SUPPORTED_OPERATIONS = frozenset(
    {
        "GET_SCHEDULE_VERSION",
        "APPROVE_SCHEDULE_VERSION",
        "REJECT_SCHEDULE_VERSION",
        "PUBLISH_SCHEDULE_VERSION",
        "CREATE_EXPORT_JOB",
        "GET_EXPORT_JOB",
    }
)
_MANUAL_OPERATIONS = frozenset(
    {"EXECUTE_SCHEDULE_COMMAND", "VALIDATE_SCHEDULE_VERSION"}
)
type ManualBinding = Callable[
    [Mapping[str, object]], tuple[Mapping[str, object], ScheduleCommandService]
]


class RuntimeScheduleReadRepositoryPort(Protocol):
    def get(self, schedule_version_id: str) -> dict[str, object] | None: ...


class RuntimePublicationReadRepositoryPort(Protocol):
    def get(self, publication_id: str) -> dict[str, object] | None: ...


class RuntimeExportJobReadRepositoryPort(Protocol):
    def get(self, export_job_id: str) -> object | None: ...


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
    """Bounded workspace façade; unsupported operations stay unavailable."""

    def __init__(
        self,
        *,
        data_plane: str,
        schedule_repository: RuntimeScheduleReadRepositoryPort,
        publication_repository: RuntimePublicationReadRepositoryPort,
        export_job_repository: RuntimeExportJobReadRepositoryPort,
        approval_service: ApprovalDecisionService,
        publication_service: PublicationService,
        export_service: ExportJobService,
        manual_binding: ManualBinding | None = None,
        reads: Any = None,
        exports: Any = None,
    ) -> None:
        self._data_plane = data_plane
        self._schedules = schedule_repository
        self._publications = publication_repository
        self._exports = export_job_repository
        self._approval = approval_service
        self._publication = publication_service
        self._export = export_service
        self._manual_binding = manual_binding
        self._reads = reads
        self._runtime_exports = exports

    @property
    def supported_operations(self) -> frozenset[str]:
        return (
            _SUPPORTED_OPERATIONS
            | (
                frozenset(
                    {"RETRY_EXPORT_JOB", "CANCEL_EXPORT_JOB", "DOWNLOAD_EXPORT_PACKAGE"}
                )
                if self._runtime_exports
                else frozenset()
            )
            | (
                frozenset(
                    {
                        "QUERY_WORKSPACE",
                        "COMPARE_SCHEDULE_VERSIONS",
                        "GET_PLANNING_RUN",
                        "LIST_AUDIT_EVENTS",
                    }
                )
                if self._reads
                else frozenset()
            )
            | (_MANUAL_OPERATIONS if self._manual_binding else frozenset())
        )

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

    def _read_schedule(self, request: Any) -> Mapping[str, object]:
        schedule = self._get_schedule(request)
        return {
            **schedule,
            "schedule_version": schedule,
            "allowed_actions": [
                action
                for action in cast(list[str], schedule["allowed_actions"])
                if action in request.context.resolved_capabilities
            ],
            "freshness": "FRESH",
            "generated_at_utc": request.context.occurred_at_utc,
            "correlation_id": request.context.correlation_id,
        }

    def _manual(self, request: Any) -> Mapping[str, object]:
        if self._manual_binding is None:
            _error("SERVICE_UNAVAILABLE", field="manual_binding")
        source = self._get_schedule(request)
        # v2 carries replan/fact lineage that this v1 owner must never discard.
        if source.get("schedule_version_version") != "schedule-version.v1":
            _error("MIXED_LINEAGE", field="source.schedule_version_version")
        context = request.context
        try:
            problem, service = self._manual_binding(source)
            result = service.execute(
                _document(request),
                problem,
                ScheduleCommandContext(
                    actor_ref=context.actor_ref,
                    resolved_capabilities=context.resolved_capabilities,
                    auth_policy_version=context.auth_policy_version,
                    occurred_at_utc=context.occurred_at_utc,
                    code_commit=context.code_commit,
                ),
            )
        except RuntimeExtensionError as error:
            _error(
                "VALIDATION_FAILED"
                if error.code == "EXTENSION_VALIDATION_FAILED"
                else "SERVICE_UNAVAILABLE",
                field="candidate_admission.extension",
            )
        except CandidateAdmissionError as error:
            _error(
                "STALE_SOURCE"
                if error.reason.startswith("STALE_")
                else "PERSISTENCE_FAILED",
                field="candidate_admission",
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
        if "export" not in request.context.resolved_capabilities or not _in_scope(
            request.context.schedule_version_scope, schedule_id
        ):
            _error("AUTHORIZATION_DENIED", field="schedule_version_scope")
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            _error("SOURCE_NOT_FOUND", field="resource_id")
        if self._reads is not None:
            self._reads.version_sources(schedule)
        if self._runtime_exports is not None:
            self._runtime_exports.package(schedule)
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
        if self._runtime_exports is not None:
            return self._runtime_exports.dispatch(
                result.document,
                self._runtime_exports.context(result.document, request=request),
            )
        return result.document

    def _get_export(self, request: Any) -> Mapping[str, object]:
        export_id = self._resource_id(request)
        if not _in_scope(request.context.export_job_scope, export_id):
            _error("AUTHORIZATION_DENIED", field="export_job_scope")
        record = self._exports.get(export_id)
        if record is None:
            _error("SOURCE_NOT_FOUND", field="resource_id")
        document = getattr(record, "document", None)
        if not isinstance(document, Mapping):
            _error("SERVICE_UNAVAILABLE", field="export_job_repository")
        return cast(Mapping[str, object], document)

    def execute(self, request: Any) -> Any:
        self._require_context(request)
        handlers = {
            "GET_SCHEDULE_VERSION": self._read_schedule,
            "APPROVE_SCHEDULE_VERSION": self._approve,
            "REJECT_SCHEDULE_VERSION": self._approve,
            "EXECUTE_SCHEDULE_COMMAND": self._manual,
            "VALIDATE_SCHEDULE_VERSION": self._manual,
            "PUBLISH_SCHEDULE_VERSION": self._publish,
            "CREATE_EXPORT_JOB": self._create_export,
            "GET_EXPORT_JOB": self._get_export,
        }
        if self._reads is not None:
            handlers.update(
                {
                    "QUERY_WORKSPACE": self._reads.query,
                    "LIST_AUDIT_EVENTS": self._reads.query,
                    "COMPARE_SCHEDULE_VERSIONS": self._reads.compare,
                    "GET_PLANNING_RUN": self._reads.planning_run,
                }
            )
        if self._runtime_exports is not None:
            handlers.update(
                {
                    "RETRY_EXPORT_JOB": self._runtime_exports.control,
                    "CANCEL_EXPORT_JOB": self._runtime_exports.control,
                    "DOWNLOAD_EXPORT_PACKAGE": self._runtime_exports.download,
                }
            )
        operation = getattr(request.operation, "value", request.operation)
        if (
            operation
            in {
                "QUERY_WORKSPACE",
                "COMPARE_SCHEDULE_VERSIONS",
                "GET_PLANNING_RUN",
                "GET_SCHEDULE_VERSION",
                "GET_EXPORT_JOB",
            }
            and "view" not in request.context.resolved_capabilities
        ):
            _error("AUTHORIZATION_DENIED", field="capability")
        if (
            operation == "LIST_AUDIT_EVENTS"
            and "audit" not in request.context.resolved_capabilities
        ):
            _error("AUTHORIZATION_DENIED", field="capability")
        # Recheck server context at the façade, including direct application use.
        if operation in _MANUAL_OPERATIONS or operation in {
            "APPROVE_SCHEDULE_VERSION",
            "REJECT_SCHEDULE_VERSION",
        }:
            command = _document(request)
            required = {
                "MOVE_OPERATION": "edit",
                "ASSIGN_RESOURCE": "edit",
                "SET_LOCK": "lock",
                "REMOVE_LOCK": "lock",
                "SUBMIT_FOR_REVIEW": "edit",
                "APPROVE": "approve",
                "REJECT": "reject",
            }.get(cast(str, command.get("command_type")))
            allowed = {
                "EXECUTE_SCHEDULE_COMMAND": {
                    "MOVE_OPERATION",
                    "ASSIGN_RESOURCE",
                    "SET_LOCK",
                    "REMOVE_LOCK",
                },
                "VALIDATE_SCHEDULE_VERSION": {"SUBMIT_FOR_REVIEW"},
                "APPROVE_SCHEDULE_VERSION": {"APPROVE"},
                "REJECT_SCHEDULE_VERSION": {"REJECT"},
            }[operation]
            if command.get("command_type") not in allowed or command.get(
                "source_id"
            ) != self._resource_id(request):
                _error("INVALID_COMMAND", field="command")
            if required not in request.context.resolved_capabilities or not _in_scope(
                request.context.schedule_version_scope, self._resource_id(request)
            ):
                _error("AUTHORIZATION_DENIED", field="schedule_version_scope")
        handler = handlers.get(operation)
        if handler is None:
            _error("SERVICE_UNAVAILABLE", field="operation")
        return handler(request)


__all__ = ["RuntimePlanningWorkspaceApplication", "RuntimePlanningWorkspaceError"]
