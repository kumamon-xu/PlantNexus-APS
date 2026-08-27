"""Versioned Simulation freeze policy and deterministic interval resolution.

OPEN-005 leaves every Production freeze value unresolved.  This module owns
one explicitly versioned Simulation policy and resolves it only from the
immutable new PlanningSnapshot cutoff.  It has no clock, environment, solver,
persistence, API, or UI fallback.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import NoReturn, cast

from app.domain.execution_contracts import (
    contract_fingerprint,
    freeze_policy_fingerprint,
    require_p4_document,
)
from app.planning.policy.contracts import P2_HARD_CONSTRAINT_IDS
from app.snapshots.canonical import verify_snapshot
from app.snapshots.contracts import ImmutablePlanningSnapshot, SnapshotDataPlane


FREEZE_POLICY_VERSION = "freeze-policy.v1"
FREEZE_INTERVAL_SEMANTICS = "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE"
SIMULATION_REPLAN_POLICY_ID = "POLICY-P4-SIM-DYNAMIC-FREEZE-001"
SIMULATION_REPLAN_POLICY_REVISION = "1.0.0"
SIMULATION_FREEZE_POLICY_ID = "FREEZE-POLICY-P4-SIM-001"
SIMULATION_FREEZE_POLICY_REVISION = "1.0.0"
SIMULATION_FREEZE_SOURCE_SYSTEM = "plantnexus-synthetic-policy"
SIMULATION_FREEZE_SOURCE_VERSION = "1.0.0"
SIMULATION_FREEZE_SOURCE_RECORD_ID = "SIM-P4-FREEZE-001"
SIMULATION_FREEZE_WINDOW_SECONDS = 900


class FreezePolicyFailure(StrEnum):
    """Stable module-local failures; the product error registry is unchanged."""

    INVALID_POLICY = "INVALID_POLICY"
    UNAPPROVED_SIMULATION_POLICY = "UNAPPROVED_SIMULATION_POLICY"
    PRODUCTION_NOT_AUTHORIZED = "PRODUCTION_NOT_AUTHORIZED"
    SNAPSHOT_PLANE_MISMATCH = "SNAPSHOT_PLANE_MISMATCH"
    INVALID_FREEZE_ANCHOR = "INVALID_FREEZE_ANCHOR"


class FreezePolicyError(ValueError):
    """Fail-closed policy rejection before projection or solve."""

    def __init__(self, reason: FreezePolicyFailure, *, field: str, message: str) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value} at {field}: {message}")


@dataclass(frozen=True, slots=True)
class ResolvedFreezePolicy:
    """Immutable resolution anchored to one verified new Snapshot."""

    policy_id: str
    policy_revision: str
    policy_fingerprint: str
    freeze_policy_id: str
    freeze_policy_revision: str
    freeze_policy_fingerprint: str
    source_system: str
    source_version: str
    source_record_id: str
    window_seconds: int
    effective_from_utc: str
    effective_until_utc: str

    def document(self, *, effective_lock_ids: tuple[str, ...] = ()) -> dict[str, object]:
        """Return the exact ReplanRequest ``freezeResolution`` shape."""

        return {
            "freeze_policy_version": FREEZE_POLICY_VERSION,
            "freeze_policy_id": self.freeze_policy_id,
            "freeze_policy_revision": self.freeze_policy_revision,
            "freeze_policy_fingerprint": self.freeze_policy_fingerprint,
            "source": {
                "source_system": self.source_system,
                "source_version": self.source_version,
                "source_record_id": self.source_record_id,
            },
            "window_seconds": self.window_seconds,
            "effective_from_utc": self.effective_from_utc,
            "effective_until_utc": self.effective_until_utc,
            "interval_semantics": FREEZE_INTERVAL_SEMANTICS,
            "effective_lock_ids": list(effective_lock_ids),
        }

    def policy_reference(self) -> dict[str, object]:
        """Return the exact PlanningPolicy v2 reference shape."""

        return {
            "planning_policy_version": "planning-policy.v2",
            "policy_id": self.policy_id,
            "policy_revision": self.policy_revision,
            "policy_fingerprint": self.policy_fingerprint,
        }


def _reject(reason: FreezePolicyFailure, *, field: str, message: str) -> NoReturn:
    raise FreezePolicyError(reason, field=field, message=message)


def _utc_second(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _reject(
            FreezePolicyFailure.INVALID_FREEZE_ANCHOR,
            field=field,
            message="freeze anchor must be an RFC3339 UTC Z instant",
        )
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FreezePolicyError(
            FreezePolicyFailure.INVALID_FREEZE_ANCHOR,
            field=field,
            message="freeze anchor is not a valid UTC instant",
        ) from error
    if instant.microsecond != 0:
        _reject(
            FreezePolicyFailure.INVALID_FREEZE_ANCHOR,
            field=field,
            message="freeze anchor must have whole-second precision",
        )
    return instant


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def simulation_replan_policy() -> dict[str, object]:
    """Return the sole repository-approved P4 Simulation freeze policy."""

    policy: dict[str, object] = {
        "planning_policy_version": "planning-policy.v2",
        "schema_set_version": "2.8.0",
        "policy_id": SIMULATION_REPLAN_POLICY_ID,
        "policy_revision": SIMULATION_REPLAN_POLICY_REVISION,
        "data_plane": "SIMULATION",
        "policy_source": {
            "source_system": SIMULATION_FREEZE_SOURCE_SYSTEM,
            "source_version": SIMULATION_FREEZE_SOURCE_VERSION,
            "source_record_id": SIMULATION_FREEZE_SOURCE_RECORD_ID,
        },
        "canonicalization_version": "canonical-json.v1",
        "constraint_contract_version": "constraint-rule-sheet.v1",
        "objective_policy_version": "objective-policy.v2",
        "hard_constraint_ids": list(P2_HARD_CONSTRAINT_IDS),
        "freeze_policy": {
            "freeze_policy_version": FREEZE_POLICY_VERSION,
            "freeze_policy_id": SIMULATION_FREEZE_POLICY_ID,
            "freeze_policy_revision": SIMULATION_FREEZE_POLICY_REVISION,
            "source": {
                "source_system": SIMULATION_FREEZE_SOURCE_SYSTEM,
                "source_version": SIMULATION_FREEZE_SOURCE_VERSION,
                "source_record_id": SIMULATION_FREEZE_SOURCE_RECORD_ID,
            },
            "window_seconds": SIMULATION_FREEZE_WINDOW_SECONDS,
            "interval_semantics": FREEZE_INTERVAL_SEMANTICS,
        },
        "objective_stages": [
            {
                "stage_index": 1,
                "objective_id": "OBJ-001",
                "metric": "WEIGHTED_TARDINESS_SECONDS",
                "sense": "MINIMIZE",
            },
            {
                "stage_index": 2,
                "objective_id": "OBJ-002",
                "metric": "STABILITY_VECTOR",
                "sense": "LEXICOGRAPHIC_MINIMIZE",
                "components": [
                    "SOFT_LOCK_VIOLATIONS",
                    "CHANGED_EXISTING_OPERATIONS",
                    "RESOURCE_CHANGES",
                    "ABSOLUTE_START_SHIFT_SECONDS",
                ],
            },
            {
                "stage_index": 3,
                "objective_id": "OBJ-003",
                "metric": "MAKESPAN_SECONDS",
                "sense": "MINIMIZE",
            },
        ],
    }
    require_p4_document(policy)
    return cast(dict[str, object], deepcopy(policy))


def resolve_simulation_freeze_policy(
    policy: Mapping[str, object],
    snapshot: ImmutablePlanningSnapshot,
) -> ResolvedFreezePolicy:
    """Validate the approved policy and resolve ``[cutoff, cutoff+duration)``."""

    if policy.get("data_plane") != "SIMULATION":
        _reject(
            FreezePolicyFailure.PRODUCTION_NOT_AUTHORIZED,
            field="policy.data_plane",
            message="OPEN-005 provides no approved Production freeze policy",
        )
    try:
        require_p4_document(policy)
    except ValueError as error:
        raise FreezePolicyError(
            FreezePolicyFailure.INVALID_POLICY,
            field=getattr(error, "field", "policy"),
            message="PlanningPolicy v2 failed its immutable contract",
        ) from error
    if dict(policy) != simulation_replan_policy():
        _reject(
            FreezePolicyFailure.UNAPPROVED_SIMULATION_POLICY,
            field="policy",
            message="policy differs from SIM-P4-FREEZE-001@1.0.0",
        )
    verify_snapshot(snapshot)
    snapshot_document = snapshot.document
    if snapshot.data_plane is not SnapshotDataPlane.SIMULATION or snapshot_document.get(
        "synthetic"
    ) is not True:
        _reject(
            FreezePolicyFailure.SNAPSHOT_PLANE_MISMATCH,
            field="snapshot.data_plane",
            message="P4 freeze execution is isolated to verified Simulation Snapshots",
        )
    start_text = snapshot_document.get("cutoff_at_utc")
    start = _utc_second(start_text, "snapshot.cutoff_at_utc")
    freeze = cast(Mapping[str, object], policy["freeze_policy"])
    window = freeze.get("window_seconds")
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        _reject(
            FreezePolicyFailure.INVALID_POLICY,
            field="policy.freeze_policy.window_seconds",
            message="freeze duration must be a positive integer number of seconds",
        )
    source = cast(Mapping[str, object], freeze["source"])
    return ResolvedFreezePolicy(
        policy_id=cast(str, policy["policy_id"]),
        policy_revision=cast(str, policy["policy_revision"]),
        policy_fingerprint=contract_fingerprint(policy),
        freeze_policy_id=cast(str, freeze["freeze_policy_id"]),
        freeze_policy_revision=cast(str, freeze["freeze_policy_revision"]),
        freeze_policy_fingerprint=freeze_policy_fingerprint(freeze),
        source_system=cast(str, source["source_system"]),
        source_version=cast(str, source["source_version"]),
        source_record_id=cast(str, source["source_record_id"]),
        window_seconds=window,
        effective_from_utc=cast(str, start_text),
        effective_until_utc=_format_utc(start + timedelta(seconds=window)),
    )


__all__ = [
    "FREEZE_INTERVAL_SEMANTICS",
    "FREEZE_POLICY_VERSION",
    "FreezePolicyError",
    "FreezePolicyFailure",
    "ResolvedFreezePolicy",
    "SIMULATION_FREEZE_POLICY_ID",
    "SIMULATION_FREEZE_POLICY_REVISION",
    "SIMULATION_FREEZE_SOURCE_RECORD_ID",
    "SIMULATION_FREEZE_WINDOW_SECONDS",
    "SIMULATION_REPLAN_POLICY_ID",
    "SIMULATION_REPLAN_POLICY_REVISION",
    "resolve_simulation_freeze_policy",
    "simulation_replan_policy",
]
