"""Immutable SolverReport freezing at the validated P2 output boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Never, cast

from app.planning.contracts import (
    PLANNING_SOLUTION_VERSION,
    SOLVER_REPORT_VERSION,
    PlanningContractError,
    canonical_contract_bytes,
    contract_fingerprint,
    validate_planning_solution,
    validate_solver_report,
)
from app.planning.strategies.global_cp_sat import STRATEGY_ID, STRATEGY_VERSION


type JsonObject = dict[str, Any]


class ReportingContractErrorCode(StrEnum):
    """Stable P2 reporting rejection categories."""

    INVALID_CONTRACT = "INVALID_CONTRACT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MIXED_LINEAGE = "MIXED_LINEAGE"
    INVALID_COUNT = "INVALID_COUNT"


class ReportingContractError(ValueError):
    """A deterministic rejection from the KPI/SolverReport boundary."""

    def __init__(
        self,
        code: ReportingContractErrorCode,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code.value} at {field}: {message}")


@dataclass(frozen=True, slots=True)
class FrozenSolverReport:
    """A SolverReport represented only by canonical JSON bytes."""

    canonical_bytes: bytes
    fingerprint: str
    report_id: str
    planning_run_id: str

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))


def _reject(
    code: ReportingContractErrorCode, field: str, message: str
) -> Never:
    raise ReportingContractError(code, field=field, message=message)


def freeze_solver_report(
    solution: Mapping[str, object],
    solver_report: Mapping[str, object],
    validation_report: Mapping[str, object],
) -> FrozenSolverReport:
    """Validate cross-document lineage and freeze one real SolverReport.

    This deliberately does not rewrite timing or solver identity. Determinism means
    the same already-formed logical report freezes to the same bytes and fingerprint.
    """

    try:
        validate_planning_solution(solution)
        validate_solver_report(solver_report)
    except (KeyError, TypeError, ValueError, PlanningContractError) as error:
        raise ReportingContractError(
            ReportingContractErrorCode.INVALID_CONTRACT,
            field="solution/solver_report",
            message="planning output contract validation failed",
        ) from error

    if solution.get("planning_solution_version") != PLANNING_SOLUTION_VERSION:
        _reject(
            ReportingContractErrorCode.INVALID_CONTRACT,
            "solution.planning_solution_version",
            "only planning-solution.v1 can be frozen",
        )
    if solver_report.get("solver_report_version") != SOLVER_REPORT_VERSION:
        _reject(
            ReportingContractErrorCode.INVALID_CONTRACT,
            "solver_report.solver_report_version",
            "only solver-report.v1 can be frozen",
        )
    if solution.get("evidence_kind") != "SOLVER_RUN" or solver_report.get(
        "evidence_kind"
    ) != "SOLVER_RUN":
        _reject(
            ReportingContractErrorCode.INVALID_CONTRACT,
            "evidence_kind",
            "contract samples cannot be emitted as run evidence",
        )
    if solution.get("solver_status") not in {"OPTIMAL", "FEASIBLE"}:
        _reject(
            ReportingContractErrorCode.VALIDATION_FAILED,
            "solution.solver_status",
            "an internal output package requires a candidate status",
        )
    if (
        validation_report.get("validation_report_version")
        != "validation-report.v2"
        or validation_report.get("status") != "PASS"
        or validation_report.get("hard_violation_count") != 0
        or validation_report.get("violations") != []
    ):
        _reject(
            ReportingContractErrorCode.VALIDATION_FAILED,
            "validation_report",
            "a candidate must have an exact PASS ValidationReport v2",
        )

    problem = cast(Mapping[str, object], solution["problem"])
    if validation_report.get("problem_hash") != problem.get("problem_hash"):
        _reject(
            ReportingContractErrorCode.MIXED_LINEAGE,
            "validation_report.problem_hash",
            "ValidationReport and PlanningSolution refer to different Problems",
        )

    solution_fingerprint = contract_fingerprint(solution)
    report_identity_basis: Mapping[str, object] = {
        "planning_run_id": solver_report["planning_run_id"],
        "solution_fingerprint": solution_fingerprint,
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
    }
    expected_report_id = (
        "solver-report-global-"
        f"{sha256(canonical_contract_bytes(report_identity_basis)).hexdigest()}"
    )
    if solver_report.get("report_id") != expected_report_id:
        _reject(
            ReportingContractErrorCode.MIXED_LINEAGE,
            "solver_report.report_id",
            "report identity does not bind planning run, solution, and strategy",
        )
    expected_solution_reference = {
        "planning_solution_version": PLANNING_SOLUTION_VERSION,
        "solution_id": solution["solution_id"],
        "solution_fingerprint": solution_fingerprint,
        "solver_status": solution["solver_status"],
    }
    exact_pairs = {
        "problem": solution["problem"],
        "policy": solution["policy"],
        "limits": solution["limits"],
        "solution": expected_solution_reference,
        "solver_status": solution["solver_status"],
        "planning_run_outcome": solution["planning_run_outcome"],
        "objective_stage_results": solution["objective_stage_results"],
        "diagnostics": solution["diagnostics"],
    }
    for field, expected in exact_pairs.items():
        if solver_report.get(field) != expected:
            _reject(
                ReportingContractErrorCode.MIXED_LINEAGE,
                f"solver_report.{field}",
                "SolverReport does not exactly bind the supplied PlanningSolution",
            )

    canonical_bytes = canonical_contract_bytes(solver_report)
    return FrozenSolverReport(
        canonical_bytes=canonical_bytes,
        fingerprint=contract_fingerprint(solver_report),
        report_id=cast(str, solver_report["report_id"]),
        planning_run_id=cast(str, solver_report["planning_run_id"]),
    )


__all__ = [
    "FrozenSolverReport",
    "ReportingContractError",
    "ReportingContractErrorCode",
    "freeze_solver_report",
]
