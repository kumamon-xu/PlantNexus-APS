"""Pure integer OBJ-002 stability calculation for P4 replanning evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from app.domain.change_report import (
    ChangeReportFailure,
    reject_change_report,
)


STABILITY_OBJECTIVE_VERSION = "obj-002-stability.v1"
STABILITY_COMPONENTS = (
    "SOFT_LOCK_VIOLATIONS",
    "CHANGED_EXISTING_OPERATIONS",
    "RESOURCE_CHANGES",
    "ABSOLUTE_START_SHIFT_SECONDS",
)

_ASSIGNMENT_FIELDS = frozenset(
    {
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
)


@dataclass(frozen=True, slots=True)
class OperationDelta:
    """Exact integer delta between two comparable operation assignments."""

    resource_changed: bool
    start_shift_seconds: int
    absolute_start_shift_seconds: int
    end_shift_seconds: int
    duration_delta_seconds: int

    @property
    def changed(self) -> bool:
        return (
            self.resource_changed
            or self.start_shift_seconds != 0
            or self.end_shift_seconds != 0
        )

    @property
    def document(self) -> dict[str, object]:
        return {
            "resource_changed": self.resource_changed,
            "start_shift_seconds": self.start_shift_seconds,
            "absolute_start_shift_seconds": self.absolute_start_shift_seconds,
            "end_shift_seconds": self.end_shift_seconds,
            "duration_delta_seconds": self.duration_delta_seconds,
        }


@dataclass(frozen=True, slots=True)
class StabilityVector:
    """The accepted four-component OBJ-002 score plus exact KPI ratio."""

    soft_lock_violations: int
    changed_existing_operations: int
    resource_changes: int
    absolute_start_shift_seconds: int
    unchanged_existing: int
    comparable_existing: int

    @property
    def score(self) -> tuple[int, int, int, int]:
        return (
            self.soft_lock_violations,
            self.changed_existing_operations,
            self.resource_changes,
            self.absolute_start_shift_seconds,
        )

    @property
    def document(self) -> dict[str, object]:
        if self.comparable_existing == 0:
            ratio: dict[str, object] = {
                "status": "NOT_APPLICABLE_NO_COMPARABLE_OPERATION",
                "numerator": 0,
                "denominator": 0,
            }
        else:
            ratio = {
                "status": "APPLICABLE",
                "numerator": self.unchanged_existing,
                "denominator": self.comparable_existing,
            }
        return {
            "soft_lock_violations": self.soft_lock_violations,
            "changed_existing_operations": self.changed_existing_operations,
            "resource_changes": self.resource_changes,
            "absolute_start_shift_seconds": self.absolute_start_shift_seconds,
            "unchanged_existing": self.unchanged_existing,
            "comparable_existing": self.comparable_existing,
            "unchanged_ratio": ratio,
        }


def _mapping(value: object, field: str, entity_id: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message="value must be an object",
        )
    return cast(Mapping[str, object], value)


def _identifier(value: object, field: str, entity_id: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(character.isspace() for character in value)
    ):
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message="value must be a canonical identifier",
        )
    return value


def _integer(value: object, field: str, entity_id: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message=f"value must be an integer >= {minimum}",
        )
    return value


def _utc_second(value: object, field: str, entity_id: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message="instant must be RFC3339 UTC Z",
        )
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message=f"instant is invalid: {type(error).__name__}",
        )
    if instant.microsecond:
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message="instant must have whole-second precision",
        )
    return instant


def _identifier_list(value: object, field: str, entity_id: str) -> list[str]:
    if not isinstance(value, list):
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message="value must be an array",
        )
    identifiers = [
        _identifier(item, f"{field}[]", entity_id) for item in cast(list[object], value)
    ]
    if len(identifiers) != len(set(identifiers)):
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=entity_id,
            message="identifiers must be unique",
        )
    return sorted(identifiers)


def canonical_assignment(
    value: object,
    *,
    field: str,
) -> dict[str, object]:
    """Validate and normalize one frozen operation-assignment carrier."""

    assignment = _mapping(value, field, "<assignment>")
    operation_id = _identifier(
        assignment.get("operation_id"), f"{field}.operation_id", "<assignment>"
    )
    if set(assignment) != _ASSIGNMENT_FIELDS:
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=operation_id,
            message="fields differ from planning-solution.v1 operationAssignment",
        )
    resource_id = _identifier(
        assignment.get("resource_id"), f"{field}.resource_id", operation_id
    )
    start_tick = _integer(
        assignment.get("start_tick"), f"{field}.start_tick", operation_id, minimum=0
    )
    end_tick = _integer(
        assignment.get("end_tick"), f"{field}.end_tick", operation_id, minimum=1
    )
    duration_ticks = _integer(
        assignment.get("duration_ticks"),
        f"{field}.duration_ticks",
        operation_id,
        minimum=1,
    )
    duration_seconds = _integer(
        assignment.get("duration_seconds"),
        f"{field}.duration_seconds",
        operation_id,
        minimum=1,
    )
    start = _utc_second(
        assignment.get("start_at_utc"), f"{field}.start_at_utc", operation_id
    )
    end = _utc_second(
        assignment.get("end_at_utc"), f"{field}.end_at_utc", operation_id
    )
    if (
        end <= start
        or int((end - start).total_seconds()) != duration_seconds
        or end_tick - start_tick != duration_ticks
    ):
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field=field,
            entity_id=operation_id,
            message="tick, UTC, and duration fields are inconsistent",
        )
    return {
        "operation_id": operation_id,
        "resource_id": resource_id,
        "start_tick": start_tick,
        "end_tick": end_tick,
        "duration_ticks": duration_ticks,
        "start_at_utc": cast(str, assignment["start_at_utc"]),
        "end_at_utc": cast(str, assignment["end_at_utc"]),
        "duration_seconds": duration_seconds,
        "lock_ids": _identifier_list(
            assignment.get("lock_ids"), f"{field}.lock_ids", operation_id
        ),
        "execution_fact_ids": _identifier_list(
            assignment.get("execution_fact_ids"),
            f"{field}.execution_fact_ids",
            operation_id,
        ),
    }


def index_assignments(
    values: Sequence[object],
    *,
    field: str,
) -> dict[str, dict[str, object]]:
    """Return a deterministic operation-indexed assignment map."""

    indexed: dict[str, dict[str, object]] = {}
    for index, value in enumerate(values):
        assignment = canonical_assignment(value, field=f"{field}[{index}]")
        operation_id = cast(str, assignment["operation_id"])
        if operation_id in indexed:
            reject_change_report(
                ChangeReportFailure.DUPLICATE_OPERATION,
                field=field,
                entity_id=operation_id,
                message="operation assignment appears more than once",
            )
        indexed[operation_id] = assignment
    return dict(sorted(indexed.items()))


def calculate_operation_delta(
    base: Mapping[str, object],
    new: Mapping[str, object],
) -> OperationDelta:
    """Calculate exact UTC-second deltas without tick or float substitution."""

    operation_id = cast(str, base["operation_id"])
    if new.get("operation_id") != operation_id:
        reject_change_report(
            ChangeReportFailure.INVALID_ASSIGNMENT,
            field="new_assignment.operation_id",
            entity_id=operation_id,
            message="base and new operation IDs differ",
        )
    base_start = _utc_second(base["start_at_utc"], "base.start_at_utc", operation_id)
    new_start = _utc_second(new["start_at_utc"], "new.start_at_utc", operation_id)
    base_end = _utc_second(base["end_at_utc"], "base.end_at_utc", operation_id)
    new_end = _utc_second(new["end_at_utc"], "new.end_at_utc", operation_id)
    start_shift = int((new_start - base_start).total_seconds())
    return OperationDelta(
        resource_changed=base["resource_id"] != new["resource_id"],
        start_shift_seconds=start_shift,
        absolute_start_shift_seconds=abs(start_shift),
        end_shift_seconds=int((new_end - base_end).total_seconds()),
        duration_delta_seconds=cast(int, new["duration_seconds"])
        - cast(int, base["duration_seconds"]),
    )


def _active_ids(values: Sequence[str]) -> tuple[str, ...]:
    ids = tuple(_identifier(value, "active_operation_ids[]", "<active>") for value in values)
    if len(ids) != len(set(ids)):
        reject_change_report(
            ChangeReportFailure.DUPLICATE_OPERATION,
            field="active_operation_ids",
            entity_id="<active>",
            message="active operation IDs must be unique",
        )
    return tuple(sorted(ids))


def _soft_lock_violations(
    active_soft_locks: Sequence[object],
    new: Mapping[str, Mapping[str, object]],
) -> int:
    seen: set[str] = set()
    violations = 0
    for index, raw in enumerate(active_soft_locks):
        lock = _mapping(raw, f"active_soft_locks[{index}]", "<soft-lock>")
        lock_id = _identifier(
            lock.get("reference_id"),
            f"active_soft_locks[{index}].reference_id",
            "<soft-lock>",
        )
        if lock_id in seen:
            reject_change_report(
                ChangeReportFailure.INVALID_ASSIGNMENT,
                field="active_soft_locks",
                entity_id=lock_id,
                message="active SOFT lock IDs must be unique",
            )
        seen.add(lock_id)
        operation_id = _identifier(
            lock.get("operation_id"),
            f"active_soft_locks[{index}].operation_id",
            lock_id,
        )
        if lock.get("protection_kind") != "SOFT_LOCK" or lock.get(
            "protection_priority"
        ) != 4:
            reject_change_report(
                ChangeReportFailure.INVALID_ASSIGNMENT,
                field=f"active_soft_locks[{index}]",
                entity_id=lock_id,
                message="only active priority-4 SOFT_LOCK projections are accepted",
            )
        assignment = new.get(operation_id)
        if assignment is None:
            reject_change_report(
                ChangeReportFailure.ACTIVE_UNIVERSE_MISMATCH,
                field="active_soft_locks.operation_id",
                entity_id=operation_id,
                message="active SOFT lock must reference a new active assignment",
            )
        target = (
            _identifier(lock.get("resource_id"), "soft_lock.resource_id", lock_id),
            cast(str, lock.get("start_at_utc")),
            cast(str, lock.get("end_at_utc")),
        )
        target_start = _utc_second(target[1], "soft_lock.start_at_utc", lock_id)
        target_end = _utc_second(target[2], "soft_lock.end_at_utc", lock_id)
        if target_end <= target_start:
            reject_change_report(
                ChangeReportFailure.INVALID_ASSIGNMENT,
                field=f"active_soft_locks[{index}]",
                entity_id=lock_id,
                message="SOFT lock end must be after start",
            )
        observed = (
            assignment["resource_id"],
            assignment["start_at_utc"],
            assignment["end_at_utc"],
        )
        violations += int(observed != target)
    return violations


def calculate_stability(
    *,
    base_assignments: Sequence[object],
    new_assignments: Sequence[object],
    active_operation_ids: Sequence[str],
    active_soft_locks: Sequence[object],
) -> StabilityVector:
    """Calculate the accepted non-negative integer OBJ-002 vector."""

    base = index_assignments(base_assignments, field="base_assignments")
    new = index_assignments(new_assignments, field="new_assignments")
    active = _active_ids(active_operation_ids)
    if tuple(new) != active:
        reject_change_report(
            ChangeReportFailure.ACTIVE_UNIVERSE_MISMATCH,
            field="active_operation_ids",
            entity_id="<active>",
            message="new assignments must equal the complete active operation set",
        )
    changed = resource_changes = absolute_shift = 0
    comparable = sorted(set(base).intersection(active))
    for operation_id in comparable:
        delta = calculate_operation_delta(base[operation_id], new[operation_id])
        if delta.changed:
            changed += 1
            resource_changes += int(delta.resource_changed)
            absolute_shift += delta.absolute_start_shift_seconds
    return StabilityVector(
        soft_lock_violations=_soft_lock_violations(active_soft_locks, new),
        changed_existing_operations=changed,
        resource_changes=resource_changes,
        absolute_start_shift_seconds=absolute_shift,
        unchanged_existing=len(comparable) - changed,
        comparable_existing=len(comparable),
    )


__all__ = [
    "OperationDelta",
    "STABILITY_COMPONENTS",
    "STABILITY_OBJECTIVE_VERSION",
    "StabilityVector",
    "calculate_operation_delta",
    "calculate_stability",
    "canonical_assignment",
    "index_assignments",
]
