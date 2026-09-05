"""TEST-P8-PLANNING-RUN-001 frozen machine-contract implementation proof."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import yaml

from app.application.planning_runs import (
    PlanningRunOrchestrationService,
    PlanningRunTransitionCommand,
)
from app.application.planning_run_check import run_checks
from app.domain.planning_run import (
    PLANNING_RUN_STATES,
    PLANNING_RUN_TERMINAL_STATES,
    PLANNING_RUN_TRANSITIONS,
    PlanningRunActionResult,
)
from backend.tests.contract.p8_planning_run_support import (
    InMemoryPlanningRunRepository,
    canonical_ingress_record,
    command_context,
    schemas,
)


ROOT = Path(__file__).resolve().parents[3]
PLANNING_RUN_SCHEMA_SHA256 = (
    "3d5f4d21ccf3bf227a42530e59c4b4df456353a77801901bb9c5e695f206861a"
)
PATH_TO_STATE = {
    "CREATED": (),
    "INGESTING": ("INGESTING",),
    "VALIDATING": ("INGESTING", "VALIDATING"),
    "SNAPSHOTTED": ("INGESTING", "VALIDATING", "SNAPSHOTTED"),
    "BUILDING": ("INGESTING", "VALIDATING", "SNAPSHOTTED", "BUILDING"),
    "SOLVING": (
        "INGESTING",
        "VALIDATING",
        "SNAPSHOTTED",
        "BUILDING",
        "SOLVING",
    ),
    "SOLVED": (
        "INGESTING",
        "VALIDATING",
        "SNAPSHOTTED",
        "BUILDING",
        "SOLVING",
        "SOLVED",
    ),
    "VERIFYING": (
        "INGESTING",
        "VALIDATING",
        "SNAPSHOTTED",
        "BUILDING",
        "SOLVING",
        "SOLVED",
        "VERIFYING",
    ),
}
ATTEMPT_TARGETS = {
    "BUILDING",
    "SOLVING",
    "SOLVED",
    "VERIFYING",
    "COMPLETED",
    "MODEL_INVALID",
    "INFEASIBLE",
    "NO_SOLUTION_WITHIN_LIMIT",
    "VALIDATION_FAILED",
    "CANCELLED",
    "FAILED",
    "DATA_REJECTED",
}


def _reference(document_version: str, marker: str) -> dict[str, str]:
    return {
        "document_version": document_version,
        "artifact_id": f"P8-{marker}",
        "fingerprint": f"sha256:{marker.lower()[0] * 64}",
    }


def _artifacts(
    target: str,
    *,
    current: Mapping[str, object],
    prepared: Mapping[str, object],
) -> dict[str, object]:
    result = dict(current)
    if target in {"SNAPSHOTTED", "BUILDING"}:
        result.update(
            import_quality_report=prepared["import_quality_report"],
            snapshot=prepared["snapshot"],
        )
    elif target == "DATA_REJECTED":
        result.update(
            import_quality_report=prepared["import_quality_report"],
            snapshot=None,
            problem=None,
            planning_solution=None,
            solver_report=None,
            validation_report=None,
            schedule_version=None,
        )
    elif target == "SOLVING":
        result.update(
            import_quality_report=prepared["import_quality_report"],
            snapshot=prepared["snapshot"],
            problem=prepared["problem"],
        )
    elif target in {"SOLVED", "VERIFYING"}:
        result.update(
            import_quality_report=prepared["import_quality_report"],
            snapshot=prepared["snapshot"],
            problem=prepared["problem"],
            planning_solution=_reference("planning-solution.v1", "A-SOLUTION"),
            solver_report=_reference("solver-report.v2", "B-SOLVER"),
        )
    elif target in {"INFEASIBLE", "NO_SOLUTION_WITHIN_LIMIT"}:
        result.update(
            import_quality_report=prepared["import_quality_report"],
            snapshot=prepared["snapshot"],
            problem=prepared["problem"],
            planning_solution=None,
            solver_report=_reference("solver-report.v2", "B-SOLVER"),
            validation_report=None,
            schedule_version=None,
        )
    elif target in {"VALIDATION_FAILED", "COMPLETED"}:
        result.update(
            import_quality_report=prepared["import_quality_report"],
            snapshot=prepared["snapshot"],
            problem=prepared["problem"],
            planning_solution=_reference("planning-solution.v1", "A-SOLUTION"),
            solver_report=_reference("solver-report.v2", "B-SOLVER"),
            validation_report=_reference("validation-report.v2", "C-VALIDATION"),
            schedule_version=(
                _reference("schedule-version.v2", "D-SCHEDULE")
                if target == "COMPLETED"
                else None
            ),
        )
    return result


def _materialized() -> tuple[
    PlanningRunOrchestrationService,
    PlanningRunActionResult,
]:
    service = PlanningRunOrchestrationService(
        schemas=schemas(), repository=InMemoryPlanningRunRepository()
    )
    return service, service.materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )


def _transition(
    service: PlanningRunOrchestrationService,
    result: PlanningRunActionResult,
    target: str,
    *,
    sequence: int,
) -> PlanningRunActionResult:
    current = result.aggregate.document
    prepared = result.aggregate.prepared_artifacts
    model = service.read(
        cast(str, current["planning_run_id"]), context=command_context()
    )
    attempt_id = (
        cast(str, model.attempts[-1].document["attempt_id"])
        if target in ATTEMPT_TARGETS
        else None
    )
    return service.transition(
        PlanningRunTransitionCommand(
            planning_run_id=cast(str, current["planning_run_id"]),
            expected_revision=cast(int, current["revision"]),
            expected_state=cast(str, current["state"]),
            expected_run_fingerprint=cast(str, current["run_fingerprint"]),
            to_state=target,
            idempotency_key=f"p8-contract-{sequence:02d}-{target.lower()}",
            reason=f"Exercise frozen PlanningRun pair to {target}.",
            artifacts=_artifacts(
                target,
                current=cast(Mapping[str, object], current["artifacts"]),
                prepared=prepared,
            ),
            attempt_id=attempt_id,
        ),
        context=command_context(occurred_at_utc=f"2026-09-05T00:{sequence:02d}:00Z"),
    )


def _at_state(
    target: str,
) -> tuple[PlanningRunOrchestrationService, PlanningRunActionResult]:
    service, result = _materialized()
    for sequence, state in enumerate(PATH_TO_STATE[target], start=2):
        result = _transition(service, result, state, sequence=sequence)
    return service, result


def test_domain_constants_are_exactly_the_frozen_registry_and_schema() -> None:
    registry = cast(
        dict[str, Any],
        yaml.safe_load(
            (ROOT / "schemas" / "rules" / "state-machines.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    machine = next(
        item for item in registry["machines"] if item["machine"] == "PLANNING_RUN"
    )
    transitions = {
        (cast(str, item["from"]), cast(str, item["to"]))
        for item in machine["transitions"]
    }

    assert PLANNING_RUN_STATES == frozenset(machine["states"])
    assert PLANNING_RUN_TERMINAL_STATES == frozenset(machine["terminal_states"])
    assert PLANNING_RUN_TRANSITIONS == transitions
    assert len(PLANNING_RUN_STATES) == 16
    assert len(PLANNING_RUN_TRANSITIONS) == 31
    assert all(source != target for source, target in PLANNING_RUN_TRANSITIONS)
    assert (
        sha256(
            (ROOT / "schemas/json/planning-run.schema.json").read_bytes()
        ).hexdigest()
        == PLANNING_RUN_SCHEMA_SHA256
    )


def test_all_31_frozen_pairs_are_executable_without_a_self_transition() -> None:
    observed: set[tuple[str, str]] = set()
    for index, (source, target) in enumerate(
        sorted(PLANNING_RUN_TRANSITIONS), start=20
    ):
        service, current = _at_state(source)
        transitioned = _transition(service, current, target, sequence=index)
        transition = cast(
            Mapping[str, object], transitioned.aggregate.document["last_transition"]
        )
        observed.add((cast(str, transition["from_state"]), target))
        assert transitioned.aggregate.document["state"] == target
        assert transitioned.aggregate.document["terminal"] is (
            target in PLANNING_RUN_TERMINAL_STATES
        )
    assert observed == PLANNING_RUN_TRANSITIONS


def test_queue_ready_carrier_is_strict_and_contains_no_executable_selector() -> None:
    _service, materialized = _materialized()
    assert materialized.work_item is not None
    work = materialized.work_item.document

    assert set(work) == {
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
    serialized = materialized.work_item.canonical_bytes.lower()
    for forbidden in (
        b'"module"',
        b'"class"',
        b'"entry_point"',
        b'"artifact_path"',
        b'"plugin_id"',
        b'"callable"',
    ):
        assert forbidden not in serialized
    assert (
        work["runtime_resolution"]
        == materialized.aggregate.document["runtime_resolution"]
    )
    assert work["inputs"] == materialized.aggregate.document["inputs"]


def test_machine_readable_orchestration_report_passes() -> None:
    report = run_checks(ROOT)

    assert report["status"] == "PASS"
    assert report["issues"] == []
    assert report["task_id"] == "TASK-P8-04"
