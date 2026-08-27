"""Solver-neutral freeze-window and effective-lock projection.

The projection consumes immutable Snapshot/Problem/base ScheduleVersion inputs
and never rewrites ``planning-problem.v2``.  It classifies authoritative facts,
explicit locks, and freeze-derived locks into a separate content-addressed
carrier for later P4 solver/application consumers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import json
from math import ceil
from typing import NoReturn, cast

from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    require_p4_document,
)
from app.domain.workspace_contracts import require_workspace_document
from app.planning.policy.freeze_window import (
    ResolvedFreezePolicy,
    resolve_simulation_freeze_policy,
)
from app.planning.problem.contracts import ImmutablePlanningProblemV2
from app.planning.problem.hashing import verify_problem_v2
from app.snapshots.canonical import verify_snapshot
from app.snapshots.contracts import ImmutablePlanningSnapshot, SnapshotDataPlane


EFFECTIVE_LOCK_PROJECTION_VERSION = "effective-lock-projection.v1"
FREEZE_DERIVED_LOCK_VERSION = "freeze-derived-lock.v1"
_ASSIGNMENT_FIELDS = {
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


class FreezeProjectionFailure(StrEnum):
    """Stable local projection failures without extending product error codes."""

    INVALID_BASE_SCHEDULE = "INVALID_BASE_SCHEDULE"
    INVALID_SNAPSHOT = "INVALID_SNAPSHOT"
    INVALID_PROBLEM = "INVALID_PROBLEM"
    POLICY_REJECTED = "POLICY_REJECTED"
    PLANE_MISMATCH = "PLANE_MISMATCH"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    DUPLICATE_OPERATION = "DUPLICATE_OPERATION"
    STALE_BASE = "STALE_BASE"
    UNREPRESENTABLE_LOCK = "UNREPRESENTABLE_LOCK"
    FACT_LOCK_CONFLICT = "FACT_LOCK_CONFLICT"
    HARD_LOCK_CONFLICT = "HARD_LOCK_CONFLICT"
    FREEZE_LOCK_CONFLICT = "FREEZE_LOCK_CONFLICT"


class FreezeProjectionError(ValueError):
    """Fail-closed rejection before Solver, Version, or persistence side effects."""

    def __init__(
        self,
        reason: FreezeProjectionFailure,
        *,
        field: str,
        entity_id: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        self.message = message
        super().__init__(f"{reason.value} at {field} ({entity_id}): {message}")


@dataclass(frozen=True, slots=True)
class EffectiveLockProjection:
    """Immutable canonical effective-lock carrier."""

    canonical_bytes: bytes
    projection_fingerprint: str

    @property
    def document(self) -> dict[str, object]:
        decoded = json.loads(self.canonical_bytes)
        return cast(dict[str, object], decoded)


@dataclass(frozen=True, slots=True)
class _Tuple:
    operation_id: str
    resource_id: str
    start_at_utc: str
    end_at_utc: str

    def values(self) -> tuple[str, str, str]:
        return self.resource_id, self.start_at_utc, self.end_at_utc


def _reject(
    reason: FreezeProjectionFailure,
    *,
    field: str,
    entity_id: str,
    message: str,
) -> NoReturn:
    raise FreezeProjectionError(
        reason,
        field=field,
        entity_id=entity_id,
        message=message,
    )


def _mapping(value: object, field: str, entity_id: str = "<input>") -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(
            FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
            field=field,
            entity_id=entity_id,
            message="value must be an object",
        )
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str, entity_id: str = "<input>") -> Sequence[object]:
    if not isinstance(value, list):
        _reject(
            FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
            field=field,
            entity_id=entity_id,
            message="value must be an array",
        )
    return value


def _identifier(value: object, field: str, entity_id: str = "<input>") -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        _reject(
            FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
            field=field,
            entity_id=entity_id,
            message="value must be a canonical identifier",
        )
    return value


def _integer(value: object, field: str, entity_id: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _reject(
            FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
            field=field,
            entity_id=entity_id,
            message=f"value must be an integer >= {minimum}",
        )
    return value


def _utc_second(value: object, field: str, entity_id: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _reject(
            FreezeProjectionFailure.UNREPRESENTABLE_LOCK,
            field=field,
            entity_id=entity_id,
            message="instant must be RFC3339 UTC Z",
        )
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FreezeProjectionError(
            FreezeProjectionFailure.UNREPRESENTABLE_LOCK,
            field=field,
            entity_id=entity_id,
            message="instant is invalid",
        ) from error
    if instant.microsecond:
        _reject(
            FreezeProjectionFailure.UNREPRESENTABLE_LOCK,
            field=field,
            entity_id=entity_id,
            message="instant must have whole-second precision",
        )
    return instant


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_base_schedule(document: Mapping[str, object]) -> str:
    version = document.get("schedule_version_version")
    try:
        if version == "schedule-version.v1":
            require_workspace_document(document)
        elif version == "schedule-version.v2":
            require_p4_document(document)
        else:
            _reject(
                FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
                field="base_schedule.schedule_version_version",
                entity_id=str(document.get("schedule_version_id", "<base>")),
                message="only immutable schedule-version.v1/v2 are supported",
            )
    except FreezeProjectionError:
        raise
    except ValueError as error:
        raise FreezeProjectionError(
            FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
            field=getattr(error, "field", "base_schedule"),
            entity_id=str(document.get("schedule_version_id", "<base>")),
            message="base ScheduleVersion failed its immutable contract",
        ) from error
    schedule_id = _identifier(
        document.get("schedule_version_id"), "base_schedule.schedule_version_id"
    )
    if document.get("state") != "PUBLISHED":
        _reject(
            FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
            field="base_schedule.state",
            entity_id=schedule_id,
            message="freeze projection requires an exact PUBLISHED base",
        )
    if (
        document.get("data_plane") != "SIMULATION"
        or document.get("synthetic") is not True
        or document.get("environment") not in {"DEVELOPMENT", "TEST", "BENCHMARK"}
    ):
        _reject(
            FreezeProjectionFailure.PLANE_MISMATCH,
            field="base_schedule.data_plane",
            entity_id=schedule_id,
            message="P4-05 is authorized only for isolated Simulation evidence",
        )
    return cast(str, version)


def _assignment_index(
    base_schedule: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    schedule_id = cast(str, base_schedule["schedule_version_id"])
    content = _mapping(base_schedule.get("content"), "base_schedule.content", schedule_id)
    assignments = _sequence(
        content.get("assignments"), "base_schedule.content.assignments", schedule_id
    )
    indexed: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(assignments):
        assignment = _mapping(
            raw, f"base_schedule.content.assignments[{index}]", schedule_id
        )
        operation_id = _identifier(
            assignment.get("operation_id"),
            f"base_schedule.content.assignments[{index}].operation_id",
            schedule_id,
        )
        if set(assignment) != _ASSIGNMENT_FIELDS:
            _reject(
                FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
                field=f"base_schedule.content.assignments[{index}]",
                entity_id=operation_id,
                message="assignment fields differ from the frozen ScheduleVersion contract",
            )
        if operation_id in indexed:
            _reject(
                FreezeProjectionFailure.DUPLICATE_OPERATION,
                field="base_schedule.content.assignments",
                entity_id=operation_id,
                message="base operation must appear exactly once",
            )
        resource_id = _identifier(
            assignment.get("resource_id"), "assignment.resource_id", operation_id
        )
        start = _utc_second(assignment.get("start_at_utc"), "assignment.start_at_utc", operation_id)
        end = _utc_second(assignment.get("end_at_utc"), "assignment.end_at_utc", operation_id)
        duration_seconds = _integer(
            assignment.get("duration_seconds"), "assignment.duration_seconds", operation_id, minimum=1
        )
        start_tick = _integer(
            assignment.get("start_tick"), "assignment.start_tick", operation_id
        )
        end_tick = _integer(
            assignment.get("end_tick"), "assignment.end_tick", operation_id, minimum=1
        )
        duration_ticks = _integer(
            assignment.get("duration_ticks"), "assignment.duration_ticks", operation_id, minimum=1
        )
        if end <= start or int((end - start).total_seconds()) != duration_seconds:
            _reject(
                FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
                field="assignment.duration_seconds",
                entity_id=operation_id,
                message="UTC assignment interval and duration diverge",
            )
        if end_tick - start_tick != duration_ticks:
            _reject(
                FreezeProjectionFailure.INVALID_BASE_SCHEDULE,
                field="assignment.duration_ticks",
                entity_id=operation_id,
                message="tick assignment interval and duration diverge",
            )
        _ = resource_id
        indexed[operation_id] = assignment
    return indexed


def _tuple_from_assignment(assignment: Mapping[str, object]) -> _Tuple:
    return _Tuple(
        operation_id=cast(str, assignment["operation_id"]),
        resource_id=cast(str, assignment["resource_id"]),
        start_at_utc=cast(str, assignment["start_at_utc"]),
        end_at_utc=cast(str, assignment["end_at_utc"]),
    )


def _tuple_from_lock(lock: Mapping[str, object]) -> _Tuple:
    return _Tuple(
        operation_id=cast(str, lock["operation_id"]),
        resource_id=cast(str, lock["resource_id"]),
        start_at_utc=cast(str, lock["start_at_utc"]),
        end_at_utc=cast(str, lock["end_at_utc"]),
    )


def _resource_durations(operation: Mapping[str, object]) -> dict[str, int]:
    values: dict[str, int] = {}
    for option in cast(Sequence[Mapping[str, object]], operation["resource_options"]):
        values[cast(str, option["resource_id"])] = cast(
            int, option["final_duration_seconds"]
        )
    return values


def _require_grid_tuple(
    value: _Tuple,
    *,
    operation: Mapping[str, object],
    cutoff: datetime,
    horizon_end: datetime,
    tick_seconds: int,
    failure: FreezeProjectionFailure,
) -> None:
    start = _utc_second(value.start_at_utc, "lock.start_at_utc", value.operation_id)
    end = _utc_second(value.end_at_utc, "lock.end_at_utc", value.operation_id)
    if start < cutoff or end > horizon_end or end <= start:
        _reject(
            failure,
            field="lock.interval",
            entity_id=value.operation_id,
            message="protected interval must remain wholly inside the new Problem horizon",
        )
    start_offset = int((start - cutoff).total_seconds())
    end_offset = int((end - cutoff).total_seconds())
    if start_offset % tick_seconds or end_offset % tick_seconds:
        _reject(
            FreezeProjectionFailure.UNREPRESENTABLE_LOCK,
            field="lock.interval",
            entity_id=value.operation_id,
            message="protected tuple is not exactly representable on the new Problem grid",
        )
    durations = _resource_durations(operation)
    expected_seconds = (
        cast(int, operation["remaining_seconds"])
        if operation["status"] == "RUNNING"
        else durations.get(value.resource_id)
    )
    if expected_seconds is None or value.resource_id not in durations:
        _reject(
            failure,
            field="lock.resource_id",
            entity_id=value.operation_id,
            message="protected resource is not a candidate in the new Problem",
        )
    expected_ticks = ceil(expected_seconds / tick_seconds)
    if end_offset - start_offset != expected_ticks * tick_seconds:
        _reject(
            failure,
            field="lock.interval",
            entity_id=value.operation_id,
            message="protected tuple conflicts with authoritative selected duration",
        )


def _protection_document(
    value: _Tuple,
    *,
    kind: str,
    priority: int,
    reference_id: str,
    fact_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "protection_kind": kind,
        "protection_priority": priority,
        "reference_id": reference_id,
        "operation_id": value.operation_id,
        "resource_id": value.resource_id,
        "start_at_utc": value.start_at_utc,
        "end_at_utc": value.end_at_utc,
    }
    if fact_evidence is not None:
        document["fact_evidence"] = dict(fact_evidence)
    return document


def _execution_fact_indexes(
    snapshot_document: Mapping[str, object],
) -> tuple[
    dict[str, Mapping[str, object]],
    dict[str, Mapping[str, object]],
]:
    instances = {
        cast(str, item["operation_instance_id"]): item
        for item in cast(
            Sequence[Mapping[str, object]], snapshot_document["operation_instances"]
        )
    }
    facts = {
        cast(str, item["execution_fact_id"]): item
        for item in cast(
            Sequence[Mapping[str, object]],
            cast(Mapping[str, object], snapshot_document["records"])[
                "execution_facts"
            ],
        )
    }
    return instances, facts


def _fact_evidence(fact: Mapping[str, object]) -> dict[str, object]:
    source = cast(Mapping[str, object], fact["source"])
    evidence: dict[str, object] = {
        "status": fact["status"],
        "observed_at_utc": fact["observed_at_utc"],
        "actual_start_at_utc": fact["actual_start_at_utc"],
        "source": dict(source),
    }
    for field in (
        "actual_end_at_utc",
        "remaining_quantity",
        "remaining_seconds",
        "completed_quantity",
        "quantity_unit",
    ):
        if field in fact:
            evidence[field] = fact[field]
    return evidence


def _historical_anchor(
    operation_id: str,
    fact: Mapping[str, object],
) -> dict[str, object]:
    source = cast(Mapping[str, object], fact["source"])
    return {
        "operation_id": operation_id,
        "execution_fact_id": fact["execution_fact_id"],
        "resource_id": fact["resource_id"],
        "actual_start_at_utc": fact["actual_start_at_utc"],
        "actual_end_at_utc": fact["actual_end_at_utc"],
        "source_system": source["source_system"],
        "source_version": source["source_version"],
        "source_record_id": source["source_record_id"],
    }


def _snapshot_option_projection(instance: Mapping[str, object]) -> list[dict[str, object]]:
    fields = (
        "resource_id",
        "setup_seconds",
        "cycle_seconds_per_unit",
        "final_duration_seconds",
        "duration_source",
        "source_version",
    )
    return sorted(
        [
            {field: option[field] for field in fields}
            for option in cast(
                Sequence[Mapping[str, object]], instance["resource_options"]
            )
        ],
        key=lambda item: cast(str, item["resource_id"]),
    )


def _require_problem_snapshot_projection(
    *,
    snapshot_document: Mapping[str, object],
    problem_document: Mapping[str, object],
    snapshot_instances: Mapping[str, Mapping[str, object]],
    operations: Mapping[str, Mapping[str, object]],
    horizon_start: datetime,
) -> None:
    shared_fields = (
        "demand_order_id",
        "status",
        "release_at_utc",
        "material_ready_at_utc",
        "required_capabilities",
    )
    for operation_id, operation in operations.items():
        instance = snapshot_instances[operation_id]
        if any(operation.get(field) != instance.get(field) for field in shared_fields):
            _reject(
                FreezeProjectionFailure.LINEAGE_MISMATCH,
                field="problem.operation_instances",
                entity_id=operation_id,
                message="Problem operation facts differ from the exact Snapshot projection",
            )
        observed_options = sorted(
            [
                dict(option)
                for option in cast(
                    Sequence[Mapping[str, object]], operation["resource_options"]
                )
            ],
            key=lambda item: cast(str, item["resource_id"]),
        )
        if observed_options != _snapshot_option_projection(instance):
            _reject(
                FreezeProjectionFailure.LINEAGE_MISMATCH,
                field="problem.operation_instances.resource_options",
                entity_id=operation_id,
                message="Problem resource options differ from the exact Snapshot projection",
            )

    records = cast(Mapping[str, object], snapshot_document["records"])
    locks_by_id = {
        cast(str, lock["lock_id"]): lock
        for lock in cast(
            Sequence[Mapping[str, object]], records["operation_locks"]
        )
    }
    expected_locks: list[dict[str, object]] = []
    for operation_id in sorted(operations):
        instance = snapshot_instances[operation_id]
        for lock_id in cast(Sequence[str], instance["lock_ids"]):
            lock = locks_by_id[lock_id]
            if _utc_second(lock["end_at_utc"], "lock.end_at_utc", lock_id) <= horizon_start:
                continue
            source = cast(Mapping[str, object], lock["source"])
            expected_locks.append(
                {
                    "lock_id": lock_id,
                    "operation_id": operation_id,
                    "lock_type": lock["lock_type"],
                    "resource_id": lock["resource_id"],
                    "start_at_utc": lock["start_at_utc"],
                    "end_at_utc": lock["end_at_utc"],
                    "source_system": source["source_system"],
                    "source_version": source["source_version"],
                    "source_record_id": source["source_record_id"],
                }
            )
    expected_locks.sort(key=lambda item: cast(str, item["lock_id"]))
    observed_locks = sorted(
        [
            dict(lock)
            for lock in cast(
                Sequence[Mapping[str, object]], problem_document["operation_locks"]
            )
        ],
        key=lambda item: cast(str, item["lock_id"]),
    )
    if observed_locks != expected_locks:
        _reject(
            FreezeProjectionFailure.LINEAGE_MISMATCH,
            field="problem.operation_locks",
            entity_id=cast(str, problem_document["problem_hash"]),
            message="Problem locks differ from the exact active Snapshot lock projection",
        )


def _derived_lock(
    value: _Tuple,
    *,
    base_schedule: Mapping[str, object],
    problem: Mapping[str, object],
    resolved: ResolvedFreezePolicy,
) -> dict[str, object]:
    identity_input = {
        "freeze_derived_lock_version": FREEZE_DERIVED_LOCK_VERSION,
        "base_schedule_version": {
            "schedule_version_version": base_schedule["schedule_version_version"],
            "schedule_version_id": base_schedule["schedule_version_id"],
            "content_fingerprint": base_schedule["content_fingerprint"],
        },
        "problem_hash": problem["problem_hash"],
        "freeze_policy_fingerprint": resolved.freeze_policy_fingerprint,
        "operation_id": value.operation_id,
        "resource_id": value.resource_id,
        "start_at_utc": value.start_at_utc,
        "end_at_utc": value.end_at_utc,
    }
    digest = contract_fingerprint(identity_input).removeprefix("sha256:")
    lock_id = f"freeze-lock-{digest}"
    return {
        "freeze_derived_lock_version": FREEZE_DERIVED_LOCK_VERSION,
        "lock_id": lock_id,
        "lock_type": "HARD_LOCK",
        "operation_id": value.operation_id,
        "resource_id": value.resource_id,
        "start_at_utc": value.start_at_utc,
        "end_at_utc": value.end_at_utc,
        "source": {
            "source_system": "plantnexus-freeze-projector",
            "source_version": EFFECTIVE_LOCK_PROJECTION_VERSION,
            "source_record_id": resolved.freeze_policy_id,
        },
        "base_schedule_version_id": base_schedule["schedule_version_id"],
        "base_content_fingerprint": base_schedule["content_fingerprint"],
        "problem_hash": problem["problem_hash"],
        "freeze_policy_fingerprint": resolved.freeze_policy_fingerprint,
    }


def _lock_document(lock: Mapping[str, object], *, kind: str, priority: int) -> dict[str, object]:
    return {
        "protection_kind": kind,
        "protection_priority": priority,
        "reference_id": lock["lock_id"],
        "operation_id": lock["operation_id"],
        "resource_id": lock["resource_id"],
        "start_at_utc": lock["start_at_utc"],
        "end_at_utc": lock["end_at_utc"],
        "source": {
            "source_system": lock["source_system"],
            "source_version": lock["source_version"],
            "source_record_id": lock["source_record_id"],
        },
    }


def project_effective_locks(
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
    base_schedule: Mapping[str, object],
    policy: Mapping[str, object],
) -> EffectiveLockProjection:
    """Project authoritative and freeze protections without mutating inputs."""

    try:
        verify_snapshot(snapshot)
    except ValueError as error:
        raise FreezeProjectionError(
            FreezeProjectionFailure.INVALID_SNAPSHOT,
            field=getattr(error, "field", "snapshot"),
            entity_id=snapshot.snapshot_id,
            message="new Snapshot failed immutable verification",
        ) from error
    try:
        verify_problem_v2(problem)
    except ValueError as error:
        raise FreezeProjectionError(
            FreezeProjectionFailure.INVALID_PROBLEM,
            field=getattr(error, "field", "problem"),
            entity_id=problem.snapshot_id,
            message="new PlanningProblem v2 failed immutable verification",
        ) from error
    _require_base_schedule(base_schedule)
    try:
        resolved = resolve_simulation_freeze_policy(policy, snapshot)
    except ValueError as error:
        raise FreezeProjectionError(
            FreezeProjectionFailure.POLICY_REJECTED,
            field=getattr(error, "field", "policy"),
            entity_id=str(policy.get("policy_id", "<policy>")),
            message="freeze policy could not be resolved",
        ) from error

    snapshot_document = snapshot.document
    problem_document = cast(Mapping[str, object], problem.document)
    if snapshot.data_plane is not SnapshotDataPlane.SIMULATION:
        _reject(
            FreezeProjectionFailure.PLANE_MISMATCH,
            field="snapshot.data_plane",
            entity_id=snapshot.snapshot_id,
            message="effective lock projection is Simulation-only",
        )
    cutoff_text = cast(str, snapshot_document["cutoff_at_utc"])
    if (
        problem_document.get("snapshot_id") != snapshot.snapshot_id
        or problem_document.get("horizon_start_utc") != cutoff_text
    ):
        _reject(
            FreezeProjectionFailure.LINEAGE_MISMATCH,
            field="problem.snapshot_id/horizon_start_utc",
            entity_id=problem.problem_hash,
            message="new Problem is not the exact solver-neutral projection of this Snapshot cutoff",
        )

    cutoff = _utc_second(cutoff_text, "snapshot.cutoff_at_utc", snapshot.snapshot_id)
    freeze_end = _utc_second(
        resolved.effective_until_utc, "freeze.effective_until_utc", resolved.freeze_policy_id
    )
    horizon_end = _utc_second(
        problem_document["horizon_end_utc"], "problem.horizon_end_utc", problem.problem_hash
    )
    tick_seconds = cast(int, problem_document["tick_seconds"])
    assignments = _assignment_index(base_schedule)
    operations = {
        cast(str, operation["operation_id"]): operation
        for operation in cast(Sequence[Mapping[str, object]], problem_document["operation_instances"])
    }
    historical_anchors = {
        cast(str, anchor["operation_id"]): anchor
        for anchor in cast(
            Sequence[Mapping[str, object]],
            problem_document["historical_completion_anchors"],
        )
    }
    snapshot_instances, execution_facts = _execution_fact_indexes(snapshot_document)
    expected_active_ids = {
        operation_id
        for operation_id, instance in snapshot_instances.items()
        if instance["status"] != "COMPLETED"
    }
    if set(operations) != expected_active_ids:
        _reject(
            FreezeProjectionFailure.LINEAGE_MISMATCH,
            field="problem.operation_instances",
            entity_id=problem.problem_hash,
            message="new Problem active operation universe differs from the exact Snapshot facts",
        )
    _require_problem_snapshot_projection(
        snapshot_document=snapshot_document,
        problem_document=problem_document,
        snapshot_instances=snapshot_instances,
        operations=operations,
        horizon_start=cutoff,
    )

    completed: dict[str, Mapping[str, object]] = {}
    completed_protections: list[dict[str, object]] = []
    for operation_id, instance in sorted(snapshot_instances.items()):
        if instance["status"] != "COMPLETED":
            continue
        execution_fact_id = instance.get("execution_fact_id")
        if not isinstance(execution_fact_id, str):
            _reject(
                FreezeProjectionFailure.LINEAGE_MISMATCH,
                field="snapshot.operation_instances.execution_fact_id",
                entity_id=operation_id,
                message="COMPLETED operation lacks an authoritative execution fact",
            )
        fact = execution_facts.get(execution_fact_id)
        if fact is None or fact.get("status") != "COMPLETED":
            _reject(
                FreezeProjectionFailure.LINEAGE_MISMATCH,
                field="snapshot.records.execution_facts",
                entity_id=operation_id,
                message="COMPLETED operation fact reference is missing or non-terminal",
            )
        completed[operation_id] = fact
        completed_protections.append(
            _protection_document(
                _Tuple(
                    operation_id=operation_id,
                    resource_id=cast(str, fact["resource_id"]),
                    start_at_utc=cast(str, fact["actual_start_at_utc"]),
                    end_at_utc=cast(str, fact["actual_end_at_utc"]),
                ),
                kind="COMPLETED_EXECUTION_FACT",
                priority=1,
                reference_id=execution_fact_id,
                fact_evidence=_fact_evidence(fact),
            )
        )
    required_anchor_ids = {
        cast(str, edge["predecessor_operation_instance_id"])
        for edge in cast(
            Sequence[Mapping[str, object]],
            snapshot_document["operation_precedence_edges"],
        )
        if cast(str, edge["predecessor_operation_instance_id"]) in completed
        and cast(str, edge["successor_operation_instance_id"]) in operations
    }
    if set(historical_anchors) != required_anchor_ids:
        _reject(
            FreezeProjectionFailure.LINEAGE_MISMATCH,
            field="problem.historical_completion_anchors",
            entity_id=problem.problem_hash,
            message="historical anchor universe differs from the exact Snapshot projection",
        )
    for operation_id in sorted(required_anchor_ids):
        anchor = historical_anchors[operation_id]
        expected_anchor = _historical_anchor(operation_id, completed[operation_id])
        if dict(anchor) != expected_anchor:
            _reject(
                FreezeProjectionFailure.LINEAGE_MISMATCH,
                field="problem.historical_completion_anchors",
                entity_id=operation_id,
                message="historical completion anchor bytes differ from Snapshot authority",
            )

    running: list[dict[str, object]] = []
    for operation_id, operation in sorted(operations.items()):
        if operation["status"] != "RUNNING":
            continue
        instance = snapshot_instances[operation_id]
        execution_fact_id = instance.get("execution_fact_id")
        fact = (
            execution_facts.get(execution_fact_id)
            if isinstance(execution_fact_id, str)
            else None
        )
        if (
            instance.get("status") != "RUNNING"
            or fact is None
            or fact.get("status") != "RUNNING"
            or fact.get("resource_id") != operation.get("assigned_resource_id")
            or fact.get("remaining_seconds") != operation.get("remaining_seconds")
        ):
            _reject(
                FreezeProjectionFailure.LINEAGE_MISMATCH,
                field="snapshot.records.execution_facts",
                entity_id=operation_id,
                message="RUNNING Problem tuple lacks exact Snapshot execution authority",
            )
        remaining = cast(int, operation["remaining_seconds"])
        end = cutoff + timedelta(seconds=ceil(remaining / tick_seconds) * tick_seconds)
        value = _Tuple(
            operation_id=operation_id,
            resource_id=cast(str, operation["assigned_resource_id"]),
            start_at_utc=cutoff_text,
            end_at_utc=_format_utc(end),
        )
        _require_grid_tuple(
            value,
            operation=operation,
            cutoff=cutoff,
            horizon_end=horizon_end,
            tick_seconds=tick_seconds,
            failure=FreezeProjectionFailure.FACT_LOCK_CONFLICT,
        )
        running.append(
            _protection_document(
                value,
                kind="RUNNING_EXECUTION_FACT",
                priority=1,
                reference_id=cast(str, execution_fact_id),
                fact_evidence=_fact_evidence(fact),
            )
        )

    explicit_hard: list[dict[str, object]] = []
    soft_locks: list[dict[str, object]] = []
    hard_by_operation: dict[str, _Tuple] = {}
    for lock in cast(Sequence[Mapping[str, object]], problem_document["operation_locks"]):
        operation_id = cast(str, lock["operation_id"])
        operation = operations[operation_id]
        value = _tuple_from_lock(lock)
        if lock["lock_type"] == "SOFT_LOCK":
            soft_locks.append(_lock_document(lock, kind="SOFT_LOCK", priority=4))
            continue
        _require_grid_tuple(
            value,
            operation=operation,
            cutoff=cutoff,
            horizon_end=horizon_end,
            tick_seconds=tick_seconds,
            failure=FreezeProjectionFailure.HARD_LOCK_CONFLICT,
        )
        previous = hard_by_operation.get(operation_id)
        if previous is not None and previous.values() != value.values():
            _reject(
                FreezeProjectionFailure.HARD_LOCK_CONFLICT,
                field="problem.operation_locks",
                entity_id=operation_id,
                message="multiple explicit HARD locks disagree",
            )
        hard_by_operation[operation_id] = value
        explicit_hard.append(_lock_document(lock, kind="EXPLICIT_HARD_LOCK", priority=2))

    running_by_operation = {
        cast(str, item["operation_id"]): (
            cast(str, item["resource_id"]),
            cast(str, item["start_at_utc"]),
            cast(str, item["end_at_utc"]),
        )
        for item in running
    }
    for operation_id, value in hard_by_operation.items():
        running_value = running_by_operation.get(operation_id)
        if running_value is not None and value.values() != running_value:
            _reject(
                FreezeProjectionFailure.FACT_LOCK_CONFLICT,
                field="problem.operation_locks",
                entity_id=operation_id,
                message="explicit HARD lock conflicts with authoritative RUNNING tuple",
            )

    derived: list[dict[str, object]] = []
    outside_freeze: list[str] = []
    for operation_id, assignment in sorted(assignments.items()):
        if operation_id in completed or (
            operation_id in operations and operations[operation_id]["status"] == "RUNNING"
        ):
            continue
        operation = operations.get(operation_id)
        if operation is None:
            _reject(
                FreezeProjectionFailure.STALE_BASE,
                field="base_schedule.content.assignments",
                entity_id=operation_id,
                message="missing active operation has no authoritative COMPLETED fact",
            )
        start = _utc_second(assignment["start_at_utc"], "assignment.start_at_utc", operation_id)
        if start < cutoff:
            _reject(
                FreezeProjectionFailure.STALE_BASE,
                field="assignment.start_at_utc",
                entity_id=operation_id,
                message="pre-cutoff NOT_STARTED assignment lacks RUNNING/COMPLETED authority",
            )
        if start >= freeze_end:
            outside_freeze.append(operation_id)
            continue
        value = _tuple_from_assignment(assignment)
        _require_grid_tuple(
            value,
            operation=operation,
            cutoff=cutoff,
            horizon_end=horizon_end,
            tick_seconds=tick_seconds,
            failure=FreezeProjectionFailure.FREEZE_LOCK_CONFLICT,
        )
        explicit_value = hard_by_operation.get(operation_id)
        if explicit_value is not None and explicit_value.values() != value.values():
            _reject(
                FreezeProjectionFailure.FREEZE_LOCK_CONFLICT,
                field="freeze_derived_hard_locks",
                entity_id=operation_id,
                message="freeze-derived tuple conflicts with explicit HARD lock",
            )
        derived.append(
            _derived_lock(
                value,
                base_schedule=base_schedule,
                problem=problem_document,
                resolved=resolved,
            )
        )

    derived.sort(key=lambda item: cast(str, item["lock_id"]))
    explicit_hard.sort(key=lambda item: cast(str, item["reference_id"]))
    soft_locks.sort(key=lambda item: cast(str, item["reference_id"]))
    running.sort(key=lambda item: cast(str, item["operation_id"]))
    completed_protections.sort(key=lambda item: cast(str, item["operation_id"]))
    derived_ids = tuple(cast(str, item["lock_id"]) for item in derived)
    active_ids = tuple(sorted(operations))
    base_ids = tuple(sorted(assignments))
    completed_ids = tuple(sorted(completed))
    added_ids = tuple(sorted(set(active_ids) - set(base_ids)))

    problem_digest = problem.problem_hash.removeprefix("sha256:")
    projection: dict[str, object] = {
        "effective_lock_projection_version": EFFECTIVE_LOCK_PROJECTION_VERSION,
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "base_schedule_version": {
            "schedule_version_version": base_schedule["schedule_version_version"],
            "schedule_version_id": base_schedule["schedule_version_id"],
            "state": "PUBLISHED",
            "content_fingerprint": base_schedule["content_fingerprint"],
        },
        "new_snapshot": {
            "document_version": "planning-snapshot.v2",
            "artifact_id": snapshot.snapshot_id,
            "fingerprint": snapshot.snapshot_hash,
        },
        "new_problem": {
            "document_version": "planning-problem.v2",
            "artifact_id": f"planning-problem-v2-{problem_digest}",
            "fingerprint": problem.problem_hash,
        },
        "planning_policy": resolved.policy_reference(),
        "freeze_resolution": resolved.document(effective_lock_ids=derived_ids),
        "base_assignment_operation_ids": list(base_ids),
        "new_active_operation_ids": list(active_ids),
        "completed_operation_ids": list(completed_ids),
        "completed_protections": completed_protections,
        "added_operation_ids": list(added_ids),
        "outside_freeze_operation_ids": sorted(outside_freeze),
        "running_protections": running,
        "explicit_hard_locks": explicit_hard,
        "freeze_derived_hard_locks": derived,
        "soft_locks": soft_locks,
    }
    fingerprint = contract_fingerprint(projection)
    projection["projection_fingerprint"] = fingerprint
    canonical_bytes = canonical_contract_bytes(projection)
    return EffectiveLockProjection(
        canonical_bytes=canonical_bytes,
        projection_fingerprint=fingerprint,
    )


__all__ = [
    "EFFECTIVE_LOCK_PROJECTION_VERSION",
    "FREEZE_DERIVED_LOCK_VERSION",
    "EffectiveLockProjection",
    "FreezeProjectionError",
    "FreezeProjectionFailure",
    "project_effective_locks",
]
