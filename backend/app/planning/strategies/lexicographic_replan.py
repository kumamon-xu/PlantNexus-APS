"""P4 Simulation-only global Delivery→Stability→Makespan strategy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import cast

from app.domain.execution_contracts import (
    contract_fingerprint,
    require_p4_document,
    solver_report_fingerprint,
)
from app.domain.types import format_utc_instant
from app.domain.workspace_contracts import require_workspace_document
from app.planning.backends.cp_sat.backend import parameters_for_limits
from app.planning.backends.cp_sat.replan_backend import (
    LexicographicReplanBackend,
    ReplanRoundReport,
)
from app.planning.contracts import SolverParameterDocument, SolverStatus
from app.planning.policy.contracts import SolveLimitsDocument, validate_solve_limits
from app.planning.policy.delivery import (
    SIMULATION_DELIVERY_SOURCE_SYSTEM,
    SIMULATION_DELIVERY_SOURCE_VERSION,
)
from app.planning.policy.freeze_window import simulation_replan_policy
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.validation.replan_candidate_validator import (
    ReplanCandidateValidationReport,
)


REPLAN_STRATEGY_ID = "global-lexicographic-replan-cp-sat"
REPLAN_STRATEGY_VERSION = "global-lexicographic-replan-cp-sat.v1"
REPLAN_SOLVER_REPORT_NAME = "Google-OR-Tools-CP-SAT"
_COMMIT = re.compile(r"^(?:uncommitted|[0-9a-f]{40})$")


@dataclass(frozen=True)
class LexicographicReplanResult:
    solver_report: dict[str, object]
    round_reports: tuple[ReplanRoundReport, ...]
    validation_reports: tuple[ReplanCandidateValidationReport, ...]

    @property
    def candidate(self) -> Mapping[str, object] | None:
        value = self.solver_report["candidate"]
        return cast(Mapping[str, object] | None, value)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _reference(
    *,
    document_version: str,
    artifact_id: object,
    fingerprint: object,
) -> dict[str, object]:
    if not isinstance(artifact_id, str) or not isinstance(fingerprint, str):
        raise ValueError("artifact reference identity is incomplete")
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": fingerprint,
    }


def _limits_reference(limits: SolveLimitsDocument) -> dict[str, object]:
    return {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }


def _policy_reference(policy: Mapping[str, object]) -> dict[str, object]:
    return {
        "planning_policy_version": policy["planning_policy_version"],
        "policy_id": policy["policy_id"],
        "policy_revision": policy["policy_revision"],
        "policy_fingerprint": contract_fingerprint(policy),
    }


def _report_parameters(
    limits: SolveLimitsDocument,
) -> list[SolverParameterDocument]:
    native = {item["name"]: item for item in parameters_for_limits(limits)}
    parameters: list[SolverParameterDocument] = [
        native["log_search_progress"],
        native["max_time_in_seconds"],
        {
            "name": "max_wall_time_seconds",
            "value": limits["max_wall_time_seconds"],
            "source": "SOLVE_LIMITS",
        },
        {
            "name": "max_workers",
            "value": limits["max_workers"],
            "source": "SOLVE_LIMITS",
        },
        native["num_search_workers"],
        {
            "name": "objective_round_order",
            "value": "OBJ-001>OBJ-002.1>OBJ-002.2>OBJ-002.3>OBJ-002.4>OBJ-003",
            "source": "BACKEND",
        },
        {
            "name": "random_seed",
            "value": limits["random_seed"],
            "source": "SOLVE_LIMITS",
        },
        {
            "name": "stage_budget_allocation",
            "value": "EQUAL_POLICY_STAGE_SHARE",
            "source": "BACKEND",
        },
    ]
    parameters.sort(key=lambda item: item["name"])
    return parameters


def _base_assignments(base_schedule: Mapping[str, object]) -> Sequence[object]:
    content = _mapping(base_schedule.get("content"), "base_schedule.content")
    assignments = content.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("base_schedule.content.assignments must be an array")
    return assignments


def _validate_base_schedule(base_schedule: Mapping[str, object]) -> None:
    version = base_schedule.get("schedule_version_version")
    if version == "schedule-version.v1":
        require_workspace_document(base_schedule)
    elif version == "schedule-version.v2":
        require_p4_document(base_schedule)
    else:
        raise ValueError("base schedule must be schedule-version.v1/v2")
    if (
        base_schedule.get("state") != "PUBLISHED"
        or base_schedule.get("data_plane") != "SIMULATION"
        or base_schedule.get("synthetic") is not True
    ):
        raise ValueError("P4 replan requires an immutable Simulation PUBLISHED base")


def _validate_projection_identity(projection: Mapping[str, object]) -> None:
    if (
        projection.get("effective_lock_projection_version")
        != "effective-lock-projection.v1"
        or projection.get("data_plane") != "SIMULATION"
    ):
        raise ValueError("effective lock projection version/plane is invalid")
    basis = dict(projection)
    observed = basis.pop("projection_fingerprint", None)
    if observed != contract_fingerprint(basis):
        raise ValueError("effective lock projection fingerprint is invalid")


def _validate_inputs(
    *,
    problem: PlanningProblemDocumentV2,
    base_schedule: Mapping[str, object],
    effective_locks: Mapping[str, object],
    replan_request: Mapping[str, object],
    policy: Mapping[str, object],
    limits: SolveLimitsDocument,
) -> None:
    require_p4_document(policy)
    require_p4_document(replan_request)
    validate_solve_limits(limits)
    _validate_base_schedule(base_schedule)
    _validate_projection_identity(effective_locks)
    if dict(policy) != simulation_replan_policy():
        raise ValueError("only the approved versioned P4 Simulation policy may execute")
    if policy.get("data_plane") != "SIMULATION" or limits["data_plane"] != "SIMULATION":
        raise ValueError("P4 replan execution has no Production authorization")
    source = limits["limits_source"]
    if (
        source["source_system"] != SIMULATION_DELIVERY_SOURCE_SYSTEM
        or source["source_version"] != SIMULATION_DELIVERY_SOURCE_VERSION
    ):
        raise ValueError("SolveLimits source is not the approved Simulation source")
    for index, demand in enumerate(problem["delivery_demands"]):
        if (
            demand["priority_source_system"] != SIMULATION_DELIVERY_SOURCE_SYSTEM
            or demand["priority_source_version"] != SIMULATION_DELIVERY_SOURCE_VERSION
        ):
            raise ValueError(
                f"delivery_demands[{index}] has an unapproved priority source"
            )

    projected_base = _mapping(
        effective_locks.get("base_schedule_version"),
        "effective_locks.base_schedule_version",
    )
    expected_base = {
        "schedule_version_version": base_schedule["schedule_version_version"],
        "schedule_version_id": base_schedule["schedule_version_id"],
        "state": "PUBLISHED",
        "content_fingerprint": base_schedule["content_fingerprint"],
    }
    if dict(projected_base) != expected_base:
        raise ValueError("effective lock projection references a stale base schedule")
    projected_problem = _mapping(
        effective_locks.get("new_problem"), "effective_locks.new_problem"
    )
    expected_problem = _reference(
        document_version="planning-problem.v2",
        artifact_id=(
            "planning-problem-v2-"
            + problem["problem_hash"].removeprefix("sha256:")
        ),
        fingerprint=problem["problem_hash"],
    )
    if dict(projected_problem) != expected_problem:
        raise ValueError("effective lock projection references another PlanningProblem")
    if dict(
        _mapping(effective_locks.get("planning_policy"), "effective_locks.policy")
    ) != _policy_reference(policy):
        raise ValueError("effective lock projection policy reference is stale")

    request_base = _mapping(
        replan_request.get("base_schedule_version"),
        "replan_request.base_schedule_version",
    )
    if dict(request_base) != expected_base:
        raise ValueError("ReplanRequest references a stale base schedule")
    if dict(
        _mapping(replan_request.get("new_problem"), "replan_request.new_problem")
    ) != expected_problem:
        raise ValueError("ReplanRequest references another PlanningProblem")
    for request_field, projection_field in (
        ("new_snapshot", "new_snapshot"),
        ("freeze_resolution", "freeze_resolution"),
    ):
        if replan_request.get(request_field) != effective_locks.get(projection_field):
            raise ValueError(f"ReplanRequest {request_field} differs from projection")
    if dict(
        _mapping(replan_request.get("planning_policy"), "replan_request.policy")
    ) != _policy_reference(policy):
        raise ValueError("ReplanRequest policy reference is stale")
    if dict(
        _mapping(replan_request.get("solve_limits"), "replan_request.solve_limits")
    ) != _limits_reference(limits):
        raise ValueError("ReplanRequest SolveLimits reference is stale")


def _outcome(status: SolverStatus) -> dict[str, object]:
    if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        return {"state": "SOLVED", "product_error": None}
    mapping = {
        SolverStatus.INFEASIBLE: ("INFEASIBLE", "INFEASIBLE"),
        SolverStatus.UNKNOWN: (
            "NO_SOLUTION_WITHIN_LIMIT",
            "NO_SOLUTION_WITHIN_LIMIT",
        ),
        SolverStatus.MODEL_INVALID: ("MODEL_INVALID", "MODEL_INVALID"),
        SolverStatus.CANCELLED: ("CANCELLED", None),
        SolverStatus.FAILED: ("FAILED", "SYSTEM_ERROR"),
    }
    state, error = mapping[status]
    return {
        "state": state,
        "product_error": (
            None if error is None else {"category": error, "code": error}
        ),
    }


def _relative_gap(value: object, bound: object, status: SolverStatus) -> float | None:
    if not isinstance(value, int) or not isinstance(bound, int):
        return None
    if status is SolverStatus.OPTIMAL:
        return 0.0
    return max(0.0, (value - bound) / max(1, value))


def _stage_results(
    status: SolverStatus,
    evidence: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    delivery = evidence["delivery"]
    stability = evidence["stability"]
    makespan = evidence["makespan"]
    return [
        {
            "stage_index": 1,
            "objective_id": "OBJ-001",
            "metric": "WEIGHTED_TARDINESS_SECONDS",
            "sense": "MINIMIZE",
            "status": status.value,
            "objective_value": delivery["objective_value"],
            "best_bound": delivery["best_bound"],
            "relative_gap": _relative_gap(
                delivery["objective_value"], delivery["best_bound"], status
            ),
            "allocated_wall_time_seconds": delivery[
                "allocated_wall_time_seconds"
            ],
            "solve_seconds": delivery["solve_seconds"],
            "stop_reason": delivery["stop_reason"],
        },
        {
            "stage_index": 2,
            "objective_id": "OBJ-002",
            "metric": "STABILITY_VECTOR",
            "sense": "LEXICOGRAPHIC_MINIMIZE",
            "status": status.value,
            "objective_value": stability["objective_value"],
            "best_bound": stability["best_bound"],
            "relative_gap": None,
            "allocated_wall_time_seconds": stability[
                "allocated_wall_time_seconds"
            ],
            "solve_seconds": stability["solve_seconds"],
            "stop_reason": stability["stop_reason"],
        },
        {
            "stage_index": 3,
            "objective_id": "OBJ-003",
            "metric": "MAKESPAN_SECONDS",
            "sense": "MINIMIZE",
            "status": status.value,
            "objective_value": makespan["objective_value"],
            "best_bound": makespan["best_bound"],
            "relative_gap": _relative_gap(
                makespan["objective_value"], makespan["best_bound"], status
            ),
            "allocated_wall_time_seconds": makespan[
                "allocated_wall_time_seconds"
            ],
            "solve_seconds": makespan["solve_seconds"],
            "stop_reason": makespan["stop_reason"],
        },
    ]


class LexicographicReplanStrategy:
    """The sole P4 global replan strategy; it owns no persistence or state."""

    def __init__(self, backend: LexicographicReplanBackend | None = None) -> None:
        self._backend = LexicographicReplanBackend() if backend is None else backend

    def solve(
        self,
        problem: PlanningProblemDocumentV2,
        policy: Mapping[str, object],
        limits: SolveLimitsDocument,
        *,
        base_schedule: Mapping[str, object],
        effective_locks: Mapping[str, object],
        replan_request: Mapping[str, object],
        planning_run_id: str,
        code_commit: str,
    ) -> LexicographicReplanResult:
        """Validate frozen lineage, solve globally, and emit SolverReport v2."""

        if (
            not planning_run_id
            or len(planning_run_id) > 256
            or any(character.isspace() for character in planning_run_id)
        ):
            raise ValueError("planning_run_id must be a canonical identifier")
        if _COMMIT.fullmatch(code_commit) is None:
            raise ValueError(
                "code_commit must be 'uncommitted' or 40 lowercase hexadecimal characters"
            )
        _validate_inputs(
            problem=problem,
            base_schedule=base_schedule,
            effective_locks=effective_locks,
            replan_request=replan_request,
            policy=policy,
            limits=limits,
        )
        started = datetime.now(UTC)
        backend_result = self._backend.solve_with_evidence(
            problem,
            base_assignments=_base_assignments(base_schedule),
            effective_locks=effective_locks,
            limits=limits,
        )
        finished = datetime.now(UTC)
        status = backend_result.solver_status
        stages = _stage_results(status, backend_result.stage_evidence)
        candidate = backend_result.candidate
        stability = (
            None
            if backend_result.objective_values is None
            else backend_result.objective_values["stability"]
        )
        request_reference = {
            "replan_request_version": replan_request["replan_request_version"],
            "request_id": replan_request["request_id"],
            "request_fingerprint": replan_request["request_fingerprint"],
        }
        identity = self._backend.identity
        diagnostics = list(backend_result.diagnostics)
        report: dict[str, object] = {
            "solver_report_version": "solver-report.v2",
            "schema_set_version": "2.8.0",
            "canonicalization_version": "canonical-json.v1",
            "report_id": "pending",
            "report_fingerprint": "pending",
            "evidence_kind": "SOLVER_RUN",
            "replan_request": request_reference,
            "planning_run_id": planning_run_id,
            "started_at_utc": format_utc_instant(started),
            "finished_at_utc": format_utc_instant(finished),
            "base_problem": dict(
                _mapping(replan_request["base_problem"], "replan_request.base_problem")
            ),
            "new_problem": dict(
                _mapping(replan_request["new_problem"], "replan_request.new_problem")
            ),
            "policy": _policy_reference(policy),
            "limits": _limits_reference(limits),
            "candidate": candidate,
            "solver_status": status.value,
            "planning_run_outcome": _outcome(status),
            "solver": {
                **identity,
                "solver_name": REPLAN_SOLVER_REPORT_NAME,
                "parameters": _report_parameters(limits),
            },
            "objective_stage_results": stages,
            "stability_evidence": stability,
            "timings": {
                "model_build_seconds": backend_result.telemetry[
                    "model_build_seconds"
                ],
                "first_feasible_seconds": backend_result.telemetry[
                    "first_feasible_seconds"
                ],
                "solve_seconds": backend_result.telemetry["solve_seconds"],
                "validation_seconds": backend_result.telemetry[
                    "validation_seconds"
                ],
                "total_seconds": backend_result.telemetry["total_seconds"],
            },
            "model_metrics": backend_result.telemetry["model_metrics"],
            "memory_peak_mb": backend_result.telemetry["python_memory_peak_mb"],
            "diagnostics": diagnostics,
            "provenance": {
                "code_commit": code_commit,
                "spec_version": "0.3.0",
                "schema_set_version": "2.8.0",
                "canonicalization_version": "canonical-json.v1",
                "constraint_contract_version": "constraint-rule-sheet.v1",
                "objective_policy_version": "objective-policy.v2",
                "state_machine_contract_version": "state-machines.v1",
                "error_registry_version": "error-code-registry.v2",
            },
        }
        fingerprint = solver_report_fingerprint(report)
        report["report_fingerprint"] = fingerprint
        report["report_id"] = "solver-report-" + fingerprint.removeprefix("sha256:")
        require_p4_document(report)
        return LexicographicReplanResult(
            solver_report=report,
            round_reports=backend_result.round_reports,
            validation_reports=backend_result.validation_reports,
        )


__all__ = [
    "REPLAN_STRATEGY_ID",
    "REPLAN_STRATEGY_VERSION",
    "REPLAN_SOLVER_REPORT_NAME",
    "LexicographicReplanResult",
    "LexicographicReplanStrategy",
]
