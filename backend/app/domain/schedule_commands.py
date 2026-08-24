"""Pure P3 schedule edit and lock command semantics.

This module validates the frozen ``workspace-command.v1`` carrier, applies one
copy-on-write mutation to immutable ScheduleVersion content, constructs a new
DRAFT, or builds an explicit same-content DRAFT-to-READY review submission.
It never persists data, runs a solver, or evaluates the formal C-001 through
C-011 rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
import re
from typing import Never, cast

from app.domain.types import (
    ContractValueError,
    duration_to_ticks,
    format_utc_instant,
    parse_utc_instant,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    require_workspace_document,
    schedule_content_fingerprint,
    workspace_fingerprint,
)


SCHEDULE_COMMAND_PIPELINE_VERSION = "schedule-command-pipeline.v1"
_CONTENT_COMMANDS = frozenset(
    {"MOVE_OPERATION", "ASSIGN_RESOURCE", "SET_LOCK", "REMOVE_LOCK"}
)
_SUPPORTED_COMMANDS = frozenset({*_CONTENT_COMMANDS, "SUBMIT_FOR_REVIEW"})
_COMMAND_CAPABILITY = {
    "MOVE_OPERATION": "edit",
    "ASSIGN_RESOURCE": "edit",
    "SET_LOCK": "lock",
    "REMOVE_LOCK": "lock",
    "SUBMIT_FOR_REVIEW": "edit",
}
_COMMAND_ACTION = {
    "MOVE_OPERATION": "EDIT_SCHEDULE",
    "ASSIGN_RESOURCE": "EDIT_SCHEDULE",
    "SET_LOCK": "SET_LOCK",
    "REMOVE_LOCK": "REMOVE_LOCK",
    "SUBMIT_FOR_REVIEW": "SUBMIT_FOR_REVIEW",
}
_COMMAND_PAYLOAD_FIELDS = {
    "MOVE_OPERATION": frozenset(
        {"operation_id", "resource_id", "start_at_utc", "end_at_utc"}
    ),
    "ASSIGN_RESOURCE": frozenset({"operation_id", "resource_id"}),
    "SET_LOCK": frozenset({"lock"}),
    "REMOVE_LOCK": frozenset({"lock_id", "operation_id"}),
    "SUBMIT_FOR_REVIEW": frozenset(),
}
_COMMAND_FIELDS = frozenset(
    {
        "workspace_command_version",
        "schema_set_version",
        "canonicalization_version",
        "command_id",
        "command_type",
        "required_capability",
        "idempotency_key",
        "idempotency_scope",
        "request_fingerprint",
        "source_id",
        "expected_state",
        "expected_content_fingerprint",
        "data_plane",
        "environment",
        "synthetic",
        "synthetic_provenance",
        "target",
        "reason",
        "correlation_id",
        "payload",
    }
)
_LOCK_FIELDS = frozenset(
    {
        "lock_id",
        "operation_id",
        "lock_type",
        "resource_id",
        "start_at_utc",
        "end_at_utc",
    }
)
_ACTOR_REFERENCE = re.compile(r"actor:[A-Za-z0-9._:-]+")
_CANONICAL_ID = re.compile(r"[^\s\x00-\x1f\x7f]+")
_GIT_COMMIT = re.compile(r"(?:[0-9a-f]{40}|uncommitted)")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{16,128}")


class ScheduleCommandFailure(StrEnum):
    """Stable sanitized failure reasons for TASK-P3-06."""

    INVALID_COMMAND = "INVALID_COMMAND"
    UNAUTHORIZED = "UNAUTHORIZED"
    PRODUCTION_AUTHORITY_UNAVAILABLE = "PRODUCTION_AUTHORITY_UNAVAILABLE"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    STALE_SOURCE = "STALE_SOURCE"
    MIXED_LINEAGE = "MIXED_LINEAGE"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    INVALID_TIME = "INVALID_TIME"
    IMMUTABLE_EXECUTION_FACT = "IMMUTABLE_EXECUTION_FACT"
    LOCK_CONFLICT = "LOCK_CONFLICT"
    NO_OP = "NO_OP"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ScheduleCommandError(ValueError):
    """One stable command rejection without adapter or credential details."""

    def __init__(
        self,
        reason: ScheduleCommandFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value}: {field}: {message}")


@dataclass(frozen=True, slots=True)
class ScheduleCommandContext:
    """Server-resolved execution facts; never a client authorization claim."""

    actor_ref: str
    resolved_capabilities: frozenset[str]
    auth_policy_version: str
    occurred_at_utc: str
    code_commit: str
    parent_audit_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class ScheduleCommandIdentity:
    """Deterministic idempotency identity available before source lookup."""

    command_type: str
    action: str
    required_capability: str
    request_fingerprint: str
    key_reference: str
    schedule_version_id: str
    audit_event_id: str


@dataclass(frozen=True, slots=True)
class PreparedScheduleCommand:
    """A server-checked copy-on-write candidate awaiting formal validation."""

    source: dict[str, object]
    command: dict[str, object]
    problem: dict[str, object]
    content: dict[str, object]
    validator_candidate: dict[str, object]
    identity: ScheduleCommandIdentity
    context: ScheduleCommandContext
    data_plane: str


@dataclass(frozen=True, slots=True)
class ScheduleCommandDocuments:
    """The two durable documents written in one consistency boundary."""

    draft: dict[str, object]
    audit_event: dict[str, object]
    identity: ScheduleCommandIdentity
    validation_fingerprint: str


@dataclass(frozen=True, slots=True)
class PreparedReviewSubmission:
    """One immutable manual DRAFT awaiting a fresh formal review gate."""

    source: dict[str, object]
    command: dict[str, object]
    problem: dict[str, object]
    validator_candidate: dict[str, object]
    identity: ScheduleCommandIdentity
    context: ScheduleCommandContext
    data_plane: str


@dataclass(frozen=True, slots=True)
class ScheduleReviewSubmissionDocuments:
    """The READY candidate and audit committed by one CAS transaction."""

    ready_for_review: dict[str, object]
    audit_event: dict[str, object]
    identity: ScheduleCommandIdentity
    validation_fingerprint: str


def reject_command(
    reason: ScheduleCommandFailure,
    *,
    field: str,
    message: str,
) -> Never:
    raise ScheduleCommandError(reason, field=field, message=message)


def _clone(value: Mapping[str, object]) -> dict[str, object]:
    import json

    return cast(dict[str, object], json.loads(canonical_workspace_bytes(value)))


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=field,
            message="must be an object",
        )
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=field,
            message="must be an array",
        )
    return cast(Sequence[object], value)


def _text(value: object, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=field,
            message="must be bounded non-empty text",
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=field,
            message="must not contain control characters",
        )
    return value


def _canonical_id(value: object, field: str) -> str:
    text = _text(value, field, maximum=256)
    if _CANONICAL_ID.fullmatch(text) is None:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=field,
            message="must be a canonical identifier",
        )
    return text


def _require_fields(
    value: Mapping[str, object],
    expected: frozenset[str],
    field: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=field,
            message="fields do not match the frozen command contract",
        )


def _utc(value: object, field: str):  # type: ignore[no-untyped-def]
    text = _text(value, field)
    try:
        parsed = parse_utc_instant(text)
    except ContractValueError as error:
        raise ScheduleCommandError(
            ScheduleCommandFailure.INVALID_TIME,
            field=field,
            message="must be a valid RFC 3339 UTC instant ending in Z",
        ) from error
    if format_utc_instant(parsed) != text:
        reject_command(
            ScheduleCommandFailure.INVALID_TIME,
            field=field,
            message="must use canonical second-precision UTC",
        )
    return parsed


def _validate_context(context: ScheduleCommandContext, data_plane: str) -> None:
    actor = _text(context.actor_ref, "context.actor_ref", maximum=256)
    if _ACTOR_REFERENCE.fullmatch(actor) is None:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="context.actor_ref",
            message="must be a sanitized actor reference",
        )
    _text(context.auth_policy_version, "context.auth_policy_version")
    _utc(context.occurred_at_utc, "context.occurred_at_utc")
    if _GIT_COMMIT.fullmatch(context.code_commit) is None:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="context.code_commit",
            message="must be a full Git commit or uncommitted",
        )
    if context.parent_audit_event_id is not None:
        _canonical_id(context.parent_audit_event_id, "context.parent_audit_event_id")
    if data_plane not in {"SIMULATION", "PRODUCTION"}:
        reject_command(
            ScheduleCommandFailure.DATA_PLANE_MISMATCH,
            field="data_plane",
            message="must be SIMULATION or PRODUCTION",
        )
    if data_plane == "PRODUCTION":
        reject_command(
            ScheduleCommandFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
            field="data_plane",
            message="Production command authority is not configured",
        )


def schedule_command_identity(
    command: Mapping[str, object], *, data_plane: str
) -> ScheduleCommandIdentity:
    """Validate identity; derive Audit/new-DRAFT IDs or retain submit source ID."""

    command_fields = set(_COMMAND_FIELDS)
    if "synthetic_provenance" not in command:
        command_fields.remove("synthetic_provenance")
    _require_fields(command, frozenset(command_fields), "command")
    try:
        require_workspace_document(command)
    except (TypeError, ValueError) as error:
        raise ScheduleCommandError(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=getattr(error, "field", "command"),
            message="failed the frozen workspace command contract",
        ) from error
    command_type = _text(command.get("command_type"), "command.command_type")
    if command_type not in _SUPPORTED_COMMANDS:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="command.command_type",
            message="TASK-P3-06 accepts only edit, lock, and review-submit commands",
        )
    payload = _mapping(command.get("payload"), "command.payload")
    _require_fields(payload, _COMMAND_PAYLOAD_FIELDS[command_type], "command.payload")
    source_id = _canonical_id(command.get("source_id"), "command.source_id")
    if command.get("data_plane") != data_plane:
        reject_command(
            ScheduleCommandFailure.DATA_PLANE_MISMATCH,
            field="command.data_plane",
            message="does not match the repository plane",
        )
    if command.get("target") != "WORKSPACE_INTERNAL":
        reject_command(
            ScheduleCommandFailure.DATA_PLANE_MISMATCH,
            field="command.target",
            message="edit and lock commands are workspace-internal only",
        )
    key = _text(command.get("idempotency_key"), "command.idempotency_key", maximum=128)
    if _IDEMPOTENCY_KEY.fullmatch(key) is None:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="command.idempotency_key",
            message="does not match the frozen idempotency key contract",
        )
    scope = _text(command.get("idempotency_scope"), "command.idempotency_scope")
    expected_scope = f"{data_plane}/{command_type}/{source_id}/WORKSPACE_INTERNAL"
    if scope != expected_scope:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="command.idempotency_scope",
            message="does not match the server-derived command scope",
        )
    key_reference = workspace_fingerprint(
        {"idempotency_scope": scope, "idempotency_key": key}
    )
    identity_suffix = key_reference.removeprefix("sha256:")
    schedule_version_id = (
        source_id
        if command_type == "SUBMIT_FOR_REVIEW"
        else f"schedule-version-command-{identity_suffix}"
    )
    return ScheduleCommandIdentity(
        command_type=command_type,
        action=_COMMAND_ACTION[command_type],
        required_capability=_COMMAND_CAPABILITY[command_type],
        request_fingerprint=_text(
            command.get("request_fingerprint"), "command.request_fingerprint"
        ),
        key_reference=key_reference,
        schedule_version_id=schedule_version_id,
        audit_event_id=f"audit-event-command-{identity_suffix}",
    )


def require_schedule_command_authorization(
    context: ScheduleCommandContext,
    identity: ScheduleCommandIdentity,
    *,
    data_plane: str,
) -> None:
    """Fail closed before source lookup or idempotent result replay."""

    _validate_context(context, data_plane)
    if identity.required_capability not in context.resolved_capabilities:
        reject_command(
            ScheduleCommandFailure.UNAUTHORIZED,
            field="context.resolved_capabilities",
            message="does not contain the server-required capability",
        )


def _prepare_command_inputs(
    source: Mapping[str, object],
    problem: Mapping[str, object],
    command: Mapping[str, object],
    context: ScheduleCommandContext,
    *,
    data_plane: str,
) -> tuple[
    ScheduleCommandIdentity,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    """Bind one authorized command to an exact immutable source and Problem."""

    identity = schedule_command_identity(command, data_plane=data_plane)
    require_schedule_command_authorization(context, identity, data_plane=data_plane)
    try:
        require_workspace_document(source)
    except (TypeError, ValueError) as error:
        raise ScheduleCommandError(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field=getattr(error, "field", "source"),
            message="source ScheduleVersion failed its immutable carrier contract",
        ) from error
    if source.get("schedule_version_version") != "schedule-version.v1":
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="source.schedule_version_version",
            message="must be schedule-version.v1",
        )
    comparisons = {
        "source_id": source.get("schedule_version_id"),
        "expected_state": source.get("state"),
        "expected_content_fingerprint": source.get("content_fingerprint"),
        "data_plane": source.get("data_plane"),
        "environment": source.get("environment"),
        "synthetic": source.get("synthetic"),
    }
    for command_field, source_value in comparisons.items():
        if command.get(command_field) != source_value:
            reason = (
                ScheduleCommandFailure.STALE_SOURCE
                if command_field
                in {"source_id", "expected_state", "expected_content_fingerprint"}
                else ScheduleCommandFailure.DATA_PLANE_MISMATCH
            )
            reject_command(
                reason,
                field=f"command.{command_field}",
                message="does not match the authoritative source Version",
            )
    if command.get("synthetic_provenance") != source.get("synthetic_provenance"):
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="command.synthetic_provenance",
            message="does not match the source Version provenance",
        )
    _canonical_id(command.get("command_id"), "command.command_id")
    _canonical_id(command.get("correlation_id"), "command.correlation_id")
    _text(command.get("reason"), "command.reason")
    payload = _mapping(command.get("payload"), "command.payload")
    _require_fields(
        payload, _COMMAND_PAYLOAD_FIELDS[identity.command_type], "command.payload"
    )
    return identity, _clone(source), _clone(problem), _clone(command)


def _problem_views(
    problem: Mapping[str, object], source: Mapping[str, object]
) -> tuple[dict[str, Mapping[str, object]], set[str], int, object, object]:
    if problem.get("problem_version") != "planning-problem.v2":
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="problem.problem_version",
            message="must be planning-problem.v2",
        )
    lineage = _mapping(source.get("lineage"), "source.lineage")
    problem_reference = _mapping(lineage.get("problem"), "source.lineage.problem")
    if problem_reference.get("fingerprint") != problem.get("problem_hash"):
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="problem.problem_hash",
            message="does not match the source ScheduleVersion lineage",
        )
    operations: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(
        _sequence(problem.get("operation_instances"), "problem.operation_instances")
    ):
        operation = _mapping(raw, f"problem.operation_instances[{index}]")
        operation_id = _canonical_id(
            operation.get("operation_id"),
            f"problem.operation_instances[{index}].operation_id",
        )
        if operation_id in operations:
            reject_command(
                ScheduleCommandFailure.MIXED_LINEAGE,
                field="problem.operation_instances.operation_id",
                message="contains a duplicate operation",
            )
        operations[operation_id] = operation
    resources = {
        _canonical_id(
            _mapping(raw, f"problem.resources[{index}]").get("resource_id"),
            f"problem.resources[{index}].resource_id",
        )
        for index, raw in enumerate(
            _sequence(problem.get("resources"), "problem.resources")
        )
    }
    tick_seconds = problem.get("tick_seconds")
    if (
        isinstance(tick_seconds, bool)
        or not isinstance(tick_seconds, int)
        or tick_seconds <= 0
    ):
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="problem.tick_seconds",
            message="must be a positive integer",
        )
    horizon_start = _utc(problem.get("horizon_start_utc"), "problem.horizon_start_utc")
    horizon_end = _utc(problem.get("horizon_end_utc"), "problem.horizon_end_utc")
    return operations, resources, tick_seconds, horizon_start, horizon_end


def _content_views(
    source: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    content = _mapping(source.get("content"), "source.content")
    assignments: dict[str, dict[str, object]] = {}
    for index, raw in enumerate(
        _sequence(content.get("assignments"), "source.content.assignments")
    ):
        assignment = _clone(_mapping(raw, f"source.content.assignments[{index}]"))
        operation_id = _canonical_id(
            assignment.get("operation_id"),
            f"source.content.assignments[{index}].operation_id",
        )
        if operation_id in assignments:
            reject_command(
                ScheduleCommandFailure.MIXED_LINEAGE,
                field="source.content.assignments.operation_id",
                message="contains a duplicate assignment",
            )
        assignments[operation_id] = assignment
    locks: dict[str, dict[str, object]] = {}
    for index, raw in enumerate(
        _sequence(content.get("locks"), "source.content.locks")
    ):
        lock = _clone(_mapping(raw, f"source.content.locks[{index}]"))
        lock_id = _canonical_id(
            lock.get("lock_id"), f"source.content.locks[{index}].lock_id"
        )
        if lock_id in locks:
            reject_command(
                ScheduleCommandFailure.MIXED_LINEAGE,
                field="source.content.locks.lock_id",
                message="contains a duplicate lock",
            )
        locks[lock_id] = lock
    return assignments, locks


def _resource_option(
    operation: Mapping[str, object], resource_id: str
) -> Mapping[str, object]:
    for index, raw in enumerate(
        _sequence(operation.get("resource_options"), "operation.resource_options")
    ):
        option = _mapping(raw, f"operation.resource_options[{index}]")
        if option.get("resource_id") == resource_id:
            duration = option.get("final_duration_seconds")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, int)
                or duration <= 0
            ):
                reject_command(
                    ScheduleCommandFailure.MIXED_LINEAGE,
                    field="operation.resource_options.final_duration_seconds",
                    message="must be a positive integer",
                )
            return option
    reject_command(
        ScheduleCommandFailure.INVALID_REFERENCE,
        field="command.payload.resource_id",
        message="is not a candidate resource for the operation",
    )


def _modifiable_assignment(
    operation_id: str,
    operations: Mapping[str, Mapping[str, object]],
    assignments: Mapping[str, dict[str, object]],
) -> tuple[Mapping[str, object], dict[str, object]]:
    operation = operations.get(operation_id)
    assignment = assignments.get(operation_id)
    if operation is None or assignment is None:
        reject_command(
            ScheduleCommandFailure.INVALID_REFERENCE,
            field="command.payload.operation_id",
            message="does not identify one scheduled operation",
        )
    if operation.get("status") in {"RUNNING", "COMPLETED"}:
        reject_command(
            ScheduleCommandFailure.IMMUTABLE_EXECUTION_FACT,
            field="command.payload.operation_id",
            message="RUNNING and COMPLETED facts cannot be moved or reassigned",
        )
    return operation, assignment


def _require_hard_locks(
    assignment: Mapping[str, object], locks: Mapping[str, Mapping[str, object]]
) -> None:
    operation_id = assignment.get("operation_id")
    for lock in locks.values():
        if lock.get("operation_id") != operation_id or lock.get("lock_type") != "HARD":
            continue
        if any(
            (
                assignment.get("resource_id") != lock.get("resource_id"),
                assignment.get("start_at_utc") != lock.get("start_at_utc"),
                assignment.get("end_at_utc") != lock.get("end_at_utc"),
            )
        ):
            reject_command(
                ScheduleCommandFailure.LOCK_CONFLICT,
                field="command.payload",
                message="would violate an existing HARD lock",
            )


def _move_operation(
    payload: Mapping[str, object],
    *,
    operations: Mapping[str, Mapping[str, object]],
    resources: set[str],
    assignments: dict[str, dict[str, object]],
    locks: Mapping[str, Mapping[str, object]],
    tick_seconds: int,
    horizon_start,
    horizon_end,
) -> None:  # type: ignore[no-untyped-def]
    operation_id = _canonical_id(
        payload.get("operation_id"), "command.payload.operation_id"
    )
    resource_id = _canonical_id(
        payload.get("resource_id"), "command.payload.resource_id"
    )
    if resource_id not in resources:
        reject_command(
            ScheduleCommandFailure.INVALID_REFERENCE,
            field="command.payload.resource_id",
            message="does not identify a Problem resource",
        )
    operation, assignment = _modifiable_assignment(
        operation_id, operations, assignments
    )
    option = _resource_option(operation, resource_id)
    start = _utc(payload.get("start_at_utc"), "command.payload.start_at_utc")
    end = _utc(payload.get("end_at_utc"), "command.payload.end_at_utc")
    start_seconds = int((start - horizon_start).total_seconds())
    end_seconds = int((end - horizon_start).total_seconds())
    if (
        start < horizon_start
        or end > horizon_end
        or start >= end
        or start_seconds % tick_seconds != 0
        or end_seconds % tick_seconds != 0
    ):
        reject_command(
            ScheduleCommandFailure.INVALID_TIME,
            field="command.payload.start_at_utc/end_at_utc",
            message="must be one positive tick-aligned interval inside the horizon",
        )
    duration_seconds = cast(int, option["final_duration_seconds"])
    duration_ticks = duration_to_ticks(duration_seconds, tick_seconds)
    start_tick = start_seconds // tick_seconds
    end_tick = end_seconds // tick_seconds
    if end_tick - start_tick != duration_ticks:
        reject_command(
            ScheduleCommandFailure.INVALID_TIME,
            field="command.payload.end_at_utc",
            message="does not match the selected resource duration",
        )
    assignment.update(
        {
            "resource_id": resource_id,
            "start_tick": start_tick,
            "end_tick": end_tick,
            "duration_ticks": duration_ticks,
            "start_at_utc": format_utc_instant(start),
            "end_at_utc": format_utc_instant(end),
            "duration_seconds": duration_seconds,
        }
    )
    _require_hard_locks(assignment, locks)


def _assign_resource(
    payload: Mapping[str, object],
    *,
    operations: Mapping[str, Mapping[str, object]],
    resources: set[str],
    assignments: dict[str, dict[str, object]],
    locks: Mapping[str, Mapping[str, object]],
    tick_seconds: int,
    horizon_start,
    horizon_end,
) -> None:  # type: ignore[no-untyped-def]
    operation_id = _canonical_id(
        payload.get("operation_id"), "command.payload.operation_id"
    )
    resource_id = _canonical_id(
        payload.get("resource_id"), "command.payload.resource_id"
    )
    if resource_id not in resources:
        reject_command(
            ScheduleCommandFailure.INVALID_REFERENCE,
            field="command.payload.resource_id",
            message="does not identify a Problem resource",
        )
    operation, assignment = _modifiable_assignment(
        operation_id, operations, assignments
    )
    option = _resource_option(operation, resource_id)
    start_tick = assignment.get("start_tick")
    if (
        isinstance(start_tick, bool)
        or not isinstance(start_tick, int)
        or start_tick < 0
    ):
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="source.content.assignment.start_tick",
            message="must be a non-negative integer",
        )
    duration_seconds = cast(int, option["final_duration_seconds"])
    duration_ticks = duration_to_ticks(duration_seconds, tick_seconds)
    end_tick = start_tick + duration_ticks
    end = horizon_start + timedelta(seconds=end_tick * tick_seconds)
    if end > horizon_end:
        reject_command(
            ScheduleCommandFailure.INVALID_TIME,
            field="command.payload.resource_id",
            message="selected duration would exceed the planning horizon",
        )
    assignment.update(
        {
            "resource_id": resource_id,
            "end_tick": end_tick,
            "duration_ticks": duration_ticks,
            "end_at_utc": format_utc_instant(end),
            "duration_seconds": duration_seconds,
        }
    )
    _require_hard_locks(assignment, locks)


def _set_lock(
    payload: Mapping[str, object],
    *,
    operations: Mapping[str, Mapping[str, object]],
    resources: set[str],
    assignments: dict[str, dict[str, object]],
    locks: dict[str, dict[str, object]],
) -> None:
    lock = _clone(_mapping(payload.get("lock"), "command.payload.lock"))
    _require_fields(lock, _LOCK_FIELDS, "command.payload.lock")
    lock_id = _canonical_id(lock.get("lock_id"), "command.payload.lock.lock_id")
    operation_id = _canonical_id(
        lock.get("operation_id"), "command.payload.lock.operation_id"
    )
    if operation_id not in operations or operation_id not in assignments:
        reject_command(
            ScheduleCommandFailure.INVALID_REFERENCE,
            field="command.payload.lock.operation_id",
            message="does not identify one scheduled operation",
        )
    if lock_id in locks:
        reject_command(
            ScheduleCommandFailure.LOCK_CONFLICT,
            field="command.payload.lock.lock_id",
            message="already exists in the source Version",
        )
    lock_type = lock.get("lock_type")
    if lock_type not in {"HARD", "SOFT"}:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="command.payload.lock.lock_type",
            message="must be HARD or SOFT",
        )
    resource_id = lock.get("resource_id")
    if resource_id is not None and resource_id not in resources:
        reject_command(
            ScheduleCommandFailure.INVALID_REFERENCE,
            field="command.payload.lock.resource_id",
            message="does not identify a Problem resource",
        )
    start_raw = lock.get("start_at_utc")
    end_raw = lock.get("end_at_utc")
    if (start_raw is None) != (end_raw is None):
        reject_command(
            ScheduleCommandFailure.INVALID_TIME,
            field="command.payload.lock.start_at_utc/end_at_utc",
            message="must both be null or both be present",
        )
    if start_raw is not None and end_raw is not None:
        start = _utc(start_raw, "command.payload.lock.start_at_utc")
        end = _utc(end_raw, "command.payload.lock.end_at_utc")
        if start >= end:
            reject_command(
                ScheduleCommandFailure.INVALID_TIME,
                field="command.payload.lock.start_at_utc/end_at_utc",
                message="must have positive duration",
            )
    assignment = assignments[operation_id]
    if lock_type == "HARD" and any(
        (
            assignment.get("resource_id") != resource_id,
            assignment.get("start_at_utc") != start_raw,
            assignment.get("end_at_utc") != end_raw,
        )
    ):
        reject_command(
            ScheduleCommandFailure.LOCK_CONFLICT,
            field="command.payload.lock",
            message="a HARD lock must match the current assignment exactly",
        )
    lock_ids = assignment.get("lock_ids")
    if not isinstance(lock_ids, list) or not all(
        isinstance(value, str) for value in lock_ids
    ):
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="source.content.assignment.lock_ids",
            message="must be an array of lock identities",
        )
    assignment["lock_ids"] = sorted({*cast(list[str], lock_ids), lock_id})
    locks[lock_id] = lock


def _remove_lock(
    payload: Mapping[str, object],
    *,
    problem: Mapping[str, object],
    assignments: dict[str, dict[str, object]],
    locks: dict[str, dict[str, object]],
) -> None:
    lock_id = _canonical_id(payload.get("lock_id"), "command.payload.lock_id")
    operation_id = _canonical_id(
        payload.get("operation_id"), "command.payload.operation_id"
    )
    lock = locks.get(lock_id)
    assignment = assignments.get(operation_id)
    if lock is None or assignment is None or lock.get("operation_id") != operation_id:
        reject_command(
            ScheduleCommandFailure.INVALID_REFERENCE,
            field="command.payload.lock_id/operation_id",
            message="does not identify one Version lock",
        )
    for raw in _sequence(problem.get("operation_locks"), "problem.operation_locks"):
        source_lock = _mapping(raw, "problem.operation_locks[]")
        if (
            source_lock.get("lock_id") == lock_id
            and source_lock.get("lock_type") == "HARD_LOCK"
        ):
            reject_command(
                ScheduleCommandFailure.LOCK_CONFLICT,
                field="command.payload.lock_id",
                message="an authoritative Problem HARD lock cannot be removed",
            )
    lock_ids = assignment.get("lock_ids")
    if not isinstance(lock_ids, list) or lock_id not in lock_ids:
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="source.content.assignment.lock_ids",
            message="does not bind the Version lock",
        )
    assignment["lock_ids"] = sorted(
        value for value in cast(list[str], lock_ids) if value != lock_id
    )
    del locks[lock_id]


def prepare_schedule_command(
    source: Mapping[str, object],
    problem: Mapping[str, object],
    command: Mapping[str, object],
    context: ScheduleCommandContext,
    *,
    data_plane: str,
) -> PreparedScheduleCommand:
    """Apply one server-checked mutation without touching durable state."""

    identity, source_clone, problem_clone, command_clone = _prepare_command_inputs(
        source,
        problem,
        command,
        context,
        data_plane=data_plane,
    )
    if identity.command_type not in _CONTENT_COMMANDS:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="command.command_type",
            message="review submission is not a content mutation",
        )
    payload = _mapping(command_clone.get("payload"), "command.payload")
    operations, resources, tick_seconds, horizon_start, horizon_end = _problem_views(
        problem_clone, source_clone
    )
    assignments, locks = _content_views(source_clone)
    if identity.command_type == "MOVE_OPERATION":
        _move_operation(
            payload,
            operations=operations,
            resources=resources,
            assignments=assignments,
            locks=locks,
            tick_seconds=tick_seconds,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
    elif identity.command_type == "ASSIGN_RESOURCE":
        _assign_resource(
            payload,
            operations=operations,
            resources=resources,
            assignments=assignments,
            locks=locks,
            tick_seconds=tick_seconds,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
    elif identity.command_type == "SET_LOCK":
        _set_lock(
            payload,
            operations=operations,
            resources=resources,
            assignments=assignments,
            locks=locks,
        )
    else:
        _remove_lock(
            payload,
            problem=problem_clone,
            assignments=assignments,
            locks=locks,
        )
    content: dict[str, object] = {
        "assignments": [assignments[key] for key in sorted(assignments)],
        "locks": [locks[key] for key in sorted(locks)],
    }
    if workspace_fingerprint(content) == source.get("content_fingerprint"):
        reject_command(
            ScheduleCommandFailure.NO_OP,
            field="command.payload",
            message="does not change ScheduleVersion content",
        )
    validator_candidate = {
        "problem": {
            field: problem_clone[field]
            for field in (
                "problem_version",
                "problem_builder_version",
                "problem_hash_projection_version",
                "problem_hash",
                "snapshot_id",
                "tick_seconds",
                "horizon_start_utc",
                "horizon_end_utc",
            )
        },
        "assignments": deepcopy(content["assignments"]),
    }
    return PreparedScheduleCommand(
        source=source_clone,
        command=command_clone,
        problem=problem_clone,
        content=content,
        validator_candidate=validator_candidate,
        identity=identity,
        context=context,
        data_plane=data_plane,
    )


def prepare_review_submission(
    source: Mapping[str, object],
    problem: Mapping[str, object],
    command: Mapping[str, object],
    context: ScheduleCommandContext,
    *,
    data_plane: str,
) -> PreparedReviewSubmission:
    """Prepare an explicit manual DRAFT→READY submission without content change."""

    identity, source_clone, problem_clone, command_clone = _prepare_command_inputs(
        source,
        problem,
        command,
        context,
        data_plane=data_plane,
    )
    if identity.command_type != "SUBMIT_FOR_REVIEW":
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="command.command_type",
            message="must be SUBMIT_FOR_REVIEW",
        )
    if source_clone.get("state") != "DRAFT":
        reject_command(
            ScheduleCommandFailure.STALE_SOURCE,
            field="command.expected_state",
            message="review submission requires an exact DRAFT source",
        )
    if source_clone.get("source_kind") not in {"MANUAL_EDIT", "LOCK_CHANGE"}:
        reject_command(
            ScheduleCommandFailure.INVALID_COMMAND,
            field="source.source_kind",
            message="TASK-P3-06 submits only manual edit or lock DRAFTs",
        )
    _problem_views(problem_clone, source_clone)
    content = _mapping(source_clone.get("content"), "source.content")
    assignments = _sequence(content.get("assignments"), "source.content.assignments")
    validator_candidate = {
        "problem": {
            field: problem_clone[field]
            for field in (
                "problem_version",
                "problem_builder_version",
                "problem_hash_projection_version",
                "problem_hash",
                "snapshot_id",
                "tick_seconds",
                "horizon_start_utc",
                "horizon_end_utc",
            )
        },
        "assignments": deepcopy(assignments),
    }
    return PreparedReviewSubmission(
        source=source_clone,
        command=command_clone,
        problem=problem_clone,
        validator_candidate=validator_candidate,
        identity=identity,
        context=context,
        data_plane=data_plane,
    )


def _fresh_validation(
    problem: Mapping[str, object], validation_report: Mapping[str, object]
) -> tuple[dict[str, object], str]:
    if (
        validation_report.get("validation_report_version") != "validation-report.v2"
        or validation_report.get("problem_hash") != problem.get("problem_hash")
        or validation_report.get("status") != "PASS"
        or validation_report.get("hard_violation_count") != 0
        or validation_report.get("violations") != []
    ):
        reject_command(
            ScheduleCommandFailure.VALIDATION_FAILED,
            field="validation_report",
            message="fresh independent validation did not return PASS with zero violations",
        )
    report = _clone(validation_report)
    return report, workspace_fingerprint(report)


def build_schedule_command_documents(
    prepared: PreparedScheduleCommand,
    validation_report: Mapping[str, object],
) -> ScheduleCommandDocuments:
    """Build a new DRAFT and success audit only after a fresh formal PASS."""

    report, validation_fingerprint = _fresh_validation(
        prepared.problem, validation_report
    )
    lineage = _clone(_mapping(prepared.source.get("lineage"), "source.lineage"))
    lineage["validation_report"] = {
        "document_version": "validation-report.v2",
        "artifact_id": f"validation-report-{validation_fingerprint.removeprefix('sha256:')}",
        "fingerprint": validation_fingerprint,
    }
    source_id = cast(str, prepared.source["schedule_version_id"])
    source_state = cast(str, prepared.source["state"])
    source_fingerprint = cast(str, prepared.source["content_fingerprint"])
    revision = prepared.source.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="source.revision",
            message="must be a positive integer",
        )
    draft: dict[str, object] = {
        "schedule_version_version": "schedule-version.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "schedule_version_id": prepared.identity.schedule_version_id,
        "revision": revision + 1,
        "state": "DRAFT",
        "data_plane": prepared.data_plane,
        "environment": prepared.source["environment"],
        "synthetic": prepared.source["synthetic"],
        "parent_schedule_version": {
            "schedule_version_id": source_id,
            "state": source_state,
            "content_fingerprint": source_fingerprint,
        },
        "source_kind": (
            "MANUAL_EDIT"
            if prepared.identity.command_type in {"MOVE_OPERATION", "ASSIGN_RESOURCE"}
            else "LOCK_CHANGE"
        ),
        "lineage": lineage,
        "content": deepcopy(prepared.content),
        "content_fingerprint": workspace_fingerprint(prepared.content),
        "validation": {
            "validation_report": lineage["validation_report"],
            "status": "PASS",
            "hard_violation_count": 0,
            "validated_at_utc": prepared.context.occurred_at_utc,
        },
        "decision": None,
        "publication": None,
        "superseded_by": None,
        "allowed_actions": ["view", "edit", "lock"],
        "created_at_utc": prepared.context.occurred_at_utc,
        "created_by_actor_ref": prepared.context.actor_ref,
    }
    if prepared.source.get("synthetic") is True:
        draft["synthetic_provenance"] = deepcopy(
            prepared.source["synthetic_provenance"]
        )
    draft["content_fingerprint"] = schedule_content_fingerprint(draft)
    source_reference = {
        "schedule_version_id": source_id,
        "state": source_state,
        "content_fingerprint": source_fingerprint,
    }
    new_reference = {
        "schedule_version_id": prepared.identity.schedule_version_id,
        "state": "DRAFT",
        "content_fingerprint": draft["content_fingerprint"],
    }
    audit_event: dict[str, object] = {
        "audit_event_version": "audit-event.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "audit_event_id": prepared.identity.audit_event_id,
        "occurred_at_utc": prepared.context.occurred_at_utc,
        "actor_ref": prepared.context.actor_ref,
        "resolved_capability": prepared.identity.required_capability,
        "auth_policy_version": prepared.context.auth_policy_version,
        "environment": prepared.source["environment"],
        "data_plane": prepared.data_plane,
        "synthetic": prepared.source["synthetic"],
        "action": prepared.identity.action,
        "aggregate_type": "SCHEDULE_VERSION",
        "aggregate_id": prepared.identity.schedule_version_id,
        "target": "WORKSPACE_INTERNAL",
        "intent_type": "COMMAND",
        "reason": prepared.command["reason"],
        "request_fingerprint": prepared.identity.request_fingerprint,
        "idempotency_reference": {
            "scope": prepared.command["idempotency_scope"],
            "key_reference": prepared.identity.key_reference,
            "request_fingerprint": prepared.identity.request_fingerprint,
        },
        "lineage": lineage,
        "before_state": source_state,
        "after_state": "DRAFT",
        "source_version": source_reference,
        "new_version": new_reference,
        "export_job_id": None,
        "result": {
            "outcome": "SUCCEEDED",
            "replayed": False,
            "retryable": False,
            "error": None,
        },
        "correlation_id": prepared.command["correlation_id"],
        "parent_audit_event_id": prepared.context.parent_audit_event_id,
        "code_commit": prepared.context.code_commit,
    }
    if prepared.source.get("synthetic") is True:
        audit_event["synthetic_provenance"] = deepcopy(
            prepared.source["synthetic_provenance"]
        )
    try:
        require_workspace_document(draft)
        require_workspace_document(audit_event)
    except (TypeError, ValueError) as error:
        raise ScheduleCommandError(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=getattr(error, "field", "schedule_version/audit_event"),
            message="constructed command result failed its frozen carrier contract",
        ) from error
    return ScheduleCommandDocuments(
        draft=draft,
        audit_event=audit_event,
        identity=prepared.identity,
        validation_fingerprint=validation_fingerprint,
    )


def build_review_submission_documents(
    prepared: PreparedReviewSubmission,
    validation_report: Mapping[str, object],
) -> ScheduleReviewSubmissionDocuments:
    """Build an immutable DRAFT→READY candidate after a second fresh PASS."""

    _, validation_fingerprint = _fresh_validation(prepared.problem, validation_report)
    lineage = _clone(_mapping(prepared.source.get("lineage"), "source.lineage"))
    validation_reference = _mapping(
        lineage.get("validation_report"), "source.lineage.validation_report"
    )
    if validation_reference.get("fingerprint") != validation_fingerprint:
        reject_command(
            ScheduleCommandFailure.MIXED_LINEAGE,
            field="source.lineage.validation_report.fingerprint",
            message="does not match the fresh independent validation report",
        )
    source_id = cast(str, prepared.source["schedule_version_id"])
    content_fingerprint = cast(str, prepared.source["content_fingerprint"])
    ready = deepcopy(prepared.source)
    ready.update(
        {
            "state": "READY_FOR_REVIEW",
            "allowed_actions": ["view", "approve", "reject"],
        }
    )
    source_reference = {
        "schedule_version_id": source_id,
        "state": "DRAFT",
        "content_fingerprint": content_fingerprint,
    }
    new_reference = {
        "schedule_version_id": source_id,
        "state": "READY_FOR_REVIEW",
        "content_fingerprint": content_fingerprint,
    }
    audit_event: dict[str, object] = {
        "audit_event_version": "audit-event.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "audit_event_id": prepared.identity.audit_event_id,
        "occurred_at_utc": prepared.context.occurred_at_utc,
        "actor_ref": prepared.context.actor_ref,
        "resolved_capability": prepared.identity.required_capability,
        "auth_policy_version": prepared.context.auth_policy_version,
        "environment": prepared.source["environment"],
        "data_plane": prepared.data_plane,
        "synthetic": prepared.source["synthetic"],
        "action": "SUBMIT_FOR_REVIEW",
        "aggregate_type": "SCHEDULE_VERSION",
        "aggregate_id": source_id,
        "target": "WORKSPACE_INTERNAL",
        "intent_type": "COMMAND",
        "reason": prepared.command["reason"],
        "request_fingerprint": prepared.identity.request_fingerprint,
        "idempotency_reference": {
            "scope": prepared.command["idempotency_scope"],
            "key_reference": prepared.identity.key_reference,
            "request_fingerprint": prepared.identity.request_fingerprint,
        },
        "lineage": lineage,
        "before_state": "DRAFT",
        "after_state": "READY_FOR_REVIEW",
        "source_version": source_reference,
        "new_version": new_reference,
        "export_job_id": None,
        "result": {
            "outcome": "SUCCEEDED",
            "replayed": False,
            "retryable": False,
            "error": None,
        },
        "correlation_id": prepared.command["correlation_id"],
        "parent_audit_event_id": prepared.context.parent_audit_event_id,
        "code_commit": prepared.context.code_commit,
    }
    if prepared.source.get("synthetic") is True:
        audit_event["synthetic_provenance"] = deepcopy(
            prepared.source["synthetic_provenance"]
        )
    try:
        require_workspace_document(ready)
        require_workspace_document(audit_event)
    except (TypeError, ValueError) as error:
        raise ScheduleCommandError(
            ScheduleCommandFailure.INVALID_COMMAND,
            field=getattr(error, "field", "schedule_version/audit_event"),
            message="constructed review submission failed its frozen carrier contract",
        ) from error
    return ScheduleReviewSubmissionDocuments(
        ready_for_review=ready,
        audit_event=audit_event,
        identity=prepared.identity,
        validation_fingerprint=validation_fingerprint,
    )


__all__ = [
    "PreparedScheduleCommand",
    "PreparedReviewSubmission",
    "SCHEDULE_COMMAND_PIPELINE_VERSION",
    "ScheduleCommandContext",
    "ScheduleCommandDocuments",
    "ScheduleCommandError",
    "ScheduleCommandFailure",
    "ScheduleCommandIdentity",
    "ScheduleReviewSubmissionDocuments",
    "build_review_submission_documents",
    "build_schedule_command_documents",
    "prepare_schedule_command",
    "prepare_review_submission",
    "require_schedule_command_authorization",
    "reject_command",
    "schedule_command_identity",
]
