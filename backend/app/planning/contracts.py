"""Solver-neutral PlanningSolution, SolverReport, and status contracts.

This module deliberately contains no solver, constraint, validator, persistence,
or API implementation.  It only fixes the JSON-compatible boundary shared by
later P2 consumers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import json
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, NoReturn, Protocol, TypedDict, cast

from app.domain.errors import ProductErrorCategory, ProductErrorCode
from app.domain.state_machines import PlanningRunState
from app.domain.types import parse_utc_instant

if TYPE_CHECKING:
    from app.planning.policy.contracts import (
        PlanningPolicyDocument,
        SolveLimitsDocument,
    )
    from app.planning.problem.contracts import PlanningProblemDocumentV2


SCHEMA_SET_VERSION = "2.4.0"
CANONICALIZATION_VERSION = "canonical-json.v1"
PLANNING_SOLUTION_VERSION = "planning-solution.v1"
SOLVER_REPORT_VERSION = "solver-report.v1"
PLANNING_POLICY_VERSION = "planning-policy.v1"
SOLVE_LIMITS_VERSION = "solve-limits.v1"
PROBLEM_VERSION = "planning-problem.v2"
PROBLEM_BUILDER_VERSION = "planning-problem-builder.v2"
PROBLEM_HASH_PROJECTION_VERSION = "planning-problem-hash-projection.v2"
OBJECTIVE_POLICY_VERSION = "objective-policy.v1"
CONSTRAINT_CONTRACT_VERSION = "constraint-rule-sheet.v1"
STATE_MACHINE_CONTRACT_VERSION = "state-machines.v1"
ERROR_REGISTRY_VERSION = "error-code-registry.v2"

_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^(?:uncommitted|[0-9a-f]{40})$")


class SolverStatus(StrEnum):
    """The seven status values shared by every solver backend."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class EvidenceKind(StrEnum):
    """Distinguish shape-only samples from a future real solver execution."""

    CONTRACT_SAMPLE = "CONTRACT_SAMPLE"
    SOLVER_RUN = "SOLVER_RUN"


class PlanningContractReason(StrEnum):
    """Module-local reasons carried under the stable MODEL_INVALID code."""

    INVALID_VERSION = "INVALID_VERSION"
    INVALID_SHAPE = "INVALID_SHAPE"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    INVALID_STATUS_COMBINATION = "INVALID_STATUS_COMBINATION"
    INVALID_TIME = "INVALID_TIME"
    INVALID_METRIC = "INVALID_METRIC"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    NON_CANONICAL_ORDER = "NON_CANONICAL_ORDER"


class PlanningContractError(ValueError):
    """A deterministic rejection from the planning machine boundary."""

    category = ProductErrorCategory.MODEL_INVALID
    code = ProductErrorCode.MODEL_INVALID

    def __init__(
        self,
        reason: PlanningContractReason,
        *,
        field: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(
            f"{self.category.value}/{self.code.value}/{reason.value} at {field}: "
            f"{message}"
        )


@dataclass(frozen=True)
class SolverOutcome:
    """Product lifecycle/error meaning for one backend status."""

    planning_run_state: PlanningRunState
    product_error_category: ProductErrorCategory | None
    product_error_code: ProductErrorCode | None
    candidate_available: bool


_SOLVER_OUTCOMES: Mapping[SolverStatus, SolverOutcome] = MappingProxyType(
    {
        SolverStatus.OPTIMAL: SolverOutcome(
            PlanningRunState.SOLVED, None, None, True
        ),
        SolverStatus.FEASIBLE: SolverOutcome(
            PlanningRunState.SOLVED, None, None, True
        ),
        SolverStatus.INFEASIBLE: SolverOutcome(
            PlanningRunState.INFEASIBLE,
            ProductErrorCategory.INFEASIBLE,
            ProductErrorCode.INFEASIBLE,
            False,
        ),
        SolverStatus.UNKNOWN: SolverOutcome(
            PlanningRunState.NO_SOLUTION_WITHIN_LIMIT,
            ProductErrorCategory.NO_SOLUTION_WITHIN_LIMIT,
            ProductErrorCode.NO_SOLUTION_WITHIN_LIMIT,
            False,
        ),
        SolverStatus.MODEL_INVALID: SolverOutcome(
            PlanningRunState.MODEL_INVALID,
            ProductErrorCategory.MODEL_INVALID,
            ProductErrorCode.MODEL_INVALID,
            False,
        ),
        SolverStatus.CANCELLED: SolverOutcome(
            PlanningRunState.CANCELLED, None, None, False
        ),
        SolverStatus.FAILED: SolverOutcome(
            PlanningRunState.FAILED,
            ProductErrorCategory.SYSTEM_ERROR,
            ProductErrorCode.SYSTEM_ERROR,
            False,
        ),
    }
)


class ProductErrorReferenceDocument(TypedDict):
    category: Literal[
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "SYSTEM_ERROR",
    ]
    code: Literal[
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "SYSTEM_ERROR",
    ]


class PlanningRunOutcomeDocument(TypedDict):
    state: Literal[
        "SOLVED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "CANCELLED",
        "FAILED",
    ]
    product_error: ProductErrorReferenceDocument | None


class ProblemReferenceDocument(TypedDict):
    problem_version: Literal["planning-problem.v2"]
    problem_builder_version: Literal["planning-problem-builder.v2"]
    problem_hash_projection_version: Literal["planning-problem-hash-projection.v2"]
    problem_hash: str
    snapshot_id: str
    tick_seconds: int
    horizon_start_utc: str
    horizon_end_utc: str


class PolicyReferenceDocument(TypedDict):
    planning_policy_version: Literal["planning-policy.v1"]
    policy_id: str
    policy_revision: str
    policy_fingerprint: str


class LimitsReferenceDocument(TypedDict):
    solve_limits_version: Literal["solve-limits.v1"]
    limits_id: str
    limits_revision: str
    limits_fingerprint: str
    max_wall_time_seconds: float
    max_workers: int
    random_seed: int


class OperationAssignmentDocument(TypedDict):
    operation_id: str
    resource_id: str
    start_tick: int
    end_tick: int
    duration_ticks: int
    start_at_utc: str
    end_at_utc: str
    duration_seconds: int
    lock_ids: list[str]
    execution_fact_ids: list[str]


class ObjectiveStageResultDocument(TypedDict):
    stage_index: Literal[1]
    objective_id: Literal["OBJ-001"]
    metric: Literal["WEIGHTED_TARDINESS"]
    sense: Literal["MINIMIZE"]
    status: Literal[
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "UNKNOWN",
        "MODEL_INVALID",
        "CANCELLED",
        "FAILED",
    ]
    objective_value: int | None
    best_bound: int | None
    relative_gap: float | None
    allocated_wall_time_seconds: float
    solve_seconds: float
    stop_reason: str


class DiagnosticDocument(TypedDict):
    code: str
    message: str


class PlanningSolutionDocument(TypedDict):
    planning_solution_version: Literal["planning-solution.v1"]
    schema_set_version: Literal["2.4.0"]
    solution_id: str
    evidence_kind: Literal["CONTRACT_SAMPLE", "SOLVER_RUN"]
    canonicalization_version: Literal["canonical-json.v1"]
    problem: ProblemReferenceDocument
    policy: PolicyReferenceDocument
    limits: LimitsReferenceDocument
    solver_status: Literal[
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "UNKNOWN",
        "MODEL_INVALID",
        "CANCELLED",
        "FAILED",
    ]
    planning_run_outcome: PlanningRunOutcomeDocument
    assignments: list[OperationAssignmentDocument]
    objective_stage_results: list[ObjectiveStageResultDocument]
    diagnostics: list[DiagnosticDocument]


class SolutionReferenceDocument(TypedDict):
    planning_solution_version: Literal["planning-solution.v1"]
    solution_id: str
    solution_fingerprint: str
    solver_status: Literal[
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "UNKNOWN",
        "MODEL_INVALID",
        "CANCELLED",
        "FAILED",
    ]


class SolverParameterDocument(TypedDict):
    name: str
    value: str | int | float | bool
    source: Literal["SOLVE_LIMITS", "BACKEND"]


class SolverIdentityDocument(TypedDict):
    backend_id: str
    backend_version: str
    solver_name: str
    solver_version: str
    parameters: list[SolverParameterDocument]


class SolverTimingDocument(TypedDict):
    model_build_seconds: float
    first_feasible_seconds: float | None
    solve_seconds: float
    validation_seconds: float | None
    total_seconds: float


class ModelMetricsDocument(TypedDict):
    variables: int
    constraints: int
    optional_intervals: int


class SolverProvenanceDocument(TypedDict):
    code_commit: str
    spec_version: Literal["0.3.0"]
    schema_set_version: Literal["2.4.0"]
    canonicalization_version: Literal["canonical-json.v1"]
    constraint_contract_version: Literal["constraint-rule-sheet.v1"]
    objective_policy_version: Literal["objective-policy.v1"]
    state_machine_contract_version: Literal["state-machines.v1"]
    error_registry_version: Literal["error-code-registry.v2"]


class SolverReportDocument(TypedDict):
    solver_report_version: Literal["solver-report.v1"]
    schema_set_version: Literal["2.4.0"]
    report_id: str
    evidence_kind: Literal["CONTRACT_SAMPLE", "SOLVER_RUN"]
    planning_run_id: str
    started_at_utc: str
    finished_at_utc: str
    problem: ProblemReferenceDocument
    policy: PolicyReferenceDocument
    limits: LimitsReferenceDocument
    solution: SolutionReferenceDocument
    solver_status: Literal[
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "UNKNOWN",
        "MODEL_INVALID",
        "CANCELLED",
        "FAILED",
    ]
    planning_run_outcome: PlanningRunOutcomeDocument
    solver: SolverIdentityDocument
    objective_stage_results: list[ObjectiveStageResultDocument]
    timings: SolverTimingDocument
    model_metrics: ModelMetricsDocument
    memory_peak_mb: float
    diagnostics: list[DiagnosticDocument]
    provenance: SolverProvenanceDocument


class SolverBackend(Protocol):
    """Future backend boundary; TASK-P2-02 provides no implementation."""

    def solve(
        self,
        problem: PlanningProblemDocumentV2,
        policy: PlanningPolicyDocument,
        limits: SolveLimitsDocument,
    ) -> PlanningSolutionDocument: ...


def _fail(
    reason: PlanningContractReason,
    field: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise PlanningContractError(
        reason,
        field=field,
        expected_contract=expected_contract,
        message=message,
    )


def _object(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            field,
            "JSON object",
            "value must be an object",
        )
    return cast(Mapping[str, object], value)


def _items(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            field,
            "JSON array",
            "value must be an array",
        )
    return cast(list[object], value)


def _exact_keys(
    value: Mapping[str, object], expected: set[str], field: str
) -> None:
    observed = set(value)
    if observed != expected:
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            field,
            f"exact fields {sorted(expected)}",
            f"missing={sorted(expected - observed)} extra={sorted(observed - expected)}",
        )


def _text(value: object, field: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            field,
            "non-empty text",
            "value must be a non-empty string",
        )
    if identifier and (
        any(character.isspace() for character in value) or len(value) > 256
    ):
        _fail(
            PlanningContractReason.INVALID_REFERENCE,
            field,
            "canonical whitespace-free identifier up to 256 characters",
            "identifier is not canonical",
        )
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(
            PlanningContractReason.INVALID_METRIC,
            field,
            f"integer >= {minimum}",
            "value is outside the integer contract",
        )
    return value


def _number(
    value: object,
    field: str,
    *,
    minimum: float = 0.0,
    exclusive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(
            PlanningContractReason.INVALID_METRIC,
            field,
            "finite number",
            "value must be numeric and not boolean",
        )
    observed = float(value)
    if not math.isfinite(observed) or (
        observed <= minimum if exclusive else observed < minimum
    ):
        comparator = ">" if exclusive else ">="
        _fail(
            PlanningContractReason.INVALID_METRIC,
            field,
            f"finite number {comparator} {minimum}",
            "value is outside the numeric contract",
        )
    return observed


def _utc(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        return parse_utc_instant(text)
    except ValueError:
        _fail(
            PlanningContractReason.INVALID_TIME,
            field,
            "RFC3339 UTC instant ending in Z",
            "timestamp is not canonical UTC",
        )


def _fingerprint(value: object, field: str) -> str:
    text = _text(value, field)
    if _HASH_PATTERN.fullmatch(text) is None:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            field,
            "sha256:<64 lowercase hex>",
            "fingerprint has an invalid shape",
        )
    return text


def canonical_contract_bytes(document: Mapping[str, object]) -> bytes:
    """Return deterministic canonical-json.v1 bytes without mutating input."""

    try:
        rendered = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise PlanningContractError(
            PlanningContractReason.INVALID_SHAPE,
            field="$",
            expected_contract="finite JSON-compatible document",
            message="document cannot be canonicalized",
        ) from error
    return rendered.encode("utf-8")


def contract_fingerprint(document: Mapping[str, object]) -> str:
    """Fingerprint the complete canonical document; no self field is excluded."""

    return f"sha256:{sha256(canonical_contract_bytes(document)).hexdigest()}"


def outcome_for_solver_status(status: SolverStatus | str) -> SolverOutcome:
    """Return the sole product meaning allocated to a solver status."""

    try:
        selected = SolverStatus(status)
    except ValueError as error:
        raise PlanningContractError(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            field="solver_status",
            expected_contract="one of the seven SolverStatus values",
            message="solver status is not registered",
        ) from error
    return _SOLVER_OUTCOMES[selected]


def outcome_document_for_status(status: SolverStatus | str) -> PlanningRunOutcomeDocument:
    """Build the canonical PlanningRun/product-error outcome document."""

    outcome = outcome_for_solver_status(status)
    product_error: ProductErrorReferenceDocument | None
    if outcome.product_error_category is None or outcome.product_error_code is None:
        product_error = None
    else:
        product_error = {
            "category": cast(AnyProductErrorCategory, outcome.product_error_category.value),
            "code": cast(AnyProductErrorCode, outcome.product_error_code.value),
        }
    return {
        "state": cast(AnyPlanningRunOutcome, outcome.planning_run_state.value),
        "product_error": product_error,
    }


type AnyProductErrorCategory = Literal[
    "MODEL_INVALID", "INFEASIBLE", "NO_SOLUTION_WITHIN_LIMIT", "SYSTEM_ERROR"
]
type AnyProductErrorCode = Literal[
    "MODEL_INVALID", "INFEASIBLE", "NO_SOLUTION_WITHIN_LIMIT", "SYSTEM_ERROR"
]
type AnyPlanningRunOutcome = Literal[
    "SOLVED",
    "MODEL_INVALID",
    "INFEASIBLE",
    "NO_SOLUTION_WITHIN_LIMIT",
    "CANCELLED",
    "FAILED",
]


def _validate_outcome(value: object, status: SolverStatus, field: str) -> None:
    document = _object(value, field)
    _exact_keys(document, {"state", "product_error"}, field)
    expected = outcome_document_for_status(status)
    if dict(document) != expected:
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            field,
            f"exact outcome {expected}",
            "status was mapped to a different product meaning",
        )


def _validate_problem_reference(value: object, field: str) -> Mapping[str, object]:
    document = _object(value, field)
    expected = {
        "problem_version",
        "problem_builder_version",
        "problem_hash_projection_version",
        "problem_hash",
        "snapshot_id",
        "tick_seconds",
        "horizon_start_utc",
        "horizon_end_utc",
    }
    _exact_keys(document, expected, field)
    versions = {
        "problem_version": PROBLEM_VERSION,
        "problem_builder_version": PROBLEM_BUILDER_VERSION,
        "problem_hash_projection_version": PROBLEM_HASH_PROJECTION_VERSION,
    }
    for key, expected_value in versions.items():
        if document[key] != expected_value:
            _fail(
                PlanningContractReason.INVALID_VERSION,
                f"{field}.{key}",
                expected_value,
                "reference version is not supported by this contract",
            )
    _fingerprint(document["problem_hash"], f"{field}.problem_hash")
    _text(document["snapshot_id"], f"{field}.snapshot_id", identifier=True)
    _integer(document["tick_seconds"], f"{field}.tick_seconds", minimum=1)
    start = _utc(document["horizon_start_utc"], f"{field}.horizon_start_utc")
    end = _utc(document["horizon_end_utc"], f"{field}.horizon_end_utc")
    if end <= start:
        _fail(
            PlanningContractReason.INVALID_TIME,
            field,
            "horizon_end_utc > horizon_start_utc",
            "problem horizon is empty or reversed",
        )
    return document


def _validate_policy_reference(value: object, field: str) -> Mapping[str, object]:
    document = _object(value, field)
    expected = {
        "planning_policy_version",
        "policy_id",
        "policy_revision",
        "policy_fingerprint",
    }
    _exact_keys(document, expected, field)
    if document["planning_policy_version"] != PLANNING_POLICY_VERSION:
        _fail(
            PlanningContractReason.INVALID_VERSION,
            f"{field}.planning_policy_version",
            PLANNING_POLICY_VERSION,
            "policy reference version is not supported",
        )
    _text(document["policy_id"], f"{field}.policy_id", identifier=True)
    _text(document["policy_revision"], f"{field}.policy_revision")
    _fingerprint(document["policy_fingerprint"], f"{field}.policy_fingerprint")
    return document


def _validate_limits_reference(value: object, field: str) -> Mapping[str, object]:
    document = _object(value, field)
    expected = {
        "solve_limits_version",
        "limits_id",
        "limits_revision",
        "limits_fingerprint",
        "max_wall_time_seconds",
        "max_workers",
        "random_seed",
    }
    _exact_keys(document, expected, field)
    if document["solve_limits_version"] != SOLVE_LIMITS_VERSION:
        _fail(
            PlanningContractReason.INVALID_VERSION,
            f"{field}.solve_limits_version",
            SOLVE_LIMITS_VERSION,
            "limits reference version is not supported",
        )
    _text(document["limits_id"], f"{field}.limits_id", identifier=True)
    _text(document["limits_revision"], f"{field}.limits_revision")
    _fingerprint(document["limits_fingerprint"], f"{field}.limits_fingerprint")
    _number(
        document["max_wall_time_seconds"],
        f"{field}.max_wall_time_seconds",
        exclusive=True,
    )
    _integer(document["max_workers"], f"{field}.max_workers", minimum=1)
    _integer(document["random_seed"], f"{field}.random_seed")
    return document


def _validate_sorted_ids(value: object, field: str) -> list[str]:
    items = [_text(item, field, identifier=True) for item in _items(value, field)]
    if items != sorted(set(items)):
        _fail(
            PlanningContractReason.NON_CANONICAL_ORDER,
            field,
            "sorted unique canonical identifiers",
            "identifier collection is duplicated or not sorted",
        )
    return items


def _validate_diagnostics(value: object, field: str) -> list[Mapping[str, object]]:
    diagnostics: list[Mapping[str, object]] = []
    for index, item in enumerate(_items(value, field)):
        path = f"{field}[{index}]"
        document = _object(item, path)
        _exact_keys(document, {"code", "message"}, path)
        _text(document["code"], f"{path}.code", identifier=True)
        _text(document["message"], f"{path}.message")
        diagnostics.append(document)
    keys = [(str(item["code"]), str(item["message"])) for item in diagnostics]
    if keys != sorted(set(keys)):
        _fail(
            PlanningContractReason.NON_CANONICAL_ORDER,
            field,
            "sorted unique diagnostics by code/message",
            "diagnostics are duplicated or not sorted",
        )
    return diagnostics


def _validate_stage_result(
    value: object, field: str, expected_status: SolverStatus
) -> Mapping[str, object]:
    document = _object(value, field)
    expected_keys = {
        "stage_index",
        "objective_id",
        "metric",
        "sense",
        "status",
        "objective_value",
        "best_bound",
        "relative_gap",
        "allocated_wall_time_seconds",
        "solve_seconds",
        "stop_reason",
    }
    _exact_keys(document, expected_keys, field)
    fixed = {
        "stage_index": 1,
        "objective_id": "OBJ-001",
        "metric": "WEIGHTED_TARDINESS",
        "sense": "MINIMIZE",
        "status": expected_status.value,
    }
    for key, expected in fixed.items():
        if document[key] != expected:
            _fail(
                PlanningContractReason.INVALID_STATUS_COMBINATION,
                f"{field}.{key}",
                repr(expected),
                "objective stage is inconsistent with P2 OBJ-001 or overall status",
            )
    objective = document["objective_value"]
    bound = document["best_bound"]
    gap = document["relative_gap"]
    if expected_status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        objective_value = _integer(objective, f"{field}.objective_value")
        bound_value = _integer(bound, f"{field}.best_bound")
        gap_value = _number(gap, f"{field}.relative_gap")
        if bound_value > objective_value:
            _fail(
                PlanningContractReason.INVALID_STATUS_COMBINATION,
                field,
                "minimization best_bound <= objective_value",
                "bound is worse than the certified candidate objective",
            )
        expected_gap = (objective_value - bound_value) / max(1, objective_value)
        if not math.isclose(gap_value, expected_gap, rel_tol=0.0, abs_tol=1e-12):
            _fail(
                PlanningContractReason.INVALID_STATUS_COMBINATION,
                f"{field}.relative_gap",
                "(objective_value - best_bound) / max(1, objective_value)",
                "reported relative gap is inconsistent with objective and bound",
            )
        if expected_status is SolverStatus.OPTIMAL and (
            objective_value != bound_value or gap_value != 0.0
        ):
            _fail(
                PlanningContractReason.INVALID_STATUS_COMBINATION,
                field,
                "OPTIMAL objective == best_bound and relative_gap == 0",
                "optimality fields do not prove the declared status",
            )
    elif expected_status is SolverStatus.UNKNOWN:
        if objective is not None or gap is not None:
            _fail(
                PlanningContractReason.INVALID_STATUS_COMBINATION,
                field,
                "UNKNOWN has no objective candidate or relative gap",
                "UNKNOWN was given candidate-only values",
            )
        if bound is not None:
            _integer(bound, f"{field}.best_bound")
    elif any(item is not None for item in (objective, bound, gap)):
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            field,
            "non-candidate status has null objective/bound/gap",
            "status carries values that imply a certified candidate",
        )
    allocated_wall_time = _number(
        document["allocated_wall_time_seconds"],
        f"{field}.allocated_wall_time_seconds",
        exclusive=True,
    )
    solve_seconds = _number(document["solve_seconds"], f"{field}.solve_seconds")
    if solve_seconds > allocated_wall_time:
        _fail(
            PlanningContractReason.INVALID_TIME,
            f"{field}.solve_seconds",
            "solve_seconds <= allocated_wall_time_seconds",
            "stage timing exceeds its explicit budget",
        )
    _text(document["stop_reason"], f"{field}.stop_reason")
    return document


def _validate_stage_results(
    value: object, field: str, status: SolverStatus
) -> list[Mapping[str, object]]:
    values = _items(value, field)
    if len(values) != 1:
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            field,
            "exactly one P2 OBJ-001 stage",
            "P2 contract must neither omit nor add objective stages",
        )
    return [_validate_stage_result(values[0], f"{field}[0]", status)]


def _validate_assignments(
    value: object,
    problem: Mapping[str, object],
    status: SolverStatus,
    field: str,
) -> list[Mapping[str, object]]:
    raw = _items(value, field)
    if status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE} and raw:
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            field,
            "empty assignments when no certified candidate exists",
            "non-candidate status contains assignments",
        )
    assignments: list[Mapping[str, object]] = []
    tick_seconds = _integer(problem["tick_seconds"], "problem.tick_seconds", minimum=1)
    horizon_start = _utc(problem["horizon_start_utc"], "problem.horizon_start_utc")
    horizon_end = _utc(problem["horizon_end_utc"], "problem.horizon_end_utc")
    for index, item in enumerate(raw):
        path = f"{field}[{index}]"
        document = _object(item, path)
        expected = {
            "operation_id",
            "resource_id",
            "start_tick",
            "end_tick",
            "duration_ticks",
            "start_at_utc",
            "end_at_utc",
            "duration_seconds",
            "lock_ids",
            "execution_fact_ids",
        }
        _exact_keys(document, expected, path)
        _text(document["operation_id"], f"{path}.operation_id", identifier=True)
        _text(document["resource_id"], f"{path}.resource_id", identifier=True)
        start_tick = _integer(document["start_tick"], f"{path}.start_tick")
        end_tick = _integer(document["end_tick"], f"{path}.end_tick", minimum=1)
        duration_ticks = _integer(
            document["duration_ticks"], f"{path}.duration_ticks", minimum=1
        )
        duration_seconds = _integer(
            document["duration_seconds"], f"{path}.duration_seconds", minimum=1
        )
        if end_tick <= start_tick or duration_ticks != end_tick - start_tick:
            _fail(
                PlanningContractReason.INVALID_TIME,
                path,
                "end_tick > start_tick and duration_ticks == end_tick - start_tick",
                "tick interval is inconsistent",
            )
        if duration_ticks != (duration_seconds + tick_seconds - 1) // tick_seconds:
            _fail(
                PlanningContractReason.INVALID_TIME,
                f"{path}.duration_ticks",
                "ceil(duration_seconds / tick_seconds)",
                "authoritative seconds and solver ticks disagree",
            )
        start_at = _utc(document["start_at_utc"], f"{path}.start_at_utc")
        end_at = _utc(document["end_at_utc"], f"{path}.end_at_utc")
        expected_start = horizon_start + timedelta(seconds=start_tick * tick_seconds)
        expected_end = horizon_start + timedelta(seconds=end_tick * tick_seconds)
        if start_at != expected_start or end_at != expected_end or end_at > horizon_end:
            _fail(
                PlanningContractReason.INVALID_TIME,
                path,
                "UTC instants exactly restored from horizon_start + tick * tick_seconds",
                "UTC/tick projection is inconsistent or outside the horizon",
            )
        _validate_sorted_ids(document["lock_ids"], f"{path}.lock_ids")
        _validate_sorted_ids(
            document["execution_fact_ids"], f"{path}.execution_fact_ids"
        )
        assignments.append(document)
    operation_ids = [str(item["operation_id"]) for item in assignments]
    if operation_ids != sorted(set(operation_ids)):
        _fail(
            PlanningContractReason.NON_CANONICAL_ORDER,
            field,
            "assignments sorted by unique operation_id",
            "assignment collection is duplicated or not sorted",
        )
    return assignments


def validate_planning_solution(document: Mapping[str, object]) -> None:
    """Validate shape-independent invariants without evaluating C-IDs."""

    expected = {
        "planning_solution_version",
        "schema_set_version",
        "solution_id",
        "evidence_kind",
        "canonicalization_version",
        "problem",
        "policy",
        "limits",
        "solver_status",
        "planning_run_outcome",
        "assignments",
        "objective_stage_results",
        "diagnostics",
    }
    _exact_keys(document, expected, "$")
    versions = {
        "planning_solution_version": PLANNING_SOLUTION_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
    }
    for key, expected_value in versions.items():
        if document[key] != expected_value:
            _fail(
                PlanningContractReason.INVALID_VERSION,
                key,
                expected_value,
                "solution version is not supported",
            )
    _text(document["solution_id"], "solution_id", identifier=True)
    try:
        EvidenceKind(cast(str, document["evidence_kind"]))
        status = SolverStatus(cast(str, document["solver_status"]))
    except ValueError as error:
        raise PlanningContractError(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            field="evidence_kind/solver_status",
            expected_contract="registered evidence kind and SolverStatus",
            message="unregistered enum value",
        ) from error
    problem = _validate_problem_reference(document["problem"], "problem")
    _validate_policy_reference(document["policy"], "policy")
    _validate_limits_reference(document["limits"], "limits")
    _validate_outcome(document["planning_run_outcome"], status, "planning_run_outcome")
    _validate_assignments(document["assignments"], problem, status, "assignments")
    _validate_stage_results(
        document["objective_stage_results"], "objective_stage_results", status
    )
    diagnostics = _validate_diagnostics(document["diagnostics"], "diagnostics")
    if not outcome_for_solver_status(status).candidate_available and not diagnostics:
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            "diagnostics",
            "at least one sanitized diagnostic for non-candidate outcomes",
            "terminal outcome has no explanation",
        )


def _validate_solution_reference(
    value: object, field: str, status: SolverStatus
) -> Mapping[str, object]:
    document = _object(value, field)
    _exact_keys(
        document,
        {
            "planning_solution_version",
            "solution_id",
            "solution_fingerprint",
            "solver_status",
        },
        field,
    )
    if document["planning_solution_version"] != PLANNING_SOLUTION_VERSION:
        _fail(
            PlanningContractReason.INVALID_VERSION,
            f"{field}.planning_solution_version",
            PLANNING_SOLUTION_VERSION,
            "solution reference version is not supported",
        )
    _text(document["solution_id"], f"{field}.solution_id", identifier=True)
    _fingerprint(document["solution_fingerprint"], f"{field}.solution_fingerprint")
    if document["solver_status"] != status.value:
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            f"{field}.solver_status",
            status.value,
            "solution reference status differs from report",
        )
    return document


def _validate_solver_identity(
    value: object, limits: Mapping[str, object], field: str
) -> None:
    document = _object(value, field)
    _exact_keys(
        document,
        {"backend_id", "backend_version", "solver_name", "solver_version", "parameters"},
        field,
    )
    for key in ("backend_id", "backend_version", "solver_name", "solver_version"):
        _text(document[key], f"{field}.{key}", identifier=key in {"backend_id", "solver_name"})
    parameters: list[Mapping[str, object]] = []
    for index, item in enumerate(_items(document["parameters"], f"{field}.parameters")):
        path = f"{field}.parameters[{index}]"
        parameter = _object(item, path)
        _exact_keys(parameter, {"name", "value", "source"}, path)
        name = _text(parameter["name"], f"{path}.name", identifier=True)
        value_item = parameter["value"]
        if isinstance(value_item, float) and not math.isfinite(value_item):
            _fail(
                PlanningContractReason.INVALID_METRIC,
                f"{path}.value",
                "finite JSON scalar",
                "parameter is not finite",
            )
        if not isinstance(value_item, (str, int, float, bool)):
            _fail(
                PlanningContractReason.INVALID_SHAPE,
                f"{path}.value",
                "string/number/integer/boolean",
                "parameter value is not a JSON scalar",
            )
        if parameter["source"] not in {"SOLVE_LIMITS", "BACKEND"}:
            _fail(
                PlanningContractReason.INVALID_PROVENANCE,
                f"{path}.source",
                "SOLVE_LIMITS or BACKEND",
                "parameter source is not registered",
            )
        parameters.append(parameter)
    names = [str(item["name"]) for item in parameters]
    if names != sorted(set(names)):
        _fail(
            PlanningContractReason.NON_CANONICAL_ORDER,
            f"{field}.parameters",
            "parameters sorted by unique name",
            "parameter collection is duplicated or not sorted",
        )
    by_name = {str(item["name"]): item for item in parameters}
    required = {
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }
    for name, expected_value in required.items():
        parameter = by_name.get(name)
        if (
            parameter is None
            or parameter["source"] != "SOLVE_LIMITS"
            or parameter["value"] != expected_value
            or type(parameter["value"]) is not type(expected_value)
        ):
            _fail(
                PlanningContractReason.INVALID_PROVENANCE,
                f"{field}.parameters.{name}",
                f"SOLVE_LIMITS value {expected_value!r}",
                "report does not preserve the explicit limit parameter",
            )


def _validate_timings(
    value: object, status: SolverStatus, field: str
) -> Mapping[str, object]:
    document = _object(value, field)
    _exact_keys(
        document,
        {
            "model_build_seconds",
            "first_feasible_seconds",
            "solve_seconds",
            "validation_seconds",
            "total_seconds",
        },
        field,
    )
    build = _number(document["model_build_seconds"], f"{field}.model_build_seconds")
    solve = _number(document["solve_seconds"], f"{field}.solve_seconds")
    total = _number(document["total_seconds"], f"{field}.total_seconds")
    first = document["first_feasible_seconds"]
    if outcome_for_solver_status(status).candidate_available:
        first_value = _number(first, f"{field}.first_feasible_seconds")
        if first_value > solve:
            _fail(
                PlanningContractReason.INVALID_TIME,
                f"{field}.first_feasible_seconds",
                "first feasible time <= solve time",
                "first feasible time occurs after solve completion",
            )
    elif first is not None:
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            f"{field}.first_feasible_seconds",
            "null when no candidate exists",
            "timing implies an unavailable feasible candidate",
        )
    validation = document["validation_seconds"]
    validation_seconds = 0.0
    if validation is not None:
        validation_seconds = _number(validation, f"{field}.validation_seconds")
    if total < build + solve + validation_seconds:
        _fail(
            PlanningContractReason.INVALID_TIME,
            f"{field}.total_seconds",
            "total_seconds >= build + solve + validation seconds",
            "total timing is internally inconsistent",
        )
    return document


def _validate_model_metrics(value: object, field: str) -> None:
    document = _object(value, field)
    _exact_keys(document, {"variables", "constraints", "optional_intervals"}, field)
    for key in ("variables", "constraints", "optional_intervals"):
        _integer(document[key], f"{field}.{key}")


def _validate_provenance(value: object, field: str) -> None:
    document = _object(value, field)
    expected = {
        "code_commit",
        "spec_version",
        "schema_set_version",
        "canonicalization_version",
        "constraint_contract_version",
        "objective_policy_version",
        "state_machine_contract_version",
        "error_registry_version",
    }
    _exact_keys(document, expected, field)
    versions = {
        "spec_version": "0.3.0",
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "constraint_contract_version": CONSTRAINT_CONTRACT_VERSION,
        "objective_policy_version": OBJECTIVE_POLICY_VERSION,
        "state_machine_contract_version": STATE_MACHINE_CONTRACT_VERSION,
        "error_registry_version": ERROR_REGISTRY_VERSION,
    }
    for key, expected_value in versions.items():
        if document[key] != expected_value:
            _fail(
                PlanningContractReason.INVALID_VERSION,
                f"{field}.{key}",
                expected_value,
                "provenance version differs from the contract",
            )
    commit = _text(document["code_commit"], f"{field}.code_commit")
    if _COMMIT_PATTERN.fullmatch(commit) is None:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            f"{field}.code_commit",
            "uncommitted or 40 lowercase hexadecimal characters",
            "code commit is not traceable",
        )


def validate_solver_report(document: Mapping[str, object]) -> None:
    """Validate report metrics, provenance, status, and limit preservation."""

    expected = {
        "solver_report_version",
        "schema_set_version",
        "report_id",
        "evidence_kind",
        "planning_run_id",
        "started_at_utc",
        "finished_at_utc",
        "problem",
        "policy",
        "limits",
        "solution",
        "solver_status",
        "planning_run_outcome",
        "solver",
        "objective_stage_results",
        "timings",
        "model_metrics",
        "memory_peak_mb",
        "diagnostics",
        "provenance",
    }
    _exact_keys(document, expected, "$")
    versions = {
        "solver_report_version": SOLVER_REPORT_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
    }
    for key, expected_value in versions.items():
        if document[key] != expected_value:
            _fail(
                PlanningContractReason.INVALID_VERSION,
                key,
                expected_value,
                "report version is not supported",
            )
    _text(document["report_id"], "report_id", identifier=True)
    _text(document["planning_run_id"], "planning_run_id", identifier=True)
    try:
        EvidenceKind(cast(str, document["evidence_kind"]))
        status = SolverStatus(cast(str, document["solver_status"]))
    except ValueError as error:
        raise PlanningContractError(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            field="evidence_kind/solver_status",
            expected_contract="registered evidence kind and SolverStatus",
            message="unregistered enum value",
        ) from error
    started = _utc(document["started_at_utc"], "started_at_utc")
    finished = _utc(document["finished_at_utc"], "finished_at_utc")
    if finished < started:
        _fail(
            PlanningContractReason.INVALID_TIME,
            "finished_at_utc",
            "finished_at_utc >= started_at_utc",
            "report interval is reversed",
        )
    _validate_problem_reference(document["problem"], "problem")
    _validate_policy_reference(document["policy"], "policy")
    limits = _validate_limits_reference(document["limits"], "limits")
    _validate_solution_reference(document["solution"], "solution", status)
    _validate_outcome(document["planning_run_outcome"], status, "planning_run_outcome")
    _validate_solver_identity(document["solver"], limits, "solver")
    stages = _validate_stage_results(
        document["objective_stage_results"], "objective_stage_results", status
    )
    timings = _validate_timings(document["timings"], status, "timings")
    if timings["solve_seconds"] != stages[0]["solve_seconds"]:
        _fail(
            PlanningContractReason.INVALID_TIME,
            "timings.solve_seconds",
            "same solve_seconds as the sole OBJ-001 stage",
            "report timing and objective-stage timing diverge",
        )
    _validate_model_metrics(document["model_metrics"], "model_metrics")
    _number(document["memory_peak_mb"], "memory_peak_mb")
    diagnostics = _validate_diagnostics(document["diagnostics"], "diagnostics")
    if not outcome_for_solver_status(status).candidate_available and not diagnostics:
        _fail(
            PlanningContractReason.INVALID_STATUS_COMBINATION,
            "diagnostics",
            "at least one sanitized diagnostic for non-candidate outcomes",
            "terminal report has no explanation",
        )
    _validate_provenance(document["provenance"], "provenance")


def validate_contract_bundle(
    policy: Mapping[str, object],
    limits: Mapping[str, object],
    solution: Mapping[str, object],
    report: Mapping[str, object],
) -> None:
    """Cross-check the four documents without running a solver or validator."""

    from app.planning.policy.contracts import (
        validate_planning_policy,
        validate_solve_limits,
    )

    validate_planning_policy(policy)
    validate_solve_limits(limits)
    validate_planning_solution(solution)
    validate_solver_report(report)

    if policy["data_plane"] != limits["data_plane"]:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            "policy.data_plane/limits.data_plane",
            "the same explicit data plane",
            "policy and limits belong to different data planes",
        )

    policy_reference = cast(Mapping[str, object], solution["policy"])
    limits_reference = cast(Mapping[str, object], solution["limits"])
    expected_policy = {
        "planning_policy_version": policy["planning_policy_version"],
        "policy_id": policy["policy_id"],
        "policy_revision": policy["policy_revision"],
        "policy_fingerprint": contract_fingerprint(policy),
    }
    expected_limits = {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }
    if dict(policy_reference) != expected_policy:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            "solution.policy",
            "exact fingerprint/reference to PlanningPolicy",
            "solution policy reference does not identify the supplied policy",
        )
    if dict(limits_reference) != expected_limits:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            "solution.limits",
            "exact fingerprint/reference to SolveLimits",
            "solution limits reference does not identify the supplied limits",
        )
    stage = cast(list[Mapping[str, object]], solution["objective_stage_results"])[0]
    policy_stage = cast(list[Mapping[str, object]], policy["objective_stages"])[0]
    for key in ("stage_index", "objective_id", "metric", "sense"):
        if stage[key] != policy_stage[key]:
            _fail(
                PlanningContractReason.INVALID_REFERENCE,
                f"solution.objective_stage_results[0].{key}",
                "exact PlanningPolicy objective stage",
                "solution stage differs from the supplied policy",
            )
    allocated_wall_time = _number(
        stage["allocated_wall_time_seconds"],
        "solution.objective_stage_results[0].allocated_wall_time_seconds",
        exclusive=True,
    )
    max_wall_time = _number(
        limits["max_wall_time_seconds"],
        "limits.max_wall_time_seconds",
        exclusive=True,
    )
    if allocated_wall_time > max_wall_time:
        _fail(
            PlanningContractReason.INVALID_METRIC,
            "solution.objective_stage_results[0].allocated_wall_time_seconds",
            "stage budget <= SolveLimits max_wall_time_seconds",
            "objective stage budget exceeds the run limit",
        )

    for field in ("problem", "policy", "limits"):
        if report[field] != solution[field]:
            _fail(
                PlanningContractReason.INVALID_PROVENANCE,
                f"report.{field}",
                f"exact solution {field} reference",
                "report and solution provenance diverge",
            )
    solution_reference = cast(Mapping[str, object], report["solution"])
    expected_solution_reference = {
        "planning_solution_version": solution["planning_solution_version"],
        "solution_id": solution["solution_id"],
        "solution_fingerprint": contract_fingerprint(solution),
        "solver_status": solution["solver_status"],
    }
    if dict(solution_reference) != expected_solution_reference:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            "report.solution",
            "exact fingerprint/reference to PlanningSolution",
            "report solution reference does not identify the supplied solution",
        )
    for field in (
        "evidence_kind",
        "solver_status",
        "planning_run_outcome",
        "objective_stage_results",
        "diagnostics",
    ):
        if report[field] != solution[field]:
            _fail(
                PlanningContractReason.INVALID_STATUS_COMBINATION,
                f"report.{field}",
                f"same value as solution.{field}",
                "report and solution outcome evidence diverge",
            )


def statuses() -> Sequence[SolverStatus]:
    """Return the stable ordered status vocabulary."""

    return tuple(SolverStatus)


__all__ = [
    "CANONICALIZATION_VERSION",
    "CONSTRAINT_CONTRACT_VERSION",
    "DiagnosticDocument",
    "ERROR_REGISTRY_VERSION",
    "EvidenceKind",
    "LimitsReferenceDocument",
    "ModelMetricsDocument",
    "OBJECTIVE_POLICY_VERSION",
    "ObjectiveStageResultDocument",
    "OperationAssignmentDocument",
    "PLANNING_POLICY_VERSION",
    "PLANNING_SOLUTION_VERSION",
    "PlanningContractError",
    "PlanningContractReason",
    "PlanningRunOutcomeDocument",
    "PlanningSolutionDocument",
    "PolicyReferenceDocument",
    "ProblemReferenceDocument",
    "SCHEMA_SET_VERSION",
    "SOLVER_REPORT_VERSION",
    "SOLVE_LIMITS_VERSION",
    "STATE_MACHINE_CONTRACT_VERSION",
    "SolutionReferenceDocument",
    "SolverBackend",
    "SolverOutcome",
    "SolverParameterDocument",
    "SolverProvenanceDocument",
    "SolverReportDocument",
    "SolverStatus",
    "SolverTimingDocument",
    "canonical_contract_bytes",
    "contract_fingerprint",
    "outcome_document_for_status",
    "outcome_for_solver_status",
    "statuses",
    "validate_contract_bundle",
    "validate_planning_solution",
    "validate_solver_report",
]
