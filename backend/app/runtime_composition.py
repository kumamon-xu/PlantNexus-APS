"""Single explicit composition root for the Headless APS Runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, NoReturn, cast

from celery import Celery

from app import APPLICATION_VERSION, CORE_VERSION, RUNTIME_VERSION
from app.application.runtime_dynamic_replanning import (
    RuntimeDynamicReplanningApplication,
    RuntimeExecutionFactProjectionService,
    RuntimeEventError,
    event_bindings,
)
from app.application.execution_fact_projection import ExecutionFactProjectionService
from app.domain.execution_fact_projection import ProjectionScope
from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.replan_repository import (
    SqlAlchemyProjectionCheckpointRepository,
    SqlAlchemyReplanAuditRepository,
)
from app.infrastructure.replan_persistence import (
    ProjectionCheckpoint,
    ArtifactReference,
    ReplanAuditAction,
    build_replan_audit_record,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import WorkspacePersistenceError
from app.snapshots import SnapshotDataPlane, SnapshotError, build_planning_snapshot
from app.normalization import expand_orders
from sqlalchemy.exc import SQLAlchemyError
from app.application.approval import ApprovalDecisionService
from app.application.canonical_ingress import CanonicalIngressApplicationService
from app.application.export_jobs import ExportJobService
from app.application.planning_runs import PlanningRunOrchestrationService
from app.application.publication import PublicationService
from app.application.runtime_facade import (
    APSRuntimeApplicationFacade,
    RuntimeApplicationBinding,
)
from app.application.runtime_http_adapter import (
    RuntimeHttpContextAdapter,
    RuntimeHttpPolicyCatalog,
)
from app.application.runtime_planning_workspace import (
    RuntimePlanningWorkspaceApplication,
    RuntimePlanningWorkspaceError,
)
from app.application.schedule_commands import ScheduleCommandService
from app.application.runtime_workspace_reads import RuntimeWorkspaceReads
from app.application.workspace_queries import WorkspaceQueryService
from app.application.schedule_comparison import ScheduleComparisonService
from app.domain.workspace import WorkspaceSourceDocuments, bind_workspace_sources
from app.application.schedule_versions import (
    ValidatedSolutionToScheduleVersionService,
)
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    FrozenSchemaCatalog,
    canonical_fingerprint,
    canonical_json_bytes,
    parse_strict_json,
)
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from app.infrastructure.database import DatabaseClient, create_database_client
from app.infrastructure.planning_run_repository import (
    SqlAlchemyPlanningRunRepository,
)
from app.infrastructure.export_job_repository import SqlAlchemyExportJobRepository
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.redis_client import RedisClient, create_redis_client
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.extensions.contracts import RuntimeExtensionArtifact, RuntimeExtensionError
from app.extensions.product_execution import RuntimeExtensionProductExecutor
from app.jobs.planning_run_solver_worker import (
    PlanningRunSolverWorker,
    WorkerReliabilityPolicy,
    utc_now,
)
from app.jobs.planning_run_task import CeleryPlanningRunDispatcher
from app.jobs.runtime_export_task import RuntimeExports
from app.jobs.planning_run_worker_repository import (
    SqlAlchemyPlanningRunWorkerRepository,
)
from app.jobs.runtime_adapters import (
    FrozenPlanningArtifactCatalog,
    RepositoryPlanningInputResolver,
    RepositoryPlanningRunContextProvider,
)
from app.planning.strategies import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    GlobalCpSatStrategy,
)
from app.planning.validation.problem_schedule_validator import (
    VALIDATION_REPORT_CONTRACT,
    ProblemScheduleValidator,
)

if TYPE_CHECKING:
    from app.api.contracts import PlanningWorkspaceApplicationPort
    from app.extensions.registry import LoadedRuntimeExtensionAdapter


RUNTIME_COMPOSITION_DESCRIPTOR_VERSION = "aps-runtime-composition.v1"
RUNTIME_RESOLUTION_VERSION = "runtime-resolution.v1"
EMPTY_EXTENSION_ADAPTER_VERSION = "runtime-extension-adapter.v1"
UNPUBLISHED_EXTENSION_SDK_VERSION = "0.0.0-not-published"
UNPUBLISHED_DEVELOPER_KIT_VERSION = "0.0.0-not-published"
_MAX_CONFIGURED_DOCUMENT_BYTES = 256 * 1024


type JsonObject = dict[str, Any]
type RuntimeClock = Callable[[], datetime]
type RuntimeIdentityFactory = Callable[[], str]


class RuntimeProcess(StrEnum):
    API = "api"
    WORKER = "worker"


class RuntimeCompositionError(RuntimeError):
    """Sanitized startup failure raised before serving business traffic."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code}: {field}: {message}")


def _fail(code: str, *, field: str, message: str) -> NoReturn:
    raise RuntimeCompositionError(code, field=field, message=message)


@dataclass(frozen=True, slots=True)
class EmptyRuntimeExtensionAdapter:
    """Versioned seam only; it performs no discovery or code loading."""

    canonical_bytes: bytes

    @classmethod
    def create(cls) -> EmptyRuntimeExtensionAdapter:
        base: JsonObject = {
            "adapter_version": EMPTY_EXTENSION_ADAPTER_VERSION,
            "mode": "EMPTY",
            "load_policy": "DISABLED_UNTIL_P8_13",
            "extensions": [],
        }
        document = {
            **base,
            "configuration_fingerprint": canonical_fingerprint(base),
        }
        return cls(canonical_bytes=canonical_json_bytes(document))

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))

    @property
    def contributions(self) -> tuple[object, ...]:
        return ()

    @property
    def sdk_api_version(self) -> str:
        return UNPUBLISHED_EXTENSION_SDK_VERSION

    @property
    def registry_protocol_version(self) -> str:
        return "plugin-registry.v1"

    @property
    def readiness_probe(self) -> None:
        return None

    @property
    def extension_set_reference(self) -> JsonObject:
        document = self.document
        basis = {
            "extension_set_version": "runtime-empty-extension-set.v1",
            "adapter_version": document["adapter_version"],
            "extensions": document["extensions"],
            "configuration_fingerprint": document["configuration_fingerprint"],
        }
        return {
            "extension_set_id": "EXTENSION-SET-NONE",
            "extension_set_fingerprint": canonical_fingerprint(basis),
            "configuration_fingerprint": document["configuration_fingerprint"],
        }


@dataclass(frozen=True, slots=True)
class RuntimeCompositionDescriptor:
    """Immutable process-independent identity shared by API and Worker."""

    canonical_bytes: bytes

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))

    @property
    def fingerprint(self) -> str:
        return cast(str, self.document["composition_fingerprint"])

    @property
    def runtime_resolution(self) -> JsonObject:
        return cast(JsonObject, self.document["runtime_resolution"])


class _DescriptorRuntimeProvider:
    def __init__(self, descriptor: RuntimeCompositionDescriptor) -> None:
        self._canonical_bytes = canonical_json_bytes(descriptor.runtime_resolution)

    def current_resolution(self, planning_run_id: str) -> Mapping[str, object]:
        del planning_run_id
        return cast(Mapping[str, object], json.loads(self._canonical_bytes))


@dataclass(slots=True)
class RuntimeComposition:
    """Owned runtime graph for exactly one process role."""

    process: RuntimeProcess
    descriptor: RuntimeCompositionDescriptor
    extension_adapter: EmptyRuntimeExtensionAdapter | LoadedRuntimeExtensionAdapter
    application: APSRuntimeApplicationFacade | None
    planning_workspace_application: PlanningWorkspaceApplicationPort | None
    http_context_adapter: RuntimeHttpContextAdapter
    extension_product_executor: RuntimeExtensionProductExecutor
    worker: PlanningRunSolverWorker | None
    database: DatabaseClient
    redis: RedisClient | None
    export_worker: RuntimeExports | None = None
    dynamic_replanning_application: RuntimeDynamicReplanningApplication | None = None

    @property
    def probes(self) -> Mapping[str, Callable[[], None]]:
        values: dict[str, Callable[[], None]] = {"database": self.database.probe}
        if self.redis is not None:
            values["redis"] = self.redis.probe
        extension_probe = self.extension_adapter.readiness_probe
        if extension_probe is not None:
            values["extension_registry"] = extension_probe
        return MappingProxyType(values)

    def close(self) -> None:
        if self.redis is not None:
            self.redis.close()
        self.database.close()

    def safe_manifest(self) -> JsonObject:
        """Return evidence without endpoints, paths, credentials, or documents."""

        descriptor = self.descriptor.document
        return {
            "manifest_version": "aps-runtime-composition-manifest.v1",
            "process": self.process.value,
            "environment": descriptor["environment"],
            "data_plane": descriptor["data_plane"],
            "composition_fingerprint": descriptor["composition_fingerprint"],
            "runtime_resolution_fingerprint": cast(
                Mapping[str, object], descriptor["runtime_resolution"]
            )["resolution_fingerprint"],
            "extension_adapter": descriptor["extension_adapter"],
            "http_context_policy": descriptor["http_context_policy"],
            "port_bindings": descriptor["port_bindings"],
            "secrets_embedded": False,
            "production_ready": False,
        }


def _workspace_plane(settings: Settings) -> WorkspaceDataPlane:
    mapping = {
        DataPlane.SIMULATION: WorkspaceDataPlane.SIMULATION,
        DataPlane.PRODUCTION: WorkspaceDataPlane.PRODUCTION,
    }
    plane = mapping.get(settings.data_plane)
    if plane is None:
        _fail(
            "DATA_PLANE_UNAVAILABLE",
            field="data_plane",
            message="Headless Runtime requires an explicit APS business data plane",
        )
    return cast(WorkspaceDataPlane, plane)


def _runtime_environment(settings: Settings) -> str:
    environment = settings.runtime_environment.value.upper()
    if environment == RuntimeEnvironment.STAGING.value.upper():
        _fail(
            "UNKNOWN_ENVIRONMENT",
            field="runtime_environment",
            message="Staging is not a frozen Headless carrier environment",
        )
    return environment


def _configured_document(path: Path | None, *, field: str) -> JsonObject:
    if path is None:
        _fail(
            "CONFIGURATION_MISSING",
            field=field,
            message="Runtime planning artifact is not configured",
        )
    try:
        candidate = cast(Path, path)
        if candidate.is_symlink():
            raise OSError
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file() or resolved.is_symlink():
            raise OSError
        size = resolved.stat().st_size
        if size < 2 or size > _MAX_CONFIGURED_DOCUMENT_BYTES:
            raise OSError
        return parse_strict_json(resolved.read_bytes())
    except Exception as error:  # noqa: BLE001 - paths/content stay private
        raise RuntimeCompositionError(
            "CONFIGURATION_INVALID",
            field=field,
            message="Runtime planning artifact could not be safely loaded",
        ) from error


def _schema_contract(settings: Settings) -> CanonicalIngressContract:
    try:
        directory = settings.runtime_schema_directory
        if directory.is_symlink():
            raise OSError
        resolved = directory.resolve(strict=True)
        if not resolved.is_dir() or resolved.is_symlink():
            raise OSError
        return CanonicalIngressContract.from_schema_directory(resolved)
    except Exception as error:  # noqa: BLE001 - configured paths stay private
        raise RuntimeCompositionError(
            "CONFIGURATION_INVALID",
            field="runtime_schema_directory",
            message="Runtime Schema catalog could not be safely loaded",
        ) from error


def _component_fingerprint(
    explicit: str | None,
    *,
    component: str,
    settings: Settings,
) -> str:
    return explicit or canonical_fingerprint(
        {
            "evidence": "DEVELOPMENT_DERIVED_NOT_RELEASE_DIGEST",
            "component": component,
            "version": APPLICATION_VERSION,
            "code_commit": settings.code_commit,
        }
    )


def _descriptor(
    *,
    settings: Settings,
    contract: CanonicalIngressContract,
    catalog: FrozenPlanningArtifactCatalog,
    extension_adapter: EmptyRuntimeExtensionAdapter | LoadedRuntimeExtensionAdapter,
    http_policy: RuntimeHttpPolicyCatalog,
    configured_events: tuple[dict[str, Any], ...] = (),
) -> RuntimeCompositionDescriptor:
    plane = _workspace_plane(settings).value
    environment = _runtime_environment(settings)
    kit_identity = (
        settings.developer_kit_version,
        settings.developer_kit_fingerprint,
    )
    if any(value is not None for value in kit_identity) and not all(
        value is not None for value in kit_identity
    ):
        _fail(
            "CONFIGURATION_INVALID",
            field="developer_kit_identity",
            message="Developer Kit version and fingerprint must be configured together",
        )
    if extension_adapter.document["mode"] == "LOADED" and not all(
        value is not None for value in kit_identity
    ):
        _fail(
            "CONFIGURATION_INVALID",
            field="developer_kit_identity",
            message="Loaded Extensions require an exact Developer Kit identity",
        )
    developer_kit_version = (
        settings.developer_kit_version or UNPUBLISHED_DEVELOPER_KIT_VERSION
    )
    runtime_resolution: JsonObject = {
        "runtime_resolution_version": RUNTIME_RESOLUTION_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "runtime_artifact_fingerprint": _component_fingerprint(
            settings.runtime_artifact_fingerprint,
            component="aps-runtime",
            settings=settings,
        ),
        "core_version": CORE_VERSION,
        "core_artifact_fingerprint": _component_fingerprint(
            settings.core_artifact_fingerprint,
            component="aps-core",
            settings=settings,
        ),
        "extension_sdk_version": extension_adapter.sdk_api_version,
        "registry_protocol_version": extension_adapter.registry_protocol_version,
        "extension_set": extension_adapter.extension_set_reference,
        "developer_kit_version": developer_kit_version,
        "developer_kit_fingerprint": _component_fingerprint(
            settings.developer_kit_fingerprint,
            component=f"aps-developer-kit-{developer_kit_version}",
            settings=settings,
        ),
        "solver_backend_id": STRATEGY_ID,
        "solver_backend_version": CORE_VERSION,
        "validator_version": CORE_VERSION,
        "resolution_fingerprint": "",
    }
    runtime_resolution["resolution_fingerprint"] = canonical_fingerprint(
        {
            key: value
            for key, value in runtime_resolution.items()
            if key != "resolution_fingerprint"
        }
    )
    try:
        contract.validate_runtime_resolution(runtime_resolution)
    except Exception as error:  # noqa: BLE001 - expose only stable startup failure
        raise RuntimeCompositionError(
            "RUNTIME_RESOLUTION_INVALID",
            field="runtime_resolution",
            message="Runtime identity violates the frozen Headless contract",
        ) from error

    port_bindings = {
        "canonical_ingress_repository": "sqlalchemy-canonical-ingress.v1",
        "planning_run_repository": "sqlalchemy-planning-run.v1",
        "worker_repository": "sqlalchemy-planning-run-worker.v1",
        "transaction": "sqlalchemy-engine-begin.v1",
        "clock": "utc-system-clock.v1",
        "identity": "uuid4-dispatch-identity.v1",
        "solver": f"{STRATEGY_ID}/{STRATEGY_VERSION}",
        "validator": f"problem-schedule-validator/{VALIDATION_REPORT_CONTRACT}",
        "audit": "sqlalchemy-append-only-audit.v1",
        "http_context": "runtime-http-context-adapter.v1",
    }
    if extension_adapter.document["mode"] == "LOADED":
        port_bindings["extension_registry"] = "runtime-plugin-registry.v1"
    base: JsonObject = {
        "composition_descriptor_version": RUNTIME_COMPOSITION_DESCRIPTOR_VERSION,
        "environment": environment,
        "data_plane": plane,
        "code_commit": settings.code_commit,
        "runtime_resolution": runtime_resolution,
        "extension_adapter": extension_adapter.document,
        "http_context_policy": http_policy.safe_reference,
        "planning_artifacts": {
            "planning_policy": catalog.planning_policy_reference,
            "solve_limits": catalog.solve_limits_reference,
        },
        "port_bindings": port_bindings,
        "secret_policy": {
            "source": "EXPLICIT_SETTINGS_OR_PLANTNEXUS_ENV",
            "endpoint_values_in_descriptor": False,
            "document_paths_in_descriptor": False,
        },
        "production_authority": "UNAVAILABLE_EXPLICIT_PROVIDER_REQUIRED",
    }
    if configured_events:
        base["execution_event_authority"] = {
            "configuration_version": "runtime-event-bindings.v1",
            "configuration_fingerprint": canonical_fingerprint(configured_events),
            "scope_count": len(configured_events),
        }
    document = {**base, "composition_fingerprint": canonical_fingerprint(base)}
    return RuntimeCompositionDescriptor(canonical_bytes=canonical_json_bytes(document))


def _dispatch_client(settings: Settings) -> Celery:
    application = Celery(
        "plantnexus-runtime-dispatch",
        broker=settings.celery_broker_url.get_secret_value(),
        backend=settings.celery_result_backend_url.get_secret_value(),
    )
    application.conf.update(
        accept_content=["json"],
        enable_utc=True,
        result_serializer="json",
        task_default_queue="plantnexus.engineering",
        task_serializer="json",
        timezone="UTC",
    )
    return application


def _runtime_extension_adapter(
    settings: Settings,
    artifacts: Sequence[RuntimeExtensionArtifact],
) -> EmptyRuntimeExtensionAdapter | LoadedRuntimeExtensionAdapter:
    catalog_path = settings.runtime_extension_catalog_path
    if catalog_path is None:
        if artifacts:
            _fail(
                "EXTENSION_CATALOG_INVALID",
                field="runtime_extension_artifacts",
                message="Extension artifacts require an explicit startup catalog",
            )
        return EmptyRuntimeExtensionAdapter.create()
    key_id = settings.runtime_extension_verification_key_id
    key = settings.runtime_extension_verification_key
    if key_id is None or key is None:
        _fail(
            "EXTENSION_ARTIFACT_SIGNATURE_INVALID",
            field="runtime_extension_verification",
            message="Extension verification configuration is incomplete",
        )
    from app.extensions.loader import load_runtime_extensions

    try:
        return load_runtime_extensions(
            catalog_path,
            artifacts=artifacts,
            runtime_version=RUNTIME_VERSION,
            verification_key_id=key_id,
            verification_key=key.get_secret_value().encode("utf-8"),
        )
    except RuntimeExtensionError as error:
        raise RuntimeCompositionError(
            error.code,
            field="runtime_extension",
            message="Runtime Extension startup preflight failed",
        ) from error
    except Exception as error:  # noqa: BLE001 - never expose provider internals
        raise RuntimeCompositionError(
            "EXTENSION_STARTUP_FAILED",
            field="runtime_extension",
            message="Runtime Extension startup preflight failed",
        ) from error


def compose_runtime(
    settings: Settings,
    *,
    process: RuntimeProcess,
    clock: RuntimeClock = utc_now,
    identity_factory: RuntimeIdentityFactory | None = None,
    dispatch_client: Celery | None = None,
    extension_artifacts: Sequence[RuntimeExtensionArtifact] = (),
) -> RuntimeComposition:
    """Build one process graph after all fail-closed checks pass."""

    if not settings.runtime_composition_enabled:
        _fail(
            "RUNTIME_COMPOSITION_DISABLED",
            field="runtime_composition_enabled",
            message="Headless Runtime composition is not explicitly enabled",
        )
    plane = _workspace_plane(settings)
    environment = _runtime_environment(settings)
    if plane is WorkspaceDataPlane.PRODUCTION:
        _fail(
            "PRODUCTION_RUNTIME_UNAVAILABLE",
            field="production_authority",
            message="Production identity and deployment providers are not available in P8-06",
        )
    contract = _schema_contract(settings)
    policy = _configured_document(
        settings.runtime_planning_policy_path,
        field="runtime_planning_policy_path",
    )
    limits = _configured_document(
        settings.runtime_solve_limits_path,
        field="runtime_solve_limits_path",
    )
    http_policy_document = _configured_document(
        settings.runtime_http_policy_path,
        field="runtime_http_policy_path",
    )
    try:
        catalog = FrozenPlanningArtifactCatalog.create(
            planning_policy=policy,
            solve_limits=limits,
            data_plane=plane.value,
        )
    except ValueError as error:
        raise RuntimeCompositionError(
            "CONFIGURATION_INVALID",
            field="runtime_planning_artifacts",
            message="Runtime planning artifacts are incompatible",
        ) from error
    extension_adapter = _runtime_extension_adapter(settings, extension_artifacts)
    try:
        http_policy = RuntimeHttpPolicyCatalog.create(
            http_policy_document,
            planning_inputs={
                "planning_policy": catalog.planning_policy_reference,
                "solve_limits": catalog.solve_limits_reference,
            },
        )
    except ValueError as error:
        raise RuntimeCompositionError(
            "CONFIGURATION_INVALID",
            field="runtime_http_policy",
            message="Runtime HTTP context policy is incompatible",
        ) from error
    try:
        configured_events = event_bindings(
            _configured_document(
                settings.runtime_event_bindings_path,
                field="runtime_event_bindings_path",
            )
            if settings.runtime_event_bindings_path is not None
            else None
        )
        for event_binding in configured_events:
            http_policy.extension_facts_for(
                **{
                    key: event_binding[key]
                    for key in ("tenant_id", "factory_id", "planning_scope_id")
                }
            )
    except (KeyError, ValueError) as error:
        raise RuntimeCompositionError(
            "CONFIGURATION_INVALID",
            field="runtime_event_bindings",
            message="Event authority configuration is invalid",
        ) from error
    descriptor = _descriptor(
        settings=settings,
        contract=contract,
        catalog=catalog,
        extension_adapter=extension_adapter,
        http_policy=http_policy,
        configured_events=configured_events,
    )
    extension_product_executor = RuntimeExtensionProductExecutor(
        adapter=extension_adapter,
        policy=http_policy,
    )

    database = create_database_client(
        settings.database_url,
        timeout_seconds=settings.readiness_timeout_seconds,
    )
    redis: RedisClient | None = None
    try:
        ingress_repository = SqlAlchemyCanonicalIngressRepository(
            database.engine, data_plane=plane
        )
        planning_run_repository = SqlAlchemyPlanningRunRepository(
            database.engine, data_plane=plane
        )
        workspace_results = SqlAlchemyPlanningRunWorkerRepository(
            database.engine, data_plane=plane
        )

        def workspace_ingress(run_id: str) -> Any:
            record = ingress_repository.get_by_planning_run_id(run_id)
            if record is None:
                raise RuntimePlanningWorkspaceError(
                    "MIXED_LINEAGE", field="source.ingress"
                )
            scope = record.document["effective_scope"]
            try:
                http_policy.extension_facts_for(
                    tenant_id=scope["tenant_id"],
                    factory_id=scope["factory_id"],
                    planning_scope_id=scope["planning_scope_id"],
                )
            except (KeyError, ValueError) as error:
                raise RuntimePlanningWorkspaceError(
                    "AUTHORIZATION_DENIED", field="source.scope"
                ) from error
            return record

        def workspace_sources(
            run_id: str, version: Mapping[str, object] | None
        ) -> WorkspaceSourceDocuments:
            record = workspace_ingress(run_id)
            if version is not None:
                if version.get("schedule_version_version") != "schedule-version.v1":
                    raise RuntimePlanningWorkspaceError(
                        "MIXED_LINEAGE", field="source.schedule_version_version"
                    )
                lineage = cast(Any, version["lineage"])
                result = workspace_results.get_result_for_solution(
                    run_id, lineage["planning_solution"]["fingerprint"]
                )
            else:
                result = workspace_results.get_latest_result_for_run(run_id)
            if result is None or result.document["outcome_state"] != "COMPLETED":
                raise RuntimePlanningWorkspaceError(
                    "MIXED_LINEAGE", field="source.worker_result"
                )
            if (
                result.document["runtime_resolution_fingerprint"]
                != record.document["runtime_resolution"]["resolution_fingerprint"]
            ):
                raise RuntimePlanningWorkspaceError(
                    "MIXED_LINEAGE", field="source.runtime_resolution"
                )
            documents = result.document["documents"]
            sources = WorkspaceSourceDocuments(
                snapshot=record.snapshot.document,
                problem=record.problem.document,
                solution=documents["planning_solution"],
                solver_report=documents["solver_report"],
                validation_report=documents["validation_report"],
                kpi=documents["kpi"],
                import_quality_report=record.document["import_quality_report"],
            )
            if version is not None:
                bind_workspace_sources(
                    version, sources, expected_data_plane=plane.value
                )
            return sources

        orchestration = PlanningRunOrchestrationService(
            schemas=FrozenSchemaCatalog.from_directory(
                settings.runtime_schema_directory.resolve(strict=True)
            ),
            repository=planning_run_repository,
        )
        binding = RuntimeApplicationBinding.create(
            data_plane=plane.value,
            environment=environment,
            code_commit=settings.code_commit,
            runtime_resolution=descriptor.runtime_resolution,
            production_available=False,
        )
        http_context_adapter = RuntimeHttpContextAdapter(
            binding=binding,
            policy=http_policy,
        )
        event_repository = SqlAlchemyExecutionEventRepository(
            database.engine, data_plane=plane
        )
        event_checkpoints = SqlAlchemyProjectionCheckpointRepository(
            database.engine, data_plane=plane
        )
        event_audits = SqlAlchemyReplanAuditRepository(
            database.engine, data_plane=plane
        )
        event_snapshots = SqlAlchemySnapshotRepository(
            database.engine, data_plane=SnapshotDataPlane.SIMULATION
        )

        def event_source(event_binding: dict[str, Any], run_id: str) -> Any:
            record = ingress_repository.get_by_planning_run_id(run_id)
            if record is None:
                raise RuntimeEventError("NOT_FOUND", "canonical_ingress")
            expected_scope = {
                key: event_binding[key]
                for key in ("tenant_id", "factory_id", "planning_scope_id")
            }
            actual = record.document["effective_scope"]
            if (
                any(actual.get(k) != v for k, v in expected_scope.items())
                or actual["environment"] != environment
            ):
                raise RuntimeEventError(
                    "AUTHORIZATION_DENIED", "canonical_ingress.scope"
                )
            http_policy.extension_facts_for(**expected_scope)
            return record

        def event_service(
            event_binding: dict[str, Any],
            key_reference: str | None,
        ) -> ExecutionFactProjectionService:
            def checkpoint_factory(**values: Any) -> Any:
                fact = ArtifactReference(
                    document_version=values.pop("fact_document_version"),
                    artifact_id=values.pop("fact_artifact_id"),
                    fingerprint=values.pop("fact_fingerprint"),
                )
                return ProjectionCheckpoint(**values, fact_checkpoint=fact)

            def audit_factory(**values: Any) -> Any:
                if (
                    values["action"] == "EXECUTION_EVENT_APPENDED"
                    and key_reference is not None
                ):
                    values["idempotency_scope"] = (
                        "SIMULATION/EXECUTION_EVENT_APPEND/"
                        + "/".join(
                            event_binding[k]
                            for k in (
                                "factory_id",
                                "planning_scope_id",
                                "authority_id",
                                "stream_id",
                                "stream_version",
                            )
                        )
                        + "/HTTP"
                    )
                    values["idempotency_key_reference"] = key_reference
                values["action"] = ReplanAuditAction(values["action"])
                return build_replan_audit_record(**values)

            def urgent_snapshot(event_id: str, cutoff: str) -> Any:
                run_id = event_binding["urgent_import_runs"].get(event_id)
                if run_id is None:
                    raise RuntimeEventError("INVALID_REFERENCE", "urgent_import_runs")
                record = event_source(event_binding, run_id)
                payload = record.document["canonical_request"]["payload"]
                quality = record.document["import_quality_report"]
                # Durable canonical ingress has already validated the complete
                # package; rebuild through the same expansion/Snapshot owner at
                # the explicit event cutoff, never accept a private Snapshot.
                return build_planning_snapshot(
                    payload,
                    quality,
                    expand_orders(payload, quality),
                    cutoff_at_utc=cutoff,
                )

            return RuntimeExecutionFactProjectionService(
                transaction_factory=database.engine.begin,
                scope=ProjectionScope(
                    **{
                        k: event_binding[k]
                        for k in (
                            "factory_id",
                            "planning_scope_id",
                            "authority_id",
                            "stream_id",
                            "stream_version",
                        )
                    }
                ),
                events=cast(Any, event_repository),
                checkpoints=cast(Any, event_checkpoints),
                audits=cast(Any, event_audits),
                snapshots=cast(Any, event_snapshots),
                checkpoint_factory=checkpoint_factory,
                audit_factory=audit_factory,
                persistence_error_types=(
                    WorkspacePersistenceError,
                    SQLAlchemyError,
                    SnapshotError,
                ),
                urgent_resolver=urgent_snapshot,
            )

        dynamic_application = RuntimeDynamicReplanningApplication(
            bindings=configured_events,
            environment=environment,
            events=event_repository,
            checkpoints=event_checkpoints,
            snapshots=event_snapshots,
            source=event_source,
            service=event_service,
        )
        runtime_exports = None
        if settings.runtime_export_storage_root is not None:
            export_schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=plane
            )
            export_audits = SqlAlchemyAuditRepository(database.engine, data_plane=plane)
            export_jobs = SqlAlchemyExportJobRepository(
                database.engine, data_plane=plane
            )
            runtime_exports = RuntimeExports(
                service=ExportJobService(
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, export_schedules),
                    export_job_repository=cast(Any, export_jobs),
                    audit_repository=cast(Any, export_audits),
                ),
                jobs=export_jobs,
                schedules=export_schedules,
                publications=SqlAlchemyPublicationRepository(
                    database.engine, data_plane=plane
                ),
                sources=workspace_sources,
                root=settings.runtime_export_storage_root,
                scenario_directory=settings.runtime_export_scenario_directory,
                clock=clock,
                code_commit=settings.code_commit,
                lease_seconds=settings.job_lease_seconds,
                publisher=(dispatch_client or _dispatch_client(settings))
                if process is RuntimeProcess.API
                else None,
            )
        if process is RuntimeProcess.API:

            def workspace_download(result: Any) -> Any:
                from app.api.contracts import PlanningWorkspaceDownload

                return PlanningWorkspaceDownload(
                    **{
                        field: getattr(result, field)
                        for field in (
                            "content",
                            "filename",
                            "media_type",
                            "package_id",
                            "manifest_fingerprint",
                            "archive_fingerprint",
                            "completion_audit_event_id",
                            "correlation_id",
                        )
                    }
                )

            redis = create_redis_client(
                settings.redis_url,
                timeout_seconds=settings.readiness_timeout_seconds,
            )
            publisher = dispatch_client or _dispatch_client(settings)
            application = APSRuntimeApplicationFacade(
                binding=binding,
                ingress=CanonicalIngressApplicationService(
                    contract=contract,
                    repository=ingress_repository,
                ),
                ingress_repository=ingress_repository,
                planning_runs=orchestration,
                dispatcher=CeleryPlanningRunDispatcher(
                    publisher,
                    identity_factory=identity_factory,
                ),
            )
            schedule_repository = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=plane
            )
            audit_repository = SqlAlchemyAuditRepository(
                database.engine, data_plane=plane
            )
            publication_repository = SqlAlchemyPublicationRepository(
                database.engine, data_plane=plane
            )
            export_repository = SqlAlchemyExportJobRepository(
                database.engine, data_plane=plane
            )

            def manual_binding(
                source: Mapping[str, object],
            ) -> tuple[Mapping[str, object], ScheduleCommandService]:
                lineage = source.get("lineage")
                if not isinstance(lineage, Mapping) or not isinstance(
                    lineage.get("planning_run_id"), str
                ):
                    raise RuntimePlanningWorkspaceError(
                        "MIXED_LINEAGE", field="source.lineage"
                    )
                run_id = lineage["planning_run_id"]
                record = ingress_repository.get_by_planning_run_id(run_id)
                reference = lineage.get("problem")
                if (
                    record is None
                    or not isinstance(reference, Mapping)
                    or reference.get("fingerprint") != record.problem.problem_hash
                ):
                    raise RuntimePlanningWorkspaceError(
                        "MIXED_LINEAGE", field="source.lineage.problem"
                    )
                scope = cast(Mapping[str, object], record.document["effective_scope"])
                if (
                    record.document.get("runtime_resolution")
                    != descriptor.runtime_resolution
                ):
                    raise RuntimePlanningWorkspaceError(
                        "STALE_SOURCE", field="source.runtime_resolution"
                    )
                try:
                    http_policy.extension_facts_for(
                        tenant_id=cast(str, scope["tenant_id"]),
                        factory_id=cast(str, scope["factory_id"]),
                        planning_scope_id=cast(str, scope["planning_scope_id"]),
                    )
                except (KeyError, ValueError) as error:
                    raise RuntimePlanningWorkspaceError(
                        "AUTHORIZATION_DENIED", field="source.scope"
                    ) from error
                admission = extension_product_executor.candidate_admission(
                    scope=scope,
                    planning_run_id=run_id,
                    runtime_identity=lambda: descriptor.runtime_resolution,
                )
                return record.problem.document, ScheduleCommandService(
                    data_plane=plane.value,
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, schedule_repository),
                    audit_repository=cast(Any, audit_repository),
                    validator_factory=ProblemScheduleValidator,
                    admission=admission,
                )

            planning_workspace_application = RuntimePlanningWorkspaceApplication(
                data_plane=plane.value,
                schedule_repository=schedule_repository,
                publication_repository=publication_repository,
                export_job_repository=export_repository,
                manual_binding=manual_binding,
                exports=runtime_exports,
                download_adapter=workspace_download,
                reads=RuntimeWorkspaceReads(
                    queries=WorkspaceQueryService(
                        data_plane=plane.value,
                        schedule_repository=schedule_repository,
                        audit_repository=audit_repository,
                    ),
                    comparisons=ScheduleComparisonService(
                        data_plane=plane.value, schedule_repository=schedule_repository
                    ),
                    schedules=schedule_repository,
                    sources=workspace_sources,
                    run_ids=ingress_repository.list_planning_run_ids,
                    read_run=planning_run_repository.get,
                    read_ingress=workspace_ingress,
                ),
                approval_service=ApprovalDecisionService(
                    data_plane=plane.value,
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, schedule_repository),
                    audit_repository=cast(Any, audit_repository),
                ),
                publication_service=PublicationService(
                    data_plane=plane.value,
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, schedule_repository),
                    audit_repository=cast(Any, audit_repository),
                    publication_repository=cast(Any, publication_repository),
                ),
                export_service=ExportJobService(
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, schedule_repository),
                    export_job_repository=cast(Any, export_repository),
                    audit_repository=cast(Any, audit_repository),
                ),
            )
            worker = None
        else:
            application = None
            planning_workspace_application = None
            worker = PlanningRunSolverWorker(
                orchestration=orchestration,
                worker_repository=SqlAlchemyPlanningRunWorkerRepository(
                    database.engine, data_plane=plane
                ),
                input_resolver=RepositoryPlanningInputResolver(
                    ingress_repository=ingress_repository,
                    catalog=catalog,
                ),
                runtime_provider=_DescriptorRuntimeProvider(descriptor),
                context_provider=RepositoryPlanningRunContextProvider(
                    repository=planning_run_repository,
                    environment=environment,
                    code_commit=settings.code_commit,
                ),
                solver=cast(Any, GlobalCpSatStrategy()),
                validator=ProblemScheduleValidator(),
                publisher=ValidatedSolutionToScheduleVersionService(
                    data_plane=plane.value,
                    transaction_factory=database.engine.begin,
                    schedule_repository=SqlAlchemyScheduleVersionRepository(
                        database.engine, data_plane=plane
                    ),
                    audit_repository=SqlAlchemyAuditRepository(
                        database.engine, data_plane=plane
                    ),
                ),
                extension_executor=extension_product_executor,
                policy=WorkerReliabilityPolicy(
                    heartbeat_seconds=settings.job_heartbeat_seconds,
                    lease_seconds=settings.job_lease_seconds,
                ),
                clock=clock,
            )
        return RuntimeComposition(
            process=process,
            descriptor=descriptor,
            extension_adapter=extension_adapter,
            application=application,
            planning_workspace_application=planning_workspace_application,
            http_context_adapter=http_context_adapter,
            extension_product_executor=extension_product_executor,
            worker=worker,
            database=database,
            redis=redis,
            export_worker=runtime_exports,
            dynamic_replanning_application=dynamic_application,
        )
    except Exception:
        if redis is not None:
            redis.close()
        database.close()
        raise


__all__ = [
    "DataPlane",
    "EMPTY_EXTENSION_ADAPTER_VERSION",
    "EmptyRuntimeExtensionAdapter",
    "RUNTIME_COMPOSITION_DESCRIPTOR_VERSION",
    "RuntimeComposition",
    "RuntimeCompositionDescriptor",
    "RuntimeCompositionError",
    "RuntimeEnvironment",
    "RuntimeExtensionArtifact",
    "RuntimeProcess",
    "Settings",
    "compose_runtime",
]
