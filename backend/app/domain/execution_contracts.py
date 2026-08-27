"""Pure P4 execution/replan machine-contract values and semantic prechecks.

The module has no persistence, solver, simulator, API, clock, random, or network
dependency.  It validates already-built documents and their immutable lineage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import json
from typing import NoReturn, TypedDict, cast


SCHEMA_SET_VERSION = "2.8.0"
CANONICALIZATION_VERSION = "canonical-json.v1"

EXECUTION_EVENT_VERSION = "execution-event.v1"
REPLAN_REQUEST_VERSION = "replan-request.v1"
CHANGE_REPORT_VERSION = "change-report.v1"
EXECUTION_SIMULATION_MANIFEST_VERSION = "execution-simulation-manifest.v1"
PLANNING_POLICY_VERSION = "planning-policy.v2"
SOLVER_REPORT_VERSION = "solver-report.v2"
SCHEDULE_VERSION = "schedule-version.v2"
EXPORT_MANIFEST_VERSION = "export-manifest.v3"
EXPORT_JOB_VERSION = "export-job.v3"


class ArtifactReference(TypedDict):
    """Versioned immutable artifact identity used by P4 carriers."""

    document_version: str
    artifact_id: str
    fingerprint: str


class P4ContractReason(StrEnum):
    """Stable local reasons; these do not extend the product error registry."""

    UNKNOWN_DOCUMENT = "UNKNOWN_DOCUMENT"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    PLANE_VIOLATION = "PLANE_VIOLATION"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    ORDERING_VIOLATION = "ORDERING_VIOLATION"
    FREEZE_VIOLATION = "FREEZE_VIOLATION"
    INCOMPLETE_CHANGE_REPORT = "INCOMPLETE_CHANGE_REPORT"
    STABILITY_MISMATCH = "STABILITY_MISMATCH"
    CONTRACT_BOUNDARY_VIOLATION = "CONTRACT_BOUNDARY_VIOLATION"


class P4ContractError(ValueError):
    """Fail-closed P4 carrier rejection before any downstream side effect."""

    def __init__(self, reason: P4ContractReason, field: str, message: str) -> None:
        super().__init__(f"{reason.value}:{field}:{message}")
        self.reason = reason
        self.field = field


_VERSION_FIELDS = {
    "execution_event_version": EXECUTION_EVENT_VERSION,
    "replan_request_version": REPLAN_REQUEST_VERSION,
    "change_report_version": CHANGE_REPORT_VERSION,
    "execution_simulation_manifest_version": EXECUTION_SIMULATION_MANIFEST_VERSION,
    "planning_policy_version": PLANNING_POLICY_VERSION,
    "solver_report_version": SOLVER_REPORT_VERSION,
    "schedule_version_version": SCHEDULE_VERSION,
    "export_manifest_version": EXPORT_MANIFEST_VERSION,
    "export_job_version": EXPORT_JOB_VERSION,
}

_STAGE_SIGNATURES = (
    (1, "OBJ-001", "WEIGHTED_TARDINESS_SECONDS", "MINIMIZE"),
    (2, "OBJ-002", "STABILITY_VECTOR", "LEXICOGRAPHIC_MINIMIZE"),
    (3, "OBJ-003", "MAKESPAN_SECONDS", "MINIMIZE"),
)

_STABILITY_COMPONENTS = (
    "SOFT_LOCK_VIOLATIONS",
    "CHANGED_EXISTING_OPERATIONS",
    "RESOURCE_CHANGES",
    "ABSOLUTE_START_SHIFT_SECONDS",
)

_STATUS_OUTCOMES: dict[str, tuple[str, str | None]] = {
    "OPTIMAL": ("SOLVED", None),
    "FEASIBLE": ("SOLVED", None),
    "INFEASIBLE": ("INFEASIBLE", "INFEASIBLE"),
    "UNKNOWN": ("NO_SOLUTION_WITHIN_LIMIT", "NO_SOLUTION_WITHIN_LIMIT"),
    "MODEL_INVALID": ("MODEL_INVALID", "MODEL_INVALID"),
    "CANCELLED": ("CANCELLED", None),
    "FAILED": ("FAILED", "SYSTEM_ERROR"),
}

_EXPORT_PATHS = (
    "change_report.json",
    "import_quality_report.json",
    "kpi.json",
    "order_summary.csv",
    "planning_solution.json",
    "publication_result.json",
    "resource_load.csv",
    "scenario_manifest.json",
    "schedule_operations.csv",
    "schedule_version.json",
    "solver_report.json",
    "standard_package.xlsx",
    "validation_report.json",
)


def _reject(reason: P4ContractReason, field: str, message: str) -> NoReturn:
    raise P4ContractError(reason, field, message)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(P4ContractReason.VERSION_MISMATCH, field, "must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, list):
        _reject(P4ContractReason.VERSION_MISMATCH, field, "must be an array")
    return value


def _integer(value: object, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _reject(P4ContractReason.VERSION_MISMATCH, field, "must be an integer")
    if minimum is not None and value < minimum:
        _reject(P4ContractReason.VERSION_MISMATCH, field, "is below minimum")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        _reject(P4ContractReason.VERSION_MISMATCH, field, "must be a canonical identifier")
    return value


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _reject(P4ContractReason.VERSION_MISMATCH, field, "must be RFC3339 UTC Z")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject(P4ContractReason.VERSION_MISMATCH, field, "is not a valid instant")
    return instant


def _equal(actual: object, expected: object, field: str, reason: P4ContractReason) -> None:
    if actual != expected:
        _reject(reason, field, "does not match the immutable contract projection")


def canonical_contract_bytes(value: object) -> bytes:
    """Return stable canonical-json.v1 bytes for JSON-compatible values."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        _reject(
            P4ContractReason.CONTRACT_BOUNDARY_VIOLATION,
            "$",
            f"cannot canonicalize: {type(error).__name__}",
        )
    return encoded.encode("utf-8")


def contract_fingerprint(value: object) -> str:
    """Hash complete canonical content with lowercase SHA-256."""

    return f"sha256:{sha256(canonical_contract_bytes(value)).hexdigest()}"


def _without(document: Mapping[str, object], *excluded: str) -> dict[str, object]:
    return {key: value for key, value in document.items() if key not in excluded}


def execution_event_fingerprint(document: Mapping[str, object]) -> str:
    """Identity excludes self fields and non-authoritative receive observation."""

    return contract_fingerprint(
        _without(document, "event_id", "event_fingerprint", "received_at_utc")
    )


def event_stream_fingerprint(event_fingerprints: Sequence[object]) -> str:
    """Fingerprint an ordered authority stream prefix."""

    return contract_fingerprint(
        {
            "stream_projection_version": "execution-event-stream.v1",
            "ordered_event_fingerprints": list(event_fingerprints),
        }
    )


def freeze_policy_fingerprint(policy: Mapping[str, object]) -> str:
    return contract_fingerprint(policy)


def replan_request_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(_without(document, "request_id", "request_fingerprint"))


def solver_report_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(_without(document, "report_id", "report_fingerprint"))


def change_report_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(
        _without(document, "report_id", "report_fingerprint", "generated_at_utc")
    )


def schedule_content_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(_mapping(document.get("content"), "content"))


def simulation_manifest_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(_without(document, "manifest_id", "manifest_fingerprint"))


def export_manifest_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(
        _without(document, "package_id", "manifest_fingerprint", "generated_at_utc")
    )


def export_job_fingerprint(document: Mapping[str, object]) -> str:
    return contract_fingerprint(_without(document, "job_fingerprint"))


def p4_document_version(document: Mapping[str, object]) -> str:
    """Return the one supported P4 discriminator; reject cross-interchange."""

    found = [
        expected
        for field, expected in _VERSION_FIELDS.items()
        if document.get(field) == expected
    ]
    if len(found) != 1:
        _reject(
            P4ContractReason.UNKNOWN_DOCUMENT,
            "$",
            "exactly one supported P4 document version is required",
        )
    return found[0]


def _require_simulation_boundary(document: Mapping[str, object]) -> None:
    if "data_plane" in document:
        _equal(
            document["data_plane"],
            "SIMULATION",
            "data_plane",
            P4ContractReason.PLANE_VIOLATION,
        )
    if "environment" in document and document["environment"] not in {
        "DEVELOPMENT",
        "TEST",
        "BENCHMARK",
    }:
        _reject(P4ContractReason.PLANE_VIOLATION, "environment", "is not isolated")
    if "production_binding" in document:
        _equal(
            document["production_binding"],
            False,
            "production_binding",
            P4ContractReason.PLANE_VIOLATION,
        )
    if "synthetic" in document:
        _equal(
            document["synthetic"],
            True,
            "synthetic",
            P4ContractReason.PLANE_VIOLATION,
        )


def _require_identity(
    document: Mapping[str, object],
    *,
    fingerprint_field: str,
    identity_field: str,
    identity_prefix: str,
    expected_fingerprint: str,
) -> None:
    _equal(
        document.get(fingerprint_field),
        expected_fingerprint,
        fingerprint_field,
        P4ContractReason.IDENTITY_MISMATCH,
    )
    _equal(
        document.get(identity_field),
        f"{identity_prefix}{expected_fingerprint.removeprefix('sha256:')}",
        identity_field,
        P4ContractReason.IDENTITY_MISMATCH,
    )


def _authority_scope(document: Mapping[str, object]) -> None:
    authority = _mapping(document.get("authority"), "authority")
    stream = _mapping(document.get("source_stream"), "source_stream")
    expected_scope = (
        f"SIMULATION/{document.get('factory_id')}/{document.get('planning_scope_id')}"
    )
    _equal(
        authority.get("authority_scope"),
        expected_scope,
        "authority.authority_scope",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        stream.get("authority_id"),
        authority.get("authority_id"),
        "source_stream.authority_id",
        P4ContractReason.REFERENCE_MISMATCH,
    )


def _require_event(document: Mapping[str, object]) -> None:
    _authority_scope(document)
    payload = _mapping(document.get("payload"), "payload")
    _equal(
        payload.get("kind"),
        document.get("event_type"),
        "payload.kind",
        P4ContractReason.VERSION_MISMATCH,
    )
    references = [
        (
            _text(_mapping(item, "entity_refs[]").get("entity_type"), "entity_type"),
            _text(_mapping(item, "entity_refs[]").get("entity_id"), "entity_id"),
        )
        for item in _sequence(document.get("entity_refs"), "entity_refs")
    ]
    if references != sorted(set(references)):
        _reject(
            P4ContractReason.ORDERING_VIOLATION,
            "entity_refs",
            "must be sorted and unique",
        )
    occurred = _utc(document.get("occurred_at_utc"), "occurred_at_utc")
    received = _utc(document.get("received_at_utc"), "received_at_utc")
    if received < occurred:
        _reject(
            P4ContractReason.ORDERING_VIOLATION,
            "received_at_utc",
            "cannot precede occurred_at_utc",
        )
    expected = execution_event_fingerprint(document)
    _require_identity(
        document,
        fingerprint_field="event_fingerprint",
        identity_field="event_id",
        identity_prefix="execution-event-",
        expected_fingerprint=expected,
    )


def _require_policy(document: Mapping[str, object]) -> None:
    freeze = _mapping(document.get("freeze_policy"), "freeze_policy")
    _integer(freeze.get("window_seconds"), "freeze_policy.window_seconds", minimum=1)
    stages = _sequence(document.get("objective_stages"), "objective_stages")
    signatures = tuple(
        (
            _mapping(stage, "objective_stages[]").get("stage_index"),
            _mapping(stage, "objective_stages[]").get("objective_id"),
            _mapping(stage, "objective_stages[]").get("metric"),
            _mapping(stage, "objective_stages[]").get("sense"),
        )
        for stage in stages
    )
    _equal(
        signatures,
        _STAGE_SIGNATURES,
        "objective_stages",
        P4ContractReason.ORDERING_VIOLATION,
    )
    stability = _mapping(stages[1], "objective_stages[1]")
    _equal(
        tuple(_sequence(stability.get("components"), "objective_stages[1].components")),
        _STABILITY_COMPONENTS,
        "objective_stages[1].components",
        P4ContractReason.ORDERING_VIOLATION,
    )


def _require_replan(document: Mapping[str, object]) -> None:
    base = _mapping(document.get("base_schedule_version"), "base_schedule_version")
    _equal(
        base.get("state"),
        "PUBLISHED",
        "base_schedule_version.state",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    stream = _mapping(document.get("event_stream"), "event_stream")
    first = _integer(stream.get("from_position"), "event_stream.from_position", minimum=1)
    last = _integer(stream.get("through_position"), "event_stream.through_position", minimum=1)
    ids = _sequence(stream.get("event_ids"), "event_stream.event_ids")
    fingerprints = _sequence(
        stream.get("event_fingerprints"), "event_stream.event_fingerprints"
    )
    if last < first or len(ids) != last - first + 1 or len(fingerprints) != len(ids):
        _reject(
            P4ContractReason.ORDERING_VIOLATION,
            "event_stream",
            "positions and ordered event vectors diverge",
        )
    _equal(
        stream.get("stream_fingerprint"),
        event_stream_fingerprint(fingerprints),
        "event_stream.stream_fingerprint",
        P4ContractReason.IDENTITY_MISMATCH,
    )
    triggers = _sequence(document.get("trigger_event_ids"), "trigger_event_ids")
    if not triggers or any(trigger not in ids for trigger in triggers):
        _reject(
            P4ContractReason.REFERENCE_MISMATCH,
            "trigger_event_ids",
            "must reference the ordered event stream",
        )
    freeze = _mapping(document.get("freeze_resolution"), "freeze_resolution")
    start = _utc(freeze.get("effective_from_utc"), "freeze_resolution.effective_from_utc")
    end = _utc(freeze.get("effective_until_utc"), "freeze_resolution.effective_until_utc")
    window = _integer(
        freeze.get("window_seconds"), "freeze_resolution.window_seconds", minimum=1
    )
    _equal(
        document.get("new_snapshot_cutoff_at_utc"),
        freeze.get("effective_from_utc"),
        "new_snapshot_cutoff_at_utc",
        P4ContractReason.FREEZE_VIOLATION,
    )
    if end != start + timedelta(seconds=window):
        _reject(
            P4ContractReason.FREEZE_VIOLATION,
            "freeze_resolution.effective_until_utc",
            "must close the exact half-open window",
        )
    expected = replan_request_fingerprint(document)
    _require_identity(
        document,
        fingerprint_field="request_fingerprint",
        identity_field="request_id",
        identity_prefix="replan-request-",
        expected_fingerprint=expected,
    )


def _require_solver_report(document: Mapping[str, object]) -> None:
    stages = _sequence(document.get("objective_stage_results"), "objective_stage_results")
    signatures = tuple(
        (
            _mapping(stage, "objective_stage_results[]").get("stage_index"),
            _mapping(stage, "objective_stage_results[]").get("objective_id"),
            _mapping(stage, "objective_stage_results[]").get("metric"),
            _mapping(stage, "objective_stage_results[]").get("sense"),
        )
        for stage in stages
    )
    _equal(
        signatures,
        _STAGE_SIGNATURES,
        "objective_stage_results",
        P4ContractReason.ORDERING_VIOLATION,
    )
    status = document.get("solver_status")
    if not isinstance(status, str) or status not in _STATUS_OUTCOMES:
        _reject(
            P4ContractReason.VERSION_MISMATCH,
            "solver_status",
            "is not a supported honest status",
        )
    if any(_mapping(stage, "objective_stage_results[]").get("status") != status for stage in stages):
        _reject(
            P4ContractReason.VERSION_MISMATCH,
            "objective_stage_results[].status",
            "must preserve the honest solver status",
        )
    outcome = _mapping(document.get("planning_run_outcome"), "planning_run_outcome")
    expected_state, expected_error = _STATUS_OUTCOMES[status]
    _equal(
        outcome.get("state"),
        expected_state,
        "planning_run_outcome.state",
        P4ContractReason.VERSION_MISMATCH,
    )
    product_error = outcome.get("product_error")
    if expected_error is None:
        _equal(
            product_error,
            None,
            "planning_run_outcome.product_error",
            P4ContractReason.VERSION_MISMATCH,
        )
    else:
        error = _mapping(product_error, "planning_run_outcome.product_error")
        _equal(
            error.get("category"),
            expected_error,
            "planning_run_outcome.product_error.category",
            P4ContractReason.VERSION_MISMATCH,
        )
        _equal(
            error.get("code"),
            expected_error,
            "planning_run_outcome.product_error.code",
            P4ContractReason.VERSION_MISMATCH,
        )
    expected = solver_report_fingerprint(document)
    _require_identity(
        document,
        fingerprint_field="report_fingerprint",
        identity_field="report_id",
        identity_prefix="solver-report-",
        expected_fingerprint=expected,
    )


def _assignment(value: object, field: str) -> Mapping[str, object] | None:
    if value is None:
        return None
    return _mapping(value, field)


def _require_change_report(document: Mapping[str, object]) -> None:
    operations = _sequence(document.get("operations"), "operations")
    _equal(
        document.get("operation_universe_count"),
        len(operations),
        "operation_universe_count",
        P4ContractReason.INCOMPLETE_CHANGE_REPORT,
    )
    operation_ids: list[str] = []
    unchanged = changed = resource_changes = absolute_shift = 0
    for index, value in enumerate(operations):
        operation = _mapping(value, f"operations[{index}]")
        operation_id = _text(operation.get("operation_id"), f"operations[{index}].operation_id")
        operation_ids.append(operation_id)
        classification = operation.get("classification")
        base = _assignment(operation.get("base_assignment"), "base_assignment")
        new = _assignment(operation.get("new_assignment"), "new_assignment")
        deltas = _mapping(operation.get("deltas"), "deltas")
        reasons = _sequence(operation.get("reasons"), "reasons")
        if not reasons:
            _reject(
                P4ContractReason.INCOMPLETE_CHANGE_REPORT,
                f"operations[{index}].reasons",
                "at least one evidence-backed reason is required",
            )
        for assignment in (base, new):
            if assignment is not None:
                _equal(
                    assignment.get("operation_id"),
                    operation_id,
                    f"operations[{index}].assignment.operation_id",
                    P4ContractReason.REFERENCE_MISMATCH,
                )
        shift = _integer(deltas.get("start_shift_seconds"), "start_shift_seconds")
        _equal(
            deltas.get("absolute_start_shift_seconds"),
            abs(shift),
            f"operations[{index}].deltas.absolute_start_shift_seconds",
            P4ContractReason.STABILITY_MISMATCH,
        )
        if classification == "UNCHANGED":
            if base is None or new is None or dict(base) != dict(new):
                _reject(
                    P4ContractReason.INCOMPLETE_CHANGE_REPORT,
                    f"operations[{index}]",
                    "UNCHANGED requires byte-equivalent assignments",
                )
            if any(
                deltas.get(field) not in (0, False)
                for field in (
                    "resource_changed",
                    "start_shift_seconds",
                    "absolute_start_shift_seconds",
                    "end_shift_seconds",
                    "duration_delta_seconds",
                )
            ):
                _reject(
                    P4ContractReason.STABILITY_MISMATCH,
                    f"operations[{index}].deltas",
                    "UNCHANGED deltas must be zero",
                )
            unchanged += 1
        elif classification == "CHANGED":
            if base is None or new is None or dict(base) == dict(new):
                _reject(
                    P4ContractReason.INCOMPLETE_CHANGE_REPORT,
                    f"operations[{index}]",
                    "CHANGED requires two distinct assignments",
                )
            changed += 1
            if deltas.get("resource_changed") is True:
                resource_changes += 1
            absolute_shift += abs(shift)
        elif classification == "ADDED":
            if base is not None or new is None:
                _reject(
                    P4ContractReason.INCOMPLETE_CHANGE_REPORT,
                    f"operations[{index}]",
                    "ADDED requires only a new assignment",
                )
        elif classification == "REMOVED_BY_FACT":
            if base is None or new is not None:
                _reject(
                    P4ContractReason.INCOMPLETE_CHANGE_REPORT,
                    f"operations[{index}]",
                    "REMOVED_BY_FACT requires only a base assignment",
                )
        else:
            _reject(
                P4ContractReason.VERSION_MISMATCH,
                f"operations[{index}].classification",
                "is unknown",
            )
    if operation_ids != sorted(set(operation_ids)):
        _reject(
            P4ContractReason.INCOMPLETE_CHANGE_REPORT,
            "operations",
            "operation universe must be sorted and unique",
        )
    stability = _mapping(document.get("stability"), "stability")
    expected = {
        "changed_existing_operations": changed,
        "resource_changes": resource_changes,
        "absolute_start_shift_seconds": absolute_shift,
        "unchanged_existing": unchanged,
        "comparable_existing": unchanged + changed,
    }
    for field, value in expected.items():
        _equal(
            stability.get(field),
            value,
            f"stability.{field}",
            P4ContractReason.STABILITY_MISMATCH,
        )
    ratio = _mapping(stability.get("unchanged_ratio"), "stability.unchanged_ratio")
    if unchanged + changed == 0:
        expected_ratio = {
            "status": "NOT_APPLICABLE_NO_COMPARABLE_OPERATION",
            "numerator": 0,
            "denominator": 0,
        }
    else:
        expected_ratio = {
            "status": "APPLICABLE",
            "numerator": unchanged,
            "denominator": unchanged + changed,
        }
    _equal(
        dict(ratio),
        expected_ratio,
        "stability.unchanged_ratio",
        P4ContractReason.STABILITY_MISMATCH,
    )
    expected_fingerprint = change_report_fingerprint(document)
    _require_identity(
        document,
        fingerprint_field="report_fingerprint",
        identity_field="report_id",
        identity_prefix="change-report-",
        expected_fingerprint=expected_fingerprint,
    )


def _require_schedule_version(document: Mapping[str, object]) -> None:
    _equal(
        document.get("content_fingerprint"),
        schedule_content_fingerprint(document),
        "content_fingerprint",
        P4ContractReason.IDENTITY_MISMATCH,
    )
    _equal(
        document.get("parent_schedule_version"),
        _mapping(document.get("lineage"), "lineage").get("base_schedule_version"),
        "lineage.base_schedule_version",
        P4ContractReason.REFERENCE_MISMATCH,
    )


def _require_simulation_manifest(document: Mapping[str, object]) -> None:
    _authority_scope(document)
    stream = _mapping(document.get("event_stream"), "event_stream")
    count = _integer(stream.get("event_count"), "event_stream.event_count", minimum=1)
    first = _integer(stream.get("first_position"), "event_stream.first_position", minimum=1)
    last = _integer(stream.get("last_position"), "event_stream.last_position", minimum=1)
    ids = _sequence(stream.get("ordered_event_ids"), "event_stream.ordered_event_ids")
    fingerprints = _sequence(
        stream.get("ordered_event_fingerprints"),
        "event_stream.ordered_event_fingerprints",
    )
    if count != len(ids) or count != len(fingerprints) or last - first + 1 != count:
        _reject(
            P4ContractReason.ORDERING_VIOLATION,
            "event_stream",
            "count, positions and ordered vectors diverge",
        )
    expected_stream = event_stream_fingerprint(fingerprints)
    _equal(
        stream.get("stream_fingerprint"),
        expected_stream,
        "event_stream.stream_fingerprint",
        P4ContractReason.IDENTITY_MISMATCH,
    )
    checkpoint = _mapping(document.get("checkpoint"), "checkpoint")
    _equal(
        checkpoint.get("last_applied_position"),
        last,
        "checkpoint.last_applied_position",
        P4ContractReason.ORDERING_VIOLATION,
    )
    _equal(
        checkpoint.get("prefix_fingerprint"),
        expected_stream,
        "checkpoint.prefix_fingerprint",
        P4ContractReason.IDENTITY_MISMATCH,
    )
    expected = simulation_manifest_fingerprint(document)
    _require_identity(
        document,
        fingerprint_field="manifest_fingerprint",
        identity_field="manifest_id",
        identity_prefix="execution-simulation-",
        expected_fingerprint=expected,
    )


def _require_export_manifest(document: Mapping[str, object]) -> None:
    files = _sequence(document.get("files"), "files")
    paths = tuple(_mapping(item, "files[]").get("path") for item in files)
    _equal(
        paths,
        _EXPORT_PATHS,
        "files[].path",
        P4ContractReason.ORDERING_VIOLATION,
    )
    expected = export_manifest_fingerprint(document)
    _require_identity(
        document,
        fingerprint_field="manifest_fingerprint",
        identity_field="package_id",
        identity_prefix="export-package-",
        expected_fingerprint=expected,
    )


def _require_export_job(document: Mapping[str, object]) -> None:
    _equal(
        document.get("job_fingerprint"),
        export_job_fingerprint(document),
        "job_fingerprint",
        P4ContractReason.IDENTITY_MISMATCH,
    )


def require_p4_document(document: Mapping[str, object]) -> str:
    """Apply version, isolation, canonical identity, and semantic prechecks."""

    version = p4_document_version(document)
    _equal(
        document.get("schema_set_version"),
        SCHEMA_SET_VERSION,
        "schema_set_version",
        P4ContractReason.VERSION_MISMATCH,
    )
    _equal(
        document.get("canonicalization_version"),
        CANONICALIZATION_VERSION,
        "canonicalization_version",
        P4ContractReason.VERSION_MISMATCH,
    )
    _require_simulation_boundary(document)
    if version == EXECUTION_EVENT_VERSION:
        _require_event(document)
    elif version == PLANNING_POLICY_VERSION:
        _require_policy(document)
    elif version == REPLAN_REQUEST_VERSION:
        _require_replan(document)
    elif version == SOLVER_REPORT_VERSION:
        _require_solver_report(document)
    elif version == CHANGE_REPORT_VERSION:
        _require_change_report(document)
    elif version == SCHEDULE_VERSION:
        _require_schedule_version(document)
    elif version == EXECUTION_SIMULATION_MANIFEST_VERSION:
        _require_simulation_manifest(document)
    elif version == EXPORT_MANIFEST_VERSION:
        _require_export_manifest(document)
    elif version == EXPORT_JOB_VERSION:
        _require_export_job(document)
    return version


def validate_p4_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Cross-check all nine P4 samples without executing any business behavior."""

    expected_versions = set(_VERSION_FIELDS.values())
    if set(documents) != expected_versions:
        _reject(
            P4ContractReason.UNKNOWN_DOCUMENT,
            "bundle",
            "must contain exactly the nine P4 document versions",
        )
    for version, document in documents.items():
        _equal(
            require_p4_document(document),
            version,
            f"bundle.{version}",
            P4ContractReason.VERSION_MISMATCH,
        )

    event = documents[EXECUTION_EVENT_VERSION]
    policy = documents[PLANNING_POLICY_VERSION]
    request = documents[REPLAN_REQUEST_VERSION]
    solver = documents[SOLVER_REPORT_VERSION]
    change = documents[CHANGE_REPORT_VERSION]
    schedule = documents[SCHEDULE_VERSION]
    simulation = documents[EXECUTION_SIMULATION_MANIFEST_VERSION]
    manifest = documents[EXPORT_MANIFEST_VERSION]
    job = documents[EXPORT_JOB_VERSION]

    policy_fingerprint = contract_fingerprint(policy)
    freeze_fingerprint = freeze_policy_fingerprint(
        _mapping(policy.get("freeze_policy"), "policy.freeze_policy")
    )
    event_id = event.get("event_id")
    event_fingerprint = event.get("event_fingerprint")
    stream_fingerprint = event_stream_fingerprint([event_fingerprint])
    request_fingerprint = request.get("request_fingerprint")
    solver_fingerprint = solver.get("report_fingerprint")
    change_fingerprint = change.get("report_fingerprint")
    content_fingerprint = schedule.get("content_fingerprint")

    request_policy = _mapping(request.get("planning_policy"), "request.planning_policy")
    _equal(
        request_policy.get("policy_fingerprint"),
        policy_fingerprint,
        "request.planning_policy.policy_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(request.get("freeze_resolution"), "request.freeze_resolution").get(
            "freeze_policy_fingerprint"
        ),
        freeze_fingerprint,
        "request.freeze_resolution.freeze_policy_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    request_stream = _mapping(request.get("event_stream"), "request.event_stream")
    _equal(
        request_stream.get("event_ids"),
        [event_id],
        "request.event_stream.event_ids",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        request_stream.get("event_fingerprints"),
        [event_fingerprint],
        "request.event_stream.event_fingerprints",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        request_stream.get("stream_fingerprint"),
        stream_fingerprint,
        "request.event_stream.stream_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )

    request_reference = _mapping(solver.get("replan_request"), "solver.replan_request")
    _equal(
        request_reference.get("request_fingerprint"),
        request_fingerprint,
        "solver.replan_request.request_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(solver.get("policy"), "solver.policy").get("policy_fingerprint"),
        policy_fingerprint,
        "solver.policy.policy_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )

    change_lineage = _mapping(change.get("lineage"), "change.lineage")
    _equal(
        _mapping(change_lineage.get("replan_request"), "change.replan_request").get(
            "request_fingerprint"
        ),
        request_fingerprint,
        "change.lineage.replan_request.request_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(change_lineage.get("solver_report"), "change.solver_report").get(
            "fingerprint"
        ),
        solver_fingerprint,
        "change.lineage.solver_report.fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(change.get("new_schedule_version"), "change.new_schedule_version").get(
            "content_fingerprint"
        ),
        content_fingerprint,
        "change.new_schedule_version.content_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )

    schedule_lineage = _mapping(schedule.get("lineage"), "schedule.lineage")
    _equal(
        _mapping(schedule_lineage.get("replan_request"), "schedule.replan_request").get(
            "request_fingerprint"
        ),
        request_fingerprint,
        "schedule.lineage.replan_request.request_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(schedule_lineage.get("change_report"), "schedule.change_report").get(
            "report_fingerprint"
        ),
        change_fingerprint,
        "schedule.lineage.change_report.report_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(schedule_lineage.get("solver_report"), "schedule.solver_report").get(
            "fingerprint"
        ),
        solver_fingerprint,
        "schedule.lineage.solver_report.fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )

    simulation_stream = _mapping(simulation.get("event_stream"), "simulation.event_stream")
    _equal(
        simulation_stream.get("ordered_event_ids"),
        [event_id],
        "simulation.event_stream.ordered_event_ids",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        simulation_stream.get("stream_fingerprint"),
        stream_fingerprint,
        "simulation.event_stream.stream_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )
    _equal(
        _mapping(simulation.get("planning_policy"), "simulation.policy").get(
            "policy_fingerprint"
        ),
        policy_fingerprint,
        "simulation.planning_policy.policy_fingerprint",
        P4ContractReason.REFERENCE_MISMATCH,
    )

    for owner, document in (("manifest", manifest), ("job", job)):
        _equal(
            _mapping(document.get("change_report"), f"{owner}.change_report").get(
                "report_fingerprint"
            ),
            change_fingerprint,
            f"{owner}.change_report.report_fingerprint",
            P4ContractReason.REFERENCE_MISMATCH,
        )
        _equal(
            _mapping(document.get("schedule_version"), f"{owner}.schedule_version").get(
                "content_fingerprint"
            ),
            content_fingerprint,
            f"{owner}.schedule_version.content_fingerprint",
            P4ContractReason.REFERENCE_MISMATCH,
        )


__all__ = [
    "CANONICALIZATION_VERSION",
    "CHANGE_REPORT_VERSION",
    "EXECUTION_EVENT_VERSION",
    "EXECUTION_SIMULATION_MANIFEST_VERSION",
    "EXPORT_JOB_VERSION",
    "EXPORT_MANIFEST_VERSION",
    "PLANNING_POLICY_VERSION",
    "P4ContractError",
    "P4ContractReason",
    "REPLAN_REQUEST_VERSION",
    "SCHEMA_SET_VERSION",
    "SCHEDULE_VERSION",
    "SOLVER_REPORT_VERSION",
    "canonical_contract_bytes",
    "change_report_fingerprint",
    "contract_fingerprint",
    "event_stream_fingerprint",
    "execution_event_fingerprint",
    "export_job_fingerprint",
    "export_manifest_fingerprint",
    "freeze_policy_fingerprint",
    "p4_document_version",
    "replan_request_fingerprint",
    "require_p4_document",
    "schedule_content_fingerprint",
    "simulation_manifest_fingerprint",
    "solver_report_fingerprint",
    "validate_p4_bundle",
]
