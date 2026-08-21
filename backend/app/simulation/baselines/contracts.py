"""Versioned contracts for deterministic, non-production reference schedulers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import NotRequired, TypedDict

from app.domain.contracts import ValidationReportDocumentV2
from app.planning.contracts import (
    OperationAssignmentDocument,
    ProblemReferenceDocument,
)


REFERENCE_SCHEDULER_CONTRACT_VERSION = "reference-scheduler-contracts.v1"
REFERENCE_SCHEDULER_POLICY_VERSION = "reference-scheduler-policy.v1"
REFERENCE_SCHEDULER_RESULT_VERSION = "reference-scheduler-result.v1"
REFERENCE_SCHEDULER_REPORT_VERSION = "reference-scheduler-report.v1"


class ReferenceAlgorithm(StrEnum):
    """The complete TASK-P2-10 reference algorithm set."""

    FCFS = "FCFS"
    EDD = "EDD"
    SPT = "SPT"
    PRIORITY_EDD = "PRIORITY_EDD"
    GREEDY_EARLIEST_AVAILABLE_MACHINE = "GREEDY_EARLIEST_AVAILABLE_MACHINE"


class ReferenceSchedulerStatus(StrEnum):
    """Honest outcomes that deliberately exclude an infeasibility certificate."""

    FEASIBLE = "FEASIBLE"
    HEURISTIC_FAILURE = "HEURISTIC_FAILURE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_PROBLEM = "INVALID_PROBLEM"


@dataclass(frozen=True, slots=True)
class ReferenceAlgorithmIdentity:
    """Stable identity and exact deterministic selection keys for one algorithm."""

    algorithm: ReferenceAlgorithm
    algorithm_id: str
    operation_selection: tuple[str, ...]
    resource_selection: tuple[str, ...]


_RESOURCE_SELECTION = (
    "earliest_end_tick",
    "earliest_start_tick",
    "duration_ticks",
    "resource_id",
)

ALGORITHM_IDENTITIES: Mapping[ReferenceAlgorithm, ReferenceAlgorithmIdentity] = (
    MappingProxyType(
        {
            ReferenceAlgorithm.FCFS: ReferenceAlgorithmIdentity(
                algorithm=ReferenceAlgorithm.FCFS,
                algorithm_id="reference-fcfs.v1",
                operation_selection=(
                    "release_at_utc",
                    "demand_order_id",
                    "operation_id",
                ),
                resource_selection=_RESOURCE_SELECTION,
            ),
            ReferenceAlgorithm.EDD: ReferenceAlgorithmIdentity(
                algorithm=ReferenceAlgorithm.EDD,
                algorithm_id="reference-edd.v1",
                operation_selection=(
                    "due_at_utc",
                    "release_at_utc",
                    "demand_order_id",
                    "operation_id",
                ),
                resource_selection=_RESOURCE_SELECTION,
            ),
            ReferenceAlgorithm.SPT: ReferenceAlgorithmIdentity(
                algorithm=ReferenceAlgorithm.SPT,
                algorithm_id="reference-spt.v1",
                operation_selection=(
                    "minimum_duration_seconds",
                    "due_at_utc",
                    "operation_id",
                ),
                resource_selection=_RESOURCE_SELECTION,
            ),
            ReferenceAlgorithm.PRIORITY_EDD: ReferenceAlgorithmIdentity(
                algorithm=ReferenceAlgorithm.PRIORITY_EDD,
                algorithm_id="reference-priority-edd.v1",
                operation_selection=(
                    "negative_priority_weight",
                    "due_at_utc",
                    "release_at_utc",
                    "demand_order_id",
                    "operation_id",
                ),
                resource_selection=_RESOURCE_SELECTION,
            ),
            ReferenceAlgorithm.GREEDY_EARLIEST_AVAILABLE_MACHINE: (
                ReferenceAlgorithmIdentity(
                    algorithm=ReferenceAlgorithm.GREEDY_EARLIEST_AVAILABLE_MACHINE,
                    algorithm_id=(
                        "reference-greedy-earliest-available-machine.v1"
                    ),
                    operation_selection=(
                        "earliest_end_tick",
                        "earliest_start_tick",
                        "duration_ticks",
                        "resource_id",
                        "operation_id",
                    ),
                    resource_selection=_RESOURCE_SELECTION,
                )
            ),
        }
    )
)


class ReferenceCandidateDocument(TypedDict):
    """The solver-neutral subset consumed by the formal schedule Validator."""

    problem: ProblemReferenceDocument
    assignments: list[OperationAssignmentDocument]


class ReferenceSchedulerMetricsDocument(TypedDict):
    weighted_tardiness_seconds: int | None
    makespan_seconds: int | None
    runtime_seconds: float
    scheduled_operation_count: int
    unscheduled_operation_count: int


class ReferenceSchedulerFailureDocument(TypedDict):
    code: str
    message: str
    operation_id: NotRequired[str]


class ReferenceSchedulerResultDocument(TypedDict):
    reference_scheduler_result_version: str
    reference_scheduler_contract_version: str
    reference_scheduler_policy_version: str
    algorithm: ReferenceAlgorithm
    algorithm_id: str
    status: ReferenceSchedulerStatus
    problem_hash: str
    non_production: bool
    optimality_claim: str
    candidate: ReferenceCandidateDocument | None
    validation_report: ValidationReportDocumentV2 | None
    metrics: ReferenceSchedulerMetricsDocument
    failure: ReferenceSchedulerFailureDocument | None


def algorithm_identity(
    algorithm: ReferenceAlgorithm | str,
) -> ReferenceAlgorithmIdentity:
    """Resolve one registered algorithm without accepting aliases or defaults."""

    selected = ReferenceAlgorithm(algorithm)
    return ALGORITHM_IDENTITIES[selected]


__all__ = [
    "ALGORITHM_IDENTITIES",
    "REFERENCE_SCHEDULER_CONTRACT_VERSION",
    "REFERENCE_SCHEDULER_POLICY_VERSION",
    "REFERENCE_SCHEDULER_REPORT_VERSION",
    "REFERENCE_SCHEDULER_RESULT_VERSION",
    "ReferenceAlgorithm",
    "ReferenceAlgorithmIdentity",
    "ReferenceCandidateDocument",
    "ReferenceSchedulerFailureDocument",
    "ReferenceSchedulerMetricsDocument",
    "ReferenceSchedulerResultDocument",
    "ReferenceSchedulerStatus",
    "algorithm_identity",
]
