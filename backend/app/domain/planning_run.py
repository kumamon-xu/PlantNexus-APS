"""Pure PlanningRun orchestration contracts for the P8 Runtime boundary.

The public carrier remains ``planning-run.v1``.  This module implements the
frozen state table and bounded internal attempt/work-item records without
adding a PlanningRun state or a self-transition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
import re
from typing import Any, NoReturn, cast

from app.data_validation.canonical_ingress import (
    FrozenSchemaCatalog,
    canonical_fingerprint,
    canonical_json_bytes,
    run_fingerprint,
    runtime_resolution_fingerprint,
    scope_fingerprint,
)


type JsonObject = dict[str, Any]

PLANNING_RUN_SCHEMA_ID = "urn:plantnexus:aps:schema:planning-run:v1"
AUDIT_EVENT_SCHEMA_ID = "urn:plantnexus:aps:schema:audit-event:v1"
PLANNING_RUN_ATTEMPT_VERSION = "planning-run-attempt.v1"
PLANNING_RUN_WORK_ITEM_VERSION = "planning-run-work-item.v1"
PLANNING_RUN_COMMAND_RECORD_VERSION = "planning-run-command-record.v1"

PLANNING_RUN_STATES = frozenset(
    {
        "CREATED",
        "INGESTING",
        "VALIDATING",
        "SNAPSHOTTED",
        "BUILDING",
        "SOLVING",
        "SOLVED",
        "VERIFYING",
        "COMPLETED",
        "DATA_REJECTED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "CANCELLED",
        "FAILED",
    }
)
PLANNING_RUN_TERMINAL_STATES = frozenset(
    {
        "COMPLETED",
        "DATA_REJECTED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "CANCELLED",
        "FAILED",
    }
)
PLANNING_RUN_TRANSITIONS = frozenset(
    {
        ("CREATED", "INGESTING"),
        ("CREATED", "CANCELLED"),
        ("CREATED", "FAILED"),
        ("INGESTING", "VALIDATING"),
        ("INGESTING", "DATA_REJECTED"),
        ("INGESTING", "CANCELLED"),
        ("INGESTING", "FAILED"),
        ("VALIDATING", "SNAPSHOTTED"),
        ("VALIDATING", "DATA_REJECTED"),
        ("VALIDATING", "CANCELLED"),
        ("VALIDATING", "FAILED"),
        ("SNAPSHOTTED", "BUILDING"),
        ("SNAPSHOTTED", "CANCELLED"),
        ("SNAPSHOTTED", "FAILED"),
        ("BUILDING", "SOLVING"),
        ("BUILDING", "MODEL_INVALID"),
        ("BUILDING", "CANCELLED"),
        ("BUILDING", "FAILED"),
        ("SOLVING", "SOLVED"),
        ("SOLVING", "MODEL_INVALID"),
        ("SOLVING", "INFEASIBLE"),
        ("SOLVING", "NO_SOLUTION_WITHIN_LIMIT"),
        ("SOLVING", "CANCELLED"),
        ("SOLVING", "FAILED"),
        ("SOLVED", "VERIFYING"),
        ("SOLVED", "CANCELLED"),
        ("SOLVED", "FAILED"),
        ("VERIFYING", "COMPLETED"),
        ("VERIFYING", "VALIDATION_FAILED"),
        ("VERIFYING", "CANCELLED"),
        ("VERIFYING", "FAILED"),
    }
)

_IMMUTABLE_RUN_FIELDS = (
    "planning_run_version",
    "schema_set_version",
    "canonicalization_version",
    "transition_registry_version",
    "error_registry_version",
    "planning_run_id",
    "effective_scope",
    "ingress",
    "runtime_resolution",
    "inputs",
    "created_at_utc",
)
_ARTIFACT_FIELDS = (
    "import_quality_report",
    "snapshot",
    "problem",
    "planning_solution",
    "solver_report",
    "validation_report",
    "schedule_version",
)
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_FAILURE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


class PlanningRunErrorCode(StrEnum):
    """Stable application/persistence failures before P8 HTTP mapping."""

    INVALID_REFERENCE = "INVALID_REFERENCE"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    AUTHORITY_CONFLICT = "AUTHORITY_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    LINEAGE_INVALID = "LINEAGE_INVALID"
    RUNTIME_RESOLUTION_FAILED = "RUNTIME_RESOLUTION_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"
    STALE_RUN = "STALE_RUN"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    ATTEMPT_NOT_RETRYABLE = "ATTEMPT_NOT_RETRYABLE"
    QUEUE_FAILED = "QUEUE_FAILED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    APPEND_ONLY = "APPEND_ONLY"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class PlanningRunOrchestrationError(RuntimeError):
    """Sanitized error that never includes payload, SQL, paths, or secrets."""

    def __init__(
        self,
        code: PlanningRunErrorCode,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code.value}: {field}: {message}")


def reject(
    code: PlanningRunErrorCode,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise PlanningRunOrchestrationError(code, field=field, message=message)


class PlanningRunAttemptStatus(StrEnum):
    QUEUED = "QUEUED"
    ACTIVE = "ACTIVE"
    DISPATCH_FAILED = "DISPATCH_FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


ATTEMPT_TERMINAL_STATUSES = frozenset(
    {
        PlanningRunAttemptStatus.DISPATCH_FAILED,
        PlanningRunAttemptStatus.TIMED_OUT,
        PlanningRunAttemptStatus.CANCELLED,
        PlanningRunAttemptStatus.SUCCEEDED,
        PlanningRunAttemptStatus.FAILED,
    }
)
ATTEMPT_RETRYABLE_STATUSES = frozenset(
    {
        PlanningRunAttemptStatus.DISPATCH_FAILED,
        PlanningRunAttemptStatus.TIMED_OUT,
    }
)
ATTEMPT_TRANSITIONS = frozenset(
    {
        (PlanningRunAttemptStatus.QUEUED, PlanningRunAttemptStatus.ACTIVE),
        (
            PlanningRunAttemptStatus.QUEUED,
            PlanningRunAttemptStatus.DISPATCH_FAILED,
        ),
        (PlanningRunAttemptStatus.QUEUED, PlanningRunAttemptStatus.TIMED_OUT),
        (PlanningRunAttemptStatus.QUEUED, PlanningRunAttemptStatus.CANCELLED),
        (PlanningRunAttemptStatus.ACTIVE, PlanningRunAttemptStatus.SUCCEEDED),
        (PlanningRunAttemptStatus.ACTIVE, PlanningRunAttemptStatus.FAILED),
        (PlanningRunAttemptStatus.ACTIVE, PlanningRunAttemptStatus.TIMED_OUT),
        (
            PlanningRunAttemptStatus.ACTIVE,
            PlanningRunAttemptStatus.CANCEL_REQUESTED,
        ),
        (PlanningRunAttemptStatus.ACTIVE, PlanningRunAttemptStatus.CANCELLED),
        (
            PlanningRunAttemptStatus.CANCEL_REQUESTED,
            PlanningRunAttemptStatus.CANCELLED,
        ),
        (
            PlanningRunAttemptStatus.CANCEL_REQUESTED,
            PlanningRunAttemptStatus.FAILED,
        ),
        (
            PlanningRunAttemptStatus.CANCEL_REQUESTED,
            PlanningRunAttemptStatus.TIMED_OUT,
        ),
    }
)


def _document(raw: bytes, *, field: str) -> JsonObject:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlanningRunOrchestrationError(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Stored canonical document is unreadable",
        ) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Stored document is not canonical JSON",
        )
    return cast(JsonObject, value)


def _require_fields(
    document: Mapping[str, object], fields: set[str], field: str
) -> None:
    if set(document) != fields:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Stored document field set is invalid",
        )


def _require_fingerprint(value: object, field: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT.fullmatch(value) is None:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Expected a lowercase SHA-256 fingerprint",
        )
    return value


def _require_audit_reference(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Audit reference is absent",
        )
    _require_fields(
        value,
        {"document_version", "artifact_id", "fingerprint"},
        field,
    )
    if (
        value.get("document_version") != "audit-event.v1"
        or not isinstance(value.get("artifact_id"), str)
        or not value.get("artifact_id")
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Audit reference is invalid",
        )
    _require_fingerprint(value.get("fingerprint"), field)
    return value


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Expected a UTC instant ending in Z",
        )
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise PlanningRunOrchestrationError(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field=field,
            message="Expected a valid UTC instant",
        ) from error
    return parsed


def derived_identity(prefix: str, value: object) -> str:
    return f"{prefix}-{canonical_fingerprint(value).removeprefix('sha256:')}"


def require_planning_run_transition(from_state: str, to_state: str) -> None:
    """Reject every unknown, self, terminal-source, or unregistered pair."""

    if (
        from_state not in PLANNING_RUN_STATES
        or to_state not in PLANNING_RUN_STATES
        or from_state in PLANNING_RUN_TERMINAL_STATES
        or (from_state, to_state) not in PLANNING_RUN_TRANSITIONS
    ):
        reject(
            PlanningRunErrorCode.INVALID_STATE_TRANSITION,
            field="planning_run.last_transition",
            message="PlanningRun pair is not present in state-machines.v1",
        )


@dataclass(frozen=True, slots=True)
class PlanningRunAggregate:
    canonical_bytes: bytes
    initial_run_bytes: bytes
    prepared_artifacts_bytes: bytes
    source_ingress_id: str
    source_record_fingerprint: str

    @property
    def document(self) -> JsonObject:
        return _document(self.canonical_bytes, field="planning_run")

    @property
    def initial_document(self) -> JsonObject:
        return _document(self.initial_run_bytes, field="initial_planning_run")

    @property
    def prepared_artifacts(self) -> JsonObject:
        return _document(self.prepared_artifacts_bytes, field="prepared_artifacts")


@dataclass(frozen=True, slots=True)
class PlanningRunAttempt:
    canonical_bytes: bytes

    @property
    def document(self) -> JsonObject:
        return _document(self.canonical_bytes, field="planning_run_attempt")


@dataclass(frozen=True, slots=True)
class PlanningRunWorkItem:
    canonical_bytes: bytes

    @property
    def document(self) -> JsonObject:
        return _document(self.canonical_bytes, field="planning_run_work_item")


@dataclass(frozen=True, slots=True)
class PlanningRunCommandRecord:
    canonical_bytes: bytes

    @property
    def document(self) -> JsonObject:
        return _document(self.canonical_bytes, field="planning_run_command")


@dataclass(frozen=True, slots=True)
class PlanningRunReadModel:
    aggregate: PlanningRunAggregate
    attempts: tuple[PlanningRunAttempt, ...]
    work_items: tuple[PlanningRunWorkItem, ...]


@dataclass(frozen=True, slots=True)
class PlanningRunActionResult:
    aggregate: PlanningRunAggregate
    attempt: PlanningRunAttempt | None
    work_item: PlanningRunWorkItem | None
    audit_reference: Mapping[str, object] | None
    replayed: bool


def verify_planning_run(
    aggregate: PlanningRunAggregate,
    *,
    schemas: FrozenSchemaCatalog,
    previous: Mapping[str, object] | None = None,
) -> None:
    """Verify Schema, frozen transition pairs, fingerprints, and lineage."""

    document = aggregate.document
    initial = aggregate.initial_document
    prepared = aggregate.prepared_artifacts
    try:
        schemas.validate(PLANNING_RUN_SCHEMA_ID, document)
    except ValueError as error:
        raise PlanningRunOrchestrationError(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run",
            message="PlanningRun violates the frozen planning-run.v1 Schema",
        ) from error
    if initial.get("state") != "CREATED" or initial.get("revision") != 1:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="initial_planning_run",
            message="Source PlanningRun is not the frozen CREATED revision",
        )
    for field in _IMMUTABLE_RUN_FIELDS:
        if document.get(field) != initial.get(field):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field=f"planning_run.{field}",
                message="Immutable PlanningRun lineage changed",
            )
    if document.get("run_fingerprint") != run_fingerprint(document):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.run_fingerprint",
            message="PlanningRun fingerprint is invalid",
        )
    scope = document.get("effective_scope")
    runtime = document.get("runtime_resolution")
    if not isinstance(scope, Mapping) or scope.get("scope_fingerprint") != (
        scope_fingerprint(scope)
    ):
        reject(
            PlanningRunErrorCode.SCOPE_MISMATCH,
            field="planning_run.effective_scope",
            message="Effective scope fingerprint is invalid",
        )
    if not isinstance(runtime, Mapping) or runtime.get("resolution_fingerprint") != (
        runtime_resolution_fingerprint(runtime)
    ):
        reject(
            PlanningRunErrorCode.RUNTIME_RESOLUTION_FAILED,
            field="planning_run.runtime_resolution",
            message="Runtime resolution fingerprint is invalid",
        )
    transition = document.get("last_transition")
    if not isinstance(transition, Mapping):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.last_transition",
            message="PlanningRun transition evidence is absent",
        )
    sequence = transition.get("sequence")
    if type(sequence) is not int or document.get("revision") != sequence + 1:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.revision",
            message="PlanningRun revision does not equal transition sequence plus one",
        )
    if document.get("state") != transition.get("to_state"):
        reject(
            PlanningRunErrorCode.INVALID_STATE_TRANSITION,
            field="planning_run.last_transition.to_state",
            message="Current state and transition target differ",
        )
    if document.get("updated_at_utc") != transition.get("occurred_at_utc"):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.updated_at_utc",
            message="Update time and latest transition time differ",
        )
    audits = document.get("audit_references")
    revision = document.get("revision")
    if (
        not isinstance(audits, list)
        or type(revision) is not int
        or len(audits) != revision
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.audit_references",
            message="Audit history length does not equal PlanningRun revision",
        )
    for index, reference in enumerate(audits):
        _require_audit_reference(reference, f"planning_run.audit_references[{index}]")
    if transition.get("audit") != audits[-1]:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.audit_references",
            message="Latest transition audit is not the final audit reference",
        )
    cancellation = document.get("cancellation")
    if isinstance(cancellation, Mapping) and cancellation.get("audit") != transition.get(
        "audit"
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.cancellation.audit",
            message="Cancellation and terminal transition audit references differ",
        )
    from_state = transition.get("from_state")
    to_state = transition.get("to_state")
    if sequence == 0:
        if from_state is not None or to_state != "CREATED":
            reject(
                PlanningRunErrorCode.INVALID_STATE_TRANSITION,
                field="planning_run.last_transition",
                message="Initial transition must be null to CREATED",
            )
    elif not isinstance(from_state, str) or not isinstance(to_state, str):
        reject(
            PlanningRunErrorCode.INVALID_STATE_TRANSITION,
            field="planning_run.last_transition",
            message="PlanningRun transition states are invalid",
        )
    else:
        require_planning_run_transition(from_state, to_state)
    if previous is not None:
        previous_state = previous.get("state")
        previous_transition = previous.get("last_transition")
        previous_sequence = (
            previous_transition.get("sequence")
            if isinstance(previous_transition, Mapping)
            else None
        )
        if (
            previous_state in PLANNING_RUN_TERMINAL_STATES
            or from_state != previous_state
            or document.get("revision") != cast(int, previous.get("revision")) + 1
            or type(previous_sequence) is not int
            or sequence != previous_sequence + 1
        ):
            reject(
                PlanningRunErrorCode.INVALID_STATE_TRANSITION,
                field="planning_run.last_transition",
                message="PlanningRun transition is stale, terminal, or non-monotonic",
            )
        if _utc(document["updated_at_utc"], "planning_run.updated_at_utc") < _utc(
            previous["updated_at_utc"], "previous.updated_at_utc"
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run.updated_at_utc",
                message="PlanningRun transition time moved backwards",
            )
        previous_audits = previous.get("audit_references")
        if (
            not isinstance(previous_audits, list)
            or audits[:-1] != previous_audits
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run.audit_references",
                message="PlanningRun audit history is not append-only",
            )
        previous_artifacts = previous.get("artifacts")
        current_artifacts = document.get("artifacts")
        if isinstance(previous_artifacts, Mapping) and isinstance(
            current_artifacts, Mapping
        ):
            for name in _ARTIFACT_FIELDS:
                old = previous_artifacts.get(name)
                new = current_artifacts.get(name)
                if old is not None and new != old:
                    reject(
                        PlanningRunErrorCode.LINEAGE_INVALID,
                        field=f"planning_run.artifacts.{name}",
                        message="Published artifact reference was removed or changed",
                    )
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, Mapping):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run.artifacts",
            message="PlanningRun artifact map is invalid",
        )
    for name in ("import_quality_report", "snapshot", "problem"):
        value = artifacts.get(name)
        expected = prepared.get(name)
        if value is not None and value != expected:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field=f"planning_run.artifacts.{name}",
                message="PlanningRun prepared artifact differs from canonical ingress",
            )
    attempt = document.get("attempt")
    if isinstance(attempt, Mapping) and attempt.get(
        "runtime_resolution_fingerprint"
    ) != runtime.get("resolution_fingerprint"):
        reject(
            PlanningRunErrorCode.RUNTIME_RESOLUTION_FAILED,
            field="planning_run.attempt.runtime_resolution_fingerprint",
            message="Attempt and Runtime resolution fingerprints differ",
        )


_ATTEMPT_FIELDS = {
    "attempt_version",
    "attempt_id",
    "planning_run_id",
    "attempt_number",
    "revision",
    "status",
    "expected_run_revision",
    "expected_run_state",
    "expected_run_fingerprint",
    "runtime_resolution_fingerprint",
    "extension_set_fingerprint",
    "available_at_utc",
    "timeout_at_utc",
    "started_at_utc",
    "finished_at_utc",
    "failure_code",
    "result_references",
    "audit",
    "attempt_fingerprint",
}


def verify_attempt(
    attempt: PlanningRunAttempt,
    *,
    aggregate: PlanningRunAggregate,
    previous: Mapping[str, object] | None = None,
) -> None:
    document = attempt.document
    _require_fields(document, _ATTEMPT_FIELDS, "planning_run_attempt")
    if document.get("attempt_version") != PLANNING_RUN_ATTEMPT_VERSION:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.attempt_version",
            message="Attempt version is unsupported",
        )
    run = aggregate.document
    if document.get("planning_run_id") != run.get("planning_run_id"):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.planning_run_id",
            message="Attempt references another PlanningRun",
        )
    if document.get("attempt_fingerprint") != canonical_fingerprint(
        {key: value for key, value in document.items() if key != "attempt_fingerprint"}
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.attempt_fingerprint",
            message="Attempt fingerprint is invalid",
        )
    number = document.get("attempt_number")
    revision = document.get("revision")
    if (
        type(number) is not int
        or number < 1
        or type(revision) is not int
        or revision < 1
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt",
            message="Attempt number and revision must be positive integers",
        )
    try:
        status = PlanningRunAttemptStatus(cast(str, document.get("status")))
    except (TypeError, ValueError) as error:
        raise PlanningRunOrchestrationError(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.status",
            message="Attempt status is unknown",
        ) from error
    _require_fingerprint(
        document.get("expected_run_fingerprint"),
        "planning_run_attempt.expected_run_fingerprint",
    )
    _require_fingerprint(
        document.get("runtime_resolution_fingerprint"),
        "planning_run_attempt.runtime_resolution_fingerprint",
    )
    _require_fingerprint(
        document.get("extension_set_fingerprint"),
        "planning_run_attempt.extension_set_fingerprint",
    )
    runtime = run.get("runtime_resolution")
    extension_set = (
        runtime.get("extension_set") if isinstance(runtime, Mapping) else None
    )
    if (
        not isinstance(runtime, Mapping)
        or document.get("runtime_resolution_fingerprint")
        != runtime.get("resolution_fingerprint")
        or not isinstance(extension_set, Mapping)
        or document.get("extension_set_fingerprint")
        != extension_set.get("extension_set_fingerprint")
    ):
        reject(
            PlanningRunErrorCode.RUNTIME_RESOLUTION_FAILED,
            field="planning_run_attempt.runtime_resolution_fingerprint",
            message="Attempt is not bound to the PlanningRun Runtime resolution",
        )
    expected_revision = document.get("expected_run_revision")
    expected_state = document.get("expected_run_state")
    if (
        type(expected_revision) is not int
        or expected_revision < 1
        or expected_state not in PLANNING_RUN_STATES
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.expected_run",
            message="Attempt expected-run precondition is invalid",
        )
    available = _utc(document.get("available_at_utc"), "attempt.available_at_utc")
    timeout = _utc(document.get("timeout_at_utc"), "attempt.timeout_at_utc")
    if timeout <= available:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.timeout_at_utc",
            message="Attempt timeout must be after availability",
        )
    started = document.get("started_at_utc")
    finished = document.get("finished_at_utc")
    if status is PlanningRunAttemptStatus.QUEUED:
        if (
            started is not None
            or finished is not None
            or document.get("failure_code") is not None
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.status",
                message="Queued attempt cannot expose execution outcome",
            )
    elif status in {
        PlanningRunAttemptStatus.ACTIVE,
        PlanningRunAttemptStatus.CANCEL_REQUESTED,
    }:
        if (
            started is None
            or finished is not None
            or document.get("failure_code") is not None
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.status",
                message="Active attempt evidence is incomplete",
            )
    else:
        if finished is None:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.finished_at_utc",
                message="Non-active attempt must have a finish time",
            )
        if status in {
            PlanningRunAttemptStatus.SUCCEEDED,
            PlanningRunAttemptStatus.FAILED,
        } and started is None:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.started_at_utc",
                message="Executed terminal attempt has no start time",
            )
        if (
            status is PlanningRunAttemptStatus.DISPATCH_FAILED
            and started is not None
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.started_at_utc",
                message="Dispatch-failed attempt cannot expose a start time",
            )
        if status in {
            PlanningRunAttemptStatus.DISPATCH_FAILED,
            PlanningRunAttemptStatus.TIMED_OUT,
            PlanningRunAttemptStatus.FAILED,
        } and (
            not isinstance(document.get("failure_code"), str)
            or _FAILURE_CODE.fullmatch(cast(str, document.get("failure_code")))
            is None
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.failure_code",
                message="Failed attempt must have a stable sanitized failure code",
            )
        if (
            status
            in {
                PlanningRunAttemptStatus.CANCELLED,
                PlanningRunAttemptStatus.SUCCEEDED,
            }
            and document.get("failure_code") is not None
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.failure_code",
                message="Successful or cancelled attempt cannot report failure",
            )
    results = document.get("result_references")
    if not isinstance(results, Mapping) or set(results) != set(_ARTIFACT_FIELDS):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.result_references",
            message="Attempt result-reference field set is invalid",
        )
    if started is not None:
        started_at = _utc(started, "attempt.started_at_utc")
        if started_at < available or started_at > timeout:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.started_at_utc",
                message="Attempt start is outside its execution window",
            )
    if (
        finished is not None
        and started is not None
        and _utc(finished, "attempt.finished_at_utc")
        < _utc(started, "attempt.started_at_utc")
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_attempt.finished_at_utc",
            message="Attempt finish precedes its start",
        )
    audit = _require_audit_reference(
        document.get("audit"), "planning_run_attempt.audit"
    )
    if previous is not None:
        if any(
            document.get(field) != previous.get(field)
            for field in (
                "attempt_version",
                "attempt_id",
                "planning_run_id",
                "attempt_number",
                "expected_run_revision",
                "expected_run_state",
                "expected_run_fingerprint",
                "runtime_resolution_fingerprint",
                "extension_set_fingerprint",
                "available_at_utc",
                "timeout_at_utc",
            )
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt",
                message="Immutable attempt identity changed",
            )
        try:
            old_status = PlanningRunAttemptStatus(cast(str, previous.get("status")))
        except ValueError as error:
            raise PlanningRunOrchestrationError(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="previous_attempt.status",
                message="Previous attempt status is unknown",
            ) from error
        if (old_status, status) not in ATTEMPT_TRANSITIONS or document.get(
            "revision"
        ) != cast(int, previous.get("revision")) + 1:
            reject(
                PlanningRunErrorCode.STALE_ATTEMPT,
                field="planning_run_attempt.status",
                message="Attempt transition is stale or illegal",
            )
        if previous.get("started_at_utc") is not None and document.get(
            "started_at_utc"
        ) != previous.get("started_at_utc"):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.started_at_utc",
                message="Attempt start time changed after execution began",
            )
        previous_results = previous.get("result_references")
        if not isinstance(previous_results, Mapping):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="previous_attempt.result_references",
                message="Previous attempt result references are invalid",
            )
        for name in _ARTIFACT_FIELDS:
            prior = previous_results.get(name)
            if prior is not None and results.get(name) != prior:
                reject(
                    PlanningRunErrorCode.LINEAGE_INVALID,
                    field=f"planning_run_attempt.result_references.{name}",
                    message="Attempt result reference was removed or changed",
                )
        previous_audit = _require_audit_reference(
            previous.get("audit"), "previous_attempt.audit"
        )
        if audit == previous_audit:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="planning_run_attempt.audit",
                message="Attempt transition did not append new audit evidence",
            )


_WORK_ITEM_FIELDS = {
    "work_item_version",
    "work_item_id",
    "planning_run_id",
    "attempt_id",
    "attempt_number",
    "expected_run_revision",
    "expected_run_state",
    "expected_run_fingerprint",
    "runtime_resolution",
    "prepared_artifacts",
    "inputs",
    "available_at_utc",
    "timeout_at_utc",
    "correlation_id",
    "audit",
    "work_item_fingerprint",
}


def verify_work_item(
    work_item: PlanningRunWorkItem,
    *,
    aggregate: PlanningRunAggregate,
    attempt: PlanningRunAttempt,
    bind_attempt_audit: bool = True,
) -> None:
    document = work_item.document
    _require_fields(document, _WORK_ITEM_FIELDS, "planning_run_work_item")
    if document.get("work_item_version") != PLANNING_RUN_WORK_ITEM_VERSION:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_work_item.work_item_version",
            message="Work-item version is unsupported",
        )
    run = aggregate.document
    attempt_document = attempt.document
    if (
        document.get("planning_run_id") != run.get("planning_run_id")
        or document.get("attempt_id") != attempt_document.get("attempt_id")
        or document.get("attempt_number") != attempt_document.get("attempt_number")
        or document.get("expected_run_revision")
        != attempt_document.get("expected_run_revision")
        or document.get("expected_run_state")
        != attempt_document.get("expected_run_state")
        or document.get("expected_run_fingerprint")
        != attempt_document.get("expected_run_fingerprint")
        or document.get("available_at_utc") != attempt_document.get("available_at_utc")
        or document.get("timeout_at_utc") != attempt_document.get("timeout_at_utc")
        or document.get("runtime_resolution") != run.get("runtime_resolution")
        or document.get("prepared_artifacts") != aggregate.prepared_artifacts
        or document.get("inputs") != run.get("inputs")
        or (
            bind_attempt_audit
            and document.get("audit") != attempt_document.get("audit")
        )
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_work_item",
            message="Work item differs from its immutable Run/attempt inputs",
        )
    _require_audit_reference(
        document.get("audit"), "planning_run_work_item.audit"
    )
    if document.get("work_item_fingerprint") != canonical_fingerprint(
        {
            key: value
            for key, value in document.items()
            if key != "work_item_fingerprint"
        }
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_work_item.work_item_fingerprint",
            message="Work-item fingerprint is invalid",
        )


_COMMAND_FIELDS = {
    "command_record_version",
    "command_id",
    "operation",
    "planning_run_id",
    "scope_fingerprint",
    "key_reference",
    "request_fingerprint",
    "occurred_at_utc",
    "audit",
    "result",
    "record_fingerprint",
}


def verify_command_record(record: PlanningRunCommandRecord) -> None:
    document = record.document
    _require_fields(document, _COMMAND_FIELDS, "planning_run_command")
    if document.get("command_record_version") != PLANNING_RUN_COMMAND_RECORD_VERSION:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_command.command_record_version",
            message="Command-record version is unsupported",
        )
    for field in (
        "scope_fingerprint",
        "key_reference",
        "request_fingerprint",
    ):
        _require_fingerprint(document.get(field), f"planning_run_command.{field}")
    _utc(document.get("occurred_at_utc"), "planning_run_command.occurred_at_utc")
    if document.get("record_fingerprint") != canonical_fingerprint(
        {key: value for key, value in document.items() if key != "record_fingerprint"}
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_command.record_fingerprint",
            message="Command-record fingerprint is invalid",
        )
    result = document.get("result")
    if not isinstance(result, Mapping) or set(result) != {
        "planning_run",
        "attempt",
        "work_item",
    }:
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_command.result",
            message="Command result is invalid",
        )
    _require_audit_reference(document.get("audit"), "planning_run_command.audit")
    planning_run = result.get("planning_run")
    attempt = result.get("attempt")
    work_item = result.get("work_item")
    if (
        not isinstance(planning_run, Mapping)
        or (attempt is not None and not isinstance(attempt, Mapping))
        or (work_item is not None and not isinstance(work_item, Mapping))
        or planning_run.get("planning_run_id") != document.get("planning_run_id")
        or (
            isinstance(attempt, Mapping)
            and attempt.get("planning_run_id") != document.get("planning_run_id")
        )
        or (
            isinstance(work_item, Mapping)
            and (
                not isinstance(attempt, Mapping)
                or work_item.get("planning_run_id")
                != document.get("planning_run_id")
                or work_item.get("attempt_id") != attempt.get("attempt_id")
            )
        )
    ):
        reject(
            PlanningRunErrorCode.LINEAGE_INVALID,
            field="planning_run_command.result",
            message="Command result lineage is inconsistent",
        )


__all__ = [
    "ATTEMPT_RETRYABLE_STATUSES",
    "ATTEMPT_TERMINAL_STATUSES",
    "ATTEMPT_TRANSITIONS",
    "AUDIT_EVENT_SCHEMA_ID",
    "PLANNING_RUN_ATTEMPT_VERSION",
    "PLANNING_RUN_COMMAND_RECORD_VERSION",
    "PLANNING_RUN_SCHEMA_ID",
    "PLANNING_RUN_STATES",
    "PLANNING_RUN_TERMINAL_STATES",
    "PLANNING_RUN_TRANSITIONS",
    "PLANNING_RUN_WORK_ITEM_VERSION",
    "PlanningRunActionResult",
    "PlanningRunAggregate",
    "PlanningRunAttempt",
    "PlanningRunAttemptStatus",
    "PlanningRunCommandRecord",
    "PlanningRunErrorCode",
    "PlanningRunOrchestrationError",
    "PlanningRunReadModel",
    "PlanningRunWorkItem",
    "derived_identity",
    "reject",
    "require_planning_run_transition",
    "verify_attempt",
    "verify_command_record",
    "verify_planning_run",
    "verify_work_item",
]
