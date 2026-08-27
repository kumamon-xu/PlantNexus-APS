"""Pure, deterministic ExecutionEvent to canonical-fact projection.

The projector interprets only the approved P4 Simulation carrier.  It has no
database, solver, ScheduleVersion, freeze-policy, or wall-clock dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NoReturn, cast

from app.domain.canonical_records import COLLECTION_ID_FIELDS
from app.domain.execution_contracts import (
    P4ContractError,
    event_stream_fingerprint,
    require_p4_document,
)
from app.domain.types import ContractValueError, parse_utc_instant

PROJECTOR_RECORD_VERSION = "execution-fact-projector.v1"
PROJECTOR_SOURCE_SYSTEM = "plantnexus-execution-fact-projector"
PROJECTOR_SOURCE_VERSION = "1.0.0"
BASE_SNAPSHOT_SOURCE = "plantnexus-previous-snapshot"
EVENT_STREAM_SOURCE = "plantnexus-execution-event-prefix"
EVENT_AUTHORITY_SOURCE = "plantnexus-execution-event-authority"

_EVENT_ROOT_FIELDS = {
    "execution_event_version",
    "schema_set_version",
    "canonicalization_version",
    "event_id",
    "event_type",
    "data_plane",
    "environment",
    "factory_id",
    "planning_scope_id",
    "authority",
    "source_stream",
    "source_position",
    "occurred_at_utc",
    "received_at_utc",
    "entity_refs",
    "payload",
    "synthetic",
    "synthetic_provenance",
    "production_binding",
    "correlation_id",
    "event_fingerprint",
}
_PAYLOAD_FIELDS = {
    "OPERATION_STARTED": {
        "kind",
        "operation_id",
        "resource_id",
        "actual_start_at_utc",
    },
    "OPERATION_COMPLETED": {
        "kind",
        "operation_id",
        "resource_id",
        "actual_start_at_utc",
        "actual_end_at_utc",
    },
    "MACHINE_UNAVAILABLE": {
        "kind",
        "resource_id",
        "unavailable_from_utc",
        "unavailable_until_utc",
    },
    "MACHINE_RECOVERED": {
        "kind",
        "resource_id",
        "available_from_utc",
    },
    "MATERIAL_READY": {"kind", "material_id", "available_at_utc"},
    "MATERIAL_DELAYED": {"kind", "material_id", "available_at_utc"},
    "PROCESSING_DURATION_CHANGED": {
        "kind",
        "operation_id",
        "final_duration_seconds",
        "duration_source",
        "source_version",
    },
    "PROCESSING_REMAINING_CHANGED": {
        "kind",
        "operation_id",
        "remaining_seconds",
        "as_of_utc",
    },
    "URGENT_DEMAND_RECEIVED": {
        "kind",
        "demand_order_id",
        "quantity",
        "due_at_utc",
        "priority_weight",
        "priority_source",
    },
    "LOCK_CREATED": {
        "kind",
        "lock_id",
        "operation_id",
        "lock_type",
        "resource_id",
        "start_at_utc",
        "end_at_utc",
        "policy_reference",
    },
    "LOCK_RELEASED": {"kind", "lock_id", "release_reason", "policy_reference"},
}


class ProjectionFailure(StrEnum):
    """Stable failure reasons at the business projection boundary."""

    INVALID_EVENT = "INVALID_EVENT"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    ORDERING_VIOLATION = "ORDERING_VIOLATION"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    FACT_CONFLICT = "FACT_CONFLICT"
    TERMINAL_REGRESSION = "TERMINAL_REGRESSION"
    URGENT_IMPORT_REQUIRED = "URGENT_IMPORT_REQUIRED"
    URGENT_IMPORT_MISMATCH = "URGENT_IMPORT_MISMATCH"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ExecutionFactProjectionError(ValueError):
    """A deterministic, sanitized projection rejection."""

    def __init__(
        self,
        reason: ProjectionFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value} at {field}: {message}")


@dataclass(frozen=True, slots=True)
class ProjectionScope:
    factory_id: str
    planning_scope_id: str
    authority_id: str
    stream_id: str
    stream_version: str


@dataclass(frozen=True, slots=True)
class UrgentPriorityFact:
    event_id: str
    demand_order_id: str
    priority_weight: int
    source_system: str
    source_version: str
    source_record_id: str


@dataclass(frozen=True, slots=True)
class ProjectedFactBatch:
    document: dict[str, object]
    from_position: int
    through_position: int
    event_ids: tuple[str, ...]
    event_fingerprints: tuple[str, ...]
    stream_fingerprint: str
    priority_facts: tuple[UrgentPriorityFact, ...]


def _reject(reason: ProjectionFailure, field: str, message: str) -> NoReturn:
    raise ExecutionFactProjectionError(reason, field=field, message=message)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(ProjectionFailure.INVALID_EVENT, field, "must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _reject(ProjectionFailure.INVALID_EVENT, field, "must be an array")
    return cast(Sequence[object], value)


def _text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > 768
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _reject(
            ProjectionFailure.INVALID_EVENT,
            field,
            "must be bounded non-empty text without control characters",
        )
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _reject(
            ProjectionFailure.INVALID_EVENT,
            field,
            f"must be an integer greater than or equal to {minimum}",
        )
    return value


def _utc(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        return parse_utc_instant(text)
    except ContractValueError:
        _reject(
            ProjectionFailure.INVALID_EVENT,
            field,
            "must be a canonical second-precision UTC instant ending in Z",
        )


def _exact_fields(
    document: Mapping[str, object], expected: set[str], field: str
) -> None:
    if set(document) != expected:
        _reject(
            ProjectionFailure.INVALID_EVENT,
            field,
            "field set does not match the approved carrier",
        )


def _source_reference(value: object, field: str) -> Mapping[str, object]:
    source = _mapping(value, field)
    _exact_fields(
        source, {"source_system", "source_version", "source_record_id"}, field
    )
    for name in ("source_system", "source_version", "source_record_id"):
        _text(source.get(name), f"{field}.{name}")
    return source


def _artifact_reference(value: object, field: str) -> None:
    reference = _mapping(value, field)
    _exact_fields(reference, {"document_version", "artifact_id", "fingerprint"}, field)
    _text(reference.get("document_version"), f"{field}.document_version")
    _text(reference.get("artifact_id"), f"{field}.artifact_id")
    fingerprint = _text(reference.get("fingerprint"), f"{field}.fingerprint")
    if len(fingerprint) != 71 or not fingerprint.startswith("sha256:"):
        _reject(
            ProjectionFailure.INVALID_EVENT, f"{field}.fingerprint", "must be SHA-256"
        )


def _expected_entity_references(
    event_type: str, payload: Mapping[str, object]
) -> set[tuple[str, str]]:
    if event_type in {"OPERATION_STARTED", "OPERATION_COMPLETED"}:
        return {
            ("OPERATION", _text(payload.get("operation_id"), "payload.operation_id")),
            ("RESOURCE", _text(payload.get("resource_id"), "payload.resource_id")),
        }
    if event_type in {"PROCESSING_DURATION_CHANGED", "PROCESSING_REMAINING_CHANGED"}:
        return {
            ("OPERATION", _text(payload.get("operation_id"), "payload.operation_id"))
        }
    if event_type in {"MACHINE_UNAVAILABLE", "MACHINE_RECOVERED"}:
        return {("RESOURCE", _text(payload.get("resource_id"), "payload.resource_id"))}
    if event_type in {"MATERIAL_READY", "MATERIAL_DELAYED"}:
        return {("MATERIAL", _text(payload.get("material_id"), "payload.material_id"))}
    if event_type == "URGENT_DEMAND_RECEIVED":
        return {
            (
                "DEMAND_ORDER",
                _text(payload.get("demand_order_id"), "payload.demand_order_id"),
            )
        }
    if event_type == "LOCK_CREATED":
        return {
            ("OPERATION", _text(payload.get("operation_id"), "payload.operation_id")),
            ("RESOURCE", _text(payload.get("resource_id"), "payload.resource_id")),
            ("OPERATION_LOCK", _text(payload.get("lock_id"), "payload.lock_id")),
        }
    return {("OPERATION_LOCK", _text(payload.get("lock_id"), "payload.lock_id"))}


def _validate_payload_times(
    event_type: str,
    payload: Mapping[str, object],
    occurred: datetime,
) -> None:
    if event_type == "OPERATION_STARTED":
        if (
            _utc(payload.get("actual_start_at_utc"), "payload.actual_start_at_utc")
            > occurred
        ):
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.actual_start_at_utc",
                "cannot follow event occurrence",
            )
    elif event_type == "OPERATION_COMPLETED":
        start = _utc(payload.get("actual_start_at_utc"), "payload.actual_start_at_utc")
        end = _utc(payload.get("actual_end_at_utc"), "payload.actual_end_at_utc")
        if start >= end or end > occurred:
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.actual_end_at_utc",
                "must follow start and not follow occurrence",
            )
    elif event_type == "MACHINE_UNAVAILABLE":
        start = _utc(
            payload.get("unavailable_from_utc"), "payload.unavailable_from_utc"
        )
        if start > occurred:
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.unavailable_from_utc",
                "cannot follow event occurrence",
            )
        until_value = payload.get("unavailable_until_utc")
        if (
            until_value is not None
            and _utc(until_value, "payload.unavailable_until_utc") <= start
        ):
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.unavailable_until_utc",
                "must follow unavailable_from_utc",
            )
    elif event_type == "MACHINE_RECOVERED":
        if (
            _utc(payload.get("available_from_utc"), "payload.available_from_utc")
            > occurred
        ):
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.available_from_utc",
                "cannot follow event occurrence",
            )
    elif event_type == "MATERIAL_READY":
        if _utc(payload.get("available_at_utc"), "payload.available_at_utc") > occurred:
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.available_at_utc",
                "ready fact cannot be future-dated",
            )
    elif event_type == "PROCESSING_REMAINING_CHANGED":
        if _utc(payload.get("as_of_utc"), "payload.as_of_utc") > occurred:
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.as_of_utc",
                "cannot follow event occurrence",
            )
    elif event_type == "LOCK_CREATED":
        start = _utc(payload.get("start_at_utc"), "payload.start_at_utc")
        end = _utc(payload.get("end_at_utc"), "payload.end_at_utc")
        if start >= end:
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.end_at_utc",
                "must follow lock start",
            )


def validate_execution_event(
    document: Mapping[str, object], *, scope: ProjectionScope
) -> None:
    """Apply strict runtime checks before any fact interpretation."""

    _exact_fields(document, _EVENT_ROOT_FIELDS, "event")
    try:
        observed_version = require_p4_document(document)
    except (P4ContractError, KeyError, TypeError, ValueError) as error:
        raise ExecutionFactProjectionError(
            ProjectionFailure.INVALID_EVENT,
            field=getattr(error, "field", "event"),
            message="ExecutionEvent semantic identity is invalid",
        ) from error
    if observed_version != "execution-event.v1":
        _reject(
            ProjectionFailure.INVALID_EVENT,
            "execution_event_version",
            "unsupported version",
        )
    expected_root = {
        "execution_event_version": "execution-event.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "data_plane": "SIMULATION",
        "synthetic": True,
        "production_binding": False,
    }
    if any(document.get(field) != value for field, value in expected_root.items()):
        _reject(
            ProjectionFailure.INVALID_EVENT,
            "event",
            "version or Simulation boundary mismatch",
        )
    event_type = _text(document.get("event_type"), "event_type")
    if event_type not in _PAYLOAD_FIELDS:
        _reject(ProjectionFailure.INVALID_EVENT, "event_type", "unsupported event type")
    payload = _mapping(document.get("payload"), "payload")
    _exact_fields(payload, _PAYLOAD_FIELDS[event_type], "payload")
    if payload.get("kind") != event_type:
        _reject(
            ProjectionFailure.INVALID_EVENT, "payload.kind", "must equal event_type"
        )

    authority = _mapping(document.get("authority"), "authority")
    _exact_fields(
        authority,
        {
            "authority_version",
            "authority_id",
            "authority_scope",
            "source",
            "decision",
            "production_binding",
        },
        "authority",
    )
    if (
        authority.get("authority_version") != "execution-event-authority.v1"
        or authority.get("decision") != "AUTHORIZED_SIMULATION_SOURCE"
        or authority.get("production_binding") is not False
    ):
        _reject(
            ProjectionFailure.AUTHORITY_MISMATCH,
            "authority",
            "authority decision is not approved for Simulation",
        )
    _source_reference(authority.get("source"), "authority.source")
    stream = _mapping(document.get("source_stream"), "source_stream")
    _exact_fields(
        stream, {"stream_id", "stream_version", "authority_id"}, "source_stream"
    )
    observed_scope = (
        document.get("factory_id"),
        document.get("planning_scope_id"),
        authority.get("authority_id"),
        stream.get("stream_id"),
        stream.get("stream_version"),
    )
    expected_scope = (
        scope.factory_id,
        scope.planning_scope_id,
        scope.authority_id,
        scope.stream_id,
        scope.stream_version,
    )
    if (
        observed_scope != expected_scope
        or stream.get("authority_id") != scope.authority_id
    ):
        _reject(
            ProjectionFailure.AUTHORITY_MISMATCH,
            "authority/source_stream",
            "event is outside the selected projection scope",
        )
    if (
        authority.get("authority_scope")
        != f"SIMULATION/{scope.factory_id}/{scope.planning_scope_id}"
    ):
        _reject(
            ProjectionFailure.AUTHORITY_MISMATCH,
            "authority.authority_scope",
            "scope string is not canonical",
        )

    provenance = _mapping(document.get("synthetic_provenance"), "synthetic_provenance")
    _exact_fields(
        provenance,
        {
            "scenario_id",
            "scenario_version",
            "factory_profile_id",
            "profile_version",
            "generator_id",
            "generator_version",
            "simulator_id",
            "simulator_version",
            "seed",
        },
        "synthetic_provenance",
    )
    for name in (
        "scenario_id",
        "scenario_version",
        "factory_profile_id",
        "profile_version",
        "generator_id",
        "generator_version",
        "simulator_id",
        "simulator_version",
    ):
        _text(provenance.get(name), f"synthetic_provenance.{name}")
    _integer(provenance.get("seed"), "synthetic_provenance.seed")
    _integer(document.get("source_position"), "source_position", minimum=1)
    occurred = _utc(document.get("occurred_at_utc"), "occurred_at_utc")
    if _utc(document.get("received_at_utc"), "received_at_utc") < occurred:
        _reject(
            ProjectionFailure.ORDERING_VIOLATION,
            "received_at_utc",
            "cannot precede occurred_at_utc",
        )

    references: list[tuple[str, str]] = []
    for index, value in enumerate(
        _sequence(document.get("entity_refs"), "entity_refs")
    ):
        reference = _mapping(value, f"entity_refs[{index}]")
        _exact_fields(reference, {"entity_type", "entity_id"}, f"entity_refs[{index}]")
        references.append(
            (
                _text(
                    reference.get("entity_type"), f"entity_refs[{index}].entity_type"
                ),
                _text(reference.get("entity_id"), f"entity_refs[{index}].entity_id"),
            )
        )
    expected_references = _expected_entity_references(event_type, payload)
    if references != sorted(expected_references):
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "entity_refs",
            "must exactly match sorted payload references",
        )

    if event_type == "PROCESSING_DURATION_CHANGED":
        _integer(
            payload.get("final_duration_seconds"),
            "payload.final_duration_seconds",
            minimum=1,
        )
        _text(payload.get("duration_source"), "payload.duration_source")
        _text(payload.get("source_version"), "payload.source_version")
    elif event_type == "PROCESSING_REMAINING_CHANGED":
        _integer(payload.get("remaining_seconds"), "payload.remaining_seconds")
    elif event_type == "URGENT_DEMAND_RECEIVED":
        _integer(payload.get("quantity"), "payload.quantity", minimum=1)
        _integer(payload.get("priority_weight"), "payload.priority_weight", minimum=1)
        _utc(payload.get("due_at_utc"), "payload.due_at_utc")
        _source_reference(payload.get("priority_source"), "payload.priority_source")
    elif event_type == "LOCK_CREATED":
        if payload.get("lock_type") not in {"HARD", "SOFT"}:
            _reject(
                ProjectionFailure.INVALID_EVENT,
                "payload.lock_type",
                "unsupported lock type",
            )
        _artifact_reference(payload.get("policy_reference"), "payload.policy_reference")
    elif event_type == "LOCK_RELEASED":
        if payload.get("release_reason") not in {
            "POLICY_REEVALUATION",
            "FACT_SUPERSEDED",
            "OPERATION_COMPLETED",
        }:
            _reject(
                ProjectionFailure.INVALID_EVENT,
                "payload.release_reason",
                "unsupported release reason",
            )
        _artifact_reference(payload.get("policy_reference"), "payload.policy_reference")
    _validate_payload_times(event_type, payload, occurred)


def validate_event_prefix(
    events: Sequence[Mapping[str, object]], *, scope: ProjectionScope
) -> tuple[str, ...]:
    """Validate one complete stream prefix and return ordered fingerprints."""

    fingerprints: list[str] = []
    identities: set[str] = set()
    for expected_position, event in enumerate(events, start=1):
        validate_execution_event(event, scope=scope)
        if event.get("source_position") != expected_position:
            _reject(
                ProjectionFailure.ORDERING_VIOLATION,
                "source_position",
                "stream prefix contains a gap, duplicate, or late position",
            )
        event_id = _text(event.get("event_id"), "event_id")
        if event_id in identities:
            _reject(
                ProjectionFailure.ORDERING_VIOLATION,
                "event_id",
                "stream prefix repeats an event identity",
            )
        identities.add(event_id)
        fingerprints.append(_text(event.get("event_fingerprint"), "event_fingerprint"))
    return tuple(fingerprints)


def _records(document: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], document["records"])


def _collection(document: dict[str, object], name: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], _records(document)[name])


def _index(
    document: dict[str, object], collection: str
) -> dict[str, dict[str, object]]:
    id_field = COLLECTION_ID_FIELDS[collection]
    return {
        cast(str, record[id_field]): record
        for record in _collection(document, collection)
    }


def _instance_index(document: dict[str, object]) -> dict[str, dict[str, object]]:
    instances = cast(list[dict[str, object]], document["operation_instances"])
    return {
        cast(str, instance["operation_instance_id"]): instance for instance in instances
    }


def _event_source(event: Mapping[str, object]) -> dict[str, str]:
    return {
        "source_system": PROJECTOR_SOURCE_SYSTEM,
        "source_version": PROJECTOR_SOURCE_VERSION,
        "source_record_id": _text(event.get("event_id"), "event_id"),
    }


def _operation_instance(
    document: dict[str, object], operation_id: object
) -> dict[str, object]:
    identifier = _text(operation_id, "payload.operation_id")
    instance = _instance_index(document).get(identifier)
    if instance is None:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.operation_id",
            "must identify one operation instance",
        )
    return instance


def _resource_option(
    instance: Mapping[str, object], resource_id: object
) -> Mapping[str, object]:
    identifier = _text(resource_id, "payload.resource_id")
    matches = [
        _mapping(option, "operation_instance.resource_options[]")
        for option in _sequence(
            instance.get("resource_options"), "operation_instance.resource_options"
        )
        if _mapping(option, "operation_instance.resource_options[]").get("resource_id")
        == identifier
    ]
    if len(matches) != 1:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.resource_id",
            "is not one exact candidate resource",
        )
    return matches[0]


def _replace_execution_fact(
    document: dict[str, object],
    instance: dict[str, object],
    fact: dict[str, object],
) -> None:
    facts = _collection(document, "execution_facts")
    lot_id = instance["production_lot_id"]
    routing_operation_id = instance["routing_operation_id"]
    facts[:] = [
        existing
        for existing in facts
        if not (
            existing.get("production_lot_id") == lot_id
            and existing.get("routing_operation_id") == routing_operation_id
        )
    ]
    facts.append(fact)
    instance["status"] = fact["status"]
    instance["execution_fact_id"] = fact["execution_fact_id"]


def _fact_id(event: Mapping[str, object]) -> str:
    fingerprint = _text(event.get("event_fingerprint"), "event_fingerprint")
    return f"execution-fact-{fingerprint.removeprefix('sha256:')}"


def _project_operation_started(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    instance = _operation_instance(document, payload.get("operation_id"))
    if instance.get("status") == "COMPLETED":
        _reject(
            ProjectionFailure.TERMINAL_REGRESSION,
            "payload.operation_id",
            "completed operation cannot restart",
        )
    if (
        instance.get("status") != "NOT_STARTED"
        or instance.get("execution_fact_id") is not None
    ):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.operation_id",
            "operation already has an effective fact",
        )
    option = _resource_option(instance, payload.get("resource_id"))
    resource = _index(document, "resources").get(cast(str, payload.get("resource_id")))
    if resource is None or resource.get("status") != "AVAILABLE":
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.resource_id",
            "resource is not currently available",
        )
    fact: dict[str, object] = {
        "execution_fact_id": _fact_id(event),
        "production_lot_id": instance["production_lot_id"],
        "routing_operation_id": instance["routing_operation_id"],
        "status": "RUNNING",
        "observed_at_utc": event["occurred_at_utc"],
        "quantity_unit": instance["quantity_unit"],
        "resource_id": payload["resource_id"],
        "actual_start_at_utc": payload["actual_start_at_utc"],
        "remaining_quantity": instance["quantity"],
        "remaining_seconds": option["final_duration_seconds"],
        "source": _event_source(event),
    }
    _replace_execution_fact(document, instance, fact)


def _project_operation_completed(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    instance = _operation_instance(document, payload.get("operation_id"))
    status = instance.get("status")
    if status == "COMPLETED":
        _reject(
            ProjectionFailure.TERMINAL_REGRESSION,
            "payload.operation_id",
            "completed operation is terminal",
        )
    _resource_option(instance, payload.get("resource_id"))
    if status == "RUNNING":
        fact_id = cast(str, instance.get("execution_fact_id"))
        current = _index(document, "execution_facts").get(fact_id)
        if (
            current is None
            or current.get("resource_id") != payload.get("resource_id")
            or current.get("actual_start_at_utc") != payload.get("actual_start_at_utc")
        ):
            _reject(
                ProjectionFailure.FACT_CONFLICT,
                "payload.operation_id",
                "completion contradicts the RUNNING fact",
            )
    elif status != "NOT_STARTED":
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.operation_id",
            "operation status is unsupported",
        )
    fact: dict[str, object] = {
        "execution_fact_id": _fact_id(event),
        "production_lot_id": instance["production_lot_id"],
        "routing_operation_id": instance["routing_operation_id"],
        "status": "COMPLETED",
        "observed_at_utc": event["occurred_at_utc"],
        "quantity_unit": instance["quantity_unit"],
        "resource_id": payload["resource_id"],
        "actual_start_at_utc": payload["actual_start_at_utc"],
        "actual_end_at_utc": payload["actual_end_at_utc"],
        "completed_quantity": instance["quantity"],
        "source": _event_source(event),
    }
    _replace_execution_fact(document, instance, fact)


def _project_remaining_changed(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    remaining = _integer(payload.get("remaining_seconds"), "payload.remaining_seconds")
    if remaining == 0:
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.remaining_seconds",
            "zero remainder requires OPERATION_COMPLETED",
        )
    instance = _operation_instance(document, payload.get("operation_id"))
    if instance.get("status") != "RUNNING":
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.operation_id",
            "remaining duration requires a RUNNING operation",
        )
    current = _index(document, "execution_facts").get(
        cast(str, instance.get("execution_fact_id"))
    )
    if current is None:
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "execution_fact_id",
            "RUNNING fact is absent",
        )
    if _utc(payload.get("as_of_utc"), "payload.as_of_utc") < _utc(
        current.get("actual_start_at_utc"), "execution_fact.actual_start_at_utc"
    ):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.as_of_utc",
            "cannot precede actual start",
        )
    fact = {
        **current,
        "execution_fact_id": _fact_id(event),
        "observed_at_utc": payload["as_of_utc"],
        "remaining_seconds": remaining,
        "source": _event_source(event),
    }
    _replace_execution_fact(document, instance, fact)


def _routing_operation_id(document: dict[str, object], operation_id: object) -> str:
    identifier = _text(operation_id, "payload.operation_id")
    instance = _instance_index(document).get(identifier)
    direct = _index(document, "routing_operations").get(identifier)
    if instance is not None and direct is not None:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.operation_id",
            "ambiguously identifies instance and routing operation",
        )
    if instance is not None:
        return cast(str, instance["routing_operation_id"])
    if direct is not None:
        return identifier
    _reject(
        ProjectionFailure.INVALID_REFERENCE,
        "payload.operation_id",
        "does not identify a routing operation",
    )


def _project_duration_changed(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    routing_operation_id = _routing_operation_id(document, payload.get("operation_id"))
    targeted_instances = [
        instance
        for instance in _instance_index(document).values()
        if instance.get("routing_operation_id") == routing_operation_id
    ]
    if not targeted_instances or any(
        instance.get("status") == "COMPLETED" for instance in targeted_instances
    ):
        _reject(
            ProjectionFailure.TERMINAL_REGRESSION,
            "payload.operation_id",
            "duration cannot rewrite completed history",
        )
    options = [
        option
        for option in _collection(document, "routing_resource_options")
        if option.get("routing_operation_id") == routing_operation_id
    ]
    if not options:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.operation_id",
            "routing operation has no resource option",
        )
    option_ids = {cast(str, option["routing_resource_option_id"]) for option in options}
    for option in options:
        option["final_duration_seconds"] = payload["final_duration_seconds"]
        option["duration_source"] = payload["duration_source"]
        option["duration_source_version"] = payload["source_version"]
        option["source"] = _event_source(event)
    for instance in targeted_instances:
        for option in cast(list[dict[str, object]], instance["resource_options"]):
            if option.get("routing_resource_option_id") in option_ids:
                option["final_duration_seconds"] = payload["final_duration_seconds"]
                option["duration_source"] = payload["duration_source"]
                option["source_version"] = payload["source_version"]


def _open_unavailability(
    events: Sequence[Mapping[str, object]],
    *,
    before_position: int,
    resource_id: str,
) -> Mapping[str, object] | None:
    open_event: Mapping[str, object] | None = None
    for event in events:
        position = cast(int, event["source_position"])
        if position >= before_position:
            break
        payload = _mapping(event["payload"], "payload")
        if payload.get("resource_id") != resource_id:
            continue
        if event.get("event_type") == "MACHINE_UNAVAILABLE":
            open_event = event if payload.get("unavailable_until_utc") is None else None
        elif event.get("event_type") == "MACHINE_RECOVERED":
            open_event = None
    return open_event


def _project_machine_unavailable(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    resource_id = _text(payload.get("resource_id"), "payload.resource_id")
    resource = _index(document, "resources").get(resource_id)
    if resource is None:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.resource_id",
            "resource is absent",
        )
    if resource.get("status") != "AVAILABLE":
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.resource_id",
            "resource is already unavailable",
        )
    resource["status"] = "UNAVAILABLE"
    resource["source"] = _event_source(event)
    until = payload.get("unavailable_until_utc")
    if until is not None:
        calendar = _index(document, "calendars").get(cast(str, resource["calendar_id"]))
        if calendar is None:
            _reject(
                ProjectionFailure.INVALID_REFERENCE,
                "resource.calendar_id",
                "calendar is absent",
            )
        intervals = cast(list[dict[str, object]], calendar["unavailable_intervals"])
        intervals.append(
            {
                "interval_id": f"unavailable-{_text(event['event_fingerprint'], 'event_fingerprint').removeprefix('sha256:')}",
                "start_at_utc": payload["unavailable_from_utc"],
                "end_at_utc": until,
                "reason": "ExecutionEvent MACHINE_UNAVAILABLE",
            }
        )
        calendar["source"] = _event_source(event)


def _project_machine_recovered(
    document: dict[str, object],
    event: Mapping[str, object],
    full_prefix: Sequence[Mapping[str, object]],
) -> None:
    payload = _mapping(event["payload"], "payload")
    resource_id = _text(payload.get("resource_id"), "payload.resource_id")
    resource = _index(document, "resources").get(resource_id)
    if resource is None:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.resource_id",
            "resource is absent",
        )
    open_event = _open_unavailability(
        full_prefix,
        before_position=cast(int, event["source_position"]),
        resource_id=resource_id,
    )
    if resource.get("status") != "UNAVAILABLE" or open_event is None:
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.resource_id",
            "no open unavailability can be recovered",
        )
    open_payload = _mapping(open_event["payload"], "open_unavailability.payload")
    if _utc(payload.get("available_from_utc"), "payload.available_from_utc") <= _utc(
        open_payload.get("unavailable_from_utc"),
        "open_unavailability.unavailable_from_utc",
    ):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.available_from_utc",
            "must follow the open unavailability",
        )
    calendar = _index(document, "calendars").get(cast(str, resource["calendar_id"]))
    if calendar is None:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "resource.calendar_id",
            "calendar is absent",
        )
    cast(list[dict[str, object]], calendar["unavailable_intervals"]).append(
        {
            "interval_id": f"unavailable-{_text(open_event['event_fingerprint'], 'event_fingerprint').removeprefix('sha256:')}",
            "start_at_utc": open_payload["unavailable_from_utc"],
            "end_at_utc": payload["available_from_utc"],
            "reason": "ExecutionEvent MACHINE_UNAVAILABLE/RECOVERED",
        }
    )
    calendar["source"] = _event_source(event)
    resource["status"] = "AVAILABLE"
    resource["source"] = _event_source(event)


def _material_order(
    document: dict[str, object], material_id: object
) -> dict[str, object]:
    identifier = _text(material_id, "payload.material_id")
    orders = _index(document, "production_orders")
    candidates: set[str] = set()
    if identifier in orders:
        candidates.add(identifier)
    lot = _index(document, "production_lots").get(identifier)
    if lot is not None:
        candidates.add(cast(str, lot["production_order_id"]))
    if len(candidates) != 1:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.material_id",
            "must resolve to exactly one production order",
        )
    return orders[candidates.pop()]


def _project_material(document: dict[str, object], event: Mapping[str, object]) -> None:
    payload = _mapping(event["payload"], "payload")
    order = _material_order(document, payload.get("material_id"))
    available = _text(payload.get("available_at_utc"), "payload.available_at_utc")
    if _utc(available, "payload.available_at_utc") < _utc(
        order.get("release_at_utc"), "production_order.release_at_utc"
    ):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.available_at_utc",
            "cannot precede order release",
        )
    if event.get("event_type") == "MATERIAL_DELAYED" and _utc(
        available, "payload.available_at_utc"
    ) <= _utc(
        order.get("material_ready_at_utc"), "production_order.material_ready_at_utc"
    ):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.available_at_utc",
            "delay must move readiness later",
        )
    order["material_ready_at_utc"] = available
    order["source"] = _event_source(event)
    for instance in _instance_index(document).values():
        if instance.get("production_order_id") == order.get("production_order_id"):
            instance["material_ready_at_utc"] = available


def _project_lock_created(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    lock_id = _text(payload.get("lock_id"), "payload.lock_id")
    if lock_id in _index(document, "operation_locks"):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.lock_id",
            "lock identity already exists",
        )
    instance = _operation_instance(document, payload.get("operation_id"))
    if instance.get("status") == "COMPLETED":
        _reject(
            ProjectionFailure.TERMINAL_REGRESSION,
            "payload.operation_id",
            "completed operation cannot receive a lock",
        )
    _resource_option(instance, payload.get("resource_id"))
    lock = {
        "lock_id": lock_id,
        "production_lot_id": instance["production_lot_id"],
        "routing_operation_id": instance["routing_operation_id"],
        "lock_type": f"{payload['lock_type']}_LOCK",
        "resource_id": payload["resource_id"],
        "start_at_utc": payload["start_at_utc"],
        "end_at_utc": payload["end_at_utc"],
        "source": _event_source(event),
    }
    _collection(document, "operation_locks").append(lock)
    lock_ids = cast(list[str], instance["lock_ids"])
    lock_ids.append(lock_id)
    lock_ids.sort()


def _project_lock_released(
    document: dict[str, object], event: Mapping[str, object]
) -> None:
    payload = _mapping(event["payload"], "payload")
    lock_id = _text(payload.get("lock_id"), "payload.lock_id")
    lock = _index(document, "operation_locks").get(lock_id)
    if lock is None:
        _reject(
            ProjectionFailure.INVALID_REFERENCE,
            "payload.lock_id",
            "effective lock is absent",
        )
    matching = [
        instance
        for instance in _instance_index(document).values()
        if lock_id in cast(list[str], instance["lock_ids"])
    ]
    if len(matching) != 1:
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.lock_id",
            "lock does not map to one operation instance",
        )
    instance = matching[0]
    if (
        payload.get("release_reason") == "OPERATION_COMPLETED"
        and instance.get("status") != "COMPLETED"
    ):
        _reject(
            ProjectionFailure.FACT_CONFLICT,
            "payload.release_reason",
            "operation is not completed",
        )
    _collection(document, "operation_locks")[:] = [
        item
        for item in _collection(document, "operation_locks")
        if item.get("lock_id") != lock_id
    ]
    cast(list[str], instance["lock_ids"]).remove(lock_id)


def _by_id(
    document: Mapping[str, object], collection: str, id_field: str
) -> dict[str, Mapping[str, object]]:
    records = cast(Mapping[str, object], document["records"])
    values = cast(Sequence[Mapping[str, object]], records[collection])
    return {cast(str, value[id_field]): value for value in values}


def _validate_urgent_candidate(
    current: Mapping[str, object],
    candidate: Mapping[str, object],
    event: Mapping[str, object],
) -> UrgentPriorityFact:
    payload = _mapping(event["payload"], "payload")
    demand_id = _text(payload.get("demand_order_id"), "payload.demand_order_id")
    if (
        current.get("synthetic") is not True
        or candidate.get("synthetic") is not True
        or current.get("synthetic_provenance") != candidate.get("synthetic_provenance")
    ):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "synthetic_provenance",
            "urgent import crossed its Simulation provenance boundary",
        )
    for collection, id_field in COLLECTION_ID_FIELDS.items():
        before = _by_id(current, collection, id_field)
        after = _by_id(candidate, collection, id_field)
        if any(
            after.get(identifier) != record for identifier, record in before.items()
        ):
            _reject(
                ProjectionFailure.URGENT_IMPORT_MISMATCH,
                collection,
                "urgent import removed or changed an existing canonical record",
            )
    before_demands = _by_id(current, "demand_orders", "demand_order_id")
    after_demands = _by_id(candidate, "demand_orders", "demand_order_id")
    added_demands = set(after_demands).difference(before_demands)
    if added_demands != {demand_id}:
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "demand_orders",
            "must add exactly the event demand",
        )
    demand = after_demands[demand_id]
    if demand.get("quantity") != payload.get("quantity") or demand.get(
        "due_at_utc"
    ) != payload.get("due_at_utc"):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "payload",
            "quantity or due time differs from standard Import",
        )

    before_orders = _by_id(current, "production_orders", "production_order_id")
    after_orders = _by_id(candidate, "production_orders", "production_order_id")
    new_orders = [
        after_orders[identifier]
        for identifier in set(after_orders).difference(before_orders)
    ]
    if not new_orders or any(
        order.get("demand_order_id") != demand_id for order in new_orders
    ):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "production_orders",
            "new production orders must belong only to the urgent demand",
        )
    if sum(cast(int | float, order["quantity"]) for order in new_orders) != payload.get(
        "quantity"
    ):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "production_orders.quantity",
            "new order quantity must exactly cover urgent demand",
        )
    new_order_ids = {cast(str, order["production_order_id"]) for order in new_orders}
    before_lots = _by_id(current, "production_lots", "production_lot_id")
    after_lots = _by_id(candidate, "production_lots", "production_lot_id")
    new_lots = [
        after_lots[identifier] for identifier in set(after_lots).difference(before_lots)
    ]
    if not new_lots or any(
        lot.get("production_order_id") not in new_order_ids for lot in new_lots
    ):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "production_lots",
            "new lots must belong only to urgent production orders",
        )

    no_additions = (
        "factories",
        "workshops",
        "production_lines",
        "resource_groups",
        "resources",
        "calendars",
        "execution_facts",
        "operation_locks",
    )
    for collection in no_additions:
        id_field = COLLECTION_ID_FIELDS[collection]
        if set(_by_id(candidate, collection, id_field)) != set(
            _by_id(current, collection, id_field)
        ):
            _reject(
                ProjectionFailure.URGENT_IMPORT_MISMATCH,
                collection,
                "urgent import may not change topology or effective facts",
            )
    current_instances = {
        cast(str, item["operation_instance_id"]): item
        for item in cast(Sequence[Mapping[str, object]], current["operation_instances"])
    }
    candidate_instances = {
        cast(str, item["operation_instance_id"]): item
        for item in cast(
            Sequence[Mapping[str, object]], candidate["operation_instances"]
        )
    }
    if any(
        candidate_instances.get(identifier) != item
        for identifier, item in current_instances.items()
    ):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "operation_instances",
            "existing expanded operations changed",
        )
    added_instances = [
        candidate_instances[identifier]
        for identifier in set(candidate_instances).difference(current_instances)
    ]
    if not added_instances or any(
        item.get("production_order_id") not in new_order_ids for item in added_instances
    ):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "operation_instances",
            "new expanded operations are not confined to urgent orders",
        )
    source = _source_reference(
        payload.get("priority_source"), "payload.priority_source"
    )
    return UrgentPriorityFact(
        event_id=_text(event.get("event_id"), "event_id"),
        demand_order_id=demand_id,
        priority_weight=_integer(
            payload.get("priority_weight"), "payload.priority_weight", minimum=1
        ),
        source_system=cast(str, source["source_system"]),
        source_version=cast(str, source["source_version"]),
        source_record_id=cast(str, source["source_record_id"]),
    )


def _apply_event(
    document: dict[str, object],
    event: Mapping[str, object],
    *,
    full_prefix: Sequence[Mapping[str, object]],
    urgent_snapshot: Mapping[str, object] | None,
) -> tuple[dict[str, object], UrgentPriorityFact | None]:
    event_type = cast(str, event["event_type"])
    if event_type == "URGENT_DEMAND_RECEIVED":
        if urgent_snapshot is None:
            _reject(
                ProjectionFailure.URGENT_IMPORT_REQUIRED,
                "urgent_import",
                "complete standard Import/Validation artifacts are required",
            )
        priority = _validate_urgent_candidate(document, urgent_snapshot, event)
        candidate = cast(dict[str, object], deepcopy(urgent_snapshot))
        merged_versions = {
            **cast(dict[str, str], document["source_versions"]),
            **cast(dict[str, str], candidate["source_versions"]),
        }
        candidate["source_versions"] = merged_versions
        return candidate, priority
    if event_type == "OPERATION_STARTED":
        _project_operation_started(document, event)
    elif event_type == "OPERATION_COMPLETED":
        _project_operation_completed(document, event)
    elif event_type == "PROCESSING_REMAINING_CHANGED":
        _project_remaining_changed(document, event)
    elif event_type == "PROCESSING_DURATION_CHANGED":
        _project_duration_changed(document, event)
    elif event_type == "MACHINE_UNAVAILABLE":
        _project_machine_unavailable(document, event)
    elif event_type == "MACHINE_RECOVERED":
        _project_machine_recovered(document, event, full_prefix)
    elif event_type in {"MATERIAL_READY", "MATERIAL_DELAYED"}:
        _project_material(document, event)
    elif event_type == "LOCK_CREATED":
        _project_lock_created(document, event)
    elif event_type == "LOCK_RELEASED":
        _project_lock_released(document, event)
    else:
        _reject(
            ProjectionFailure.INVALID_EVENT,
            "event_type",
            "unsupported projection event",
        )
    return document, None


def project_execution_event_batch(
    base_snapshot: Mapping[str, object],
    *,
    full_prefix: Sequence[Mapping[str, object]],
    after_position: int,
    scope: ProjectionScope,
    urgent_snapshots: Mapping[str, Mapping[str, object]] | None = None,
) -> ProjectedFactBatch:
    """Project the continuous tail of a fully verified event-stream prefix."""

    fingerprints = validate_event_prefix(full_prefix, scope=scope)
    if after_position < 0 or after_position > len(full_prefix):
        _reject(
            ProjectionFailure.ORDERING_VIOLATION,
            "after_position",
            "is outside the verified prefix",
        )
    tail = tuple(full_prefix[after_position:])
    if not tail:
        _reject(
            ProjectionFailure.ORDERING_VIOLATION,
            "event_stream",
            "projection tail is empty",
        )
    factories = _by_id(base_snapshot, "factories", "factory_id")
    if (
        set(factories) != {scope.factory_id}
        or base_snapshot.get("synthetic") is not True
    ):
        _reject(
            ProjectionFailure.AUTHORITY_MISMATCH,
            "base_snapshot",
            "Snapshot factory or plane differs from projection scope",
        )
    original_hash = _text(
        base_snapshot.get("snapshot_hash"), "base_snapshot.snapshot_hash"
    )
    document = cast(dict[str, object], deepcopy(base_snapshot))
    priority_facts: list[UrgentPriorityFact] = []
    supplied = urgent_snapshots or {}
    tail_ids = {_text(event.get("event_id"), "event_id") for event in tail}
    if set(supplied).difference(tail_ids):
        _reject(
            ProjectionFailure.URGENT_IMPORT_MISMATCH,
            "urgent_imports",
            "contains an event outside the projection tail",
        )
    for event in tail:
        event_id = _text(event.get("event_id"), "event_id")
        document, priority = _apply_event(
            document,
            event,
            full_prefix=full_prefix,
            urgent_snapshot=supplied.get(event_id),
        )
        if priority is not None:
            priority_facts.append(priority)

    through = cast(int, tail[-1]["source_position"])
    prefix_fingerprint = event_stream_fingerprint(fingerprints[:through])
    source_versions = cast(dict[str, str], document["source_versions"])
    source_versions[PROJECTOR_SOURCE_SYSTEM] = PROJECTOR_SOURCE_VERSION
    source_versions[BASE_SNAPSHOT_SOURCE] = original_hash
    source_versions[EVENT_AUTHORITY_SOURCE] = scope.authority_id
    source_versions[EVENT_STREAM_SOURCE] = (
        f"{scope.stream_id}@{scope.stream_version}#position={through}#{prefix_fingerprint}"
    )
    cutoffs = [_utc(document.get("cutoff_at_utc"), "snapshot.cutoff_at_utc")]
    cutoffs.extend(
        _utc(event.get("occurred_at_utc"), "occurred_at_utc") for event in tail
    )
    document["cutoff_at_utc"] = (
        max(cutoffs).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    return ProjectedFactBatch(
        document=document,
        from_position=after_position + 1,
        through_position=through,
        event_ids=tuple(_text(event.get("event_id"), "event_id") for event in tail),
        event_fingerprints=tuple(fingerprints[after_position:through]),
        stream_fingerprint=prefix_fingerprint,
        priority_facts=tuple(priority_facts),
    )


__all__ = [
    "BASE_SNAPSHOT_SOURCE",
    "EVENT_AUTHORITY_SOURCE",
    "EVENT_STREAM_SOURCE",
    "PROJECTOR_RECORD_VERSION",
    "PROJECTOR_SOURCE_SYSTEM",
    "PROJECTOR_SOURCE_VERSION",
    "ExecutionFactProjectionError",
    "ProjectedFactBatch",
    "ProjectionFailure",
    "ProjectionScope",
    "UrgentPriorityFact",
    "project_execution_event_batch",
    "validate_event_prefix",
    "validate_execution_event",
]
