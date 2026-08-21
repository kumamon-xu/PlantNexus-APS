"""The sole approved P2 strategy: one global CP-SAT OBJ-001 run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import re
from typing import cast

from app.domain.contracts import ValidationReportDocumentV2
from app.domain.types import format_utc_instant
from app.planning.backends.cp_sat.backend import (
    CpSatBackend,
    parameters_for_limits,
)
from app.planning.backends.cp_sat.core_constraints import precheck_core_problem
from app.planning.contracts import (
    CANONICALIZATION_VERSION,
    CONSTRAINT_CONTRACT_VERSION,
    ERROR_REGISTRY_VERSION,
    OBJECTIVE_POLICY_VERSION,
    PLANNING_SOLUTION_VERSION,
    SCHEMA_SET_VERSION,
    SOLVER_REPORT_VERSION,
    STATE_MACHINE_CONTRACT_VERSION,
    SolverParameterDocument,
    PlanningSolutionDocument,
    SolverReportDocument,
    SolverStatus,
    canonical_contract_bytes,
    contract_fingerprint,
    outcome_for_solver_status,
    validate_contract_bundle,
)
from app.planning.policy.contracts import PlanningPolicyDocument, SolveLimitsDocument
from app.planning.policy.delivery import validate_simulation_delivery_execution
from app.planning.problem.contracts import PlanningProblemDocumentV2


STRATEGY_ID = "global-cp-sat"
STRATEGY_VERSION = "global-cp-sat-strategy.v1"
SOLVER_REPORT_NAME = "Google-OR-Tools-CP-SAT"
_COMMIT_PATTERN = re.compile(r"^(?:uncommitted|[0-9a-f]{40})$")


@dataclass(frozen=True)
class GlobalStrategyResult:
    solution: PlanningSolutionDocument
    solver_report: SolverReportDocument
    validation_report: ValidationReportDocumentV2 | None


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
            "name": "random_seed",
            "value": limits["random_seed"],
            "source": "SOLVE_LIMITS",
        },
    ]
    parameters.sort(key=lambda item: item["name"])
    return parameters


def _report_id(planning_run_id: str, solution_fingerprint: str) -> str:
    payload: Mapping[str, object] = {
        "planning_run_id": planning_run_id,
        "solution_fingerprint": solution_fingerprint,
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
    }
    return f"solver-report-global-{sha256(canonical_contract_bytes(payload)).hexdigest()}"


class GlobalCpSatStrategy:
    """Solve all active operations together with no decomposition or fallback."""

    def __init__(self, backend: CpSatBackend | None = None) -> None:
        self._backend = CpSatBackend() if backend is None else backend

    def solve(
        self,
        problem: PlanningProblemDocumentV2,
        policy: PlanningPolicyDocument,
        limits: SolveLimitsDocument,
        *,
        planning_run_id: str,
        code_commit: str,
    ) -> GlobalStrategyResult:
        """Run precheck → one global Backend solve → independent Validator gate."""

        if (
            not planning_run_id
            or len(planning_run_id) > 256
            or any(character.isspace() for character in planning_run_id)
        ):
            raise ValueError("planning_run_id must be a canonical identifier")
        if _COMMIT_PATTERN.fullmatch(code_commit) is None:
            raise ValueError(
                "code_commit must be 'uncommitted' or 40 lowercase hexadecimal characters"
            )
        precheck_core_problem(cast(Mapping[str, object], problem))
        validate_simulation_delivery_execution(problem, policy, limits)

        started = datetime.now(UTC)
        backend_result = self._backend.solve_delivery_with_evidence(
            problem, policy, limits
        )
        finished = datetime.now(UTC)
        if not backend_result.telemetry["objective_optimized"]:
            raise RuntimeError("GlobalCpSatStrategy backend did not execute OBJ-001")

        solution = backend_result.solution
        status = SolverStatus(solution["solver_status"])
        candidate_available = outcome_for_solver_status(status).candidate_available
        if candidate_available and (
            backend_result.validation_report is None
            or backend_result.validation_report["status"] != "PASS"
        ):
            raise RuntimeError(
                "GlobalCpSatStrategy cannot expose a candidate without Validator PASS"
            )

        solution_fingerprint = contract_fingerprint(
            cast(Mapping[str, object], solution)
        )
        stage = solution["objective_stage_results"][0]
        validation_seconds = backend_result.telemetry["validation_seconds"]
        first_feasible = backend_result.telemetry["first_feasible_seconds"]
        if candidate_available:
            first_feasible = min(
                0.0 if first_feasible is None else first_feasible,
                float(stage["solve_seconds"]),
            )
        else:
            first_feasible = None
        accounted_total = (
            backend_result.telemetry["model_build_seconds"]
            + float(stage["solve_seconds"])
            + (0.0 if validation_seconds is None else validation_seconds)
        )
        total_seconds = max(
            accounted_total, backend_result.telemetry["total_seconds"]
        )
        identity = self._backend.identity
        report = cast(
            SolverReportDocument,
            {
                "solver_report_version": SOLVER_REPORT_VERSION,
                "schema_set_version": SCHEMA_SET_VERSION,
                "report_id": _report_id(planning_run_id, solution_fingerprint),
                "evidence_kind": "SOLVER_RUN",
                "planning_run_id": planning_run_id,
                "started_at_utc": format_utc_instant(started),
                "finished_at_utc": format_utc_instant(finished),
                "problem": solution["problem"],
                "policy": solution["policy"],
                "limits": solution["limits"],
                "solution": {
                    "planning_solution_version": PLANNING_SOLUTION_VERSION,
                    "solution_id": solution["solution_id"],
                    "solution_fingerprint": solution_fingerprint,
                    "solver_status": solution["solver_status"],
                },
                "solver_status": solution["solver_status"],
                "planning_run_outcome": solution["planning_run_outcome"],
                "solver": {
                    **identity,
                    "solver_name": SOLVER_REPORT_NAME,
                    "parameters": _report_parameters(limits),
                },
                "objective_stage_results": solution["objective_stage_results"],
                "timings": {
                    "model_build_seconds": backend_result.telemetry[
                        "model_build_seconds"
                    ],
                    "first_feasible_seconds": first_feasible,
                    "solve_seconds": stage["solve_seconds"],
                    "validation_seconds": validation_seconds,
                    "total_seconds": total_seconds,
                },
                "model_metrics": backend_result.telemetry["model_metrics"],
                "memory_peak_mb": backend_result.telemetry[
                    "python_memory_peak_mb"
                ],
                "diagnostics": solution["diagnostics"],
                "provenance": {
                    "code_commit": code_commit,
                    "spec_version": "0.3.0",
                    "schema_set_version": SCHEMA_SET_VERSION,
                    "canonicalization_version": CANONICALIZATION_VERSION,
                    "constraint_contract_version": CONSTRAINT_CONTRACT_VERSION,
                    "objective_policy_version": OBJECTIVE_POLICY_VERSION,
                    "state_machine_contract_version": (
                        STATE_MACHINE_CONTRACT_VERSION
                    ),
                    "error_registry_version": ERROR_REGISTRY_VERSION,
                },
            },
        )
        validate_contract_bundle(
            cast(Mapping[str, object], policy),
            cast(Mapping[str, object], limits),
            cast(Mapping[str, object], solution),
            cast(Mapping[str, object], report),
        )
        return GlobalStrategyResult(
            solution=solution,
            solver_report=report,
            validation_report=backend_result.validation_report,
        )


__all__ = [
    "GlobalCpSatStrategy",
    "GlobalStrategyResult",
    "STRATEGY_ID",
    "STRATEGY_VERSION",
    "SOLVER_REPORT_NAME",
]
