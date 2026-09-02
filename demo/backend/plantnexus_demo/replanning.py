"""Demo-only urgent-event projection and real dynamic-replanning orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app.application.execution_fact_projection import ExecutionFactProjectionService
from app.application.replan_application import (
    ReplanApplicationInput,
    ReplanApplicationService,
)
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    event_stream_fingerprint,
    execution_event_fingerprint,
    replan_request_fingerprint,
    require_p4_document,
)
from app.domain.execution_fact_projection import ProjectionScope
from app.domain.replan_application import (
    ReplanApplicationContext,
    ReplanApplicationError,
)
from app.importers import StagingDataPlane
from app.importers.urgent_demand import UrgentDemandImport
from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.import_staging_repository import (
    SqlAlchemyImportStagingRepository,
)
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.replan_persistence import (
    ArtifactReference,
    ProjectionCheckpoint,
    ReplanAuditAction,
    ReplanAuditRecord,
    build_replan_audit_record,
)
from app.infrastructure.replan_repository import (
    SqlAlchemyProjectionCheckpointRepository,
    SqlAlchemyReplanAuditRepository,
    SqlAlchemyReplanLineageRepository,
    SqlAlchemyReplanRequestRepository,
)
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import (
    WorkspaceDataPlane,
    WorkspacePersistenceError,
)
from app.normalization import NormalizationInput
from app.planning.policy import simulation_replan_policy
from app.planning.policy.delivery import simulation_solve_limits
from app.planning.problem import PROBLEM_BUILDER_VERSION_V2, build_planning_problem_v2
from app.planning.problem.contracts import DemandPriorityInput, ImmutablePlanningProblemV2
from app.planning.problem.freeze_projection import (
    EffectiveLockProjection,
    project_effective_locks as root_project_effective_locks,
)
from app.planning.reporting.kpi import calculate_schedule_kpi_metrics
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanResult,
    LexicographicReplanStrategy,
)
from app.snapshots import ImmutablePlanningSnapshot, SnapshotDataPlane, SnapshotError

from .generator import PRIORITY_SOURCE_SYSTEM, DemoPackageGenerator
from .ingress import DemoIngressArtifacts, DemoIngressPipeline, load_unit_registry
from .orchestration import DemoOperationError, StageSink
from .persistence import (
    ControlStore,
    DemoPersistenceError,
    DemoRuntimePaths,
    RunDatabase,
    artifact_version,
)
from .security import DEMO_ACTOR_REF
from .urgent import (
    UrgentCandidate,
    UrgentOrderCommand,
    UrgentOrderError,
    prepare_urgent_candidate,
)


SIMULATOR_ID = "PLANTNEXUS-DEMO-EXECUTION-SIMULATOR"
SIMULATOR_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class UrgentPreflight:
    run_id: str
    profile_name: str
    base_schedule: dict[str, object]
    base_snapshot: ImmutablePlanningSnapshot
    base_ingress: DemoIngressArtifacts
    candidate: UrgentCandidate
    candidate_ingress: DemoIngressArtifacts
    canonical_demand_id: str
    scope: ProjectionScope
    event: dict[str, object]


@dataclass(frozen=True, slots=True)
class UrgentReplanResult:
    run_id: str
    demand_order_id: str
    event_id: str
    snapshot_id: str
    problem_hash: str
    request_id: str
    attempt_id: str
    schedule_version_id: str
    schedule_state: str
    solver_status: str
    validation_status: str
    change_report_id: str
    added_operations: int
    changed_operations: int
    unchanged_operations: int
    current_published_version_id: str
    exact_replay: bool

    @property
    def document(self) -> dict[str, object]:
        return {
            "result_version": "cnc-demo-urgent-replan-result.v1",
            "run_id": self.run_id,
            "demand_order_id": self.demand_order_id,
            "event_id": self.event_id,
            "snapshot_id": self.snapshot_id,
            "problem_hash": self.problem_hash,
            "request_id": self.request_id,
            "attempt_id": self.attempt_id,
            "schedule_version_id": self.schedule_version_id,
            "schedule_state": self.schedule_state,
            "solver_status": self.solver_status,
            "validation_status": self.validation_status,
            "change_report_id": self.change_report_id,
            "operation_changes": {
                "ADDED": self.added_operations,
                "CHANGED": self.changed_operations,
                "UNCHANGED": self.unchanged_operations,
            },
            "current_published_version_id": self.current_published_version_id,
            "exact_replay": self.exact_replay,
        }


def _checkpoint_factory(
    *,
    factory_id: str,
    planning_scope_id: str,
    authority_id: str,
    stream_id: str,
    stream_version: str,
    last_applied_position: int,
    prefix_fingerprint: str,
    fact_document_version: str,
    fact_artifact_id: str,
    fact_fingerprint: str,
    updated_at_utc: str,
) -> ProjectionCheckpoint:
    return ProjectionCheckpoint(
        factory_id=factory_id,
        planning_scope_id=planning_scope_id,
        authority_id=authority_id,
        stream_id=stream_id,
        stream_version=stream_version,
        last_applied_position=last_applied_position,
        prefix_fingerprint=prefix_fingerprint,
        fact_checkpoint=ArtifactReference(
            document_version=fact_document_version,
            artifact_id=fact_artifact_id,
            fingerprint=fact_fingerprint,
        ),
        updated_at_utc=updated_at_utc,
    )


def _audit_factory(
    *,
    action: str,
    aggregate_type: str,
    aggregate_id: str,
    correlation_id: str,
    idempotency_scope: str,
    idempotency_key_reference: str,
    request_fingerprint: str | None,
    occurred_at_utc: str,
) -> ReplanAuditRecord:
    return build_replan_audit_record(
        action=ReplanAuditAction(action),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        correlation_id=correlation_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_reference=idempotency_key_reference,
        request_fingerprint=request_fingerprint,
        occurred_at_utc=occurred_at_utc,
    )


def _scope(run_id: str, snapshot: ImmutablePlanningSnapshot) -> ProjectionScope:
    factory = cast(Sequence[Mapping[str, object]], snapshot.document["records"]["factories"])[0]
    suffix = sha256(run_id.encode("utf-8")).hexdigest()[:20]
    return ProjectionScope(
        factory_id=cast(str, factory["factory_id"]),
        planning_scope_id=f"cnc-demo-planning-scope-{suffix}",
        authority_id=f"cnc-demo-event-authority-{suffix}",
        stream_id=f"cnc-demo-execution-stream-{suffix}",
        stream_version="1.0.0",
    )


def _synthetic_provenance(
    snapshot: ImmutablePlanningSnapshot, *, event: bool
) -> dict[str, object]:
    snapshot_document = cast(Mapping[str, object], snapshot.document)
    provenance = dict(
        cast(Mapping[str, object], snapshot_document["synthetic_provenance"])
    )
    if event:
        provenance.update(
            {"simulator_id": SIMULATOR_ID, "simulator_version": SIMULATOR_VERSION}
        )
    return provenance


def build_urgent_event(
    *,
    scope: ProjectionScope,
    snapshot: ImmutablePlanningSnapshot,
    candidate: UrgentCandidate,
    demand_order_id: str,
) -> dict[str, object]:
    occurred_at = cast(str, snapshot.document["cutoff_at_utc"])
    correlation_id = (
        "correlation-demo-urgent-"
        + candidate.command_fingerprint.removeprefix("sha256:")[:24]
    )
    document: dict[str, object] = {
        "execution_event_version": "execution-event.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "event_id": "pending",
        "event_type": "URGENT_DEMAND_RECEIVED",
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "factory_id": scope.factory_id,
        "planning_scope_id": scope.planning_scope_id,
        "authority": {
            "authority_version": "execution-event-authority.v1",
            "authority_id": scope.authority_id,
            "authority_scope": (
                f"SIMULATION/{scope.factory_id}/{scope.planning_scope_id}"
            ),
            "source": {
                "source_system": "plantnexus-demo-simulator",
                "source_version": SIMULATOR_VERSION,
                "source_record_id": scope.stream_id,
            },
            "decision": "AUTHORIZED_SIMULATION_SOURCE",
            "production_binding": False,
        },
        "source_stream": {
            "stream_id": scope.stream_id,
            "stream_version": scope.stream_version,
            "authority_id": scope.authority_id,
        },
        "source_position": 1,
        "occurred_at_utc": occurred_at,
        "received_at_utc": occurred_at,
        "entity_refs": [
            {"entity_type": "DEMAND_ORDER", "entity_id": demand_order_id}
        ],
        "payload": {
            "kind": "URGENT_DEMAND_RECEIVED",
            "demand_order_id": demand_order_id,
            "quantity": candidate.command.quantity,
            "due_at_utc": candidate.due_at_utc,
            "priority_weight": candidate.priority_weight,
            "priority_source": {
                "source_system": PRIORITY_SOURCE_SYSTEM,
                "source_version": "1.0.0",
                "source_record_id": (
                    f"priority:{candidate.demand_source_id}:"
                    f"{candidate.command.priority_class}"
                ),
            },
        },
        "synthetic": True,
        "synthetic_provenance": _synthetic_provenance(snapshot, event=True),
        "production_binding": False,
        "correlation_id": correlation_id,
        "event_fingerprint": "pending",
    }
    event_fingerprint_value = execution_event_fingerprint(document)
    document["event_fingerprint"] = event_fingerprint_value
    document["event_id"] = (
        "execution-event-" + event_fingerprint_value.removeprefix("sha256:")
    )
    require_p4_document(document)
    return document


def _problem_reference(problem: ImmutablePlanningProblemV2) -> dict[str, object]:
    return {
        "document_version": "planning-problem.v2",
        "artifact_id": (
            "planning-problem-v2-" + problem.problem_hash.removeprefix("sha256:")
        ),
        "fingerprint": problem.problem_hash,
    }


def _snapshot_reference(snapshot: ImmutablePlanningSnapshot) -> dict[str, object]:
    return {
        "document_version": "planning-snapshot.v2",
        "artifact_id": snapshot.snapshot_id,
        "fingerprint": snapshot.snapshot_hash,
    }


def project_demo_effective_locks(
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
    base_schedule: Mapping[str, object],
    policy: Mapping[str, object],
) -> EffectiveLockProjection:
    """Narrow completed protections to facts that changed since the base.

    The CNC baseline already excludes operations completed before it was
    published.  The formal projector truthfully lists every completed Snapshot
    fact, while the Replan comparison validator expects only base assignments
    removed by a later completion.  This adapter preserves the immutable
    Snapshot and historical anchors and narrows only that comparison view.
    """

    owner = root_project_effective_locks(
        snapshot=snapshot,
        problem=problem,
        base_schedule=base_schedule,
        policy=policy,
    )
    document = owner.document
    base_ids = set(cast(Sequence[str], document["base_assignment_operation_ids"]))
    active_ids = set(cast(Sequence[str], document["new_active_operation_ids"]))
    removed_since_base = base_ids.difference(active_ids)
    document["completed_operation_ids"] = sorted(removed_since_base)
    document["completed_protections"] = [
        protection
        for protection in cast(
            Sequence[Mapping[str, object]], document["completed_protections"]
        )
        if protection["operation_id"] in removed_since_base
    ]
    document.pop("projection_fingerprint", None)
    projection_fingerprint = contract_fingerprint(document)
    document["projection_fingerprint"] = projection_fingerprint
    return EffectiveLockProjection(
        canonical_bytes=canonical_contract_bytes(document),
        projection_fingerprint=projection_fingerprint,
    )


def _limits_reference(limits: Mapping[str, object]) -> dict[str, object]:
    return {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }


def build_replan_request(
    *,
    preflight: UrgentPreflight,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
    checkpoint: ProjectionCheckpoint,
    freeze_projection: Mapping[str, object],
    limits: Mapping[str, object],
) -> dict[str, object]:
    base_lineage = cast(Mapping[str, object], preflight.base_schedule["lineage"])
    event = preflight.event
    fingerprint_value = cast(str, event["event_fingerprint"])
    correlation_id = cast(str, event["correlation_id"])
    document: dict[str, object] = {
        "replan_request_version": "replan-request.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "request_id": "pending",
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "factory_id": preflight.scope.factory_id,
        "planning_scope_id": preflight.scope.planning_scope_id,
        "base_schedule_version": {
            field: preflight.base_schedule[field]
            for field in (
                "schedule_version_version",
                "schedule_version_id",
                "state",
                "content_fingerprint",
            )
        },
        "base_snapshot": deepcopy(base_lineage["snapshot"]),
        "base_problem": deepcopy(base_lineage["problem"]),
        "new_snapshot": _snapshot_reference(snapshot),
        "new_snapshot_cutoff_at_utc": snapshot.document["cutoff_at_utc"],
        "new_problem": _problem_reference(problem),
        "event_stream": {
            "authority": deepcopy(event["authority"]),
            "source_stream": deepcopy(event["source_stream"]),
            "from_position": 1,
            "through_position": 1,
            "event_ids": [event["event_id"]],
            "event_fingerprints": [fingerprint_value],
            "stream_fingerprint": event_stream_fingerprint([fingerprint_value]),
            "fact_checkpoint": checkpoint.fact_checkpoint.as_document(),
        },
        "trigger_event_ids": [event["event_id"]],
        "trigger_reason": "URGENT_DEMAND_RECEIVED",
        "freeze_resolution": deepcopy(freeze_projection["freeze_resolution"]),
        "planning_policy": deepcopy(freeze_projection["planning_policy"]),
        "solve_limits": _limits_reference(limits),
        "synthetic": True,
        "synthetic_provenance": deepcopy(event["synthetic_provenance"]),
        "production_binding": False,
        "requested_at_utc": snapshot.document["cutoff_at_utc"],
        "correlation_id": correlation_id,
        "request_fingerprint": "pending",
    }
    fingerprint = replan_request_fingerprint(document)
    document["request_fingerprint"] = fingerprint
    document["request_id"] = (
        "replan-request-" + fingerprint.removeprefix("sha256:")
    )
    require_p4_document(document)
    return document


def _kpi_document(
    repository_root: Path,
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: Mapping[str, object],
    assignments: Sequence[Mapping[str, object]],
    planning_run_id: str,
    synthetic_provenance: Mapping[str, object],
    solver_report: Mapping[str, object],
    validation_report: Mapping[str, object],
    import_quality_report: Mapping[str, object],
) -> dict[str, object]:
    metrics = calculate_schedule_kpi_metrics(problem, assignments)
    document = cast(
        dict[str, object],
        json.loads(
            (repository_root / "schemas" / "samples" / "kpi.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["planning_run_id"] = planning_run_id
    inputs = cast(dict[str, object], document["inputs"])
    inputs["snapshot"] = {
        "snapshot_version": "planning-snapshot.v2",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": snapshot.snapshot_hash,
    }
    problem_hash = cast(str, problem["problem_hash"])
    inputs["problem"] = {
        "problem_version": "planning-problem.v2",
        "problem_hash": problem_hash,
    }
    solution_fingerprint = contract_fingerprint(
        {"problem_hash": problem_hash, "assignments": list(assignments)}
    )
    inputs["solution"] = {
        "planning_solution_version": "planning-solution.v1",
        "solution_id": (
            "planning-solution-" + solution_fingerprint.removeprefix("sha256:")
        ),
        "solution_fingerprint": solution_fingerprint,
    }
    formal = validation_report.get("formal_validation")
    validation_fingerprint = contract_fingerprint(
        formal
        if isinstance(formal, Mapping)
        else {"problem_hash": problem_hash, "assignments": list(assignments)}
    )
    inputs["validation_report"] = {
        "validation_report_version": "validation-report.v2",
        "validation_report_fingerprint": validation_fingerprint,
        "status": "PASS",
    }
    solver_fingerprint = contract_fingerprint(solver_report)
    inputs["solver_report"] = {
        "solver_report_version": "solver-report.v1",
        "report_id": "solver-report-kpi-" + solver_fingerprint.removeprefix("sha256:"),
        "solver_report_fingerprint": solver_fingerprint,
    }
    quality_fingerprint = contract_fingerprint(import_quality_report)
    inputs["import_quality_report"] = {
        "report_version": import_quality_report["report_version"],
        "report_id": import_quality_report["report_id"],
        "import_quality_report_fingerprint": quality_fingerprint,
        "status": import_quality_report["status"],
    }
    document["delivery"] = metrics.delivery_document
    document["planning"] = metrics.planning_document
    document["resources"] = metrics.resource_documents
    document["synthetic_provenance"] = {
        key: synthetic_provenance[key]
        for key in (
            "scenario_id",
            "scenario_version",
            "seed",
            "factory_profile_id",
            "profile_version",
            "generator_id",
            "generator_version",
        )
    }
    solver = cast(dict[str, object], document["solver"])
    solver["solver_status"] = solver_report["solver_status"]
    stages = cast(Sequence[Mapping[str, object]], solver_report["objective_stage_results"])
    delivery_stage = stages[0]
    solver["objective_value"] = metrics.priority_weighted_tardiness_seconds
    solver["best_bound"] = delivery_stage["best_bound"]
    solver["relative_gap"] = delivery_stage["relative_gap"]
    timings = cast(Mapping[str, object], solver_report["timings"])
    for field in (
        "model_build_seconds",
        "first_feasible_seconds",
        "solve_seconds",
        "validation_seconds",
        "total_seconds",
    ):
        solver[field] = timings[field]
    model_metrics = cast(Mapping[str, object], solver_report["model_metrics"])
    for field in ("variables", "constraints", "optional_intervals"):
        solver[field] = model_metrics[field]
    solver["memory_peak_mb"] = solver_report["memory_peak_mb"]
    document.pop("kpi_id", None)
    document["kpi_id"] = "kpi-" + sha256(canonical_contract_bytes(document)).hexdigest()
    return document


class DemoKpiCapturingStrategy:
    """Bind KPI evidence to the actual candidate returned by the real strategy."""

    def __init__(
        self,
        repository_root: Path,
        *,
        snapshot: ImmutablePlanningSnapshot,
        target: dict[str, object],
        synthetic_provenance: Mapping[str, object],
        import_quality_report: Mapping[str, object],
    ) -> None:
        self._repository_root = repository_root
        self._snapshot = snapshot
        self._target = target
        self._synthetic_provenance = synthetic_provenance
        self._import_quality_report = import_quality_report
        self._owner = LexicographicReplanStrategy()

    def solve(
        self,
        problem: Mapping[str, object],
        policy: Mapping[str, object],
        limits: Mapping[str, object],
        *,
        base_schedule: Mapping[str, object],
        effective_locks: Mapping[str, object],
        replan_request: Mapping[str, object],
        planning_run_id: str,
        code_commit: str,
    ) -> LexicographicReplanResult:
        result = self._owner.solve(
            cast(Any, problem),
            policy,
            cast(Any, limits),
            base_schedule=base_schedule,
            effective_locks=effective_locks,
            replan_request=replan_request,
            planning_run_id=planning_run_id,
            code_commit=code_commit,
        )
        if result.candidate is not None:
            assignments = cast(
                Sequence[Mapping[str, object]], result.candidate["assignments"]
            )
            generated = _kpi_document(
                self._repository_root,
                snapshot=self._snapshot,
                problem=problem,
                assignments=assignments,
                planning_run_id=planning_run_id,
                synthetic_provenance=self._synthetic_provenance,
                solver_report=result.solver_report,
                validation_report=result.validation_reports[-1],
                import_quality_report=self._import_quality_report,
            )
            self._target.clear()
            self._target.update(generated)
        return result


class UrgentReplanOrchestrator:
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

    def _database(self, run_id: str) -> RunDatabase:
        record = self.control.get_run(run_id)
        if record is None:
            raise DemoOperationError(
                "DEMO_NOT_INITIALIZED", field="expected_run_id", message="run is absent"
            )
        return RunDatabase(
            repository_root=self.repository_root,
            database_path=self.paths.resolve_relative_database(
                record.database_relative_path
            ),
        )

    def preflight(self, command: UrgentOrderCommand) -> UrgentPreflight:
        """Perform every stale/base/input check before any command-side write."""

        active = self.control.active_run()
        if active is None:
            raise DemoOperationError(
                "DEMO_NOT_INITIALIZED", field="expected_run_id", message="no active Demo run"
            )
        if active.run_id != command.expected_run_id:
            raise DemoOperationError(
                "STALE_RUN", field="expected_run_id", message="active Demo run changed"
            )
        database = self._database(active.run_id)
        try:
            manifest = database.get_manifest()
            if manifest is None or not isinstance(manifest.get("profile_name"), str):
                raise DemoOperationError(
                    "DEMO_NOT_INITIALIZED",
                    field="scenario_manifest",
                    message="active run manifest is absent",
                )
            profile_name = cast(str, manifest["profile_name"])
            plane = WorkspaceDataPlane.SIMULATION
            publications = SqlAlchemyPublicationRepository(
                database.engine, data_plane=plane
            )
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=plane
            )
            current = publications.get_current(target="SIMULATION_INTERNAL")
            if current is None:
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="expected_base_version_id",
                    message="no current PUBLISHED Simulation baseline exists",
                )
            if current.schedule_version_id != command.expected_base_version_id:
                raise DemoOperationError(
                    "STALE_BASE_VERSION",
                    field="expected_base_version_id",
                    message="current PUBLISHED baseline changed",
                )
            record = schedules.get_record(current.schedule_version_id)
            if record is None or record.document.get("state") != "PUBLISHED":
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="expected_base_version_id",
                    message="current baseline is not a stored PUBLISHED version",
                )
            base_schedule = dict(record.document)
            lineage = cast(Mapping[str, object], base_schedule["lineage"])
            snapshot_reference = cast(Mapping[str, object], lineage["snapshot"])
            snapshots = SqlAlchemySnapshotRepository(
                database.engine, data_plane=SnapshotDataPlane.SIMULATION
            )
            base_snapshot = snapshots.get_by_id(
                cast(str, snapshot_reference["artifact_id"])
            )
            if (
                base_snapshot is None
                or base_snapshot.snapshot_hash != snapshot_reference["fingerprint"]
            ):
                raise DemoOperationError(
                    "PERSISTENCE_FAILED",
                    field="base_snapshot",
                    message="PUBLISHED baseline Snapshot lineage is unavailable",
                )
            base_generated = DemoPackageGenerator().prepare_batch(profile_name)
            base_ingress = DemoIngressPipeline().run(base_generated)
            if base_ingress.snapshot != base_snapshot:
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="base_snapshot",
                    message="fixed Demo source no longer reproduces the baseline Snapshot",
                )
            try:
                candidate = prepare_urgent_candidate(base_generated, command)
                candidate_ingress = DemoIngressPipeline().run(candidate.generated)
            except UrgentOrderError as error:
                raise DemoOperationError(
                    "INVALID_URGENT_ORDER", field=error.field, message=error.message
                ) from error
            except Exception as error:
                raise DemoOperationError(
                    "IMPORT_VALIDATION_FAILED",
                    field="urgent_import",
                    message="urgent candidate failed the Standard Import chain",
                ) from error
            normalized_document = cast(
                Mapping[str, object], candidate_ingress.normalization.document
            )
            normalized_records = cast(
                Mapping[str, object], normalized_document["records"]
            )
            demands = cast(
                Sequence[Mapping[str, object]], normalized_records["demand_orders"]
            )
            canonical_demand = next(
                (
                    demand
                    for demand in demands
                    if cast(Mapping[str, object], demand["source"])[
                        "source_record_id"
                    ]
                    == candidate.demand_source_id
                ),
                None,
            )
            if canonical_demand is None:
                raise DemoOperationError(
                    "IMPORT_VALIDATION_FAILED",
                    field="urgent_import.demand_order_id",
                    message="canonical urgent demand is absent",
                )
            canonical_demand_id = cast(str, canonical_demand["demand_order_id"])
            scope = _scope(active.run_id, base_snapshot)
            event = build_urgent_event(
                scope=scope,
                snapshot=base_snapshot,
                candidate=candidate,
                demand_order_id=canonical_demand_id,
            )
            events = SqlAlchemyExecutionEventRepository(
                database.engine, data_plane=plane
            ).list_stream(
                authority_id=scope.authority_id,
                stream_id=scope.stream_id,
                stream_version=scope.stream_version,
                after_position=0,
            )
            if events and events != (event,):
                raise DemoOperationError(
                    "BASELINE_STATE_CONFLICT",
                    field="execution_event_stream",
                    message="this Demo run already contains a different urgent event",
                )
            return UrgentPreflight(
                run_id=active.run_id,
                profile_name=profile_name,
                base_schedule=base_schedule,
                base_snapshot=base_snapshot,
                base_ingress=base_ingress,
                candidate=candidate,
                candidate_ingress=candidate_ingress,
                canonical_demand_id=canonical_demand_id,
                scope=scope,
                event=event,
            )
        finally:
            database.close()

    def execute(
        self,
        *,
        command: UrgentOrderCommand,
        idempotency_key_reference: str,
        correlation_id: str,
        occurred_at_utc: str,
        stages: StageSink | None = None,
    ) -> UrgentReplanResult:
        del correlation_id, occurred_at_utc
        stage_sink = StageSink() if stages is None else stages
        with stage_sink.stage("PREPARING_IMPORT"):
            preflight = self.preflight(command)
        request_fingerprint = preflight.candidate.command_fingerprint
        claim = self.control.claim_command(
            scope="URGENT_REPLAN",
            key_reference=idempotency_key_reference,
            request_fingerprint=request_fingerprint,
        )
        command_replay = claim.status == "SUCCEEDED" and claim.result is not None

        database = self._database(preflight.run_id)
        try:
            plane = WorkspaceDataPlane.SIMULATION
            snapshots = SqlAlchemySnapshotRepository(
                database.engine, data_plane=SnapshotDataPlane.SIMULATION
            )
            events = SqlAlchemyExecutionEventRepository(
                database.engine, data_plane=plane
            )
            checkpoints = SqlAlchemyProjectionCheckpointRepository(
                database.engine, data_plane=plane
            )
            replan_audits = SqlAlchemyReplanAuditRepository(
                database.engine, data_plane=plane
            )
            with stage_sink.stage("IMPORTING_URGENT_DEMAND"):
                SqlAlchemyImportStagingRepository(
                    database.engine, data_plane=StagingDataPlane.SIMULATION
                ).stage(preflight.candidate.generated.batch)
            projection = ExecutionFactProjectionService(
                transaction_factory=database.engine.begin,
                scope=preflight.scope,
                events=events,
                checkpoints=checkpoints,
                audits=replan_audits,
                snapshots=snapshots,
                checkpoint_factory=_checkpoint_factory,
                audit_factory=_audit_factory,
                persistence_error_types=(
                    WorkspacePersistenceError,
                    SQLAlchemyError,
                    SnapshotError,
                ),
                unit_registry=load_unit_registry(self.repository_root),
            )
            with stage_sink.stage("APPENDING_EVENT"):
                projection.ingest_event(preflight.event)
            event_id = cast(str, preflight.event["event_id"])
            urgent_import = UrgentDemandImport(
                event_id=event_id,
                inputs=(
                    NormalizationInput(
                        preflight.candidate.generated.batch,
                        preflight.candidate.generated.mapping_profile,
                    ),
                ),
            )
            with stage_sink.stage("PROJECTING_FACTS"):
                projected = projection.project_available(
                    preflight.base_snapshot,
                    urgent_imports={event_id: urgent_import},
                )
            priority_facts: dict[str, DemandPriorityInput] = {
                demand_id: cast(DemandPriorityInput, dict(fact))
                for demand_id, fact in preflight.base_ingress.priority_facts.items()
            }
            payload = cast(Mapping[str, object], preflight.event["payload"])
            priority_source = cast(Mapping[str, object], payload["priority_source"])
            priority_facts[preflight.canonical_demand_id] = {
                "priority_weight": cast(int, payload["priority_weight"]),
                "source_system": cast(str, priority_source["source_system"]),
                "source_version": cast(str, priority_source["source_version"]),
                "source_record_id": cast(str, priority_source["source_record_id"]),
            }
            manifest = database.get_manifest()
            assert manifest is not None
            horizon_start = cast(str, manifest["horizon_start_utc"])
            horizon_end = cast(str, manifest["horizon_end_utc"])
            tick_seconds = cast(int, manifest["tick_seconds"])
            new_problem = build_planning_problem_v2(
                projected.snapshot,
                priority_facts=priority_facts,
                problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
                tick_seconds=tick_seconds,
                horizon_start_utc=horizon_start,
                horizon_end_utc=horizon_end,
            )
            policy = simulation_replan_policy()
            limits = simulation_solve_limits(
                limits_id=f"CNC-DEMO-REPLAN-LIMITS-{preflight.profile_name.upper()}",
                limits_revision="1.0.0",
                source_record_id=f"cnc-demo-replan-limits-{preflight.profile_name}",
                max_wall_time_seconds=float(
                    cast(float | int, manifest["replan_solve_seconds"])
                ),
                max_workers=1,
                random_seed=cast(int, manifest["seed"]),
            )
            freeze_projection = project_demo_effective_locks(
                snapshot=projected.snapshot,
                problem=new_problem,
                base_schedule=preflight.base_schedule,
                policy=policy,
            ).document
            with stage_sink.stage("CREATING_REQUEST"):
                replan_request = build_replan_request(
                    preflight=preflight,
                    snapshot=projected.snapshot,
                    problem=new_problem,
                    checkpoint=cast(ProjectionCheckpoint, projected.checkpoint),
                    freeze_projection=freeze_projection,
                    limits=limits,
                )
            base_lineage = cast(Mapping[str, object], preflight.base_schedule["lineage"])
            kpi_reference = cast(Mapping[str, object], base_lineage["kpi"])
            before_kpi = database.get_artifact(
                artifact_kind="KPI", artifact_id=cast(str, kpi_reference["artifact_id"])
            )
            if (
                before_kpi is None
                or contract_fingerprint(before_kpi) != kpi_reference["fingerprint"]
            ):
                raise DemoOperationError(
                    "PERSISTENCE_FAILED",
                    field="before_kpi",
                    message="PUBLISHED baseline KPI evidence is unavailable",
                )
            after_kpi: dict[str, object] = {}
            planning_run_id = (
                "planning-run-demo-replan-"
                + request_fingerprint.removeprefix("sha256:")
            )
            context = ReplanApplicationContext(
                data_plane="SIMULATION",
                environment="TEST",
                production_binding=False,
                actor_ref=DEMO_ACTOR_REF,
                idempotency_key_reference=idempotency_key_reference,
                correlation_id=cast(str, preflight.event["correlation_id"]),
                occurred_at_utc=cast(str, projected.snapshot.document["cutoff_at_utc"]),
                planning_run_id=planning_run_id,
                attempt_number=1,
                code_commit="uncommitted",
            )
            application = ReplanApplicationService(
                transaction_factory=database.engine.begin,
                schedule_repository=SqlAlchemyScheduleVersionRepository(
                    database.engine, data_plane=plane
                ),
                publication_repository=SqlAlchemyPublicationRepository(
                    database.engine, data_plane=plane
                ),
                snapshot_repository=snapshots,
                request_repository=SqlAlchemyReplanRequestRepository(
                    database.engine, data_plane=plane
                ),
                lineage_repository=SqlAlchemyReplanLineageRepository(
                    database.engine, data_plane=plane
                ),
                audit_repository=replan_audits,
                strategy=DemoKpiCapturingStrategy(
                    self.repository_root,
                    snapshot=projected.snapshot,
                    target=after_kpi,
                    synthetic_provenance=cast(
                        Mapping[str, object], preflight.event["synthetic_provenance"]
                    ),
                    import_quality_report=preflight.candidate_ingress.quality.document,
                ),
            )
            try:
                with stage_sink.stage("SOLVING"):
                    # ReplanApplicationService does not expose projection as a
                    # dependency yet.  Demo jobs are single-worker, so bind the
                    # narrow comparison adapter only for this scoped call.
                    with patch(
                        "app.application.replan_application.project_effective_locks",
                        project_demo_effective_locks,
                    ):
                        applied = application.execute(
                            ReplanApplicationInput(
                                request=replan_request,
                                priority_facts=priority_facts,
                                problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
                                tick_seconds=tick_seconds,
                                horizon_start_utc=horizon_start,
                                horizon_end_utc=horizon_end,
                                policy=policy,
                                limits=limits,
                                before_kpi=before_kpi,
                                after_kpi=after_kpi,
                            ),
                            context,
                        )
            except ReplanApplicationError as error:
                code = {
                    "SOLVER_NO_CANDIDATE": "SOLVER_NO_CANDIDATE",
                    "VALIDATION_FAILED": "SOLUTION_VALIDATION_FAILED",
                    "CHANGE_REPORT_FAILED": "CHANGE_REPORT_INVALID",
                    "STATE_CONFLICT": "STALE_BASE_VERSION",
                }.get(error.reason.value, error.reason.value)
                raise DemoOperationError(
                    code, field=error.field, message="dynamic Replan application rejected the command"
                ) from error
            solver_report = applied.solver_report
            if applied.schedule_version is None or solver_report is None:
                status = "UNKNOWN" if solver_report is None else str(solver_report["solver_status"])
                code = "SOLVER_INFEASIBLE" if status == "INFEASIBLE" else "SOLVER_NO_CANDIDATE"
                raise DemoOperationError(
                    code, field="solver_status", message="replan produced no candidate DRAFT"
                )
            schedule = applied.schedule_version
            validation = applied.validation_report
            change_report = applied.change_report
            if validation is None or change_report is None or applied.kpi is None:
                raise DemoOperationError(
                    "PERSISTENCE_FAILED",
                    field="replan_result",
                    message="applied Replan evidence is incomplete",
                )
            with stage_sink.stage("VERIFYING_SOLUTION"):
                current = SqlAlchemyPublicationRepository(
                    database.engine, data_plane=plane
                ).get_current(target="SIMULATION_INTERNAL")
                if (
                    schedule.get("schedule_version_version") != "schedule-version.v2"
                    or schedule.get("state") != "DRAFT"
                    or current is None
                    or current.schedule_version_id
                    != preflight.base_schedule["schedule_version_id"]
                    or current.content_fingerprint
                    != preflight.base_schedule["content_fingerprint"]
                ):
                    raise DemoOperationError(
                        "BASELINE_STATE_CONFLICT",
                        field="schedule_version",
                        message="DRAFT/current PUBLISHED postcondition failed",
                    )
                if validation.get("status") != "PASS":
                    raise DemoOperationError(
                        "SOLUTION_VALIDATION_FAILED",
                        field="validation_report",
                        message="fresh Replan validation did not PASS",
                    )
            with stage_sink.stage("COMMITTING_RESULT"):
                artifact_documents: tuple[tuple[str, Mapping[str, object], str], ...] = (
                    (
                        "IMPORT_QUALITY",
                        cast(Mapping[str, object], preflight.candidate_ingress.quality.document),
                        cast(str, preflight.candidate_ingress.quality.document["report_id"]),
                    ),
                    ("SNAPSHOT", projected.snapshot.document, projected.snapshot.snapshot_id),
                    ("PLANNING_PROBLEM", new_problem.document, cast(str, _problem_reference(new_problem)["artifact_id"])),
                    ("REPLAN_REQUEST", replan_request, cast(str, replan_request["request_id"])),
                    ("SOLVER_REPORT", solver_report, cast(str, solver_report["report_id"])),
                    (
                        "VALIDATION_REPORT",
                        validation,
                        "validation-report-" + contract_fingerprint(validation).removeprefix("sha256:"),
                    ),
                    ("KPI", applied.kpi, cast(str, applied.kpi["kpi_id"])),
                    ("CHANGE_REPORT", change_report, cast(str, change_report["report_id"])),
                )
                for kind, document, artifact_id in artifact_documents:
                    database.put_artifact(
                        artifact_kind=kind,
                        artifact_id=artifact_id,
                        document_version=artifact_version(document),
                        document=document,
                    )
            classifications: dict[str, int] = {"ADDED": 0, "CHANGED": 0, "UNCHANGED": 0}
            for operation in cast(Sequence[Mapping[str, object]], change_report["operations"]):
                classification = cast(str, operation["classification"])
                if classification in classifications:
                    classifications[classification] += 1
            with stage_sink.stage("BUILDING_PRESENTATION"):
                result = UrgentReplanResult(
                    run_id=preflight.run_id,
                    demand_order_id=preflight.canonical_demand_id,
                    event_id=event_id,
                    snapshot_id=projected.snapshot.snapshot_id,
                    problem_hash=new_problem.problem_hash,
                    request_id=cast(str, replan_request["request_id"]),
                    attempt_id=cast(str, applied.attempt["attempt_id"]),
                    schedule_version_id=cast(str, schedule["schedule_version_id"]),
                    schedule_state="DRAFT",
                    solver_status=cast(str, solver_report["solver_status"]),
                    validation_status=cast(str, validation["status"]),
                    change_report_id=cast(str, change_report["report_id"]),
                    added_operations=classifications["ADDED"],
                    changed_operations=classifications["CHANGED"],
                    unchanged_operations=classifications["UNCHANGED"],
                    current_published_version_id=cast(
                        str, preflight.base_schedule["schedule_version_id"]
                    ),
                    exact_replay=applied.exact_replay,
                )
                durable_result = result.document | {"exact_replay": False}
                if command_replay:
                    if durable_result != claim.result or not applied.exact_replay:
                        raise DemoOperationError(
                            "IDEMPOTENCY_CONFLICT",
                            field="urgent_replan.result",
                            message="formal replay differs from the durable Demo result",
                        )
                    return result
                database.append_command_audit(
                    audit_id=(
                        "demo-audit-urgent-"
                        + request_fingerprint.removeprefix("sha256:")
                    ),
                    command_type="URGENT_ORDER_REPLAN",
                    request_fingerprint=request_fingerprint,
                    actor_ref=DEMO_ACTOR_REF,
                    correlation_id=cast(str, preflight.event["correlation_id"]),
                    result_reference={
                        "command": command.model_dump(mode="json"),
                        "formal_event": {
                            "event_id": event_id,
                            "event_fingerprint": preflight.event["event_fingerprint"],
                        },
                        "result": durable_result,
                    },
                    occurred_at_utc=cast(
                        str, projected.snapshot.document["cutoff_at_utc"]
                    ),
                )
                self.control.complete_command(
                    scope="URGENT_REPLAN",
                    key_reference=idempotency_key_reference,
                    request_fingerprint=request_fingerprint,
                    result=durable_result,
                )
            with stage_sink.stage("COMPLETE"):
                return result
        except (DemoOperationError, DemoPersistenceError):
            raise
        except Exception as error:
            raise DemoOperationError(
                "PERSISTENCE_FAILED",
                field="urgent_replan",
                message="urgent Replan failed closed",
            ) from error
        finally:
            database.close()


def _result_from_document(
    document: Mapping[str, object], *, exact_replay: bool
) -> UrgentReplanResult:
    changes = cast(Mapping[str, object], document["operation_changes"])
    return UrgentReplanResult(
        run_id=cast(str, document["run_id"]),
        demand_order_id=cast(str, document["demand_order_id"]),
        event_id=cast(str, document["event_id"]),
        snapshot_id=cast(str, document["snapshot_id"]),
        problem_hash=cast(str, document["problem_hash"]),
        request_id=cast(str, document["request_id"]),
        attempt_id=cast(str, document["attempt_id"]),
        schedule_version_id=cast(str, document["schedule_version_id"]),
        schedule_state=cast(str, document["schedule_state"]),
        solver_status=cast(str, document["solver_status"]),
        validation_status=cast(str, document["validation_status"]),
        change_report_id=cast(str, document["change_report_id"]),
        added_operations=cast(int, changes["ADDED"]),
        changed_operations=cast(int, changes["CHANGED"]),
        unchanged_operations=cast(int, changes["UNCHANGED"]),
        current_published_version_id=cast(
            str, document["current_published_version_id"]
        ),
        exact_replay=exact_replay,
    )


__all__ = [
    "DemoKpiCapturingStrategy",
    "UrgentPreflight",
    "UrgentReplanOrchestrator",
    "UrgentReplanResult",
    "build_replan_request",
    "build_urgent_event",
    "project_demo_effective_locks",
]
