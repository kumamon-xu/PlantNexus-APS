"""Approved P2 Simulation delivery policy and explicit solve limits.

OPEN-006 keeps Production priority/tardiness semantics unresolved.  This
module therefore exposes one repository-owned Simulation policy and requires
every objective weight to carry the matching synthetic source version.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import NoReturn

from app.planning.policy.contracts import (
    P2_HARD_CONSTRAINT_IDS,
    PlanningPolicyDocument,
    SolveLimitsDocument,
    validate_planning_policy,
    validate_solve_limits,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2


SIMULATION_DELIVERY_POLICY_ID = "POLICY-P2-SIM-DELIVERY-OBJ001-001"
SIMULATION_DELIVERY_POLICY_REVISION = "1.0.0"
SIMULATION_DELIVERY_SOURCE_SYSTEM = "plantnexus-synthetic-policy"
SIMULATION_DELIVERY_SOURCE_VERSION = "1.0.0"


class DeliveryPolicyReason(StrEnum):
    """Stable fail-closed reasons at the P2 strategy boundary."""

    PRODUCTION_NOT_AUTHORIZED = "PRODUCTION_NOT_AUTHORIZED"
    UNAPPROVED_SIMULATION_POLICY = "UNAPPROVED_SIMULATION_POLICY"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    UNAPPROVED_LIMITS_SOURCE = "UNAPPROVED_LIMITS_SOURCE"
    UNAPPROVED_PRIORITY_SOURCE = "UNAPPROVED_PRIORITY_SOURCE"


class DeliveryPolicyError(ValueError):
    """The run does not use the approved versioned Simulation policy."""

    def __init__(
        self,
        reason: DeliveryPolicyReason,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value} at {field}: {message}")


def _reject(
    reason: DeliveryPolicyReason,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise DeliveryPolicyError(reason, field=field, message=message)


def simulation_delivery_policy() -> PlanningPolicyDocument:
    """Return the sole repository-approved P2 OBJ-001 Simulation policy."""

    policy: PlanningPolicyDocument = {
        "planning_policy_version": "planning-policy.v1",
        "schema_set_version": "2.4.0",
        "policy_id": SIMULATION_DELIVERY_POLICY_ID,
        "policy_revision": SIMULATION_DELIVERY_POLICY_REVISION,
        "data_plane": "SIMULATION",
        "policy_source": {
            "source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
            "source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
            "source_record_id": SIMULATION_DELIVERY_POLICY_ID,
        },
        "canonicalization_version": "canonical-json.v1",
        "constraint_contract_version": "constraint-rule-sheet.v1",
        "objective_policy_version": "objective-policy.v1",
        "hard_constraint_ids": list(P2_HARD_CONSTRAINT_IDS),
        "objective_stages": [
            {
                "stage_index": 1,
                "objective_id": "OBJ-001",
                "metric": "WEIGHTED_TARDINESS",
                "sense": "MINIMIZE",
            }
        ],
    }
    validate_planning_policy(policy)
    return policy


def simulation_solve_limits(
    *,
    limits_id: str,
    limits_revision: str,
    source_record_id: str,
    max_wall_time_seconds: float,
    max_workers: int,
    random_seed: int,
) -> SolveLimitsDocument:
    """Build explicit Simulation limits; intentionally provides no defaults."""

    limits: SolveLimitsDocument = {
        "solve_limits_version": "solve-limits.v1",
        "schema_set_version": "2.4.0",
        "limits_id": limits_id,
        "limits_revision": limits_revision,
        "data_plane": "SIMULATION",
        "limits_source": {
            "source_system": SIMULATION_DELIVERY_SOURCE_SYSTEM,
            "source_version": SIMULATION_DELIVERY_SOURCE_VERSION,
            "source_record_id": source_record_id,
        },
        "canonicalization_version": "canonical-json.v1",
        "max_wall_time_seconds": max_wall_time_seconds,
        "max_workers": max_workers,
        "random_seed": random_seed,
    }
    validate_solve_limits(limits)
    return limits


def validate_simulation_delivery_execution(
    problem: PlanningProblemDocumentV2,
    policy: PlanningPolicyDocument,
    limits: SolveLimitsDocument,
) -> None:
    """Reject Production or unapproved synthetic weight provenance before solve."""

    validate_planning_policy(policy)
    validate_solve_limits(limits)
    if policy["data_plane"] != limits["data_plane"]:
        _reject(
            DeliveryPolicyReason.DATA_PLANE_MISMATCH,
            field="policy.data_plane/limits.data_plane",
            message="policy and limits must identify the same explicit data plane",
        )
    if policy["data_plane"] != "SIMULATION":
        _reject(
            DeliveryPolicyReason.PRODUCTION_NOT_AUTHORIZED,
            field="policy.data_plane/limits.data_plane",
            message="OPEN-006/011/012 allow P2 objective execution only in Simulation",
        )
    if policy != simulation_delivery_policy():
        _reject(
            DeliveryPolicyReason.UNAPPROVED_SIMULATION_POLICY,
            field="policy",
            message="policy differs from the approved P2 Simulation OBJ-001 revision",
        )
    if (
        limits["limits_source"]["source_system"]
        != SIMULATION_DELIVERY_SOURCE_SYSTEM
        or limits["limits_source"]["source_version"]
        != SIMULATION_DELIVERY_SOURCE_VERSION
    ):
        _reject(
            DeliveryPolicyReason.UNAPPROVED_LIMITS_SOURCE,
            field="limits.limits_source",
            message=(
                "solve limits are not owned by the approved versioned "
                "Simulation delivery source"
            ),
        )
    for index, demand in enumerate(problem["delivery_demands"]):
        if (
            demand["priority_source_system"]
            != SIMULATION_DELIVERY_SOURCE_SYSTEM
            or demand["priority_source_version"]
            != SIMULATION_DELIVERY_SOURCE_VERSION
        ):
            _reject(
                DeliveryPolicyReason.UNAPPROVED_PRIORITY_SOURCE,
                field=f"delivery_demands[{index}].priority_source",
                message=(
                    "priority weight is not owned by the approved versioned "
                    "Simulation delivery source"
                ),
            )


def is_approved_simulation_delivery_policy(
    policy: Mapping[str, object],
) -> bool:
    """Return a side-effect-free exact-policy predicate for evidence checks."""

    return dict(policy) == simulation_delivery_policy()


__all__ = [
    "DeliveryPolicyError",
    "DeliveryPolicyReason",
    "SIMULATION_DELIVERY_POLICY_ID",
    "SIMULATION_DELIVERY_POLICY_REVISION",
    "SIMULATION_DELIVERY_SOURCE_SYSTEM",
    "SIMULATION_DELIVERY_SOURCE_VERSION",
    "is_approved_simulation_delivery_policy",
    "simulation_delivery_policy",
    "simulation_solve_limits",
    "validate_simulation_delivery_execution",
]
