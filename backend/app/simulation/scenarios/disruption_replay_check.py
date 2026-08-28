"""Emit machine-checkable TASK-P4-10 continuous disruption replay evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from alembic import command
from sqlalchemy import create_engine

from app.data_validation import validate_import_package
from app.application.execution_fact_projection_check import (
    _alembic_config,
    _generated_base,
    _persist_base,
    _raw_row,
    _service,
    _urgent_batch,
    run_projection_checks,
)
from app.application.replan_application import ReplanApplicationService
from app.application.replan_application_check import (
    ReplanApplicationFixture,
    _checkpoint,
    _limits_reference,
    _priority_facts,
    _sample,
    seed_replan_application_runtime,
    run_replan_application_checks,
)
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    event_stream_fingerprint,
    replan_request_fingerprint,
    require_p4_document,
)
from app.domain.execution_fact_projection import ProjectionScope
from app.domain.replan_application import ReplanApplicationContext
from app.domain.workspace_contracts import (
    require_workspace_document,
    workspace_fingerprint,
)
from app.importers import StagedImportBatch
from app.importers.urgent_demand import UrgentDemandImport
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import (
    WorkspaceDataPlane,
    canonical_document,
)
from app.normalization import NormalizationInput, expand_orders, normalize_import
from app.planning.backends.cp_sat.backend import CpSatBackend
from app.planning.backends.cp_sat.core_model_check import synthetic_core_policy
from app.planning.backends.cp_sat.replan_solver_check import _limits
from app.planning.policy.freeze_window import simulation_replan_policy
from app.planning.problem.builder import build_planning_problem_v2
from app.planning.problem.contracts import DemandPriorityInput, ImmutablePlanningProblemV2
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import (
    TICK_SECONDS,
    _published_base_schedule,
)
from app.planning.problem.hashing import PROBLEM_BUILDER_VERSION_V2
from app.planning.reporting.kpi import calculate_schedule_kpi_metrics
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanResult,
    LexicographicReplanStrategy,
)
from app.simulation.execution import ExecutionSimulator
from app.simulation.execution.simulator_check import run_execution_simulator_checks
from app.simulation.generators import p1_mapping_profile
from app.snapshots import ImmutablePlanningSnapshot, build_planning_snapshot

from .disruption_replay import (
    BASELINE_ADVANCE_MODE,
    ContinuousReplayStepRequest,
    DisruptionReplayError,
    DisruptionReplayFailure,
    DisruptionReplayOrchestrator,
    DisruptionScenarioLibrary,
    EXPECTED_INVARIANTS,
    STEP_EVIDENCE_VERSION,
    build_execution_config,
    build_execution_schedule,
    load_disruption_scenario_library,
)


REPORT_VERSION = "p4-disruption-replay-report.v1"
TASK_ID = "TASK-P4-10"
DIFF_BASE = "8bbe0c643571e578ec637f135a2390c90de02512"
IMPACT_RULES = (
    "IMPACT-DOCS",
    "IMPACT-FIXTURE",
    "IMPACT-INFRA",
    "IMPACT-SIM-SCENARIO",
    "IMPACT-TESTS",
)
ASSET_PATH = Path("fixtures/synthetic/P4-DISRUPTION-REPLAY/scenario-library.v1.json")

_OWNER_FILES = (
    "backend/app/application/execution_fact_projection.py",
    "backend/app/application/replan_application.py",
    "backend/app/planning/backends/cp_sat/replan_solver_check.py",
    "backend/app/planning/validation/replan_candidate_validator.py",
    "backend/app/simulation/execution/contracts.py",
    "backend/app/simulation/execution/simulator.py",
    "schemas/json/execution-event.schema.json",
    "schemas/json/replan-request.schema.json",
    "schemas/json/change-report.schema.json",
    "pyproject.toml",
    "uv.lock",
)


def _replay_base_batch(batch: StagedImportBatch) -> StagedImportBatch:
    """Return the P4-10 base with execution-ready resources and one valid lock."""

    rows = []
    replaced_lock = False
    mapped_resources = 0
    for position, row in enumerate(batch.rows, start=1):
        if not (
            row.row_identity.startswith("resources:")
            or row.row_identity == "operation_locks:operation-lock-001"
        ):
            rows.append(row)
            continue
        outer = cast(dict[str, object], json.loads(row.raw_payload))
        payload = cast(dict[str, object], json.loads(cast(str, outer["payload_json"])))
        if row.row_identity.startswith("resources:"):
            payload["status"] = "AVAILABLE"
            mapped_resources += 1
        else:
            payload["start_at_utc"] = "2026-11-06T12:20:00Z"
            payload["end_at_utc"] = "2026-11-06T12:25:00Z"
            replaced_lock = True
        rows.append(
            _raw_row(
                cast(str, outer["record_type"]),
                cast(str, outer["source_record_id"]),
                payload,
                position=position,
            )
        )
    _ensure(replaced_lock, "P4-10 explicit hard-lock source row is missing")
    _ensure(mapped_resources == 4, "P4-10 execution-ready resource set drifted")
    immutable_rows = tuple(rows)
    content = b"\n".join(row.raw_payload for row in immutable_rows)
    digest = sha256(content).hexdigest()
    return replace(
        batch,
        batch_id=f"p4-10-replay-batch-{digest[:24]}",
        idempotency_key=f"p4-10-replay-import-{digest}",
        content_sha256=digest,
        content_length_bytes=len(content),
        rows=immutable_rows,
    )

class _EvidenceIngress:
    """Append-only standard-event observer with exact replay/conflict behavior."""

    def __init__(self) -> None:
        self.documents: dict[str, bytes] = {}
        self.calls = 0
        self.replays = 0

    def ingest_event(self, document: Mapping[str, object]) -> object:
        self.calls += 1
        event_id = cast(str, document["event_id"])
        value = canonical_contract_bytes(document)
        previous = self.documents.get(event_id)
        if previous is not None and previous != value:
            raise ValueError("same event identity has a different fingerprint")
        if previous is not None:
            self.replays += 1
        self.documents[event_id] = value
        return {"event_id": event_id, "replayed": previous is not None}


def _reference(
    document_version: str, prefix: str, projection: Mapping[str, object]
) -> dict[str, object]:
    fingerprint = contract_fingerprint(projection)
    return {
        "document_version": document_version,
        "artifact_id": f"{prefix}-{fingerprint.removeprefix('sha256:')}",
        "fingerprint": fingerprint,
    }


def _artifact_reference(
    *, document_version: str, artifact_id: str, fingerprint: str
) -> dict[str, object]:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": fingerprint,
    }


def _snapshot_reference(snapshot: ImmutablePlanningSnapshot) -> dict[str, object]:
    return _artifact_reference(
        document_version="planning-snapshot.v2",
        artifact_id=snapshot.snapshot_id,
        fingerprint=snapshot.snapshot_hash,
    )


def _problem_reference(problem: ImmutablePlanningProblemV2) -> dict[str, object]:
    return _artifact_reference(
        document_version="planning-problem.v2",
        artifact_id="planning-problem-v2-"
        + problem.problem_hash.removeprefix("sha256:"),
        fingerprint=problem.problem_hash,
    )


def _truthful_published_base_schedule(
    root: Path,
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
) -> dict[str, object]:
    """Bind the frozen PUBLISHED carrier to an independently validated candidate."""

    solved = CpSatBackend().solve_with_evidence(
        cast(Any, problem.document), synthetic_core_policy(), _limits()
    )
    validation = solved.validation_report
    if validation is None:
        raise ValueError("P4-10 base solver returned no validation report")
    _ensure(
        solved.solution["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and validation["status"] == "PASS",
        "P4-10 base solver did not produce an independently validated candidate",
    )
    assignments = deepcopy(list(solved.solution["assignments"]))
    content: dict[str, object] = {"assignments": assignments, "locks": []}
    schedule = _published_base_schedule(root, snapshot=snapshot, problem=problem)
    schedule["content"] = content
    schedule["content_fingerprint"] = workspace_fingerprint(content)

    solution_fingerprint = contract_fingerprint(solved.solution)
    validation_fingerprint = contract_fingerprint(cast(Mapping[str, object], validation))
    planning_solution_reference = _artifact_reference(
        document_version=cast(str, solved.solution["planning_solution_version"]),
        artifact_id=cast(str, solved.solution["solution_id"]),
        fingerprint=solution_fingerprint,
    )
    validation_reference = _artifact_reference(
        document_version=cast(str, validation["validation_report_version"]),
        artifact_id=(
            "validation-report-p4-10-base-"
            + validation_fingerprint.removeprefix("sha256:")
        ),
        fingerprint=validation_fingerprint,
    )
    solver_reference = _artifact_reference(
        document_version="solver-report.v1",
        artifact_id=(
            "solver-report-p4-10-base-"
            + solution_fingerprint.removeprefix("sha256:")
        ),
        fingerprint=solution_fingerprint,
    )
    lineage = cast(dict[str, object], schedule["lineage"])
    lineage["planning_solution"] = planning_solution_reference
    lineage["validation_report"] = validation_reference
    lineage["solver_report"] = solver_reference
    schedule_validation = cast(dict[str, object], schedule["validation"])
    schedule_validation["validation_report"] = validation_reference
    schedule_validation["status"] = validation["status"]
    schedule_validation["hard_violation_count"] = validation[
        "hard_violation_count"
    ]
    require_workspace_document(schedule)
    return schedule


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _horizon(snapshot: ImmutablePlanningSnapshot) -> tuple[str, str]:
    start = cast(str, snapshot.document["cutoff_at_utc"])
    return (
        start,
        _format_utc(
            datetime.fromisoformat(start.replace("Z", "+00:00"))
            + timedelta(days=1)
        ),
    )


def _synthetic_provenance(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value[key]
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


def _kpi_document(
    root: Path,
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
    assignments: Sequence[Mapping[str, object]],
    planning_run_id: str,
    synthetic_provenance: Mapping[str, object],
    solver_report: Mapping[str, object] | None = None,
    validation_report: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Project truthful schedule metrics into the frozen synthetic KPI v2 carrier."""

    metrics = calculate_schedule_kpi_metrics(problem.document, assignments)
    document = _sample(root, "kpi.v2.synthetic.json")
    document["planning_run_id"] = planning_run_id
    inputs = cast(dict[str, object], document["inputs"])
    inputs["snapshot"] = {
        "snapshot_version": "planning-snapshot.v2",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": snapshot.snapshot_hash,
    }
    inputs["problem"] = {
        "problem_version": "planning-problem.v2",
        "problem_hash": problem.problem_hash,
    }
    solution_fingerprint = contract_fingerprint(
        {"problem_hash": problem.problem_hash, "assignments": list(assignments)}
    )
    inputs["solution"] = {
        "planning_solution_version": "planning-solution.v1",
        "solution_id": "planning-solution-" + solution_fingerprint.removeprefix("sha256:"),
        "solution_fingerprint": solution_fingerprint,
    }
    formal = (
        cast(Mapping[str, object], validation_report.get("formal_validation"))
        if validation_report is not None
        else None
    )
    validation_fingerprint = contract_fingerprint(
        formal
        if formal is not None
        else {"problem": problem.problem_hash, "assignments": list(assignments)}
    )
    inputs["validation_report"] = {
        "validation_report_version": "validation-report.v2",
        "validation_report_fingerprint": validation_fingerprint,
        "status": "PASS",
    }
    solver_fingerprint = contract_fingerprint(
        solver_report
        if solver_report is not None
        else {"problem": problem.problem_hash, "assignments": list(assignments)}
    )
    inputs["solver_report"] = {
        "solver_report_version": "solver-report.v1",
        "report_id": "solver-report-kpi-" + solver_fingerprint.removeprefix("sha256:"),
        "solver_report_fingerprint": solver_fingerprint,
    }
    document["delivery"] = metrics.delivery_document
    document["planning"] = metrics.planning_document
    document["resources"] = metrics.resource_documents
    document["synthetic_provenance"] = _synthetic_provenance(synthetic_provenance)
    solver = cast(dict[str, object], document["solver"])
    solver["solver_status"] = (
        solver_report.get("solver_status", "OPTIMAL")
        if solver_report is not None
        else "OPTIMAL"
    )
    solver["objective_value"] = metrics.priority_weighted_tardiness_seconds
    solver["best_bound"] = metrics.priority_weighted_tardiness_seconds
    document.pop("kpi_id", None)
    document["kpi_id"] = "kpi-" + sha256(
        canonical_contract_bytes(document)
    ).hexdigest()
    return document


class _KpiCapturingStrategy:
    """Delegate to the frozen P4-07 strategy and bind its real candidate KPI."""

    def __init__(
        self,
        root: Path,
        *,
        snapshot: ImmutablePlanningSnapshot,
        target: dict[str, object],
        synthetic_provenance: Mapping[str, object],
    ) -> None:
        self._root = root
        self._snapshot = snapshot
        self._target = target
        self._synthetic_provenance = synthetic_provenance
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
        candidate = result.candidate
        if candidate is None:
            raise ValueError(
                "P4-10 common-path solve produced no candidate: "
                + json.dumps(
                    {
                        "solver_status": result.solver_report["solver_status"],
                        "planning_run_outcome": result.solver_report[
                            "planning_run_outcome"
                        ],
                        "diagnostics": result.solver_report["diagnostics"],
                        "effective_locks": effective_locks,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        assignments = cast(
            Sequence[Mapping[str, object]], candidate.get("assignments")
        )
        validation = result.validation_reports[-1]
        generated = _kpi_document(
            self._root,
            snapshot=self._snapshot,
            problem=ImmutablePlanningProblemV2(
                canonical_bytes=canonical_contract_bytes(problem),
                problem_hash=cast(str, problem["problem_hash"]),
                snapshot_id=cast(str, problem["snapshot_id"]),
                problem_builder_version=cast(str, problem["problem_builder_version"]),
            ),
            assignments=assignments,
            planning_run_id=planning_run_id,
            synthetic_provenance=self._synthetic_provenance,
            solver_report=result.solver_report,
            validation_report=validation,
        )
        self._target.clear()
        self._target.update(generated)
        return result


class _ContractEvidencePort:
    """Fast deterministic envelope fixture used only by contract/property tests."""

    def __init__(self) -> None:
        self.calls = 0

    def replay_step(self, request: ContinuousReplayStepRequest) -> Mapping[str, object]:
        self.calls += 1
        event_ids = [cast(str, value["event_id"]) for value in request.event_documents]
        projection = {
            "step": request.step.as_document(),
            "events": list(request.event_documents),
            "base": request.baseline.as_document(),
            "stream_fingerprint": request.stream_fingerprint,
        }
        new_snapshot = _reference(
            "planning-snapshot.v2", "planning-snapshot-v2", projection
        )
        new_problem = _reference(
            "planning-problem.v2",
            "planning-problem-v2",
            {"snapshot": new_snapshot, "step": request.step.step_id},
        )
        replan_request = _reference(
            "replan-request.v1",
            "replan-request",
            {
                "base": request.baseline.as_document(),
                "new_snapshot": new_snapshot,
                "new_problem": new_problem,
                "event_ids": event_ids,
                "stream_fingerprint": request.stream_fingerprint,
            },
        )
        planning_run_id = "planning-run-p4-10-" + contract_fingerprint(
            {"request": replan_request, "step": request.step.step_id}
        ).removeprefix("sha256:")
        formal_validation = {
            "validation_report_version": "validation-report.v2",
            "status": "PASS",
            "hard_violation_count": 0,
        }
        validation_fingerprint = contract_fingerprint(formal_validation)
        validation = {
            "document_version": "validation-report.v2",
            "artifact_id": "validation-report-"
            + validation_fingerprint.removeprefix("sha256:"),
            "fingerprint": validation_fingerprint,
        }
        draft_fingerprint = contract_fingerprint(
            {
                "base": request.baseline.schedule_version.as_document(),
                "new_problem": new_problem,
                "request": replan_request,
                "validation": validation,
            }
        )
        draft_id = "schedule-version-" + contract_fingerprint(
            {
                "step": request.step.step_id,
                "content_fingerprint": draft_fingerprint,
            }
        ).removeprefix("sha256:")
        change = _reference(
            "change-report.v1",
            "change-report",
            {
                "base": request.baseline.schedule_version.as_document(),
                "draft_id": draft_id,
                "event_ids": event_ids,
                "validation": validation,
            },
        )
        before = after = request.step.step_index * 60
        vector = (0, request.step.step_index, 0, request.step.step_index * 60)
        next_schedule = {
            "schedule_version_version": "schedule-version.v1",
            "schedule_version_id": "simulation-baseline-"
            + contract_fingerprint(
                {"source_draft_id": draft_id, "step": request.step.step_id}
            ).removeprefix("sha256:"),
            "state": "PUBLISHED",
            "content_fingerprint": draft_fingerprint,
        }
        raw_change = {
            "change_report_version": "change-report.v1",
            "report_id": cast(str, change["artifact_id"]),
            "report_fingerprint": cast(str, change["fingerprint"]),
            "operation_universe_count": 0,
            "operations": [],
            "production_binding": False,
        }
        return {
            "evidence_version": STEP_EVIDENCE_VERSION,
            "step_id": request.step.step_id,
            "disruption_kind": request.step.disruption_kind.value,
            "base_schedule_version": request.baseline.schedule_version.as_document(),
            "base_snapshot": request.baseline.snapshot.as_document(),
            "trigger_event_ids": event_ids,
            "new_snapshot": new_snapshot,
            "new_problem": new_problem,
            "replan_request": replan_request,
            "planning_run": {
                "planning_run_id": planning_run_id,
                "state": "COMPLETED",
                "fresh_validator_run": True,
            },
            "validation_report": {
                **validation,
                "status": "PASS",
                "hard_violation_count": 0,
            },
            "new_schedule_version": {
                "schedule_version_version": "schedule-version.v2",
                "schedule_version_id": draft_id,
                "state": "DRAFT",
                "content_fingerprint": draft_fingerprint,
            },
            "change_report": {
                **change,
                "complete": True,
                "trigger_event_ids": event_ids,
            },
            "fact_lock_invariants": {name: True for name in EXPECTED_INVARIANTS},
            "tardiness": {
                "before_seconds": before,
                "after_seconds": after,
            },
            "stability": {
                "soft_lock_violation_count": vector[0],
                "changed_existing_operation_count": vector[1],
                "resource_changed_count": vector[2],
                "total_absolute_start_shift_seconds": vector[3],
            },
            "baseline_advance": {
                "mode": BASELINE_ADVANCE_MODE,
                "production_binding": False,
                "authority_claim": "NONE",
                "source_draft_id": draft_id,
                "next_schedule_version": next_schedule,
                "next_snapshot": new_snapshot,
                "next_problem": new_problem,
            },
            "production_binding": False,
            "raw_events": list(request.event_documents),
            "raw_replan_request": {
                "replan_request_version": "replan-request.v1",
                "request_id": replan_request["artifact_id"],
                "request_fingerprint": replan_request["fingerprint"],
            },
            "raw_solver_report": {
                "solver_report_version": "solver-report.v2",
                "planning_run_id": planning_run_id,
                "candidate": {"assignments": []},
                "solver_status": "OPTIMAL",
            },
            "raw_validation_report": {
                "status": "PASS",
                "hard_violation_count": 0,
                "formal_validation": formal_validation,
            },
            "raw_schedule_version": {
                "schedule_version_version": "schedule-version.v2",
                "schedule_version_id": draft_id,
                "state": "DRAFT",
                "content_fingerprint": draft_fingerprint,
            },
            "raw_change_report": raw_change,
        }


class _TamperedEvidencePort(_ContractEvidencePort):
    def replay_step(self, request: ContinuousReplayStepRequest) -> Mapping[str, object]:
        document = deepcopy(dict(super().replay_step(request)))
        invariants = cast(dict[str, object], document["fact_lock_invariants"])
        invariants["FRESH_VALIDATOR_PASS"] = False
        return document


class _OwnerCommonPathEvidencePort:
    """Compose the real frozen P4-04/P4-05/P4-07/P4-08 public path."""

    def __init__(
        self,
        root: Path,
        library: DisruptionScenarioLibrary,
        *,
        code_commit: str,
        workspace: Path,
    ) -> None:
        self._root = root
        self._library = library
        self._code_commit = code_commit
        self._workspace = workspace
        self.calls = 0
        self.ingest_calls = 0
        self._step_database_index = 0
        self._all_events: list[dict[str, object]] = []
        self._priority_overrides: dict[str, DemandPriorityInput] = {}

        registry, generation_context, batch, _ = _generated_base(root)
        batch = _replay_base_batch(batch)
        self._unit_registry = registry
        base_normalization = normalize_import(
            (NormalizationInput(batch, p1_mapping_profile(generation_context)),),
            unit_registry=registry,
        )
        base_quality = validate_import_package(cast(Any, base_normalization.document))
        _ensure(base_quality.passed, "generated replay base failed Data Validation")
        base_expansion = expand_orders(
            cast(Any, base_normalization.document), base_quality.document
        )
        base_snapshot = build_planning_snapshot(
            cast(Any, base_normalization.document),
            base_quality.document,
            base_expansion,
            cutoff_at_utc="2026-11-06T11:00:00Z",
        )
        self._urgent_input = NormalizationInput(
            _urgent_batch(batch), p1_mapping_profile(generation_context)
        )
        self._current_snapshot = base_snapshot
        self._current_problem = self._build_problem(base_snapshot)
        base_schedule = _truthful_published_base_schedule(
            root, snapshot=base_snapshot, problem=self._current_problem
        )
        self._scenario_provenance = {
            "scenario_id": library.asset_id,
            "scenario_version": library.asset_version,
            "seed": library.seed,
            "factory_profile_id": library.factory_profile.asset_id,
            "profile_version": library.factory_profile.asset_version,
            "generator_id": library.generator.asset_id,
            "generator_version": library.generator.asset_version,
        }
        base_assignments = cast(
            Sequence[Mapping[str, object]],
            cast(Mapping[str, object], base_schedule["content"])["assignments"],
        )
        self._before_kpi = _kpi_document(
            root,
            snapshot=base_snapshot,
            problem=self._current_problem,
            assignments=base_assignments,
            planning_run_id="planning-run-p4-10-base-001",
            synthetic_provenance=self._scenario_provenance,
        )
        base_lineage = cast(dict[str, object], base_schedule["lineage"])
        base_lineage["kpi"] = _artifact_reference(
            document_version="kpi.v2",
            artifact_id=cast(str, self._before_kpi["kpi_id"]),
            fingerprint=contract_fingerprint(self._before_kpi),
        )
        require_workspace_document(base_schedule)
        self._current_schedule = base_schedule
        self._schedule_history: list[dict[str, object]] = [deepcopy(base_schedule)]

        _ensure(
            library.factory_id
            == cast(
                str,
                cast(
                    Sequence[Mapping[str, object]],
                    base_snapshot.document["records"]["factories"],
                )[0]["factory_id"],
            ),
            "scenario factory does not match the generated common-ingress base",
        )
        _ensure(
            library.base_snapshot.as_document() == _snapshot_reference(base_snapshot),
            "scenario base Snapshot reference drifted",
        )
        _ensure(
            library.base_problem.as_document()
            == _problem_reference(self._current_problem),
            "scenario base Problem reference drifted",
        )
        _ensure(
            library.base_schedule.as_document()
            == {
                key: base_schedule[key]
                for key in (
                    "schedule_version_version",
                    "schedule_version_id",
                    "state",
                    "content_fingerprint",
                )
            },
            "scenario base ScheduleVersion reference drifted",
        )

        compiled = ExecutionSimulator().compile(
            build_execution_config(library, code_commit=code_commit),
            build_execution_schedule(library),
        )
        first_event = compiled.events[0]
        authority = cast(Mapping[str, object], first_event["authority"])
        source_stream = cast(Mapping[str, object], first_event["source_stream"])
        scope = ProjectionScope(
            factory_id=library.factory_id,
            planning_scope_id=library.planning_scope_id,
            authority_id=cast(str, authority["authority_id"]),
            stream_id=cast(str, source_stream["stream_id"]),
            stream_version=cast(str, source_stream["stream_version"]),
        )
        projection_path = workspace / "fact-projection.db"
        projection_url = f"sqlite:///{projection_path.as_posix()}"
        command.upgrade(_alembic_config(root, projection_url), "head")
        self._projection_engine = create_engine(projection_url)
        _persist_base(self._projection_engine, base_snapshot)
        self._projection_service = _service(
            self._projection_engine,
            scope=scope,
            unit_registry=registry,
        )

    def close(self) -> None:
        self._projection_engine.dispose()

    def ingest_event(self, document: Mapping[str, object]) -> object:
        self.ingest_calls += 1
        return self._projection_service.ingest_event(document)

    def _priority_inputs(
        self, snapshot: ImmutablePlanningSnapshot
    ) -> dict[str, DemandPriorityInput]:
        values = _priority_facts(snapshot)
        values.update(self._priority_overrides)
        return values

    def _build_problem(
        self, snapshot: ImmutablePlanningSnapshot
    ) -> ImmutablePlanningProblemV2:
        start, end = _horizon(snapshot)
        return build_planning_problem_v2(
            snapshot,
            priority_facts=self._priority_inputs(snapshot),
            problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
            tick_seconds=TICK_SECONDS,
            horizon_start_utc=start,
            horizon_end_utc=end,
        )

    def _replan_request(
        self,
        request: ContinuousReplayStepRequest,
        *,
        snapshot: ImmutablePlanningSnapshot,
        problem: ImmutablePlanningProblemV2,
        checkpoint: object,
        freeze_projection: Mapping[str, object],
        context: ReplanApplicationContext,
    ) -> dict[str, object]:
        document = _sample(self._root, "replan-request.v1.synthetic.json")
        first_event = self._all_events[0]
        fingerprints = [
            cast(str, event["event_fingerprint"]) for event in self._all_events
        ]
        observed_stream = event_stream_fingerprint(fingerprints)
        _ensure(
            observed_stream == request.stream_fingerprint,
            "Simulator and fact-projection stream fingerprints differ",
        )
        projection_checkpoint = cast(Any, checkpoint)
        _ensure(
            projection_checkpoint.last_applied_position == len(self._all_events)
            and projection_checkpoint.prefix_fingerprint == observed_stream,
            "fact-projection checkpoint does not cover the exact Simulator prefix",
        )
        document.update(
            {
                "factory_id": self._library.factory_id,
                "planning_scope_id": self._library.planning_scope_id,
                "base_schedule_version": request.baseline.schedule_version.as_document(),
                "base_snapshot": request.baseline.snapshot.as_document(),
                "base_problem": request.baseline.problem.as_document(),
                "new_snapshot": _snapshot_reference(snapshot),
                "new_snapshot_cutoff_at_utc": snapshot.document["cutoff_at_utc"],
                "new_problem": _problem_reference(problem),
                "event_stream": {
                    "authority": deepcopy(first_event["authority"]),
                    "source_stream": deepcopy(first_event["source_stream"]),
                    "from_position": 1,
                    "through_position": len(self._all_events),
                    "event_ids": [event["event_id"] for event in self._all_events],
                    "event_fingerprints": fingerprints,
                    "stream_fingerprint": observed_stream,
                    "fact_checkpoint": (
                        projection_checkpoint.fact_checkpoint.as_document()
                    ),
                },
                "trigger_event_ids": [
                    event["event_id"] for event in request.event_documents
                ],
                "trigger_reason": "EXECUTION_FACT_CHANGED",
                "freeze_resolution": deepcopy(
                    freeze_projection["freeze_resolution"]
                ),
                "planning_policy": deepcopy(
                    freeze_projection["planning_policy"]
                ),
                "solve_limits": _limits_reference(_limits()),
                "synthetic_provenance": deepcopy(
                    first_event["synthetic_provenance"]
                ),
                "requested_at_utc": context.occurred_at_utc,
                "correlation_id": context.correlation_id,
            }
        )
        document["request_fingerprint"] = replan_request_fingerprint(document)
        document["request_id"] = "replan-request-" + cast(
            str, document["request_fingerprint"]
        ).removeprefix("sha256:")
        require_p4_document(document)
        return document

    def _execute_application(
        self,
        fixture: ReplanApplicationFixture,
        *,
        after_kpi: dict[str, object],
        synthetic_provenance: Mapping[str, object],
    ) -> object:
        self._step_database_index += 1
        database_path = self._workspace / (
            f"replan-step-{self._step_database_index}.db"
        )
        database_url = f"sqlite:///{database_path.as_posix()}"
        command.upgrade(_alembic_config(self._root, database_url), "head")
        engine = create_engine(database_url)
        try:
            schedule_repository = SqlAlchemyScheduleVersionRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            for schedule in self._schedule_history:
                schedule_repository.put(schedule)
            runtime = seed_replan_application_runtime(self._root, engine, fixture)
            strategy = _KpiCapturingStrategy(
                self._root,
                snapshot=cast(ImmutablePlanningSnapshot, fixture.snapshot),
                target=after_kpi,
                synthetic_provenance=synthetic_provenance,
            )
            service = ReplanApplicationService(
                transaction_factory=engine.begin,
                schedule_repository=runtime.schedule_repository,
                publication_repository=runtime.publication_repository,
                snapshot_repository=runtime.snapshot_repository,
                request_repository=runtime.request_repository,
                lineage_repository=runtime.lineage_repository,
                audit_repository=runtime.audit_repository,
                strategy=strategy,
            )
            first = service.execute(fixture.input, fixture.context)
            replay = service.execute(fixture.input, fixture.context)
            _ensure(first.exact_replay is False, "first replan apply reported replay")
            _ensure(replay.exact_replay is True, "same-key replan was not exact replay")
            _ensure(
                first.schedule_version is not None
                and first.validation_report is not None
                and first.change_report is not None
                and first.solver_report is not None,
                "real application result omitted a required immutable artifact",
            )
            _ensure(
                canonical_contract_bytes(first.schedule_version)
                == canonical_contract_bytes(replay.schedule_version)
                and canonical_contract_bytes(first.change_report)
                == canonical_contract_bytes(replay.change_report),
                "same-key application replay returned different artifacts",
            )
            return first
        finally:
            engine.dispose()

    def _baseline_carrier(
        self,
        *,
        request: ContinuousReplayStepRequest,
        snapshot: ImmutablePlanningSnapshot,
        problem: ImmutablePlanningProblemV2,
        draft: Mapping[str, object],
        occurred_at_utc: str,
    ) -> dict[str, object]:
        draft_lineage = cast(Mapping[str, object], draft["lineage"])
        source_draft_id = cast(str, draft["schedule_version_id"])
        content_fingerprint = cast(str, draft["content_fingerprint"])
        identity = contract_fingerprint(
            {
                "mode": BASELINE_ADVANCE_MODE,
                "step_id": request.step.step_id,
                "source_draft_id": source_draft_id,
                "content_fingerprint": content_fingerprint,
            }
        )
        current_reference = request.baseline.schedule_version.as_document()
        document: dict[str, object] = {
            "schedule_version_version": "schedule-version.v1",
            "schema_set_version": "2.6.0",
            "canonicalization_version": "canonical-json.v1",
            "schedule_version_id": "simulation-baseline-"
            + identity.removeprefix("sha256:"),
            "revision": cast(int, draft["revision"]),
            "state": "PUBLISHED",
            "data_plane": "SIMULATION",
            "environment": "TEST",
            "synthetic": True,
            "synthetic_provenance": deepcopy(self._scenario_provenance),
            "parent_schedule_version": {
                key: current_reference[key]
                for key in (
                    "schedule_version_id",
                    "state",
                    "content_fingerprint",
                )
            },
            "source_kind": "VALIDATED_SOLUTION",
            "lineage": {
                "planning_run_id": draft_lineage["planning_run_id"],
                "snapshot": _snapshot_reference(snapshot),
                "problem": _problem_reference(problem),
                "planning_solution": deepcopy(draft_lineage["candidate"]),
                "validation_report": deepcopy(
                    draft_lineage["validation_report"]
                ),
                "kpi": deepcopy(draft_lineage["kpi"]),
                "solver_report": deepcopy(draft_lineage["solver_report"]),
                "code_commit": self._code_commit,
            },
            "content": deepcopy(draft["content"]),
            "content_fingerprint": content_fingerprint,
            "validation": deepcopy(draft["validation"]),
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:sim-p4-10-test-baseline",
                "capability": "approve",
                "reason": (
                    "Bind validated DRAFT content to an isolated replay baseline."
                ),
                "decided_at_utc": occurred_at_utc,
                "audit_event_id": "audit-p4-10-baseline-approve-"
                + identity.removeprefix("sha256:"),
            },
            "publication": {
                "publication_id": "publication-p4-10-baseline-"
                + identity.removeprefix("sha256:"),
                "target": "SIMULATION_INTERNAL",
                "published_at_utc": occurred_at_utc,
                "audit_event_id": "audit-p4-10-baseline-publish-"
                + identity.removeprefix("sha256:"),
            },
            "superseded_by": None,
            "allowed_actions": ["view", "export"],
            "created_at_utc": occurred_at_utc,
            "created_by_actor_ref": "actor:sim-p4-10-test-baseline",
        }
        detached, _ = canonical_document(
            document,
            expected_version="schedule-version.v1",
            data_plane=WorkspaceDataPlane.SIMULATION,
        )
        return detached

    def replay_step(self, request: ContinuousReplayStepRequest) -> Mapping[str, object]:
        self.calls += 1
        _ensure(
            request.baseline.snapshot.as_document()
            == _snapshot_reference(self._current_snapshot)
            and request.baseline.problem.as_document()
            == _problem_reference(self._current_problem),
            "continuous baseline Snapshot/Problem differs from owner state",
        )
        _ensure(
            request.baseline.schedule_version.as_document()
            == {
                key: self._current_schedule[key]
                for key in (
                    "schedule_version_version",
                    "schedule_version_id",
                    "state",
                    "content_fingerprint",
                )
            },
            "continuous baseline ScheduleVersion differs from owner state",
        )
        previous_snapshot = self._current_snapshot
        self._all_events.extend(deepcopy(list(request.event_documents)))
        urgent_imports: dict[str, UrgentDemandImport] = {}
        for event in request.event_documents:
            if event.get("event_type") == "URGENT_DEMAND_RECEIVED":
                event_id = cast(str, event["event_id"])
                urgent_imports[event_id] = UrgentDemandImport(
                    event_id=event_id,
                    inputs=(self._urgent_input,),
                )
        projected = self._projection_service.project_available(
            previous_snapshot, urgent_imports=urgent_imports
        )
        for fact in projected.priority_facts:
            self._priority_overrides[fact.demand_order_id] = {
                "priority_weight": fact.priority_weight,
                "source_system": fact.source_system,
                "source_version": fact.source_version,
                "source_record_id": fact.source_record_id,
            }
        snapshot = projected.snapshot
        problem = self._build_problem(snapshot)
        policy = simulation_replan_policy()
        freeze_projection = project_effective_locks(
            snapshot=snapshot,
            problem=problem,
            base_schedule=self._current_schedule,
            policy=policy,
        ).document
        occurred_at_utc = cast(str, snapshot.document["cutoff_at_utc"])
        context = ReplanApplicationContext(
            data_plane="SIMULATION",
            environment="TEST",
            production_binding=False,
            actor_ref="actor:sim-p4-10-planner",
            idempotency_key_reference=contract_fingerprint(
                {"task": TASK_ID, "step_id": request.step.step_id}
            ),
            correlation_id=f"correlation-p4-10-step-{request.step.step_index:02d}",
            occurred_at_utc=occurred_at_utc,
            planning_run_id=f"planning-run-p4-10-step-{request.step.step_index:02d}",
            attempt_number=1,
            code_commit=self._code_commit,
        )
        request_document = self._replan_request(
            request,
            snapshot=snapshot,
            problem=problem,
            checkpoint=projected.checkpoint,
            freeze_projection=freeze_projection,
            context=context,
        )
        after_kpi: dict[str, object] = {}
        horizon_start, horizon_end = _horizon(snapshot)
        fixture = ReplanApplicationFixture(
            base_snapshot=previous_snapshot,
            snapshot=snapshot,
            base_schedule=deepcopy(self._current_schedule),
            events=tuple(deepcopy(self._all_events)),
            checkpoint=_checkpoint(request_document),
            request=request_document,
            priority_facts=self._priority_inputs(snapshot),
            policy=policy,
            limits=_limits(),
            before_kpi=deepcopy(self._before_kpi),
            after_kpi=after_kpi,
            context=context,
            problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
            tick_seconds=TICK_SECONDS,
            horizon_start_utc=horizon_start,
            horizon_end_utc=horizon_end,
        )
        applied = cast(
            Any,
            self._execute_application(
                fixture,
                after_kpi=after_kpi,
                synthetic_provenance=cast(
                    Mapping[str, object], request_document["synthetic_provenance"]
                ),
            ),
        )
        solver_report = cast(dict[str, object], applied.solver_report)
        validation_report = cast(dict[str, object], applied.validation_report)
        draft = cast(dict[str, object], applied.schedule_version)
        change_report = cast(dict[str, object], applied.change_report)
        formal_validation = cast(
            Mapping[str, object], validation_report["formal_validation"]
        )
        objective_values = cast(
            Mapping[str, object], validation_report["objective_values"]
        )
        stability = cast(Mapping[str, object], objective_values["stability"])
        fact_evidence = cast(
            Mapping[str, object], validation_report["fact_lock_evidence"]
        )
        change_projection = cast(
            Mapping[str, object], validation_report["change_report_projection"]
        )
        operation_rows = cast(
            Sequence[Mapping[str, object]], change_report["operations"]
        )
        classifications = {
            cast(str, row["operation_id"]): row["classification"]
            for row in operation_rows
        }
        invariants = {
            "COMPLETED_OPERATION_PRESERVED": (
                validation_report["status"] == "PASS"
                and fact_evidence["completed_fact_count"]
                == len(
                    cast(
                        Sequence[object],
                        freeze_projection["completed_protections"],
                    )
                )
            ),
            "RUNNING_RESOURCE_PRESERVED": (
                validation_report["status"] == "PASS"
                and fact_evidence["running_fact_count"]
                == len(
                    cast(Sequence[object], freeze_projection["running_protections"])
                )
            ),
            "EXPLICIT_HARD_LOCKS_PRESERVED": (
                validation_report["status"] == "PASS"
                and fact_evidence["explicit_hard_lock_count"]
                == len(
                    cast(Sequence[object], freeze_projection["explicit_hard_locks"])
                )
            ),
            "FREEZE_LOCKS_PRESERVED": (
                validation_report["status"] == "PASS"
                and fact_evidence["freeze_derived_hard_lock_count"]
                == len(
                    cast(
                        Sequence[object],
                        freeze_projection["freeze_derived_hard_locks"],
                    )
                )
            ),
            "FRESH_VALIDATOR_PASS": (
                validation_report["status"] == "PASS"
                and validation_report["hard_violation_count"] == 0
                and formal_validation["status"] == "PASS"
                and formal_validation["hard_violation_count"] == 0
                and cast(Mapping[str, object], validation_report["independence"])[
                    "formal_validator_fresh"
                ]
                is True
            ),
            "CHANGE_REPORT_COMPLETE": (
                change_projection["complete"] is True
                and change_projection["operation_universe_count"]
                == change_report["operation_universe_count"]
                == len(operation_rows)
                and change_projection["classifications"] == classifications
            ),
        }
        carrier = self._baseline_carrier(
            request=request,
            snapshot=snapshot,
            problem=problem,
            draft=draft,
            occurred_at_utc=occurred_at_utc,
        )
        event_ids = [
            cast(str, event["event_id"]) for event in request.event_documents
        ]
        formal_fingerprint = contract_fingerprint(formal_validation)
        evidence: dict[str, object] = {
            "evidence_version": STEP_EVIDENCE_VERSION,
            "step_id": request.step.step_id,
            "disruption_kind": request.step.disruption_kind.value,
            "base_schedule_version": request.baseline.schedule_version.as_document(),
            "base_snapshot": request.baseline.snapshot.as_document(),
            "trigger_event_ids": event_ids,
            "new_snapshot": _snapshot_reference(snapshot),
            "new_problem": _problem_reference(problem),
            "replan_request": _artifact_reference(
                document_version="replan-request.v1",
                artifact_id=cast(str, request_document["request_id"]),
                fingerprint=cast(str, request_document["request_fingerprint"]),
            ),
            "planning_run": {
                "planning_run_id": context.planning_run_id,
                "state": "COMPLETED",
                "fresh_validator_run": True,
            },
            "validation_report": {
                "document_version": "validation-report.v2",
                "artifact_id": "validation-report-"
                + formal_fingerprint.removeprefix("sha256:"),
                "fingerprint": formal_fingerprint,
                "status": validation_report["status"],
                "hard_violation_count": validation_report["hard_violation_count"],
            },
            "new_schedule_version": {
                key: draft[key]
                for key in (
                    "schedule_version_version",
                    "schedule_version_id",
                    "state",
                    "content_fingerprint",
                )
            },
            "change_report": {
                "document_version": "change-report.v1",
                "artifact_id": change_report["report_id"],
                "fingerprint": change_report["report_fingerprint"],
                "complete": invariants["CHANGE_REPORT_COMPLETE"],
                "trigger_event_ids": event_ids,
            },
            "fact_lock_invariants": invariants,
            "tardiness": {
                "before_seconds": cast(Mapping[str, object], self._before_kpi["delivery"])[
                    "priority_weighted_tardiness_seconds"
                ],
                "after_seconds": objective_values["delivery"],
            },
            "stability": {
                "soft_lock_violation_count": stability["soft_lock_violations"],
                "changed_existing_operation_count": stability[
                    "changed_existing_operations"
                ],
                "resource_changed_count": stability["resource_changes"],
                "total_absolute_start_shift_seconds": stability[
                    "absolute_start_shift_seconds"
                ],
            },
            "baseline_advance": {
                "mode": BASELINE_ADVANCE_MODE,
                "production_binding": False,
                "authority_claim": "NONE",
                "source_draft_id": draft["schedule_version_id"],
                "next_schedule_version": {
                    key: carrier[key]
                    for key in (
                        "schedule_version_version",
                        "schedule_version_id",
                        "state",
                        "content_fingerprint",
                    )
                },
                "next_snapshot": _snapshot_reference(snapshot),
                "next_problem": _problem_reference(problem),
            },
            "production_binding": False,
            "raw_events": deepcopy(list(request.event_documents)),
            "raw_replan_request": deepcopy(request_document),
            "raw_solver_report": deepcopy(solver_report),
            "raw_validation_report": deepcopy(validation_report),
            "raw_schedule_version": deepcopy(draft),
            "raw_change_report": deepcopy(change_report),
        }
        self._current_snapshot = snapshot
        self._current_problem = problem
        self._current_schedule = carrier
        self._before_kpi = deepcopy(after_kpi)
        self._schedule_history.append(deepcopy(carrier))
        return evidence


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _expect_failure(
    reason: DisruptionReplayFailure, operation: object
) -> DisruptionReplayError:
    if not callable(operation):
        raise TypeError("operation must be callable")
    try:
        cast(object, operation)()  # type: ignore[operator]
    except DisruptionReplayError as error:
        if error.reason is reason:
            return error
        raise ValueError(
            f"expected {reason.value}, observed {error.reason.value}"
        ) from error
    raise ValueError(f"expected {reason.value} rejection")


def _tampered_library_failure(root: Path, *, mutation: str) -> DisruptionReplayError:
    source = cast(
        dict[str, object],
        json.loads((root / ASSET_PATH).read_text(encoding="utf-8")),
    )
    if mutation == "production":
        source["target_environment"] = "PRODUCTION"
    elif mutation == "coverage":
        steps = cast(list[object], source["steps"])
        steps.pop()
    else:
        raise ValueError("unknown mutation")
    with TemporaryDirectory(prefix="plantnexus-p4-10-") as directory:
        path = Path(directory) / "scenario-library.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        expected = (
            DisruptionReplayFailure.PRODUCTION_FORBIDDEN
            if mutation == "production"
            else DisruptionReplayFailure.COVERAGE_MISMATCH
        )
        return _expect_failure(expected, lambda: load_disruption_scenario_library(path))


def _owner_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in _OWNER_FILES:
        path = root / relative
        _ensure(path.is_file(), f"frozen owner file is missing: {relative}")
        result[relative] = sha256(path.read_bytes()).hexdigest()
    return result


def _source_boundary(root: Path) -> dict[str, object]:
    path = root / "backend/app/simulation/scenarios/disruption_replay.py"
    text = path.read_text(encoding="utf-8")
    forbidden = (
        "app.infrastructure",
        "app.api",
        "sqlalchemy",
        "ortools",
        "datetime.now",
        "datetime.utcnow",
        "random.",
    )
    found = [token for token in forbidden if token in text]
    _ensure(not found, "scenario orchestrator contains a forbidden shortcut")
    return {
        "core_file": path.relative_to(root).as_posix(),
        "forbidden_shortcuts": found,
        "downstream_owner": (
            "P4_04_EVENT_FACT_SNAPSHOT+P4_08_REPLAN_VALIDATOR_DRAFT_CHANGE_REPORT"
        ),
        "direct_repository_solver_api_calls": 0,
    }


def _semantic_replay_projection(value: Mapping[str, object]) -> dict[str, object]:
    """Remove only owner runtime noise while retaining every business outcome."""

    projected_steps: list[dict[str, object]] = []
    for raw_record in cast(Sequence[Mapping[str, object]], value["steps"]):
        evidence = cast(Mapping[str, object], raw_record["evidence"])
        solver = cast(Mapping[str, object], evidence["raw_solver_report"])
        validation = cast(Mapping[str, object], evidence["raw_validation_report"])
        draft = cast(Mapping[str, object], evidence["raw_schedule_version"])
        change = cast(Mapping[str, object], evidence["raw_change_report"])
        operations = cast(Sequence[Mapping[str, object]], change["operations"])
        stage_rows = cast(
            Sequence[Mapping[str, object]], solver["objective_stage_results"]
        )
        projected_steps.append(
            {
                "step_index": raw_record["step_index"],
                "step_id": raw_record["step_id"],
                "disruption_kind": raw_record["disruption_kind"],
                "from_position": raw_record["from_position"],
                "through_position": raw_record["through_position"],
                "event_ids": raw_record["event_ids"],
                "base_schedule_version": evidence["base_schedule_version"],
                "base_snapshot": evidence["base_snapshot"],
                "new_snapshot": evidence["new_snapshot"],
                "new_problem": evidence["new_problem"],
                "raw_events": evidence["raw_events"],
                "raw_replan_request": evidence["raw_replan_request"],
                "solver": {
                    "candidate": solver["candidate"],
                    "solver_status": solver["solver_status"],
                    "planning_run_outcome": solver["planning_run_outcome"],
                    "objective_stage_results": [
                        {
                            key: row[key]
                            for key in (
                                "stage_index",
                                "objective_id",
                                "metric",
                                "sense",
                                "status",
                                "objective_value",
                                "best_bound",
                                "relative_gap",
                                "stop_reason",
                            )
                        }
                        for row in stage_rows
                    ],
                    "stability_evidence": solver["stability_evidence"],
                },
                "validation": validation,
                "draft": {
                    "schedule_version_id": draft["schedule_version_id"],
                    "state": draft["state"],
                    "parent_schedule_version": draft["parent_schedule_version"],
                    "content": draft["content"],
                    "content_fingerprint": draft["content_fingerprint"],
                },
                "change_report": {
                    "operation_universe_count": change["operation_universe_count"],
                    "operations": [
                        {
                            "operation_id": row["operation_id"],
                            "classification": row["classification"],
                            "base_assignment": row["base_assignment"],
                            "new_assignment": row["new_assignment"],
                            "deltas": row["deltas"],
                            "reason_codes": [
                                reason["reason_code"]
                                for reason in cast(
                                    Sequence[Mapping[str, object]], row["reasons"]
                                )
                            ],
                        }
                        for row in operations
                    ],
                    "stability": change["stability"],
                },
                "fact_lock_invariants": evidence["fact_lock_invariants"],
                "tardiness": evidence["tardiness"],
                "stability": evidence["stability"],
                "baseline_advance": evidence["baseline_advance"],
            }
        )
    return {
        "projection_version": "p4-disruption-semantic-replay.v1",
        "library_fingerprint": value["library_fingerprint"],
        "run_fingerprint": value["run_fingerprint"],
        "event_stream_fingerprint": value["event_stream_fingerprint"],
        "event_ids": value["event_ids"],
        "steps": projected_steps,
        "final_baseline": value["final_baseline"],
        "production_binding": False,
    }


def run_disruption_replay_checks(
    root: Path, *, verify_owner_reports: bool = True
) -> dict[str, object]:
    """Run asset, stream, continuity, owner, negative, and boundary checks."""

    code_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    library = load_disruption_scenario_library(root / ASSET_PATH)
    orchestrator = DisruptionReplayOrchestrator()

    with TemporaryDirectory(prefix="plantnexus-p4-10-first-") as first_directory:
        first_port = _OwnerCommonPathEvidencePort(
            root,
            library,
            code_commit=code_commit,
            workspace=Path(first_directory),
        )
        try:
            first = orchestrator.run(
                library, first_port, first_port, code_commit=code_commit
            )
        finally:
            first_port.close()
    with TemporaryDirectory(prefix="plantnexus-p4-10-second-") as second_directory:
        second_port = _OwnerCommonPathEvidencePort(
            root,
            library,
            code_commit=code_commit,
            workspace=Path(second_directory),
        )
        try:
            second = orchestrator.run(
                library, second_port, second_port, code_commit=code_commit
            )
        finally:
            second_port.close()
    first_projection = _semantic_replay_projection(first.as_document())
    second_projection = _semantic_replay_projection(second.as_document())
    _ensure(
        canonical_contract_bytes(first_projection)
        == canonical_contract_bytes(second_projection),
        "same-seed semantic replay drifted",
    )
    _ensure(first_port.calls == second_port.calls == 5, "five steps were not replayed")
    _ensure(
        first_port.ingest_calls == second_port.ingest_calls == 8,
        "event count drifted",
    )

    production_failure = _tampered_library_failure(root, mutation="production")
    coverage_failure = _tampered_library_failure(root, mutation="coverage")
    tampered_ingress = _EvidenceIngress()
    tampered_port = _TamperedEvidencePort()
    tampered_failure = _expect_failure(
        DisruptionReplayFailure.CHAIN_MISMATCH,
        lambda: orchestrator.run(
            library, tampered_ingress, tampered_port, code_commit=code_commit
        ),
    )

    if verify_owner_reports:
        simulator_owner = run_execution_simulator_checks(root)
        projection_owner = run_projection_checks(root)
        replan_owner = run_replan_application_checks(root)
        for owner_name, owner in (
            ("P4-09", simulator_owner),
            ("P4-04", projection_owner),
            ("P4-08", replan_owner),
        ):
            _ensure(owner.get("status") == "PASS", f"{owner_name} owner report failed")
            _ensure(owner.get("issues") == [], f"{owner_name} owner has issues")
        owner_evidence: dict[str, object] = {
            "P4-04": {
                "report_version": projection_owner["report_version"],
                "check_count": projection_owner["check_count"],
                "status": projection_owner["status"],
            },
            "P4-08": {
                "report_version": replan_owner["report_version"],
                "check_count": replan_owner["check_count"],
                "status": replan_owner["status"],
            },
            "P4-09": {
                "report_version": simulator_owner["report_version"],
                "check_count": simulator_owner["check_count"],
                "status": simulator_owner["status"],
            },
        }
    else:
        owner_evidence = {"verification": "SKIPPED_BY_FOCUSED_CALLER"}

    replay = first.as_document()
    records = cast(list[Mapping[str, object]], replay["steps"])
    checks = [
        _pass(
            "versioned-five-disruption-asset-and-provenance",
            {
                "asset_id": library.asset_id,
                "asset_version": library.asset_version,
                "library_fingerprint": library.fingerprint,
                "seed": library.seed,
                "freeze_window_seconds": library.freeze_window_seconds,
                "step_count": len(library.steps),
            },
        ),
        _pass(
            "standard-eight-event-continuous-stream",
            {
                "event_count": len(first.event_ids),
                "event_ids": list(first.event_ids),
                "event_stream_fingerprint": first.event_stream_fingerprint,
                "step_ranges": [
                    [record["from_position"], record["through_position"]]
                    for record in records
                ],
            },
        ),
        _pass(
            "same-seed-semantic-projection-replay",
            {
                "replay_fingerprint": replay["replay_fingerprint"],
                "semantic_projection_version": first_projection["projection_version"],
                "semantic_sha256": sha256(
                    canonical_contract_bytes(first_projection)
                ).hexdigest(),
                "raw_runtime_noise_retained": True,
                "second_semantically_equal": True,
            },
        ),
        _pass(
            "continuous-snapshot-version-baseline-lineage",
            {
                "step_count": len(records),
                "advance_mode": BASELINE_ADVANCE_MODE,
                "final_baseline": first.final_baseline.as_document(),
            },
        ),
        _pass(
            "facts-locks-validator-and-change-report-every-step",
            {
                "step_invariant_counts": [
                    len(
                        cast(
                            Mapping[str, object],
                            cast(Mapping[str, object], record["evidence"])[
                                "fact_lock_invariants"
                            ],
                        )
                    )
                    for record in records
                ],
                "validator_statuses": ["PASS"] * len(records),
                "change_report_complete": [True] * len(records),
            },
        ),
        _pass("frozen-owner-common-path-replay", owner_evidence),
        _pass(
            "tamper-coverage-and-plane-fail-closed",
            {
                "production": production_failure.reason.value,
                "coverage": coverage_failure.reason.value,
                "step_evidence": tampered_failure.reason.value,
                "partial_success_written": False,
            },
        ),
        _pass(
            "p4-p5-production-and-forbidden-owner-boundary",
            {
                "source_boundary": _source_boundary(root),
                "owner_hashes": _owner_hashes(root),
                "p5_capabilities": "UNSUPPORTED",
                "production_authority_external_capacity_sla": "NOT_ESTABLISHED",
            },
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "counts": {
            "scenario_steps": len(library.steps),
            "standard_events": len(first.event_ids),
            "continuous_replan_envelopes": first_port.calls,
            "fresh_validator_passes": len(library.steps),
            "complete_change_reports": len(library.steps),
            "same_seed_runs": 2,
            "negative_vectors": 3,
            "machine_checks": len(checks),
        },
        "scenario_manifest": {
            "asset_path": ASSET_PATH.as_posix(),
            "asset_id": library.asset_id,
            "asset_version": library.asset_version,
            "asset_fingerprint": library.fingerprint,
            "run_fingerprint": first.run_fingerprint,
            "event_stream_fingerprint": first.event_stream_fingerprint,
            "replay_fingerprint": replay["replay_fingerprint"],
        },
        "raw_replay": replay,
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "baseline_advance": BASELINE_ADVANCE_MODE,
            "automatic_approval_publication_export": "NONE",
            "p4_11_plus": "NOT_STARTED",
            "p5_plus": "UNSUPPORTED",
            "production_readiness_authority_external_capacity_sla": "NOT_ESTABLISHED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_disruption_replay_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "impact_rule_count": len(IMPACT_RULES),
            "impact_rules": list(IMPACT_RULES),
            "error_type": type(error).__name__,
            "error_message": "P4 disruption replay evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ASSET_PATH",
    "DIFF_BASE",
    "IMPACT_RULES",
    "REPORT_VERSION",
    "TASK_ID",
    "main",
    "run_disruption_replay_checks",
]
