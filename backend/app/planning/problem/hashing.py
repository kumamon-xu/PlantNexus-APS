"""Canonical serialization, hashing, and integrity checks for PlanningProblem."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Final, NoReturn, cast

from app.domain.capabilities import (
    CapabilityContractError,
    require_v1_capability_contract,
)
from .contracts import (
    ImmutablePlanningProblem,
    ImmutablePlanningProblemV2,
    PlanningProblemDocument,
    PlanningProblemDocumentV2,
    PlanningProblemError,
    PlanningProblemErrorCode,
)

PLANNING_PROBLEM_VERSION: Final = "planning-problem.v1"
PROBLEM_BUILDER_VERSION: Final = "planning-problem-builder.v1"
PROBLEM_CANONICALIZATION_VERSION: Final = "canonical-json.v1"
PROBLEM_HASH_PROJECTION_VERSION: Final = "planning-problem-hash-projection.v1"
PLANNING_PROBLEM_VERSION_V2: Final = "planning-problem.v2"
PROBLEM_SCHEMA_SET_VERSION_V2: Final = "2.3.0"
PROBLEM_BUILDER_VERSION_V2: Final = "planning-problem-builder.v2"
PROBLEM_HASH_PROJECTION_VERSION_V2: Final = "planning-problem-hash-projection.v2"

_ROOT_FIELDS = {
    "problem_version",
    "snapshot_id",
    "problem_builder_version",
    "problem_hash",
    "tick_seconds",
    "horizon_start_utc",
    "horizon_end_utc",
    "resource_ids",
    "operation_instances",
    "precedence_edges",
    "resource_unavailable_intervals",
    "required_capabilities",
}
_OPERATION_FIELDS = {
    "operation_id",
    "status",
    "release_at_utc",
    "material_ready_at_utc",
    "resource_options",
}
_RUNNING_FIELDS = {
    "actual_start_at_utc",
    "assigned_resource_id",
    "remaining_seconds",
}
_OPTION_FIELDS = {
    "resource_id",
    "setup_seconds",
    "cycle_seconds_per_unit",
    "final_duration_seconds",
    "duration_source",
    "source_version",
}
_EDGE_FIELDS = {
    "predecessor_operation_id",
    "successor_operation_id",
    "min_lag_seconds",
    "transport_lag_seconds",
}
_INTERVAL_FIELDS = {"resource_id", "start_utc", "end_utc"}


def _reject(
    code: PlanningProblemErrorCode,
    *,
    field: str,
    entity_id: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise PlanningProblemError(
        code,
        field=field,
        entity_id=entity_id,
        expected_contract=expected_contract,
        message=message,
    )


def _canonical_option(option: Mapping[str, object]) -> dict[str, object]:
    return {field: option[field] for field in sorted(_OPTION_FIELDS)}


def _canonical_operation(operation: Mapping[str, object]) -> dict[str, object]:
    canonical: dict[str, object] = {
        field: operation[field]
        for field in sorted(_OPERATION_FIELDS - {"resource_options"})
    }
    raw_options = cast(list[Mapping[str, object]], operation["resource_options"])
    options = [_canonical_option(option) for option in raw_options]
    options.sort(
        key=lambda option: (
            str(option["resource_id"]),
            cast(int, option["final_duration_seconds"]),
            cast(int, option["setup_seconds"]),
            cast(int, option["cycle_seconds_per_unit"]),
            str(option["duration_source"]),
            str(option["source_version"]),
        )
    )
    canonical["resource_options"] = options
    if operation.get("status") == "RUNNING":
        canonical.update({field: operation[field] for field in sorted(_RUNNING_FIELDS)})
    return canonical


def _canonical_edge(edge: Mapping[str, object]) -> dict[str, object]:
    canonical = {field: edge[field] for field in sorted(_EDGE_FIELDS)}
    if "max_lag_seconds" in edge:
        canonical["max_lag_seconds"] = edge["max_lag_seconds"]
    return canonical


def _canonical_interval(interval: Mapping[str, object]) -> dict[str, object]:
    return {field: interval[field] for field in sorted(_INTERVAL_FIELDS)}


def canonical_problem_document(
    document: Mapping[str, object],
) -> PlanningProblemDocument:
    """Return the versioned stable ordering for a Problem document."""

    raw_operations = cast(list[Mapping[str, object]], document["operation_instances"])
    operations = [_canonical_operation(operation) for operation in raw_operations]
    operations.sort(key=lambda operation: str(operation["operation_id"]))

    raw_edges = cast(list[Mapping[str, object]], document["precedence_edges"])
    edges = [_canonical_edge(edge) for edge in raw_edges]
    edges.sort(
        key=lambda edge: (
            str(edge["predecessor_operation_id"]),
            str(edge["successor_operation_id"]),
            cast(int, edge["min_lag_seconds"]),
            cast(int, edge["transport_lag_seconds"]),
            cast(int, edge.get("max_lag_seconds", -1)),
        )
    )

    raw_intervals = cast(
        list[Mapping[str, object]], document["resource_unavailable_intervals"]
    )
    intervals = [_canonical_interval(interval) for interval in raw_intervals]
    intervals.sort(
        key=lambda interval: (
            str(interval["resource_id"]),
            str(interval["start_utc"]),
            str(interval["end_utc"]),
        )
    )

    canonical = {
        "problem_version": document["problem_version"],
        "snapshot_id": document["snapshot_id"],
        "problem_builder_version": document["problem_builder_version"],
        "problem_hash": document.get("problem_hash", ""),
        "tick_seconds": document["tick_seconds"],
        "horizon_start_utc": document["horizon_start_utc"],
        "horizon_end_utc": document["horizon_end_utc"],
        "resource_ids": sorted(cast(list[str], document["resource_ids"])),
        "operation_instances": operations,
        "precedence_edges": edges,
        "resource_unavailable_intervals": intervals,
        "required_capabilities": sorted(
            cast(list[str], document["required_capabilities"])
        ),
    }
    return cast(PlanningProblemDocument, canonical)


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_problem_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize only the PlanningProblem contract using canonical-json.v1."""

    canonical = canonical_problem_document(document)
    return _canonical_json_bytes(cast(Mapping[str, object], canonical))


def problem_hash_projection(document: Mapping[str, object]) -> dict[str, object]:
    """Project stable Problem semantics, excluding self-hash and runtime noise."""

    canonical = cast(dict[str, object], canonical_problem_document(document))
    canonical.pop("problem_hash", None)
    return {
        "problem_hash_projection_version": PROBLEM_HASH_PROJECTION_VERSION,
        "problem": canonical,
    }


def problem_hash_for(document: Mapping[str, object]) -> str:
    """Return the SHA-256 identity for a canonical Problem hash projection."""

    projection = problem_hash_projection(document)
    return f"sha256:{sha256(_canonical_json_bytes(projection)).hexdigest()}"


def _require_exact_fields(
    value: Mapping[str, object],
    expected: set[str],
    *,
    field: str,
    entity_id: str,
) -> None:
    if set(value) != expected:
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field=field,
            entity_id=entity_id,
            expected_contract=f"exact fields {sorted(expected)}",
            message="Problem fields do not match planning-problem.v1",
        )


def _validate_exact_shape(document: Mapping[str, object]) -> None:
    _require_exact_fields(
        document,
        _ROOT_FIELDS,
        field="planning_problem",
        entity_id=str(document.get("snapshot_id", "<missing>")),
    )
    operations = cast(list[Mapping[str, object]], document["operation_instances"])
    for index, operation in enumerate(operations):
        status = operation.get("status")
        if status not in {"NOT_STARTED", "RUNNING"}:
            _reject(
                PlanningProblemErrorCode.MODEL_INVALID,
                field=f"operation_instances[{index}].status",
                entity_id=str(operation.get("operation_id", f"index:{index}")),
                expected_contract="NOT_STARTED or RUNNING",
                message="Problem operation status is invalid",
            )
        expected = _OPERATION_FIELDS | (
            _RUNNING_FIELDS if status == "RUNNING" else set()
        )
        operation_id = str(operation.get("operation_id", f"index:{index}"))
        _require_exact_fields(
            operation,
            expected,
            field=f"operation_instances[{index}]",
            entity_id=operation_id,
        )
        options = cast(list[Mapping[str, object]], operation["resource_options"])
        if not options:
            _reject(
                PlanningProblemErrorCode.MODEL_INVALID,
                field=f"operation_instances[{index}].resource_options",
                entity_id=operation_id,
                expected_contract="at least one unique candidate resource",
                message="Problem operation has no candidate resource",
            )
        option_resource_ids: set[str] = set()
        for option_index, option in enumerate(options):
            _require_exact_fields(
                option,
                _OPTION_FIELDS,
                field=f"operation_instances[{index}].resource_options[{option_index}]",
                entity_id=operation_id,
            )
            resource_id = str(option.get("resource_id", "<missing>"))
            if resource_id in option_resource_ids:
                _reject(
                    PlanningProblemErrorCode.MODEL_INVALID,
                    field=f"operation_instances[{index}].resource_options",
                    entity_id=operation_id,
                    expected_contract="one candidate option per resource",
                    message="Candidate resource is duplicated",
                )
            option_resource_ids.add(resource_id)
    logical_edges: set[tuple[str, str]] = set()
    for index, edge in enumerate(
        cast(list[Mapping[str, object]], document["precedence_edges"])
    ):
        expected = _EDGE_FIELDS | ({"max_lag_seconds"} if "max_lag_seconds" in edge else set())
        _require_exact_fields(
            edge,
            expected,
            field=f"precedence_edges[{index}]",
            entity_id=(
                f"{edge.get('predecessor_operation_id', '?')}->"
                f"{edge.get('successor_operation_id', '?')}"
            ),
        )
        logical_edge = (
            str(edge.get("predecessor_operation_id", "<missing>")),
            str(edge.get("successor_operation_id", "<missing>")),
        )
        if logical_edge in logical_edges:
            _reject(
                PlanningProblemErrorCode.MODEL_INVALID,
                field="precedence_edges",
                entity_id=f"{logical_edge[0]}->{logical_edge[1]}",
                expected_contract="one logical edge per active operation pair",
                message="Logical precedence edge is duplicated",
            )
        logical_edges.add(logical_edge)
    interval_keys: set[tuple[str, str, str]] = set()
    for index, interval in enumerate(
        cast(list[Mapping[str, object]], document["resource_unavailable_intervals"])
    ):
        _require_exact_fields(
            interval,
            _INTERVAL_FIELDS,
            field=f"resource_unavailable_intervals[{index}]",
            entity_id=str(interval.get("resource_id", f"index:{index}")),
        )
        interval_key = (
            str(interval.get("resource_id", "<missing>")),
            str(interval.get("start_utc", "<missing>")),
            str(interval.get("end_utc", "<missing>")),
        )
        if interval_key in interval_keys:
            _reject(
                PlanningProblemErrorCode.MODEL_INVALID,
                field="resource_unavailable_intervals",
                entity_id=interval_key[0],
                expected_contract="unique resource/time interval",
                message="Unavailable interval is duplicated",
            )
        interval_keys.add(interval_key)


def _validate_dag(document: Mapping[str, object]) -> None:
    operation_ids = {
        str(operation["operation_id"])
        for operation in cast(list[Mapping[str, object]], document["operation_instances"])
    }
    successors = {operation_id: [] for operation_id in operation_ids}
    indegree = {operation_id: 0 for operation_id in operation_ids}
    for edge in cast(list[Mapping[str, object]], document["precedence_edges"]):
        predecessor = str(edge["predecessor_operation_id"])
        successor = str(edge["successor_operation_id"])
        successors[predecessor].append(successor)
        indegree[successor] += 1
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for successor in sorted(successors[node]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
                ready.sort()
    if visited != len(operation_ids):
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="precedence_edges",
            entity_id=str(document.get("snapshot_id", "<missing>")),
            expected_contract="acyclic active-operation precedence graph",
            message="PlanningProblem precedence graph contains a cycle",
        )


def validate_built_problem(document: Mapping[str, object]) -> None:
    """Validate exact shape, pure contract semantics, capabilities, and DAG."""

    from app.domain.validation import (  # local import avoids the domain contract cycle
        ContractViolation,
        validate_planning_problem_contract,
    )

    _validate_exact_shape(document)
    if document["problem_version"] != PLANNING_PROBLEM_VERSION:
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="problem_version",
            entity_id=str(document.get("snapshot_id", "<missing>")),
            expected_contract=PLANNING_PROBLEM_VERSION,
            message="Problem version is unsupported",
        )
    if document["problem_builder_version"] != PROBLEM_BUILDER_VERSION:
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="problem_builder_version",
            entity_id=str(document.get("snapshot_id", "<missing>")),
            expected_contract=PROBLEM_BUILDER_VERSION,
            message="Problem builder version is unsupported",
        )
    try:
        validate_planning_problem_contract(cast(PlanningProblemDocument, document))
        require_v1_capability_contract(
            cast(list[str], document["required_capabilities"])
        )
    except (ContractViolation, CapabilityContractError, KeyError, TypeError, ValueError) as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.MODEL_INVALID,
            field=getattr(error, "field", "planning_problem"),
            entity_id=str(document.get("snapshot_id", "<missing>")),
            expected_contract="valid solver-neutral planning-problem.v1",
            message="Built Problem failed the pure contract precheck",
        ) from error
    _validate_dag(document)


def verify_problem(problem: ImmutablePlanningProblem) -> None:
    """Verify canonical bytes, metadata, contract, DAG, and content hash."""

    try:
        decoded = json.loads(problem.canonical_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="canonical_bytes",
            entity_id=problem.snapshot_id,
            expected_contract="canonical-json.v1 PlanningProblem object",
            message="Problem bytes are not valid canonical JSON",
        ) from error
    if not isinstance(decoded, dict):
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="canonical_bytes",
            entity_id=problem.snapshot_id,
            expected_contract="PlanningProblem JSON object",
            message="Problem bytes do not contain an object",
        )
    document = cast(dict[str, object], decoded)
    validate_built_problem(document)
    if canonical_problem_bytes(document) != problem.canonical_bytes:
        _reject(
            PlanningProblemErrorCode.HASH_MISMATCH,
            field="canonical_bytes",
            entity_id=problem.snapshot_id,
            expected_contract=PROBLEM_CANONICALIZATION_VERSION,
            message="Problem bytes are not in canonical order",
        )
    expected_hash = problem_hash_for(document)
    if (
        document["problem_hash"] != expected_hash
        or problem.problem_hash != expected_hash
        or problem.snapshot_id != document["snapshot_id"]
        or problem.problem_builder_version != document["problem_builder_version"]
    ):
        _reject(
            PlanningProblemErrorCode.HASH_MISMATCH,
            field="problem_hash",
            entity_id=problem.snapshot_id,
            expected_contract="content-derived PlanningProblem hash and matching metadata",
            message="Problem identity does not match its canonical content",
        )


_V2_ROOT_FIELDS = {
    "problem_version",
    "schema_set_version",
    "snapshot_id",
    "problem_builder_version",
    "problem_hash",
    "canonicalization_version",
    "problem_hash_projection_version",
    "tick_seconds",
    "horizon_start_utc",
    "horizon_end_utc",
    "delivery_demands",
    "resources",
    "operation_instances",
    "historical_completion_anchors",
    "precedence_edges",
    "operation_locks",
    "resource_unavailable_intervals",
    "required_capabilities",
}
_V2_DEMAND_FIELDS = {
    "demand_order_id",
    "due_at_utc",
    "due_source_system",
    "due_source_version",
    "due_source_record_id",
    "priority_weight",
    "priority_source_system",
    "priority_source_version",
    "priority_source_record_id",
}
_V2_RESOURCE_FIELDS = {
    "resource_id",
    "resource_code",
    "resource_type",
    "status",
    "factory_id",
    "workshop_id",
    "production_line_id",
    "resource_group_id",
    "calendar_id",
    "capabilities",
    "capacity",
}
_V2_OPERATION_FIELDS = {
    "operation_id",
    "demand_order_id",
    "status",
    "release_at_utc",
    "material_ready_at_utc",
    "required_capabilities",
    "resource_options",
}
_V2_ANCHOR_FIELDS = {
    "operation_id",
    "execution_fact_id",
    "resource_id",
    "actual_start_at_utc",
    "actual_end_at_utc",
    "source_system",
    "source_version",
    "source_record_id",
}
_V2_EDGE_FIELDS = {
    "precedence_edge_id",
    "predecessor_operation_id",
    "successor_operation_id",
    "min_lag_seconds",
    "transport_lag_seconds",
}
_V2_LOCK_FIELDS = {
    "lock_id",
    "operation_id",
    "lock_type",
    "resource_id",
    "start_at_utc",
    "end_at_utc",
    "source_system",
    "source_version",
    "source_record_id",
}
_V2_INTERVAL_FIELDS = {"calendar_id", "resource_id", "start_utc", "end_utc"}


def _canonical_demand_v2(demand: Mapping[str, object]) -> dict[str, object]:
    return {field: demand[field] for field in sorted(_V2_DEMAND_FIELDS)}


def _canonical_resource_v2(resource: Mapping[str, object]) -> dict[str, object]:
    canonical = {
        field: resource[field]
        for field in sorted(_V2_RESOURCE_FIELDS - {"capabilities"})
    }
    canonical["capabilities"] = sorted(cast(list[str], resource["capabilities"]))
    return canonical


def _canonical_operation_v2(operation: Mapping[str, object]) -> dict[str, object]:
    canonical = {
        field: operation[field]
        for field in sorted(
            _V2_OPERATION_FIELDS - {"required_capabilities", "resource_options"}
        )
    }
    canonical["required_capabilities"] = sorted(
        cast(list[str], operation["required_capabilities"])
    )
    options = [
        _canonical_option(option)
        for option in cast(list[Mapping[str, object]], operation["resource_options"])
    ]
    options.sort(
        key=lambda option: (
            str(option["resource_id"]),
            cast(int, option["final_duration_seconds"]),
            cast(int, option["setup_seconds"]),
            cast(int, option["cycle_seconds_per_unit"]),
            str(option["duration_source"]),
            str(option["source_version"]),
        )
    )
    canonical["resource_options"] = options
    if operation.get("status") == "RUNNING":
        canonical.update({field: operation[field] for field in sorted(_RUNNING_FIELDS)})
    return canonical


def _canonical_anchor_v2(anchor: Mapping[str, object]) -> dict[str, object]:
    return {field: anchor[field] for field in sorted(_V2_ANCHOR_FIELDS)}


def _canonical_edge_v2(edge: Mapping[str, object]) -> dict[str, object]:
    canonical = {field: edge[field] for field in sorted(_V2_EDGE_FIELDS)}
    if "max_lag_seconds" in edge:
        canonical["max_lag_seconds"] = edge["max_lag_seconds"]
    return canonical


def _canonical_lock_v2(lock: Mapping[str, object]) -> dict[str, object]:
    return {field: lock[field] for field in sorted(_V2_LOCK_FIELDS)}


def _canonical_interval_v2(interval: Mapping[str, object]) -> dict[str, object]:
    return {field: interval[field] for field in sorted(_V2_INTERVAL_FIELDS)}


def canonical_problem_document_v2(
    document: Mapping[str, object],
) -> PlanningProblemDocumentV2:
    """Return stable collection ordering for planning-problem.v2."""

    demands = [
        _canonical_demand_v2(demand)
        for demand in cast(list[Mapping[str, object]], document["delivery_demands"])
    ]
    demands.sort(key=lambda demand: str(demand["demand_order_id"]))

    resources = [
        _canonical_resource_v2(resource)
        for resource in cast(list[Mapping[str, object]], document["resources"])
    ]
    resources.sort(key=lambda resource: str(resource["resource_id"]))

    operations = [
        _canonical_operation_v2(operation)
        for operation in cast(list[Mapping[str, object]], document["operation_instances"])
    ]
    operations.sort(key=lambda operation: str(operation["operation_id"]))

    anchors = [
        _canonical_anchor_v2(anchor)
        for anchor in cast(
            list[Mapping[str, object]], document["historical_completion_anchors"]
        )
    ]
    anchors.sort(
        key=lambda anchor: (
            str(anchor["operation_id"]),
            str(anchor["execution_fact_id"]),
        )
    )

    edges = [
        _canonical_edge_v2(edge)
        for edge in cast(list[Mapping[str, object]], document["precedence_edges"])
    ]
    edges.sort(
        key=lambda edge: (
            str(edge["precedence_edge_id"]),
            str(edge["predecessor_operation_id"]),
            str(edge["successor_operation_id"]),
        )
    )

    locks = [
        _canonical_lock_v2(lock)
        for lock in cast(list[Mapping[str, object]], document["operation_locks"])
    ]
    locks.sort(key=lambda lock: str(lock["lock_id"]))

    intervals = [
        _canonical_interval_v2(interval)
        for interval in cast(
            list[Mapping[str, object]], document["resource_unavailable_intervals"]
        )
    ]
    intervals.sort(
        key=lambda interval: (
            str(interval["resource_id"]),
            str(interval["calendar_id"]),
            str(interval["start_utc"]),
            str(interval["end_utc"]),
        )
    )

    canonical = {
        "problem_version": document["problem_version"],
        "schema_set_version": document["schema_set_version"],
        "snapshot_id": document["snapshot_id"],
        "problem_builder_version": document["problem_builder_version"],
        "problem_hash": document.get("problem_hash", ""),
        "canonicalization_version": document["canonicalization_version"],
        "problem_hash_projection_version": document[
            "problem_hash_projection_version"
        ],
        "tick_seconds": document["tick_seconds"],
        "horizon_start_utc": document["horizon_start_utc"],
        "horizon_end_utc": document["horizon_end_utc"],
        "delivery_demands": demands,
        "resources": resources,
        "operation_instances": operations,
        "historical_completion_anchors": anchors,
        "precedence_edges": edges,
        "operation_locks": locks,
        "resource_unavailable_intervals": intervals,
        "required_capabilities": sorted(
            cast(list[str], document["required_capabilities"])
        ),
    }
    return cast(PlanningProblemDocumentV2, canonical)


def canonical_problem_v2_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize planning-problem.v2 using canonical-json.v1."""

    canonical = canonical_problem_document_v2(document)
    return _canonical_json_bytes(cast(Mapping[str, object], canonical))


def problem_v2_hash_projection(document: Mapping[str, object]) -> dict[str, object]:
    """Project all v2 planning semantics while excluding the self-hash."""

    canonical = cast(dict[str, object], canonical_problem_document_v2(document))
    canonical.pop("problem_hash", None)
    return {
        "problem_hash_projection_version": PROBLEM_HASH_PROJECTION_VERSION_V2,
        "problem": canonical,
    }


def problem_v2_hash_for(document: Mapping[str, object]) -> str:
    """Return the SHA-256 identity of the v2 Problem hash projection."""

    projection = problem_v2_hash_projection(document)
    return f"sha256:{sha256(_canonical_json_bytes(projection)).hexdigest()}"


def _require_exact_fields_v2(
    value: Mapping[str, object],
    expected: set[str],
    *,
    field: str,
    entity_id: str,
) -> None:
    if set(value) != expected:
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field=field,
            entity_id=entity_id,
            expected_contract=f"planning-problem.v2 exact fields {sorted(expected)}",
            message="Problem fields do not match planning-problem.v2",
        )


def _validate_exact_shape_v2(document: Mapping[str, object]) -> None:
    snapshot_id = str(document.get("snapshot_id", "<missing>"))
    _require_exact_fields_v2(
        document,
        _V2_ROOT_FIELDS,
        field="planning_problem",
        entity_id=snapshot_id,
    )
    collection_shapes = (
        ("delivery_demands", _V2_DEMAND_FIELDS, "demand_order_id"),
        ("resources", _V2_RESOURCE_FIELDS, "resource_id"),
        (
            "historical_completion_anchors",
            _V2_ANCHOR_FIELDS,
            "operation_id",
        ),
        ("operation_locks", _V2_LOCK_FIELDS, "lock_id"),
        (
            "resource_unavailable_intervals",
            _V2_INTERVAL_FIELDS,
            "resource_id",
        ),
    )
    for collection, fields, identity_field in collection_shapes:
        values = cast(list[Mapping[str, object]], document[collection])
        for index, value in enumerate(values):
            _require_exact_fields_v2(
                value,
                fields,
                field=f"{collection}[{index}]",
                entity_id=str(value.get(identity_field, f"index:{index}")),
            )

    for index, operation in enumerate(
        cast(list[Mapping[str, object]], document["operation_instances"])
    ):
        status = operation.get("status")
        if status not in {"NOT_STARTED", "RUNNING"}:
            _reject(
                PlanningProblemErrorCode.MODEL_INVALID,
                field=f"operation_instances[{index}].status",
                entity_id=str(operation.get("operation_id", f"index:{index}")),
                expected_contract="NOT_STARTED or RUNNING",
                message="Problem operation status is invalid",
            )
        expected = _V2_OPERATION_FIELDS | (
            _RUNNING_FIELDS if status == "RUNNING" else set()
        )
        operation_id = str(operation.get("operation_id", f"index:{index}"))
        _require_exact_fields_v2(
            operation,
            expected,
            field=f"operation_instances[{index}]",
            entity_id=operation_id,
        )
        for option_index, option in enumerate(
            cast(list[Mapping[str, object]], operation["resource_options"])
        ):
            _require_exact_fields_v2(
                option,
                _OPTION_FIELDS,
                field=f"operation_instances[{index}].resource_options[{option_index}]",
                entity_id=operation_id,
            )

    for index, edge in enumerate(
        cast(list[Mapping[str, object]], document["precedence_edges"])
    ):
        expected = _V2_EDGE_FIELDS | (
            {"max_lag_seconds"} if "max_lag_seconds" in edge else set()
        )
        _require_exact_fields_v2(
            edge,
            expected,
            field=f"precedence_edges[{index}]",
            entity_id=str(edge.get("precedence_edge_id", f"index:{index}")),
        )


def _validate_dag_v2(document: Mapping[str, object]) -> None:
    operation_ids = {
        str(operation["operation_id"])
        for operation in cast(
            list[Mapping[str, object]], document["operation_instances"]
        )
    }
    anchor_ids = {
        str(anchor["operation_id"])
        for anchor in cast(
            list[Mapping[str, object]], document["historical_completion_anchors"]
        )
    }
    node_ids = operation_ids | anchor_ids
    successors = {node_id: [] for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in cast(list[Mapping[str, object]], document["precedence_edges"]):
        predecessor = str(edge["predecessor_operation_id"])
        successor = str(edge["successor_operation_id"])
        successors[predecessor].append(successor)
        indegree[successor] += 1
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for successor in sorted(successors[node]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
                ready.sort()
    if visited != len(node_ids):
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="precedence_edges",
            entity_id=str(document.get("snapshot_id", "<missing>")),
            expected_contract="acyclic active and historical-anchor precedence graph",
            message="PlanningProblem precedence graph contains a cycle",
        )


def validate_built_problem_v2(document: Mapping[str, object]) -> None:
    """Validate exact v2 shape, semantics, capabilities, and precedence DAG."""

    from app.domain.validation import (  # local import avoids the domain contract cycle
        ContractViolation,
        validate_planning_problem_v2_contract,
    )

    _validate_exact_shape_v2(document)
    version_expectations = (
        ("problem_version", PLANNING_PROBLEM_VERSION_V2),
        ("schema_set_version", PROBLEM_SCHEMA_SET_VERSION_V2),
        ("problem_builder_version", PROBLEM_BUILDER_VERSION_V2),
        ("canonicalization_version", PROBLEM_CANONICALIZATION_VERSION),
        (
            "problem_hash_projection_version",
            PROBLEM_HASH_PROJECTION_VERSION_V2,
        ),
    )
    for field, expected in version_expectations:
        if document[field] != expected:
            _reject(
                PlanningProblemErrorCode.MODEL_INVALID,
                field=field,
                entity_id=str(document.get("snapshot_id", "<missing>")),
                expected_contract=expected,
                message="Problem contract version is unsupported",
            )
    try:
        validate_planning_problem_v2_contract(
            cast(PlanningProblemDocumentV2, document)
        )
        require_v1_capability_contract(
            cast(list[str], document["required_capabilities"])
        )
    except (
        ContractViolation,
        CapabilityContractError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.MODEL_INVALID,
            field=getattr(error, "field", "planning_problem"),
            entity_id=str(document.get("snapshot_id", "<missing>")),
            expected_contract="valid solver-neutral planning-problem.v2",
            message="Built Problem failed the pure contract precheck",
        ) from error
    _validate_dag_v2(document)


def verify_problem_v2(problem: ImmutablePlanningProblemV2) -> None:
    """Verify v2 canonical bytes, metadata, semantics, and content hash."""

    try:
        decoded = json.loads(problem.canonical_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlanningProblemError(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="canonical_bytes",
            entity_id=problem.snapshot_id,
            expected_contract="canonical-json.v1 planning-problem.v2 object",
            message="Problem bytes are not valid canonical JSON",
        ) from error
    if not isinstance(decoded, dict):
        _reject(
            PlanningProblemErrorCode.MODEL_INVALID,
            field="canonical_bytes",
            entity_id=problem.snapshot_id,
            expected_contract="planning-problem.v2 JSON object",
            message="Problem bytes do not contain an object",
        )
    document = cast(dict[str, object], decoded)
    validate_built_problem_v2(document)
    if canonical_problem_v2_bytes(document) != problem.canonical_bytes:
        _reject(
            PlanningProblemErrorCode.HASH_MISMATCH,
            field="canonical_bytes",
            entity_id=problem.snapshot_id,
            expected_contract=PROBLEM_CANONICALIZATION_VERSION,
            message="Problem bytes are not in canonical order",
        )
    expected_hash = problem_v2_hash_for(document)
    if (
        document["problem_hash"] != expected_hash
        or problem.problem_hash != expected_hash
        or problem.snapshot_id != document["snapshot_id"]
        or problem.problem_builder_version != document["problem_builder_version"]
    ):
        _reject(
            PlanningProblemErrorCode.HASH_MISMATCH,
            field="problem_hash",
            entity_id=problem.snapshot_id,
            expected_contract="content-derived v2 Problem hash and matching metadata",
            message="Problem identity does not match its canonical content",
        )


__all__ = [
    "PLANNING_PROBLEM_VERSION",
    "PLANNING_PROBLEM_VERSION_V2",
    "PROBLEM_BUILDER_VERSION",
    "PROBLEM_BUILDER_VERSION_V2",
    "PROBLEM_CANONICALIZATION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION",
    "PROBLEM_HASH_PROJECTION_VERSION_V2",
    "PROBLEM_SCHEMA_SET_VERSION_V2",
    "canonical_problem_bytes",
    "canonical_problem_document",
    "canonical_problem_document_v2",
    "canonical_problem_v2_bytes",
    "problem_hash_for",
    "problem_hash_projection",
    "problem_v2_hash_for",
    "problem_v2_hash_projection",
    "validate_built_problem",
    "validate_built_problem_v2",
    "verify_problem",
    "verify_problem_v2",
]
