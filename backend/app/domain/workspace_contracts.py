"""Pure P3 workspace carrier fingerprints and fail-closed prechecks.

This module deliberately contains no repository, API, worker, authorization, or
state-transition execution. JSON Schema remains the shape authority; these
prechecks bind canonical fingerprints and cross-document invariants that JSON
Schema cannot express by value equality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from hashlib import sha256
import json
from typing import Literal, TypedDict, cast

from app.domain.state_machines.contracts import (
    StateMachineName,
    states_for,
    transitions_for,
)


SCHEMA_SET_VERSION = "2.6.0"
CANONICALIZATION_VERSION = "canonical-json.v1"


class WorkspaceControlReason(StrEnum):
    """Module-local control reasons; these are not global product error codes."""

    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    EXPORT_FAILED = "EXPORT_FAILED"


class WorkspaceContractError(ValueError):
    """A carrier failed a pure, side-effect-free workspace precheck."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"{field}: {message}")


class VersionReference(TypedDict):
    schedule_version_id: str
    state: str
    content_fingerprint: str


class ScheduleVersionDocument(TypedDict):
    schedule_version_version: Literal["schedule-version.v1"]
    schema_set_version: Literal["2.6.0"]
    canonicalization_version: Literal["canonical-json.v1"]
    schedule_version_id: str
    state: str
    content: dict[str, object]
    content_fingerprint: str


class WorkspaceQueryDocument(TypedDict):
    workspace_query_version: Literal["workspace-query.v1"]
    schema_set_version: Literal["2.6.0"]
    canonicalization_version: Literal["canonical-json.v1"]
    query_fingerprint: str


class WorkspaceCommandDocument(TypedDict):
    workspace_command_version: Literal["workspace-command.v1"]
    schema_set_version: Literal["2.6.0"]
    canonicalization_version: Literal["canonical-json.v1"]
    command_type: str
    request_fingerprint: str


_VERSION_FIELDS: Mapping[str, str] = {
    "schedule_version_version": "schedule-version.v1",
    "workspace_query_version": "workspace-query.v1",
    "workspace_command_version": "workspace-command.v1",
    "schedule_version_comparison_version": "schedule-version-comparison.v1",
    "audit_event_version": "audit-event.v1",
    "publication_result_version": "publication-result.v1",
    "export_job_version": "export-job.v1",
}

_QUERY_FINGERPRINT_FIELDS = (
    "workspace_query_version",
    "schema_set_version",
    "canonicalization_version",
    "query_kind",
    "data_plane",
    "environment",
    "synthetic",
    "synthetic_provenance",
    "resource",
    "view",
    "schedule_version_precondition",
    "sort",
    "filters",
    "page",
)

_COMMAND_FINGERPRINT_FIELDS = (
    "workspace_command_version",
    "schema_set_version",
    "canonicalization_version",
    "command_type",
    "source_id",
    "expected_state",
    "expected_content_fingerprint",
    "data_plane",
    "environment",
    "synthetic",
    "synthetic_provenance",
    "target",
    "reason",
    "payload",
)

_COMMAND_CAPABILITIES: Mapping[str, str] = {
    "MOVE_OPERATION": "edit",
    "ASSIGN_RESOURCE": "edit",
    "SET_LOCK": "lock",
    "REMOVE_LOCK": "lock",
    "SUBMIT_FOR_REVIEW": "edit",
    "APPROVE": "approve",
    "REJECT": "reject",
    "PUBLISH": "publish",
    "REQUEST_EXPORT": "export",
    "RETRY_EXPORT": "export",
    "CANCEL_EXPORT": "export",
}

_FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "authorization",
        "authorization_header",
        "cookie",
        "credential",
        "credentials",
        "database_dsn",
        "password",
        "raw_sql",
        "secret",
        "stack_trace",
        "token",
    }
)


def canonical_workspace_bytes(document: Mapping[str, object]) -> bytes:
    """Return finite, deterministic canonical-json.v1 bytes."""

    try:
        rendered = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise WorkspaceContractError(
            "$", "document must be finite and JSON-compatible"
        ) from error
    return rendered.encode("utf-8")


def workspace_fingerprint(document: Mapping[str, object]) -> str:
    """Fingerprint a complete canonical mapping without hidden exclusions."""

    return f"sha256:{sha256(canonical_workspace_bytes(document)).hexdigest()}"


def _projection(
    document: Mapping[str, object], fields: Sequence[str]
) -> dict[str, object]:
    missing = [field for field in fields if field not in document]
    optional = {"synthetic_provenance"}
    required_missing = [field for field in missing if field not in optional]
    if required_missing:
        raise WorkspaceContractError(
            required_missing[0], "field is required by fingerprint projection"
        )
    return {field: document[field] for field in fields if field in document}


def schedule_content_fingerprint(document: Mapping[str, object]) -> str:
    content = document.get("content")
    if not isinstance(content, Mapping):
        raise WorkspaceContractError("content", "must be an object")
    return workspace_fingerprint(cast(Mapping[str, object], content))


def workspace_query_fingerprint(document: Mapping[str, object]) -> str:
    return workspace_fingerprint(_projection(document, _QUERY_FINGERPRINT_FIELDS))


def workspace_command_fingerprint(document: Mapping[str, object]) -> str:
    return workspace_fingerprint(_projection(document, _COMMAND_FINGERPRINT_FIELDS))


def comparison_fingerprint(document: Mapping[str, object]) -> str:
    excluded = {"comparison_id", "comparison_fingerprint", "generated_at_utc"}
    return workspace_fingerprint(
        {key: value for key, value in document.items() if key not in excluded}
    )


def publication_result_fingerprint(document: Mapping[str, object]) -> str:
    return workspace_fingerprint(
        {key: value for key, value in document.items() if key != "result_fingerprint"}
    )


def export_job_fingerprint(document: Mapping[str, object]) -> str:
    return workspace_fingerprint(
        {key: value for key, value in document.items() if key != "job_fingerprint"}
    )


def workspace_document_version(document: Mapping[str, object]) -> str:
    """Return the sole supported P3 document discriminator."""

    found = [
        expected
        for field, expected in _VERSION_FIELDS.items()
        if document.get(field) == expected
    ]
    if len(found) != 1:
        raise WorkspaceContractError(
            "$", "exactly one supported workspace document version is required"
        )
    return found[0]


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WorkspaceContractError(field, "must be an object")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkspaceContractError(field, "must be a non-empty string")
    return value


def _require_equal(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        raise WorkspaceContractError(field, "does not match canonical projection")


def _check_no_secret_keys(value: object, field: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()
            if key in _FORBIDDEN_SECRET_KEYS:
                raise WorkspaceContractError(
                    f"{field}.{raw_key}", "raw secret-bearing field is forbidden"
                )
            _check_no_secret_keys(nested, f"{field}.{raw_key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _check_no_secret_keys(nested, f"{field}[{index}]")


def _precheck_schedule(document: Mapping[str, object]) -> None:
    if document.get("state") not in states_for(StateMachineName.SCHEDULE_VERSION):
        raise WorkspaceContractError("state", "unknown ScheduleVersion state")
    _require_equal(
        document.get("content_fingerprint"),
        schedule_content_fingerprint(document),
        "content_fingerprint",
    )
    lineage = _mapping(document.get("lineage"), "lineage")
    validation = _mapping(document.get("validation"), "validation")
    _require_equal(
        validation.get("validation_report"),
        lineage.get("validation_report"),
        "validation.validation_report",
    )


def _precheck_query(document: Mapping[str, object]) -> None:
    _require_equal(
        document.get("query_fingerprint"),
        workspace_query_fingerprint(document),
        "query_fingerprint",
    )


def _precheck_command(document: Mapping[str, object]) -> None:
    command_type = _text(document.get("command_type"), "command_type")
    capability = _COMMAND_CAPABILITIES.get(command_type)
    if capability is None:
        raise WorkspaceContractError("command_type", "unsupported P3 command")
    _require_equal(
        document.get("required_capability"), capability, "required_capability"
    )
    _require_equal(
        document.get("request_fingerprint"),
        workspace_command_fingerprint(document),
        "request_fingerprint",
    )
    forbidden_authority_fields = {
        "actor",
        "actor_ref",
        "capabilities",
        "principal",
        "role",
    }
    overlap = forbidden_authority_fields.intersection(document)
    if overlap:
        raise WorkspaceContractError(
            sorted(overlap)[0], "client body must not claim authorization authority"
        )


def _precheck_comparison(document: Mapping[str, object]) -> None:
    base = _mapping(document.get("base_version"), "base_version")
    compared = _mapping(document.get("compared_version"), "compared_version")
    if base.get("schedule_version_id") == compared.get("schedule_version_id"):
        raise WorkspaceContractError(
            "compared_version.schedule_version_id", "must differ from base version"
        )
    _require_equal(
        document.get("comparison_fingerprint"),
        comparison_fingerprint(document),
        "comparison_fingerprint",
    )
    deltas = document.get("operation_deltas")
    summary = _mapping(document.get("summary"), "summary")
    if not isinstance(deltas, list):
        raise WorkspaceContractError("operation_deltas", "must be an array")
    changed = sum(
        1
        for delta in deltas
        if isinstance(delta, Mapping) and delta.get("change_kind") != "UNCHANGED"
    )
    _require_equal(
        summary.get("changed_operation_count"),
        changed,
        "summary.changed_operation_count",
    )


def _precheck_audit(document: Mapping[str, object]) -> None:
    request_fingerprint = document.get("request_fingerprint")
    idempotency = document.get("idempotency_reference")
    if request_fingerprint is not None and idempotency is not None:
        reference = _mapping(idempotency, "idempotency_reference")
        _require_equal(
            reference.get("request_fingerprint"),
            request_fingerprint,
            "idempotency_reference.request_fingerprint",
        )
    _check_no_secret_keys(document)


def _precheck_publication(document: Mapping[str, object]) -> None:
    source = _mapping(
        document.get("source_approved_version"), "source_approved_version"
    )
    published = _mapping(document.get("published_version"), "published_version")
    for field in ("schedule_version_id", "content_fingerprint"):
        _require_equal(
            published.get(field), source.get(field), f"published_version.{field}"
        )
    previous = document.get("previous_current_version")
    superseded = document.get("superseded_version")
    if (previous is None) != (superseded is None):
        raise WorkspaceContractError(
            "superseded_version", "must be present exactly when previous current exists"
        )
    if previous is not None and superseded is not None:
        previous_ref = _mapping(previous, "previous_current_version")
        superseded_ref = _mapping(superseded, "superseded_version")
        for field in ("schedule_version_id", "content_fingerprint"):
            _require_equal(
                superseded_ref.get(field),
                previous_ref.get(field),
                f"superseded_version.{field}",
            )
    _require_equal(
        document.get("result_fingerprint"),
        publication_result_fingerprint(document),
        "result_fingerprint",
    )


def _precheck_export_job(document: Mapping[str, object]) -> None:
    if document.get("state") not in states_for(StateMachineName.EXPORT_JOB):
        raise WorkspaceContractError("state", "unknown ExportJob state")
    schedule = _mapping(document.get("schedule_version"), "schedule_version")
    _require_equal(schedule.get("state"), "PUBLISHED", "schedule_version.state")
    _require_equal(
        document.get("job_fingerprint"),
        export_job_fingerprint(document),
        "job_fingerprint",
    )


def require_workspace_document(document: Mapping[str, object]) -> str:
    """Apply version, canonical fingerprint, state, and no-secret prechecks."""

    version = workspace_document_version(document)
    _require_equal(
        document.get("schema_set_version"), SCHEMA_SET_VERSION, "schema_set_version"
    )
    _require_equal(
        document.get("canonicalization_version"),
        CANONICALIZATION_VERSION,
        "canonicalization_version",
    )
    if version == "schedule-version.v1":
        _precheck_schedule(document)
    elif version == "workspace-query.v1":
        _precheck_query(document)
    elif version == "workspace-command.v1":
        _precheck_command(document)
    elif version == "schedule-version-comparison.v1":
        _precheck_comparison(document)
    elif version == "audit-event.v1":
        _precheck_audit(document)
    elif version == "publication-result.v1":
        _precheck_publication(document)
    elif version == "export-job.v1":
        _precheck_export_job(document)
    _check_no_secret_keys(document)
    return version


def state_contract_evidence() -> dict[str, object]:
    """Return the existing state sets/pairs without adding or executing a pair."""

    schedule_pairs = sorted(
        [list(pair) for pair in transitions_for(StateMachineName.SCHEDULE_VERSION)]
    )
    export_pairs = sorted(
        [list(pair) for pair in transitions_for(StateMachineName.EXPORT_JOB)]
    )
    return {
        "schedule_states": sorted(states_for(StateMachineName.SCHEDULE_VERSION)),
        "schedule_pairs": schedule_pairs,
        "export_states": sorted(states_for(StateMachineName.EXPORT_JOB)),
        "export_pairs": export_pairs,
    }


__all__ = [
    "CANONICALIZATION_VERSION",
    "SCHEMA_SET_VERSION",
    "ScheduleVersionDocument",
    "VersionReference",
    "WorkspaceCommandDocument",
    "WorkspaceContractError",
    "WorkspaceControlReason",
    "WorkspaceQueryDocument",
    "canonical_workspace_bytes",
    "comparison_fingerprint",
    "export_job_fingerprint",
    "publication_result_fingerprint",
    "require_workspace_document",
    "schedule_content_fingerprint",
    "state_contract_evidence",
    "workspace_command_fingerprint",
    "workspace_document_version",
    "workspace_fingerprint",
    "workspace_query_fingerprint",
]
