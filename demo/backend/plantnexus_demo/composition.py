"""Standalone Demo composition root; the product default remains untouched."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

from fastapi import FastAPI

from app.api.app import create_app
from app.api.contracts import (
    PlanningWorkspaceApplicationError,
    PlanningWorkspaceApplicationRequest,
    PlanningWorkspaceOperation,
    RoutedPlanningWorkspaceApplication,
)
from app.api.replanning_contracts import (
    DYNAMIC_REPLANNING_RESPONSE_VERSION,
    DynamicReplanningApplicationError,
    DynamicReplanningApplicationRequest,
    DynamicReplanningOperation,
    RoutedDynamicReplanningApplication,
)
from app.application.approval import ApprovalDecisionService
from app.application.publication import PublicationService
from app.domain.authorization import ApprovalDecisionContext
from app.domain.publication import PublicationContext
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.replan_repository import (
    SqlAlchemyReplanLineageRepository,
    SqlAlchemyReplanRequestRepository,
)
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane

from .assets import load_demo_assets
from .api import (
    DemoApiError,
    DemoSessionCookieMiddleware,
    create_demo_router,
    demo_error_response,
)
from .jobs import DemoJobRunner, DemoJobService
from .orchestration import BaselineActivationService
from .persistence import (
    ControlStore,
    DemoPersistenceError,
    DemoRuntimePaths,
    RunDatabase,
)
from .presentation import DemoPresentationService
from .security import (
    ControlAuthorizationAuditSink,
    SimulationLocalAuthorizationProvider,
    load_or_create_local_token,
)


def _application_error(error: BaseException, *, field: str) -> PlanningWorkspaceApplicationError:
    raw_reason = getattr(error, "reason", None)
    reason = getattr(raw_reason, "value", raw_reason)
    if not isinstance(reason, str):
        reason = getattr(error, "code", "PERSISTENCE_FAILED")
    if not isinstance(reason, str):
        reason = "PERSISTENCE_FAILED"
    return PlanningWorkspaceApplicationError(
        reason,
        field=field,
        message="Demo workspace operation was rejected",
    )


class ActiveWorkspaceApplication:
    """Resolve repositories from the current run for every formal request."""

    def __init__(self, runtime: DemoRuntime) -> None:
        self.runtime = runtime

    def _database(self) -> RunDatabase:
        active = self.runtime.control.active_run()
        if active is None:
            raise PlanningWorkspaceApplicationError(
                "NOT_FOUND",
                field="active_run",
                message="Demo has no active run",
            )
        return RunDatabase(
            repository_root=self.runtime.repository_root,
            database_path=self.runtime.paths.resolve_relative_database(
                active.database_relative_path
            ),
        )

    def get_schedule(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> Mapping[str, object]:
        database = self._database()
        try:
            if request.resource_id is None:
                raise PlanningWorkspaceApplicationError(
                    "INVALID_REQUEST", field="resource_id", message="resource is required"
                )
            repository = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            document = repository.get(request.resource_id)
            if document is None:
                raise PlanningWorkspaceApplicationError(
                    "NOT_FOUND",
                    field="schedule_version_id",
                    message="ScheduleVersion was not found",
                )
            return document
        finally:
            database.close()


    def list_audit(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> Mapping[str, object]:
        database = self._database()
        try:
            if request.resource_id is None:
                raise PlanningWorkspaceApplicationError(
                    "INVALID_REQUEST", field="resource_id", message="resource is required"
                )
            repository = SqlAlchemyAuditRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            return {
                "items": list(
                    repository.list_for_aggregate(
                        aggregate_type="SCHEDULE_VERSION",
                        aggregate_id=request.resource_id,
                    )
                )
            }
        finally:
            database.close()

    def decide(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> Mapping[str, object]:
        database = self._database()
        try:
            if request.document is None or request.resource_id is None:
                raise PlanningWorkspaceApplicationError(
                    "INVALID_REQUEST", field="command", message="command is required"
                )
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            audits = SqlAlchemyAuditRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            service = ApprovalDecisionService(
                data_plane="SIMULATION",
                transaction_factory=database.engine.begin,
                schedule_repository=cast(Any, schedules),
                audit_repository=cast(Any, audits),
            )
            result = service.execute(
                request.document,
                ApprovalDecisionContext(
                    actor_ref=request.context.actor_ref,
                    authenticated=request.context.authenticated,
                    resolved_capabilities=request.context.resolved_capabilities,
                    schedule_version_scope=request.context.schedule_version_scope,
                    auth_policy_version=request.context.auth_policy_version,
                    production_binding=request.context.production_binding,
                    occurred_at_utc=request.context.occurred_at_utc,
                    code_commit=request.context.code_commit,
                ),
            )
            return {
                "command_id": result.command_id,
                "command_type": result.command_type,
                "source_version": result.source_version,
                "new_version": result.new_version,
                "audit_event_id": result.audit_event_id,
                "replayed": result.exact_replay,
                "correlation_id": result.correlation_id,
            }
        except PlanningWorkspaceApplicationError:
            raise
        except Exception as error:  # noqa: BLE001 - formal HTTP mapper sanitizes
            raise _application_error(error, field="approval") from None
        finally:
            database.close()

    def publish(
        self, request: PlanningWorkspaceApplicationRequest
    ) -> Mapping[str, object]:
        database = self._database()
        try:
            if request.document is None or request.resource_id is None:
                raise PlanningWorkspaceApplicationError(
                    "INVALID_REQUEST", field="command", message="command is required"
                )
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            audits = SqlAlchemyAuditRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            publications = SqlAlchemyPublicationRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            source = schedules.get(request.resource_id)
            decision = None if source is None else source.get("decision")
            parent = (
                cast(str, decision.get("audit_event_id"))
                if isinstance(decision, Mapping)
                and isinstance(decision.get("audit_event_id"), str)
                else None
            )
            result = PublicationService(
                data_plane="SIMULATION",
                transaction_factory=database.engine.begin,
                schedule_repository=cast(Any, schedules),
                audit_repository=cast(Any, audits),
                publication_repository=cast(Any, publications),
            ).execute(
                request.document,
                PublicationContext(
                    actor_ref=request.context.actor_ref,
                    authenticated=request.context.authenticated,
                    resolved_capabilities=request.context.resolved_capabilities,
                    schedule_version_scope=request.context.schedule_version_scope,
                    auth_policy_version=request.context.auth_policy_version,
                    production_binding=request.context.production_binding,
                    occurred_at_utc=request.context.occurred_at_utc,
                    code_commit=request.context.code_commit,
                    parent_audit_event_id=parent,
                ),
            )
            return {
                "published_version": result.published_version,
                "superseded_version": result.superseded_version,
                "audit_event_id": result.audit_event_id,
                "current_schedule_version_id": result.current_schedule_version_id,
                "replayed": result.exact_replay,
                "correlation_id": request.context.correlation_id,
            }
        except PlanningWorkspaceApplicationError:
            raise
        except Exception as error:  # noqa: BLE001 - formal HTTP mapper sanitizes
            raise _application_error(error, field="publication") from None
        finally:
            database.close()


class ActiveDynamicReplanningApplication:
    """Durable P4 append/read façade; business solve runs through Demo jobs."""

    _RESOURCE_TYPES = {
        DynamicReplanningOperation.APPEND_EXECUTION_EVENT: "EXECUTION_EVENT",
        DynamicReplanningOperation.GET_EXECUTION_EVENT: "EXECUTION_EVENT",
        DynamicReplanningOperation.LIST_EXECUTION_EVENTS: "EXECUTION_EVENT_STREAM",
        DynamicReplanningOperation.CREATE_REPLAN_REQUEST: "REPLAN_REQUEST",
        DynamicReplanningOperation.GET_REPLAN_REQUEST: "REPLAN_REQUEST",
        DynamicReplanningOperation.GET_REPLAN_RESULT: "REPLAN_RESULT",
        DynamicReplanningOperation.GET_CHANGE_REPORT: "CHANGE_REPORT",
    }

    def __init__(self, runtime: DemoRuntime) -> None:
        self.runtime = runtime

    def _database(self) -> RunDatabase:
        active = self.runtime.control.active_run()
        if active is None:
            raise DynamicReplanningApplicationError(
                "NOT_FOUND", field="active_run", message="Demo has no active run"
            )
        return RunDatabase(
            repository_root=self.runtime.repository_root,
            database_path=self.runtime.paths.resolve_relative_database(
                active.database_relative_path
            ),
        )

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise DynamicReplanningApplicationError(
                "INVALID_QUERY", field=field, message="query field is required"
            )
        return value

    def execute(
        self, request: DynamicReplanningApplicationRequest
    ) -> Mapping[str, object]:
        if request.operation in {
            DynamicReplanningOperation.CANCEL_REPLAN_REQUEST,
            DynamicReplanningOperation.RETRY_REPLAN_REQUEST,
        }:
            raise DynamicReplanningApplicationError(
                "SERVICE_UNAVAILABLE",
                field="operation",
                message="manual replan control is not enabled in this Demo slice",
            )
        database = self._database()
        try:
            plane = WorkspaceDataPlane.SIMULATION
            events = SqlAlchemyExecutionEventRepository(
                database.engine, data_plane=plane
            )
            requests = SqlAlchemyReplanRequestRepository(
                database.engine, data_plane=plane
            )
            lineage = SqlAlchemyReplanLineageRepository(
                database.engine, data_plane=plane
            )
            replayed = False
            result: dict[str, object]
            if request.operation is DynamicReplanningOperation.APPEND_EXECUTION_EVENT:
                if request.document is None:
                    raise DynamicReplanningApplicationError(
                        "INVALID_INPUT", field="execution_event", message="event is required"
                    )
                write = events.append(request.document)
                result, replayed = write.document, write.replayed
            elif request.operation is DynamicReplanningOperation.GET_EXECUTION_EVENT:
                if request.resource_id is None:
                    raise DynamicReplanningApplicationError(
                        "INVALID_QUERY", field="event_id", message="event id is required"
                    )
                stored = events.get(request.resource_id)
                if stored is None:
                    raise DynamicReplanningApplicationError(
                        "NOT_FOUND", field="event_id", message="event was not found"
                    )
                result = stored
            elif request.operation is DynamicReplanningOperation.LIST_EXECUTION_EVENTS:
                query = request.query or {}
                authority_id = self._required_text(query.get("authority_id"), "authority_id")
                stream_id = self._required_text(query.get("stream_id"), "stream_id")
                stream_version = self._required_text(
                    query.get("stream_version"), "stream_version"
                )
                position = query.get("from_position")
                after_position = (
                    max(0, position - 1)
                    if isinstance(position, int) and not isinstance(position, bool)
                    else 0
                )
                result = {
                    "items": list(
                        events.list_stream(
                            authority_id=authority_id,
                            stream_id=stream_id,
                            stream_version=stream_version,
                            after_position=after_position,
                        )
                    )
                }
            elif request.operation is DynamicReplanningOperation.CREATE_REPLAN_REQUEST:
                if request.document is None:
                    raise DynamicReplanningApplicationError(
                        "INVALID_INPUT", field="replan_request", message="request is required"
                    )
                write = requests.append(request.document)
                result, replayed = write.document, write.replayed
            elif request.operation is DynamicReplanningOperation.GET_REPLAN_REQUEST:
                if request.resource_id is None:
                    raise DynamicReplanningApplicationError(
                        "INVALID_QUERY", field="request_id", message="request id is required"
                    )
                stored = requests.get(request.resource_id)
                if stored is None:
                    raise DynamicReplanningApplicationError(
                        "NOT_FOUND", field="request_id", message="request was not found"
                    )
                result = stored
            elif request.operation is DynamicReplanningOperation.GET_REPLAN_RESULT:
                query = request.query or {}
                attempt_id = self._required_text(query.get("attempt_id"), "attempt_id")
                stored = lineage.get_result_for_attempt(attempt_id)
                if stored is None:
                    raise DynamicReplanningApplicationError(
                        "NOT_FOUND", field="attempt_id", message="result was not found"
                    )
                result = stored
            elif request.operation is DynamicReplanningOperation.GET_CHANGE_REPORT:
                query = request.query or {}
                attempt_id = self._required_text(query.get("attempt_id"), "attempt_id")
                stored = lineage.get_applied_result_for_attempt(attempt_id)
                if stored is None:
                    raise DynamicReplanningApplicationError(
                        "NOT_FOUND", field="attempt_id", message="change report was not found"
                    )
                result = stored.change_report
            else:
                raise DynamicReplanningApplicationError(
                    "SERVICE_UNAVAILABLE",
                    field="operation",
                    message="dynamic replanning operation is not configured",
                )
            return {
                "response_version": DYNAMIC_REPLANNING_RESPONSE_VERSION,
                "operation": request.operation.value,
                "resource_type": self._RESOURCE_TYPES[request.operation],
                "resource_id": request.resource_id,
                "result": result,
                "replayed": replayed,
                "correlation_id": request.context.correlation_id,
            }
        except DynamicReplanningApplicationError:
            raise
        except Exception as error:  # noqa: BLE001 - sanitize repository failures
            raw_reason = getattr(error, "reason", None)
            reason = getattr(raw_reason, "value", raw_reason)
            raise DynamicReplanningApplicationError(
                reason if isinstance(reason, str) else "PERSISTENCE_FAILED",
                field="dynamic_replanning",
                message="dynamic replanning persistence rejected the request",
            ) from None
        finally:
            database.close()


@dataclass(slots=True)
class DemoRuntime:
    repository_root: Path
    paths: DemoRuntimePaths
    control: ControlStore
    runner: DemoJobRunner
    jobs: DemoJobService
    baseline: BaselineActivationService
    presentation: DemoPresentationService
    local_token: str

    def active_run_id(self) -> str | None:
        active = self.control.active_run()
        return None if active is None else active.run_id

    def _presentation_configuration(self) -> dict[str, object]:
        assets = load_demo_assets(
            self.repository_root / "demo" / "data" / "cnc-showcase"
        )
        templates = cast(list[Mapping[str, object]], assets.route_templates["templates"])
        classes = cast(list[Mapping[str, object]], assets.priority_policy["classes"])
        return {
            "configuration_version": "cnc-demo-presentation-configuration.v1",
            "factory_timezone": assets.manifest["factory_timezone"],
            "route_template_version": assets.route_templates["route_template_version"],
            "route_templates": [
                {
                    "template_id": template["template_id"],
                    "product_family_zh": template["product_family_zh"],
                    "operation_count": len(cast(list[object], template["steps"])),
                    "operation_names_zh": [
                        cast(Mapping[str, object], step)["operation_name_zh"]
                        for step in cast(list[object], template["steps"])
                    ],
                }
                for template in templates
            ],
            "priority_policy_version": assets.priority_policy[
                "priority_policy_version"
            ],
            "priority_classes": [
                {
                    "class_id": item["class_id"],
                    "label_zh": item["label_zh"],
                    "priority_weight": item["priority_weight"],
                }
                for item in classes
            ],
        }

    def _comparison_reference(
        self,
        *,
        run_id: str,
        schedule: Mapping[str, object] | None,
        current_schedule_version_id: str | None,
    ) -> dict[str, object] | None:
        if (
            schedule is None
            or schedule.get("schedule_version_version") != "schedule-version.v2"
            or schedule.get("state") != "DRAFT"
        ):
            return None
        job = self.control.latest_succeeded_job(
            job_kind="URGENT_REPLAN", run_id=run_id
        )
        result = None if job is None else job.result
        required = (
            "request_id",
            "schedule_version_id",
            "current_published_version_id",
            "change_report_id",
            "demand_order_id",
        )
        if result is None or any(
            not isinstance(result.get(field), str) or not result[field]
            for field in required
        ):
            raise DemoPersistenceError(
                "PERSISTENCE_FAILED",
                field="comparison_reference",
                message="DRAFT comparison lineage is not recoverable",
            )
        if (
            result["schedule_version_id"] != schedule["schedule_version_id"]
            or result["current_published_version_id"]
            != current_schedule_version_id
        ):
            raise DemoPersistenceError(
                "PERSISTENCE_FAILED",
                field="comparison_reference.lineage",
                message="DRAFT comparison lineage differs from current state",
            )
        return {
            "request_id": result["request_id"],
            "before_schedule_version_id": result["current_published_version_id"],
            "after_schedule_version_id": result["schedule_version_id"],
            "change_report_id": result["change_report_id"],
            "demand_order_id": result["demand_order_id"],
        }

    def story_state(self) -> dict[str, object]:
        active = self.control.active_run()
        active_job = self.control.active_job()
        configuration = self._presentation_configuration()
        if active is None:
            return {
                "story_state": "EMPTY",
                "run": None,
                "active_job": None if active_job is None else active_job.job_id,
                "schedule_version": None,
                "current_publication": None,
                "scenario_manifest": None,
                "comparison_reference": None,
                "configuration": configuration,
            }
        database = RunDatabase(
            repository_root=self.repository_root,
            database_path=self.paths.resolve_relative_database(
                active.database_relative_path
            ),
        )
        try:
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            publications = SqlAlchemyPublicationRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            with database.engine.connect() as connection:
                row = connection.exec_driver_sql(
                    """
                    SELECT schedule_version_id FROM schedule_versions
                    WHERE data_plane = 'SIMULATION'
                    ORDER BY created_at_utc DESC, schedule_version_id DESC LIMIT 1
                    """
                ).first()
            schedule = None if row is None else schedules.get(cast(str, row[0]))
            current = publications.get_current(target="SIMULATION_INTERNAL")
            current_schedule_version_id = (
                None if current is None else current.schedule_version_id
            )
            comparison_reference = self._comparison_reference(
                run_id=active.run_id,
                schedule=cast(Mapping[str, object] | None, schedule),
                current_schedule_version_id=current_schedule_version_id,
            )
            if active_job is not None and active_job.job_kind == "URGENT_REPLAN":
                story = "REPLAN_RUNNING"
            elif active_job is not None and active_job.job_kind == "INITIAL_PLAN":
                story = "INITIAL_PLAN_RUNNING"
            elif (
                schedule is not None
                and schedule.get("schedule_version_version") == "schedule-version.v2"
                and schedule.get("state") == "DRAFT"
            ):
                story = "DRAFT_COMPARISON_READY"
            elif current is not None:
                story = "BASELINE_PUBLISHED"
            elif schedule is not None and schedule.get("state") == "READY_FOR_REVIEW":
                story = "READY_FOR_REVIEW"
            else:
                story = "INITIALIZED"
            return {
                "story_state": story,
                "run": {
                    "run_id": active.run_id,
                    "scenario_id": active.scenario_id,
                    "seed": active.seed,
                    "status": active.status,
                    "created_at_utc": active.created_at_utc,
                },
                "active_job": (
                    None
                    if active_job is None
                    else {
                        "job_id": active_job.job_id,
                        "job_kind": active_job.job_kind,
                        "status": active_job.status,
                        "stage": active_job.stage,
                    }
                ),
                "schedule_version": (
                    None
                    if schedule is None
                    else {
                        "schedule_version_id": schedule["schedule_version_id"],
                        "state": schedule["state"],
                        "content_fingerprint": schedule["content_fingerprint"],
                    }
                ),
                "current_publication": (
                    None
                    if current is None
                    else {
                        "schedule_version_id": current.schedule_version_id,
                        "content_fingerprint": current.content_fingerprint,
                        "publication_id": current.publication_id,
                        "reference_revision": current.reference_revision,
                    }
                ),
                "scenario_manifest": database.get_manifest(),
                "comparison_reference": comparison_reference,
                "configuration": configuration,
            }
        finally:
            database.close()

    def close(self) -> None:
        self.runner.shutdown()


def create_demo_runtime(
    *,
    repository_root: Path | None = None,
    runtime_root: Path | None = None,
    auto_resume_queued: bool = True,
) -> DemoRuntime:
    root = (
        Path(__file__).resolve().parents[3]
        if repository_root is None
        else repository_root.resolve()
    )
    resolved_runtime = (
        root / "demo" / "runtime" if runtime_root is None else runtime_root
    )
    paths = DemoRuntimePaths(resolved_runtime)
    control = ControlStore(paths)
    token = load_or_create_local_token(paths)
    runner = DemoJobRunner(
        repository_root=root,
        paths=paths,
        control=control,
        auto_resume_queued=auto_resume_queued,
    )
    runtime = DemoRuntime(
        repository_root=root,
        paths=paths,
        control=control,
        runner=runner,
        jobs=DemoJobService(control=control, runner=runner),
        baseline=BaselineActivationService(
            repository_root=root, paths=paths, control=control
        ),
        presentation=DemoPresentationService(
            repository_root=root, paths=paths, control=control
        ),
        local_token=token,
    )
    return runtime


def create_demo_app(
    *,
    repository_root: Path | None = None,
    runtime_root: Path | None = None,
    auto_resume_queued: bool = True,
) -> FastAPI:
    runtime = create_demo_runtime(
        repository_root=repository_root,
        runtime_root=runtime_root,
        auto_resume_queued=auto_resume_queued,
    )
    workspace = ActiveWorkspaceApplication(runtime)
    dynamic = ActiveDynamicReplanningApplication(runtime)

    def control_probe() -> None:
        runtime.control.active_run()
    planning_application = RoutedPlanningWorkspaceApplication(
        {
            PlanningWorkspaceOperation.GET_SCHEDULE_VERSION: workspace.get_schedule,
            PlanningWorkspaceOperation.APPROVE_SCHEDULE_VERSION: workspace.decide,
            PlanningWorkspaceOperation.REJECT_SCHEDULE_VERSION: workspace.decide,
            PlanningWorkspaceOperation.PUBLISH_SCHEDULE_VERSION: workspace.publish,
            PlanningWorkspaceOperation.LIST_AUDIT_EVENTS: workspace.list_audit,
        }
    )
    application = create_app(
        Settings(
            service_name="plantnexus-cnc-demo",
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
            code_commit="uncommitted",
        ),
        probes={"demo_control": control_probe},
        planning_workspace_application=planning_application,
        dynamic_replanning_application=RoutedDynamicReplanningApplication(
            {operation: dynamic.execute for operation in DynamicReplanningOperation}
        ),
        authorization_provider=SimulationLocalAuthorizationProvider(runtime.local_token),
        authorization_audit_sink=ControlAuthorizationAuditSink(runtime.control),
    )
    application.state.demo_runtime = runtime
    application.add_middleware(DemoSessionCookieMiddleware)
    application.include_router(create_demo_router(runtime))
    application.add_exception_handler(DemoApiError, cast(Any, demo_error_response))
    application.add_event_handler("shutdown", runtime.close)
    return application


__all__ = [
    "ActiveDynamicReplanningApplication",
    "ActiveWorkspaceApplication",
    "DemoRuntime",
    "create_demo_app",
    "create_demo_runtime",
]
