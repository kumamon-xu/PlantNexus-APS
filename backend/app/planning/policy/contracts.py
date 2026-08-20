"""Pure PlanningPolicy and SolveLimits machine contracts."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Literal, NoReturn, TypedDict, cast

from app.planning.contracts import (
    CANONICALIZATION_VERSION,
    CONSTRAINT_CONTRACT_VERSION,
    OBJECTIVE_POLICY_VERSION,
    PLANNING_POLICY_VERSION,
    SCHEMA_SET_VERSION,
    SOLVE_LIMITS_VERSION,
    PlanningContractError,
    PlanningContractReason,
)


P2_HARD_CONSTRAINT_IDS = tuple(f"C-{index:03d}" for index in range(1, 12))


class ContractSourceDocument(TypedDict):
    source_system: str
    source_version: str
    source_record_id: str


class ObjectiveStagePolicyDocument(TypedDict):
    stage_index: Literal[1]
    objective_id: Literal["OBJ-001"]
    metric: Literal["WEIGHTED_TARDINESS"]
    sense: Literal["MINIMIZE"]


class PlanningPolicyDocument(TypedDict):
    planning_policy_version: Literal["planning-policy.v1"]
    schema_set_version: Literal["2.4.0"]
    policy_id: str
    policy_revision: str
    data_plane: Literal["SIMULATION", "PRODUCTION"]
    policy_source: ContractSourceDocument
    canonicalization_version: Literal["canonical-json.v1"]
    constraint_contract_version: Literal["constraint-rule-sheet.v1"]
    objective_policy_version: Literal["objective-policy.v1"]
    hard_constraint_ids: list[str]
    objective_stages: list[ObjectiveStagePolicyDocument]


class SolveLimitsDocument(TypedDict):
    solve_limits_version: Literal["solve-limits.v1"]
    schema_set_version: Literal["2.4.0"]
    limits_id: str
    limits_revision: str
    data_plane: Literal["SIMULATION", "PRODUCTION"]
    limits_source: ContractSourceDocument
    canonicalization_version: Literal["canonical-json.v1"]
    max_wall_time_seconds: float
    max_workers: int
    random_seed: int


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


def _exact_keys(
    document: Mapping[str, object], expected: set[str], field: str
) -> None:
    observed = set(document)
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


def _source(value: object, field: str) -> None:
    if not isinstance(value, Mapping):
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            field,
            "source reference object",
            "source must be an object",
        )
    document = cast(Mapping[str, object], value)
    _exact_keys(document, {"source_system", "source_version", "source_record_id"}, field)
    for key in ("source_system", "source_version", "source_record_id"):
        _text(document[key], f"{field}.{key}")


def validate_planning_policy(document: Mapping[str, object]) -> None:
    """Require the P2 delivery-only lexicographic policy without defaults."""

    expected = {
        "planning_policy_version",
        "schema_set_version",
        "policy_id",
        "policy_revision",
        "data_plane",
        "policy_source",
        "canonicalization_version",
        "constraint_contract_version",
        "objective_policy_version",
        "hard_constraint_ids",
        "objective_stages",
    }
    _exact_keys(document, expected, "$")
    versions = {
        "planning_policy_version": PLANNING_POLICY_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "constraint_contract_version": CONSTRAINT_CONTRACT_VERSION,
        "objective_policy_version": OBJECTIVE_POLICY_VERSION,
    }
    for key, expected_value in versions.items():
        if document[key] != expected_value:
            _fail(
                PlanningContractReason.INVALID_VERSION,
                key,
                expected_value,
                "policy version is not supported",
            )
    _text(document["policy_id"], "policy_id", identifier=True)
    _text(document["policy_revision"], "policy_revision")
    if document["data_plane"] not in {"SIMULATION", "PRODUCTION"}:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            "data_plane",
            "SIMULATION or PRODUCTION",
            "policy data plane is not explicit",
        )
    _source(document["policy_source"], "policy_source")
    hard_constraints = document["hard_constraint_ids"]
    if not isinstance(hard_constraints, list) or tuple(hard_constraints) != P2_HARD_CONSTRAINT_IDS:
        _fail(
            PlanningContractReason.INVALID_REFERENCE,
            "hard_constraint_ids",
            "ordered C-001 through C-011",
            "P2 policy cannot omit, disable, reorder, or add hard constraints",
        )
    stages = document["objective_stages"]
    if not isinstance(stages, list) or len(stages) != 1:
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            "objective_stages",
            "exactly one OBJ-001 stage",
            "P2 policy must contain one delivery stage",
        )
    stage_value = stages[0]
    if not isinstance(stage_value, Mapping):
        _fail(
            PlanningContractReason.INVALID_SHAPE,
            "objective_stages[0]",
            "objective stage object",
            "P2 objective stage must be an object",
        )
    stage = cast(Mapping[str, object], stage_value)
    _exact_keys(
        stage,
        {"stage_index", "objective_id", "metric", "sense"},
        "objective_stages[0]",
    )
    expected_stage = {
        "stage_index": 1,
        "objective_id": "OBJ-001",
        "metric": "WEIGHTED_TARDINESS",
        "sense": "MINIMIZE",
    }
    if dict(stage) != expected_stage:
        _fail(
            PlanningContractReason.INVALID_REFERENCE,
            "objective_stages[0]",
            str(expected_stage),
            "policy changes the accepted P2 objective decision",
        )


def validate_solve_limits(document: Mapping[str, object]) -> None:
    """Validate explicit solver-neutral budgets without inventing defaults."""

    expected = {
        "solve_limits_version",
        "schema_set_version",
        "limits_id",
        "limits_revision",
        "data_plane",
        "limits_source",
        "canonicalization_version",
        "max_wall_time_seconds",
        "max_workers",
        "random_seed",
    }
    _exact_keys(document, expected, "$")
    versions = {
        "solve_limits_version": SOLVE_LIMITS_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
    }
    for key, expected_value in versions.items():
        if document[key] != expected_value:
            _fail(
                PlanningContractReason.INVALID_VERSION,
                key,
                expected_value,
                "limits version is not supported",
            )
    _text(document["limits_id"], "limits_id", identifier=True)
    _text(document["limits_revision"], "limits_revision")
    if document["data_plane"] not in {"SIMULATION", "PRODUCTION"}:
        _fail(
            PlanningContractReason.INVALID_PROVENANCE,
            "data_plane",
            "SIMULATION or PRODUCTION",
            "limits data plane is not explicit",
        )
    _source(document["limits_source"], "limits_source")
    wall_time = document["max_wall_time_seconds"]
    if (
        isinstance(wall_time, bool)
        or not isinstance(wall_time, (int, float))
        or not math.isfinite(float(wall_time))
        or float(wall_time) <= 0
    ):
        _fail(
            PlanningContractReason.INVALID_METRIC,
            "max_wall_time_seconds",
            "finite number > 0",
            "wall-time limit is invalid",
        )
    workers = document["max_workers"]
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        _fail(
            PlanningContractReason.INVALID_METRIC,
            "max_workers",
            "integer >= 1",
            "worker limit is invalid",
        )
    seed = document["random_seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        _fail(
            PlanningContractReason.INVALID_METRIC,
            "random_seed",
            "integer >= 0",
            "random seed is invalid",
        )


__all__ = [
    "ContractSourceDocument",
    "ObjectiveStagePolicyDocument",
    "P2_HARD_CONSTRAINT_IDS",
    "PlanningPolicyDocument",
    "SolveLimitsDocument",
    "validate_planning_policy",
    "validate_solve_limits",
]
