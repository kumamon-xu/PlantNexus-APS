"""Single explicit composition root for the Headless APS Runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from celery import Celery

from app import CODE_VERSION
from app.application.canonical_ingress import CanonicalIngressApplicationService
from app.application.planning_runs import PlanningRunOrchestrationService
from app.application.runtime_facade import (
    APSRuntimeApplicationFacade,
    RuntimeApplicationBinding,
)
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
from app.infrastructure.redis_client import RedisClient, create_redis_client
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.jobs.planning_run_solver_worker import (
    PlanningRunSolverWorker,
    WorkerReliabilityPolicy,
    utc_now,
)
from app.jobs.planning_run_task import CeleryPlanningRunDispatcher
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


def _fail(code: str, *, field: str, message: str) -> None:
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
    application: APSRuntimeApplicationFacade | None
    worker: PlanningRunSolverWorker | None
    database: DatabaseClient
    redis: RedisClient | None

    @property
    def probes(self) -> Mapping[str, Callable[[], None]]:
        values: dict[str, Callable[[], None]] = {"database": self.database.probe}
        if self.redis is not None:
            values["redis"] = self.redis.probe
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
            "version": CODE_VERSION,
            "code_commit": settings.code_commit,
        }
    )


def _descriptor(
    *,
    settings: Settings,
    contract: CanonicalIngressContract,
    catalog: FrozenPlanningArtifactCatalog,
    extension_adapter: EmptyRuntimeExtensionAdapter,
) -> RuntimeCompositionDescriptor:
    plane = _workspace_plane(settings).value
    environment = _runtime_environment(settings)
    runtime_resolution: JsonObject = {
        "runtime_resolution_version": RUNTIME_RESOLUTION_VERSION,
        "runtime_version": CODE_VERSION,
        "runtime_artifact_fingerprint": _component_fingerprint(
            settings.runtime_artifact_fingerprint,
            component="aps-runtime",
            settings=settings,
        ),
        "core_version": CODE_VERSION,
        "core_artifact_fingerprint": _component_fingerprint(
            settings.core_artifact_fingerprint,
            component="aps-core",
            settings=settings,
        ),
        "extension_sdk_version": UNPUBLISHED_EXTENSION_SDK_VERSION,
        "registry_protocol_version": "plugin-registry.v1",
        "extension_set": extension_adapter.extension_set_reference,
        "developer_kit_version": UNPUBLISHED_DEVELOPER_KIT_VERSION,
        "developer_kit_fingerprint": _component_fingerprint(
            settings.developer_kit_fingerprint,
            component="aps-developer-kit-unpublished",
            settings=settings,
        ),
        "solver_backend_id": STRATEGY_ID,
        "solver_backend_version": CODE_VERSION,
        "validator_version": CODE_VERSION,
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

    base: JsonObject = {
        "composition_descriptor_version": RUNTIME_COMPOSITION_DESCRIPTOR_VERSION,
        "environment": environment,
        "data_plane": plane,
        "code_commit": settings.code_commit,
        "runtime_resolution": runtime_resolution,
        "extension_adapter": extension_adapter.document,
        "planning_artifacts": {
            "planning_policy": catalog.planning_policy_reference,
            "solve_limits": catalog.solve_limits_reference,
        },
        "port_bindings": {
            "canonical_ingress_repository": "sqlalchemy-canonical-ingress.v1",
            "planning_run_repository": "sqlalchemy-planning-run.v1",
            "worker_repository": "sqlalchemy-planning-run-worker.v1",
            "transaction": "sqlalchemy-engine-begin.v1",
            "clock": "utc-system-clock.v1",
            "identity": "uuid4-dispatch-identity.v1",
            "solver": f"{STRATEGY_ID}/{STRATEGY_VERSION}",
            "validator": f"problem-schedule-validator/{VALIDATION_REPORT_CONTRACT}",
            "audit": "sqlalchemy-append-only-audit.v1",
        },
        "secret_policy": {
            "source": "EXPLICIT_SETTINGS_OR_PLANTNEXUS_ENV",
            "endpoint_values_in_descriptor": False,
            "document_paths_in_descriptor": False,
        },
        "production_authority": "UNAVAILABLE_UNTIL_P8_08_TO_P8_10",
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


def compose_runtime(
    settings: Settings,
    *,
    process: RuntimeProcess,
    clock: RuntimeClock = utc_now,
    identity_factory: RuntimeIdentityFactory | None = None,
    dispatch_client: Celery | None = None,
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
    extension_adapter = EmptyRuntimeExtensionAdapter.create()
    descriptor = _descriptor(
        settings=settings,
        contract=contract,
        catalog=catalog,
        extension_adapter=extension_adapter,
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
        if process is RuntimeProcess.API:
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
            worker = None
        else:
            application = None
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
                policy=WorkerReliabilityPolicy(
                    heartbeat_seconds=settings.job_heartbeat_seconds,
                    lease_seconds=settings.job_lease_seconds,
                ),
                clock=clock,
            )
        return RuntimeComposition(
            process=process,
            descriptor=descriptor,
            application=application,
            worker=worker,
            database=database,
            redis=redis,
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
    "RuntimeProcess",
    "Settings",
    "compose_runtime",
]
