"""Independent precheck for P4 freeze/effective-lock projection.

This evaluator intentionally does not import the projector.  It recomputes the
half-open boundary, authoritative RUNNING tuples, explicit HARD tuples, and
freeze-derived locks from immutable inputs.  It does not call CP-SAT or reuse
the formal ScheduleValidator's C-001..C-011 implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from math import ceil
from typing import cast

from app.domain.execution_contracts import (
    contract_fingerprint,
    freeze_policy_fingerprint,
    require_p4_document,
)
from app.domain.workspace_contracts import require_workspace_document
from app.planning.policy.freeze_window import simulation_replan_policy
from app.planning.problem.contracts import ImmutablePlanningProblemV2
from app.planning.problem.hashing import verify_problem_v2
from app.snapshots.canonical import verify_snapshot
from app.snapshots.contracts import ImmutablePlanningSnapshot, SnapshotDataPlane


PRECHECK_VERSION = "freeze-window-precheck.v1"
PROJECTION_VERSION = "effective-lock-projection.v1"
DERIVED_LOCK_VERSION = "freeze-derived-lock.v1"
INTERVAL_SEMANTICS = "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE"
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
_ROOT_FIELDS = {
    "effective_lock_projection_version",
    "canonicalization_version",
    "data_plane",
    "base_schedule_version",
    "new_snapshot",
    "new_problem",
    "planning_policy",
    "freeze_resolution",
    "base_assignment_operation_ids",
    "new_active_operation_ids",
    "completed_operation_ids",
    "completed_protections",
    "added_operation_ids",
    "outside_freeze_operation_ids",
    "running_protections",
    "explicit_hard_locks",
    "freeze_derived_hard_locks",
    "soft_locks",
    "projection_fingerprint",
}


class FreezePrecheckInputError(ValueError):
    """Authoritative inputs are invalid, stale, conflicting, or cross-plane."""

    def __init__(self, reason: str, *, field: str, entity_id: str) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        super().__init__(f"{reason} at {field} ({entity_id})")


def _input_error(reason: str, field: str, entity_id: str) -> FreezePrecheckInputError:
    return FreezePrecheckInputError(reason, field=field, entity_id=entity_id)


def _utc(value: object, field: str, entity_id: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise _input_error("INVALID_UTC", field, entity_id)
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _input_error("INVALID_UTC", field, entity_id) from error
    if instant.microsecond:
        raise _input_error("INVALID_UTC_PRECISION", field, entity_id)
    return instant


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _as_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _input_error("INVALID_SHAPE", field, "<input>")
    return cast(Mapping[str, object], value)


def _as_list(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise _input_error("INVALID_SHAPE", field, "<input>")
    return value


def _base_assignments(base: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    version = base.get("schedule_version_version")
    try:
        if version == "schedule-version.v1":
            require_workspace_document(base)
        elif version == "schedule-version.v2":
            require_p4_document(base)
        else:
            raise _input_error("UNSUPPORTED_BASE_VERSION", "base.schedule_version_version", "<base>")
    except FreezePrecheckInputError:
        raise
    except ValueError as error:
        raise _input_error(
            "INVALID_BASE_SCHEDULE",
            getattr(error, "field", "base_schedule"),
            str(base.get("schedule_version_id", "<base>")),
        ) from error
    schedule_id = str(base.get("schedule_version_id", "<base>"))
    if base.get("state") != "PUBLISHED":
        raise _input_error("BASE_NOT_PUBLISHED", "base.state", schedule_id)
    if (
        base.get("data_plane") != "SIMULATION"
        or base.get("synthetic") is not True
        or base.get("environment") not in {"DEVELOPMENT", "TEST", "BENCHMARK"}
    ):
        raise _input_error("PLANE_MISMATCH", "base.data_plane", schedule_id)
    content = _as_mapping(base.get("content"), "base.content")
    values: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(_as_list(content.get("assignments"), "base.content.assignments")):
        assignment = _as_mapping(raw, f"base.content.assignments[{index}]")
        operation_id = assignment.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise _input_error("INVALID_ASSIGNMENT", "assignment.operation_id", schedule_id)
        if set(assignment) != _ASSIGNMENT_FIELDS:
            raise _input_error(
                "INVALID_ASSIGNMENT",
                f"base.content.assignments[{index}]",
                operation_id,
            )
        if operation_id in values:
            raise _input_error("DUPLICATE_OPERATION", "base.content.assignments", operation_id)
        start = _utc(assignment.get("start_at_utc"), "assignment.start_at_utc", operation_id)
        end = _utc(assignment.get("end_at_utc"), "assignment.end_at_utc", operation_id)
        duration = assignment.get("duration_seconds")
        start_tick = assignment.get("start_tick")
        end_tick = assignment.get("end_tick")
        duration_ticks = assignment.get("duration_ticks")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or duration < 1
            or isinstance(start_tick, bool)
            or not isinstance(start_tick, int)
            or start_tick < 0
            or isinstance(end_tick, bool)
            or not isinstance(end_tick, int)
            or end_tick < 1
            or isinstance(duration_ticks, bool)
            or not isinstance(duration_ticks, int)
            or duration_ticks < 1
            or end <= start
            or int((end - start).total_seconds()) != duration
            or end_tick - start_tick != duration_ticks
        ):
            raise _input_error("INVALID_ASSIGNMENT", "assignment.duration_seconds", operation_id)
        values[operation_id] = assignment
    return values


def _protection(
    *,
    kind: str,
    priority: int,
    reference_id: str,
    operation_id: str,
    resource_id: str,
    start_at_utc: str,
    end_at_utc: str,
    source: Mapping[str, object] | None = None,
    fact_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "protection_kind": kind,
        "protection_priority": priority,
        "reference_id": reference_id,
        "operation_id": operation_id,
        "resource_id": resource_id,
        "start_at_utc": start_at_utc,
        "end_at_utc": end_at_utc,
    }
    if source is not None:
        value["source"] = dict(source)
    if fact_evidence is not None:
        value["fact_evidence"] = dict(fact_evidence)
    return value


def _fact_evidence(fact: Mapping[str, object]) -> dict[str, object]:
    source = _as_mapping(fact.get("source"), "execution_fact.source")
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
    source = _as_mapping(fact.get("source"), "execution_fact.source")
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


def _snapshot_options(instance: Mapping[str, object]) -> list[dict[str, object]]:
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


def _require_snapshot_problem_equivalence(
    *,
    snapshot_document: Mapping[str, object],
    problem_document: Mapping[str, object],
    snapshot_instances: Mapping[str, Mapping[str, object]],
    operations: Mapping[str, Mapping[str, object]],
    cutoff: datetime,
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
            raise _input_error(
                "LINEAGE_MISMATCH", "problem.operation_instances", operation_id
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
        if observed_options != _snapshot_options(instance):
            raise _input_error(
                "LINEAGE_MISMATCH",
                "problem.operation_instances.resource_options",
                operation_id,
            )

    records = _as_mapping(snapshot_document.get("records"), "snapshot.records")
    locks_by_id = {
        cast(str, lock["lock_id"]): lock
        for lock in cast(
            Sequence[Mapping[str, object]],
            _as_list(records.get("operation_locks"), "snapshot.records.operation_locks"),
        )
    }
    expected_locks: list[dict[str, object]] = []
    for operation_id in sorted(operations):
        instance = snapshot_instances[operation_id]
        for lock_id in cast(Sequence[str], instance["lock_ids"]):
            lock = locks_by_id[lock_id]
            if _utc(lock["end_at_utc"], "lock.end_at_utc", lock_id) <= cutoff:
                continue
            source = _as_mapping(lock.get("source"), "lock.source")
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
        raise _input_error(
            "LINEAGE_MISMATCH",
            "problem.operation_locks",
            cast(str, problem_document["problem_hash"]),
        )


def _tuple(value: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        cast(str, value["resource_id"]),
        cast(str, value["start_at_utc"]),
        cast(str, value["end_at_utc"]),
    )


def _operation_durations(operation: Mapping[str, object]) -> dict[str, int]:
    return {
        cast(str, option["resource_id"]): cast(int, option["final_duration_seconds"])
        for option in cast(Sequence[Mapping[str, object]], operation["resource_options"])
    }


def _require_protected_tuple(
    value: Mapping[str, object],
    operation: Mapping[str, object],
    *,
    cutoff: datetime,
    horizon_end: datetime,
    tick_seconds: int,
    reason: str,
) -> None:
    operation_id = cast(str, value["operation_id"])
    start = _utc(value.get("start_at_utc"), "protected.start_at_utc", operation_id)
    end = _utc(value.get("end_at_utc"), "protected.end_at_utc", operation_id)
    if start < cutoff or end > horizon_end or end <= start:
        raise _input_error(reason, "protected.interval", operation_id)
    start_seconds = int((start - cutoff).total_seconds())
    end_seconds = int((end - cutoff).total_seconds())
    if start_seconds % tick_seconds or end_seconds % tick_seconds:
        raise _input_error("UNREPRESENTABLE_LOCK", "protected.interval", operation_id)
    durations = _operation_durations(operation)
    resource_id = cast(str, value["resource_id"])
    duration = (
        cast(int, operation["remaining_seconds"])
        if operation["status"] == "RUNNING"
        else durations.get(resource_id)
    )
    if resource_id not in durations or duration is None:
        raise _input_error(reason, "protected.resource_id", operation_id)
    expected = ceil(duration / tick_seconds) * tick_seconds
    if end_seconds - start_seconds != expected:
        raise _input_error(reason, "protected.interval", operation_id)


def _derived_lock(
    assignment: Mapping[str, object],
    *,
    base: Mapping[str, object],
    problem: Mapping[str, object],
    freeze_fingerprint: str,
    freeze_policy_id: str,
) -> dict[str, object]:
    identity_input = {
        "freeze_derived_lock_version": DERIVED_LOCK_VERSION,
        "base_schedule_version": {
            "schedule_version_version": base["schedule_version_version"],
            "schedule_version_id": base["schedule_version_id"],
            "content_fingerprint": base["content_fingerprint"],
        },
        "problem_hash": problem["problem_hash"],
        "freeze_policy_fingerprint": freeze_fingerprint,
        "operation_id": assignment["operation_id"],
        "resource_id": assignment["resource_id"],
        "start_at_utc": assignment["start_at_utc"],
        "end_at_utc": assignment["end_at_utc"],
    }
    digest = contract_fingerprint(identity_input).removeprefix("sha256:")
    return {
        "freeze_derived_lock_version": DERIVED_LOCK_VERSION,
        "lock_id": f"freeze-lock-{digest}",
        "lock_type": "HARD_LOCK",
        "operation_id": assignment["operation_id"],
        "resource_id": assignment["resource_id"],
        "start_at_utc": assignment["start_at_utc"],
        "end_at_utc": assignment["end_at_utc"],
        "source": {
            "source_system": "plantnexus-freeze-projector",
            "source_version": PROJECTION_VERSION,
            "source_record_id": freeze_policy_id,
        },
        "base_schedule_version_id": base["schedule_version_id"],
        "base_content_fingerprint": base["content_fingerprint"],
        "problem_hash": problem["problem_hash"],
        "freeze_policy_fingerprint": freeze_fingerprint,
    }


def _expected_projection(
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
    base: Mapping[str, object],
    policy: Mapping[str, object],
) -> dict[str, object]:
    try:
        verify_snapshot(snapshot)
        verify_problem_v2(problem)
        require_p4_document(policy)
    except ValueError as error:
        raise _input_error(
            "INVALID_AUTHORITATIVE_INPUT",
            getattr(error, "field", "input"),
            snapshot.snapshot_id,
        ) from error
    if snapshot.data_plane is not SnapshotDataPlane.SIMULATION:
        raise _input_error("PLANE_MISMATCH", "snapshot.data_plane", snapshot.snapshot_id)
    if dict(policy) != simulation_replan_policy():
        raise _input_error("UNAPPROVED_SIMULATION_POLICY", "policy", str(policy.get("policy_id")))

    snapshot_document = snapshot.document
    problem_document = cast(Mapping[str, object], problem.document)
    cutoff_text = cast(str, snapshot_document["cutoff_at_utc"])
    if (
        problem_document.get("snapshot_id") != snapshot.snapshot_id
        or problem_document.get("horizon_start_utc") != cutoff_text
    ):
        raise _input_error("LINEAGE_MISMATCH", "problem.snapshot_id", problem.problem_hash)
    assignments = _base_assignments(base)
    operations = {
        cast(str, item["operation_id"]): item
        for item in cast(Sequence[Mapping[str, object]], problem_document["operation_instances"])
    }
    anchors = {
        cast(str, item["operation_id"]): item
        for item in cast(
            Sequence[Mapping[str, object]],
            problem_document["historical_completion_anchors"],
        )
    }
    cutoff = _utc(cutoff_text, "snapshot.cutoff_at_utc", snapshot.snapshot_id)
    horizon_end = _utc(problem_document["horizon_end_utc"], "problem.horizon_end_utc", problem.problem_hash)
    tick_seconds = cast(int, problem_document["tick_seconds"])
    freeze = cast(Mapping[str, object], policy["freeze_policy"])
    window = freeze.get("window_seconds")
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise _input_error("INVALID_FREEZE_POLICY", "freeze.window_seconds", str(policy.get("policy_id")))
    freeze_end = cutoff + timedelta(seconds=window)
    freeze_fingerprint = freeze_policy_fingerprint(freeze)

    snapshot_instances = {
        cast(str, item["operation_instance_id"]): item
        for item in cast(
            Sequence[Mapping[str, object]], snapshot_document["operation_instances"]
        )
    }
    expected_active_ids = {
        operation_id
        for operation_id, instance in snapshot_instances.items()
        if instance["status"] != "COMPLETED"
    }
    if set(operations) != expected_active_ids:
        raise _input_error(
            "LINEAGE_MISMATCH", "problem.operation_instances", problem.problem_hash
        )
    _require_snapshot_problem_equivalence(
        snapshot_document=snapshot_document,
        problem_document=problem_document,
        snapshot_instances=snapshot_instances,
        operations=operations,
        cutoff=cutoff,
    )
    records = _as_mapping(snapshot_document.get("records"), "snapshot.records")
    execution_facts = {
        cast(str, item["execution_fact_id"]): item
        for item in cast(
            Sequence[Mapping[str, object]],
            _as_list(records.get("execution_facts"), "snapshot.records.execution_facts"),
        )
    }
    completed: dict[str, Mapping[str, object]] = {}
    completed_protections: list[dict[str, object]] = []
    for operation_id, instance in sorted(snapshot_instances.items()):
        if instance["status"] != "COMPLETED":
            continue
        fact_id = instance.get("execution_fact_id")
        fact = execution_facts.get(fact_id) if isinstance(fact_id, str) else None
        if fact is None or fact.get("status") != "COMPLETED":
            raise _input_error(
                "MISSING_COMPLETED_AUTHORITY",
                "snapshot.records.execution_facts",
                operation_id,
            )
        completed[operation_id] = fact
        completed_protections.append(
            _protection(
                kind="COMPLETED_EXECUTION_FACT",
                priority=1,
                reference_id=cast(str, fact_id),
                operation_id=operation_id,
                resource_id=cast(str, fact["resource_id"]),
                start_at_utc=cast(str, fact["actual_start_at_utc"]),
                end_at_utc=cast(str, fact["actual_end_at_utc"]),
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
    if set(anchors) != required_anchor_ids:
        raise _input_error(
            "LINEAGE_MISMATCH",
            "problem.historical_completion_anchors",
            problem.problem_hash,
        )
    for operation_id in sorted(required_anchor_ids):
        if dict(anchors[operation_id]) != _historical_anchor(
            operation_id, completed[operation_id]
        ):
            raise _input_error(
                "LINEAGE_MISMATCH",
                "problem.historical_completion_anchors",
                operation_id,
            )

    running: list[dict[str, object]] = []
    for operation_id, operation in sorted(operations.items()):
        if operation["status"] != "RUNNING":
            continue
        instance = snapshot_instances[operation_id]
        fact_id = instance.get("execution_fact_id")
        fact = execution_facts.get(fact_id) if isinstance(fact_id, str) else None
        if (
            instance.get("status") != "RUNNING"
            or fact is None
            or fact.get("status") != "RUNNING"
            or fact.get("resource_id") != operation.get("assigned_resource_id")
            or fact.get("remaining_seconds") != operation.get("remaining_seconds")
        ):
            raise _input_error(
                "MISSING_RUNNING_AUTHORITY",
                "snapshot.records.execution_facts",
                operation_id,
            )
        end = cutoff + timedelta(
            seconds=ceil(cast(int, operation["remaining_seconds"]) / tick_seconds)
            * tick_seconds
        )
        candidate = {
            "operation_id": operation_id,
            "resource_id": operation["assigned_resource_id"],
            "start_at_utc": cutoff_text,
            "end_at_utc": _format_utc(end),
        }
        _require_protected_tuple(
            candidate,
            operation,
            cutoff=cutoff,
            horizon_end=horizon_end,
            tick_seconds=tick_seconds,
            reason="RUNNING_FACT_CONFLICT",
        )
        running.append(
            _protection(
                kind="RUNNING_EXECUTION_FACT",
                priority=1,
                reference_id=cast(str, fact_id),
                operation_id=operation_id,
                resource_id=cast(str, candidate["resource_id"]),
                start_at_utc=cutoff_text,
                end_at_utc=cast(str, candidate["end_at_utc"]),
                fact_evidence=_fact_evidence(fact),
            )
        )

    hard: list[dict[str, object]] = []
    soft: list[dict[str, object]] = []
    hard_tuples: dict[str, tuple[str, str, str]] = {}
    for lock in cast(Sequence[Mapping[str, object]], problem_document["operation_locks"]):
        operation_id = cast(str, lock["operation_id"])
        source = {
            "source_system": lock["source_system"],
            "source_version": lock["source_version"],
            "source_record_id": lock["source_record_id"],
        }
        projected = _protection(
            kind="EXPLICIT_HARD_LOCK" if lock["lock_type"] == "HARD_LOCK" else "SOFT_LOCK",
            priority=2 if lock["lock_type"] == "HARD_LOCK" else 4,
            reference_id=cast(str, lock["lock_id"]),
            operation_id=operation_id,
            resource_id=cast(str, lock["resource_id"]),
            start_at_utc=cast(str, lock["start_at_utc"]),
            end_at_utc=cast(str, lock["end_at_utc"]),
            source=source,
        )
        if lock["lock_type"] == "SOFT_LOCK":
            soft.append(projected)
            continue
        _require_protected_tuple(
            projected,
            operations[operation_id],
            cutoff=cutoff,
            horizon_end=horizon_end,
            tick_seconds=tick_seconds,
            reason="HARD_LOCK_CONFLICT",
        )
        observed = _tuple(projected)
        previous = hard_tuples.get(operation_id)
        if previous is not None and previous != observed:
            raise _input_error("HARD_LOCK_CONFLICT", "problem.operation_locks", operation_id)
        hard_tuples[operation_id] = observed
        hard.append(projected)

    running_tuples = {cast(str, item["operation_id"]): _tuple(item) for item in running}
    for operation_id, observed in hard_tuples.items():
        if operation_id in running_tuples and observed != running_tuples[operation_id]:
            raise _input_error("FACT_LOCK_CONFLICT", "problem.operation_locks", operation_id)

    derived: list[dict[str, object]] = []
    outside: list[str] = []
    for operation_id, assignment in sorted(assignments.items()):
        if operation_id in completed or (
            operation_id in operations and operations[operation_id]["status"] == "RUNNING"
        ):
            continue
        operation = operations.get(operation_id)
        if operation is None:
            raise _input_error("STALE_BASE", "base.content.assignments", operation_id)
        start = _utc(assignment["start_at_utc"], "assignment.start_at_utc", operation_id)
        if start < cutoff:
            raise _input_error("STALE_BASE", "assignment.start_at_utc", operation_id)
        if start >= freeze_end:
            outside.append(operation_id)
            continue
        _require_protected_tuple(
            assignment,
            operation,
            cutoff=cutoff,
            horizon_end=horizon_end,
            tick_seconds=tick_seconds,
            reason="FREEZE_LOCK_CONFLICT",
        )
        observed = _tuple(assignment)
        if operation_id in hard_tuples and observed != hard_tuples[operation_id]:
            raise _input_error("FREEZE_LOCK_CONFLICT", "freeze_derived_hard_locks", operation_id)
        derived.append(
            _derived_lock(
                assignment,
                base=base,
                problem=problem_document,
                freeze_fingerprint=freeze_fingerprint,
                freeze_policy_id=cast(str, freeze["freeze_policy_id"]),
            )
        )

    running.sort(key=lambda item: cast(str, item["operation_id"]))
    completed_protections.sort(key=lambda item: cast(str, item["operation_id"]))
    hard.sort(key=lambda item: cast(str, item["reference_id"]))
    soft.sort(key=lambda item: cast(str, item["reference_id"]))
    derived.sort(key=lambda item: cast(str, item["lock_id"]))
    derived_ids = [cast(str, item["lock_id"]) for item in derived]
    active_ids = sorted(operations)
    base_ids = sorted(assignments)
    problem_digest = problem.problem_hash.removeprefix("sha256:")
    source = cast(Mapping[str, object], freeze["source"])
    expected: dict[str, object] = {
        "effective_lock_projection_version": PROJECTION_VERSION,
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "base_schedule_version": {
            "schedule_version_version": base["schedule_version_version"],
            "schedule_version_id": base["schedule_version_id"],
            "state": "PUBLISHED",
            "content_fingerprint": base["content_fingerprint"],
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
        "planning_policy": {
            "planning_policy_version": "planning-policy.v2",
            "policy_id": policy["policy_id"],
            "policy_revision": policy["policy_revision"],
            "policy_fingerprint": contract_fingerprint(policy),
        },
        "freeze_resolution": {
            "freeze_policy_version": "freeze-policy.v1",
            "freeze_policy_id": freeze["freeze_policy_id"],
            "freeze_policy_revision": freeze["freeze_policy_revision"],
            "freeze_policy_fingerprint": freeze_fingerprint,
            "source": dict(source),
            "window_seconds": window,
            "effective_from_utc": cutoff_text,
            "effective_until_utc": _format_utc(freeze_end),
            "interval_semantics": INTERVAL_SEMANTICS,
            "effective_lock_ids": derived_ids,
        },
        "base_assignment_operation_ids": base_ids,
        "new_active_operation_ids": active_ids,
        "completed_operation_ids": sorted(completed),
        "completed_protections": completed_protections,
        "added_operation_ids": sorted(set(active_ids) - set(base_ids)),
        "outside_freeze_operation_ids": sorted(outside),
        "running_protections": running,
        "explicit_hard_locks": hard,
        "freeze_derived_hard_locks": derived,
        "soft_locks": soft,
    }
    expected["projection_fingerprint"] = contract_fingerprint(expected)
    return expected


def _violation(check_id: str, field: str, observed: object, expected: object) -> dict[str, object]:
    return {
        "check_id": check_id,
        "field": field,
        "observed_fingerprint": contract_fingerprint({"value": observed}),
        "expected_fingerprint": contract_fingerprint({"value": expected}),
        "message": "effective-lock projection differs from independent recomputation",
    }


def validate_freeze_window_projection(
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
    base_schedule: Mapping[str, object],
    policy: Mapping[str, object],
    projection: Mapping[str, object],
) -> dict[str, object]:
    """Return a deterministic PASS/FAIL precheck report for one projection."""

    expected = _expected_projection(
        snapshot=snapshot,
        problem=problem,
        base=base_schedule,
        policy=policy,
    )
    violations: list[dict[str, object]] = []
    if set(projection) != _ROOT_FIELDS:
        violations.append(
            _violation(
                "FREEZE-COMPLETENESS",
                "$",
                sorted(projection),
                sorted(_ROOT_FIELDS),
            )
        )
    checks = (
        ("FREEZE-LINEAGE", "base_schedule_version"),
        ("FREEZE-LINEAGE", "new_snapshot"),
        ("FREEZE-LINEAGE", "new_problem"),
        ("FREEZE-POLICY", "planning_policy"),
        ("FREEZE-POLICY", "freeze_resolution"),
        ("FREEZE-COMPLETENESS", "base_assignment_operation_ids"),
        ("FREEZE-COMPLETENESS", "new_active_operation_ids"),
        ("C-007", "completed_operation_ids"),
        ("C-007", "completed_protections"),
        ("FREEZE-COMPLETENESS", "added_operation_ids"),
        ("FREEZE-BOUNDARY", "outside_freeze_operation_ids"),
        ("C-007", "running_protections"),
        ("C-008", "explicit_hard_locks"),
        ("C-008", "freeze_derived_hard_locks"),
        ("FREEZE-SOFT-INPUT", "soft_locks"),
    )
    for check_id, field in checks:
        if projection.get(field) != expected[field]:
            violations.append(
                _violation(check_id, field, projection.get(field), expected[field])
            )
    header = {
        "effective_lock_projection_version": projection.get(
            "effective_lock_projection_version"
        ),
        "canonicalization_version": projection.get("canonicalization_version"),
        "data_plane": projection.get("data_plane"),
    }
    expected_header = {
        "effective_lock_projection_version": PROJECTION_VERSION,
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
    }
    if header != expected_header:
        violations.append(_violation("FREEZE-VERSION", "header", header, expected_header))
    projected_without_self = {
        key: value for key, value in projection.items() if key != "projection_fingerprint"
    }
    observed_fingerprint = projection.get("projection_fingerprint")
    recomputed_fingerprint = contract_fingerprint(projected_without_self)
    if observed_fingerprint != recomputed_fingerprint:
        violations.append(
            _violation(
                "FREEZE-IDENTITY",
                "projection_fingerprint",
                observed_fingerprint,
                recomputed_fingerprint,
            )
        )
    expected_fingerprint = expected["projection_fingerprint"]
    if observed_fingerprint != expected_fingerprint:
        violations.append(
            _violation(
                "FREEZE-IDENTITY",
                "projection_fingerprint.expected",
                observed_fingerprint,
                expected_fingerprint,
            )
        )
    violations.sort(key=lambda item: (cast(str, item["check_id"]), cast(str, item["field"])))
    report_without_id: dict[str, object] = {
        "freeze_window_precheck_version": PRECHECK_VERSION,
        "status": "PASS" if not violations else "FAIL",
        "hard_violation_count": len(violations),
        "violations": violations,
        "projection_fingerprint": projection.get("projection_fingerprint"),
        "expected_projection_fingerprint": expected_fingerprint,
        "independence": {
            "projector_imported": False,
            "cp_sat_imported": False,
            "formal_schedule_validator_modified": False,
        },
    }
    report_digest = contract_fingerprint(report_without_id).removeprefix("sha256:")
    return {
        "report_id": f"freeze-precheck-{report_digest}",
        **report_without_id,
    }


__all__ = [
    "FreezePrecheckInputError",
    "PRECHECK_VERSION",
    "validate_freeze_window_projection",
]
