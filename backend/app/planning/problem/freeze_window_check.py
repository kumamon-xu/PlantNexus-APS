"""Emit machine-checkable TASK-P4-05 freeze/effective-lock evidence."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.execution_contracts import (
    contract_fingerprint,
    execution_event_fingerprint,
)
from app.domain.execution_fact_projection import (
    ProjectionScope,
    project_execution_event_batch,
)
from app.domain.workspace_contracts import workspace_fingerprint
from app.normalization import expand_orders
from app.planning.policy.freeze_window import (
    FREEZE_INTERVAL_SEMANTICS,
    SIMULATION_FREEZE_WINDOW_SECONDS,
    FreezePolicyError,
    FreezePolicyFailure,
    resolve_simulation_freeze_policy,
    simulation_replan_policy,
)
from app.planning.problem.builder import build_planning_problem_v2
from app.planning.problem.contracts import ImmutablePlanningProblemV2
from app.planning.problem.freeze_projection import (
    FreezeProjectionError,
    FreezeProjectionFailure,
    project_effective_locks,
)
from app.planning.problem.hashing import (
    PROBLEM_BUILDER_VERSION_V2,
    canonical_problem_document_v2,
    canonical_problem_v2_bytes,
    problem_v2_hash_for,
    verify_problem_v2,
)
from app.planning.validation.freeze_window_precheck import (
    validate_freeze_window_projection,
)
from app.snapshots import (
    ImmutablePlanningSnapshot,
    build_planning_snapshot,
    import_package_id_for,
)
from app.snapshots.projection import build_projected_snapshot


REPORT_VERSION = "p4-freeze-window-report.v1"
TASK_ID = "TASK-P4-05"
DIFF_BASE = "e7b96e28913e7eb5be63ae4265c09f8281456b1c"
TICK_SECONDS = 60
_CUTOFF = "2026-08-19T00:00:00Z"
_FROZEN_SHA256 = {
    "schemas/json/planning-problem.v2.schema.json": (
        "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8"
    ),
    "schemas/json/planning-policy.v2.schema.json": (
        "d56d092ebac445a359ab2b84ee5df8e810c53b2e0a2852fe6bc5a78290239668"
    ),
    "schemas/json/replan-request.schema.json": (
        "f16b7a22078a8c33495be009b6c934477b625c7aebc97966f4ec7c6b897104f9"
    ),
    "schemas/json/schedule-version.v2.schema.json": (
        "853c25f7211e233baa7c275e4de69cc67c070e1a4672afa1fc6b91a260df56d5"
    ),
    "backend/app/planning/problem/builder.py": (
        "c96a55a8d59da785a0109d83a75fbd2df2e2bfcccf234c07581019033af0f291"
    ),
    "backend/app/planning/problem/hashing.py": (
        "ec2b98ed59ed8b5a4d4588254e2a49d9b9c7df1c2b666f78f00104c39cc76b4e"
    ),
    "backend/app/planning/validation/problem_schedule_validator.py": (
        "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f"
    ),
    "schemas/rules/state-machines.v1.yaml": (
        "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7"
    ),
    "pyproject.toml": (
        "327b705255dc9792139aa690351601a1e6a6cba019920142adfa656d6902fe5e"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}


@dataclass(frozen=True, slots=True)
class FreezeWindowFixture:
    """Immutable synthetic inputs for projector and independent precheck tests."""

    base_snapshot: ImmutablePlanningSnapshot
    snapshot: ImmutablePlanningSnapshot
    problem: ImmutablePlanningProblemV2
    base_schedule: dict[str, object]
    policy: dict[str, object]
    first_operation_id: str
    second_operation_id: str


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _timestamp(seconds: int) -> str:
    return _format_utc(datetime(2026, 8, 19, tzinfo=UTC) + timedelta(seconds=seconds))


def _base_snapshot(root: Path) -> ImmutablePlanningSnapshot:
    document = cast(
        ImportPackageDocumentV2,
        json.loads(
            (root / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["records"]["execution_facts"] = []
    document["records"]["operation_locks"] = []
    document["package_id"] = import_package_id_for(document)
    quality = validate_import_package(document)
    if not quality.passed:
        raise ValueError("freeze fixture base failed standard Data Validation")
    expansion = expand_orders(document, quality.document)
    return build_planning_snapshot(
        document,
        quality.document,
        expansion,
        cutoff_at_utc=_CUTOFF,
    )


def _scope(snapshot: ImmutablePlanningSnapshot, suffix: str) -> ProjectionScope:
    factory_id = cast(
        str,
        cast(Sequence[Mapping[str, object]], snapshot.document["records"]["factories"])[
            0
        ]["factory_id"],
    )
    return ProjectionScope(
        factory_id=factory_id,
        planning_scope_id=f"scope-p4-freeze-{suffix}",
        authority_id=f"authority-p4-freeze-{suffix}",
        stream_id=f"stream-p4-freeze-{suffix}",
        stream_version="1.0.0",
    )


def _event(
    scope: ProjectionScope,
    *,
    event_type: str,
    payload: Mapping[str, object],
    references: set[tuple[str, str]],
    position: int,
    occurred_at_utc: str,
) -> dict[str, object]:
    document: dict[str, object] = {
        "execution_event_version": "execution-event.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "event_id": "pending",
        "event_type": event_type,
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "factory_id": scope.factory_id,
        "planning_scope_id": scope.planning_scope_id,
        "authority": {
            "authority_version": "execution-event-authority.v1",
            "authority_id": scope.authority_id,
            "authority_scope": (
                f"SIMULATION/{scope.factory_id}/{scope.planning_scope_id}"
            ),
            "source": {
                "source_system": "p4-freeze-machine-source",
                "source_version": "1.0.0",
                "source_record_id": scope.stream_id,
            },
            "decision": "AUTHORIZED_SIMULATION_SOURCE",
            "production_binding": False,
        },
        "source_stream": {
            "stream_id": scope.stream_id,
            "stream_version": scope.stream_version,
            "authority_id": scope.authority_id,
        },
        "source_position": position,
        "occurred_at_utc": occurred_at_utc,
        "received_at_utc": occurred_at_utc,
        "entity_refs": [
            {"entity_type": entity_type, "entity_id": entity_id}
            for entity_type, entity_id in sorted(references)
        ],
        "payload": {"kind": event_type, **dict(payload)},
        "synthetic": True,
        "synthetic_provenance": {
            "scenario_id": "SIM-P4-FREEZE-001",
            "scenario_version": "1.0.0",
            "factory_profile_id": "PROFILE-P4-FREEZE-001",
            "profile_version": "1.0.0",
            "generator_id": "plantnexus-p4-freeze-check",
            "generator_version": "1.0.0",
            "simulator_id": "plantnexus-p4-freeze-check",
            "simulator_version": "1.0.0",
            "seed": 20260827,
        },
        "production_binding": False,
        "correlation_id": f"correlation-p4-freeze-{position}",
        "event_fingerprint": "pending",
    }
    fingerprint = execution_event_fingerprint(document)
    document["event_fingerprint"] = fingerprint
    document["event_id"] = "execution-event-" + fingerprint.removeprefix("sha256:")
    return document


def _priority_facts(snapshot: ImmutablePlanningSnapshot) -> dict[str, dict[str, object]]:
    records = cast(Mapping[str, object], snapshot.document["records"])
    demands = cast(Sequence[Mapping[str, object]], records["demand_orders"])
    return {
        cast(str, demand["demand_order_id"]): {
            "priority_weight": 2,
            "source_system": "plantnexus-synthetic-policy",
            "source_version": "1.0.0",
            "source_record_id": (
                f"SIM-P4-FREEZE-PRIORITY-{demand['demand_order_id']}"
            ),
        }
        for demand in demands
    }


def _problem(snapshot: ImmutablePlanningSnapshot) -> ImmutablePlanningProblemV2:
    horizon_start = cast(str, snapshot.document["cutoff_at_utc"])
    horizon_end = _format_utc(_parse_utc(horizon_start) + timedelta(days=1))
    return build_planning_problem_v2(
        snapshot,
        priority_facts=_priority_facts(snapshot),
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=TICK_SECONDS,
        horizon_start_utc=horizon_start,
        horizon_end_utc=horizon_end,
    )


def _artifact_reference(
    *, document_version: str, artifact_id: str, fingerprint_seed: object
) -> dict[str, str]:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": contract_fingerprint({"fixture": fingerprint_seed}),
    }


def _schema_validator(root: Path, name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((root / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append(
            (cast(str, schema["$id"]), Resource.from_contents(schema))
        )
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def _published_base_schedule(
    root: Path,
    *,
    snapshot: ImmutablePlanningSnapshot,
    problem: ImmutablePlanningProblemV2,
) -> dict[str, object]:
    cutoff = _parse_utc(cast(str, snapshot.document["cutoff_at_utc"]))
    assignments: list[dict[str, object]] = []
    offset_seconds = 0
    for operation in cast(
        Sequence[Mapping[str, object]], problem.document["operation_instances"]
    ):
        option = cast(
            Sequence[Mapping[str, object]], operation["resource_options"]
        )[0]
        raw_duration = cast(int, option["final_duration_seconds"])
        duration_ticks = (raw_duration + TICK_SECONDS - 1) // TICK_SECONDS
        duration_seconds = duration_ticks * TICK_SECONDS
        start = cutoff + timedelta(seconds=offset_seconds)
        end = start + timedelta(seconds=duration_seconds)
        operation_id = cast(str, operation["operation_id"])
        snapshot_instance = next(
            item
            for item in cast(
                Sequence[Mapping[str, object]], snapshot.document["operation_instances"]
            )
            if item["operation_instance_id"] == operation_id
        )
        assignments.append(
            {
                "operation_id": operation_id,
                "resource_id": option["resource_id"],
                "start_tick": offset_seconds // TICK_SECONDS,
                "end_tick": offset_seconds // TICK_SECONDS + duration_ticks,
                "duration_ticks": duration_ticks,
                "start_at_utc": _format_utc(start),
                "end_at_utc": _format_utc(end),
                "duration_seconds": duration_seconds,
                "lock_ids": list(cast(Sequence[str], snapshot_instance["lock_ids"])),
                "execution_fact_ids": (
                    [snapshot_instance["execution_fact_id"]]
                    if isinstance(snapshot_instance.get("execution_fact_id"), str)
                    else []
                ),
            }
        )
        offset_seconds += duration_seconds
    content: dict[str, object] = {"assignments": assignments, "locks": []}
    validation_reference = _artifact_reference(
        document_version="validation-report.v2",
        artifact_id="validation-p4-freeze-base-001",
        fingerprint_seed={"problem_hash": problem.problem_hash, "content": content},
    )
    schedule: dict[str, object] = {
        "schedule_version_version": "schedule-version.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "schedule_version_id": "schedule-version-p4-freeze-base-001",
        "revision": 3,
        "state": "PUBLISHED",
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "synthetic": True,
        "synthetic_provenance": snapshot.document.get("synthetic_provenance"),
        "parent_schedule_version": None,
        "source_kind": "VALIDATED_SOLUTION",
        "lineage": {
            "planning_run_id": "planning-run-p4-freeze-base-001",
            "snapshot": {
                "document_version": "planning-snapshot.v2",
                "artifact_id": snapshot.snapshot_id,
                "fingerprint": snapshot.snapshot_hash,
            },
            "problem": {
                "document_version": "planning-problem.v2",
                "artifact_id": (
                    "planning-problem-v2-"
                    + problem.problem_hash.removeprefix("sha256:")
                ),
                "fingerprint": problem.problem_hash,
            },
            "planning_solution": _artifact_reference(
                document_version="planning-solution.v1",
                artifact_id="planning-solution-p4-freeze-base-001",
                fingerprint_seed=content,
            ),
            "validation_report": validation_reference,
            "kpi": _artifact_reference(
                document_version="kpi.v2",
                artifact_id="kpi-p4-freeze-base-001",
                fingerprint_seed={"content": content, "kind": "kpi"},
            ),
            "solver_report": _artifact_reference(
                document_version="solver-report.v1",
                artifact_id="solver-report-p4-freeze-base-001",
                fingerprint_seed={"content": content, "kind": "solver-report"},
            ),
            "code_commit": DIFF_BASE,
        },
        "content": content,
        "content_fingerprint": workspace_fingerprint(content),
        "validation": {
            "validation_report": validation_reference,
            "status": "PASS",
            "hard_violation_count": 0,
            "validated_at_utc": _timestamp(720),
        },
        "decision": {
            "decision": "APPROVED",
            "actor_ref": "actor:sim-p4-freeze-approver",
            "capability": "approve",
            "reason": "Approve the bounded synthetic freeze-window fixture.",
            "decided_at_utc": _timestamp(780),
            "audit_event_id": "audit-p4-freeze-approve-001",
        },
        "publication": {
            "publication_id": "publication-p4-freeze-base-001",
            "target": "SIMULATION_INTERNAL",
            "published_at_utc": _timestamp(840),
            "audit_event_id": "audit-p4-freeze-publish-001",
        },
        "superseded_by": None,
        "allowed_actions": ["view", "export"],
        "created_at_utc": _timestamp(600),
        "created_by_actor_ref": "actor:sim-p4-freeze-planner",
    }
    _schema_validator(root, "schedule-version.schema.json").validate(schedule)
    return schedule


def _policy_reference(policy: Mapping[str, object]) -> dict[str, str]:
    return {
        "document_version": "planning-policy.v2",
        "artifact_id": cast(str, policy["policy_id"]),
        "fingerprint": contract_fingerprint(policy),
    }


def _project_events(
    base: ImmutablePlanningSnapshot,
    *,
    suffix: str,
    events_factory: Callable[
        [ProjectionScope, Mapping[str, object], Mapping[str, object]],
        Sequence[Mapping[str, object]],
    ],
) -> ImmutablePlanningSnapshot:
    instances = cast(
        Sequence[Mapping[str, object]], base.document["operation_instances"]
    )
    first, second = instances[0], instances[1]
    scope = _scope(base, suffix)
    events = events_factory(scope, first, second)
    projected = project_execution_event_batch(
        base.document,
        full_prefix=events,
        after_position=0,
        scope=scope,
    )
    return build_projected_snapshot(projected.document)


def _primary_events(
    scope: ProjectionScope,
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> Sequence[Mapping[str, object]]:
    policy = simulation_replan_policy()
    policy_reference = _policy_reference(policy)
    first_id = cast(str, first["operation_instance_id"])
    second_id = cast(str, second["operation_instance_id"])
    first_option = cast(Sequence[Mapping[str, object]], first["resource_options"])[0]
    second_option = cast(Sequence[Mapping[str, object]], second["resource_options"])[0]
    first_resource = cast(str, first_option["resource_id"])
    second_resource = cast(str, second_option["resource_id"])
    first_seconds = (
        (cast(int, first_option["final_duration_seconds"]) + TICK_SECONDS - 1)
        // TICK_SECONDS
        * TICK_SECONDS
    )
    second_seconds = (
        (cast(int, second_option["final_duration_seconds"]) + TICK_SECONDS - 1)
        // TICK_SECONDS
        * TICK_SECONDS
    )
    return (
        _event(
            scope,
            event_type="OPERATION_STARTED",
            payload={
                "operation_id": first_id,
                "resource_id": first_resource,
                "actual_start_at_utc": _CUTOFF,
            },
            references={("OPERATION", first_id), ("RESOURCE", first_resource)},
            position=1,
            occurred_at_utc=_CUTOFF,
        ),
        _event(
            scope,
            event_type="LOCK_CREATED",
            payload={
                "lock_id": "LOCK-P4-FREEZE-RUNNING-HARD-001",
                "operation_id": first_id,
                "lock_type": "HARD",
                "resource_id": first_resource,
                "start_at_utc": _CUTOFF,
                "end_at_utc": _timestamp(first_seconds),
                "policy_reference": policy_reference,
            },
            references={
                ("OPERATION", first_id),
                ("RESOURCE", first_resource),
                ("OPERATION_LOCK", "LOCK-P4-FREEZE-RUNNING-HARD-001"),
            },
            position=2,
            occurred_at_utc=_CUTOFF,
        ),
        _event(
            scope,
            event_type="LOCK_CREATED",
            payload={
                "lock_id": "LOCK-P4-FREEZE-NOT-STARTED-HARD-001",
                "operation_id": second_id,
                "lock_type": "HARD",
                "resource_id": second_resource,
                "start_at_utc": _timestamp(first_seconds),
                "end_at_utc": _timestamp(first_seconds + second_seconds),
                "policy_reference": policy_reference,
            },
            references={
                ("OPERATION", second_id),
                ("RESOURCE", second_resource),
                ("OPERATION_LOCK", "LOCK-P4-FREEZE-NOT-STARTED-HARD-001"),
            },
            position=3,
            occurred_at_utc=_CUTOFF,
        ),
        _event(
            scope,
            event_type="LOCK_CREATED",
            payload={
                "lock_id": "LOCK-P4-FREEZE-NOT-STARTED-SOFT-001",
                "operation_id": second_id,
                "lock_type": "SOFT",
                "resource_id": second_resource,
                "start_at_utc": _timestamp(first_seconds),
                "end_at_utc": _timestamp(first_seconds + second_seconds),
                "policy_reference": policy_reference,
            },
            references={
                ("OPERATION", second_id),
                ("RESOURCE", second_resource),
                ("OPERATION_LOCK", "LOCK-P4-FREEZE-NOT-STARTED-SOFT-001"),
            },
            position=4,
            occurred_at_utc=_CUTOFF,
        ),
    )


def _completed_events(
    scope: ProjectionScope,
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> Sequence[Mapping[str, object]]:
    del second
    first_id = cast(str, first["operation_instance_id"])
    first_option = cast(Sequence[Mapping[str, object]], first["resource_options"])[0]
    resource_id = cast(str, first_option["resource_id"])
    duration = (
        (cast(int, first_option["final_duration_seconds"]) + TICK_SECONDS - 1)
        // TICK_SECONDS
        * TICK_SECONDS
    )
    return (
        _event(
            scope,
            event_type="OPERATION_STARTED",
            payload={
                "operation_id": first_id,
                "resource_id": resource_id,
                "actual_start_at_utc": _CUTOFF,
            },
            references={("OPERATION", first_id), ("RESOURCE", resource_id)},
            position=1,
            occurred_at_utc=_CUTOFF,
        ),
        _event(
            scope,
            event_type="OPERATION_COMPLETED",
            payload={
                "operation_id": first_id,
                "resource_id": resource_id,
                "actual_start_at_utc": _CUTOFF,
                "actual_end_at_utc": _timestamp(duration),
            },
            references={("OPERATION", first_id), ("RESOURCE", resource_id)},
            position=2,
            occurred_at_utc=_timestamp(duration),
        ),
    )


def build_freeze_window_fixture(
    root: Path, *, completed: bool = False
) -> FreezeWindowFixture:
    """Build an event-derived Snapshot/Problem and a strict PUBLISHED base."""

    base_snapshot = _base_snapshot(root)
    base_problem = _problem(base_snapshot)
    base_schedule = _published_base_schedule(
        root, snapshot=base_snapshot, problem=base_problem
    )
    snapshot = _project_events(
        base_snapshot,
        suffix="completed" if completed else "primary",
        events_factory=_completed_events if completed else _primary_events,
    )
    problem = _problem(snapshot)
    instances = cast(
        Sequence[Mapping[str, object]], base_snapshot.document["operation_instances"]
    )
    return FreezeWindowFixture(
        base_snapshot=base_snapshot,
        snapshot=snapshot,
        problem=problem,
        base_schedule=base_schedule,
        policy=simulation_replan_policy(),
        first_operation_id=cast(str, instances[0]["operation_instance_id"]),
        second_operation_id=cast(str, instances[1]["operation_instance_id"]),
    )


def move_base_assignment(
    base_schedule: Mapping[str, object],
    *,
    operation_id: str,
    start_at_utc: str,
) -> dict[str, object]:
    """Copy one fixture base and move an assignment while preserving duration."""

    document = cast(dict[str, object], deepcopy(base_schedule))
    content = cast(dict[str, object], document["content"])
    assignments = cast(list[dict[str, object]], content["assignments"])
    assignment = next(
        item for item in assignments if item["operation_id"] == operation_id
    )
    start = _parse_utc(start_at_utc)
    duration = cast(int, assignment["duration_seconds"])
    assignment["start_at_utc"] = start_at_utc
    assignment["end_at_utc"] = _format_utc(start + timedelta(seconds=duration))
    assignment["start_tick"] = max(
        0, int((start - _parse_utc(_CUTOFF)).total_seconds()) // TICK_SECONDS
    )
    assignment["end_tick"] = cast(int, assignment["start_tick"]) + cast(
        int, assignment["duration_ticks"]
    )
    document["content_fingerprint"] = workspace_fingerprint(content)
    return document


def omit_base_assignment(
    base_schedule: Mapping[str, object], *, operation_id: str
) -> dict[str, object]:
    document = cast(dict[str, object], deepcopy(base_schedule))
    content = cast(dict[str, object], document["content"])
    assignments = cast(list[dict[str, object]], content["assignments"])
    content["assignments"] = [
        assignment
        for assignment in assignments
        if assignment["operation_id"] != operation_id
    ]
    document["content_fingerprint"] = workspace_fingerprint(content)
    return document


def rehash_problem_v2(document: Mapping[str, object]) -> ImmutablePlanningProblemV2:
    """Rebuild a tampered test Problem with an internally valid new identity."""

    canonical = canonical_problem_document_v2(document)
    canonical["problem_hash"] = problem_v2_hash_for(canonical)
    problem = ImmutablePlanningProblemV2(
        canonical_bytes=canonical_problem_v2_bytes(canonical),
        problem_hash=cast(str, canonical["problem_hash"]),
        snapshot_id=cast(str, canonical["snapshot_id"]),
        problem_builder_version=cast(str, canonical["problem_builder_version"]),
    )
    verify_problem_v2(problem)
    return problem


def _expect_projection_failure(
    reason: FreezeProjectionFailure, operation: Callable[[], object]
) -> None:
    try:
        operation()
    except FreezeProjectionError as error:
        if error.reason is reason:
            return
        raise ValueError(f"unexpected projection failure {error.reason.value}") from error
    raise ValueError(f"expected projection failure {reason.value}")


def _frozen_input_check(root: Path) -> dict[str, object]:
    observed = {
        relative: sha256((root / relative).read_bytes()).hexdigest()
        for relative in _FROZEN_SHA256
    }
    _ensure(observed == _FROZEN_SHA256, "frozen P2/P4 input bytes changed")
    projector_source = (
        root / "backend/app/planning/problem/freeze_projection.py"
    ).read_text(encoding="utf-8")
    precheck_source = (
        root / "backend/app/planning/validation/freeze_window_precheck.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(projector_source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    forbidden_import_prefixes = (
        "ort" + "ools",
        "app.planning." + "backends",
        "app." + "infrastructure",
        "app." + "api",
    )
    _ensure(
        all(
            not any(name.startswith(prefix) for prefix in forbidden_import_prefixes)
            for name in imported
        ),
        "projector crossed the solver, persistence, or API dependency boundary",
    )
    for forbidden in (
        "create_schedule_version",
        "ScheduleVersionRepository",
    ):
        _ensure(
            forbidden not in projector_source,
            f"projector crossed solver/version boundary: {forbidden}",
        )
    _ensure(
        "freeze_projection" not in precheck_source,
        "independent precheck imported the projector",
    )
    return {
        "frozen_files": len(observed),
        "problem_v2_schema_sha256": observed[
            "schemas/json/planning-problem.v2.schema.json"
        ],
        "formal_validator_sha256": observed[
            "backend/app/planning/validation/problem_schedule_validator.py"
        ],
        "solver_imports": 0,
        "schedule_version_mutations": 0,
    }


def run_freeze_window_checks(root: Path) -> dict[str, object]:
    frozen = _frozen_input_check(root)
    primary = build_freeze_window_fixture(root)
    snapshot_bytes = primary.snapshot.canonical_bytes
    problem_bytes = primary.problem.canonical_bytes
    base_bytes = json.dumps(primary.base_schedule, sort_keys=True)
    projection = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
    )
    document = projection.document
    precheck = validate_freeze_window_projection(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
        projection=document,
    )
    _ensure(precheck["status"] == "PASS", "independent freeze precheck failed")
    _ensure(len(cast(list[object], document["running_protections"])) == 1, "RUNNING missing")
    _ensure(len(cast(list[object], document["explicit_hard_locks"])) == 2, "HARD missing")
    _ensure(len(cast(list[object], document["soft_locks"])) == 1, "SOFT missing")
    _ensure(
        len(cast(list[object], document["freeze_derived_hard_locks"])) == 1,
        "freeze-derived HARD missing",
    )
    _ensure(
        primary.snapshot.canonical_bytes == snapshot_bytes
        and primary.problem.canonical_bytes == problem_bytes
        and json.dumps(primary.base_schedule, sort_keys=True) == base_bytes,
        "immutable input bytes changed during projection",
    )

    completed = build_freeze_window_fixture(root, completed=True)
    completed_projection = project_effective_locks(
        snapshot=completed.snapshot,
        problem=completed.problem,
        base_schedule=completed.base_schedule,
        policy=completed.policy,
    ).document
    _ensure(
        completed_projection["completed_operation_ids"]
        == [completed.first_operation_id],
        "COMPLETED operation was not classified from Snapshot authority",
    )
    _ensure(
        len(cast(list[object], completed_projection["completed_protections"])) == 1,
        "COMPLETED execution fact evidence is incomplete",
    )

    cutoff = _parse_utc(cast(str, primary.snapshot.document["cutoff_at_utc"]))
    boundary_base = move_base_assignment(
        primary.base_schedule,
        operation_id=primary.second_operation_id,
        start_at_utc=_format_utc(
            cutoff + timedelta(seconds=SIMULATION_FREEZE_WINDOW_SECONDS)
        ),
    )
    boundary_projection = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=boundary_base,
        policy=primary.policy,
    ).document
    _ensure(
        boundary_projection["outside_freeze_operation_ids"]
        == [primary.second_operation_id]
        and boundary_projection["freeze_derived_hard_locks"] == [],
        "half-open freeze_end boundary was not excluded",
    )

    added_base = omit_base_assignment(
        primary.base_schedule, operation_id=primary.second_operation_id
    )
    added_projection = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=added_base,
        policy=primary.policy,
    ).document
    _ensure(
        added_projection["added_operation_ids"] == [primary.second_operation_id],
        "new active operation was not classified as ADDED",
    )

    conflicting_base = move_base_assignment(
        primary.base_schedule,
        operation_id=primary.second_operation_id,
        start_at_utc=_timestamp(480),
    )
    _expect_projection_failure(
        FreezeProjectionFailure.FREEZE_LOCK_CONFLICT,
        lambda: project_effective_locks(
            snapshot=primary.snapshot,
            problem=primary.problem,
            base_schedule=conflicting_base,
            policy=primary.policy,
        ),
    )
    stale_base = move_base_assignment(
        completed.base_schedule,
        operation_id=completed.second_operation_id,
        start_at_utc=_CUTOFF,
    )
    _expect_projection_failure(
        FreezeProjectionFailure.STALE_BASE,
        lambda: project_effective_locks(
            snapshot=completed.snapshot,
            problem=completed.problem,
            base_schedule=stale_base,
            policy=completed.policy,
        ),
    )
    production_base = cast(dict[str, object], deepcopy(primary.base_schedule))
    production_base["data_plane"] = "PRODUCTION"
    _expect_projection_failure(
        FreezeProjectionFailure.PLANE_MISMATCH,
        lambda: project_effective_locks(
            snapshot=primary.snapshot,
            problem=primary.problem,
            base_schedule=production_base,
            policy=primary.policy,
        ),
    )

    repeated = project_effective_locks(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
    )
    _ensure(
        repeated.canonical_bytes == projection.canonical_bytes,
        "same immutable inputs did not replay byte-exactly",
    )
    tampered = cast(dict[str, object], deepcopy(document))
    cast(list[dict[str, object]], tampered["freeze_derived_hard_locks"])[0][
        "resource_id"
    ] = "RESOURCE-TAMPERED"
    mutation_report = validate_freeze_window_projection(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
        projection=tampered,
    )
    _ensure(
        mutation_report["status"] == "FAIL"
        and cast(int, mutation_report["hard_violation_count"]) >= 1,
        "independent precheck accepted a mutated effective lock",
    )

    rejected_policy = cast(dict[str, object], deepcopy(primary.policy))
    rejected_policy["data_plane"] = "PRODUCTION"
    try:
        resolve_simulation_freeze_policy(rejected_policy, primary.snapshot)
    except FreezePolicyError as error:
        _ensure(
            error.reason is FreezePolicyFailure.PRODUCTION_NOT_AUTHORIZED,
            "Production policy rejection reason drifted",
        )
    else:
        raise ValueError("Production freeze policy was silently defaulted")

    resolved = resolve_simulation_freeze_policy(primary.policy, primary.snapshot)
    boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "freeze_policy": "SIM-P4-FREEZE-001_VERSIONED_900_SECONDS",
        "interval_semantics": FREEZE_INTERVAL_SEMANTICS,
        "production_freeze_default": "OPEN_005_NOT_FORMED",
        "problem_v2_bytes": "UNCHANGED_REFERENCED_CARRIER",
        "solver_obj_002_change_report": "NOT_IMPLEMENTED_BY_TASK",
        "schedule_version_or_state_transition": "NONE",
        "formal_validator_c001_c011": "UNCHANGED_INDEPENDENT_PRECHECK",
        "p4_06_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
    checks = [
        _pass("frozen-schema-problem-validator-state-and-dependencies", frozen),
        _pass(
            "versioned-simulation-policy-and-snapshot-cutoff-resolution",
            {
                "policy_id": resolved.policy_id,
                "policy_revision": resolved.policy_revision,
                "freeze_policy_id": resolved.freeze_policy_id,
                "freeze_policy_revision": resolved.freeze_policy_revision,
                "window_seconds": resolved.window_seconds,
                "effective_from_utc": resolved.effective_from_utc,
                "effective_until_utc": resolved.effective_until_utc,
            },
        ),
        _pass(
            "completed-running-hard-soft-and-freeze-effective-projection",
            {
                "completed": 1,
                "running": 1,
                "explicit_hard": 2,
                "freeze_derived_hard": 1,
                "soft": 1,
                "projection_fingerprint": projection.projection_fingerprint,
            },
        ),
        _pass(
            "half-open-boundary-added-and-immutable-inputs",
            {
                "freeze_end_excluded": True,
                "added_operations": 1,
                "snapshot_bytes_preserved": True,
                "problem_bytes_preserved": True,
                "base_bytes_preserved": True,
            },
        ),
        _pass(
            "conflict-stale-plane-and-production-default-rejections",
            {
                "freeze_hard_conflicts": 1,
                "stale_bases": 1,
                "cross_plane_inputs": 1,
                "production_policy_defaults": 0,
            },
        ),
        _pass(
            "independent-precheck-mutation-and-byte-exact-replay",
            {
                "positive_status": precheck["status"],
                "mutation_status": mutation_report["status"],
                "mutation_violations": mutation_report["hard_violation_count"],
                "deterministic_replays": 2,
            },
        ),
        _pass("p4-p5-production-capability-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "diff_base": DIFF_BASE,
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "artifacts": {
            "new_snapshot_id": primary.snapshot.snapshot_id,
            "new_snapshot_hash": primary.snapshot.snapshot_hash,
            "new_problem_hash": primary.problem.problem_hash,
            "base_schedule_version_id": primary.base_schedule["schedule_version_id"],
            "base_content_fingerprint": primary.base_schedule["content_fingerprint"],
            "planning_policy_fingerprint": contract_fingerprint(primary.policy),
            "freeze_policy_fingerprint": resolved.freeze_policy_fingerprint,
            "effective_lock_projection_fingerprint": projection.projection_fingerprint,
            "precheck_report_id": precheck["report_id"],
        },
        "counts": {
            "simulation_policies": 1,
            "event_derived_snapshots": 2,
            "positive_projection_vectors": 4,
            "negative_projection_vectors": 4,
            "independent_mutation_vectors": 1,
            "machine_checks": len(checks),
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_freeze_window_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "error_type": type(error).__name__,
            "error_message": "freeze-window evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "REPORT_VERSION",
    "FreezeWindowFixture",
    "build_freeze_window_fixture",
    "main",
    "move_base_assignment",
    "omit_base_assignment",
    "rehash_problem_v2",
    "run_freeze_window_checks",
]
