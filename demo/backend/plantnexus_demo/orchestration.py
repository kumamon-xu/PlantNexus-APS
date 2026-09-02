"""Demo orchestration over the repository's formal planning lifecycles."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, ContextManager, cast

from app.application.approval import ApprovalDecisionService
from app.application.publication import PublicationService
from app.application.schedule_versions import ValidatedSolutionToScheduleVersionService
from app.domain.authorization import ApprovalDecisionContext
from app.domain.publication import PublicationContext
from app.domain.schedule_version import (
    ScheduleVersionCreationContext,
    ValidatedPlanningOutput,
)
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.importers import StagingDataPlane
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.import_staging_repository import (
    SqlAlchemyImportStagingRepository,
)
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.planning.policy.delivery import (
    simulation_delivery_policy,
    simulation_solve_limits,
)
from app.planning.reporting.kpi import build_kpi_v2
from app.planning.strategies.global_cp_sat import GlobalCpSatStrategy
from app.planning.validation.problem_schedule_validator import (
    validate_problem_schedule,
)
from app.snapshots import SnapshotDataPlane

from .generator import DemoPackageGenerator, source_record_counts
from .ingress import DemoIngressPipeline, problem_counts
from .persistence import (
    ControlStore,
    DemoPersistenceError,
    DemoRuntimePaths,
    RunDatabase,
    artifact_version,
    canonical_bytes,
    fingerprint,
    prune_inactive_runs,
    require_artifact_set,
    utc_now,
)
from .security import DEMO_ACTOR_REF, DEMO_AUTH_POLICY_VERSION


INITIAL_ARTIFACT_KINDS = (
    "IMPORT_QUALITY",
    "SNAPSHOT",
    "PLANNING_PROBLEM",
    "PLANNING_SOLUTION",
    "SOLVER_REPORT",
    "VALIDATION_REPORT",
    "KPI",
)
_SAFE_ARTIFACT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class DemoOperationError(RuntimeError):
    """Sanitized, stable failure consumed by jobs and HTTP adapters."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code}: {field}: {message}")


class StageSink:
    """Small context boundary so orchestration records only real stages."""

    def stage(self, name: str) -> ContextManager[None]:
        del name
        return nullcontext()


class ControlJobStageSink(StageSink):
    def __init__(self, control: ControlStore, job_id: str) -> None:
        self._control = control
        self._job_id = job_id
        self._sequence = 0

    @contextmanager
    def stage(self, name: str) -> Any:
        self._sequence += 1
        sequence = self._sequence
        self._control.start_stage(self._job_id, sequence=sequence, stage=name)
        try:
            yield
        except BaseException:
            raise
        else:
            self._control.finish_stage(self._job_id, sequence=sequence)


def _artifact_id(kind: str, document: Mapping[str, object]) -> str:
    preferred_fields = {
        "IMPORT_QUALITY": ("report_id",),
        "SNAPSHOT": ("snapshot_id",),
        "PLANNING_PROBLEM": ("problem_id",),
        "PLANNING_SOLUTION": ("solution_id",),
        "SOLVER_REPORT": ("report_id",),
        "VALIDATION_REPORT": ("validation_report_id",),
        "KPI": ("kpi_id",),
    }
    for field in preferred_fields.get(kind, ()):  # pragma: no branch - fixed map
        value = document.get(field)
        if isinstance(value, str) and _SAFE_ARTIFACT.fullmatch(value) is not None:
            return value
    return f"{kind.lower()}-{sha256(canonical_bytes(document)).hexdigest()}"


def _planning_run_id(run_id: str, request_fingerprint: str) -> str:
    digest = sha256(f"{run_id}:{request_fingerprint}".encode("utf-8")).hexdigest()
    return f"planning-run-demo-{digest}"


def _open_run_database(
    *, repository_root: Path, paths: DemoRuntimePaths, control: ControlStore, run_id: str
) -> RunDatabase:
    record = control.get_run(run_id)
    if record is None:
        raise DemoOperationError(
            "DEMO_NOT_INITIALIZED", field="run_id", message="run does not exist"
        )
    return RunDatabase(
        repository_root=repository_root,
        database_path=paths.resolve_relative_database(record.database_relative_path),
    )


@dataclass(frozen=True, slots=True)
class ResetResult:
    run_id: str
    scenario_id: str
    profile_name: str
    seed: int
    snapshot_id: str
    problem_hash: str
    active_run_id: str
    pruned_run_ids: tuple[str, ...]

    @property
    def document(self) -> dict[str, object]:
        return {
            "result_version": "cnc-demo-reset-result.v1",
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "profile_name": self.profile_name,
            "seed": self.seed,
            "snapshot_id": self.snapshot_id,
            "problem_hash": self.problem_hash,
            "active_run_id": self.active_run_id,
            "pruned_run_ids": list(self.pruned_run_ids),
        }


class ResetOrchestrator:
    """Create, self-check, and atomically activate one fresh run database."""

    def __init__(
        self,
        *,
        repository_root: Path,
        paths: DemoRuntimePaths,
        control: ControlStore,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.paths = paths
        self.control = control

    def execute(
        self,
        *,
        run_id: str,
        profile_name: str,
        expected_active_run_id: str | None,
        created_at_utc: str,
        stages: StageSink | None = None,
        fault_point: str | None = None,
    ) -> ResetResult:
        stage_sink = StageSink() if stages is None else stages
        generator = DemoPackageGenerator()
        profile = generator.assets.profile(profile_name)
        self.control.register_run(
            run_id=run_id,
            scenario_id=profile.profile_id,
            seed=profile.seed,
            database_relative_path=self.paths.relative_run_database(run_id),
            created_at_utc=created_at_utc,
        )
        database: RunDatabase | None = None
        try:
            with stage_sink.stage("MIGRATING"):
                if fault_point == "BEFORE_MIGRATION":
                    raise DemoOperationError(
                        "MIGRATION_FAILED",
                        field="fault_point",
                        message="injected migration failure",
                    )
                database = RunDatabase.migrate(
                    repository_root=self.repository_root,
                    database_path=self.paths.run_database(run_id),
                )
            if fault_point == "AFTER_MIGRATION":
                raise DemoOperationError(
                    "RESET_FAILED",
                    field="fault_point",
                    message="injected post-migration failure",
                )
            with stage_sink.stage("GENERATING"):
                if fault_point == "BEFORE_GENERATION":
                    raise DemoOperationError(
                        "GENERATION_FAILED",
                        field="fault_point",
                        message="injected generation failure",
                    )
                generated = generator.prepare_batch(profile_name)
            with stage_sink.stage("STAGING"):
                staging = SqlAlchemyImportStagingRepository(
                    database.engine, data_plane=StagingDataPlane.SIMULATION
                )
                staging.stage(generated.batch)
            ingress = DemoIngressPipeline().run(
                generated, stage_context=stage_sink.stage
            )
            with stage_sink.stage("PERSISTING_IMPORT"):
                snapshots = SqlAlchemySnapshotRepository(
                    database.engine, data_plane=SnapshotDataPlane.SIMULATION
                )
                snapshots.put(ingress.snapshot)
                quality_document = cast(Mapping[str, object], ingress.quality.document)
                snapshot_document = cast(Mapping[str, object], ingress.snapshot.document)
                problem_document = cast(Mapping[str, object], ingress.problem.document)
                for kind, document in (
                    ("IMPORT_QUALITY", quality_document),
                    ("SNAPSHOT", snapshot_document),
                    ("PLANNING_PROBLEM", problem_document),
                ):
                    database.put_artifact(
                        artifact_kind=kind,
                        artifact_id=_artifact_id(kind, document),
                        document_version=artifact_version(document),
                        document=document,
                    )
                manifest = {
                    "manifest_version": "cnc-demo-scenario-manifest.v1",
                    "run_id": run_id,
                    "scenario_id": profile.profile_id,
                    "scenario_version": profile.scenario_version,
                    "profile_name": profile_name,
                    "seed": profile.seed,
                    "assets_digest": generated.assets_digest,
                    "batch_id": generated.batch.batch_id,
                    "batch_request_fingerprint": generated.batch.request_fingerprint,
                    "dataset_hash": ingress.normalization.dataset_hash,
                    "snapshot_id": ingress.snapshot.snapshot_id,
                    "snapshot_hash": ingress.snapshot.snapshot_hash,
                    "problem_hash": ingress.problem.problem_hash,
                    "source_counts": source_record_counts(generated),
                    "problem_counts": problem_counts(ingress),
                    "tick_seconds": ingress.problem.document["tick_seconds"],
                    "horizon_start_utc": ingress.problem.document["horizon_start_utc"],
                    "horizon_end_utc": ingress.problem.document["horizon_end_utc"],
                    "initial_solve_seconds": profile.initial_solve_seconds,
                    "replan_solve_seconds": profile.replan_solve_seconds,
                    "created_at_utc": created_at_utc,
                }
                database.put_manifest(manifest)
            with stage_sink.stage("SELF_CHECKING"):
                database.self_check()
                stored_batch = staging.get(generated.batch.batch_id)
                stored_snapshot = snapshots.get_by_id(ingress.snapshot.snapshot_id)
                if stored_batch != generated.batch or stored_snapshot != ingress.snapshot:
                    raise DemoOperationError(
                        "PERSISTENCE_FAILED",
                        field="reset.self_check",
                        message="run database round-trip verification failed",
                    )
            with stage_sink.stage("SWITCHING_ACTIVE_RUN"):
                if fault_point == "BEFORE_SWITCH":
                    raise DemoOperationError(
                        "RESET_FAILED",
                        field="fault_point",
                        message="injected pre-switch failure",
                    )
                activated = self.control.activate_run(
                    run_id=run_id,
                    expected_active_run_id=expected_active_run_id,
                )
            pruned = prune_inactive_runs(
                control=self.control, paths=self.paths, retain=3
            )
            return ResetResult(
                run_id=run_id,
                scenario_id=profile.profile_id,
                profile_name=profile_name,
                seed=profile.seed,
                snapshot_id=ingress.snapshot.snapshot_id,
                problem_hash=ingress.problem.problem_hash,
                active_run_id=activated.run_id,
                pruned_run_ids=pruned,
            )
        except (DemoOperationError, DemoPersistenceError):
            self.control.mark_run_failed(run_id)
            raise
        except Exception as error:  # noqa: BLE001 - sanitize component failures
            self.control.mark_run_failed(run_id)
            raise DemoOperationError(
                "RESET_FAILED",
                field="reset",
                message="Demo reset failed before active-run switch",
            ) from error
        finally:
            if database is not None:
                database.close()


@dataclass(frozen=True, slots=True)
class InitialPlanningResult:
    run_id: str
    planning_run_id: str
    schedule_version_id: str
    schedule_state: str
    state_revision: int
    content_fingerprint: str
    solver_status: str
    validation_status: str
    exact_replay: bool

    @property
    def document(self) -> dict[str, object]:
        return {
            "result_version": "cnc-demo-initial-planning-result.v1",
            "run_id": self.run_id,
            "planning_run_id": self.planning_run_id,
            "schedule_version_id": self.schedule_version_id,
            "schedule_state": self.schedule_state,
            "state_revision": self.state_revision,
            "content_fingerprint": self.content_fingerprint,
            "solver_status": self.solver_status,
            "validation_status": self.validation_status,
            "exact_replay": self.exact_replay,
        }


class InitialPlanningOrchestrator:
    """Run v2 global CP-SAT and commit only fresh Validator-PASS output."""

    def __init__(
        self,
        *,
        repository_root: Path,
        paths: DemoRuntimePaths,
        control: ControlStore,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.paths = paths
        self.control = control

    def execute(
        self,
        *,
        run_id: str,
        request_fingerprint: str,
        idempotency_key_reference: str,
        correlation_id: str,
        occurred_at_utc: str,
        stages: StageSink | None = None,
        validation_override: Mapping[str, object] | None = None,
    ) -> InitialPlanningResult:
        active = self.control.active_run()
        if active is None:
            raise DemoOperationError(
                "DEMO_NOT_INITIALIZED", field="run_id", message="no active Demo run"
            )
        if active.run_id != run_id:
            raise DemoOperationError(
                "STALE_RUN", field="expected_run_id", message="active Demo run changed"
            )
        stage_sink = StageSink() if stages is None else stages
        database = _open_run_database(
            repository_root=self.repository_root,
            paths=self.paths,
            control=self.control,
            run_id=run_id,
        )
        try:
            manifest = database.get_manifest()
            if manifest is None:
                raise DemoOperationError(
                    "DEMO_NOT_INITIALIZED",
                    field="scenario_manifest",
                    message="active run has no scenario manifest",
                )
            profile_name = manifest.get("profile_name")
            if not isinstance(profile_name, str):
                raise DemoOperationError(
                    "PERSISTENCE_FAILED",
                    field="scenario_manifest.profile_name",
                    message="scenario manifest is invalid",
                )
            with stage_sink.stage("GENERATING"):
                generated = DemoPackageGenerator().prepare_batch(profile_name)
            with stage_sink.stage("STAGING"):
                SqlAlchemyImportStagingRepository(
                    database.engine, data_plane=StagingDataPlane.SIMULATION
                ).stage(generated.batch)
            ingress = DemoIngressPipeline().run(
                generated, stage_context=stage_sink.stage
            )
            with stage_sink.stage("PERSISTING_SNAPSHOT"):
                SqlAlchemySnapshotRepository(
                    database.engine, data_plane=SnapshotDataPlane.SIMULATION
                ).put(ingress.snapshot)
            planning_run_id = _planning_run_id(run_id, request_fingerprint)
            limits = simulation_solve_limits(
                limits_id=f"CNC-DEMO-LIMITS-{profile_name.upper()}",
                limits_revision="1.0.0",
                source_record_id=f"cnc-demo-limits-{profile_name}",
                max_wall_time_seconds=float(generated.profile.initial_solve_seconds),
                max_workers=1,
                random_seed=generated.profile.seed,
            )
            with stage_sink.stage("SOLVING"):
                result = GlobalCpSatStrategy().solve(
                    ingress.problem.document,
                    simulation_delivery_policy(),
                    limits,
                    planning_run_id=planning_run_id,
                    code_commit="uncommitted",
                )
            solver_status = str(result.solution["solver_status"])
            if solver_status == "INFEASIBLE":
                raise DemoOperationError(
                    "SOLVER_INFEASIBLE",
                    field="solver_status",
                    message="solver proved the synthetic instance infeasible",
                )
            if solver_status not in {"OPTIMAL", "FEASIBLE"}:
                raise DemoOperationError(
                    "SOLVER_NO_CANDIDATE",
                    field="solver_status",
                    message="solver returned no candidate within the configured limit",
                )
            with stage_sink.stage("VERIFYING_SOLUTION"):
                fresh_validation = validate_problem_schedule(
                    ingress.problem.document, result.solution
                )
                if validation_override is not None:
                    fresh_validation = cast(Any, dict(validation_override))
                if (
                    fresh_validation["status"] != "PASS"
                    or fresh_validation["hard_violation_count"] != 0
                    or result.validation_report != fresh_validation
                ):
                    raise DemoOperationError(
                        "SOLUTION_VALIDATION_FAILED",
                        field="validation_report",
                        message="fresh independent validation did not match a passing candidate",
                    )
                kpi = build_kpi_v2(
                    snapshot=ingress.snapshot.document,
                    problem=ingress.problem.document,
                    solution=result.solution,
                    solver_report=result.solver_report,
                    validation_report=fresh_validation,
                    import_quality_report=ingress.quality.document,
                )
            output = ValidatedPlanningOutput(
                snapshot=ingress.snapshot.document,
                problem=ingress.problem.document,
                solution=result.solution,
                solver_report=result.solver_report,
                validation_report=fresh_validation,
                import_quality_report=ingress.quality.document,
                kpi=kpi.document,
            )
            plane = WorkspaceDataPlane.SIMULATION
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=plane
            )
            audits = SqlAlchemyAuditRepository(database.engine, data_plane=plane)
            lifecycle = ValidatedSolutionToScheduleVersionService(
                data_plane="SIMULATION",
                transaction_factory=database.engine.begin,
                schedule_repository=schedules,
                audit_repository=audits,
            )
            with stage_sink.stage("PERSISTING_VERSION"):
                created = lifecycle.create_reviewable(
                    output,
                    ScheduleVersionCreationContext(
                        planning_run_state="COMPLETED",
                        environment="TEST",
                        actor_ref=DEMO_ACTOR_REF,
                        auth_policy_version=DEMO_AUTH_POLICY_VERSION,
                        occurred_at_utc=occurred_at_utc,
                        correlation_id=correlation_id,
                        idempotency_key_reference=idempotency_key_reference,
                        reason="Create the validated CNC Demo initial plan for review.",
                    ),
                )
                documents: tuple[tuple[str, Mapping[str, object]], ...] = (
                    ("IMPORT_QUALITY", cast(Mapping[str, object], ingress.quality.document)),
                    ("SNAPSHOT", cast(Mapping[str, object], ingress.snapshot.document)),
                    ("PLANNING_PROBLEM", cast(Mapping[str, object], ingress.problem.document)),
                    ("PLANNING_SOLUTION", cast(Mapping[str, object], result.solution)),
                    ("SOLVER_REPORT", cast(Mapping[str, object], result.solver_report)),
                    ("VALIDATION_REPORT", cast(Mapping[str, object], fresh_validation)),
                    ("KPI", cast(Mapping[str, object], kpi.document)),
                )
                for kind, document in documents:
                    database.put_artifact(
                        artifact_kind=kind,
                        artifact_id=_artifact_id(kind, document),
                        document_version=artifact_version(document),
                        document=document,
                    )
                require_artifact_set(database, INITIAL_ARTIFACT_KINDS)
            schedule = created.schedule_version
            return InitialPlanningResult(
                run_id=run_id,
                planning_run_id=planning_run_id,
                schedule_version_id=created.schedule_version_id,
                schedule_state=cast(str, schedule["state"]),
                state_revision=created.state_revision,
                content_fingerprint=cast(str, schedule["content_fingerprint"]),
                solver_status=solver_status,
                validation_status=cast(str, fresh_validation["status"]),
                exact_replay=created.exact_replay,
            )
        except DemoOperationError:
            raise
        except DemoPersistenceError:
            raise
        except Exception as error:  # noqa: BLE001 - stable job failure contract
            raise DemoOperationError(
                "INITIAL_PLAN_FAILED",
                field="initial_plan",
                message="initial planning failed before a reviewable version was committed",
            ) from error
        finally:
            database.close()


def _formal_key(prefix: str, key_ref: str) -> str:
    return f"demo-{prefix}-{key_ref.removeprefix('sha256:')}"


def _approval_command(
    source: Mapping[str, object], *, key_ref: str, correlation_id: str
) -> dict[str, object]:
    key = _formal_key("approve", key_ref)
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "APPROVE",
        "required_capability": "approve",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/APPROVE/{source['schedule_version_id']}/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "READY_FOR_REVIEW",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": "Explicitly approve the reviewed CNC Demo Simulation baseline.",
        "correlation_id": correlation_id,
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _schedule_reference(source: Mapping[str, object]) -> dict[str, object]:
    return {
        "schedule_version_id": source["schedule_version_id"],
        "state": source["state"],
        "content_fingerprint": source["content_fingerprint"],
    }


def _publication_command(
    source: Mapping[str, object],
    *,
    key_ref: str,
    correlation_id: str,
    previous: Mapping[str, object] | None,
) -> dict[str, object]:
    key = _formal_key("publish", key_ref)
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "PUBLISH",
        "required_capability": "publish",
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/PUBLISH/{source['schedule_version_id']}/SIMULATION_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "APPROVED",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "SIMULATION_INTERNAL",
        "reason": "Explicitly publish the approved CNC Demo Simulation baseline.",
        "correlation_id": correlation_id,
        "payload": {
            "previous_current_version": (
                None if previous is None else dict(previous)
            )
        },
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


@dataclass(frozen=True, slots=True)
class BaselineActivationResult:
    run_id: str
    schedule_version_id: str
    content_fingerprint: str
    state: str
    state_revision: int
    publication_id: str
    current_reference_revision: int
    replayed: bool

    @property
    def document(self) -> dict[str, object]:
        return {
            "result_version": "cnc-demo-baseline-activation-result.v1",
            "run_id": self.run_id,
            "schedule_version_id": self.schedule_version_id,
            "content_fingerprint": self.content_fingerprint,
            "state": self.state,
            "state_revision": self.state_revision,
            "publication_id": self.publication_id,
            "current_reference_revision": self.current_reference_revision,
            "replayed": self.replayed,
        }


class BaselineActivationService:
    """Resume-safe APPROVE then PUBLISH; never mutates state fields directly."""

    CONFIRMATION = "ACTIVATE_SIMULATION_BASELINE"

    def __init__(
        self,
        *,
        repository_root: Path,
        paths: DemoRuntimePaths,
        control: ControlStore,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.paths = paths
        self.control = control

    def execute(
        self,
        *,
        expected_run_id: str,
        schedule_version_id: str,
        content_fingerprint: str,
        expected_state_revision: int,
        confirmation: str,
        idempotency_key_reference: str,
        correlation_id: str,
        occurred_at_utc: str | None = None,
        fail_after_approval: bool = False,
    ) -> BaselineActivationResult:
        request = {
            "command_version": "cnc-demo-baseline-activation.v1",
            "expected_run_id": expected_run_id,
            "schedule_version_id": schedule_version_id,
            "content_fingerprint": content_fingerprint,
            "expected_state_revision": expected_state_revision,
            "confirmation": confirmation,
        }
        request_fingerprint = fingerprint(request)
        claim = self.control.claim_command(
            scope="BASELINE_ACTIVATION",
            key_reference=idempotency_key_reference,
            request_fingerprint=request_fingerprint,
            created_at_utc=occurred_at_utc,
        )
        if claim.status == "SUCCEEDED" and claim.result is not None:
            result = claim.result
            return BaselineActivationResult(
                run_id=cast(str, result["run_id"]),
                schedule_version_id=cast(str, result["schedule_version_id"]),
                content_fingerprint=cast(str, result["content_fingerprint"]),
                state=cast(str, result["state"]),
                state_revision=cast(int, result["state_revision"]),
                publication_id=cast(str, result["publication_id"]),
                current_reference_revision=cast(
                    int, result["current_reference_revision"]
                ),
                replayed=True,
            )
        active_job = self.control.active_job()
        if active_job is not None:
            raise DemoOperationError(
                "ACTIVE_JOB_CONFLICT",
                field="job",
                message="baseline activation cannot run beside a mutating job",
            )
        if confirmation != self.CONFIRMATION:
            raise DemoOperationError(
                "BASELINE_CONFIRMATION_REQUIRED",
                field="confirmation",
                message="explicit Simulation baseline confirmation is required",
            )
        active = self.control.active_run()
        if active is None or active.run_id != expected_run_id:
            raise DemoOperationError(
                "STALE_RUN", field="expected_run_id", message="active Demo run changed"
            )
        database = _open_run_database(
            repository_root=self.repository_root,
            paths=self.paths,
            control=self.control,
            run_id=expected_run_id,
        )
        now = utc_now() if occurred_at_utc is None else occurred_at_utc
        try:
            plane = WorkspaceDataPlane.SIMULATION
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=plane
            )
            audits = SqlAlchemyAuditRepository(database.engine, data_plane=plane)
            publications = SqlAlchemyPublicationRepository(
                database.engine, data_plane=plane
            )
            record = schedules.get_record(schedule_version_id)
            if record is None:
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="schedule_version_id",
                    message="schedule version does not exist in the active run",
                )
            schedule = record.document
            if schedule.get("content_fingerprint") != content_fingerprint:
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="content_fingerprint",
                    message="schedule content changed or precondition is stale",
                )
            if schedule.get("state") == "READY_FOR_REVIEW":
                if record.state_revision != expected_state_revision:
                    raise DemoOperationError(
                        "BASELINE_STATE_CONFLICT",
                        field="expected_state_revision",
                        message="schedule state revision is stale",
                    )
                approval = ApprovalDecisionService(
                    data_plane="SIMULATION",
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, schedules),
                    audit_repository=cast(Any, audits),
                )
                approval_result = approval.execute(
                    _approval_command(
                        schedule,
                        key_ref=idempotency_key_reference,
                        correlation_id=correlation_id,
                    ),
                    ApprovalDecisionContext(
                        actor_ref=DEMO_ACTOR_REF,
                        authenticated=True,
                        resolved_capabilities=frozenset({"approve"}),
                        schedule_version_scope=frozenset({schedule_version_id}),
                        auth_policy_version=DEMO_AUTH_POLICY_VERSION,
                        production_binding=False,
                        occurred_at_utc=now,
                        code_commit="uncommitted",
                    ),
                )
                schedule = schedules.get(schedule_version_id)
                if schedule is None or schedule.get("state") != "APPROVED":
                    raise DemoOperationError(
                        "PERSISTENCE_FAILED",
                        field="approval",
                        message="approved schedule could not be read back",
                    )
                parent_audit_event_id = approval_result.audit_event_id
            elif schedule.get("state") == "APPROVED":
                decision = schedule.get("decision")
                parent_audit_event_id = (
                    cast(str, decision.get("audit_event_id"))
                    if isinstance(decision, Mapping)
                    and isinstance(decision.get("audit_event_id"), str)
                    else None
                )
                if parent_audit_event_id is None:
                    raise DemoOperationError(
                        "PERSISTENCE_FAILED",
                        field="schedule.decision",
                        message="approved schedule lacks decision evidence",
                    )
            elif schedule.get("state") == "PUBLISHED":
                parent_audit_event_id = None
            else:
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="schedule.state",
                    message="only READY or recoverable APPROVED can be activated",
                )
            if fail_after_approval and schedule.get("state") == "APPROVED":
                raise DemoOperationError(
                    "PUBLISH_FAILED",
                    field="fault_point",
                    message="injected failure after approval",
                )
            current = publications.get_current(target="SIMULATION_INTERNAL")
            if schedule.get("state") != "PUBLISHED":
                previous_document: Mapping[str, object] | None = None
                if current is not None:
                    previous = schedules.get(current.schedule_version_id)
                    if previous is None:
                        raise DemoOperationError(
                            "PERSISTENCE_FAILED",
                            field="publication.current",
                            message="current publication points to a missing schedule",
                        )
                    previous_document = _schedule_reference(previous)
                publication = PublicationService(
                    data_plane="SIMULATION",
                    transaction_factory=database.engine.begin,
                    schedule_repository=cast(Any, schedules),
                    audit_repository=cast(Any, audits),
                    publication_repository=cast(Any, publications),
                )
                publication.execute(
                    _publication_command(
                        schedule,
                        key_ref=idempotency_key_reference,
                        correlation_id=correlation_id,
                        previous=previous_document,
                    ),
                    PublicationContext(
                        actor_ref=DEMO_ACTOR_REF,
                        authenticated=True,
                        resolved_capabilities=frozenset({"publish"}),
                        schedule_version_scope=frozenset({schedule_version_id}),
                        auth_policy_version=DEMO_AUTH_POLICY_VERSION,
                        production_binding=False,
                        occurred_at_utc=now,
                        code_commit="uncommitted",
                        parent_audit_event_id=parent_audit_event_id,
                    ),
                )
            final_record = schedules.get_record(schedule_version_id)
            final_current = publications.get_current(target="SIMULATION_INTERNAL")
            if (
                final_record is None
                or final_record.document.get("state") != "PUBLISHED"
                or final_current is None
                or final_current.schedule_version_id != schedule_version_id
                or final_current.content_fingerprint != content_fingerprint
            ):
                raise DemoOperationError(
                    "PERSISTENCE_FAILED",
                    field="publication.current",
                    message="published schedule and current reference differ",
                )
            publication_value = final_record.document.get("publication")
            if not isinstance(publication_value, Mapping) or not isinstance(
                publication_value.get("publication_id"), str
            ):
                raise DemoOperationError(
                    "PERSISTENCE_FAILED",
                    field="schedule.publication",
                    message="published schedule lacks publication evidence",
                )
            result = BaselineActivationResult(
                run_id=expected_run_id,
                schedule_version_id=schedule_version_id,
                content_fingerprint=content_fingerprint,
                state="PUBLISHED",
                state_revision=final_record.state_revision,
                publication_id=cast(str, publication_value["publication_id"]),
                current_reference_revision=final_current.reference_revision,
                replayed=claim.replayed,
            )
            audit_id = "demo-command-baseline-" + request_fingerprint.removeprefix(
                "sha256:"
            )
            database.append_command_audit(
                audit_id=audit_id,
                command_type="BASELINE_ACTIVATION",
                request_fingerprint=request_fingerprint,
                actor_ref=DEMO_ACTOR_REF,
                correlation_id=correlation_id,
                result_reference=result.document,
                occurred_at_utc=now,
            )
            self.control.complete_command(
                scope="BASELINE_ACTIVATION",
                key_reference=idempotency_key_reference,
                request_fingerprint=request_fingerprint,
                result=result.document,
            )
            return result
        except DemoOperationError:
            raise
        except DemoPersistenceError:
            raise
        except Exception as error:  # noqa: BLE001 - stable activation failure
            raise DemoOperationError(
                "BASELINE_STATE_CONFLICT",
                field="baseline_activation",
                message="baseline activation was rejected by the formal lifecycle",
            ) from error
        finally:
            database.close()


__all__ = [
    "BaselineActivationResult",
    "BaselineActivationService",
    "ControlJobStageSink",
    "DemoOperationError",
    "INITIAL_ARTIFACT_KINDS",
    "InitialPlanningOrchestrator",
    "InitialPlanningResult",
    "ResetOrchestrator",
    "ResetResult",
    "StageSink",
]
